"""Aggregates individual CheckResults into an overall report."""
from __future__ import annotations

from dataclasses import dataclass

from .checks import CHECKS, CheckResult
from .github_client import GitHubClient, RepoRef


FIX_HINTS: dict[str, list[str]] = {
    "README Quality": [
        "Expand your README to at least 300 characters.",
        "Add an ## Installation section with pip/npm install instructions.",
        "Add a ## Usage section with a code example.",
        "Add a PyPI/CI badge using shields.io.",
    ],
    "CI/CD": [
        "Create .github/workflows/ci.yml to run your tests on every push.",
    ],
    "Test Presence": [
        "Create a tests/ directory with at least one test file.",
        "Add a pytest.ini file at the repo root.",
    ],
    "Dependency Hygiene": [
        "Pin all versions in requirements.txt using == instead of >=.",
        "Add a lockfile (package-lock.json / yarn.lock) if using Node.",
    ],
    "License": [
        "Add a LICENSE file (MIT is a common permissive choice).",
    ],
    "Security": [
        "Add a SECURITY.md explaining how to report vulnerabilities.",
        "Add .github/dependabot.yml to automate dependency updates.",
    ],
    "Contributing Guide": [
        "Add a CONTRIBUTING.md with steps for running locally and opening PRs.",
    ],
    "Docker/Deploy": [
        "Add a Dockerfile if your project is a deployable app.",
        "Add a docker-compose.yml for local dev environment setup.",
    ],
    "Branch Protection": [
        "Enable branch protection on main: require PR reviews before merging.",
        "Add required status checks so CI must pass before merging.",
    ],
}


@dataclass
class Report:
    repo: RepoRef
    checks: list[CheckResult]
    overall_score: int
    overall_grade: str
    repo_meta: dict

    def to_dict(self) -> dict:
        return {
            "repo": self.repo.full_name,
            "overall_score": self.overall_score,
            "overall_grade": self.overall_grade,
            "stars": self.repo_meta.get("stargazers_count"),
            "forks": self.repo_meta.get("forks_count"),
            "language": self.repo_meta.get("language"),
            "checks": [
                {
                    "name": c.name,
                    "score": c.score,
                    "grade": c.grade,
                    "details": c.details,
                }
                for c in self.checks
            ],
        }

    def to_markdown(self) -> str:
        lines = [
            f"# repocheck: {self.repo.full_name}",
            "",
            f"**Overall: {self.overall_score}/100 ({self.overall_grade})**  ",
            f"★ {self.repo_meta.get('stargazers_count', 0)}  "
            f"⑂ {self.repo_meta.get('forks_count', 0)}  "
            f"{self.repo_meta.get('language') or 'unknown'}",
            "",
            "| Check | Score | Grade |",
            "|---|---|---|",
        ]
        for c in self.checks:
            lines.append(f"| {c.name} | {c.score} | {c.grade} |")
        lines.append("")
        lines.append("## Details")
        for c in self.checks:
            lines.append(f"\n### {c.name} — {c.score}/100 ({c.grade})")
            for d in c.details:
                lines.append(f"- {d}")
        return "\n".join(lines)

    def fix_suggestions(self) -> list[tuple[str, list[str]]]:
        suggestions = []
        for c in sorted(self.checks, key=lambda x: x.score):
            if c.score >= 90:
                continue
            hints = FIX_HINTS.get(c.name, [])
            if hints:
                suggestions.append((c.name, hints))
        return suggestions


def run_report(client: GitHubClient, ref: RepoRef) -> Report:
    repo_meta = client.repo(ref)
    results = [check_fn(client, ref) for check_fn in CHECKS]

    total_weight = sum(r.weight for r in results)
    weighted_sum = sum(r.score * r.weight for r in results)
    overall_score = round(weighted_sum / total_weight) if total_weight else 0
    overall_grade = CheckResult.grade_for(overall_score)

    return Report(
        repo=ref,
        checks=results,
        overall_score=overall_score,
        overall_grade=overall_grade,
        repo_meta=repo_meta,
    )
