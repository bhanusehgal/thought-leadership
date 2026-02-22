from __future__ import annotations

STATES = (
    "IDEA",
    "OUTLINE",
    "DRAFT",
    "SOURCE_VERIFY",
    "STYLE_CHECK",
    "READY_FOR_REVIEW",
    "APPROVED",
    "PUBLISHED",
    "FAILED",
)

ALLOWED_TRANSITIONS = {
    "IDEA": {"OUTLINE", "FAILED"},
    "OUTLINE": {"DRAFT", "FAILED"},
    "DRAFT": {"SOURCE_VERIFY", "FAILED"},
    "SOURCE_VERIFY": {"STYLE_CHECK", "DRAFT", "FAILED"},
    "STYLE_CHECK": {"READY_FOR_REVIEW", "DRAFT", "FAILED"},
    "READY_FOR_REVIEW": {"APPROVED", "DRAFT", "FAILED"},
    "APPROVED": {"PUBLISHED", "DRAFT", "FAILED"},
    "PUBLISHED": set(),
    "FAILED": {"DRAFT"},
}


class StateError(RuntimeError):
    pass


def can_transition(current: str, nxt: str) -> bool:
    return nxt in ALLOWED_TRANSITIONS.get(current, set())
