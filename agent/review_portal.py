from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import REVIEWS_DIR
from .db import AgentDB


NAV_JS = r"""
(function () {
  const THEME_KEY = "review-theme";

  function preferredTheme() {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === "light" || stored === "dark") {
      return stored;
    }
    if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
      return "dark";
    }
    return "light";
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
  }

  function currentTheme() {
    return document.documentElement.getAttribute("data-theme") || "light";
  }

  function toggleTheme() {
    const next = currentTheme() === "dark" ? "light" : "dark";
    localStorage.setItem(THEME_KEY, next);
    applyTheme(next);
    const btn = document.getElementById("review-theme-toggle");
    if (btn) {
      btn.textContent = next === "dark" ? "Theme: Dark" : "Theme: Light";
    }
  }

  async function boot() {
    applyTheme(preferredTheme());

    const rootId = "review-nav-root";
    let root = document.getElementById(rootId);
    if (!root) {
      root = document.createElement("div");
      root.id = rootId;
      document.body.insertBefore(root, document.body.firstChild);
    }

    const style = document.createElement("style");
    style.textContent = `
      #review-nav-root {
        position: sticky;
        top: 0;
        z-index: 9999;
        background: var(--nav-bg, rgba(255, 255, 255, 0.88));
        color: var(--nav-ink, var(--ink, #0f172a));
        backdrop-filter: blur(8px);
        border-bottom: 1px solid var(--nav-border, rgba(148, 163, 184, 0.35));
      }
      #review-nav-root .inner {
        max-width: 1080px;
        margin: 0 auto;
        padding: 10px 16px;
        font-family: "IBM Plex Sans", Arial, sans-serif;
        display: flex;
        gap: 10px;
        align-items: center;
        justify-content: space-between;
      }
      #review-nav-root .left, #review-nav-root .right {
        display: flex;
        gap: 8px;
        align-items: center;
      }
      #review-nav-root a {
        color: var(--nav-link, var(--accent, #0d9488));
        text-decoration: none;
        font-size: 13px;
        font-weight: 600;
      }
      #review-nav-root .pill {
        border: 1px solid var(--nav-pill-border, #94a3b8);
        border-radius: 999px;
        padding: 3px 9px;
        font-size: 12px;
      }
      #review-nav-root .theme {
        border: 1px solid var(--nav-pill-border, #94a3b8);
        background: transparent;
        color: inherit;
        border-radius: 999px;
        padding: 5px 10px;
        font-size: 12px;
        cursor: pointer;
      }
    `;
    document.head.appendChild(style);

    const page = location.pathname.split("/").pop();
    const isHub = !page || page === "index.html";
    const articleId = isHub ? "" : page.replace(".html", "");
    let manifest = [];
    try {
      const resp = await fetch("./manifest.json", { cache: "no-store" });
      if (resp.ok) {
        const data = await resp.json();
        manifest = data.items || [];
      }
    } catch (_err) {}

    const idx = manifest.findIndex((x) => x.id === articleId);
    const prev = idx > 0 ? manifest[idx - 1] : null;
    const next = idx >= 0 && idx < manifest.length - 1 ? manifest[idx + 1] : null;
    const current = idx >= 0 ? manifest[idx] : null;
    const theme = preferredTheme();

    root.innerHTML = `
      <div class="inner">
        <div class="left">
          <a href="./index.html">Draft Review Hub</a>
          ${current ? `<span class="pill">${current.state}</span><span class="pill">${current.id}</span>` : ""}
        </div>
        <div class="right">
          ${!isHub && prev ? `<a href="./${prev.id}.html">&larr; Previous</a>` : ""}
          ${!isHub && next ? `<a href="./${next.id}.html">Next &rarr;</a>` : ""}
          <button class="theme" id="review-theme-toggle">${theme === "dark" ? "Theme: Dark" : "Theme: Light"}</button>
        </div>
      </div>
    `;

    const toggle = document.getElementById("review-theme-toggle");
    if (toggle) {
      toggle.addEventListener("click", toggleTheme);
    }
  }
  boot();
})();
"""


