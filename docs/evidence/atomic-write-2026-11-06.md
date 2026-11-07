# `atomic_write` failed under concurrency on Windows

2026-11-06. Found by the full gate run for the reel-digest pass, not by reading
code: `pytest` came back **433 passed, 1 failed**.

```
FAILED tests/test_e2e_ui.py::test_a_user_builds_their_identity_and_sees_matching_jobs
E   AssertionError: Locator expected to contain text 'Wrote'
E   - heading "The Dossier API failed (500). Internal Server Error" [level=2]
PermissionError: [WinError 32] The process cannot access the file because it is
  being used by another process:
  '...\dossier-e2e-lo0i34ri\IDENTITY.md.tmp' -> '...\IDENTITY.md'
```

The test had passed five minutes earlier, and passed **5/5** in isolation. So this
is not a test bug and not deterministic: it is a race in `src/dossier/safety.py`,
the single function every write in the program goes through.

## Three defects in one function

`atomic_write` (before):

```python
tmp=path.with_suffix(path.suffix+'.tmp')          # (1)
try:
    with open(tmp,'wb') as f: ... ; os.fsync(f.fileno())
    if current != observed: raise Conflict(...)
    os.replace(tmp,path); return stamp(path)      # (2)
finally:
    if tmp.exists(): tmp.unlink()                 # (3)
```

1. **One fixed temp name per destination.** Two writers of `IDENTITY.md` — an API
   retry and a second tab, or the UI and the agent — both opened `IDENTITY.md.tmp`.
   One renamed it while the other still held it, and the loser's `finally` deleted
   a file the winner had just written.
2. **One attempt at `os.replace`, and the failure was not retried.** On Windows
   that call needs DELETE access on the destination, and CPython opens files
   *without* `FILE_SHARE_DELETE`. **Any** concurrent reader of the target blocks
   the rename with WinError 32 for as long as it holds the handle. This is not a
   slow-disk problem that a retry alone fixes: two writers in the same process
   starve each other no matter how long either one waits.
3. **Cleanup could raise, and did.** The `finally` unlinked a path that was still
   open, raising a second WinError 32 that replaced the first in the traceback.

## Fix

- **A mutex per destination path**, process-wide (`_write_lock`), wrapping the whole
  observe → write → rename sequence. This is what actually removes the failure:
  one process, one writer per file at a time. A different process is still handled
  by (2).
- **A unique temp file per call** (`tempfile.mkstemp(dir=..., prefix='.<name>.', suffix='.tmp')`),
  in the same directory so `os.replace` stays a same-volume atomic rename.
- **A bounded rename retry**: 6 attempts, 10 → 200 ms, re-reading the CAS stamp
  between attempts so a destination that genuinely changed still raises `Conflict`
  (a 409) immediately rather than being overwritten after a wait. An unreadable
  destination during the wait is treated as "unknown", not as a conflict.
- **Cleanup that cannot raise**: 50 × 10 ms on `PermissionError`, `FileNotFoundError`
  exits quietly. The temp file's only job is to never be the target.

Semantics are unchanged where they were deliberate: losing the compare-and-swap is
still `Conflict`, which the API still maps to 409. Concurrent writers of one file
are *supposed* to lose that race sometimes; they are not supposed to get a 500.

## Before / after

Contention harness (`%TEMP%\...\hammer_off.py`), 8 threads × 10 writes to one path:
`--no-lock` disables only the mutex, leaving the unique temp name and the retry in
place, so what still fails is failure the mutex owns.

| run | errors of 80 writes |
|---|---|
| no lock, run 1 | 13 × `PermissionError`, 55 × `Conflict` |
| no lock, run 2 | 13 × `PermissionError`, 56 × `Conflict` |
| **with lock, run 3** | **0** (0 conflicts) |
| with lock, repeats | 0, 0, 0 |

Live product path (`hammer.py`): 8 clients × 5 concurrent `PUT /api/file` on
`IDENTITY.md` against the running server — **40 writes, 40 × 200, 0 × 500,
0 × 409**. That is the request that answered 500 in the failing run.

Suite: **434 → 437 passed** (60 s).

## The three tests that hold this

Added to `tests/test_safety.py` (8 tests in the file, all pass):

- `test_a_locked_destination_is_retried_instead_of_failing_the_write` — monkeypatches
  `os.replace` to raise WinError 32 twice, asserts the write succeeds on the third
  attempt and returns a stamp that matches the file.
- `test_a_destination_that_never_unlocks_still_raises_and_leaves_no_temp_file` —
  asserts the caller sees `PermissionError`, the destination still holds its old
  bytes, and no `.tmp` survives in the directory.
- `test_two_writers_on_one_path_never_share_a_temp_file` — 8 threads × 10 writes,
  forbids any `OSError`, requires the destination to equal one whole payload (never
  torn), requires an empty directory apart from the file, and allows `Conflict`
  only as the sanctioned CAS loss.

## Reproduce

```powershell
.venv\Scripts\python.exe -m pytest -o addopts="" -q tests/test_safety.py        # 7 passed
.venv\Scripts\python.exe %TEMP%\..\hammer_off.py --no-lock                      # 13/80 PermissionError
.venv\Scripts\python.exe %TEMP%\..\hammer_off.py                                # 0/80
.venv\Scripts\python.exe -m pytest -o addopts="" -q                             # 437 passed
```
