# DESIGN-BRIEF

> Reel `DfDlUNVNui4` doc 3. Merged into [DESIGN.md](../../DESIGN.md) on 2026-11-06; that file
> carries the full token table, this is the brief behind it.

## Look and feel

Three adjectives: **quiet, exact, papery**. One anti-reference: the gradient-hero SaaS dashboard.
The metaphor is a light table — documents on a surface, read at a glance, nothing glowing.

## Color tokens

Declared as OKLCH in `ui/src/tokens.css`; light and dark share one role table, and no component
carries a colour literal.

| Role | Light | Dark | Contrast |
|---|---|---|---|
| `--ground` (page) | `oklch(.97 .006 250)` | `oklch(.17 .01 250)` | — |
| `--ink` | `oklch(.24 .02 260)` | `oklch(.95 .005 250)` | 16.2 / 14.9 on sheet |
| `--ink-quiet` | `oklch(.52 .02 260)` | `oklch(.72 .01 250)` | 5.4 / 5.8 |
| `--signal` (fill, focus ring) | `oklch(.62 .17 255)` | same hue, lighter | 3.4 non-text |
| `--stale` (warning) | `oklch(.57 .12 62)` | same role | 4.6 text |

## Type and spacing

Inter for the interface, JetBrains Mono for identifiers only. Six sizes in `tokens.css`, body 13 px;
a 4 px spacing scale; `text-wrap: balance` on headings; measure capped at 68ch.

## Signature element

The **bundle rail**: one file's siblings grouped by role (source / analysis / artifact / render /
proof), the only place in the app where a second column earns its width. One overlay in the whole
app (the palette), which is the only element allowed a shadow.

## What the design refuses

No gradients, no glassmorphism, no cursor glow, no coloured side stripes, no uppercase eyebrows,
no emoji icons, no centred everything. `sloplint` enforces most of it; the rest is in
`DESIGN.md` § "What this is not".
