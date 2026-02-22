from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import REVIEWS_DIR, TEMPLATES_DIR


def render_review(article: dict[str, Any], checklist: dict[str, bool], flags: dict[str, list[str]]) -> Path:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("review.html.j2")
    payload = dict(article)
    payload["checklist"] = checklist
    payload["flags"] = flags
    html = template.render(item=payload)
    path = REVIEWS_DIR / f"{article['id']}.html"
    path.write_text(html, encoding="utf-8")
    return path
