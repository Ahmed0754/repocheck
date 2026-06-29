"""repocheck CLI."""
from __future__ import annotations

import json
import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .github_client import GitHubClient, GitHubError, parse_repo_arg
from .report import run_report

console = Console()

GRADE_COLORS = {
    "A": "green",
    "B": "cyan",
    "C": "yellow",
    "D": "orange3",
    "F": "red",
}


def _grade_text(grade: str) -> Text:
    color = GRADE_COLORS.get(grade, "white")
    return Text(grade, style=f"bold {color}")


@click.command()
@click.argument("repo")
@click.option("--token", envvar="GITHUB_TOKEN", help="GitHub personal access token (or set GITHUB_TOKEN env var).")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON instead of a formatted report.")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed reasoning for every check.")
@click.version_option()
def main(repo: str, token: str | None, as_json: bool, verbose: bool):
    """Scan a GitHub REPO (owner/repo or URL) and print a health report card.

    \b
    Examples:
      repocheck pallets/flask
      repocheck https://github.com/psf/requests
      repocheck torvalds/linux --json
    """
    try:
        ref = parse_repo_arg(repo)
    except ValueError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)

    client = GitHubClient(token=token)

    try:
        with console.status(f"[bold blue]Scanning {ref.full_name}..."):
            report = run_report(client, ref)
    except GitHubError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)

    if as_json:
        print(json.dumps(report.to_dict(), indent=2))
        return

    _render(report, verbose=verbose)


def _render(report, verbose: bool):
    grade_color = GRADE_COLORS.get(report.overall_grade, "white")
    header = Text()
    header.append(f"{report.repo.full_name}\n", style="bold")
    header.append(f"★ {report.repo_meta.get('stargazers_count', 0)}  ", style="dim")
    header.append(f"⑂ {report.repo_meta.get('forks_count', 0)}  ", style="dim")
    header.append(f"{report.repo_meta.get('language') or 'unknown'}", style="dim")

    score_text = Text()
    score_text.append(f"{report.overall_score}/100  ", style=f"bold {grade_color}")
    score_text.append(f"({report.overall_grade})", style=f"bold {grade_color}")

    console.print(Panel(header, title="repo", expand=False))
    console.print(Panel(score_text, title="overall health score", expand=False))

    table = Table(show_header=True, header_style="bold")
    table.add_column("Check")
    table.add_column("Score", justify="right")
    table.add_column("Grade", justify="center")
    if verbose:
        table.add_column("Details")

    for check in report.checks:
        row = [check.name, str(check.score), _grade_text(check.grade)]
        if verbose:
            row.append("\n".join(f"• {d}" for d in check.details))
        table.add_row(*row)

    console.print(table)

    if not verbose:
        console.print("[dim]Run with -v for detailed reasoning behind each score.[/dim]")

    if client_rate_hint(report):
        console.print(
            "[dim]Tip: set GITHUB_TOKEN to raise your API rate limit from 60/hr to 5000/hr.[/dim]"
        )


def client_rate_hint(report) -> bool:
    import os
    return not os.environ.get("GITHUB_TOKEN")


if __name__ == "__main__":
    main()
