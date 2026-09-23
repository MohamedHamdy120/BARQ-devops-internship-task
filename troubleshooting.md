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

## Log ordering check (analysis Q1) / 2026-09-20 / 5:50 pm

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

## Retry misclassification check (analysis Q2) / 2026-09-21 / 12:10 pm

- Symptom: Q2 requires proving requests weren't double-counted due to retries. Needed to check whether any request_id appears more than once with differing field values (not just exact-duplicate lines already found in Q1).
- Hypothesis: If a request_id appears more than once with different content, it represents an upstream retry — the same client request attempted more than once.
- Command or test: Grouped all lines by request_id; for each request_id appearing more than once, compared the set of unique line values. Ran against application.log (script: q2 retry-check, see log_analysis.md Q2 commands).
- Actual output: 47 request_ids appeared with differing content. Every one of the 47 groups contained exactly two lines: one `"event": "dependency_error"` line and one `"event": "http_request"` line, both sharing the same request_id and near-identical timestamps (~1ms apart).
- Failed attempt and what changed your thinking: Initially treated all 47 as evidence of 47 retried requests. Inspecting the actual printed line pairs showed each group was one error-detail line plus one response-summary line for a single request, not two separate `http_request` attempts — the app logs an extra diagnostic line whenever a dependency call fails, but only sends one HTTP response per request. This meant "differing content under the same request_id" does not by itself imply a retry.
- Root cause: application.log records two lines per failed request (dependency_error + http_request) by design, not two client attempts. No request_id appears twice as an `http_request`, so no line is double-counted. (NGINX upstream retries are a separate thing, see Q6.)
- Fix: N/A — not a bug. Documented the correct dedup rule: count only `event: "http_request"` lines when counting distinct requests in application.log; a request_id repeated with an accompanying dependency_error line is still one request.
- Retest evidence: `analysis/q2_retry_check_application.txt` (all 47 groups reviewed), `analysis/q2_distinct_counts.txt` (682 distinct requests via http_request count).
- Related commit: 18edb87 - "log_analysis: Q2 distinct requests & retry check; troubleshooting: retry misclassification entry"
- Remaining uncertainty: Corrected in Q6: 19 upstream retries exist in access.log (multi-address `upstream` field), all ending in 200. My Q2 check only looked for repeated log lines, so it missed them.


## Status count deduplication (analysis Q3) / 2026-09-21 / 4:30 pm

- Symptom: Raw status counts from access.log summed to 725, not the 720 denominator from Q2.
- Hypothesis: `uniq -c` would auto-dedupe by request, so no adjustment needed.
- Command: `grep -o '"status":[0-9]*' logs/access.log | sort | uniq -c`
- Actual output: 725 total (620 of them status 200).
- Failed attempt: `uniq -c` only collapses identical strings, not requests — it double-counted the 5 known duplicate lines (all status 200) from Q1.
- Root cause: Dedup must happen at request_id level, not on extracted field values.
- Fix: Subtracted 5 from the (200 status code) count (620→615). Total now 720, matches Q2.
- Retest evidence: `q3_status_counts.txt` (725), `q3_status_final.txt` (720).
- Related commit: 7aee16c - "log_analysis: Q3 status counts and error rate"
- Remaining uncertainty: none

## Failure attribution (analysis Q4) / 2026-09-21 / 5:30 pm

