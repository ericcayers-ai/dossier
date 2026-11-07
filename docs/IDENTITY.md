# Identity and relevance — the target the search is aimed at

Every other mode in Dossier assumes it knows what the user wants. This layer supplies
that, and it supplies it in a way that can be checked.

## Two sources, one precedence

| Source | Where it lives | Authority |
|---|---|---|
| Answers | `.dossier/identity/answers.json` | **wins** — a correction typed today beats a document written in August |
| Documents | `*-IDENTITY.md`, `resume.md`, `job-history.md` | proposal only, with a file and line |
| Nothing | — | the field is **absent**; it is not defaulted |

`dossier identity status` shows which fields came from where. `dossier identity mine`
shows every proposal with its evidence line. `dossier identity write` merges them into a
managed block in `*-IDENTITY.md` (user prose outside the markers is preserved).

The gate is `identity-grounded`: a field reaches `IDENTITY.md` only with an answer or a
document span behind it. There is no default name, no guessed salary, no invented target
role.

## The questionnaire

15 questions, 5 of them required because the ranker cannot infer them safely:

| Required | Why it cannot be mined |
|---|---|
| `target_roles` | a document lists what you *did*; the target is a decision |
| `seniority` | inferable from a student document, not from a career changer's |
| `employment` | internship / part-time / contract is a choice, not a fact |
| `location` | a document's address is not a commuting preference |
| `right_to_work` | a legal status that must never be guessed |

The rest (`remote`, `availability`, `salary_floor`, `currency`, `must_have`,
`nice_to_have`, `deal_breakers`, `languages`, `disclosure`, `pitch`) refine the score and
can be answered later. `disclosure` stores *your rule*; it is never written into a
document automatically.

```text
dossier identity questions                      # with what is already known
dossier identity answer --question salary_floor --value 60000
dossier identity answer --from-json answers.json
```

A blank value clears an answer, because a wrong answer that cannot be removed is worse
than a gap the profile names.

## What is mined, and how

Deterministic patterns only — no model, no guessing:

| Field | Source of truth |
|---|---|
| `name` | the `# Name — …` heading of an identity document |
| `email`, `phone` | the first unambiguous match |
| `timezone` | a `Timezone:` line |
| `location` | a known NZ city/region in the document's opening |
| `seniority` | "second-year"/"student"/"internship" wording |
| `availability` | an explicit availability phrase |
| `skills` | the `Skills` section (with or without markdown hashes) |
| `applied_roles` | the `Role`/`Title` column of `job-history.md` |
| `languages` | a named language |

A proposal whose line cannot be located is still shown, with `line: null` — the citation
is downgraded, never fabricated.

## Relevance: the arithmetic, not a vibe

`score_job` adds and subtracts in the open, and returns `{score, band, reasons,
disqualifiers}`:

| Signal | Effect |
|---|---|
| title tokens match a target role | up to +30 |
| title is in the same role family (software/data/it/design/product/…) | +16 |
| must-have skill present | +12 each, capped |
| nice-to-have present | +6 each, capped |
| skills from the resume present | up to +10 |
| location matches, or remote accepted | +8–10 |
| employment type matches | +8 |
| seniority matches / internship wording | +6–10 |
| advertised pay reaches the floor | +6 |
| language mentioned | +4 |
| posted ≤14 days ago | +6 ( >60 days: −4 ) |

Bands: `strong` ≥ 65, `possible` ≥ 40, `unlikely` below. **A disqualifier caps the band at
`unlikely` and is listed first** — a senior role against a student target, pay under the
floor, a deal-breaker word, or a remote role when the user said onsite-only. The corpus
ranker's rule is inherited here deliberately: a weighted score never hides a
disqualifier.

## Where relevance is used

1. **`dossier identity match`** (and the GUI's Identity → Matches tab) ranks the captured
   corpus. Disqualified rows stay visible under their own heading with the reason.
2. **Capture filter**: `dossier scrape capture --min-match 45` or a recipe's
   `limits.min_match`. A page below the floor is **not archived**, and the run records
   `filtered: true` with the score and the reasons — the page is not silently dropped and
   the run does not claim completeness for it.
3. **Posting frontmatter**: every archived posting carries `match: strong 72`, and
   `match_against:` when a disqualifier was recorded.

## Is the ranking right? (`labels` and `eval`)

`score_job` is arithmetic, so it can be checked. `dossier identity labels` writes a
worksheet — every row scored, its `earned`/`available` and `reasons[]` beside it, and
`grade: null` until a person writes one. The tracker's own `Fit` column is proposed where
an employer and two role tokens match unambiguously, and marked `source_of_grade: tracker`.

`dossier identity eval --labels <file>` reports nDCG@k, precision@k (both over judged rows
and over the k slots actually shown), recall@25 and Spearman against the no-skill
arrival-order baseline on the same rows. `--write-baseline` records the numbers;
`--baseline <file>` makes the command exit non-zero when nDCG@k or Spearman drops past
`evaluation.NDCG_SLACK` / `SPEARMAN_SLACK`, or when the labelled set shrank by more than
half. The gate is `fit-is-measured`.

An ungraded row is never counted as relevant and a grade is never inferred from the score
it is meant to check. First receipt, with its bias stated:
`docs/evidence/fit-eval-2026-11-05.md`.

## What this does not do

- It does not decide what the user wants. An unanswered `target_roles` means no relevance
  score, not an invented one.
- It does not rank by "culture fit" or by an LLM opinion. The score is arithmetic over the
  profile; the reasons are sentences you can argue with.
- It does not withhold a role from the user. A disqualified row is listed with its reason;
  the user can still read and apply.
- The mined `skills` list is a token list, not a competency model: a skill you never
  mention in a document will not appear until you answer for it.
