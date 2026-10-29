document.addEventListener("DOMContentLoaded", () => {
  const runBtn = document.getElementById("runTriageBtn");
  const benchmarkSelect = document.getElementById("benchmarkSelect");
  const maxSeedsInput = document.getElementById("maxSeedsInput");
  const stressSeedsInput = document.getElementById("stressSeedsInput");
  const stepper = document.getElementById("stepper");
  const placeholderState = document.getElementById("placeholderState");
  const resultsContent = document.getElementById("resultsContent");
  const errorBanner = document.getElementById("errorBanner");
  const errorMessage = document.getElementById("errorMessage");

  const steps = [
    document.getElementById("step1"),
    document.getElementById("step2"),
    document.getElementById("step3"),
    document.getElementById("step4"),
    document.getElementById("step5"),
  ];

  function setStepState(activeIdx) {
    steps.forEach((el, idx) => {
      if (idx < activeIdx) {
        el.className = "step done";
      } else if (idx === activeIdx) {
        el.className = "step active";
      } else {
        el.className = "step";
      }
    });
  }

  runBtn.addEventListener("click", async () => {
    runBtn.disabled = true;
    stepper.classList.remove("hidden");
    placeholderState.classList.add("hidden");
    resultsContent.classList.add("hidden");
    if (errorBanner) errorBanner.classList.add("hidden");

    setStepState(0);
    const stepTimer1 = setTimeout(() => setStepState(1), 350);
    const stepTimer2 = setTimeout(() => setStepState(2), 1200);
    const stepTimer3 = setTimeout(() => setStepState(3), 2000);

    try {
      const response = await fetch("/api/triage", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          benchmark_id: benchmarkSelect.value,
          max_seeds: parseInt(maxSeedsInput.value, 10),
          stress_seeds: parseInt(stressSeedsInput.value, 10),
        }),
      });

      clearTimeout(stepTimer1);
      clearTimeout(stepTimer2);
      clearTimeout(stepTimer3);

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Server returned HTTP ${response.status}`);
      }

      setStepState(4);
      const data = await response.json();
      setTimeout(() => {
        steps.forEach((el) => (el.className = "step done"));
      }, 300);

      renderResults(data);
    } catch (err) {
      clearTimeout(stepTimer1);
      clearTimeout(stepTimer2);
      clearTimeout(stepTimer3);
      steps.forEach((el) => (el.className = "step"));
      if (errorBanner && errorMessage) {
        errorMessage.innerText = err.message;
        errorBanner.classList.remove("hidden");
      } else {
        alert("Live Triage Error: " + err.message);
      }
    } finally {
      runBtn.disabled = false;
    }
  });

  function renderResults(data) {
    resultsContent.classList.remove("hidden");

    const failureBanner = document.getElementById("failureBanner");
    const traceSection = document.getElementById("traceSection");
    const reasoningSection = document.getElementById("reasoningSection");
    const diffSection = document.getElementById("diffSection");
    const stressSection = document.getElementById("stressSection");

    // Case 1: Clean run (No race condition observed)
    if (data.status === "clean") {
      failureBanner.className = "alert-box alert-clean";
      failureBanner.innerHTML = `
        <div style="color: var(--accent-green); font-weight: 700; font-size: 14px;">✔ CLEAN CONCURRENCY HARNESS</div>
        <div style="font-size: 12px; margin-top: 4px; color: var(--text-main);">${data.message}</div>
      `;
      if (traceSection) traceSection.classList.add("hidden");
      if (reasoningSection) reasoningSection.classList.add("hidden");
      if (diffSection) diffSection.classList.add("hidden");
      if (stressSection) stressSection.classList.add("hidden");
      return;
    }

    // Case 2: Race condition triaged
    failureBanner.className = "alert-box alert-failure";
    failureBanner.innerHTML = `
      <div><strong>FAILING SCHEDULE ISOLATED:</strong> Seed <span class="highlight-seed">#${data.failing_seed}</span></div>
      <div class="error-text">${data.error}</div>
    `;

    if (traceSection) traceSection.classList.remove("hidden");
    if (reasoningSection) reasoningSection.classList.remove("hidden");
    if (diffSection) diffSection.classList.remove("hidden");
    if (stressSection) stressSection.classList.remove("hidden");

    document.getElementById("rawTraceCount").innerText = data.raw_trace_count;
    document.getElementById("minTraceCount").innerText = (data.minimized_trace || []).length;

    if (document.getElementById("modelBadge")) {
      document.getElementById("modelBadge").innerText = data.model || "NVIDIA NIM";
    }
    if (document.getElementById("latencyBadge")) {
      document.getElementById("latencyBadge").innerText = `${data.inference_latency_seconds}s latency`;
    }

    const tbody = document.getElementById("traceTableBody");
    tbody.innerHTML = "";
    (data.minimized_trace || []).forEach((step, idx) => {
      const tr = document.createElement("tr");
      const role = idx % 2 === 0 ? "Read / Invalidation Hazard" : "Write / Mutation Hazard";
      tr.innerHTML = `
        <td>${step.step_id}</td>
        <td><code>${step.coro_name || "worker"}</code></td>
        <td>${step.line_no || 0}</td>
        <td><span style="color: ${idx % 2 === 0 ? "#ef4444" : "#f59e0b"}">${role}</span></td>
      `;
      tbody.appendChild(tr);
    });

    document.getElementById("resPattern").innerText = data.repair.root_cause_pattern || "CONCURRENCY_HAZARD";
    document.getElementById("resDiagnosis").innerText = data.repair.diagnosis;
    document.getElementById("resExplanation").innerText = data.repair.explanation;

    document.getElementById("diffBlock").innerText = data.diff || "// No diff generated";

    document.getElementById("stressPassed").innerText = `${data.stress_gate.passed.toLocaleString()} / ${data.stress_gate.total_tested.toLocaleString()}`;
  }
});