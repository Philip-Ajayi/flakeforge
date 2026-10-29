import pytest
from flakeforge.llm.nim_client import NvidiaNimClient

@pytest.mark.asyncio
async def test_offline_synthesizer_generates_valid_patch():
    client = NvidiaNimClient(api_key="offline")
    result = await client.synthesize_repair(
        original_code="class AsyncCache: pass",
        seed=8492,
        error="AssertionError: Cache state out of sync",
        trace_summary="step 1, step 2"
    )

    assert "diagnosis" in result
    assert "fixed_code" in result
    assert "root_cause_pattern" in result
    assert result["_meta"]["live"] is False

def test_nim_json_extractor_handles_markdown_fences():
    fenced_content = """```json
    {
      "diagnosis": "Unprotected dictionary read-write across await sleep",
      "root_cause_pattern": "READ_AFTER_WRITE_HAZARD",
      "fixed_code": "import asyncio\\nclass AsyncCache:\\n    pass",
      "explanation": "Lock serializes access"
    }
    ```"""
    parsed = NvidiaNimClient._extract_json(fenced_content)
    assert parsed["root_cause_pattern"] == "READ_AFTER_WRITE_HAZARD"
    assert "AsyncCache" in parsed["fixed_code"]