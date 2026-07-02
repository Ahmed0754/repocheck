"""Individual health checks. Each returns a CheckResult with a 0-100 score."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from .github_client import GitHubClient, RepoRef

DEPENDENCY_FILES = (
    "requirements.txt",
    "package.json",
    "Pipfile",
    "pyproject.toml",
    "go.mod",
    "Cargo.toml",
)

TEST_DIR_HINTS = ("test", "tests", "__tests__", "spec")
TEST_CONFIG_HINTS = (
    "pytest.ini",
    "setup.cfg",
    "tox.ini",
    "jest.config.js",
    "jest.config.ts",
    "vitest.config.ts",
    "phpunit.xml",
)


@dataclass
class CheckResult:
    name: str
    score: int  # 0-100
    grade: str
    details: list[str] = field(default_factory=list)
    weight: float = 1.0

    @staticmethod
    def grade_for(score: int) -> str:
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        if score >= 60:
            return "D"
        return "F"


def _result(name: str, score: int, details: list[str], weight: float = 1.0) -> CheckResult:
    score = max(0, min(100, score))
    return CheckResult(name=name, score=score, grade=CheckResult.grade_for(score), details=details, weight=weight)


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_readme(client: GitHubClient, ref: RepoRef) -> CheckResult:
    files = client.root_files(ref)
    readme_name = next((f for f in files if f.lower().startswith("readme")), None)

    if not readme_name:
        return _result("README", 0, ["No README file found at repo root."])

    text = client.file_text(ref, readme_name) or ""
    details = [f"Found {readme_name} ({len(text)} chars)."]
    score = 30  # baseline for existing

    length = len(text)
    if length > 300:
        score += 15
        details.append("Has substantive content (>300 chars).")
    else:
        details.append("Very short — consider expanding (currently <300 chars).")

    lower = text.lower()

    has_install = bool(re.search(r"\b(install|pip install|npm install|getting started|setup)\b", lower))
    if has_install:
        score += 20
        details.append("Includes install/setup instructions.")
    else:
        details.append("No clear install/setup section found.")

    has_usage = bool(re.search(r"\b(usage|example|quick ?start)\b", lower))
    if has_usage:
        score += 20
        details.append("Includes usage/example section.")
    else:
        details.append("No usage or example section found.")

    has_badges = "![" in text and ("shields.io" in text or "badge" in lower)
    if has_badges:
        score += 10
        details.append("Has status badges (CI, version, etc).")

    has_code_block = "```" in text
    if has_code_block:
        score += 5
        details.append("Contains code blocks.")

    return _result("README Quality", score, details)


def check_ci(client: GitHubClient, ref: RepoRef) -> CheckResult:
    workflows = client.workflows(ref)
    if workflows:
        names = [w["name"] for w in workflows if w.get("type") == "file"]
        return _result(
            "CI/CD",
            90 if len(names) >= 1 else 70,
            [f"GitHub Actions configured ({len(names)} workflow file(s)): {', '.join(names) or 'unnamed'}."],
        )

    root_files = client.root_files(ref)
    legacy = [f for f in root_files if f in (".travis.yml", ".circleci", "azure-pipelines.yml", ".gitlab-ci.yml")]
    if legacy:
        return _result("CI/CD", 60, [f"Legacy CI config found: {', '.join(legacy)}. Consider migrating to GitHub Actions."])

    return _result("CI/CD", 0, ["No CI/CD configuration found (no .github/workflows, no legacy CI config)."])


def check_tests(client: GitHubClient, ref: RepoRef) -> CheckResult:
    dirs = [d.lower() for d in client.root_dirs(ref)]
    files = [f.lower() for f in client.root_files(ref)]

    has_test_dir = any(hint in dirs for hint in TEST_DIR_HINTS)
    has_test_config = any(hint in files for hint in TEST_CONFIG_HINTS)

    details = []
    score = 0

    if has_test_dir:
        score += 60
        matched = [d for d in dirs if d in TEST_DIR_HINTS]
        details.append(f"Found test directory: {', '.join(matched)}.")
    else:
        details.append("No conventional test directory found (tests/, test/, __tests__/, spec/).")

    if has_test_config:
        score += 25
        matched = [f for f in files if f in [h.lower() for h in TEST_CONFIG_HINTS]]
        details.append(f"Found test config: {', '.join(matched)}.")

    # package.json may declare a test script
    pkg = client.file_text(ref, "package.json")
    if pkg and '"test"' in pkg and "no test specified" not in pkg.lower():
        score += 15
        details.append("package.json declares a test script.")

    if score == 0:
        details.append("No evidence of automated testing.")

    return _result("Test Presence", score, details)


def check_dependencies(client: GitHubClient, ref: RepoRef) -> CheckResult:
    files = client.root_files(ref)
    found = [f for f in DEPENDENCY_FILES if f in files]

    if not found:
        return _result("Dependency Hygiene", 50, ["No standard dependency manifest found — may be dependency-free or non-standard layout."])

    details = [f"Found manifest(s): {', '.join(found)}."]
    score = 70  # baseline for having a manifest

    # Check for pinned vs unpinned versions as a rough hygiene signal
    if "requirements.txt" in found:
        text = client.file_text(ref, "requirements.txt") or ""
        lines = [l for l in text.splitlines() if l.strip() and not l.startswith("#")]
        pinned = [l for l in lines if "==" in l]
        if lines:
            pin_ratio = len(pinned) / len(lines)
            if pin_ratio > 0.7:
                score += 15
                details.append(f"{len(pinned)}/{len(lines)} dependencies are version-pinned.")
            else:
                details.append(f"Only {len(pinned)}/{len(lines)} dependencies are version-pinned — consider pinning for reproducibility.")

    if "package.json" in found:
        text = client.file_text(ref, "package.json") or ""
        if '"dependencies"' in text or '"devDependencies"' in text:
            score += 10
            details.append("package.json declares dependencies.")
        if "lock" in [f.lower() for f in files] or "package-lock.json" in files or "yarn.lock" in files:
            score += 10
            details.append("Lockfile present (reproducible installs).")
        else:
            details.append("No lockfile found (package-lock.json / yarn.lock) — installs may not be reproducible.")

    return _result("Dependency Hygiene", score, details)


def check_license(client: GitHubClient, ref: RepoRef) -> CheckResult:
    repo_data = client.repo(ref)
    license_info = repo_data.get("license")
    if license_info:
        return _result("License", 100, [f"Licensed under {license_info.get('name', license_info.get('spdx_id'))}."])

    files = client.root_files(ref)
    license_file = next((f for f in files if f.lower().startswith("license")), None)
    if license_file:
        return _result("License", 80, [f"License file present ({license_file}) but not detected by GitHub's API."])

    return _result("License", 0, ["No license found. Repo is effectively 'all rights reserved' by default."])


def check_activity(client: GitHubClient, ref: RepoRef) -> CheckResult:
    commits = client.commits(ref, per_page=30)
    if not commits:
        return _result("Commit Activity", 0, ["No commit history accessible."])

    details = []
    score = 0

    try:
        latest_date_str = commits[0]["commit"]["committer"]["date"]
        latest_date = datetime.fromisoformat(latest_date_str.replace("Z", "+00:00"))
        days_since = (datetime.now(timezone.utc) - latest_date).days
        details.append(f"Last commit {days_since} day(s) ago.")
        if days_since <= 30:
            score += 50
        elif days_since <= 180:
            score += 30
        elif days_since <= 365:
            score += 15
        else:
            details.append("Repo appears inactive (no commits in over a year).")
    except (KeyError, ValueError):
        pass

    # Commit message quality — rough heuristic: average length, non-trivial messages
    messages = [c["commit"]["message"].splitlines()[0] for c in commits if c.get("commit")]
    trivial = sum(1 for m in messages if m.strip().lower() in ("fix", "update", "wip", "test", "asdf", "."))
    avg_len = sum(len(m) for m in messages) / len(messages) if messages else 0

    if avg_len >= 20:
        score += 30
        details.append(f"Commit messages average {avg_len:.0f} chars — reasonably descriptive.")
    else:
        details.append(f"Commit messages average {avg_len:.0f} chars — consider more descriptive messages.")

    if trivial / max(len(messages), 1) > 0.3:
        details.append(f"{trivial}/{len(messages)} recent commits have low-effort messages (e.g. 'fix', 'wip').")
    else:
        score += 20

    return _result("Commit Activity", score, details)


def check_issue_hygiene(client: GitHubClient, ref: RepoRef) -> CheckResult:
    repo_data = client.repo(ref)
    open_issues = repo_data.get("open_issues_count", 0)

    if open_issues == 0:
        return _result("Issue Hygiene", 100, ["No open issues — clean backlog (or issues disabled)."])

    issues = client.issues(ref, state="open", per_page=50)
    # Filter out PRs, which the issues endpoint includes
    real_issues = [i for i in issues if "pull_request" not in i]

    if not real_issues:
        return _result("Issue Hygiene", 90, [f"{open_issues} open issue(s) reported, but none returned detail (possibly all PRs)."])

    now = datetime.now(timezone.utc)
    stale = 0
    for issue in real_issues:
        created = datetime.fromisoformat(issue["created_at"].replace("Z", "+00:00"))
        if (now - created).days > 90:
            stale += 1

    stale_ratio = stale / len(real_issues)
    score = int(100 - (stale_ratio * 80))
    details = [
        f"{open_issues} open issue(s) total.",
        f"{stale}/{len(real_issues)} sampled issues are older than 90 days.",
    ]
    return _result("Issue Hygiene", score, details)


def check_security(client: GitHubClient, ref: RepoRef) -> CheckResult:
    root_files = client.root_files(ref)
    github_contents = client.contents(ref, ".github") or []
    github_names = [item["name"].lower() for item in github_contents if isinstance(github_contents, list)]

    details = []
    score = 0

    has_security_md = any(f.lower() == "security.md" for f in root_files)
    if has_security_md:
        score += 40
        details.append("SECURITY.md present — vulnerability disclosure policy defined.")
    else:
        details.append("No SECURITY.md — add one to define how to report vulnerabilities.")

    has_dependabot = "dependabot.yml" in github_names or "dependabot.yaml" in github_names
    if has_dependabot:
        score += 35
        details.append("dependabot.yml configured — automated dependency updates enabled.")
    else:
        details.append("No dependabot.yml — consider adding automated dependency updates.")

    has_codeowners = "codeowners" in [f.lower() for f in root_files] or "codeowners" in github_names
    if has_codeowners:
        score += 25
        details.append("CODEOWNERS file found — code review ownership defined.")
    else:
        details.append("No CODEOWNERS file.")

    return _result("Security", score, details)


def check_contributing(client: GitHubClient, ref: RepoRef) -> CheckResult:
    files = client.root_files(ref)
    contrib_file = next((f for f in files if f.lower().startswith("contributing")), None)

    if not contrib_file:
        return _result("Contributing Guide", 0, ["No CONTRIBUTING.md — makes it harder for others to contribute."], weight=0.75)

    text = client.file_text(ref, contrib_file) or ""
    details = [f"CONTRIBUTING.md found ({len(text)} chars)."]
    score = 70
    if len(text) > 500:
        score += 30
        details.append("Substantive contribution guide (>500 chars).")
    else:
        details.append("Short contribution guide — consider expanding.")

    return _result("Contributing Guide", score, details, weight=0.75)


def check_docker(client: GitHubClient, ref: RepoRef) -> CheckResult:
    files = [f.lower() for f in client.root_files(ref)]
    details = []
    score = 0

    if "dockerfile" in files:
        score += 60
        details.append("Dockerfile found.")

    if "docker-compose.yml" in files or "docker-compose.yaml" in files:
        score += 40
        details.append("docker-compose.yml found.")

    deploy_hints = ["railway.json", "heroku.yml", "render.yaml", "fly.toml", "vercel.json", "netlify.toml"]
    found_deploy = [f for f in deploy_hints if f in files]
    if found_deploy:
        score = max(score, 50)
        details.append(f"Deployment config found: {', '.join(found_deploy)}.")

    if score == 0:
        details.append("No Docker or deployment configuration found.")

    return _result("Docker/Deploy", score, details, weight=0.5)


def check_branch_protection(client: GitHubClient, ref: RepoRef) -> CheckResult:
    # Try old-style branch protection first
    protection = client.branch_protection(ref, "main") or client.branch_protection(ref, "master")

    if protection is not None:
        details = []
        score = 40

        required_reviews = protection.get("required_pull_request_reviews")
        if required_reviews:
            count = required_reviews.get("required_approving_review_count", 1)
            score += 30
            details.append(f"PR reviews required ({count} approver(s)).")
        else:
            details.append("No required PR reviews.")

        if protection.get("required_status_checks"):
            score += 20
            details.append("Required status checks configured.")
        else:
            details.append("No required status checks.")

        if protection.get("enforce_admins", {}).get("enabled"):
            score += 10
            details.append("Protection enforced for admins too.")

        return _result("Branch Protection", score, details, weight=0.75)

    # Fall back to newer rulesets API (GitHub's current UI uses rulesets)
    all_rulesets = client.rulesets(ref)
    active = [r for r in all_rulesets if isinstance(r, dict) and r.get("enforcement") == "active"]

    if not active:
        return _result("Branch Protection", 0, ["No branch protection on main/master — anyone can push directly."], weight=0.75)

    details = [f"Branch ruleset active: '{active[0].get('name', 'unnamed')}'."]
    score = 40

    full = client.ruleset(ref, active[0]["id"])
    if full:
        rule_types = {r["type"] for r in full.get("rules", [])}

        if "pull_request" in rule_types:
            pr_rule = next((r for r in full["rules"] if r["type"] == "pull_request"), {})
            count = pr_rule.get("parameters", {}).get("required_approving_review_count", 1)
            score += 30
            details.append(f"PR reviews required ({count} approver(s)).")
        else:
            details.append("No required PR reviews.")

        if "required_status_checks" in rule_types:
            score += 20
            details.append("Required status checks configured.")
        else:
            details.append("No required status checks.")

        if "deletion" in rule_types:
            score += 10
            details.append("Branch deletion restricted.")

    return _result("Branch Protection", score, details, weight=0.75)


CHECKS: list[Callable[[GitHubClient, RepoRef], CheckResult]] = [
    check_readme,
    check_ci,
    check_tests,
    check_dependencies,
    check_license,
    check_activity,
    check_issue_hygiene,
    check_security,
    check_contributing,
    check_docker,
    check_branch_protection,
]
