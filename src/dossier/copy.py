"""Words the engine says to a person.

The engine builds sentences that land on the landing page, in the agent brief and in
the hand-back errors. They read `3 row(s)` — the placeholder style of a log line —
until they go through here.
"""
from __future__ import annotations


def plural(n: int, one: str, many: str | None = None) -> str:
    """`1 file`, `2 files`. Pass `many` for words that do not just take an `s`."""
    return f"{n} {one if n == 1 else (many or one + 's')}"
