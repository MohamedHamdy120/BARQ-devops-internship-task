# Architecture diagram

See `architecture.png` at the repository root.

**Request flow:** Client → host port 8090 (only published port) → NGINX (frontend network) → round-robin (max_fails=1, fail_timeout=5s) across app-01, app-02, app-03 (backend network) → PostgreSQL (service name `postgres:5432`) and Redis (service name `redis:6379`).

**Networks:** `barq-assessment_frontend` connects nginx and all app instances. `barq-assessment_backend` (internal) connects apps to PostgreSQL and Redis. NGINX is not attached to backend, so it cannot reach PostgreSQL/Redis directly — enforced at the Docker network level, not just by convention.

**Health/readiness:** each app container has its own `/health` healthcheck (liveness). NGINX uses `wget --spider`. PostgreSQL uses `pg_isready`; Redis uses `redis-cli ping`. App-level `/ready` (not shown as a container healthcheck) checks both PostgreSQL and Redis before reporting ready.

**Storage:** PostgreSQL uses a named volume, `postgres-data`, mounted at `/var/lib/postgresql/data`. Redis uses AOF persistence to `redis-data`.

**Security:** all three app containers run as non-root (uid 10001); Redis and PostgreSQL run as their own dedicated users.

**Resource limits:** apps 0.5 CPU / 256M each; PostgreSQL 0.75 CPU / 512M; Redis 0.25 CPU / 128M.

**Remaining single points of failure:** PostgreSQL (single instance, no replica), Redis (single instance, no Sentinel/Cluster), NGINX (single instance, no load balancer in front of it). In production, these would need replication/clustering and a redundant edge layer.
