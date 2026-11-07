"""Does the ranking agree with a human? The measurement the app never had.

`score_job` is deterministic arithmetic and `rank_corpus` sorts by it, but nothing on
this machine said whether that order was *right*. On the only real run, 554 rows scored
0 strong / 12 possible / 542 unlikely and no row carried a human grade, so "possible"
could have meant anything.

This module is the instrument. It joins three things the workspace already holds:

* the rows the app can score (the captured corpus, and the archived
  `job-posting-*.md` files it wrote itself),
* a **labels file** — a human grade per row, with the key it was graded on, and
* the tracker's own `Fit` column, which is the user's judgement already written down.

and reports the four numbers an information-retrieval evaluation reports: nDCG@k,
precision@k, recall@k and the Spearman rank correlation between the score and the
grades. It also scores the alternative the app would otherwise have used — the order
the rows arrived in — so an improvement is a comparison, not a claim.

Two rules, both learned from the diseases this file exists to cure:

1. **A grade is not inferred.** `labels --write` produces a worksheet with `grade: null`
   and the evidence beside each row; only a person fills it. The one exception is the
   tracker's own `Fit` value, which is the user's judgement recorded earlier, and it is
   marked `source: tracker` so the report can separate it from fresh grades.
2. **A metric never stands alone.** Every report carries `n_graded`, the rows the
   grader did not see, and the no-skill baseline on the same rows. A precision@10 over
   four labelled rows is reported as such, never as "precision 0.9".

The gate is `fit-is-measured` and it fails on a regression: `dossier identity eval`
exits non-zero when nDCG@k or Spearman drops below the recorded baseline.
"""

from __future__ import annotations

import json
import math
import re
from datetime import date
from pathlib import Path

#: The graded relevance scale. `skip` is not "bad": it is "would not apply at all",
#: and it earns nothing — a document that is irrelevant should not be ranked above a
#: row the user merely did not reach.
GRADES = {"strong": 3, "possible": 2, "unlikely": 1, "skip": 0}

#: The tracker's four-value scale, and the only place a grade may be carried over
#: without a person re-reading the row. It is the user's own judgement, recorded at
#: the time the document was built.
TRACKER_GRADES = {"high": "strong", "medium": "possible", "low": "unlikely",
                  "skip": "skip", "unset": "skip", "": "skip"}

#: A regression threshold, not a tolerance for wishes. nDCG@10 is coarse on a small
#: set, so half a point of drift is noise; five points of Spearman is not.
NDCG_SLACK = 0.02
SPEARMAN_SLACK = 0.05

RELEVANCE_HEADER = "# relevance labels"


# --------------------------------------------------------------------------
# rows and keys
# --------------------------------------------------------------------------

def _norm(text: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text or "").casefold()).strip()


def _tokens(text: object) -> set[str]:
    return {token for token in _norm(text).split() if len(token) > 2}


def row_key(row: dict) -> str:
    """The key a grade is attached to.

    A URL is the strongest identity and is used when present. Otherwise the
    normalised title and employer pair — the same pair `corpus.match_row` treats as
    a unique identity, never a guess between two postings that share one.
    """
    url = str(row.get("url") or "").strip()
    if url:
        return f"url:{_norm(url)}"
    return f"pair:{_norm(row.get('title'))}|{_norm(row.get('employer'))}"


