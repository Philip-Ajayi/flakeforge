import asyncio
import inspect
import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from flakeforge.ast_engine.transformer import instrument_code
from flakeforge.ast_engine.patcher import ASTPatcher
from flakeforge.scheduler.deterministic import run_coroutine_with_seed
from flakeforge.minimizer.delta_debug import DeltaDebugMinimizer
from flakeforge.verifier.seed_replay import SeedReplayer
from flakeforge.verifier.stress_gate import StressGateVerifier
from flakeforge.llm.nim_client import NvidiaNimClient
from flakeforge.config import settings

# Benchmark source modules
from flakeforge.benchmarks import (
    test_async_cache,
    test_rate_limiter,
    test_bank_account,
    test_task_group_leak
)

router = APIRouter()

BENCHMARK_MODULES = {
    "async_cache": (test_async_cache, "run_cache_workload", "BuggyAsyncCache"),
    "rate_limiter": (test_rate_limiter, "run_limiter_workload", "BuggyRateLimiter"),
    "bank_account": (test_bank_account, "run_bank_workload", "BuggyBankAccount"),
    "task_leak": (test_task_group_leak, "run_leak_workload", "TaskLeakService"),
}

class TriageRequest(BaseModel):
    benchmark_id: str = "async_cache"
    custom_code: Optional[str] = None
    max_seeds: int = 40
    stress_seeds: int = 1000

def clean_python_code(code: str) -> str:
    code = code.strip()
    if code.startswith("```"):
        lines = code.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        code = "\n".join(lines).strip()
    return code

def build_instrumented_workload(module, workload_name: str):
    raw_source = inspect.getsource(module)
    instrumented_source = instrument_code(raw_source)

    isolated_globals = {}
    compiled_code = compile(instrumented_source, f"<{module.__name__}_instrumented>", "exec")
    exec(compiled_code, isolated_globals)

    return raw_source, isolated_globals[workload_name]

def build_repaired_workload(module, workload_name: str, target_class: str, repaired_code: str):
    """Compiles the live LLM repair into a fresh namespace and links it to the workload."""
    raw_source = inspect.getsource(module)
    repaired_code = clean_python_code(repaired_code)

    repaired_globals = {
        "__name__": f"{module.__name__}_repaired",
        "asyncio": asyncio,
        "time": time
    }
    compiled_repair = compile(repaired_code, "<repaired_code>", "exec")
    exec(compiled_repair, repaired_globals)

    # If the LLM re-emitted the entire file including the workload, use it directly
    if workload_name in repaired_globals and callable(repaired_globals[workload_name]):
        return repaired_globals[workload_name]

    # Resolve the newly patched class
    new_class = None
    candidates = [
        target_class,
        target_class.replace("Buggy", ""),
        f"Buggy{target_class}",
        "AsyncCache", "BuggyAsyncCache",
        "BuggyRateLimiter", "AsyncRateLimiter", "RateLimiter",
        "BuggyBankAccount", "BankAccount",
        "TaskLeakService", "BuggyTaskLeakService"
    ]
    for name in candidates:
        if name in repaired_globals and inspect.isclass(repaired_globals[name]):
            new_class = repaired_globals[name]
            break

    if not new_class:
        for val in repaired_globals.values():
            if inspect.isclass(val):
                new_class = val
                break

    # Build the workload harness and inject the repaired class
    workload_globals = {
        "__name__": f"{module.__name__}_test",
        "asyncio": asyncio,
        "time": time
    }
    compiled_workload = compile(raw_source, f"<{module.__name__}_test>", "exec")
    exec(compiled_workload, workload_globals)

    if new_class:
        workload_globals[target_class] = new_class
        base_name = target_class.replace("Buggy", "")
        workload_globals[base_name] = new_class

    return workload_globals[workload_name]

