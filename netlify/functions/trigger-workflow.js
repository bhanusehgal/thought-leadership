function unauthorized() {
  return {
    statusCode: 401,
    body: JSON.stringify({
      error: "Unauthorized. Provide x-dashboard-key header.",
    }),
  };
}

function checkDashboardKey(headers) {
  const expected = process.env.NETLIFY_DASHBOARD_KEY || "";
  if (!expected) {
    return true;
  }
  const provided = headers["x-dashboard-key"] || headers["X-Dashboard-Key"] || "";
  return provided === expected;
}

function githubConfig() {
  const token = process.env.GITHUB_TOKEN;
  const owner = process.env.GITHUB_OWNER;
  const repo = process.env.GITHUB_REPO;
  const workflow = process.env.GITHUB_OPS_WORKFLOW_FILE || "ops-manual.yml";
  const branch = process.env.GITHUB_BRANCH || "main";
  if (!token || !owner || !repo) {
    throw new Error("Missing GITHUB_TOKEN, GITHUB_OWNER, or GITHUB_REPO.");
  }
  return { token, owner, repo, workflow, branch };
}

function publishEnabled() {
  return String(process.env.ENABLE_MEDIUM_PUBLISH || "false").toLowerCase() === "true";
}

exports.handler = async (event) => {
  if (event.httpMethod !== "POST") {
    return { statusCode: 405, body: "Method Not Allowed" };
  }
  if (!checkDashboardKey(event.headers || {})) {
    return unauthorized();
  }

  let payload;
  try {
    payload = JSON.parse(event.body || "{}");
  } catch (_err) {
    return { statusCode: 400, body: JSON.stringify({ error: "Invalid JSON body." }) };
  }

  const command = String(payload.command || "").trim();
  const topic = String(payload.topic || "").trim();
  const pillar = String(payload.pillar || "").trim();
  const weekType = String(payload.week_type || "").trim();
  const sourceUrls = String(payload.source_urls || "").trim();
  const articleId = String(payload.article_id || "").trim();
  const state = String(payload.state || "").trim();
  const count = Number(payload.count || 1);
  const dryRun = Boolean(payload.dry_run);
  const forceRun = Boolean(payload.force_run);
  const skipUrlCheck = Boolean(payload.skip_url_check);

  const allowed = new Set(["run_weekly", "run_topic", "approve", "publish", "publish_approved", "list_items"]);
  if (!allowed.has(command)) {
    return { statusCode: 400, body: JSON.stringify({ error: "Invalid command." }) };
  }
  if (command === "run_topic" && !topic) {
    return { statusCode: 400, body: JSON.stringify({ error: "topic required for run_topic." }) };
  }
  if ((command === "approve" || command === "publish") && !articleId) {
    return { statusCode: 400, body: JSON.stringify({ error: "article_id required." }) };
  }
  if ((command === "publish" || command === "publish_approved") && !publishEnabled()) {
    return {
      statusCode: 403,
      body: JSON.stringify({
        error: "Publishing is disabled in this deployment. Set ENABLE_MEDIUM_PUBLISH=true to enable.",
      }),
    };
  }

  try {
    const cfg = githubConfig();
    const url = `https://api.github.com/repos/${cfg.owner}/${cfg.repo}/actions/workflows/${cfg.workflow}/dispatches`;
    const inputs = {
      command,
      topic,
      pillar,
      week_type: weekType,
      source_urls: sourceUrls,
      article_id: articleId,
      count: String(Number.isFinite(count) ? Math.max(1, count) : 1),
      state,
      dry_run: dryRun ? "true" : "false",
      force_run: forceRun ? "true" : "false",
      skip_url_check: skipUrlCheck ? "true" : "false",
    };
    const resp = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${cfg.token}`,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "medium-authority-engine-netlify",
      },
      body: JSON.stringify({
        ref: cfg.branch,
        inputs,
      }),
    });
    if (!resp.ok) {
      const text = await resp.text();
      return {
        statusCode: resp.status,
        body: JSON.stringify({ error: `GitHub dispatch failed: ${text}` }),
      };
    }
    return {
      statusCode: 200,
      body: JSON.stringify({ ok: true, message: "Workflow dispatched." }),
    };
  } catch (err) {
    return {
      statusCode: 500,
      body: JSON.stringify({ error: err.message || "Unknown error" }),
    };
  }
};
