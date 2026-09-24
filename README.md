# BARQ DevOps Internship Task

Fixed, tested, and documented environment: two Flask instances behind NGINX, with PostgreSQL and Redis.

## Setup

```bash
git clone https://github.com/MohamedHamdy120/BARQ-devops-internship-task
cd barq-academy
cp .env.example .env
cp config/app.env.example config/app.env
```

Edit `config/app.env` and replace `CHANGE_ME` in `DATABASE_URL` with the password set in
`docker-compose.yml`'s `POSTGRES_PASSWORD` (lab-only synthetic value, never a real credential).

## Build & Start

```bash
docker compose -p barq-assessment up -d --build
docker compose -p barq-assessment ps -a
```

All 5 containers (app-01, app-02, nginx, postgres, redis) should show `healthy` within ~15 seconds.

## Verify endpoints

```bash
curl -s http://127.0.0.1:8080/
curl -s http://127.0.0.1:8080/health
curl -s http://127.0.0.1:8080/ready
curl -s http://127.0.0.1:8080/instance
curl -s http://127.0.0.1:8080/records
curl -s http://127.0.0.1:8080/counter
```

## Run validation

```bash
python3 validate.py
```

Runs 10 checks (endpoint availability, both backends responding, postgres/redis readiness,
prohibited host ports closed, network isolation) — exits non-zero on any failure.

## Run failure test

```bash
python3 failure_test.py
```

Stops app-01, proves traffic continues via app-02, restarts app-01, proves it rejoins rotation.

## Backup & restore

```bash
./backup.sh
# creates backups/backup_<timestamp>.sql

./restore.sh backups/backup_<timestamp>.sql
```

To prove persistence across container recreation:
```bash
curl -s -X POST http://127.0.0.1:8080/records -H "Content-Type: application/json" -d '{"title":"test"}'
docker compose -p barq-assessment up -d --force-recreate postgres app-01 app-02
curl -s http://127.0.0.1:8080/records   # record still present
```

## Cleanup

```bash
docker compose -p barq-assessment down
```

Do not use `--volumes` unless you intend to permanently delete postgres/redis data.

## Documentation

- `troubleshooting.md` — investigation journal, including failed attempts
- `log_analysis.md` — log analysis questions and answers
- `decisions.md` — technical decisions and trade-offs
- `security_review.md` — security risks and improvements
- `AI_USAGE.md` — AI tool usage disclosure
- `architecture.png` — request flow, ports, networks, storage diagram
- `docs/EVIDENCE_INDEX.md` — requirement → file/output → commit → video timestamp mapping

## CI

`.github/workflows/ci.yml` builds the stack and runs `validate.py` on every push/PR.