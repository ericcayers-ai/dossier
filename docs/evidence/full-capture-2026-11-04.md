# Full board capture — first real attempt, 2026-11-04

Against a scratch copy of the real workspace's identity documents
(`DEVELOPER-IDENTITY.md`, `resume.md`, `job-history.md`), so the owner's folder was not
written to. Every number below is from a command that ran; the workspace path was
`%TEMP%\dossier-full-capture-fopyqdlz`.

## 1. Identity from the documents (no answers yet)

```text
dossier identity status --root <ws>
identity: 5/15 question(s) answered, 11 value(s) mined from documents
  name Eric · email/phone · location Waikato · timezone Pacific/Auckland
  seniority student/intern · availability summer internship · languages English, Japanese, Māori
  skills (12 from the resume) · applied_roles (15 from job-history.md)
  missing required: employment, right_to_work
```

Two required answers cannot be mined honestly: employment type and right-to-work status.
They are asked, not guessed. `target_roles` was derived from `applied_roles`, which is
**history, not intent** — and that distinction turned out to matter (§4).

## 2. Feeds fetched (6 of 9; three need a company slug)

```text
remoteok        99 rows    complete
remotive        10 rows    complete
jobicy         100 rows    complete
himalayas       20 rows    complete
arbeitnow      300 rows    complete
weworkremotely  25 rows    complete
corpus build → 554 rows, 554 distinct ids, 0 duplicates, 6 sources
```

`greenhouse`, `lever` and `ashby` are board-scoped (`--board <slug>`) by design: there is
no "all of Greenhouse" endpoint, so those three need the employer's slug.

## 3. Scoring with the mined profile

```text
scored 554 of 554: strong 0, possible 12, unlikely 542
  possible 49  IT Analyst                          Horizon3Ai              arbeitnow
  possible 49  Marketing Student Assistant         Copenhagen Optimization remoteok
  possible 45  Art Development Intern              Catawiki                jobicy
  possible 45  Customer Care Representative        Pamono GmbH             arbeitnow
  possible 45  Kernel Build Automation Engineer    Canonical               jobicy
DISQUAL  AI Engineer / AI ML Engineer / Account Manager … "role reads senior and you are
         targeting student/intern"
```

The disqualifiers are correct (5+ years or a lead-level title against a student target).
The `possible` rows are *faithful to what was mined*: the tracker shows customer-service and
compliance applications, so customer-support titles score. That is the honest answer to
"what does my history say", and a poor answer to "what do I want".

## 4. Calibration check — answering the questionnaire (a COPY, placeholder answers)

Labelled a check, not the owner's identity: `target_roles` "Software Engineer Intern, Data
Analyst Intern, IT Support", internship/part-time, Hamilton, remote yes, must-have Python.
The copy was deleted afterwards.

```text
before answers:  possible 12,  top score 49
after  answers:  possible 39,  top score 64
  possible 64  Data Associate - Internship (6 months, flexi)   Alan
  possible 64  Graduate / Junior Data Scientist                Thgingenuity
  possible 64  Process Automation Engineer - Internship        Enpal
  possible 63  Kernel Build Automation Engineer - Ubuntu       Canonical
  possible 63  Software Engineer II - Embedded Platform        Hudl
```

So the questionnaire is not decoration: it changes the shortlist from support/retail to
data/engineering internships, and moves 12 → 39 usable candidates.

## 5. Relevance-filtered captures (live pages)

```text
scrape capture <arbeitnow IT Analyst URL> --min-match 45
  complete=True filtered=False match=possible 49 posting=job-posting-web-it-analyst-horizon3ai-…
scrape capture <remoteok Marketing Student Assistant URL> --min-match 45
  complete=True filtered=False match=possible 49 posting=job-posting-remoteok-remote-marketing-…
```

obscura fetched both; both cleared the floor and were archived with `match: possible 49` in
the frontmatter. A page under the floor is refused *and recorded* (`filtered: true`,
`complete: false`, `reason: relevance N is below the floor M`), verified by
`test_a_capture_can_refuse_an_irrelevant_page_and_says_it_did`.

## 6. Blocked boards, as they actually behaved

```text
https://www.seek.co.nz/job/1
  exit 2  SourceRefused: seek is not permitted for automated access (manual_only)
https://nz.indeed.com/viewjob?jk=…
  exit 2  SourceRefused: indeed is not permitted for automated access (manual_only)
```

Not a challenge, not a timeout: the workspace policy refuses them before a socket opens.
`dossier sources --open seek` is the recorded way to change that (and then the challenge
policy applies to whatever the site answers).

## 7. What this proves, and what it does not

Proved: the pipeline runs end to end on live data — mine → ask → score → filter → archive,
with the numbers above.

Not proved: that these 554 rows are the *right* market. Six global-remote feeds are not a NZ
graduate market; seek/trade-me/linkedin are where the local internships are, and they are
policy-gated behind a session or opened explicitly. The honest next step is the owner's:
answer `employment`, `right_to_work`, and set `target_roles` as an intent (not the mined
history), then open the boards they are entitled to and re-run.
