import json
import re
import httpx
from typing import Dict, Any, Optional
from flakeforge.config import settings
from flakeforge.llm.prompts import SYSTEM_PROMPT, build_user_prompt

class NvidiaNimClient:
    """Client for NVIDIA NIM (build.nvidia.com) OpenAI-compatible API

    featuring NVIDIA Nemotron models with live production execution.
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

    async def synthesize_repair(
        self,
        original_code: str,
        seed: int,
        error: str,
        trace_summary: str
    ) -> Dict[str, Any]:
        """Calls NVIDIA NIM live API. Fails loudly on API/auth errors in production."""
        # Offline mode only when explicitly requested for offline unit tests
        if self.api_key.strip().lower() in ("offline", "mock"):
            return self._offline_synthesize(original_code, error)

        if not self.api_key or not self.api_key.strip():
            raise ValueError(
                "NVIDIA_API_KEY is not set. Please provide your NVIDIA NIM API key "
                "(from https://build.nvidia.com) in your environment variables."
            )

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key.strip()}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        user_content = build_user_prompt(original_code, seed, error, trace_summary)

        payload = {
            "model": self.model,
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
                raise RuntimeError(
                    f"NVIDIA NIM API Error ({resp.status_code}): {err_text}"
                )

            data = resp.json()

        try:
            raw_content = data["choices"][0]["message"]["content"]
            parsed_result = self._extract_json(raw_content)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to parse structured JSON from NVIDIA NIM output: {str(exc)}\n"
                f"Raw Response: {data.get('choices', [{}])[0].get('message', {}).get('content', '')[:300]}"
            )

        # Sanitize code (strip accidental markdown fences inside the JSON string)
        if "fixed_code" in parsed_result:
            parsed_result["fixed_code"] = self._clean_code(parsed_result["fixed_code"])

        parsed_result["_meta"] = {
            "live": True,
            "provider": "NVIDIA NIM",
            "model": self.model
        }
        return parsed_result

    @staticmethod
    def _extract_json(raw_text: str) -> Dict[str, Any]:
        """Extracts JSON object even if enclosed in markdown code fences or conversational text."""
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
        """Strips markdown code fences from synthesized Python code."""
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
        """Deterministic offline synthesizer used strictly for pytest unit testing."""
        return {
            "diagnosis": "Offline mode unit test fallback.",
            "root_cause_pattern": "READ_AFTER_WRITE_HAZARD",
            "fixed_code": original_code,
            "explanation": "Offline placeholder.",
            "_meta": {"live": False, "provider": "offline"}
        }