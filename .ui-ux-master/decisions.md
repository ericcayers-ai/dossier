# Decisions (P2) — refine, not replace

**Verdict: refine.** The audit's P0s were execution failures, not a wrong identity: the
light-table metaphor (ink on tinted paper, hairline rules, square panels, serif prose, mono
figures) is specific to this product and already carries the hierarchy. Replacing it would
have thrown away the one thing that makes Dossier not look generated, to fix a nav strip and
a spacing scale.

**Anti-reference (what must not survive):** eleven flat pane buttons in one strip; three
different page paddings in sibling panes; a topbar that overlaps its own controls at 390 px;
an `--ink` that is inherited from `body` and therefore wrong in dark; a dark theme nobody had
measured; "PARTIAL" shouting at the user; a loading pane that forgets its own heading.

**Preserved on purpose:** the 11 panes and their capability set (nothing was deleted to make
the nav tidy — the operator's rule is capability-preserving toggles, not amputation); the
OKLCH palette and its two chromatic tokens; the square-panel, 4 px-radius-on-controls
geometry; the reading surface (explorer → viewer → bundle rail); every API call and every
gate. No route, endpoint or test was removed.

**Cost accepted:** the two-level nav adds one click to reach a pane that is not the first in
its area. It buys a header that fits at 390 px, a scannable area label, and a screen-reader
structure with one `nav` per level instead of eleven buttons with no grouping.
