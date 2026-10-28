import pytest
from flakeforge.llm.nebius_client import NebiusTokenFactoryClient

@pytest.mark.asyncio
async def test_offline_synthesizer_generates_valid_patch():
    client = NebiusTokenFactoryClient(api_key="offline")
    result = await client.synthesize_repair(
        original_code="class AsyncCache: pass",
        seed=8492,
        error="AssertionError: Cache state out of sync",
        trace_summary="step 1, step 2"
    )

    assert "diagnosis" in result
    assert "fixed_code" in result
    assert "root_cause_pattern" in result
    assert "READ_AFTER_WRITE_HAZARD" in result["root_cause_pattern"]
