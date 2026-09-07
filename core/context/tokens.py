"""Canonical token counting and estimation for SWARAJ core context management."""

import re

# Calibrated regex for BPE / subword token estimation across English, numbers, code, and Devanagari
# Matches words, numeric sequences, Devanagari graphemes, punctuation, and whitespace chunks
_TOKEN_PATTERN = re.compile(
    r"""[\u0900-\u097F]+|[\w]+|[^\s\w]|[\s]+""",
    re.UNICODE,
)


def count_tokens(text: str) -> int:
    """Calculate calibrated token count for a given text string.

    Provides a consistent, unified token count across context budgeting,
    chunk size enforcement, and prompt assembly.
    """
    if not text:
        return 0

    # Fast path for empty or whitespace
    stripped = text.strip()
    if not stripped:
        return 0

    # Count subword/grapheme tokens
    tokens = _TOKEN_PATTERN.findall(text)
    count = 0
    for tok in tokens:
        if tok.isspace():
            # Large whitespace runs condense
            count += max(1, len(tok) // 4)
        elif any("\u0900" <= c <= "\u097F" for c in tok):
            # Devanagari words often tokenize to ~1.3-1.8 tokens per word in BPE
            count += max(1, int(len(tok) * 0.8))
        elif len(tok) > 6 and tok.isalnum():
            # Long alphanumeric identifiers (e.g. NCR-MRPL-2026-088) tokenize to multiple subwords
            count += (len(tok) + 3) // 4
        else:
            count += 1

    return max(1, count)
