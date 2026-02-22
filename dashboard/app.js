const statusBox = document.getElementById("statusBox");
const runsBox = document.getElementById("runsBox");

function status(msg, isError = false) {
  statusBox.textContent = msg;
  statusBox.className = `status ${isError ? "bad" : "ok"}`;
}

async function triggerWorkflow() {
  const command = document.getElementById("command").value;
  const topic = document.getElementById("topic").value.trim();
  const pillar = document.getElementById("pillar").value.trim();
  const weekType = document.getElementById("weekType").value.trim();
  const sourceUrls = document.getElementById("sourceUrls").value.trim();
  const articleId = document.getElementById("articleId").value.trim();
  const count = Number(document.getElementById("count").value || "1");
  const state = document.getElementById("state").value.trim();
  const dryRun = document.getElementById("dryRun").value === "true";
  const skipUrlCheck = document.getElementById("skipUrlCheck").value === "true";
  const forceRun = document.getElementById("forceRun").value === "true";
  const dashboardKey = document.getElementById("dashboardKey").value.trim();

  if ((command === "approve" || command === "publish") && !articleId) {
    status("Article ID is required for approve/publish commands.", true);
    return;
  }
  if (command === "run_topic" && !topic) {
    status("Topic is required for run_topic.", true);
    return;
  }

  const payload = {
    command,
    topic,
    pillar,
    week_type: weekType,
    source_urls: sourceUrls,
    article_id: articleId,
    count,
    state,
    dry_run: dryRun,
    skip_url_check: skipUrlCheck,
    force_run: forceRun,
  };

  status("Dispatching workflow...");
  try {
    const resp = await fetch("/api/trigger-workflow", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(dashboardKey ? { "x-dashboard-key": dashboardKey } : {}),
      },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.error || "Dispatch failed");
    }
    status(`Dispatched ${command}. Check Actions in ~10-20 seconds.`);
    await listRuns();
  } catch (err) {
    status(`Error: ${err.message}`, true);
  }
}

function runToHtml(run) {
  const conclusion = run.conclusion || "in_progress";
  const created = new Date(run.created_at).toLocaleString();
  return `
    <div class="run">
      <div><strong>${run.name}</strong></div>
      <div>Status: ${run.status} / ${conclusion}</div>
      <div>Created: ${created}</div>
      <div><a href="${run.html_url}" target="_blank" rel="noopener noreferrer">Open run</a></div>
    </div>
  `;
}

async function listRuns() {
  runsBox.innerHTML = "Loading...";
  const dashboardKey = document.getElementById("dashboardKey").value.trim();
  try {
    const resp = await fetch("/api/list-runs", {
      headers: dashboardKey ? { "x-dashboard-key": dashboardKey } : {},
    });
    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.error || "Unable to fetch runs");
    }
    if (!data.runs || data.runs.length === 0) {
      runsBox.innerHTML = "<div class='run'>No runs found yet.</div>";
      return;
    }
    runsBox.innerHTML = data.runs.map(runToHtml).join("");
  } catch (err) {
    runsBox.innerHTML = `<div class='run bad'>${err.message}</div>`;
  }
}

document.getElementById("triggerBtn").addEventListener("click", triggerWorkflow);
document.getElementById("refreshBtn").addEventListener("click", listRuns);
document.getElementById("openActionsBtn").addEventListener("click", () => {
  window.open("https://github.com", "_blank", "noopener,noreferrer");
});

listRuns();
