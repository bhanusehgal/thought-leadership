from __future__ import annotations

from pathlib import Path

import pytest

from agent.approvals import approval_path, mark_approved
from agent.db import AgentDB
from agent.pipeline import MediumAuthorityPipeline


def _db(tmp_path: Path) -> AgentDB:
    db = AgentDB(tmp_path / "agent.db")
    db.init()
    return db


def _insert_approved(db: AgentDB, article_id: str) -> None:
    db.insert_article(
        {
            "id": article_id,
            "pillar": "Asset Liability Management",
            "topic": "Publish block test",
            "week_type": "Technical deep dive",
            "state": "APPROVED",
            "title": "Test title",
            "subtitle": "Test subtitle",
            "tldr": "Test tldr",
            "body_markdown": "Body",
            "title_options": ["a", "b", "c", "d", "e"],
            "tags": ["ALM", "AML", "AI", "Banking", "ModelRisk"],
            "citations": [
                {"title": "x", "url": "https://federalreserve.gov", "domain": "federalreserve.gov"},
                {"title": "y", "url": "https://bis.org", "domain": "bis.org"},
            ],
            "metadata": {},
        }
    )


def test_publish_blocked_without_approval_file(tmp_path: Path) -> None:
    db = _db(tmp_path)
    _insert_approved(db, "pub-1")
    pipeline = MediumAuthorityPipeline(db)
    with pytest.raises(RuntimeError, match="Approval file missing"):
        pipeline.publish("pub-1", dry_run=True)


def test_publish_allowed_with_approval_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = _db(tmp_path)
    _insert_approved(db, "pub-2")
    pipeline = MediumAuthorityPipeline(db)

    def fake_publish(_article, dry_run=False):  # noqa: ARG001
        shot = tmp_path / "published.png"
        shot.write_text("ok", encoding="utf-8")
        return "https://medium.com/@test/pub-2", shot

    monkeypatch.setattr("agent.pipeline.publish_to_medium", fake_publish)
    mark_approved("pub-2")
    url, _ = pipeline.publish("pub-2", dry_run=True)
    assert url == "https://medium.com/@test/pub-2"
    assert db.get_article("pub-2")["state"] == "PUBLISHED"
    approval_path("pub-2").unlink(missing_ok=True)
