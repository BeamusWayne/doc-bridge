"""Token estimation for chunking decisions."""

from __future__ import annotations


def estimate_tokens(text: str) -> int:
    """Estimate token count for Chinese + English mixed text.

    Rough heuristic: 1 Chinese char ≈ 1.5 tokens, 1 English word ≈ 1.3 tokens.
    We use a simpler approximation: len(text) * 0.6 for mixed CJK content,
    which errs on the side of overestimation (safer for chunking decisions).
    """
    cjk_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    ascii_count = len(text) - cjk_count
    return int(cjk_count * 1.5 + ascii_count * 0.35)


TOKEN_LIMIT = 180_000  # Reserve 20K for prompt + response out of 200K
