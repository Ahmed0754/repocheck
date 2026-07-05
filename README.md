# repocheck

[![PyPI](https://img.shields.io/pypi/v/repocheck-cli)](https://pypi.org/project/repocheck-cli/)
[![CI](https://github.com/Ahmed0754/repocheck/actions/workflows/ci.yml/badge.svg)](https://github.com/Ahmed0754/repocheck/actions/workflows/ci.yml)

Scan any public GitHub repo and get an instant engineering health report card — scored A–F across 11 checks covering README quality, CI/CD, tests, dependencies, license, activity, security, and more.

```
$ repocheck pallets/flask

╭─ repo ───────────────────────╮
│ pallets/flask                │
│ ★ 68234  ⑂ 16200  Python     │
╰──────────────────────────────╯
╭─ overall health score ───────╮
│ 91/100  (A)                  │
╰──────────────────────────────╯

Check                Score  Grade
README Quality         100    A
CI/CD                   90    A
Test Presence           85    B
Dependency Hygiene      80    B
License                100    A
Commit Activity         95    A
Issue Hygiene           85    B
Security                75    C
Contributing Guide      70    C
Docker/Deploy            0    F
Branch Protection       70    C
```

## Install

```bash
pip install repocheck-cli
```

## Usage

```bash
# basic scan
repocheck pallets/flask

# full URL also works
repocheck https://github.com/psf/requests

# detailed reasoning behind every score
repocheck torvalds/linux -v

# machine-readable JSON (for CI pipelines, scripts)
repocheck your-org/your-repo --json

# markdown report (pipe to a file)
repocheck pallets/flask --md > report.md
```

### Fix suggestions

```bash
# print an actionable checklist of what to improve
repocheck your-org/your-repo --fix

# automatically create missing files (SECURITY.md, CI workflow, etc.)
repocheck your-org/your-repo --auto-fix
```

### Dashboard

```bash
# open a live browser dashboard
repocheck pallets/flask --serve

# auto-refresh every 30 seconds
# open http://127.0.0.1:5678?watch=30 in your browser

# save a standalone HTML report — no server needed, share as a file
repocheck pallets/flask --export report.html
```

### Score history

```bash
# show score trend across past runs (stored locally)
repocheck your-org/your-repo --history

# filter to the last 30 days
repocheck your-org/your-repo --history --since 30
```

### Compare repos

```bash
repocheck pallets/flask --compare psf/requests
```

### Scan an org

```bash
# scan all public repos in a GitHub org, ranked by score
repocheck --org pallets

# limit to top 10
repocheck --org pallets --limit 10
```

### Batch scan

```bash
# repos.txt: one owner/repo per line
repocheck --batch repos.txt
```

### Notifications

```bash
# post report to a Slack channel via webhook
repocheck your-org/your-repo --slack-webhook https://hooks.slack.com/...
```

### CI enforcement

```bash
# exit with code 1 if score drops below threshold (useful in CI)
repocheck your-org/your-repo --min-score 80
```

### Config file

Create `.repocheckrc` in your repo to skip checks or override weights:

```ini
[repocheck]
skip = Docker/Deploy, Branch Protection
min_score = 75

[weights]
Security = 2.0
README Quality = 0.5
```

### Rate limits

GitHub's anonymous API limit is 60 requests/hour. Set a token to raise it to 5,000/hour:

```bash
export GITHUB_TOKEN=ghp_your_token_here
repocheck your-org/your-repo
```

No special scopes needed — a basic personal access token works fine for public repos.

## What it checks

| Check | What it looks at | Weight |
|---|---|---|
| **README Quality** | Presence, length, install/usage sections, badges, code blocks | 1.0 |
| **CI/CD** | GitHub Actions workflows, legacy CI configs | 1.0 |
| **Test Presence** | Test directories, config files, declared test scripts | 1.0 |
| **Dependency Hygiene** | Manifest presence, version pinning, lockfiles | 1.0 |
| **License** | OSS license presence and type | 1.0 |
| **Commit Activity** | Recency and message quality of recent commits | 1.0 |
| **Issue Hygiene** | Open issue count and staleness | 1.0 |
| **Security** | SECURITY.md, Dependabot config, CODEOWNERS | 1.0 |
| **Contributing Guide** | CONTRIBUTING.md presence and length | 0.75 |
| **Docker/Deploy** | Dockerfile, docker-compose, deployment configs | 0.5 |
| **Branch Protection** | Main branch protection rules or rulesets | 0.75 |

## GitHub Action

Use repocheck in CI to gate PRs on health score:

```yaml
- uses: Ahmed0754/repocheck@main
  with:
    repo: your-org/your-repo
    min-score: 80
    token: ${{ secrets.GITHUB_TOKEN }}
```

## Why

Most "is this repo any good" judgments are vibes-based — a glance at stars, maybe the README. `repocheck` turns that into a repeatable, objective checklist you can run on your own repos before sharing them, or use to quickly evaluate a dependency before adopting it.

## Local development

```bash
git clone https://github.com/Ahmed0754/repocheck
cd repocheck
pip install -e "."
pytest tests/
```

## License

MIT
