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
  if (!token || !owner || !repo) {
    throw new Error("Missing GITHUB_TOKEN, GITHUB_OWNER, or GITHUB_REPO.");
  }
  return { token, owner, repo, workflow };
}

exports.handler = async (event) => {
  if (event.httpMethod !== "GET") {
    return { statusCode: 405, body: "Method Not Allowed" };
  }
  if (!checkDashboardKey(event.headers || {})) {
    return unauthorized();
  }

  try {
    const cfg = githubConfig();
    const url = `https://api.github.com/repos/${cfg.owner}/${cfg.repo}/actions/workflows/${cfg.workflow}/runs?per_page=12`;
    const resp = await fetch(url, {
      headers: {
        Authorization: `Bearer ${cfg.token}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "medium-authority-engine-netlify",
      },
    });
    if (!resp.ok) {
      const text = await resp.text();
      return {
        statusCode: resp.status,
        body: JSON.stringify({ error: `GitHub runs request failed: ${text}` }),
      };
    }
    const data = await resp.json();
    const runs = (data.workflow_runs || []).map((run) => ({
      id: run.id,
      name: run.name,
      status: run.status,
      conclusion: run.conclusion,
      html_url: run.html_url,
      created_at: run.created_at,
      event: run.event,
      run_number: run.run_number,
      head_branch: run.head_branch,
    }));
    return {
      statusCode: 200,
      body: JSON.stringify({ runs }),
    };
  } catch (err) {
    return {
      statusCode: 500,
      body: JSON.stringify({ error: err.message || "Unknown error" }),
    };
  }
};