def posting_rows(root: Path | str) -> list[dict]:
    """Every archived `job-posting-*.md` as a corpus-shaped row.

    The postings are the only listing evidence the app captured itself, so they are
    the honest set to evaluate on: each one has a title, an employer, often a
    location and URL in its header block, and the full advertisement as its body.
    """
    root = Path(root)
    rows: list[dict] = []
    for path in sorted(root.glob("job-posting-*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        title = ""
        match = re.search(r"^#\s+(.+)$", text, re.M)
        if match:
            title = match.group(1).strip()
        employer = ""
        for pattern in (r"^[-*]?\s*Employer:\s*(.+)$", r"^Company:\s*(.+)$",
                        r"^[-*]?\s*Organisation:\s*(.+)$"):
            found = re.search(pattern, text, re.M | re.I)
            if found:
                employer = found.group(1).strip()
                break
        if not employer:
            # "job-posting-<Employer>-<Role>.md" and " — <Employer>" in the heading.
            tail = re.search(r"[—–-]\s*([A-Z][\w&.' ]{2,40})\s*$", title)
            if tail:
                employer = tail.group(1).strip()
            else:
                employer = path.stem.split("-")[2] if len(path.stem.split("-")) > 2 else ""
        location = ""
        found = re.search(r"^[-*]?\s*Location:\s*(.+)$", text, re.M | re.I)
        if found:
            location = found.group(1).strip()
        url = ""
        for pattern in (r"Source(?:\s+URL)?:\s*(https?://\S+)",):
            found = re.search(pattern, text, re.I)
            if found:
                url = found.group(1).rstrip(").,")
                break
        rows.append({"id": path.stem, "title": title, "employer": employer,
                     "location": location, "url": url, "source": "posting",
                     "description": text[:20000], "path": path.name})
    return rows


def tracker_rows(root: Path | str) -> list[dict]:
    """The tracker's own rows: the user's Fit value, already recorded."""
    path = Path(root) / "job-history.md"
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip().startswith("|") or set(line.replace("|", "").strip()) <= set("-: "):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 5 or cells[0].casefold() in ("date",):
            continue
        rows.append({"date": cells[0], "employer": cells[1], "role": cells[2],
                     "fit": cells[3], "resume": cells[4],
                     "status": cells[5] if len(cells) > 5 else ""})
    return rows


def labels_from_tracker(root: Path | str, rows: list[dict]) -> tuple[dict[str, dict], list[dict]]:
    """Carry the tracker's Fit onto the rows it unambiguously describes.

    Unambiguous means: the employer's own name tokens appear in the row, *and* the
    tracker role shares at least two meaningful tokens with the row title. Anything
    less is returned as `unmatched` with its reason — a grade attached to the wrong
    listing is worse than no grade, because it is invisible.
    """
    grades: dict[str, dict] = {}
    unmatched: list[dict] = []
    index = [(_tokens(row.get("employer")) | _tokens(row.get("title")),
              _tokens(row.get("title")), row) for row in rows]
    for entry in tracker_rows(root):
        grade = TRACKER_GRADES.get(entry["fit"].casefold(), "")
        if not grade:
            continue
        employer_tokens = _tokens(entry["employer"])
        role_tokens = _tokens(entry["role"])
        best: tuple[int, dict | None] = (0, None)
        for haystack, title_tokens, row in index:
            if not employer_tokens or not employer_tokens & haystack:
                continue
            overlap = len(role_tokens & title_tokens)
            if overlap > best[0]:
                best = (overlap, row)
        if best[1] is None or best[0] < 2:
            unmatched.append({"employer": entry["employer"], "role": entry["role"],
                              "fit": entry["fit"],
                              "reason": "no archived posting shares the employer and two role tokens"})
            continue
        key = row_key(best[1])
        if key in grades:
            unmatched.append({"employer": entry["employer"], "role": entry["role"],
                              "fit": entry["fit"],
                              "reason": "another tracker row already graded this posting"})
            continue
        grades[key] = {"grade": grade, "source": "tracker", "why": f"tracker Fit {entry['fit']}",
                       "title": best[1].get("title", ""), "employer": best[1].get("employer", "")}
    return grades, unmatched


# --------------------------------------------------------------------------
# the metric arithmetic
# --------------------------------------------------------------------------

def _ranks(values: list[float]) -> list[float]:
    """Average ranks, ties included — Spearman on tied scores is not the naive one."""
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position
        while end + 1 < len(order) and values[order[end + 1]] == values[order[position]]:
            end += 1
        average = (position + end) / 2 + 1
        for slot in range(position, end + 1):
            ranks[order[slot]] = average
        position = end + 1
    return ranks


def spearman(left: list[float], right: list[float]) -> float | None:
    if len(left) < 3 or len(left) != len(right):
        return None
    a, b = _ranks(left), _ranks(right)
    mean_a, mean_b = sum(a) / len(a), sum(b) / len(b)
    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
    var_a = math.sqrt(sum((x - mean_a) ** 2 for x in a))
    var_b = math.sqrt(sum((y - mean_b) ** 2 for y in b))
    if not var_a or not var_b:
        return None
    return round(cov / (var_a * var_b), 4)


def dcg(grades: list[int]) -> float:
    return sum((2 ** grade - 1) / math.log2(index + 2) for index, grade in enumerate(grades))


def ndcg_at_k(ranked_grades: list[int], all_grades: list[int], k: int) -> float | None:
    ideal = sorted(all_grades, reverse=True)[:k]
    best = dcg(ideal)
    if not best:
        return None
    return round(dcg(ranked_grades[:k]) / best, 4)


def precision_at_k(ranked_grades: list[int], k: int, *, floor: int = 2) -> float | None:
    top = ranked_grades[:k]
    if not top:
        return None
    return round(sum(1 for grade in top if grade >= floor) / len(top), 4)


def recall_at_k(ranked_grades: list[int], all_grades: list[int], k: int, *, floor: int = 2) -> float | None:
    relevant = sum(1 for grade in all_grades if grade >= floor)
    if not relevant:
        return None
    return round(sum(1 for grade in ranked_grades[:k] if grade >= floor) / relevant, 4)


# --------------------------------------------------------------------------
# the evaluation
# --------------------------------------------------------------------------

def _order_by(items: list[dict], key) -> list[int]:
    return sorted(range(len(items)), key=lambda index: key(items[index]))


def evaluate_rows(rows: list[dict], profile_data: dict, grades: dict[str, dict],
                  *, k: int = 10) -> dict:
    """Score every row, rank it, and report the agreement with the grades.

    Both orders are reported over the *same* labelled rows, so the comparison is
    like for like: the product's order, and the order the rows arrived in.
    """
    from .identity import score_job

    scored = []
    for row in rows:
        result = score_job(row, profile_data)
        scored.append({**row, **result, "key": row_key(row)})
    product_order = _order_by(scored, lambda item: (-item["score"], str(item.get("title", ""))))
    arrival_order = list(range(len(scored)))

    matched_keys = [key for key in grades if any(row["key"] == key for row in scored)]
    by_key = {row["key"]: row for row in scored}
    labelled = [key for key in matched_keys if grades[key]["grade"] in GRADES]

    if not labelled:
        return {"present": False, "reason": "no grade matched a scored row",
                "rows": len(rows), "grades_offered": len(grades), "n_graded": 0}

    grade_of = {key: GRADES[grades[key]["grade"]] for key in labelled}
    # Judged-only ordering: rows a person did not grade are removed, never assumed
    # irrelevant. nDCG and Spearman below are therefore "over judged rows only".
    product_grades = [grade_of[scored[index]["key"]] for index in product_order
                      if scored[index]["key"] in grade_of]
    arrival_grades = [grade_of[scored[index]["key"]] for index in arrival_order
                      if scored[index]["key"] in grade_of]

    product_keys = [scored[index]["key"] for index in product_order if scored[index]["key"] in grade_of]
    arrival_keys = [scored[index]["key"] for index in arrival_order if scored[index]["key"] in grade_of]

    # Slot ordering: the first k rows the app actually shows, ungraded ones included and
    # counted as a miss. This is the number a user experiences, so it is reported beside
    # the judged-only one rather than replaced by it.
    def slots(order: list[int]) -> tuple[float | None, int]:
        top = [scored[index] for index in order[:k]]
        hits = sum(1 for row in top if grade_of.get(row["key"], 0) >= 2)
        judged = sum(1 for row in top if row["key"] in grade_of)
        return (round(hits / len(top), 4) if top else None), judged

    product_slots, product_slots_judged = slots(product_order)
    arrival_slots, arrival_slots_judged = slots(arrival_order)

    pairs = [(by_key[key]["score"], grade_of[key]) for key in labelled]
    rho = spearman([pair[0] for pair in pairs], [pair[1] for pair in pairs])

    arrival_pairs = [(index, grade_of[scored[index]["key"]]) for index in arrival_order
                     if scored[index]["key"] in grade_of]
    arrival_rho = spearman([pair[0] for pair in arrival_pairs], [pair[1] for pair in arrival_pairs])

    report = {
        "present": True,
        "rows": len(scored),
        "n_graded": len(labelled),
        "ungraded_rows": len(scored) - len(labelled) - (len(grades) - len(matched_keys)),
        "grades_offered": len(grades),
        "grades_off_corpus": len(grades) - len(matched_keys),
        "k": k,
        "product": {
            "ndcg": ndcg_at_k(product_grades, product_grades, k),
            "precision": precision_at_k(product_grades, k),
            "precision_strong": precision_at_k(product_grades, k, floor=3),
            "recall": recall_at_k(product_grades, product_grades, k=25),
            "spearman": rho,
            "precision_slots": product_slots,
            "judged_in_top_k": product_slots_judged,
            "top_keys": product_keys[:k],
        },
        "baseline_arrival": {
            "ndcg": ndcg_at_k(arrival_grades, arrival_grades, k),
            "precision": precision_at_k(arrival_grades, k),
            "recall": recall_at_k(arrival_grades, arrival_grades, k=25),
            "spearman": arrival_rho,
            "precision_slots": arrival_slots,
            "judged_in_top_k": arrival_slots_judged,
        },
        "grade_counts": {name: sum(1 for key in labelled if grades[key]["grade"] == name)
                         for name in GRADES},
        "sources": {name: sum(1 for key in labelled if grades[key].get("source") == name)
                    for name in ("tracker", "human", "agent")},
        "rows_detail": [{"key": key, "title": by_key[key].get("title", ""),
                         "employer": by_key[key].get("employer", ""),
                         "score": by_key[key]["score"], "band": by_key[key]["band"],
                         "grade": grades[key]["grade"], "why": grades[key].get("why", "")}
                        for key in labelled],
    }
    return report


def evaluate_workspace(root: Path | str, labels_path: Path | str, *, k: int = 10,
                       source: str = "auto") -> dict:
    """Score the workspace's own postings (or its corpus) against a labels file."""
    from .identity import profile

    root = Path(root)
    rows: list[dict] = []
    if source in ("auto", "postings"):
        rows = posting_rows(root)
    if source in ("auto", "corpus") and not rows:
        from .corpus import load

        rows = load(root)
    data = profile(root)
    grades = load_labels(labels_path)
    report = evaluate_rows(rows, data, grades["rows"], k=k)
    report.update({"root": str(root), "labels": str(labels_path), "source": source,
                   "corpus_hash": labels_hash(rows), "labeller": grades.get("labeller", ""),
                   "graded_at": grades.get("graded_at", ""),
                   "profile_complete": data.get("complete"),
                   "labels_corpus_hash": grades.get("corpus_hash", "")})
    return report


def labels_hash(rows: list[dict]) -> str:
    import hashlib

    payload = json.dumps(sorted(row_key(row) for row in rows)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]


# --------------------------------------------------------------------------
# the labels file
# --------------------------------------------------------------------------

def load_labels(path: Path | str) -> dict:
    """Read a labels file, accepting both shapes a person actually writes.

    The full shape is `{"corpus_hash": …, "labeller": …, "rows": [{...}]}`; a bare
    `{"<key>": "strong"}` dict is also accepted, because refusing a two-line file
    would make the instrument unusable for the one thing it must never do — stop a
    human from recording a judgement.
    """
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        rows: dict[str, dict] = {}
        for entry in payload["rows"]:
            if not isinstance(entry, dict):
                continue
            key = entry.get("key") or row_key(entry)
            grade = normalise_grade(entry.get("grade"))
            if grade:
                rows[key] = {"grade": grade,
                             "source": entry.get("source_of_grade") or entry.get("source") or "human",
                             "why": entry.get("why", ""),
                             "title": entry.get("title", ""), "employer": entry.get("employer", "")}
        return {"rows": rows, "labeller": payload.get("labeller", ""),
                "graded_at": payload.get("graded_at", ""),
                "corpus_hash": payload.get("corpus_hash", "")}
    if isinstance(payload, dict):
        rows = {}
        for key, value in payload.items():
            grade = normalise_grade(value if isinstance(value, str) else None)
            if grade:
                rows[key] = {"grade": grade, "source": "human", "why": ""}
        return {"rows": rows, "labeller": "", "graded_at": "", "corpus_hash": ""}
    raise ValueError(f"{path}: a labels file is an object, not {type(payload).__name__}")


def normalise_grade(value: object) -> str:
    text = str(value or "").strip().casefold()
    if not text or text in ("null", "none", "unset", "-", "?"):
        return ""
    if text in GRADES:
        return text
    return TRACKER_GRADES.get(text, "")


def worksheet(root: Path | str, *, limit: int = 200) -> dict:
    """The labelling job, reduced to decisions: every row scored, evidence beside it.

    `grade` is null and stays null until a person writes it. The tracker's Fit is
    proposed where the match is unambiguous, marked `source: tracker` so a report can
    say how much of the set is the user's prior judgement rather than a fresh grade.
    """
    from .identity import profile, score_job

    root = Path(root)
    rows = posting_rows(root)
    if not rows:
        from .corpus import load

        rows = load(root)
    data = profile(root)
    proposed, unmatched = labels_from_tracker(root, rows)
    entries = []
    for row in rows:
        result = score_job(row, data)
        key = row_key(row)
        prior = proposed.get(key)
        entries.append({
            "key": key, "title": row.get("title", ""), "employer": row.get("employer", ""),
            "source": row.get("source", ""),
            "path": row.get("path", ""),
            "score": result["score"], "band": result["band"],
            "reasons": result["reasons"][:6], "disqualifiers": result["disqualifiers"],
            "grade": prior["grade"] if prior else None,
            "source_of_grade": prior["source"] if prior else None,
            "why": (prior or {}).get("why", ""),
        })
    entries.sort(key=lambda entry: (-entry["score"], entry["title"]))
    return {
        "corpus_hash": labels_hash(rows),
        "graded_at": "",
        "labeller": "",
        "scale": {name: value for name, value in GRADES.items()},
        "instructions": (
            "Fill `grade` for each row: strong = would apply today, possible = would apply "
            "after a small edit, unlikely = only in a drought, skip = wrong work entirely. "
            "A null is an ungraded row and is left out of every metric. Rows carrying "
            "source_of_grade=tracker were filled from your own tracker Fit column; change "
            "them if the tracker was wrong."),
        "rows": entries[:limit],
        "unmatched_tracker_rows": unmatched,
    }


# --------------------------------------------------------------------------
# the regression gate
# --------------------------------------------------------------------------

def compare_to_baseline(report: dict, baseline: dict) -> dict:
    """Fail on a real regression, and say which number moved.

    A smaller labelled set makes every metric less stable, so the check refuses to
    compare across a set that shrank by more than half: an improvement measured on
    four rows is not an improvement.
    """
    failures: list[str] = []
    product = report.get("product") or {}
    if not report.get("present"):
        return {"ok": False, "failures": [report.get("reason", "no evaluation")],
                "baseline": baseline, "current": report}
    recorded_n = int(baseline.get("n_graded") or 0)
    if recorded_n and report.get("n_graded", 0) < recorded_n / 2:
        failures.append(f"labelled set shrank: {report.get('n_graded')} rows vs {recorded_n} "
                        "recorded; a metric on a smaller set is not comparable")
    for field, slack, label in (("ndcg", NDCG_SLACK, "nDCG@k"),
                                ("spearman", SPEARMAN_SLACK, "Spearman")):
        recorded = baseline.get(field)
        current = product.get(field)
        if recorded is None or current is None:
            continue
        if current < float(recorded) - slack:
            failures.append(f"{label} dropped to {current} from {recorded} "
                            f"(allowed drift {slack})")
    return {"ok": not failures, "failures": failures, "baseline": baseline,
            "current": {"ndcg": product.get("ndcg"), "precision": product.get("precision"),
                        "spearman": product.get("spearman"),
                        "n_graded": report.get("n_graded")}}


def record_baseline(report: dict) -> dict:
    product = report.get("product") or {}
    return {"recorded_on": date.today().isoformat(), "n_graded": report.get("n_graded", 0),
            "ndcg": product.get("ndcg"), "precision": product.get("precision"),
            "recall": product.get("recall"), "spearman": product.get("spearman"),
            "corpus_hash": report.get("corpus_hash", ""),
            "labels_corpus_hash": report.get("labels_corpus_hash", ""),
            "note": "Recorded by `dossier identity eval --write-baseline`. A drop past "
                    "the slack in evaluation.NDCG_SLACK / SPEARMAN_SLACK fails the gate."}


__all__ = ["GRADES", "TRACKER_GRADES", "compare_to_baseline", "dcg", "evaluate_rows",
           "evaluate_workspace", "labels_from_tracker", "labels_hash", "load_labels",
           "ndcg_at_k", "normalise_grade", "posting_rows", "precision_at_k",
           "recall_at_k", "record_baseline", "row_key", "spearman", "tracker_rows",
           "worksheet"]
