# repocheck

[![PyPI](https://img.shields.io/pypi/v/repocheck-cli)](https://pypi.org/project/repocheck-cli/)

Scan any public GitHub repo and get an instant engineering health report card — README quality, CI/CD, test presence, dependency hygiene, license, commit activity, and issue hygiene, scored A–F.

```
$ repocheck pallets/flask

╭─ repo ──────────────────╮
│ pallets/flask           │
│ ★ 68234  ⑂ 16200  Python│
╰──────────────────────────╯
╭─ overall health score ──╮
│ 91/100  (A)              │
╰───────────────────────────╯

Check               Score  Grade
README Quality        100    A
CI/CD                  90    A
Test Presence          85    B
Dependency Hygiene     80    B
License               100    A
Commit Activity        95    A
Issue Hygiene          85    B
```

## Install

```bash
pip install repocheck-cli
```

## Usage

```bash
# owner/repo shorthand
repocheck pallets/flask

# full URL also works
repocheck https://github.com/psf/requests

# detailed reasoning behind every score
repocheck torvalds/linux -v

# machine-readable output (for CI pipelines, scripts)
repocheck your-org/your-repo --json
```

### Higher rate limits

GitHub's anonymous API limit is 60 requests/hour. `repocheck` makes ~8 requests per scan, so you'll hit that fast without auth. Set a token to bump it to 5,000/hour:

```bash
export GITHUB_TOKEN=ghp_your_token_here
repocheck your-org/your-repo
```

No special scopes needed — a basic personal access token works fine for public repos.

## What it checks

| Check | What it looks at |
|---|---|
| **README Quality** | Presence, length, install/usage sections, badges, code blocks |
| **CI/CD** | GitHub Actions workflows, legacy CI configs |
| **Test Presence** | Test directories, test config files, declared test scripts |
| **Dependency Hygiene** | Manifest presence, version pinning, lockfiles |
| **License** | OSS license presence and type |
| **Commit Activity** | Recency and message quality of recent commits |
| **Issue Hygiene** | Open issue count and staleness |

Each check is scored 0–100 and the overall score is an average across all seven.

## Why

Most "is this repo any good" judgments are vibes-based — a glance at stars, maybe the README. `repocheck` turns that into a repeatable, objective-ish checklist you can run on your own repos before sharing them, or use to quickly evaluate a dependency before adopting it.

## Local development

```bash
git clone https://github.com/Ahmed0754/repocheck
cd repocheck
pip install -e ".[dev]"
repocheck pallets/flask
```

## License

MIT
