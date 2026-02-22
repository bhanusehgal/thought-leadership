from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import yaml

from .approvals import has_approval, mark_approved
from .artifacts import write_draft, write_metadata
from .config import CONFIG_DIR
from .db import AgentDB
from .idea_engine import Idea, generate_mixed_ideas
from .publisher import publish_to_medium
from .qa import detect_flags
from .review_portal import build_review_portal
from .review_renderer import render_review
from .scheduler import next_saturday_9pm_et, should_run_weekly
from .source_verify import verify_citations
from .style_check import evaluate_style
from .writer import compose_draft


@dataclass
class PipelineResult:
    article_id: str | None
    status: str
    message: str


def _supplement_citations(seed: list[dict[str, str]]) -> list[dict[str, str]]:
    allow_cfg = yaml.safe_load((CONFIG_DIR / "source_allowlist.yaml").read_text(encoding="utf-8"))
    domains = allow_cfg.get("domains", [])
    pool = list(seed)
    existing = {c["url"] for c in seed if "url" in c}
    for domain in domains:
        url = f"https://{domain}"
        if url in existing:
            continue
        pool.append(
            {
                "title": f"Primary publication index - {domain}",
                "url": url,
                "domain": domain,
            }
        )
        if len(pool) >= 5:
            break
    return pool


def _current_week_type() -> str:
    ideas = generate_mixed_ideas(limit=1)
    if ideas:
        return ideas[0].week_type
    return "Technical deep dive"


def _normalize_source_url(url: str, idx: int) -> dict[str, str]:
    domain = urlparse(url).netloc.replace("www.", "").lower()
    return {
        "title": f"User provided source {idx}",
        "url": url.strip(),
        "domain": domain,
    }


def _infer_pillar(topic: str) -> str:
    low = topic.lower()
    if "interest rate" in low or ("rate" in low and "econom" in low):
        return "Interest rate impact on economy"
    if "alm" in low or "asset liability" in low or "liquidity" in low:
        return "Asset Liability Management"
    if "model risk" in low:
        return "AI in Model Risk Management"
    if "transaction instability" in low:
        return "Transaction Instability Index"
    if "aml" in low and "ai" in low:
        return "AML + AI"
    if "aml" in low:
        return "AML in US and India"
    if "ai" in low:
        return "AML + AI"
    return "Asset Liability Management"


def _outline_for_idea(idea: Idea) -> list[str]:
    return [
        "Assumption to challenge",
        "Historical context and why prior controls seemed enough",
        "Observed failure pattern in current transaction dynamics",
        "Framework reframe with control linkage",
        "Implementation and operating checklist",
    ]


