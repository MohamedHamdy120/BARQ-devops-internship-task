# Security and production-readiness review

## Finding 1: Secret committed to git history
- Risk and evidence: `config/app.env` (real postgres password) was tracked in git since the baseline commit — confirmed via `git log --all --full-history -- config/app.env`.
- Impact: Anyone with repo access could read the database password from commit history, even after removing the file going forward.
- Implemented fix / commit: Added `config/app.env` to `.gitignore`, removed from tracking, created `config/app.env.example` with placeholders. Commit: 4b8fd3d.
- Production follow-up: Real secrets would need git history rewriting and credential rotation — not done here since this is synthetic lab data.
- How to verify: `git log --all --full-history -- config/app.env` still shows old exposure; `git status` confirms untracked going forward.

## Finding 2: Database/cache ports published to host
- Risk and evidence: Starter published postgres (15432) and redis (16379) directly to the host, bypassing the app layer entirely.
- Impact: Anything on the host machine (or host network in a real deployment) could connect straight to the database/cache, skipping application-level access control.
- Implemented fix / commit: Removed both host port mappings; services reachable only via the `backend` Docker network. Commit: 3aa0d8c.
- Production follow-up: In production, data-tier access should go through a bastion/VPN, never a directly published port.
- How to verify: `docker compose ps --format "table {{.Name}}\t{{.Ports}}"` shows only nginx with a host port.

## Finding 3: NGINX could reach the database tier directly
- Risk and evidence: nginx was attached to both `frontend` and `backend` networks; `nc -zv` from inside nginx showed postgres:5432 and redis:6379 both open.
- Impact: A compromised nginx container (e.g. via a config exploit) could reach the database/cache directly, bypassing the app layer entirely.
- Implemented fix / commit: Removed `backend` from nginx's `networks:` list — nginx now only on `frontend`. Commit: ed9854f.
- Production follow-up: Apply least-privilege networking to every service by default in any multi-tier deployment, not just as an afterthought fix.
- How to verify: `nc -zv` from nginx to postgres/redis now returns "bad address" (unresolvable).

## Finding 4: App containers running as root
- Risk and evidence: Dockerfile created a non-root user (`app`, uid 10001) but then explicitly set `USER root` before CMD, undoing it. `docker exec app-01 whoami` returned `root`.
- Impact: A container compromise (e.g. via a code vulnerability) would give an attacker root inside the container, increasing the blast radius.
- Implemented fix / commit: Changed `USER root` to `USER app`. Commit: 5d8dddb.
- Production follow-up: Add a CI lint step that fails the build if any Dockerfile ends with root as the effective user.
- How to verify: `docker exec app-01 whoami` → `app`.

## Finding 5: Postgres data directory mounted as tmpfs, named volume pointed at wrong path
- Risk and evidence: `postgres-data` named volume was mounted to `/var/lib/postgresql/backup`, while the actual data directory `/var/lib/postgresql/data` was tmpfs (memory-backed, wiped on stop).
- Impact: All database data would be lost on every container stop/restart, despite appearing to have a named volume configured — a false sense of persistence.
- Implemented fix / commit: Removed `tmpfs:` entry, mounted `postgres-data` to the correct path `/var/lib/postgresql/data`. Commit: 79f718a.
- Production follow-up: Add a routine persistence smoke test (create record → recreate container → verify) to CI, not just a manual one-time check.
- How to verify: `troubleshooting_evidence/postgres_persistence_check.txt` — record survives postgres+app recreation.

## Finding 6: No redis persistence
- Risk and evidence: Starter redis ran with `--save "" --appendonly no` — zero persistence; a restart wipes all data including the `/counter` value.
- Impact: The counter (a required, graded endpoint) would silently reset to 0 on any redis restart.
- Implemented fix / commit: Enabled `--appendonly yes` with a named volume (`redis-data`). Commit: ae0324f.
- Production follow-up: For higher write volume, tune AOF rewrite settings (`auto-aof-rewrite-percentage`).
- How to verify: `troubleshooting_evidence/redis_persistence_check.txt` — counter value survives redis restart.

## Finding 7: No automatic failover between app backends
- Risk and evidence: `proxy_next_upstream off` and `max_fails=0` on both upstream servers meant a dead backend caused client-visible 504 errors instead of failing over to the healthy one — confirmed via `failure_test.py` (3/6 requests failed during a deliberate app-01 outage).
- Impact: A single backend failure directly impacts availability for roughly half of client traffic, despite running two instances specifically for redundancy.
- Implemented fix / commit: Changed to `proxy_next_upstream error timeout http_502 http_503 http_504;` with `max_fails=1 fail_timeout=5s`. Commit: f038bd4.
- Production follow-up: Tune `fail_timeout`/`max_fails` against real traffic patterns; consider active health checks instead of purely passive failure detection.
- How to verify: `troubleshooting_evidence/failure_test_run.txt` — 0/6 requests failed after the fix.


## Finding 8: Single points of failure remain
- Risk and evidence: Single postgres instance, single redis instance, single nginx instance — each is a single point of failure despite the app layer being redundant (app-01/app-02).
- Impact: postgres, redis, or nginx going down takes down the entire stack, regardless of app-layer redundancy.
- Implemented fix / commit: None
- Production follow-up: Postgres replication (primary + replica), Redis Sentinel/Cluster, multiple nginx instances behind a load balancer.
- How to verify: n/a — documented as a known limitation.


## Limitation: validation script not port-aware
- Risk: validate.py assumes the service is always on port 8080. After a live port change (e.g. to 8090, as required in Part 5), the script fails entirely rather than adapting — meaning automated validation cannot follow a live config change without manual editing.
- Impact: low for this exercise (caught immediately, documented); in production this pattern would mean monitoring/validation tooling silently stops working after a legitimate config change unless someone remembers to update it too.
- Implemented fix: none — documented as-is with real failing output (see evidence index).
- Production improvement: parameterize the target URL/port via CLI arg, env var, or service discovery, so validation tracks the actual running config automatically.