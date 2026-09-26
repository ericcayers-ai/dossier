"""Deterministic engines.

Each module here does one class of mechanical work and returns a report rather
than printing one, so a caller can assert on real numbers instead of trusting a
log line. Nothing in this package calls a language model; that is the boundary
the whole repository is built around.
"""

from . import corpus, doctor, jd_skill_gap, negotiate, render, sources, tailor, tracker, verify

__all__ = [
    "corpus",
    "doctor",
    "jd_skill_gap",
    "negotiate",
    "render",
    "sources",
    "tailor",
    "tracker",
    "verify",
]
