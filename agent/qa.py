from __future__ import annotations

import re
from dataclasses import dataclass


PATTERNS = {
    "political": [
        r"\b(republican|democrat|election campaign|vote for|left[- ]wing|right[- ]wing)\b",
        r"\b(political party|partisan)\b",
    ],
    "investment_advice": [
        r"\b(you should buy|you should sell|strong buy|strong sell|guaranteed returns)\b",
        r"\b(double your money|risk[- ]free returns?)\b",
    ],
    "buzzword": [
        r"\b(revolutionary|game[- ]changing|disruptive synergy|paradigm shift)\b",
        r"\b(thought leadership|unprecedented opportunity|digital transformation)\b",
    ],
    "overconfident_claims": [
        r"\b(always|never|cannot fail|will certainly|guaranteed)\b",
        r"\b(definitively proves|undeniable truth)\b",
    ],
    "confidentiality": [
        r"\b(confidential|non-public|client-specific|internal-only|under nda)\b",
        r"\b(proprietary model details|undisclosed customer)\b",
    ],
    "controversial": [
        r"\b(scam|fraudulent government|corrupt regime|conspiracy)\b",
        r"\b(outrageous policy theft|agenda pushing)\b",
    ],
}


@dataclass
class QAResult:
    flags: dict[str, list[str]]

    @property
    def ok(self) -> bool:
        return not any(self.flags.values())


def detect_flags(text: str) -> QAResult:
    flags: dict[str, list[str]] = {}
    for category, patterns in PATTERNS.items():
        hits: list[str] = []
        for pattern in patterns:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                phrase = match.group(0)
                if phrase not in hits:
                    hits.append(phrase)
        if hits:
            flags[category] = hits
    return QAResult(flags=flags)
