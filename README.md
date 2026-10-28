# FlakeForge

> **Deterministic Concurrency De-Flaker and Synchronization Repair Agent**
> Powered by NVIDIA Nemotron on Nebius Token Factory.

---

## ⚡ Overview

FlakeForge eliminates the dangerous anti-pattern of retrying flaky asynchronous Python tests (`pytest-rerunfailures`). Retries conceal latent data races, lost updates, and deadlocks that corrupt production systems.

Instead of statistical reruns, FlakeForge uses:
1. **AST-Level Yield Pinning:** Instruments coroutines with `libcst` to inject cooperative schedule hooks (`__flake_yield__`).
2. **Deterministic Seed Scheduling:** Permutes scheduling decisions with a controlled pseudo-random seed to isolate the exact failing interleaving.
3. **Delta-Debug Minimizer (ddmin):** Prunes non-essential yields down to the minimal conflicting read/write sequence.
4. **NVIDIA Nemotron Reasoning:** Streams the AST slice and trace to Nebius Token Factory (`nvidia/nemotron-3-super-120b-a12b` or `nvidia/Nemotron-3-Ultra-550b-a55b`) to synthesize a provably race-free synchronization fix.
5. **Phase-2 Stress Gate:** Verifies the patch against 1,000 randomized seed permutations without deadlocks or timeouts.

---

## 🚀 Quickstart

### 1. Installation

```bash
git clone https://github.com/your-org/flakeforge.git
cd flakeforge
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

### 2. Configure Environment (Optional)

```bash
cp .env.example .env
# Edit .env and supply your NEBIUS_API_KEY.
# If omitted, FlakeForge automatically runs in zero-cost offline mode!
```

---

## 🖥️ Live Browser Dashboard (For Judges & Evaluators)

Run the built-in web dashboard:
```bash
flakeforge serve --host 0.0.0.0 --port 8000
```
Open **`http://localhost:8000`** in your browser. From the interface you can:
- Select from 4 real asynchronous concurrency race conditions.
- Trigger autonomous triage in real time.
- Inspect the failing seed, minimized trace, and memory hazard role.
- View the synthesized AST patch and 1,000-seed stress gate verification.

### Running with Docker

```bash
docker-compose up --build
```
Access the dashboard at `http://localhost:8000`.

---

## 💻 CLI Usage

### Autonomous Triage
```bash
# Triage the Async Cache benchmark
flakeforge triage async_cache

# Triage with custom seed bound and stress count
flakeforge triage rate_limiter --max-seeds 40 --stress-seeds 1000
```

### Pytest Plugin Integration
```bash
# Replay failing Seed #8492 deterministically (100% failure reproduction)
pytest --flake-seed=8492 tests/

# Execute 1,000-seed stress test
pytest --flake-stress=1000 tests/
```

---

## 🧪 Benchmark Suite Included

* **`test_async_cache.py`**: Read-After-Write hazard with unshielded cache invalidation.
* **`test_rate_limiter.py`**: Token bucket double-spend and lost updates under concurrency bursts.
* **`test_bank_account.py`**: Classical asymmetric lock acquisition dining philosophers deadlock.
* **`test_task_group_leak.py`**: Orphaned background coroutine leaks during task cancellation.

---

## 🔬 Running the Verification Tests

```bash
pytest -v tests/
```
```

---

### Step-by-Step Deployment & Live Evaluation Instructions

1. **Local Setup:**
   ```bash
   python3 -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   pip install -e .
   ```
2. **Run Tests:**
   ```bash
   pytest -v tests/
   ```
3. **Launch the Live Interface for Judges:**
   ```bash
   flakeforge serve --host 0.0.0.0 --port 8000
