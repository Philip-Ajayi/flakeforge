import json
import re
import httpx
from typing import Dict, Any, Optional
from flakeforge.config import settings
from flakeforge.llm.prompts import SYSTEM_PROMPT, build_user_prompt

# Recommended models hosted on integrate.api.nvidia.com
SUPPORTED_MODELS = [
    "meta/llama-3.3-70b-instruct",
    "nvidia/nemotron-3-ultra-550b-a55b",
    "meta/llama-3.1-8b-instruct",
    "mistralai/mistral-large-2407"
]

class NvidiaNimClient:
    """Client for NVIDIA NIM (build.nvidia.com) with resilient auto-model recovery."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = api_key or settings.nvidia_api_key
        self.base_url = (base_url or settings.nvidia_base_url).rstrip("/")
        self.model = model or settings.nvidia_model

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

        # Try primary model first, fallback if retired with 404
        models_to_try = [self.model] + [m for m in SUPPORTED_MODELS if m != self.model]

        last_error = None
        for candidate_model in models_to_try:
            try:
                result = await self._call_nim(candidate_model, original_code, seed, error, trace_summary)
                self.model = candidate_model
                return result
            except RuntimeError as exc:
                last_error = exc
                if "404" in str(exc) and "Function" in str(exc):
                    # Retired model detected, try next available model in catalog
                    continue
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
                lines = lines[1:]
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