@router.get("/benchmarks")
async def list_benchmarks():
    return [
        {
            "id": "async_cache",
            "name": "Async Cache Invalidation Race",
            "type": "Read-After-Write Hazard",
            "description": "Unshielded coroutine updates to in-memory cache trigger lost increments."
        },
        {
            "id": "rate_limiter",
            "name": "Token Bucket Rate Limiter",
            "type": "Lost Update & Double-Spend",
            "description": "Concurrent coroutines read token balances prior to decrement, exceeding capacity limits."
        },
        {
            "id": "bank_account",
            "name": "Bank Account Circular Transfer",
            "type": "Dining Philosophers Deadlock",
            "description": "Non-hierarchical lock acquisition leads to immediate deadlock during bi-directional transfers."
        },
        {
            "id": "task_leak",
            "name": "TaskGroup Orphaned Worker Leak",
            "type": "Orphaned Task Cancellation",
            "description": "Detached tasks remain running in event loop when calling coroutine encounters an exception."
        }
    ]

@router.post("/triage")
async def execute_triage(req: TriageRequest):
    bench_info = BENCHMARK_MODULES.get(req.benchmark_id, BENCHMARK_MODULES["async_cache"])
    module, workload_func_name, target_class_name = bench_info

    # 1. AST Schedule Injection
    original_source, instrumented_workload = build_instrumented_workload(module, workload_func_name)

    # 2. Schedule Pinning
    failing_seed = None
    failing_result = None
    for seed in range(1, req.max_seeds + 1):
        res = await run_coroutine_with_seed(instrumented_workload, seed=seed, timeout=1.5)
        if not res.passed:
            failing_seed = seed
            failing_result = res
            break

    if not failing_seed:
        return {
            "status": "clean",
            "message": f"Zero flakes discovered across {req.max_seeds} permutations."
        }

    # 3. Delta-Debug Trace Minimization
    minimizer = DeltaDebugMinimizer(coro_factory=instrumented_workload, seed=failing_seed)
    minimal_trace = await minimizer.minimize(failing_result.trace)
    if not minimal_trace:
        minimal_trace = failing_result.trace[:3]

    # 4. Deterministic Replay Verification
    reproduced = await SeedReplayer.verify_failing_seed(instrumented_workload, failing_seed, reps=3)

    # 5. Live NVIDIA NIM Synthesis
    client = NvidiaNimClient()
    trace_summary = f"{len(minimal_trace)} yield events: " + ", ".join([f"{t.coro_name}:{t.line_no}" for t in minimal_trace])

    t_start = time.perf_counter()
    try:
        repair = await client.synthesize_repair(
            original_code=original_source,
            seed=failing_seed,
            error=failing_result.error or "",
            trace_summary=trace_summary
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"NVIDIA NIM Live Inference Failed: {str(exc)}"
        )
    inference_duration = round(time.perf_counter() - t_start, 3)

    diff = ASTPatcher.generate_diff(
        original_source,
        repair.get("fixed_code", original_source),
        filename=f"{req.benchmark_id}.py"
    )

    # 6. Real Phase-2 Stress Gate with Synthesized Live Patch
    repaired_code = repair.get("fixed_code", original_source)
    try:
        repaired_workload = build_repaired_workload(module, workload_func_name, target_class_name, repaired_code)
        target_stress_coro = repaired_workload
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Live synthesized patch failed compilation: {str(exc)}"
        )

    stress_res = await StressGateVerifier.run_stress_gate(
        coro_factory=target_stress_coro,
        seed_count=req.stress_seeds,
        start_seed=20000
    )

    return {
        "status": "triaged",
        "live_mode": True,
        "provider": "NVIDIA NIM",
        "model": client.model,
        "inference_latency_seconds": inference_duration,
        "failing_seed": failing_seed,
        "error": failing_result.error,
        "raw_trace_count": len(failing_result.trace),
        "minimized_trace": [t.to_dict() for t in minimal_trace],
        "replay_reproduced": reproduced,
        "repair": repair,
        "diff": diff,
        "stress_gate": stress_res
    }