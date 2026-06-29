"""Aggregates individual CheckResults into an overall report."""
from __future__ import annotations

from dataclasses import dataclass, field

from .checks import CHECKS, CheckResult
from .github_client import GitHubClient, RepoRef


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
