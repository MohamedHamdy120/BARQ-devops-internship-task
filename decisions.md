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