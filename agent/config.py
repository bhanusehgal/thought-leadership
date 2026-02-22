from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
TEMPLATES_DIR = ROOT / "templates"
ARTIFACTS_DIR = ROOT / "artifacts"
REVIEWS_DIR = ROOT / "reviews"
APPROVALS_DIR = ROOT / "approvals"
LOGS_DIR = ROOT / "logs"


def ensure_directories() -> None:
    for path in (ARTIFACTS_DIR, REVIEWS_DIR, APPROVALS_DIR, LOGS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def db_path() -> Path:
    raw = os.getenv("AGENT_DB_PATH", "artifacts/agent.db")
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return path


def source_timeout() -> int:
    return int(os.getenv("AGENT_SOURCE_TIMEOUT_SECONDS", "10"))


def email_capture_url() -> str | None:
    url = os.getenv("EMAIL_CAPTURE_URL", "").strip()
    return url or None
