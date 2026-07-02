"""Aggregates individual CheckResults into an overall report."""
from __future__ import annotations

from dataclasses import dataclass

from .checks import CHECKS, CheckResult
from .github_client import GitHubClient, RepoRef


_FIX_SIGNALS = ("No ", "consider", "appears inactive", "low-effort", "Short ")


def _is_actionable(detail: str) -> bool:
    return any(signal in detail for signal in _FIX_SIGNALS)


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
            hints = [d for d in c.details if _is_actionable(d)]
            if hints:
                suggestions.append((c.name, hints))
        return suggestions


def run_report(client: GitHubClient, ref: RepoRef, config: dict | None = None) -> Report:
    config = config or {}
    skip = {s.lower() for s in config.get("skip", [])}
    custom_weights = {k.lower(): v for k, v in config.get("weights", {}).items()}

    repo_meta = client.repo(ref)
    results = []
    for check_fn in CHECKS:
        result = check_fn(client, ref)
        if result.name.lower() in skip:
            continue
        if result.name.lower() in custom_weights:
            result.weight = custom_weights[result.name.lower()]
        results.append(result)

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
