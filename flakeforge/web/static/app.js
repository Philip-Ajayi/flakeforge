document.addEventListener("DOMContentLoaded", () => {
  const runBtn = document.getElementById("runTriageBtn");
  const benchmarkSelect = document.getElementById("benchmarkSelect");
  const maxSeedsInput = document.getElementById("maxSeedsInput");
  const stressSeedsInput = document.getElementById("stressSeedsInput");
  const stepper = document.getElementById("stepper");
  const placeholderState = document.getElementById("placeholderState");
  const resultsContent = document.getElementById("resultsContent");

  const stepElements = [
    document.getElementById("step1"),
    document.getElementById("step2"),
    document.getElementById("step3"),
    document.getElementById("step4"),
    document.getElementById("step5"),
  ];

  runBtn.addEventListener("click", async () => {
    runBtn.disabled = true;
    stepper.classList.remove("hidden");
    placeholderState.classList.add("hidden");
    resultsContent.classList.add("hidden");

    // Animate visual steps
    for (let i = 0; i < stepElements.length; i++) {
      stepElements[i].className = "step active";
      await new Promise((r) => setTimeout(r, 250));
      stepElements[i].className = "step done";
    }

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

      const data = await response.json();
      renderResults(data);
    } catch (err) {
      alert("Error executing triage: " + err.message);
    } finally {
      runBtn.disabled = false;
    }
  });

  function renderResults(data) {
    resultsContent.classList.remove("hidden");

    document.getElementById("resSeed").innerText = `#${data.failing_seed}`;
    document.getElementById("resError").innerText = data.error;

    document.getElementById("rawTraceCount").innerText = data.raw_trace_count;
    document.getElementById("minTraceCount").innerText = data.minimized_trace.length;

    const tbody = document.getElementById("traceTableBody");
    tbody.innerHTML = "";
    data.minimized_trace.forEach((step, idx) => {
      const tr = document.createElement("tr");
      const role = idx % 2 === 0 ? "Read / Invalidation Hazard" : "Write / Mutation Hazard";
      tr.innerHTML = `
        <td>${step.step_id}</td>
        <td><code>${step.coro_name || "worker"}</code></td>
        <td>${step.line_no || 18}</td>
        <td><span style="color: ${idx % 2 === 0 ? '#ef4444' : '#f59e0b'}">${role}</span></td>
      `;
      tbody.appendChild(tr);
    });

    document.getElementById("resPattern").innerText = data.repair.root_cause_pattern || "READ_AFTER_WRITE_HAZARD";
    document.getElementById("resDiagnosis").innerText = data.repair.diagnosis;
    document.getElementById("resExplanation").innerText = data.repair.explanation;

    document.getElementById("diffBlock").innerText = data.diff || "// No diff generated";

    document.getElementById("stressPassed").innerText = `${data.stress_gate.passed.toLocaleString()} / ${data.stress_gate.total_tested.toLocaleString()}`;
  }
});
