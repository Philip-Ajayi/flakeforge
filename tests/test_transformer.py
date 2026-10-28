import pytest
from flakeforge.ast_engine.transformer import instrument_code

def test_ast_transformer_injects_flake_yield():
    source = """async def worker():
    await asyncio.sleep(0.01)
"""
    instrumented = instrument_code(source)
    assert "__flake_yield__" in instrumented
    assert "from flakeforge.scheduler.hooks import __flake_yield__" in instrumented
