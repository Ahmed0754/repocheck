from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from repocheck.checks import (
    check_activity,
    check_ci,
    check_dependencies,
    check_issue_hygiene,
    check_license,
    check_readme,
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
