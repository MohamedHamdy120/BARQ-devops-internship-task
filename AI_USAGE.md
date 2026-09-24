# AI usage disclosure

Write None if no AI was used. Otherwise record each use:

- Tool/model:
- Purpose:
- Files or decisions affected:
- What you changed or rejected:
- How you independently verified it:
- Related commit:

You may use AI and external resources. You must understand and demonstrate the work.


# AI usage disclosure

## Use 1: Concept explanations
- Tool/model: Claude (claude.ai chat)
- Purpose: Asked AI to explain and review concepts as they came up — Python syntax (dicts, sets, defaultdict), Docker networking behavior, NGINX directives (proxy_next_upstream, max_fails), tmpfs vs volumes, restart policy differences.
- Files or decisions affected: none directly — background understanding that informed decisions across all parts.
- What you changed or rejected: n/a
- How you independently verified it: Applied the explained concepts directly by running commands and observing real behavior matched the explanation (e.g. confirmed `set()` dedup behavior, confirmed tmpfs data loss, confirmed restart policy effects).
- Related commit: n/a

## Use 2: Debugging support during investigation
- Tool/model: Claude (claude.ai chat)
- Purpose: I ran commands and formed my own hypotheses; used AI to check my reasoning and get a second opinion before acting on bugs (e.g. instance-ID mismatch, nginx network isolation, postgres persistence, nginx failover).
- Files or decisions affected: docker-compose.yml, nginx.conf, Dockerfile
- What you changed or rejected: Rejected trusting a `wget` failure as proof of network isolation — confirmed independently with `nc -zv` instead, which showed the ports were actually open.
- How you independently verified it: Ran every diagnostic/fix command myself and read real output before accepting a conclusion (`nc -zv`, `docker exec ... env`, `ps aux`, curl/instance-loop tests).
- Related commit: see troubleshooting.md entries.

## Use 3: Script writing (validate.py, failure_test.py, backup.sh/restore.sh)
- Tool/model: Claude (claude.ai chat)
- Purpose: I designed the logic for each script myself — what to check, in what order, what counts as pass/fail — as pseudocode, then had AI translate that into working Python/Bash syntax. I reviewed the generated code line by line and compared it to my initial Python/Bash script I generated to confirm it matched my intended logic and flag anything unrelated or wrong.
- Files or decisions affected: validate.py, failure_test.py, backup.sh, restore.sh .
- What you changed or rejected: Chose `--data-only` pg_dump over the initial full-schema dump after it caused real restore errors I found by testing. Considered GitHub Secrets for the CI database password but chose a documented hardcoded lab-only value instead, reasoning it's synthetic/ephemeral data, not a real credential.
- How you independently verified it: Ran each script against the real environment and read actual output — `failure_test.py` results before/after the nginx fix, backup/restore tested end-to-end with a real record surviving volume wipe + restore, CI run confirmed green on GitHub Actions.
- Related commit: see decisions.md and troubleshooting.md entries.

## Use 4: Documentation drafting
- Tool/model: Claude (claude.ai chat)
- Purpose: I decided what each entry needed to say based on what I actually did; used AI to help structure/word it, then edited anything that didn't match what really happened.
- Files or decisions affected: troubleshooting.md, decisions.md, log_analysis.md, README.md, AI_USAGE.md
- What you changed or rejected: Edited wording that misrepresented my reasoning.
- How you independently verified it: Cross-checked every drafted entry against actual command output and real events from the session before committing.
- Related commit: see individual doc commits.

## Use 5: Background research
- Tool/model: Web search, YouTube
- Purpose: General background on Docker networking, NGINX configuration concepts and Python/Bash syntax.
- Files or decisions affected: none directly — general understanding only.
- What you changed or rejected: n/a
- How you independently verified it: n/a
- Related commit: n/a

You may use AI and external resources. You must understand and demonstrate the work.