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

## Log ordering check (analysis Q1) / 2026-08-20 / 5:50 pm

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
(Resolved — line 311 is malformed JSON, confirmed in q1_malformed_access.txt.)

## Retry misclassification check (analysis Q2) / 2026-08-21 / 12:10 pm

- Symptom: Q2 requires proving requests weren't double-counted due to retries. Needed to check whether any request_id appears more than once with differing field values (not just exact-duplicate lines already found in Q1).
- Hypothesis: If a request_id appears more than once with different content, it represents an upstream retry — the same client request attempted more than once.
- Command or test: Grouped all lines by request_id; for each request_id appearing more than once, compared the set of unique line values. Ran against application.log (script: q2 retry-check, see log_analysis.md Q2 commands).
- Actual output: 47 request_ids appeared with differing content. Every one of the 47 groups contained exactly two lines: one `"event": "dependency_error"` line and one `"event": "http_request"` line, both sharing the same request_id and near-identical timestamps (~1ms apart).
- Failed attempt and what changed your thinking: Initially treated all 47 as evidence of 47 retried requests. Inspecting the actual printed line pairs showed each group was one error-detail line plus one response-summary line for a single request, not two separate `http_request` attempts — the app logs an extra diagnostic line whenever a dependency call fails, but only sends one HTTP response per request. This meant "differing content under the same request_id" does not by itself imply a retry.
- Root cause: application.log records two log lines per failed request (dependency_error + http_request) by design, not two client attempts. No genuine retries (two `http_request` entries for the same request_id) exist in either access.log or application.log.
- Fix: N/A — not a bug. Documented the correct dedup rule: count only `event: "http_request"` lines when counting distinct requests in application.log; a request_id repeated with an accompanying dependency_error line is still one request.
- Retest evidence: `analysis/q2_retry_check_application.txt` (all 47 groups reviewed), `analysis/q2_distinct_counts.txt` (682 distinct requests via http_request count).
- Related commit: Pending
- Remaining uncertainty: Logs show no retries in this window; doesn't prove no retry mechanism exists in app/NGINX config.
