# Log analysis

Use all three supplied logs. Answer every question with commands/scripts and actual output.

1. What UTC interval is covered? How many valid, malformed and duplicate lines are in each file?
2. How many distinct client requests occurred? How did you deduplicate and avoid counting retries twice?
3. What are the final client status counts and error rate? State your denominator.
4. Which paths, time windows and backends account for the failures?
5. What are the median and p95 client latencies? State the percentile method and units.
6. Which requests retried upstream? How many succeeded after retrying?
7. Build an incident timeline using evidence from access, error AND application logs.
8. Show one correlated failed request and one successful request. Include IDs and timestamps.
9. Which errors appear to be proxy/connectivity issues versus dependency/application issues? What proves it?
10. What do the logs not prove? What would you check next in a running environment?

## Commands / scripts
### Q1 commands

```bash
{
  echo "=== access.log ==="
  grep -o '"timestamp":"[^"]*"' logs/access.log | sort | head -1
  grep -o '"timestamp":"[^"]*"' logs/access.log | sort | tail -1
  echo "=== application.log ==="
  grep -o '"timestamp": "[^"]*"' logs/application.log | sort | head -1
  grep -o '"timestamp": "[^"]*"' logs/application.log | sort | tail -1
  echo "=== error.log ==="
  head -1 logs/error.log
  tail -1 logs/error.log
} | tee analysis/q1_interval.txt
```


## Results
### Q1 — Interval, valid/malformed/duplicate lines

**Interval (UTC):**

| File | First | Last | Span |
|---|---|---|---|
| access.log | 2026-08-20T11:00:00.015Z | 2026-08-20T11:29:57.578Z | 29m57s |
| application.log | 2026-08-20T11:00:00.015Z | 2026-08-20T11:29:57.578Z | 29m57s |
| error.log | 2026/08/20 11:05:02 | 2026/08/20 11:30:00 | 24m58s |

Notes:
- Files are not sorted. `sort -c` showed disorder at access.log:311 and application.log:402. Min/max computed via `grep -o` + `sort`, not `head`/`tail`.
- error.log's last line is `[notice] log collector rotated stream`, not an error.
- Raw evidence: `analysis/q1_interval.txt`.
## Timeline and correlated examples
## Conclusions and limits
