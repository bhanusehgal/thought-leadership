from __future__ import annotations

from pathlib import Path

import pytest

from agent.db import AgentDB
from agent.states import StateError


def _new_db(tmp_path: Path) -> AgentDB:
    db = AgentDB(tmp_path / "agent.db")
    db.init()
    return db


def _insert_min_article(db: AgentDB, article_id: str, state: str = "IDEA") -> None:
    db.insert_article(
        {
            "id": article_id,
            "pillar": "Asset Liability Management",
            "topic": f"Topic {article_id}",
            "week_type": "Technical deep dive",
            "state": state,
            "metadata": {},
        }
    )


def test_state_transitions_happy_path(tmp_path: Path) -> None:
    db = _new_db(tmp_path)
    _insert_min_article(db, "a1", "IDEA")
    db.transition("a1", "OUTLINE")
    db.transition("a1", "DRAFT")
    db.transition("a1", "SOURCE_VERIFY")
    db.transition("a1", "STYLE_CHECK")
    db.transition("a1", "READY_FOR_REVIEW")
    db.transition("a1", "APPROVED")
    assert db.get_article("a1")["state"] == "APPROVED"


def test_illegal_transition_rejected(tmp_path: Path) -> None:
    db = _new_db(tmp_path)
    _insert_min_article(db, "a2", "IDEA")
    with pytest.raises(StateError):
        db.transition("a2", "DRAFT")


def test_ready_for_review_limit_of_three(tmp_path: Path) -> None:
    db = _new_db(tmp_path)
    for i in range(4):
        _insert_min_article(db, f"a{i}", "STYLE_CHECK")
    db.transition("a0", "READY_FOR_REVIEW")
    db.transition("a1", "READY_FOR_REVIEW")
    db.transition("a2", "READY_FOR_REVIEW")
    with pytest.raises(StateError):
        db.transition("a3", "READY_FOR_REVIEW")