- Symptom: 95 5xx responses; needed to know which paths, time windows and backends account for them.
- Hypothesis: the 502's come from both backends (shared cause such as NGINX or the network).
- Command or test: grouped deduped 5xx by path, minute, status and upstream (`analysis/q4_failures.txt`, `analysis/q4_crosstab.txt`); then counted `dependency_error` lines by dependency and minute (`analysis/q4_dependency.txt`).
- Actual output: all 40 502s came from 172.23.0.12 in 11:05-11:09. The 503s hit both backends at 11:12-15 and 11:20-21, and the 504s hit both at 11:25-26. The application log has 47 dependency errors: Redis TimeoutError (31) at 11:12-15 and PostgreSQL InvalidPassword (16) at 11:20-21.
- Failed attempt and what changed your thinking: I predicted 502s on both backends. The crosstab showed .12 only; the per-backend totals (68 vs 27) had hidden this by mixing statuses. Three sample lines from application.log showed only Redis errors, so I counted all of them, which revealed a second cause (PostgreSQL InvalidPassword).
- Root cause: not proven for 502 and 504. 503 causes are proven from the application log: Redis timeouts, then a PostgreSQL password rejection.
- Fix: InvalidPassword suggests a credential or config mismatch, which I will check in Part 2.
- Retest evidence: `analysis/q4_dependency.txt` total (47) equals the 503 count (47).
- Related commit: f237245 - "log_analysis: Q4 failures; troubleshooting: attribution entry"
- Remaining uncertainty: what error.log says about the 502 burst on .12 and the 504s

## Part 2 initial investigation — compose/nginx port and healthcheck mismatches / 2026-09-22 / 1:10 pm

- Symptom: `docker compose ps -a` showed app-01 and app-02 as "Up (unhealthy)"; nginx port mapping looked unusual (`127.0.0.1:8080->81/tcp`).
- Hypothesis: healthcheck was hitting the wrong path, and/or the app process itself was crashing.
- Command or test: `docker compose logs app-01`, `docker compose logs nginx`, `cat nginx/nginx.conf`, `grep -n -i "healthz\|healthcheck" Dockerfile docker-compose.yml`, `grep -n "8080\|ports:" docker-compose.yml`.
- Actual output: app-01 logs showed the app responding normally, but every health probe was `GET /healthz` returning 404. docker-compose.yml line 12 hardcodes the healthcheck URL as `http://127.0.0.1:8080/healthz`. nginx.conf has `listen 80;` only, but docker-compose.yml line 63 maps `127.0.0.1:${PUBLIC_PORT:-8080}:81` — host 8080 to container port 81, which nothing listens on. Also found lines 26 and 41 publish PostgreSQL (`15432:5432`) and Redis (`16379:6379`) to the host, which the brief prohibits.
- Failed attempt and what changed your thinking: initially suspected the app process itself was unhealthy (crashing or not starting). Logs showed the opposite — the app was up and responding correctly; the healthcheck was simply asking for a path (`/healthz`) that doesn't exist. Required endpoint per the brief is `/health`.
- Root cause: three independent config bugs, not one — (1) healthcheck path typo, (2) nginx.conf/docker-compose.yml port disagreement (80 vs 81), (3) PostgreSQL and Redis ports published to host against the brief's requirement.
- Fix: not yet applied — investigation only. To be fixed and committed one issue at a time.
- Retest evidence: pending, will confirm after each fix (healthy status, working curl on 8080, no PostgreSQL/Redis ports reachable from host).
- Related commit: none (investigation only)
- Remaining uncertainty: whether nginx.conf should change to `listen 81;` or docker-compose.yml should map to `:80`; whether other healthcheck/port issues exist further down the file (not yet fully reviewed).

## Healthcheck path fix (Part 2) / 2026-09-22 / 2:00 pm 

- Symptom: app-01, app-02 stuck "Up (unhealthy)".
- Hypothesis: healthcheck hitting wrong path.
- Command or test: `sed -n '9,13p' docker-compose.yml`
- Actual output: healthcheck used `/healthz`; app has no such route (confirmed 404 in app-01 logs, see prior entry).
- Root cause: hardcoded wrong path in docker-compose.yml line 12.
- Fix: `sed -i "s|/healthz|/health|" docker-compose.yml`
- Retest evidence: `docker compose ps -a` — both app-01, app-02 now "healthy".
- Related commit: 91a1f5d - "fix: healthcheck path /healthz -> /health (app-01, app-02 now healthy)"
- Remaining uncertainty: none for this issue.

