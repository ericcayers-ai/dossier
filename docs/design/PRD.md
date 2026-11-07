# PRD — product requirements

> Reel `DfDlUNVNui4` doc 6. Merged into [PROJECT.md](../PROJECT.md) on 2026-11-06; this file is
> the short form, and `PROJECT.md` is the authority.

## Overview

A local-first job-search workspace for one person on one Windows machine. You point it at a
folder; it indexes what is there and runs the loop a search actually is: capture a posting,
diagnose the resume, extract requirements, tailor a document that clones your own layout, verify
it, apply, track, follow up, negotiate, learn from the outcome.

## Problem

A search is mostly mechanical work repeated under time pressure — re-typing the same facts,
rebuilding a layout, re-reading a posting for the third time — and the judgement part (does this
role fit, is this claim honest) is drowned by it. Existing tools either upload your documents to
someone else's server or turn the whole thing into a chat with no record of what happened.

## Users

One person. No accounts, no multi-tenant surface, no sharing. `PROJECT.md` § "The one idea" and
`DESIGN.md` § Audience both say this, and the code follows: the server binds loopback, authorises
with a per-run token, and sends nothing anywhere (`telemetry.py`: 0 external hosts).

## Success criteria

1. Every claim in a generated document traces to the base document, the identity file or
   something the user said — enforced by the `no-fabrication` gate, not by intent.
2. Mechanical steps are deterministic code; judgement is an injected model working under a
   contract declared once (`src/dossier/agent/manifest.py`).
3. The folder is the source of truth; `.dossier/` is derived and can be deleted without losing a
   user document.
4. Nothing is submitted, sent or published without an explicit user action.
5. A stranger can tell what to do next within one screen (`NextStep`, landing pane).

## Non-goals

- No CAPTCHA farm, proxy pool or fingerprint spoofing beyond the declared stealth script.
- No automated application submit; no auto-send of anything.
- No cloud sync, no accounts, no telemetry.
- No template fallback: a resume without the user's real `.docx` is refused (`base-document`).

## Open questions

- The eval gold set is 18 positive grades: the ranker is measured but cannot yet lose. See
  `docs/STATE.md` § Next action.
