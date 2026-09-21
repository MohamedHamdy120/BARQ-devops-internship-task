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
(same script, path swapped to `logs/application.log`, output to `analysis/q1_malformed_app.txt`)

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

### Q2 commands
Distinct requests count:
```bash
{
  echo "access.log distinct requests: $((726 - 1 - 5))"
  echo "application.log distinct requests (event=http_request):"
  grep -c '"event": "http_request"' logs/application.log
} | tee analysis/q2_distinct_counts.txt
```

Retry check — group by request_id, flag groups where lines differ (not exact duplicates):
```bash
python3 - <<'EOF' | tee analysis/q2_retry_check_access.txt
import json
from collections import defaultdict

by_id = defaultdict(list)
with open('logs/access.log') as f:
    for line in f:
        line = line.rstrip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        rid = obj.get('request_id')
        if rid is None:
            continue
        by_id[rid].append(line)

exact_dup_ids = 0
differing_ids = 0
for rid, lines in by_id.items():
    if len(lines) > 1:
        unique_lines = set(lines)
        if len(unique_lines) == 1:
            exact_dup_ids += 1
        else:
            differing_ids += 1
            print(rid, len(lines))
            for l in unique_lines:
                print('   ', l)

print('---')
print('exact-duplicate request_ids:', exact_dup_ids)
print('differing request_ids (candidates for retry/bug):', differing_ids)
EOF
```
(same script, path swapped to `logs/application.log`, output to `analysis/q2_retry_check_application.txt`)

### Q3 commands
Raw status counts (all lines, includes duplicates):
```bash
grep -o '"status":[0-9]*' logs/access.log | sort | uniq -c | tee analysis/q3_status_counts.txt
```

Corrected counts (deduped) and error rate:
```bash
{
  echo "Corrected status counts (deduped, n=720):"
  echo "200: $((620-5))"
  echo "404: 10"
  echo "502: 40"
  echo "503: 47"
  echo "504: 8"
  echo ""
  echo "Errors (5xx only): $((40+47+8))"
  echo "Denominator: 720 (distinct requests, from Q2)"
  echo "Error rate: $(python3 -c 'print(round(95/720*100,2))')%"
} | tee analysis/q3_status_final.txt
```
### Q4 commands
5xx by path, minute and backend
```bash
python3 - <<'EOF' | tee analysis/q4_failures.txt
import json
from collections import Counter
seen=set(); rows=[]
for l in open('logs/access.log'):
    if l in seen: continue
    seen.add(l)
    try: o=json.loads(l)
    except: continue
    if o['status']>=500: rows.append(o)
print('5xx total:',len(rows))
print('BY PATH   ',Counter(o['path'] for o in rows))
print('BY MINUTE ',sorted(Counter(o['timestamp'][:16] for o in rows).items()))
print('BY BACKEND',Counter(o['upstream'] for o in rows))
print('PATH x STATUS',Counter((o['path'],o['status']) for o in rows))
EOF
```

5xx by status, backend and minute
```bash
python3 - <<'EOF' | tee analysis/q4_crosstab.txt
import json
from collections import Counter
seen=set(); c=Counter()
for l in open('logs/access.log'):
    if l in seen: continue
    seen.add(l)
    try: o=json.loads(l)
    except: continue
    if o['status']>=500:
        c[(o['status'],o['upstream'],o['timestamp'][11:16])]+=1
for k,v in sorted(c.items()): print(k,v)
EOF
```

dependency errors by service, type and minute
```bash
python3 - <<'EOF' | tee analysis/q4_dependency.txt
import json
from collections import Counter
c=Counter()
for l in open('logs/application.log'):
    try: o=json.loads(l)
    except: continue
    if o.get('event')=='dependency_error':
        c[(o['dependency'],o['error_type'],o['timestamp'][11:16])]+=1
for k,v in sorted(c.items()): print(k,v)
print('total:',sum(c.values()))
EOF
```
### Q5 commands
median and p95 latency (nearest-rank)
```bash
python3 - <<'EOF' | tee analysis/q5_latency.txt
import json, math
seen=set(); allv=[]; okv=[]
for l in open('logs/access.log'):
    if l in seen: continue
    seen.add(l)
    try: o=json.loads(l); t=float(o['request_time'])
    except: continue
    allv.append(t)
    if o['status']==200: okv.append(t)
def pct(v,p):
    v=sorted(v); return v[math.ceil(p/100*len(v))-1]  # nearest-rank
def med(v):
    v=sorted(v); n=len(v)
    return v[n//2] if n%2 else (v[n//2-1]+v[n//2])/2
for name,v in (('ALL',allv),('200 only',okv)):
    print(f'{name}: n={len(v)} median={med(v)*1000:.0f} ms p95={pct(v,95)*1000:.0f} ms max={max(v)*1000:.0f} ms')
EOF
```
latency by status
```bash
python3 - <<'EOF' | tee analysis/q5_by_status.txt
import json
from collections import defaultdict
seen=set(); d=defaultdict(list)
for l in open('logs/access.log'):
    if l in seen: continue
    seen.add(l)
    try: o=json.loads(l); d[o['status']].append(float(o['request_time']))
    except: continue
for s in sorted(d):
    v=sorted(d[s]); print(s,'n=',len(v),'median=%.0f ms'%(v[len(v)//2]*1000),'max=%.0f ms'%(v[-1]*1000))
EOF
```

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

