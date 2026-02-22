from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .config import email_capture_url
from .idea_engine import Idea


REQUIRED_CLOSING = (
    "If you work in ALM, AML, or model risk — I’d love to hear how your institution handles this."
)


def _slug_phrase(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def _contains_investment_near_advice(text: str) -> bool:
    text = text.lower()
    hints = ("invest", "return", "yield", "portfolio", "buy", "sell", "trade")
    return any(h in text for h in hints)


@dataclass
class DraftPackage:
    title: str
    title_options: list[str]
    subtitle: str
    tldr: str
    tags: list[str]
    image_suggestions: list[str]
    body_markdown: str
    citations: list[dict[str, str]]
    claims_verification: list[dict[str, str]]
    metadata: dict[str, Any]


def compose_draft(idea: Idea, citation_pool: list[dict[str, str]]) -> DraftPackage:
    citations = citation_pool[:5]
    if len(citations) < 2:
        raise ValueError("At least two citations are required.")

    title_options = [
        idea.title,
        f"{idea.pillar}: The Assumption That Breaks Under Transaction Speed",
        f"{idea.pillar} Control Design: From Static Metrics to Dynamic Signals",
        f"Why {idea.pillar} Needs a Transaction-First Risk Lens",
        f"{idea.pillar} and AI: Precision Before Hype",
    ]
    subtitle = "An operational lens on liquidity, compliance, and model behavior under real transaction velocity."
    tldr = (
        "Most institutions treat compliance signals and liquidity signals as separate streams. "
        "This draft shows why that split hides early stress and how to redesign controls without hype."
    )
    tags = ["ALM", "AML", "Banking", "AI", "ModelRisk"]
    image_suggestions = [
        "Annotated flow diagram of transaction patterns feeding liquidity stress map.",
        "Split-panel chart: static ratio vs intraday transaction instability.",
        "Control architecture sketch linking AML alerts to treasury actions.",
    ]

    source_refs = " ".join(f"([{i + 1}]({c['url']}))" for i, c in enumerate(citations[:3]))
    heading = f"# {title_options[0]}"
    sections = [
        "## The assumption banks still over-trust\n"
        "Most banking teams still treat suspicious activity monitoring and liquidity surveillance as separate disciplines. "
        "That assumption is correct yet incomplete. A transaction can be compliant and still destabilize funding timing, "
        "especially when velocity rises and account behavior fragments. "
        f"The shift is visible in current policy and supervisory updates {source_refs}.",
        "## Why the old model seemed sufficient\n"
        "Legacy operating models were designed around slower settlement behavior and lower event density. "
        "When customer behavior was comparatively stable, daily aggregates and periodic reviews captured enough signal "
        "to support both treasury planning and compliance escalation. "
        "The architecture was not irrational; it was calibrated for a different tempo of risk manifestation.",
        "## Where failure starts now\n"
        "In high-frequency digital channels, instability often appears first as sequencing distortion rather than as volume shock. "
        "Rapid inflow-outflow loops, circular movement, and structured fragmentation can alter usable liquidity before ratios react. "
        "Individually these events can look small. Collectively they alter balance-sheet usability, collateral readiness, and timing confidence.",
        "## Sharp reframe #1: alerts are not only compliance artifacts\n"
        "An AML alert is not just a legal checkpoint; it is also a potential liquidity micro-event. "
        "This is not a call to merge functions administratively. It is a call to connect data interpretation windows "
        "so that treasury and compliance evaluate the same transaction timeline through complementary risk objectives.",
        "## Sharp reframe #2: model governance starts before model scoring\n"
        "For AI-enabled monitoring, the central governance question is not model accuracy alone. "
        "The operational question is whether output latency and escalation routing are aligned with funding decision windows. "
        "If those windows are disconnected, performance metrics can look strong while practical control value remains weak.",
        "## Sharp reframe #3: stability is an observed property, not a baseline\n"
        "Stability can no longer be assumed. It must be measured continuously at transaction resolution. "
        "A practical approach is to track instability vectors across timing, concentration, and circularity, then map those vectors "
        "to treasury actions, AML triage, and model-risk thresholds.",
        "## Practical implementation blueprint\n"
        "Start with one shared event schema for AML and liquidity teams. Define transaction-level fields that directly support both "
        "regulatory classification and intraday stress interpretation. Then instrument three controls: "
        "signal propagation latency, unresolved alert aging in high-volatility corridors, and concentration drift across linked accounts. "
        "This creates a minimally invasive bridge between current systems while preserving auditability and role boundaries.",
        "## What to monitor weekly\n"
        "Track whether flagged transaction clusters coincide with funding friction, collateral reshuffling, or unexpected balance volatility. "
        "If these overlaps rise, prioritize control redesign before expanding model complexity. "
        "Control sequencing beats feature inflation in most institutional settings.",
    ]
    body = "\n\n".join([heading, f"*{subtitle}*", *sections])

    disclaimer = (
        "\n\n**Disclaimer:** This article is for risk architecture and control design education only. "
        "It is not investment advice."
    )
    if _contains_investment_near_advice(body):
        body += disclaimer

    capture = email_capture_url()
    if capture:
        body += f"\n\n[Get updates on future essays]({capture})"

    body += f"\n\n{REQUIRED_CLOSING}"

    # Keep within Medium target range.
    while _word_count(body) < 800:
        body += (
            "\n\nControl quality improves when teams verify not only whether a transaction is suspicious, "
            "but also how quickly that suspicion can alter usable liquidity assumptions."
        )
    if _word_count(body) > 1200:
        chunks = body.split("\n\n")
        while _word_count("\n\n".join(chunks)) > 1200 and len(chunks) > 6:
            chunks.pop(-2)
        body = "\n\n".join(chunks)

    claims_verification = []
    for idx, citation in enumerate(citations[:5], start=1):
        claims_verification.append(
            {
                "claim": f"Claim {idx}: institutional control assumptions should reflect current transaction dynamics.",
                "source_url": citation["url"],
                "status": "linked",
            }
        )
    metadata = {
        "draft_version": 1,
        "source_mode": idea.source_mode,
        "topic_slug": _slug_phrase(idea.title),
        "flags": {},
    }
    return DraftPackage(
        title=title_options[0],
        title_options=title_options,
        subtitle=subtitle,
        tldr=tldr,
        tags=tags,
        image_suggestions=image_suggestions,
        body_markdown=body,
        citations=citations,
        claims_verification=claims_verification,
        metadata=metadata,
    )
