from __future__ import annotations

from pathlib import Path

from agent.db import AgentDB
from agent.idea_engine import Idea
from agent.pipeline import MediumAuthorityPipeline
from agent.source_verify import SourceVerificationResult
from agent.writer import DraftPackage


def _db(tmp_path: Path) -> AgentDB:
    db = AgentDB(tmp_path / "agent.db")
    db.init()
    return db


def test_flagged_content_blocks_ready_for_review(monkeypatch, tmp_path: Path) -> None:
    db = _db(tmp_path)
    pipeline = MediumAuthorityPipeline(db)

    idea = Idea(
        title="Test topic",
        pillar="AML + AI",
        angle="test",
        week_type="Technical deep dive",
        seed_sources=[{"title": "Fed", "url": "https://federalreserve.gov", "domain": "federalreserve.gov"}],
        source_mode="roadmap",
    )

    monkeypatch.setattr("agent.pipeline.generate_mixed_ideas", lambda: [idea])
    monkeypatch.setattr(
        "agent.pipeline.verify_citations",
        lambda _citations, check_urls=True: SourceVerificationResult(ok=True, errors=[], checked=2),
    )

    flagged_body = (
        "# Test\n\n"
        "This revolutionary method is guaranteed. "
        "If you work in ALM, AML, or model risk - I'd love to hear how your institution handles this."
    )
    monkeypatch.setattr(
        "agent.pipeline.compose_draft",
        lambda _idea, _pool: DraftPackage(
            title="Title",
            title_options=["a", "b", "c", "d", "e"],
            subtitle="Sub",
            tldr="Tldr",
            tags=["ALM", "AML", "AI", "Banking", "ModelRisk"],
            image_suggestions=["i1"],
            body_markdown=flagged_body,
            citations=[
                {"title": "Fed", "url": "https://federalreserve.gov", "domain": "federalreserve.gov"},
                {"title": "BIS", "url": "https://bis.org", "domain": "bis.org"},
            ],
            claims_verification=[{"claim": "x", "source_url": "https://federalreserve.gov", "status": "linked"}],
            metadata={},
        ),
    )

    result = pipeline.create_and_process_one(check_urls=False)
    assert result.status == "blocked"
    article = db.list_articles()[0]
    assert article["state"] == "STYLE_CHECK"
    assert article["metadata"]["requires_rewrite"] is True
