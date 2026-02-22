from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import ARTIFACTS_DIR


def item_dir(article_id: str) -> Path:
    path = ARTIFACTS_DIR / article_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_metadata(article: dict[str, Any]) -> Path:
    path = item_dir(article["id"]) / "metadata.json"
    payload = {
        "id": article["id"],
        "state": article["state"],
        "pillar": article["pillar"],
        "topic": article["topic"],
        "week_type": article["week_type"],
        "title": article.get("title"),
        "subtitle": article.get("subtitle"),
        "tldr": article.get("tldr"),
        "tags": article.get("tags", []),
        "title_options": article.get("title_options", []),
        "image_suggestions": article.get("image_suggestions", []),
        "citations": article.get("citations", []),
        "claims_verification": article.get("claims_verification", []),
        "metadata": article.get("metadata", {}),
        "scheduled_publish_at": article.get("scheduled_publish_at"),
        "published_url": article.get("published_url"),
        "created_at": article.get("created_at"),
        "updated_at": article.get("updated_at"),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def write_draft(article_id: str, markdown: str) -> Path:
    path = item_dir(article_id) / "draft.md"
    path.write_text(markdown, encoding="utf-8")
    return path