## NGINX host port mismatch (Part 2) / 2026-09-22 / 2:35 pm

- Symptom: `curl http://127.0.0.1:8080/` failed to connect; `docker compose ps -a` showed nginx port mapping as `127.0.0.1:8080->81/tcp`.
- Hypothesis: docker-compose.yml and nginx.conf disagree on which container port nginx listens on.
- Command or test: `grep -n "listen" nginx/nginx.conf` vs `sed -n '60,65p' docker-compose.yml`.
- Actual output: nginx.conf has `listen 80;`; docker-compose.yml mapped host 8080 to container port `81`, which nothing listens on.
- Failed attempt and what changed your thinking: none — first check confirmed the mismatch directly.
- Root cause: docker-compose.yml line 63 mapped `:81` instead of `:80`.
- Fix: `sed -i 's|:${PUBLIC_PORT:-8080}:81|:${PUBLIC_PORT:-8080}:80|' docker-compose.yml`
- Retest evidence: `docker compose ps -a` showed `127.0.0.1:8080->80/tcp`; curl still returned 502 (next issue), but port now connects instead of refusing.
- Related commit: b34e935 - "fix: nginx port 81->80, app-01 nginx upstream port 8081->8080, APP_HOST 127.0.0.1->0.0.0.0"
- Remaining uncertainty: none for this issue.

## NGINX upstream port to app-01 (Part 2) / 2026-09-22 / 3:00 pm

- Symptom: after fixing the host port, `curl http://127.0.0.1:8080/` returned 502 Bad Gateway.
- Hypothesis: nginx's upstream config points to a wrong app port.
- Command or test: `cat nginx/nginx.conf`; checked `upstream application_pool` block.
- Actual output: `server app-01:8081` — app-01 actually listens on 8080 (confirmed via `docker compose ps -a` and `APP_PORT: "8080"`).
- Failed attempt and what changed your thinking: first `sed` edit appeared to apply, but `docker compose exec nginx cat /etc/nginx/nginx.conf` still showed the old `8081`, even though the file on disk (bind-mounted read-only) was correct. `up -d nginx` alone didn't reload it; `up -d --force-recreate nginx` did. This showed that editing a bind-mounted config file doesn't guarantee the running container sees it without a recreate/reload.
- Root cause: nginx.conf line 10 had a typo, `app-01:8081` instead of `app-01:8080`.
- Fix: `sed -i 's|server app-01:8081|server app-01:8080|' nginx/nginx.conf`, then `docker compose up -d --force-recreate nginx`.
- Retest evidence: `docker compose exec nginx cat /etc/nginx/nginx.conf | grep "server app"` showed both on 8080; curl still 502 (next issue), but nginx error log changed from "wrong port" to "connection refused on correct port".
- Related commit: b34e935 - "fix: nginx port 81->80, app-01 nginx upstream port 8081->8080, APP_HOST 127.0.0.1->0.0.0.0"
- Remaining uncertainty: none for this issue; force-recreate needed for config reload noted as a process lesson.

## App bind address (APP_HOST) (Part 2) / 2026-09-22 / 3:20 pm

