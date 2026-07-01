from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from repocheck.checks import (
    check_activity,
    check_branch_protection,
    check_ci,
    check_contributing,
    check_dependencies,
    check_docker,
    check_issue_hygiene,
    check_license,
    check_readme,
    check_security,
    check_tests,
)
from repocheck.github_client import RepoRef

REF = RepoRef("acme", "widget")


def make_client(**overrides):
    """Build a MagicMock GitHubClient with sane defaults, override what you need."""
    client = MagicMock()
    client.root_files.return_value = overrides.get("root_files", [])
    client.root_dirs.return_value = overrides.get("root_dirs", [])
    client.file_text.return_value = overrides.get("file_text", None)
    client.workflows.return_value = overrides.get("workflows", [])
    client.commits.return_value = overrides.get("commits", [])
    client.issues.return_value = overrides.get("issues", [])
    client.repo.return_value = overrides.get("repo", {})
    client.contents.return_value = overrides.get("contents", [])
    client.branch_protection.return_value = overrides.get("branch_protection", None)
    return client


# ---------------------------------------------------------------------------
# README
# ---------------------------------------------------------------------------

def test_readme_missing():
    client = make_client(root_files=[])
    result = check_readme(client, REF)
    assert result.score == 0
    assert result.grade == "F"


def test_readme_full_quality():
    text = (
        "# Widget\n\n" + ("x" * 400) + "\n\n## Installation\npip install widget\n\n"
        "## Usage\n```python\nimport widget\n```\n\n![CI](https://img.shields.io/badge/ci-passing-green)"
    )
    client = make_client(root_files=["README.md"], file_text=text)
    result = check_readme(client, REF)
    assert result.score >= 90
    assert result.grade in ("A", "B")


def test_readme_present_but_thin():
    client = make_client(root_files=["README.md"], file_text="just a title")
    result = check_readme(client, REF)
    assert 0 < result.score < 60


# ---------------------------------------------------------------------------
# CI
# ---------------------------------------------------------------------------

def test_ci_github_actions_present():
    client = make_client(workflows=[{"name": "ci.yml", "type": "file"}])
    result = check_ci(client, REF)
    assert result.score >= 70


def test_ci_none():
    client = make_client(workflows=[], root_files=["README.md"])
    result = check_ci(client, REF)
    assert result.score == 0
    assert result.grade == "F"


def test_ci_legacy_travis():
    client = make_client(workflows=[], root_files=[".travis.yml"])
    result = check_ci(client, REF)
    assert 0 < result.score < 90


# ---------------------------------------------------------------------------
# Tests presence
# ---------------------------------------------------------------------------

def test_tests_dir_present():
    client = make_client(root_dirs=["tests"], root_files=[])
    result = check_tests(client, REF)
    assert result.score >= 60


def test_tests_absent():
    client = make_client(root_dirs=["src"], root_files=["main.py"])
    result = check_tests(client, REF)
    assert result.score == 0


def test_tests_config_only():
    client = make_client(root_dirs=[], root_files=["pytest.ini"])
    result = check_tests(client, REF)
    assert result.score == 25


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def test_dependencies_pinned_requirements():
    text = "flask==2.3.0\nrequests==2.31.0\nclick==8.1.7\n"
    client = make_client(root_files=["requirements.txt"], file_text=text)
    result = check_dependencies(client, REF)
    assert result.score >= 80


def test_dependencies_unpinned_requirements():
    text = "flask\nrequests\nclick\n"
    client = make_client(root_files=["requirements.txt"], file_text=text)
    result = check_dependencies(client, REF)
    assert result.score == 70  # baseline only, no pin bonus


def test_dependencies_none_found():
    client = make_client(root_files=["README.md"])
    result = check_dependencies(client, REF)
    assert result.score == 50  # neutral, not penalized


# ---------------------------------------------------------------------------
# License
# ---------------------------------------------------------------------------

def test_license_detected_by_api():
    client = make_client(repo={"license": {"name": "MIT License", "spdx_id": "MIT"}})
    result = check_license(client, REF)
    assert result.score == 100


def test_license_file_only():
    client = make_client(repo={"license": None}, root_files=["LICENSE"])
    result = check_license(client, REF)
    assert result.score == 80


def test_license_missing():
    client = make_client(repo={"license": None}, root_files=["README.md"])
    result = check_license(client, REF)
    assert result.score == 0


# ---------------------------------------------------------------------------
# Activity
# ---------------------------------------------------------------------------

def _commit(days_ago: int, message: str):
    date = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")
    return {"commit": {"committer": {"date": date}, "message": message}}


