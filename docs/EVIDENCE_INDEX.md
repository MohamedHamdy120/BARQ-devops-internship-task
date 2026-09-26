# Evidence and submission index

- Repository URL:
- Final commit:
- Matching CI run:
- Continuous 12-18 minute video URL:
- Challenge receipt ID:
- Starting video commit:
- Later documentation-only commits, if any:

For each requirement, link: file/output -> commit -> video timestamp.
Match the final README, diagram, GitHub code and video (three instances, public port 8090).


- Repository URL: https://github.com/MohamedHamdy120/BARQ-devops-internship-task
- Final commit: 0984a6f
- Matching CI run: https://github.com/MohamedHamdy120/BARQ-devops-internship-task/actions/runs/36237527245
- Continuous 12-18 minute video URL: https://drive.google.com/file/d/16_8assB9VnwDqQ76cnOBtPY8DGJBArbz/view
- Challenge receipt ID: e49437b049854b818839ea3877f68ea7
- Starting video commit: 3575ffd
- Later documentation-only commits, if any: docs/EVIDENCE_INDEX.md and related Part 4 doc commits made after the video was recorded (post-recording documentation only, no functional changes)


## Requirement → file/output → commit → video timestamp

| Requirement | File / Output | Commit | Video Timestamp |
|---|---|---|---|
| Starting commit, clean git status | git log, git status | 8442da3 | 00:10 |
| Environment build/start, health | docker-compose.yml | 3575ffd | 00:29 |
| Core endpoints (/, /health, /ready, /records, /counter) | app/server.py | 3575ffd | 01:30 |
| Both backends via /instance | nginx/nginx.conf | 3575ffd | 02:35 |
| Backend failure + recovery | — | 3575ffd | 03:30 |
| Record survives container recreation | docker-compose.yml | 3575ffd | 04:40 |
| validate.py / failure_test run | validate.py | 3575ffd | 06:45 |
| Historical log finding | analysis/q4_dependency.txt | 3575ffd | 10:10 |
| video_challenge.sh + live fix | .assessment/challenge.json | 3575ffd | 11:50 |
| Port 8080→8090 live | .env / docker-compose.yml | 3575ffd | 13:00 |
| Third instance added live | docker-compose.yml | 3575ffd | 16:00 |
| git status/diff/commit shown on screen | .env, docker-compose.yml | 3575ffd | 16:00 |
| CI workflow, green run | .github/workflows/ci.yml | 3575ffd | [Actions run](https://github.com/MohamedHamdy120/BARQ-devops-internship-task/actions/runs/36237527245) |

