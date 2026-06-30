"""Thin GitHub REST API client used by all checks."""
from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

GITHUB_API = "https://api.github.com"


class GitHubError(Exception):
    pass


@dataclass
class RepoRef:
    owner: str
    name: str

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


def parse_repo_arg(arg: str) -> RepoRef:
    """Accepts 'owner/repo', a full GitHub URL, or a .git URL."""
    arg = arg.strip()

    # owner/repo shorthand
    if re.fullmatch(r"[\w.-]+/[\w.-]+", arg):
        owner, name = arg.split("/", 1)
        return RepoRef(owner, name.removesuffix(".git"))

    # full URL
    m = re.search(r"github\.com[:/]+([\w.-]+)/([\w.-]+?)(?:\.git)?/?$", arg)
    if m:
        return RepoRef(m.group(1), m.group(2))

    raise ValueError(
        f"Could not parse repo argument: {arg!r}. "
        "Use 'owner/repo' or a github.com URL."
    )


class GitHubClient:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.session = requests.Session()
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "repocheck-cli",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        self.session.headers.update(headers)
        self.rate_remaining: Optional[int] = None

    def _get(self, path: str, **kwargs) -> requests.Response:
        resp = self.session.get(f"{GITHUB_API}{path}", **kwargs)
        self.rate_remaining = resp.headers.get("X-RateLimit-Remaining")
        if resp.status_code == 404:
            raise GitHubError(f"Not found: {path}")
        if resp.status_code == 403 and self.rate_remaining == "0":
            raise GitHubError(
                "GitHub API rate limit exceeded. Set GITHUB_TOKEN env var "
                "for a higher limit (60/hr -> 5000/hr)."
            )
        resp.raise_for_status()
        return resp

    def repo(self, ref: RepoRef) -> dict[str, Any]:
        return self._get(f"/repos/{ref.full_name}").json()

    def contents(self, ref: RepoRef, path: str = "") -> Any:
        try:
            return self._get(f"/repos/{ref.full_name}/contents/{path}").json()
        except GitHubError:
            return None

    def file_text(self, ref: RepoRef, path: str) -> Optional[str]:
        data = self.contents(ref, path)
        if not data or "content" not in data:
            return None
        try:
            return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        except Exception:
            return None

    def workflows(self, ref: RepoRef) -> list[dict[str, Any]]:
        data = self.contents(ref, ".github/workflows")
        return data if isinstance(data, list) else []

    def commits(self, ref: RepoRef, per_page: int = 30) -> list[dict[str, Any]]:
        try:
            return self._get(
                f"/repos/{ref.full_name}/commits", params={"per_page": per_page}
            ).json()
        except GitHubError:
            return []

    def issues(self, ref: RepoRef, state: str = "open", per_page: int = 50) -> list[dict[str, Any]]:
        try:
            return self._get(
                f"/repos/{ref.full_name}/issues",
                params={"state": state, "per_page": per_page},
            ).json()
        except GitHubError:
            return []

    def root_files(self, ref: RepoRef) -> list[str]:
        data = self.contents(ref, "")
        if not isinstance(data, list):
            return []
        return [item["name"] for item in data if item["type"] == "file"]

    def root_dirs(self, ref: RepoRef) -> list[str]:
        data = self.contents(ref, "")
        if not isinstance(data, list):
            return []
        return [item["name"] for item in data if item["type"] == "dir"]

    def branch_protection(self, ref: RepoRef, branch: str = "main") -> Optional[dict[str, Any]]:
        try:
            return self._get(f"/repos/{ref.full_name}/branches/{branch}/protection").json()
        except GitHubError:
            return None

    def org_repos(self, org: str, per_page: int = 100) -> list[dict[str, Any]]:
        try:
            return self._get(
                f"/orgs/{org}/repos",
                params={"per_page": per_page, "type": "public", "sort": "updated"},
            ).json()
        except GitHubError:
            return []