def test_activity_recent_and_descriptive():
    commits = [_commit(1, "Add retry logic to API client for transient failures")]
    client = make_client(commits=commits)
    result = check_activity(client, REF)
    assert result.score >= 80


def test_activity_stale_repo():
    commits = [_commit(500, "fix")]
    client = make_client(commits=commits)
    result = check_activity(client, REF)
    assert result.score < 50


def test_activity_no_commits():
    client = make_client(commits=[])
    result = check_activity(client, REF)
    assert result.score == 0


# ---------------------------------------------------------------------------
# Issue hygiene
# ---------------------------------------------------------------------------

def test_issue_hygiene_zero_open():
    client = make_client(repo={"open_issues_count": 0})
    result = check_issue_hygiene(client, REF)
    assert result.score == 100


def test_issue_hygiene_all_fresh():
    fresh = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    issues = [{"created_at": fresh} for _ in range(5)]
    client = make_client(repo={"open_issues_count": 5}, issues=issues)
    result = check_issue_hygiene(client, REF)
    assert result.score == 100


def test_issue_hygiene_all_stale():
    old = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat().replace("+00:00", "Z")
    issues = [{"created_at": old} for _ in range(5)]
    client = make_client(repo={"open_issues_count": 5}, issues=issues)
    result = check_issue_hygiene(client, REF)
    assert result.score == 20


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

def test_security_all_present():
    client = make_client(
        root_files=["SECURITY.md", "CODEOWNERS"],
        contents=[{"name": "dependabot.yml"}, {"name": "workflows", "type": "dir"}],
    )
    result = check_security(client, REF)
    assert result.score == 100


def test_security_nothing():
    client = make_client(root_files=[], contents=[])
    result = check_security(client, REF)
    assert result.score == 0
    assert result.grade == "F"


def test_security_md_only():
    client = make_client(root_files=["SECURITY.md"], contents=[])
    result = check_security(client, REF)
    assert result.score == 40


def test_security_dependabot_only():
    client = make_client(root_files=[], contents=[{"name": "dependabot.yml"}])
    result = check_security(client, REF)
    assert result.score == 35


# ---------------------------------------------------------------------------
# Contributing
# ---------------------------------------------------------------------------

def test_contributing_missing():
    client = make_client(root_files=[])
    result = check_contributing(client, REF)
    assert result.score == 0
    assert result.grade == "F"


def test_contributing_short():
    client = make_client(root_files=["CONTRIBUTING.md"], file_text="Short guide.")
    result = check_contributing(client, REF)
    assert result.score == 70


def test_contributing_full():
    long_text = "How to contribute.\n\n" + ("x" * 600)
    client = make_client(root_files=["CONTRIBUTING.md"], file_text=long_text)
    result = check_contributing(client, REF)
    assert result.score == 100


# ---------------------------------------------------------------------------
# Docker / Deploy
# ---------------------------------------------------------------------------

def test_docker_nothing():
    client = make_client(root_files=["README.md"])
    result = check_docker(client, REF)
    assert result.score == 0


def test_docker_dockerfile_only():
    client = make_client(root_files=["Dockerfile"])
    result = check_docker(client, REF)
    assert result.score == 60


def test_docker_both():
    client = make_client(root_files=["Dockerfile", "docker-compose.yml"])
    result = check_docker(client, REF)
    assert result.score == 100


def test_docker_deploy_config():
    client = make_client(root_files=["fly.toml"])
    result = check_docker(client, REF)
    assert result.score == 50


# ---------------------------------------------------------------------------
# Branch Protection
# ---------------------------------------------------------------------------

def test_branch_protection_none():
    client = make_client(branch_protection=None)
    result = check_branch_protection(client, REF)
    assert result.score == 0
    assert result.grade == "F"


def test_branch_protection_basic():
    client = make_client(branch_protection={})
    result = check_branch_protection(client, REF)
    assert result.score == 40


def test_branch_protection_with_reviews():
    protection = {"required_pull_request_reviews": {"required_approving_review_count": 1}}
    client = make_client(branch_protection=protection)
    result = check_branch_protection(client, REF)
    assert result.score == 70


def test_branch_protection_full():
    protection = {
        "required_pull_request_reviews": {"required_approving_review_count": 2},
        "required_status_checks": {"strict": True, "contexts": ["ci"]},
        "enforce_admins": {"enabled": True},
    }
    client = make_client(branch_protection=protection)
    result = check_branch_protection(client, REF)
    assert result.score == 100
