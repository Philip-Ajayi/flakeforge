import json
import re
import httpx
from typing import Dict, Any, Optional, List
from flakeforge.config import settings
from flakeforge.llm.prompts import SYSTEM_PROMPT, build_user_prompt

# Active flagship models hosted on integrate.api.nvidia.com
ACTIVE_FALLBACK_MODELS = [
    "nvidia/nemotron-3-ultra-550b-a55b",
    "z-ai/glm-5.3",
    "deepseek-ai/deepseek-v4.1-flash",
    "meta/llama-3.1-8b-instruct",
]

class NvidiaNimClient:
    """Client for NVIDIA NIM with dynamic /v1/models catalog discovery

    and automatic failover when models reach End-of-Life (HTTP 410) or 404.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = api_key or settings.nvidia_api_key
        self.base_url = (base_url or settings.nvidia_base_url).rstrip("/")
        self.model = model or settings.nvidia_model

    async def _discover_live_model(self) -> Optional[str]:
        """Queries /v1/models directly from NVIDIA to discover active models for this account."""
        url = f"{self.base_url}/models"
        headers = {
            "Authorization": f"Bearer {self.api_key.strip()}",
            "Accept": "application/json"
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    all_ids = [m["id"] for m in data.get("data", []) if "id" in m]

                    # Filter out non-chat models (embeddings, audio, vision-only, etc.)
                    chat_models = [
                        m for m in all_ids
                        if not any(x in m.lower() for x in ["embed", "rerank", "clip", "whisper", "tts", "sdxl", "flux"])
                    ]

                    # Prioritize top Nemotron / reasoning models
                    for keyword in ["nemotron-3-ultra", "nemotron", "glm", "deepseek", "instruct"]:
                        for m in chat_models:
                            if keyword in m.lower():
                                return m

                    if chat_models:
                        return chat_models[0]
        except Exception:
            pass
        return None

    async def synthesize_repair(
        self,
        original_code: str,
        seed: int,
        error: str,
        trace_summary: str
    ) -> Dict[str, Any]:
        if self.api_key.strip().lower() in ("offline", "mock"):
            return self._offline_synthesize(original_code, error)

        if not self.api_key or not self.api_key.strip():
            raise ValueError(
                "NVIDIA_API_KEY is not set. Please provide your NVIDIA NIM API key "
                "(from https://build.nvidia.com) in your environment variables."
            )

        # Build candidate queue starting with the requested model
        models_to_try = [self.model]
        for fallback in ACTIVE_FALLBACK_MODELS:
            if fallback not in models_to_try:
                models_to_try.append(fallback)

        last_error = None
        for i, candidate_model in enumerate(models_to_try):
            try:
                result = await self._call_nim(candidate_model, original_code, seed, error, trace_summary)
                self.model = candidate_model
                return result
            except RuntimeError as exc:
                last_error = exc
                err_str = str(exc)

                # Check if model is retired (410) or not provisioned (404)
                if "410" in err_str or "404" in err_str:
                    # Dynamically inspect what is live in the account catalog
                    live_model = await self._discover_live_model()
                    if live_model and live_model not in models_to_try:
                        models_to_try.insert(i + 1, live_model)
                    continue
                else:
                    raise exc

        raise last_error

    async def _call_nim(self, model: str, original_code: str, seed: int, error: str, trace_summary: str) -> Dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key.strip()}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        user_content = build_user_prompt(original_code, seed, error, trace_summary)

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.1,
            "max_tokens": 3000
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(url, headers=headers, json=payload)

            if resp.status_code != 200:
                err_text = resp.text
                try:
                    err_json = resp.json()
                    err_text = err_json.get("message") or err_json.get("detail") or resp.text
                except Exception:
                    pass
                raise RuntimeError(f"NVIDIA NIM API Error ({resp.status_code}): {err_text}")

            data = resp.json()

        raw_content = data["choices"][0]["message"]["content"]
        parsed_result = self._extract_json(raw_content)

        if "fixed_code" in parsed_result:
            parsed_result["fixed_code"] = self._clean_code(parsed_result["fixed_code"])

        parsed_result["_meta"] = {
            "live": True,
            "provider": "NVIDIA NIM",
            "model": model
        }
        return parsed_result

    @staticmethod
    def _extract_json(raw_text: str) -> Dict[str, Any]:
        text = raw_text.strip()
        if "```" in text:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
            if match:
                text = match.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(text[start:end + 1])
            raise

    @staticmethod
    def _clean_code(code_str: str) -> str:
        code_str = code_str.strip()
        if code_str.startswith("```"):
            lines = code_str.splitlines()
            if lines[0].startswith("```"):
                lines = lines[:-1]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            code_str = "\n".join(lines).strip()
        return code_str

    def _offline_synthesize(self, original_code: str, error: str) -> Dict[str, Any]:
        return {
            "diagnosis": "Offline mode unit test fallback.",
            "root_cause_pattern": "READ_AFTER_WRITE_HAZARD",
            "fixed_code": original_code,
            "explanation": "Offline placeholder.",
            "_meta": {"live": False, "provider": "offline"}
        }