from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import requests
import yaml

from .config import CONFIG_DIR, source_timeout


@dataclass
class SourceVerificationResult:
    ok: bool
    errors: list[str]
    checked: int


def _load_allowlist() -> set[str]:
    data = yaml.safe_load((CONFIG_DIR / "source_allowlist.yaml").read_text(encoding="utf-8"))
    return set(data.get("domains", []))


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().replace("www.", "")


def _is_allowlisted(domain: str, allow: set[str]) -> bool:
    return any(domain == root or domain.endswith(f".{root}") for root in allow)


def verify_citations(citations: list[dict[str, str]], check_urls: bool = True) -> SourceVerificationResult:
    allow = _load_allowlist()
    errors: list[str] = []
    if not citations:
        return SourceVerificationResult(ok=False, errors=["No citations provided."], checked=0)
    checked = 0
    seen: set[str] = set()
    for citation in citations:
        url = citation.get("url", "").strip()
        title = citation.get("title", "").strip()
        if not url or not title:
            errors.append("Citation missing title or URL.")
            continue
        if url in seen:
            errors.append(f"Duplicate citation URL: {url}")
            continue
        seen.add(url)
        domain = _domain(url)
        if not _is_allowlisted(domain, allow):
            errors.append(f"Non-allowlisted citation domain: {domain}")
            continue
        checked += 1
        if check_urls:
            try:
                resp = requests.get(url, timeout=source_timeout(), allow_redirects=True)
                if resp.status_code >= 400:
                    errors.append(f"Citation URL unreachable ({resp.status_code}): {url}")
            except requests.RequestException as exc:
                errors.append(f"Citation URL check failed: {url} ({exc})")
    return SourceVerificationResult(ok=not errors, errors=errors, checked=checked)
