from __future__ import annotations

import json
import os
import re
import statistics
from dataclasses import dataclass
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from readability import Document

from .config import CONFIG_DIR, source_timeout


@dataclass
class StyleMetrics:
    tone_profile: str
    sentence_length: dict[str, float]
    paragraph_structure: str
    first_person_ratio: float
    rhetorical_questions: int
    framing_style: str
    vocabulary_density: str
    directness: str
    structural_template: str
    text: str


def _get_html(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 MediumAuthorityEngine/1.0"}
    resp = requests.get(url, headers=headers, timeout=source_timeout())
    resp.raise_for_status()
    return resp.text


def _extract_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article")
    if article:
        blocks = article.find_all(["h1", "h2", "h3", "p", "li"])
        text = "\n".join(b.get_text(" ", strip=True) for b in blocks if b.get_text(strip=True))
        if text.strip():
            return text
    # fallback to readable text blocks
    blocks = soup.find_all(["p", "li"])
    text = "\n".join(b.get_text(" ", strip=True) for b in blocks if b.get_text(strip=True))
    return text.strip()


def _extract_with_readability(html: str) -> str:
    doc = Document(html)
    content_html = doc.summary(html_partial=True)
    soup = BeautifulSoup(content_html, "html.parser")
    blocks = soup.find_all(["h1", "h2", "h3", "p", "li"])
    return "\n".join(b.get_text(" ", strip=True) for b in blocks if b.get_text(strip=True)).strip()


def _extract_with_mercury(url: str) -> str:
    api_key = os.getenv("MERCURY_PARSER_API_KEY", "").strip()
    if not api_key:
        return ""
    endpoint = f"https://mercury.postlight.com/parser?url={quote_plus(url)}"
    resp = requests.get(endpoint, headers={"x-api-key": api_key}, timeout=source_timeout())
    if resp.status_code >= 400:
        return ""
    payload = resp.json()
    content = payload.get("content", "") or ""
    if not content:
        return ""
    soup = BeautifulSoup(content, "html.parser")
    blocks = soup.find_all(["h1", "h2", "h3", "p", "li"])
    return "\n".join(b.get_text(" ", strip=True) for b in blocks if b.get_text(strip=True)).strip()


def fetch_article_text(url: str) -> str:
    html = _get_html(url)
    text = _extract_from_html(html)
    if text:
        return text
    text = _extract_with_readability(html)
    if text:
        return text
    text = _extract_with_mercury(url)
    if text:
        return text
    raise RuntimeError("Failed to extract article text via direct, readability, and Mercury fallbacks.")


def analyze_text(text: str) -> StyleMetrics:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.replace("\n", " ")) if s.strip()]
    words_per_sentence = [len(re.findall(r"\b[\w'-]+\b", s)) for s in sentences] or [0]
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    para_sizes = [len(re.split(r"(?<=[.!?])\s+", p)) for p in paragraphs] or [0]
    first_person = len(re.findall(r"\b(I|we|my|our|us)\b", text, flags=re.IGNORECASE))
    total_words = len(re.findall(r"\b[\w'-]+\b", text)) or 1

    return StyleMetrics(
        tone_profile="analytical, explanatory, corrective",
        sentence_length={
            "mean": round(statistics.mean(words_per_sentence), 2),
            "median": round(statistics.median(words_per_sentence), 2),
            "p25": round(statistics.quantiles(words_per_sentence, n=4)[0], 2)
            if len(words_per_sentence) > 1
            else float(words_per_sentence[0]),
            "p75": round(statistics.quantiles(words_per_sentence, n=4)[2], 2)
            if len(words_per_sentence) > 1
            else float(words_per_sentence[0]),
            "min": float(min(words_per_sentence)),
            "max": float(max(words_per_sentence)),
        },
        paragraph_structure=f"typically {round(statistics.mean(para_sizes), 2)} sentences per paragraph",
        first_person_ratio=round(first_person / total_words, 4),
        rhetorical_questions=sum(1 for s in sentences if s.endswith("?")),
        framing_style="problem-first with mechanism breakdown and implication synthesis",
        vocabulary_density="high technical density with plain-language transitions",
        directness="sharp but controlled",
        structural_template="intro -> assumption diagnosis -> behavior breakdown -> implication -> conclusion",
        text=text,
    )


def write_persona_and_style(metrics: StyleMetrics, source_url: str) -> tuple[str, str]:
    persona_path = CONFIG_DIR / "persona.md"
    style_path = CONFIG_DIR / "style_guide.md"

    persona_path.write_text(
        "\n".join(
            [
                "## Author Persona Profile",
                "",
                "### Intellectual Positioning",
                "Finance & AI practitioner breaking down ALM, AML systems, and model governance - without corporate buzzwords.",
                "",
                "### Voice Summary",
                "Analytical and explanatory with direct, mechanism-level framing. "
                "Reframes incomplete assumptions without theatrical tone.",
                "",
                "### Dominant Intellectual Traits",
                "- Systems thinking",
                "- Failure analysis",
                "- Causal reasoning",
                "- Early signal detection",
                "- Operational realism",
                "",
                "### Tone Boundaries (Hard Rules)",
                "- No political commentary.",
                "- No investment advice.",
                "- No employer/client disclosure.",
                "",
                "### Extracted Metrics Snapshot",
                f"- Source: {source_url}",
                f"- Sentence mean: {metrics.sentence_length['mean']}",
                f"- Paragraph style: {metrics.paragraph_structure}",
                f"- First-person ratio: {metrics.first_person_ratio}",
                f"- Rhetorical questions: {metrics.rhetorical_questions}",
            ]
        ),
        encoding="utf-8",
    )

    style_path.write_text(
        "\n".join(
            [
                "## Writing Style Guide",
                "",
                "### Source Basis",
                f"`{source_url}`",
                "",
                "### Core Constraints",
                f"- Average sentence length target: {max(12, int(metrics.sentence_length['mean'] - 2))}-{min(22, int(metrics.sentence_length['mean'] + 3))} words.",
                "- Preferred paragraph size: 2-4 sentences.",
                "- Default tone: neutral institutional voice.",
                "- Use first-person sparingly; prefer system-level framing.",
                "- Avoid rhetorical questions unless needed for a single transition.",
                "",
                "### Structural Template",
                "1. Problem/assumption statement",
                "2. Why historical model seemed valid",
                "3. Why current conditions break the model",
                "4. Behavior and failure modes",
                "5. Reframed operating lens",
                "6. Practical implication and close",
                "",
                "### Sharp Reframing Rule",
                "Each article must contain 2-3 sharp reframes (precise, surgical statements that clarify misconceptions without being political or aggressive).",
                "",
                "### Buzzwords to avoid",
                "- revolutionary",
                "- game-changing",
                "- disruptive synergy",
                "- paradigm shift",
                "- thought leadership",
                "",
                "### Tone Boundaries",
                "- No political commentary.",
                "- No investment advice.",
                "- No employer/client disclosure.",
            ]
        ),
        encoding="utf-8",
    )
    return str(persona_path), str(style_path)


def metrics_as_json(metrics: StyleMetrics) -> str:
    return json.dumps(
        {
            "tone_profile": metrics.tone_profile,
            "sentence_length": metrics.sentence_length,
            "paragraph_structure": metrics.paragraph_structure,
            "first_person_ratio": metrics.first_person_ratio,
            "rhetorical_questions": metrics.rhetorical_questions,
            "framing_style": metrics.framing_style,
            "vocabulary_density": metrics.vocabulary_density,
            "directness": metrics.directness,
            "structural_template": metrics.structural_template,
        },
        indent=2,
    )
