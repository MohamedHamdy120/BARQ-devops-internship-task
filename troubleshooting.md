# Troubleshooting journal

Keep chronological entries. Copy this block for each meaningful investigation.

## Entry / date / time
- Symptom:
- Hypothesis:
- Command or test:
- Actual output:
- Failed attempt and what changed your thinking:
- Root cause:
- Fix:
- Retest evidence:
- Related commit:
- Remaining uncertainty:

Do not fabricate a failed attempt just to fill the template. Record actual attempts.

## 2026-08-20 — Log ordering check (before Q1)

- Symptom: Needed first/last timestamps per log to answer Q1 interval.
- Hypothesis: Files are sorted by timestamp, so `head`/`tail` are sufficient.
- Command or test: `sort -c logs/access.log` (same for application.log and error.log).
- Actual output: access.log disorder at line 311; application.log disorder at line 402; error.log passed.
- Failed attempt and what changed your thinking: Initial `head`/`tail` gave plausible min/max by luck. `sort -c` proved the files are not ordered, so `head`/`tail` cannot be trusted for min/max. Switched to `grep -o '"timestamp"...' | sort | head/tail`.
- Root cause: Log files are not sorted by timestamp. A format variant exists at access.log:311 (timestamp without milliseconds).
- Fix: Compute min/max by extracting timestamps and sorting.
- Retest evidence: `analysis/q1_interval.txt` shows consistent min/max across access.log and application.log (11:00:00.015Z → 11:29:57.578Z).
- Related commit: 97fac56 — "log_analysis: Q1 interval; troubleshooting: log ordering check"
- Remaining uncertainty: Whether access.log:311 is malformed or a valid variant — to be decided in Q1 sub-task 2.