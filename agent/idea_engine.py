from __future__ import annotations

import random
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

import feedparser
import yaml

from .config import CONFIG_DIR


@dataclass
class Idea:
    title: str
    pillar: str
    angle: str
    week_type: str
    seed_sources: list[dict[str, str]]
    source_mode: str


def _load_yaml(name: str) -> dict:
    path = CONFIG_DIR / name
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _week_of_month(now: datetime) -> int:
    return min(((now.day - 1) // 7) + 1, 4)


def _allowlist_data() -> dict:
    return _load_yaml("source_allowlist.yaml")


def _roadmap_data() -> dict:
    return _load_yaml("roadmap.yaml")


def _domain(url: str) -> str:
    return urlparse(url).netloc.replace("www.", "").lower()


def _guess_pillar(text: str, pillars: list[str]) -> str:
    low = text.lower()
    rules = [
        (("transaction", "instability"), "Transaction Instability Index"),
        (("model", "risk"), "AI in Model Risk Management"),
        (("interest", "rate"), "Interest rate impact on economy"),
        (("alm", "liquidity"), "Asset Liability Management"),
        (("aml", "sanction", "money laundering"), "AML in US and India"),
        (("ai", "machine learning"), "AML + AI"),
    ]
    for keys, pillar in rules:
        if any(k in low for k in keys) and pillar in pillars:
            return pillar
    return pillars[0]


def _source_ideas(week_type: str, limit: int = 6) -> list[Idea]:
    allow = _allowlist_data()
    roadmap = _roadmap_data()
    pillars = roadmap["topic_pillars"]
    allowed = set(allow["domains"])
    ideas: list[Idea] = []
    for feed_url in allow.get("rss_feeds", []):
        parsed = feedparser.parse(feed_url)
        for entry in parsed.entries[:3]:
            link = getattr(entry, "link", "")
            if not link:
                continue
            domain = _domain(link)
            if not any(domain == d or domain.endswith(f".{d}") for d in allowed):
                continue
            title = getattr(entry, "title", "").strip()
            if not title:
                continue
            pillar = _guess_pillar(title, pillars)
            angle = f"Connect current signal from {domain} to operating impact in {pillar.lower()}."
            ideas.append(
                Idea(
                    title=f"{title}: What It Means for Control Design",
                    pillar=pillar,
                    angle=angle,
                    week_type=week_type,
                    seed_sources=[{"title": title, "url": link, "domain": domain}],
                    source_mode="source_generated",
                )
            )
            if len(ideas) >= limit:
                return ideas
    return ideas


def _roadmap_ideas(week_type: str) -> list[Idea]:
    roadmap = _roadmap_data()
    items = roadmap["predefined_roadmap"].get(week_type, [])
    ideas: list[Idea] = []
    for item in items:
        sources = [
            {
                "title": f"Reference from {d}",
                "url": f"https://{d}",
                "domain": d,
            }
            for d in item.get("suggested_domains", [])[:3]
        ]
        ideas.append(
            Idea(
                title=item["title"],
                pillar=item["pillar"],
                angle=item["angle"],
                week_type=week_type,
                seed_sources=sources,
                source_mode="roadmap",
            )
        )
    return ideas


def generate_mixed_ideas(now: datetime | None = None, limit: int = 6) -> list[Idea]:
    now = now or datetime.now(timezone.utc)
    roadmap = _roadmap_data()
    week_idx = _week_of_month(now)
    week_type = roadmap["monthly_structure"][week_idx]
    roadmap_candidates = _roadmap_ideas(week_type)
    source_candidates = _source_ideas(week_type)
    random.shuffle(roadmap_candidates)
    random.shuffle(source_candidates)

    combined: list[Idea] = []
    if roadmap_candidates:
        combined.append(roadmap_candidates[0])
    if source_candidates:
        combined.append(source_candidates[0])
    remaining = roadmap_candidates[1:] + source_candidates[1:]
    random.shuffle(remaining)
    combined.extend(remaining)

    # De-duplicate by normalized title
    seen: set[str] = set()
    final: list[Idea] = []
    for idea in combined:
        key = re.sub(r"\s+", " ", idea.title.lower()).strip()
        if key in seen:
            continue
        seen.add(key)
        final.append(idea)
        if len(final) >= limit:
            break
    return final
