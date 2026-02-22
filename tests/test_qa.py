from __future__ import annotations

from agent.qa import detect_flags


def test_qa_gate_detection() -> None:
    text = (
        "This revolutionary framework is a guaranteed returns engine. "
        "Vote for this party if you want better banking. "
        "These are confidential internal-only model details."
    )
    result = detect_flags(text)
    assert "buzzword" in result.flags
    assert "investment_advice" in result.flags
    assert "political" in result.flags
    assert "confidentiality" in result.flags
