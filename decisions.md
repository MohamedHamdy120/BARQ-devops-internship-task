# Technical decisions

Record at least 5 decisions. Include assumptions and limits.

## Decision
- Choice:
- Why:
- Alternative:
- Trade-off:
- Evidence / commit:
- Production improvement:

Cover your base image, health checks, networks, timeouts/retries, restart/resource settings,
storage and any other meaningful choices.

## Decision: NGINX host port mapping (80, not 81)
- Choice: map host port 8080 to container port 80 in docker-compose.yml.
- Why: nginx.conf already listens on 80; compose had a stale/wrong mapping to 81, which nothing listened on.
- Alternative: change nginx.conf to `listen 81;` instead.
- Trade-off: functionally identical either way. Chose to keep nginx.conf on the standard HTTP port and fix the mapping in compose, since compose is where external port choices belong.
- Evidence / commit: `docker compose ps -a` showed `127.0.0.1:8080->80/tcp`; curl reached nginx. Commit: b34e935
- Production improvement: none needed; this is a standard pattern.

## Decision: App bind address 0.0.0.0, not 127.0.0.1
- Choice: set `APP_HOST=0.0.0.0` for app-01/app-02.
- Why: docker-compose.yml explicitly overrode it to `127.0.0.1`, which only accepts connections from inside the same container — nginx (a different container) got "connection refused" even though ports and networking were correct.
- Alternative: none reasonable; a containerized service must bind 0.0.0.0 to be reachable from other containers.
- Trade-off: 0.0.0.0 exposes the app to anything on its Docker networks, not just nginx. Acceptable because app ports are not published to the host — confirmed only reachable via `backend`/`frontend` networks.
- Evidence / commit: `curl http://127.0.0.1:8080/` and `/health` returned valid JSON through nginx; all 5 containers healthy. Commit: b34e935
- Production improvement: if app ports were ever published to the host, this would need firewall rules or reverting to a more restricted bind + reverse-proxy-only access.

## Decision: Do not publish PostgreSQL/Redis ports to the host
- Choice: Removed the host port mappings for postgres (`15432:5432`) and redis (`16379:6379`) from docker-compose.yml. Both services stay on the `backend` network only, reachable by service name from app-01/app-02, with no `ports:` entry at all.
- Why: The brief explicitly requires "Publish only NGINX on host port 8080. Do not publish app, PostgreSQL or Redis ports." Any host-mapped port bypasses the frontend/backend network isolation entirely — it would let anything on the host machine (or, in a real deployment, anything on the host's network) connect directly to the database or cache, skipping the app layer completely.
- Alternative: Keep the host ports mapped, but restrict access with a firewall rule or bind them to `127.0.0.1` only instead of `0.0.0.0`.
- Trade-off: Removing the host ports means you lose the convenience of connecting a local GUI client (e.g. psql, RedisInsight) directly from the host for debugging. The safer alternative is `docker exec -it postgres psql ...` or `docker exec -it redis redis-cli`, which stays inside the Docker network and requires no published port at all.
- Evidence / commit: `docker compose ps --format "table {{.Name}}\t{{.Ports}}"` shows only nginx with a host-side port (`127.0.0.1:8080->80/tcp`); postgres and redis show container-only ports. Commit: 3aa0d8c.
- Production improvement: In production, extend this further — no direct host access to data-tier services at all; use a bastion host or VPN with time-limited, audited access instead of open ports.

## Decision: nginx only on the frontend network
- Choice: nginx is attached only to `frontend`, not `backend`.
- Why: nginx's only job is to proxy client requests to app-01/app-02. It never needs to talk to postgres or redis directly.
- Alternative: Keep nginx on both networks (simpler compose file, one less thing to think about).
- Trade-off: Being on both networks would work fine functionally, but breaks the task's isolation requirement and is a real security risk — if nginx were ever compromised, an attacker could reach the database directly.
- Evidence / commit: `nc -zv` from nginx to postgres/redis failed after the fix (was open before). Commit: ed9854f
- Production improvement: none — this is already the correct production pattern (least privilege networking).

## Decision: Redis persistence via AOF
- Choice: Enabled `--appendonly yes` with a named volume (`redis-data`), replacing the starter's `--save "" --appendonly no` (no persistence).
- Why: `/counter` is a required, graded endpoint — its value should survive a restart, not silently reset to 0.
- Alternative: RDB snapshots (`--save`) instead of AOF.
- Trade-off: AOF is more durable (logs every write) but slightly slower than RDB snapshots; fine for this scale.
- Evidence / commit:

```bash
{
  echo "=== Redis persistence test ==="
  echo "Before restart:"
  curl -s http://127.0.0.1:8080/counter; echo
  curl -s http://127.0.0.1:8080/counter; echo
  echo "Restarting redis..."
  docker compose -p barq-assessment restart redis
  sleep 2
  echo "After restart:"
  curl -s http://127.0.0.1:8080/counter; echo
} | tee troubleshooting_evidence/redis_persistence_check.txt
```

Result: counter went 1→2→(redis restart)→3, not reset. Commit: ae0324f.
- Production improvement: consider AOF rewrite tuning (`auto-aof-rewrite-percentage`) for high write volume.


## Decision: Base image and healthcheck choice
- Choice: Used `-alpine` variants for nginx, postgres, and redis (small, official images). Healthchecks use tools already inside each image — `wget --spider` for nginx, `pg_isready` for postgres, `redis-cli ping` for redis — no extra tools installed.
- Why: Alpine images are much smaller than full Debian/Ubuntu-based ones (faster pulls, smaller attack surface, fewer packages to patch). Using each image's built-in tool for healthchecks avoids installing curl or other extras just for checking — keeps images minimal, as the brief asks ("Use required dependencies only").
- Alternative: Full Debian-based images (e.g. `nginx:1.28`, `postgres:16`) with curl pre-installed, or a dedicated healthcheck tool added via package manager.
- Trade-off: Alpine uses musl libc instead of glibc, which occasionally causes subtle compatibility issues with some software — not a problem here since official images are built/tested for alpine. Slightly less tooling available inside the container (e.g. no bash by default) means healthcheck commands must use what's already there (wget, not curl, in nginx's case worked fine).
- Evidence / commit: `docker compose ps -a` shows all 5 containers `(healthy)`. Commit:2e0ed93 .
- Production improvement: none needed — alpine + built-in tool healthchecks is already the recommended lightweight production pattern.