- Symptom: after fixing the nginx upstream port, curl still returned 502; nginx error log showed `connect() failed (111: Connection refused)` to `172.19.0.2:8080` (app-01's network IP), even though the port was correct.
- Hypothesis: app-01 might only be listening on loopback (127.0.0.1), unreachable from other containers on the same network.
- Command or test: `docker compose exec app-01 python -c "import socket; s=socket.socket(); print(s.connect_ex(('127.0.0.1',8080)))"` (returned 0 — reachable via loopback); `grep -rn "run(" app/` showed the app defaults to `host=os.getenv("APP_HOST","0.0.0.0")`; `docker compose exec app-01 env | grep APP_HOST` and `grep -n APP_HOST docker-compose.yml`.
- Actual output: docker-compose.yml line 8 explicitly set `APP_HOST: "127.0.0.1"`, overriding the safe default and binding the app to loopback only.
- Failed attempt and what changed your thinking: initially suspected a Docker networking issue (wrong network, firewall) since nginx and app-01 were confirmed on the same networks (`docker inspect`). Only checking the app's actual bind address (not just the port) revealed the real cause.
- Root cause: docker-compose.yml explicitly overrode `APP_HOST` to `127.0.0.1`, making the app unreachable from any other container despite correct networking and ports.
- Fix: `sed -i 's|APP_HOST: "127.0.0.1"|APP_HOST: "0.0.0.0"|' docker-compose.yml`, then `docker compose up -d --force-recreate app-01 app-02`.
- Retest evidence: `curl http://127.0.0.1:8080/` and `/health` both returned valid JSON through nginx; all 5 containers reported healthy in `docker compose ps -a`.
- Related commit: b34e935 - "fix: nginx port 81->80, app-01 nginx upstream port 8081->8080, APP_HOST 127.0.0.1->0.0.0.0"
- Remaining uncertainty: none.

## Published PostgreSQL/Redis ports (Part 2) / 2026-09-22 / 5:45 pm

- Symptom: brief requires only NGINX published on host port 8080; docker-compose.yml also published PostgreSQL (15432) and Redis (16379) to the host.
- Hypothesis: these lines are leftover from local dev/debugging and violate the brief's requirement directly.
- Command or test: `grep -n "ports:" docker-compose.yml`.
- Actual output: lines 26 and 41 mapped `127.0.0.1:15432:5432` and `127.0.0.1:16379:6379`.
- Failed attempt and what changed your thinking: none — straightforward requirement check.
- Root cause: unneeded host port mappings left in docker-compose.yml.
- Fix: removed both `ports:` lines via sed; kept only nginx's.
- Retest evidence: `docker compose ps -a` shows postgres/redis with no host-port arrow (`5432/tcp`, `6379/tcp` only); `curl 127.0.0.1:15432` returns connection refused; `docker port postgres`/`docker port redis` print nothing.
- Related commit: 3aa0d8c - "fix: remove published PostgreSQL/Redis host ports (15432, 16379) per brief"
- Remaining uncertainty: none.

## Database/Redis connection config mismatch (Part 2) / 2026-09-22 / 6:50 pm

- Symptom: `/records` returned `{"error":"postgres_unavailable"}`; `/ready` showed both postgres and redis as "unavailable", even though `docker compose ps -a` showed both containers healthy.
- Hypothesis: app's connection strings don't match the actual service config.
- Command or test: `docker compose exec app-01 env | grep -i postgres\|redis`, then traced `DATABASE_URL`/`REDIS_URL` to `config/app.env` (via `env_file:` in the `x-app` anchor in docker-compose.yml, not the environment: block directly).
- Actual output: `DATABASE_URL` used port `5433`; actual postgres port is `5432` (default, confirmed via `pg_isready` healthcheck and no `PGPORT` override). `REDIS_URL` used port `6380`; actual redis port is `6379` (confirmed via `redis-cli config get port`). Additionally, the password in `config/app.env`'s `DATABASE_URL` differed by one character from `POSTGRES_PASSWORD` in docker-compose.yml.
- Failed attempt and what changed your thinking: initially checked docker-compose.yml's `environment:` block for `DATABASE_URL`/`REDIS_URL` and found nothing, which looked like a dead end. Checking the running container's actual env (`docker compose exec app-01 env`) showed the values were present, which led to finding `env_file: ./config/app.env` as the real source.
- Root cause: three independent value mismatches in `config/app.env`: wrong postgres port, wrong redis port, wrong password.
- Fix: corrected both ports via sed; password corrected manually (single-character diff) to match `docker-compose.yml`.
- Retest evidence: `/ready` returned `{"postgres":"ready","redis":"ready"}`; `/records` returned actual data instead of an error.
- Related commit: 08b21ab - "fix: correct postgres port 5433->5432, redis port 6380->6379, password mismatch in config/app.env"
- Remaining uncertainty: whether storing the password directly in `config/app.env` (committed to git) is acceptable for this exercise — flagged for decisions.md/security_review.md.

## Instance identity mismatch (Part 2) / 2026-09-22 / 8:45 pm

- Symptom: `/instance` returned `app-01` on every request in a 6-request loop through NGINX — looked like NGINX wasn't load-balancing between backends.
- Hypothesis: NGINX upstream config was misconfigured (e.g. `ip_hash` pinning, or app-02 missing from the pool), causing all traffic to route to one backend.
- Command or test: Inspected `nginx.conf` — `upstream application_pool` correctly lists both `app-01:8080` and `app-02:8080`, no `ip_hash`. Bypassed NGINX entirely: `docker exec nginx wget -qO- http://app-02:8080/` — hit app-02 directly.
- Actual output: Direct request to `app-02:8080` returned `"instance_id":"app-01"`.
- Failed attempt and what changed your thinking: Initially suspected NGINX routing/config. Config was clean, and reaching app-02 directly still returned "app-01" — proved the bug was inside app-02's own identity, not NGINX's routing at all.
- Root cause: `docker-compose.yml`'s `app-02` service had a copy-pasted `INSTANCE_ID: "app-01"` override in its `environment:` block, so both containers reported themselves as app-01 regardless of which one actually served the request.
- Fix: Changed `app-02`'s `INSTANCE_ID` override to `"app-02"` in docker-compose.yml, then `docker compose up -d` to recreate the container with the corrected environment (verified via `docker exec app-02 env | grep -i instance`, since compose's "Started" log line didn't confirm recreation on its own).
- Retest evidence: 6-request loop to `/instance` now alternates cleanly: app-02, app-01, app-02, app-01, app-02, app-01.
- Related commit: 9099880 - "fix: correct app-02 INSTANCE_ID value (was app-01)"
- Remaining uncertainty: none


## Nginx could reach postgres/redis directly (Part 2) / 2026-09-23 / 8:55 am

- Symptom: Task requires nginx blocked from postgres/redis. wget test showed errors, looked blocked.
- Hypothesis: wget errors meant the connection was blocked.
- Command or test: `nc -zv -w3 postgres 5432` and same for redis, from inside nginx container.
- Actual output: both showed "open" — nginx could reach them at the TCP level. wget only failed because postgres/redis don't speak HTTP, not because the network blocked it.
- Failed attempt and what changed your thinking: Trusted wget's failure as proof of isolation. nc proved the opposite — ports were open. Learned wget only tests HTTP, not raw TCP reachability.
- Root cause: nginx was attached to both `frontend` and `backend` networks in docker-compose.yml. Being on `backend` let it reach postgres/redis directly, bypassing isolation.
- Fix: Removed `backend` from nginx's `networks:` list — nginx now only on `frontend`.
- Retest evidence: `nc` now returns "bad address" (can't resolve postgres/redis at all). `/ready` still shows both dependencies healthy via the app containers.
- Related commit: ed9854f - "fix: remove nginx from backend network (was reachable to postgres/redis directly)"
- Remaining uncertainty: none — fix confirmed directly.

## Postgres data not actually persisted (Part 2) / 2026-09-23 / 11:50 am

- Symptom: Task requires proving a record survives postgres container recreation (Part 3). Checked config before testing.
- Hypothesis: Since a named volume (`postgres-data`) was already defined and listed in `docker volume ls`, persistence should already work.
- Command or test: Reviewed docker-compose.yml postgres volumes — `postgres-data` was mounted to `/var/lib/postgresql/backup`, while `/var/lib/postgresql/data` (postgres's real data directory) was mounted as `tmpfs`.
- Actual output: `tmpfs` is memory-backed and wiped on stop; the named volume was attached to the wrong path entirely, so it held nothing postgres actually used.
- Failed attempt and what changed your thinking: Assumed "a named volume exists" was enough to satisfy the requirement. Reading the actual mount paths showed the volume wasn't protecting postgres's real data directory at all — it was effectively a no-op.
- Root cause: `postgres-data` volume mounted to `/var/lib/postgresql/backup` instead of `/var/lib/postgresql/data`; real data directory left on `tmpfs`.
- Fix: Removed `tmpfs:` entry; changed volume mount to `/var/lib/postgresql/data`.
- Retest evidence: 
```
{
  echo "=== Postgres persistence test ==="
  echo "Creating record..."
  curl -s -X POST http://127.0.0.1:8080/records -H "Content-Type: application/json" -d '{"title":"real-persistence-test"}'; echo
  echo "Recreating postgres, app-01, app-02..."
  docker compose -p barq-assessment up -d --force-recreate postgres app-01 app-02
  sleep 5
  echo "Records after recreation:"
  curl -s http://127.0.0.1:8080/records; echo
} | tee troubleshooting_evidence/postgres_persistence_check.txt
```
`troubleshooting_evidence/postgres_persistence_check.txt` — record survives postgres+app recreation.
- Related commit: 79f718a - "fix: mount postgres-data volume to actual data dir (was tmpfs + wrong path)"
- Remaining uncertainty: none — confirmed directly with a real record surviving recreation.

## App containers running as root (Part 2) / 2026-09-23 / 3:30 pm

- Symptom: `docker exec app-01 whoami` returned `root`, failing the "avoid root/privileged operation" requirement.
- Hypothesis: Dockerfile never created a non-root user at all.
- Command or test: `cat Dockerfile`.
- Actual output: Dockerfile already created a non-root user (`app`, uid 10001) and copied app code with `--chown=app:app` — but had an explicit `USER root` line right before `CMD`, overriding all of that.
- Failed attempt and what changed your thinking: Expected to need to add a user from scratch. Reading the file showed the setup was already correct; the bug was one leftover line undoing it.
- Root cause: `USER root` instruction placed after the non-root user setup, switching the final running user back to root.
- Fix: Changed `USER root` to `USER app`.
- Retest evidence: `docker exec app-01 whoami` → `app`. Rebuilt containers show `(healthy)`; `/health` returns 200 through nginx.
- Related commit: 5d8dddb - "fix: remove USER root override, run app containers as non-root (uid 10001)"
- Remaining uncertainty: none — confirmed directly.


## config/app.env committed with real secret (Part 2) / 2026-09-23 / 5:00 pm

- Symptom: Checked whether any real secrets were committed to git history, as required by the brief.
- Hypothesis: Since `.env` was properly gitignored, all secrets were assumed safe.
- Command or test: `git log --all --full-history -- config/app.env`
- Actual output: `config/app.env` (containing the real postgres password) was tracked in git since the baseline commit, and committed again with the real password in a later fix commit.
- Failed attempt and what changed your thinking: Assumed `.gitignore` covering `.env` meant all env files were covered. `config/app.env` used a different path/name and was never added to `.gitignore`, so it was tracked the whole time.
- Root cause: `config/app.env` missing from `.gitignore`; no `.example` version existed either.
- Fix: Added `config/app.env` to `.gitignore`, removed it from tracking with `git rm --cached`, created `config/app.env.example` with placeholder values.
- Retest evidence: `git status` shows `config/app.env` untracked; file still present on disk; containers remain healthy.
- Related commit: 4b8fd3d - "fix: stop tracking config/app.env (contained real secret), add safe .env.example"
- Remaining uncertainty: Real password remains in git history on earlier commits (baseline + prior fix commit). Since this is synthetic lab data per the brief, not rewriting history; noting this as a known limitation rather than a live risk.