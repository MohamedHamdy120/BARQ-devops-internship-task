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
UTC interval:
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
Malformed lines (per file):
```bash
python3 - <<'EOF' | tee analysis/q1_malformed_access.txt
import json
bad=[]
with open('logs/access.log') as f:
    for i,l in enumerate(f,1):
        try:
            o=json.loads(l)
            for k in ('timestamp','request_id','method','path','status','upstream'):
                if k not in o: bad.append((i,'missing '+k,l.rstrip())); break
        except Exception as e: bad.append((i,str(e),l.rstrip()))
print('malformed:',len(bad))
for b in bad: print(b)
EOF
```
(same pattern for `application.log`)

Malformed lines for error.log file:
```
python3 - <<'EOF' | tee analysis/q1_malformed_error.txt
import re
pat = re.compile(r'^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \[(error|warn|crit|notice|alert|emerg|info|debug)\] ')
bad=[]
with open('logs/error.log') as f:
    for i,l in enumerate(f,1):
        if not pat.match(l): bad.append((i,l.rstrip()))
print('malformed:',len(bad))
for b in bad: print(b)
EOF
```
Duplicate lines:
```bash
for f in logs/access.log logs/application.log logs/error.log; do
  t=$(wc -l < "$f"); u=$(sort "$f" | uniq -u | wc -l)
  echo "$f total=$t duplicates=$((t-u))"
done | tee analysis/q1_duplicate_lines.txt
```

Valid = Total − Malformed − Excess duplicates (derived; see table below).


## Results
### Q1 — Interval, valid/malformed/duplicate lines

**Interval (UTC):**

| File | First | Last | Span |
|---|---|---|---|
| access.log | 2026-08-20T11:00:00.015Z | 2026-08-20T11:29:57.578Z | 29m57s |
| application.log | 2026-08-20T11:00:00.015Z | 2026-08-20T11:29:57.578Z | 29m57s |
| error.log | 2026/08/20 11:05:02 | 2026/08/20 11:30:00 | 24m58s |

**Line counts:**

| File | Total | Valid | Malformed | Duplicate (distinct) | Excess |
|---|---|---|---|---|---|
| access.log | 726 | 715 | 1 | 5 | 5 |
| application.log | 730 | 725 | 1 | 2 | 2 |
| error.log | 68 | 68 | 0 | 0 | 0 |

Valid (unique) = well-formed, appears once; Malformed = parse/field failure; Duplicate (distinct) = distinct repeated lines; Excess = extra copies. Identity: Valid + Malformed + Duplicate + Excess = Total.

Evidence: `analysis/q1_interval.txt`, `analysis/q1_malformed_*.txt`, `analysis/q1_duplicate_lines*.txt`.

Notes: logs not sorted; error.log ends with a `[notice]`, not an error.
## Timeline and correlated examples
## Conclusions and limits
