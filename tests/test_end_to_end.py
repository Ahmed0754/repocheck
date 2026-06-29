"""End-to-end test: mocks GitHub's HTTP responses and runs a full report."""
import json
from unittest.mock import MagicMock, patch

from repocheck.github_client import GitHubClient, parse_repo_arg
from repocheck.report import run_report

FAKE_REPO_META = {
    "full_name": "acme/widget",
    "stargazers_count": 1234,
    "forks_count": 56,
    "language": "Python",
    "license": {"name": "MIT License", "spdx_id": "MIT"},
    "open_issues_count": 2,
}

FAKE_README = (
    "# Widget\n\nA delightful widget library.\n\n"
    "## Installation\n```\npip install widget\n```\n\n"
    "## Usage\n```python\nimport widget\nwidget.run()\n```\n\n"
    "![build](https://img.shields.io/badge/build-passing-green)\n"
) * 3  # pad past the 300-char threshold


def _fake_response(json_data, status=200, headers=None):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data
    resp.headers = headers or {"X-RateLimit-Remaining": "59"}
    resp.raise_for_status = MagicMock()
    return resp


def fake_get(url, params=None, **kwargs):
    if url.endswith("/repos/acme/widget"):
        return _fake_response(FAKE_REPO_META)
    if "/contents/" in url and url.endswith("/contents/"):
        return _fake_response([
            {"name": "README.md", "type": "file"},
            {"name": "requirements.txt", "type": "file"},
            {"name": "tests", "type": "dir"},
            {"name": "src", "type": "dir"},
        ])
    if url.endswith("/contents/README.md"):
        import base64
        return _fake_response({"content": base64.b64encode(FAKE_README.encode()).decode()})
    if url.endswith("/contents/requirements.txt"):
        import base64
        return _fake_response({"content": base64.b64encode(b"flask==2.3.0\nrequests==2.31.0\n").decode()})
    if url.endswith("/contents/.github/workflows"):
        return _fake_response([{"name": "ci.yml", "type": "file"}])
    if url.endswith("/commits"):
        return _fake_response([
            {
                "commit": {
                    "committer": {"date": "2026-06-15T12:00:00Z"},
                    "message": "Add retry logic for transient network failures",
                }
            }
        ])
    if url.endswith("/issues"):
        return _fake_response([])
    # default: not found
    return _fake_response({"message": "Not Found"}, status=404)


def test_end_to_end_report_with_mocked_api():
    ref = parse_repo_arg("acme/widget")
    client = GitHubClient(token="fake-token")

    with patch.object(client.session, "get", side_effect=fake_get):
        report = run_report(client, ref)

    assert report.repo.full_name == "acme/widget"
    assert 0 <= report.overall_score <= 100
    assert report.overall_grade in ("A", "B", "C", "D", "F")
    assert len(report.checks) == 7

    as_dict = report.to_dict()
    # Confirm it's JSON-serializable end to end, like --json mode produces
    serialized = json.dumps(as_dict)
    assert "acme/widget" in serialized

    # Sanity check a couple of specific checks given our fake data
    names = {c.name: c for c in report.checks}
    assert names["License"].score == 100
    assert names["CI/CD"].score >= 70
    assert names["Issue Hygiene"].score == 90  # count=2 but issues list empty -> "possibly all PRs" branch
