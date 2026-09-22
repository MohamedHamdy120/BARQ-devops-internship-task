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