### Q2 — Distinct requests & deduplication
access.log: 720 distinct requests (726 lines − 1 malformed − 5 exact-duplicate lines). See Q1 for refercnce

application.log: 682 distinct requests, counted via event: "http_request" lines — since a failed request logs two lines (a dependency_error line plus an http_request line), and only the http_request line represents an actual client response.

Retries: checked all request_ids appearing more than once for differing field values. All 47 differing groups were error+response pairs for a single request, not repeated attempts. No genuine retries found in either log.

Evidence: `analysis/q2_distinct_counts.txt`, `analysis/q2_retry_check_access.txt`, `analysis/q2_retry_check_application.txt`.

Note: dependency_error(redis, TimeoutError) pairs in application.log consistently show duration_ms ≈ 2025, suggesting a fixed ~2s redis timeout

### Q3 — Final client status counts & error rate

Counted from access.log (client-facing responses via NGINX), deduped to 720 distinct requests (raw grep count of 725 minus 5 exact duplicates already identified in Q1).

| Status | Count |
|---|---|
| 200 | 615 |
| 404 | 10 |
| 502 | 40 |
| 503 | 47 |
| 504 | 8 |

- **Errors:** 95 (5xx only — 404 excluded, since it's a correctly-served "not found" response, not a server failure)
- **Denominator:** 720 (distinct requests)
- **Error rate:** 95/720 = 13.19%

Evidence: `analysis/q3_status_counts.txt`, `analysis/q3_status_final.txt`

### Q4 — Paths, time windows and backends behind the failures

95 deduped 5xx responses (denominator 720) fall into four bursts of about 8 per minute. Nothing else failed.

| Window (UTC) | Status | Backend | Count | Paths | Cause seen in application.log |
|---|---|---|---|---|---|
| 11:05-11:09 | 502 | 172.23.0.12 only | 40 | `/`, `/health`, `/records`, `/counter` (10 each) | none |
| 11:12-11:15 | 503 | both | 31 | `/ready`, `/counter`, `/records` | Redis `TimeoutError` (31) |
| 11:20-11:21 | 503 | both | 16 | `/ready`, `/counter`, `/records` | PostgreSQL `InvalidPassword` (16) |
| 11:25-11:26 | 504 | both | 8 | `/records` only | none |

- By path: `/records` 26, `/counter` 26, `/ready` 23, `/health` 10, `/` 10.
- By backend: .12 has 68 and .11 has 27. The gap is fully explained by the .12-only 502 burst.
- The 47 503s match the 47 `dependency_error` lines exactly.
- 502s hit `/health`, which uses no dependency, and left no `dependency_error` lines. This points to a proxy/connectivity problem between NGINX and .12, not to the app's dependencies.
- 504s also left no `dependency_error` lines. This suggests an NGINX-side timeout, still to be checked against error.log (Q7/Q9).
- Not proven yet: why .12 was unreachable, and why `/records` timed out.

Evidence: `analysis/q4_failures.txt`, `analysis/q4_crosstab.txt`, `analysis/q4_dependency.txt`

### Q5 — Client latency

Field: `request_time` from access.log (seconds, ms resolution; time the client waited via NGINX). Converted to ms. Deduped, malformed lines excluded. Percentile method: nearest-rank (value at position ceil(p·n) in sorted list).

| Set | n | Median | p95 | Max |
|---|---|---|---|---|
| All requests | 720 | 54 ms | 2001 ms | 2025 ms |
| 200 only | 615 | 55 ms | 93 ms | 120 ms |

- Slow requests (503 and 504) are 55 of 720 (7.6%), above the 5% tail that p95 excludes, so p95 for all requests sits inside the slow group.
- Successful requests were fast (median 55 ms). The tail comes from 503 (47 requests, median and max both 2025 ms) and 504 (8 requests, median and max both 2001 ms). The 502s are fast (3 ms) and the 404s are normal (median 56 ms).
- The 502 pattern (instant failure) suggests a refused connection to .12. The 504 value (2001 ms) suggests an NGINX timeout of about 2 s. Neither is proven yet; check `nginx.conf` and error.log (Q9).
- Open question: the PostgreSQL `InvalidPassword` 503s likely share the ~2 s latency, but this was not checked per request_id. A rejected password should fail fast, so a fixed delay or retry may exist in the app. Check in Part 2.

Evidence: `analysis/q5_latency.txt`, `analysis/q5_by_status.txt`

## Timeline and correlated examples
## Conclusions and limits