def _item_card(item: dict[str, Any]) -> str:
    safe_id = html.escape(item["id"])
    safe_title = html.escape(item.get("title") or item["id"])
    safe_subtitle = html.escape(item.get("subtitle") or "No subtitle provided.")
    safe_state = html.escape(item["state"])
    safe_updated = html.escape(_format_timestamp(item.get("updated_at")))
    state_class = _state_class(item["state"])
    return (
        f"<a class='card {state_class}' href='./{safe_id}.html'>"
        f"<div class='card-top'><span class='state {state_class}'>{safe_state}</span></div>"
        f"<h3>{safe_title}</h3>"
        f"<p class='subtitle'>{safe_subtitle}</p>"
        f"<p class='meta'>ID: {safe_id}</p>"
        f"<p class='meta'>Updated: {safe_updated}</p>"
        f"</a>"
    )


def _format_timestamp(value: str | None) -> str:
    if not value:
        return "-"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y %H:%M UTC")
    except ValueError:
        return value


def _state_class(state: str) -> str:
    mapping = {
        "READY_FOR_REVIEW": "ready",
        "APPROVED": "approved",
        "PUBLISHED": "published",
        "STYLE_CHECK": "blocked",
    }
    return mapping.get(state, "default")


def _index_html(items: list[dict[str, Any]]) -> str:
    state_counts: dict[str, int] = {}
    for item in items:
        state = item["state"]
        state_counts[state] = state_counts.get(state, 0) + 1

    stat_blocks = "".join(
        f"<div class='stat'><p>{html.escape(state.replace('_', ' '))}</p><strong>{count}</strong></div>"
        for state, count in sorted(state_counts.items())
    )

    cards = "\n".join(_item_card(i) for i in items) or "<p>No review pages found.</p>"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Draft Review Hub</title>
  <style>
    :root {{
      --bg: #eff4fb;
      --bg-2: #dbeafe;
      --ink: #0f172a;
      --sub: #4b5d73;
      --panel: #ffffff;
      --brand: #0e7490;
      --brand-2: #1d4ed8;
      --border: #d6e0eb;
      --shadow: 0 10px 28px rgba(15, 23, 42, 0.08);
      --nav-bg: rgba(255, 255, 255, 0.88);
      --nav-ink: #0f172a;
      --nav-link: #0e7490;
      --nav-border: rgba(148, 163, 184, 0.35);
      --nav-pill-border: #94a3b8;
      --card-hover: #f8fbff;
      --ready: #0f766e;
      --approved: #2563eb;
      --published: #15803d;
      --blocked: #b45309;
    }}
    html[data-theme="dark"] {{
      --bg: #081221;
      --bg-2: #0b1b33;
      --ink: #e6edf7;
      --sub: #9fb1c8;
      --panel: #0f2137;
      --brand: #22d3ee;
      --brand-2: #60a5fa;
      --border: #223853;
      --shadow: 0 10px 28px rgba(2, 8, 23, 0.45);
      --nav-bg: rgba(8, 18, 33, 0.86);
      --nav-ink: #e6edf7;
      --nav-link: #67e8f9;
      --nav-border: rgba(71, 85, 105, 0.5);
      --nav-pill-border: #4b647f;
      --card-hover: #132a44;
      --ready: #2dd4bf;
      --approved: #60a5fa;
      --published: #4ade80;
      --blocked: #fbbf24;
    }}
    body {{
      margin: 0;
      background: radial-gradient(circle at top right, var(--bg-2), var(--bg) 42%);
      color: var(--ink);
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      min-height: 100vh;
    }}
    .wrap {{
      max-width: 1080px;
      margin: 0 auto;
      padding: 24px 14px 42px;
    }}
    .hero {{
      background: linear-gradient(135deg, rgba(14, 116, 144, 0.12), rgba(29, 78, 216, 0.10));
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 18px;
      margin-bottom: 16px;
      box-shadow: var(--shadow);
    }}
    .hero h1 {{
      margin: 0 0 6px;
      font-size: 1.7rem;
    }}
    .hero p {{
      margin: 0 0 16px;
      color: var(--sub);
      font-size: 0.95rem;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
      gap: 10px;
    }}
    .stat {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 10px 12px;
    }}
    .stat p {{
      margin: 0;
      color: var(--sub);
      font-size: 0.76rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .stat strong {{
      display: block;
      margin-top: 4px;
      font-size: 1.2rem;
    }}
    .grid {{
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(310px, 1fr));
    }}
    .card {{
      display: block;
      text-decoration: none;
      color: inherit;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 14px;
      box-shadow: var(--shadow);
      transition: transform 150ms ease, background 150ms ease, border-color 150ms ease;
    }}
    .card:hover {{
      transform: translateY(-2px);
      background: var(--card-hover);
      border-color: var(--brand);
    }}
    .card-top {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }}
    .state {{
      border-radius: 999px;
      border: 1px solid var(--border);
      padding: 3px 9px;
      font-size: 0.73rem;
      font-weight: 700;
      letter-spacing: 0.03em;
    }}
    .state.ready {{
      color: var(--ready);
      border-color: var(--ready);
      background: rgba(13, 148, 136, 0.12);
    }}
    .state.approved {{
      color: var(--approved);
      border-color: var(--approved);
      background: rgba(37, 99, 235, 0.12);
    }}
    .state.published {{
      color: var(--published);
      border-color: var(--published);
      background: rgba(21, 128, 61, 0.12);
    }}
    .state.blocked {{
      color: var(--blocked);
      border-color: var(--blocked);
      background: rgba(180, 83, 9, 0.12);
    }}
    .card h3 {{
      margin: 0 0 8px;
      color: var(--brand);
      font-size: 1.03rem;
    }}
    .subtitle {{
      margin: 0 0 10px;
      font-size: 0.9rem;
      color: var(--ink);
      line-height: 1.4;
    }}
    .meta {{
      margin: 0;
      color: var(--sub);
      font-size: 0.78rem;
    }}
  </style>
