from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from .config import APPROVALS_DIR


def approval_path(article_id: str) -> Path:
    return APPROVALS_DIR / f"{article_id}.approved"


def has_approval(article_id: str) -> bool:
    return approval_path(article_id).exists()


def mark_approved(article_id: str) -> Path:
    actor = os.getenv("GITHUB_ACTOR", "local-reviewer")
    now = datetime.now(timezone.utc).isoformat()
    path = approval_path(article_id)
    path.write_text(f"approved_by={actor}\napproved_at={now}\n", encoding="utf-8")
    return path
