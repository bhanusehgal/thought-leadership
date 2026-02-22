from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .config import email_capture_url
from .writer import REQUIRED_CLOSING


@dataclass
class StyleResult:
    ok: bool
    checklist: dict[str, bool]
    findings: list[str]


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def _sentences(text: str) -> list[str]:
    normalized = text.replace("\n", " ")
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", normalized) if s.strip()]


def _avg_sentence_len(text: str) -> float:
    sent = _sentences(text)
    if not sent:
        return 0.0
    counts = [_word_count(s) for s in sent]
    return sum(counts) / len(counts)


def _sharp_reframe_count(text: str) -> int:
    low = text.lower()
    heading_hits = len(re.findall(r"sharp reframe #\d+", low))
    if heading_hits:
        return heading_hits
    sentences = _sentences(text)
    sentence_patterns = [
        r"\bcorrect yet incomplete\b",
        r"\bnot just\b",
        r"\bno longer be assumed\b",
        r"\bthe goal is not to\b",
        r"\bthis is not\b",
    ]
    count = 0
    for sentence in sentences:
        s = sentence.lower()
        if any(re.search(pattern, s) for pattern in sentence_patterns):
            count += 1
            continue
        # Keep this surgical: only count explicit "not X but Y" constructs within one sentence.
        if re.search(r"\bnot [^.!?]{1,90}\bbut\b", s):
            count += 1
    return count


def _contains_near_advice(text: str) -> bool:
    hints = ("invest", "return", "yield", "portfolio", "buy", "sell", "trade")
    low = text.lower()
    return any(h in low for h in hints)


def evaluate_style(article: dict[str, Any], citations_allowlisted: bool) -> StyleResult:
    body = article.get("body_markdown", "")
    word_count = _word_count(body)
    avg_sentence_len = _avg_sentence_len(body)
    sharp_count = _sharp_reframe_count(body)
    capture_url = email_capture_url()
    checklist = {
        "word_count": 800 <= word_count <= 1200,
        "citations_allowlisted": citations_allowlisted,
        "title_count": len(article.get("title_options", [])) == 5,
        "tag_count": len(article.get("tags", [])) == 5,
        "closing_line": REQUIRED_CLOSING in body,
        "sharp_reframes": 2 <= sharp_count <= 3,
        "avg_sentence_len": 12 <= avg_sentence_len <= 20,
        "email_capture_link": (not capture_url) or (capture_url in body),
        "disclaimer_if_needed": (not _contains_near_advice(body)) or ("not investment advice" in body.lower()),
    }
    findings: list[str] = []
    if not checklist["word_count"]:
        findings.append(f"Word count {word_count} is outside 800-1200.")
    if not checklist["title_count"]:
        findings.append("Expected exactly 5 title options.")
    if not checklist["tag_count"]:
        findings.append("Expected exactly 5 tags.")
    if not checklist["closing_line"]:
        findings.append("Missing required closing sentence.")
    if not checklist["sharp_reframes"]:
        findings.append(f"Expected 2-3 sharp reframes; found {sharp_count}.")
    if not checklist["avg_sentence_len"]:
        findings.append(f"Average sentence length {avg_sentence_len:.1f} outside 12-20.")
    if not checklist["email_capture_link"]:
        findings.append("EMAIL_CAPTURE_URL is set but link was not inserted.")
    if not checklist["disclaimer_if_needed"]:
        findings.append("Investment-near language detected without disclaimer.")
    if not checklist["citations_allowlisted"]:
        findings.append("Citation verification failed.")
    return StyleResult(ok=all(checklist.values()), checklist=checklist, findings=findings)
