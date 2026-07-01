"""repocheck CLI."""
from __future__ import annotations

import json
import os
import sys
import time

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .github_client import GitHubClient, GitHubError, RepoRef, parse_repo_arg
from .history import get_history, get_last_run, save_run
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


def _render(report, verbose: bool, last_run: dict | None = None) -> None:
    grade_color = GRADE_COLORS.get(report.overall_grade, "white")
    header = Text()
    header.append(f"{report.repo.full_name}\n", style="bold")
    header.append(f"★ {report.repo_meta.get('stargazers_count', 0)}  ", style="dim")
    header.append(f"⑂ {report.repo_meta.get('forks_count', 0)}  ", style="dim")
    header.append(f"{report.repo_meta.get('language') or 'unknown'}", style="dim")

    score_text = Text()
    score_text.append(f"{report.overall_score}/100  ", style=f"bold {grade_color}")
    score_text.append(f"({report.overall_grade})", style=f"bold {grade_color}")

    if last_run:
        diff = report.overall_score - last_run["score"]
        sign = "+" if diff >= 0 else ""
        color = "green" if diff > 0 else ("red" if diff < 0 else "dim")
        score_text.append(f"  {sign}{diff} since last run", style=color)

    console.print(Panel(header, title="repo", expand=False))
    console.print(Panel(score_text, title="overall health score", expand=False))

    table = Table(show_header=True, header_style="bold")
    table.add_column("Check")
    table.add_column("Score", justify="right")
    table.add_column("Grade", justify="center")
    if verbose:
        table.add_column("Details")

    for check in report.checks:
        score_str = str(check.score)
        if last_run and check.name in last_run.get("checks", {}):
            prev = last_run["checks"][check.name]
            diff = check.score - prev
            if diff != 0:
                sign = "+" if diff > 0 else ""
                color = "green" if diff > 0 else "red"
                score_str = f"{check.score} [{color}]({sign}{diff})[/{color}]"

        row = [check.name, score_str, _grade_text(check.grade)]
        if verbose:
            row.append("\n".join(f"• {d}" for d in check.details))
        table.add_row(*row)

    console.print(table)

    if not verbose:
        console.print("[dim]Run with -v for detailed reasoning behind each score.[/dim]")

    if not os.environ.get("GITHUB_TOKEN"):
        console.print(
            "[dim]Tip: set GITHUB_TOKEN to raise your API rate limit from 60/hr to 5000/hr.[/dim]"
        )


def _render_fix(report) -> None:
    suggestions = report.fix_suggestions()
    if not suggestions:
        console.print("[green bold]Nothing to fix — all checks are at 90+![/green bold]")
        return

    console.print(f"\n[bold]Fix checklist for {report.repo.full_name}[/bold]\n")
    for check_name, hints in suggestions:
        check = next(c for c in report.checks if c.name == check_name)
        color = GRADE_COLORS.get(check.grade, "white")
        console.print(f"[{color}]{check_name} ({check.score}/100)[/{color}]")
        for hint in hints:
            console.print(f"  [ ] {hint}")
        console.print()


def _render_compare(report_a, report_b) -> None:
    console.print(f"\n[bold]Comparing repos[/bold]\n")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Check")
    table.add_column(report_a.repo.full_name, justify="right")
    table.add_column(report_b.repo.full_name, justify="right")

    all_checks = {c.name for c in report_a.checks} | {c.name for c in report_b.checks}
    map_a = {c.name: c for c in report_a.checks}
    map_b = {c.name: c for c in report_b.checks}

    for name in sorted(all_checks):
        ca = map_a.get(name)
        cb = map_b.get(name)
        score_a = _grade_text(ca.grade) if ca else Text("—", style="dim")
        score_b = _grade_text(cb.grade) if cb else Text("—", style="dim")
        if ca and cb:
            score_a = Text(f"{ca.score} ({ca.grade})", style=f"bold {GRADE_COLORS.get(ca.grade, 'white')}")
            score_b = Text(f"{cb.score} ({cb.grade})", style=f"bold {GRADE_COLORS.get(cb.grade, 'white')}")
        table.add_row(name, score_a, score_b)

    # Overall row
    overall_a = Text(f"{report_a.overall_score} ({report_a.overall_grade})", style=f"bold {GRADE_COLORS.get(report_a.overall_grade, 'white')}")
    overall_b = Text(f"{report_b.overall_score} ({report_b.overall_grade})", style=f"bold {GRADE_COLORS.get(report_b.overall_grade, 'white')}")
    table.add_section()
    table.add_row("OVERALL", overall_a, overall_b)

    console.print(table)


_SPARK = "▁▂▃▄▅▆▇█"


def _sparkline(scores: list[int]) -> str:
    if not scores:
        return ""
    lo, hi = min(scores), max(scores)
    span = hi - lo or 1
    return "".join(_SPARK[round((s - lo) / span * (len(_SPARK) - 1))] for s in scores)