class MediumAuthorityPipeline:
    def __init__(self, db: AgentDB):
        self.db = db

    def _process_idea(self, selected: Idea, seed_sources: list[dict[str, str]], check_urls: bool = True) -> PipelineResult:
        if self.db.count_state("READY_FOR_REVIEW") >= 3:
            return PipelineResult(
                article_id=None,
                status="skipped",
                message="Review queue at capacity (max 3 READY_FOR_REVIEW items).",
            )
        article_id = datetime.now(timezone.utc).strftime("%Y%m%d") + "-" + uuid4().hex[:8]
        schedule_at = next_saturday_9pm_et().isoformat()
        self.db.insert_article(
            {
                "id": article_id,
                "pillar": selected.pillar,
                "topic": selected.title,
                "week_type": selected.week_type,
                "state": "IDEA",
                "scheduled_publish_at": schedule_at,
                "metadata": {"idea": selected.__dict__},
            }
        )

        self.db.transition(article_id, "OUTLINE", reason="Generated initial outline.")
        article = self.db.get_article(article_id)
        metadata = article["metadata"]
        metadata["outline"] = _outline_for_idea(selected)
        self.db.update_article(article_id, metadata=metadata)

        self.db.transition(article_id, "DRAFT", reason="Drafting content package.")
        citation_pool = _supplement_citations(seed_sources)
        draft = compose_draft(selected, citation_pool)
        self.db.update_article(
            article_id,
            title=draft.title,
            subtitle=draft.subtitle,
            tldr=draft.tldr,
            body_markdown=draft.body_markdown,
            tags=draft.tags,
            title_options=draft.title_options,
            image_suggestions=draft.image_suggestions,
            citations=draft.citations,
            claims_verification=draft.claims_verification,
            metadata=draft.metadata,
        )
        write_draft(article_id, draft.body_markdown)
        self.db.transition(article_id, "SOURCE_VERIFY", reason="Running citation verification.")

        article = self.db.get_article(article_id)
        source_result = verify_citations(article["citations"], check_urls=check_urls)
        metadata = article["metadata"]
        metadata["source_verify"] = {"ok": source_result.ok, "errors": source_result.errors}
        self.db.update_article(article_id, metadata=metadata)

        if not source_result.ok:
            self.db.transition(article_id, "FAILED", reason="Citation verification failed.")
            failed = self.db.get_article(article_id)
            write_metadata(failed)
            return PipelineResult(article_id, "failed", "Citation verification failed.")

        self.db.transition(article_id, "STYLE_CHECK", reason="Running style and QA gates.")
        article = self.db.get_article(article_id)

        qa_result = detect_flags(
            "\n".join(
                [
                    article.get("title") or "",
                    article.get("subtitle") or "",
                    article.get("body_markdown") or "",
                ]
            )
        )
        style_result = evaluate_style(article, citations_allowlisted=True)

        metadata = article["metadata"]
        metadata["flags"] = qa_result.flags
        metadata["style_findings"] = style_result.findings
        metadata["checklist"] = style_result.checklist
        blocked = bool(qa_result.flags) or (not style_result.ok)
        metadata["requires_rewrite"] = blocked
        self.db.update_article(article_id, metadata=metadata)
        article = self.db.get_article(article_id)
        write_metadata(article)

        if blocked:
            render_review(article, style_result.checklist, qa_result.flags)
            build_review_portal(self.db)
            return PipelineResult(
                article_id=article_id,
                status="blocked",
                message="Blocked at STYLE_CHECK. Rewrite required before READY_FOR_REVIEW.",
            )

        self.db.transition(article_id, "READY_FOR_REVIEW", reason="All QA/style gates passed.")
        ready = self.db.get_article(article_id)
        render_review(ready, style_result.checklist, qa_result.flags)
        build_review_portal(self.db)
        write_metadata(ready)
        return PipelineResult(article_id, "ready", "Draft ready for human review.")

    def create_and_process_one(self, check_urls: bool = True) -> PipelineResult:
        ideas = generate_mixed_ideas()
        if not ideas:
            return PipelineResult(None, "failed", "No ideas available from roadmap/source mix.")
        selected = next((i for i in ideas if i.source_mode == "roadmap"), ideas[0])
        source_sidecar = next((i for i in ideas if i.source_mode == "source_generated"), None)
        seed_sources = list(selected.seed_sources)
        if source_sidecar and source_sidecar.seed_sources:
            seed_sources.extend(source_sidecar.seed_sources[:2])
        return self._process_idea(selected=selected, seed_sources=seed_sources, check_urls=check_urls)

    def create_from_topic(
        self,
        topic: str,
        pillar: str | None = None,
        week_type: str | None = None,
        source_urls: list[str] | None = None,
        check_urls: bool = True,
    ) -> PipelineResult:
        topic = topic.strip()
        if not topic:
            return PipelineResult(None, "failed", "Topic cannot be empty.")
        source_urls = [u.strip() for u in (source_urls or []) if u.strip()]
        seed_sources = [_normalize_source_url(url, idx + 1) for idx, url in enumerate(source_urls)]
        selected = Idea(
            title=topic,
            pillar=(pillar or _infer_pillar(topic)),
            angle="User provided topic processed through allowlisted source verification.",
            week_type=(week_type or _current_week_type()),
            seed_sources=seed_sources,
            source_mode="user_topic",
        )
        return self._process_idea(selected=selected, seed_sources=seed_sources, check_urls=check_urls)

    def run_weekly(self, count: int = 1, respect_schedule: bool = False, check_urls: bool = True) -> list[PipelineResult]:
        if respect_schedule and not should_run_weekly():
            return [PipelineResult(None, "skipped", "Not in Saturday 9PM ET publish window.")]
        results: list[PipelineResult] = []
        for _ in range(max(1, count)):
            if self.db.count_state("READY_FOR_REVIEW") >= 3:
                results.append(
                    PipelineResult(None, "skipped", "Review queue full; generation halted at max=3.")
                )
                break
            results.append(self.create_and_process_one(check_urls=check_urls))
        return results

    def approve(self, article_id: str) -> str:
        article = self.db.get_article(article_id)
        if article["state"] != "READY_FOR_REVIEW":
            raise RuntimeError(f"Cannot approve from state {article['state']}. Must be READY_FOR_REVIEW.")
        path = mark_approved(article_id)
        self.db.transition(article_id, "APPROVED", reason="Human approval marker created.")
        approved = self.db.get_article(article_id)
        write_metadata(approved)
        return str(path)

    def publish(self, article_id: str, dry_run: bool = False) -> tuple[str, str]:
        article = self.db.get_article(article_id)
        if article["state"] != "APPROVED":
            raise RuntimeError(f"Cannot publish from state {article['state']}. Must be APPROVED.")
        if not has_approval(article_id):
            raise RuntimeError("Approval file missing; publishing blocked.")
        url, screenshot_path = publish_to_medium(article, dry_run=dry_run)
        metadata = article["metadata"]
        metadata["published_screenshot"] = str(screenshot_path)
        self.db.update_article(article_id, published_url=url, metadata=metadata)
        self.db.transition(article_id, "PUBLISHED", reason="Published to Medium.")
        published = self.db.get_article(article_id)
        write_metadata(published)
        return url, str(screenshot_path)

    def publish_approved(self, dry_run: bool = False) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        for article in self.db.list_articles(state="APPROVED"):
            if not has_approval(article["id"]):
                continue
            url, shot = self.publish(article["id"], dry_run=dry_run)
            out.append({"id": article["id"], "url": url, "screenshot": shot})
        return out
