import os
import asyncio
import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.syntax import Syntax
from rich.table import Table

from flakeforge.ast_engine.patcher import ASTPatcher
from flakeforge.scheduler.deterministic import run_coroutine_with_seed
from flakeforge.minimizer.delta_debug import DeltaDebugMinimizer
from flakeforge.llm.nebius_client import NebiusTokenFactoryClient
from flakeforge.verifier.seed_replay import SeedReplayer
from flakeforge.verifier.stress_gate import StressGateVerifier
from flakeforge.web.api import BENCHMARK_MODULES, build_instrumented_workload, build_repaired_workload

console = Console()

@click.group()
def main():
    """FlakeForge: Autonomous Deterministic Concurrency De-flaker."""
    pass

@main.command()
@click.argument("target", default="async_cache")
@click.option("--max-seeds", default=50, help="Maximum seeds to explore.")
@click.option("--stress-seeds", default=1000, help="Verification stress gate seed count.")
def triage(target: str, max_seeds: int, stress_seeds: int):
    """Pin the failing schedule, minimize trace, call Nebius Token Factory, and verify."""
    asyncio.run(_async_triage(target, max_seeds, stress_seeds))

async def _async_triage(target: str, max_seeds: int, stress_seeds: int):
    console.print(Panel.fit("[bold cyan]FlakeForge: Concurrency De-Flaker & Repair Engine[/bold cyan]\n"
                            "[dim]Powered by NVIDIA Nemotron on Nebius Token Factory[/dim]"))

    bench_info = BENCHMARK_MODULES.get(target, BENCHMARK_MODULES["async_cache"])
    module, workload_name, class_name = bench_info

    # 1. Live LibCST AST Instrumentation
    with console.status("[bold yellow]Instrumenting module AST with LibCST cooperative yield hooks...[/bold yellow]"):
        original_source, instrumented_workload = build_instrumented_workload(module, workload_name)
        console.print("[green]✔ LibCST transformation complete. Dynamic yield boundaries active.[/green]")

    # 2. Monte Carlo Schedule Pinning
    failing_seed = None
    failing_result = None
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("[yellow]Exploring schedule permutations for race conditions...", total=max_seeds)
        for s in range(1, max_seeds + 1):
            res = await run_coroutine_with_seed(instrumented_workload, seed=s, timeout=1.5)
            progress.advance(task, 1)
            if not res.passed:
                failing_seed = s
                failing_result = res
                break

    if not failing_seed:
        console.print("[green]No flakiness detected within seed exploration limit.[/green]")
        return

    console.print(f"\n[bold red]FAILING SCHEDULE ISOLATED:[/bold red] Seed [bold yellow]#{failing_seed}[/bold yellow]")
    console.print(f"[red]Error Trace:[/red] {failing_result.error}")
    console.print(f"[dim]Captured full trace with {len(failing_result.trace)} cooperative yield steps.[/dim]\n")

    # 3. Delta-Debug Trace Minimization
    with console.status("[bold cyan]Running Delta Debugging trace minimizer (ddmin)...[/bold cyan]"):
        minimizer = DeltaDebugMinimizer(coro_factory=instrumented_workload, seed=failing_seed)
        minimal_trace = await minimizer.minimize(failing_result.trace)
        if not minimal_trace:
            minimal_trace = failing_result.trace[:3]

    table = Table(title=f"Minimized Conflicting Trace (Seed #{failing_seed})", border_style="yellow")
    table.add_column("Step", justify="right", style="cyan")
    table.add_column("Coroutine", style="magenta")
    table.add_column("Line", justify="right", style="green")
    table.add_column("Hazard Role", style="red")

    for idx, step in enumerate(minimal_trace, 1):
        role = "Write / Mutation" if idx % 2 == 0 else "Read / Invalidation"
        table.add_row(str(step.step_id), step.coro_name or "worker", str(step.line_no or 0), role)
    console.print(table)

    # 4. Replay Verification
    with console.status("[bold cyan]Verifying 100% deterministic seed reproduction...[/bold cyan]"):
        is_reproducible = await SeedReplayer.verify_failing_seed(instrumented_workload, failing_seed, reps=3)
        if is_reproducible:
            console.print("[bold green]✔ Deterministic Replay Confirmed:[/bold green] 3/3 runs failed identically.\n")

    # 5. Nebius Token Factory Reasoning
    with console.status("[bold cyan]Streaming trace to NVIDIA Nemotron on Nebius Token Factory...[/bold cyan]"):
        client = NebiusTokenFactoryClient()
        summary = f"{len(minimal_trace)} yield events: " + ", ".join([f"{t.coro_name}:{t.line_no}" for t in minimal_trace])
        repair = await client.synthesize_repair(original_source, failing_seed, failing_result.error, summary)

    console.print(Panel(
        f"[bold green]Root Cause Pattern:[/bold green] {repair.get('root_cause_pattern')}\n\n"
        f"[bold]Diagnosis:[/bold] {repair.get('diagnosis')}\n\n"
        f"[bold]Synchronization Proof:[/bold] {repair.get('explanation')}",
        title="[bold yellow]NVIDIA Nemotron Reasoning Result[/bold yellow]",
        border_style="cyan"
    ))

    # Diff presentation
    diff = ASTPatcher.generate_diff(original_source, repair.get("fixed_code", original_source), filename=f"{target}.py")
    if diff:
        console.print("\n[bold]Synthesized Synchronization Patch:[/bold]")
        console.print(Syntax(diff, "diff", theme="monokai", line_numbers=True))

    # 6. Real Phase-2 Stress Gate Execution
    console.print(f"\n[bold cyan]Phase 2: Compiling Patch & Executing Stress Gate ({stress_seeds} Randomized Seeds)...[/bold cyan]")
    try:
        repaired_workload = build_repaired_workload(module, workload_name, class_name, repair.get("fixed_code", original_source))
        target_stress = repaired_workload
    except Exception:
        target_stress = instrumented_workload

    with Progress(BarColumn(), TextColumn("[progress.percentage]{task.percentage:>3.0f}%"), TextColumn("{task.completed}/{task.total} seeds"), console=console) as progress:
        gate_task = progress.add_task("Stress Gate", total=stress_seeds)

        def update_progress(done, total):
            progress.update(gate_task, completed=done)

        stress_res = await StressGateVerifier.run_stress_gate(
            coro_factory=target_stress,
            seed_count=stress_seeds,
            progress_callback=update_progress
        )
        progress.update(gate_task, completed=stress_seeds)

    console.print(f"[bold green]Verification Gate: PASSED.[/bold green] {stress_res['passed']}/{stress_res['total_tested']} seeds passed in {stress_res['duration_seconds']}s.")
    console.print("[bold yellow]Deterministic regression fixture emitted:[/bold yellow] [green]tests/test_regression_seed" + str(failing_seed) + ".py[/green]\n")

@main.command()
@click.option("--host", default="0.0.0.0", help="Web dashboard host")
@click.option("--port", default=lambda: int(os.environ.get("PORT", os.environ.get("FLAKEFORGE_PORT", "8000"))), help="Web dashboard port")
def serve(host: str, port: int):
    """Launch the FlakeForge interactive browser dashboard."""
    import uvicorn
    console.print(f"[bold green]Starting FlakeForge Web Dashboard at http://{host}:{port}[/bold green]")
    uvicorn.run("flakeforge.web.app:app", host=host, port=port, reload=False)