def _render_history(repo: str) -> None:
    runs = get_history(repo)
    if not runs:
        console.print(f"[dim]No history found for {repo}. Run a scan first.[/dim]")
        return

    scores = [r["score"] for r in runs]
    spark = _sparkline(scores)
    console.print(f"\n[bold]Trend[/bold]  {spark}  [dim]{scores[0]} → {scores[-1]}[/dim]\n")

    table = Table(show_header=True, header_style="bold", title=f"Score history: {repo}")
    table.add_column("Date")
    table.add_column("Score", justify="right")
    table.add_column("Grade", justify="center")
    table.add_column("Change", justify="right")

    for i, run in enumerate(runs):
        ts = run["timestamp"][:16].replace("T", " ")
        score = run["score"]
        grade = next((g for threshold, g in [(90,"A"),(80,"B"),(70,"C"),(60,"D")] if score >= threshold), "F")
        color = GRADE_COLORS.get(grade, "white")
        if i == 0:
            change = Text("—", style="dim")
        else:
            diff = score - runs[i - 1]["score"]
            sign = "+" if diff >= 0 else ""
            change = Text(f"{sign}{diff}", style="green" if diff > 0 else ("red" if diff < 0 else "dim"))
        table.add_row(ts, str(score), Text(grade, style=f"bold {color}"), change)

    console.print(table)


def _render_org(results: list[tuple[RepoRef, int, str]]) -> None:
    table = Table(show_header=True, header_style="bold", title="Org Health Report")
    table.add_column("Repo")
    table.add_column("Score", justify="right")
    table.add_column("Grade", justify="center")

    for ref, score, grade in results:
        color = GRADE_COLORS.get(grade, "white")
        table.add_row(ref.name, str(score), Text(grade, style=f"bold {color}"))

    console.print(table)
    avg = round(sum(s for _, s, _ in results) / len(results)) if results else 0
    console.print(f"\n[bold]Org average: {avg}/100[/bold]")


@click.command()
@click.argument("repo", required=False, default=None)
@click.option("--token", envvar="GITHUB_TOKEN", help="GitHub personal access token.")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON.")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed reasoning for every check.")
@click.option("--min-score", type=int, default=None, help="Exit with code 1 if score is below this threshold.")
@click.option("--compare", default=None, metavar="REPO2", help="Compare against a second repo.")
@click.option("--org", default=None, metavar="ORG", help="Scan all public repos in a GitHub org.")
@click.option("--fix", "show_fix", is_flag=True, help="Print a checklist of improvements.")
@click.option("--md", "as_markdown", is_flag=True, help="Output a markdown report.")
@click.option("--history", "show_history", is_flag=True, help="Show score trend from past runs.")
@click.option("--watch", type=int, default=None, metavar="SECONDS", help="Re-scan every N seconds until Ctrl+C.")
@click.option("--limit", type=int, default=20, show_default=True, help="Max repos to scan with --org.")
@click.version_option()
def main(repo, token, as_json, verbose, min_score, compare, org, show_fix, as_markdown, show_history, watch, limit):
    """Scan a GitHub REPO (owner/repo or URL) and print a health report card.

    \b
    Examples:
      repocheck pallets/flask
      repocheck pallets/flask --compare psf/requests
      repocheck pallets/flask --fix
      repocheck pallets/flask --md > report.md
      repocheck pallets/flask --min-score 80
      repocheck --org pallets
    """
    if not repo and not org:
        raise click.UsageError("Provide a REPO argument or use --org ORG.")

    client = GitHubClient(token=token)

    # --org mode: scan all public repos in an org
    if org:
        with console.status(f"[bold blue]Fetching repos for {org}..."):
            repos = client.org_repos(org, per_page=min(limit, 100))

        if not repos:
            console.print(f"[red]No public repos found for org: {org}[/red]")
            sys.exit(1)

        repos = repos[:limit]
        results = []
        for r in repos:
            ref = RepoRef(r["owner"]["login"], r["name"])
            try:
                with console.status(f"Scanning {ref.full_name}..."):
                    report = run_report(client, ref)
                results.append((ref, report.overall_score, report.overall_grade))
            except GitHubError:
                pass

        results.sort(key=lambda x: x[1], reverse=True)
        _render_org(results)
        return

    # Normal single-repo mode
    try:
        ref = parse_repo_arg(repo)
    except ValueError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)

    if show_history:
        _render_history(ref.full_name)
        return

    try:
        with console.status(f"[bold blue]Scanning {ref.full_name}..."):
            report = run_report(client, ref)
    except GitHubError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)

    # --compare mode
    if compare:
        try:
            ref2 = parse_repo_arg(compare)
            with console.status(f"[bold blue]Scanning {ref2.full_name}..."):
                report2 = run_report(client, ref2)
            _render_compare(report, report2)
        except (ValueError, GitHubError) as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            sys.exit(1)
        return

    try:
        while True:
            last_run = get_last_run(ref.full_name)
            save_run(ref.full_name, report.overall_score, [{"name": c.name, "score": c.score} for c in report.checks])

            if as_json:
                print(json.dumps(report.to_dict(), indent=2))
            elif as_markdown:
                print(report.to_markdown())
            else:
                _render(report, verbose=verbose, last_run=last_run)
                if show_fix:
                    _render_fix(report)

            if min_score is not None and report.overall_score < min_score:
                console.print(f"\n[red bold]Score {report.overall_score} is below --min-score {min_score}. Exiting with code 1.[/red bold]")
                sys.exit(1)

            if not watch:
                break

            console.print(f"\n[dim]Refreshing in {watch}s... Ctrl+C to stop.[/dim]")
            time.sleep(watch)
            console.clear()
            with console.status(f"[bold blue]Scanning {ref.full_name}..."):
                report = run_report(client, ref)
    except KeyboardInterrupt:
        console.print("\n[dim]Watch stopped.[/dim]")


if __name__ == "__main__":
    main()