</head>
<body>
  <div id="review-nav-root"></div>
  <main class="wrap">
    <section class="hero">
      <h1>Draft Review Hub</h1>
      <p>One URL for all reviews. Open Draft 1, then navigate with Previous/Next or return here for Draft 2.</p>
      <section class="stats">
        <div class="stat"><p>Total Reviews</p><strong>{len(items)}</strong></div>
        {stat_blocks}
      </section>
    </section>
    <section class="grid">
      {cards}
    </section>
  </main>
  <script src="./nav.js"></script>
</body>
</html>"""


def build_review_portal(db: AgentDB) -> tuple[Path, Path]:
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    all_items = db.list_articles()
    items: list[dict[str, Any]] = []
    for item in all_items:
        review_file = REVIEWS_DIR / f"{item['id']}.html"
        if not review_file.exists():
            continue
        if item["state"] not in {"READY_FOR_REVIEW", "APPROVED", "STYLE_CHECK", "PUBLISHED"}:
            continue
        items.append(
            {
                "id": item["id"],
                "state": item["state"],
                "title": item.get("title"),
                "subtitle": item.get("subtitle"),
                "updated_at": item.get("updated_at"),
            }
        )

    # newest first
    items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    manifest_path = REVIEWS_DIR / "manifest.json"
    index_path = REVIEWS_DIR / "index.html"
    nav_js_path = REVIEWS_DIR / "nav.js"

    manifest_path.write_text(json.dumps({"items": items}, indent=2), encoding="utf-8")
    index_path.write_text(_index_html(items), encoding="utf-8")
    nav_js_path.write_text(NAV_JS.strip() + "\n", encoding="utf-8")
    return index_path, manifest_path