## Decision: Restart policy — unless-stopped
- Choice: All 5 services use `restart: unless-stopped`.
- Why: Containers should recover automatically from crashes or a host reboot, but not fight against intentional manual stops — needed for `failure_test.sh`, which deliberately stops a backend to test recovery.
- Alternative: `restart: always` (also restarts after manual `docker stop`) or `restart: on-failure` (only restarts on non-zero exit, not clean stops).
- Trade-off: `always` would break the failure test by auto-restarting a container the test just stopped on purpose. `on-failure` wouldn't help after a host reboot if a container exited cleanly. `unless-stopped` balances both cases correctly for this project.
- Evidence / commit: `docker compose ps -a` shows all 5 containers healthy after applying the policy. Commit: 654f050 .
- Production improvement: none — `unless-stopped` (or an orchestrator-managed restart policy like Kubernetes' `Always` with proper liveness probes) is already standard practice.


## Decision: Resource limits per service
- Choice: Set different CPU/memory limits per service instead of one blanket value — nginx: 0.25 CPU/64M, app-01+app-02: 0.5 CPU/256M each, redis: 0.25 CPU/128M, postgres: 0.75 CPU/512M.
- Why: Each service has different real needs. nginx just proxies requests (lightweight); postgres runs actual queries and needs the most headroom; the app containers sit in between; redis is in-memory but the dataset here is tiny.
- Alternative: One uniform limit for all 5 services (simpler to write, less to reason about).
- Trade-off: Uniform limits either starve postgres (if set low, matching nginx) or waste resources on nginx (if set high, matching postgres). Per-service limits use the machine's stated 2 CPU/4GB budget more efficiently — total here is ~2.5 CPU/~1.2GB, comfortably within the README's suggested capacity.
- Evidence / commit: `docker compose ps -a` — all 5 containers still `(healthy)` after limits applied, no crashes or OOM kills. Commit: 8531ec3 .
- Production improvement: In real deployment, size limits from actual load-tested metrics (CPU/memory profiling under expected traffic), not estimates, and pair with autoscaling instead of static caps.


## Decision: NGINX upstream failover settings
- Choice: `proxy_next_upstream error timeout http_502 http_503 http_504;` with `proxy_next_upstream_tries 2;`, and `max_fails=1 fail_timeout=5s` per upstream server.
- Why: A dead backend should not cause client-visible errors when a healthy backend is available — the whole point of running two app instances.
- Alternative: Keep `proxy_next_upstream off` (starter default) — simplest, but means any single backend failure directly causes client errors, defeating the purpose of redundancy.
- Trade-off: Retrying on failure adds latency to affected requests (has to try the dead backend first, then fail over) and slightly more complexity to reason about. `max_fails=1` is aggressive — a single failure marks a backend down for 5s, which is fine for this lab but might be too sensitive for a flaky network in production (could cause unnecessary failover on a one-off blip).
- Evidence / commit: `failure_test.py` — 0 timeouts during backend failure after the fix, vs 3/6 before. Commit: f038bd4.
- Production improvement: tune `fail_timeout` and `max_fails` based on real traffic patterns; consider active health checks (NGINX Plus or a sidecar) instead of purely passive failure detection.


## Decision: Fixed CI-only database password instead of GitHub Secrets
- Choice: CI workflow writes a hardcoded password (`ci_lab_password_123`) into `config/app.env` and `POSTGRES_PASSWORD` during the run, instead of using a GitHub repository secret.
- Why: Simpler to set up under time pressure — no repo configuration step outside the codebase, and the value only ever exists inside a disposable GitHub Actions runner.
- Alternative: Store the real/CI password as a GitHub Actions secret (`secrets.CI_DB_PASSWORD`) and inject it into both `config/app.env` and `docker-compose.yml`'s `POSTGRES_PASSWORD`.
- Trade-off: A hardcoded value in a committed workflow file is visible to anyone with repo access — not ideal practice even for a throwaway value. Acceptable here since it's synthetic lab data (per the brief), never protects real data, and the runner (including postgres) is destroyed after every CI run.
- Evidence / commit: CI run passed (green) using this password. Commit: bcc57cc.
- Production improvement: Use GitHub Secrets (or an equivalent secret manager) for any credential in a real CI/CD pipeline, even a database used only for testing.