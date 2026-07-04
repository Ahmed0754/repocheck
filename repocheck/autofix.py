"""Auto-fix: create missing files locally based on check results."""
from __future__ import annotations

from pathlib import Path

from .checks import CheckResult

SECURITY_MD = """\
# Security Policy

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Email the maintainer directly with:
- A description of the vulnerability
- Steps to reproduce it
- Any potential impact

You can expect a response within 48 hours.
"""

DEPENDABOT_YML = """\
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
"""

CONTRIBUTING_MD = """\
# Contributing

## Running locally

```bash
git clone <repo-url>
cd <repo-name>
pip install -e "."
```

## Running tests

```bash
pip install pytest
pytest tests/
```

## Opening a pull request

- Keep PRs focused — one feature or fix per PR
- Make sure all tests pass before submitting
"""

CI_YML = """\
name: CI

on:
  push:
    branches: ["main"]
  pull_request:
    branches: ["main"]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e "." pytest
      - run: pytest tests/
"""

PYTEST_INI = """\
[pytest]
testpaths = tests
"""

LICENSE_MIT = """\
MIT License

Copyright (c) {year} {author}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


def _write(path: Path, content: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return True


def apply_fixes(checks: list[CheckResult]) -> list[str]:
    """Create missing files based on check results. Returns list of created paths."""
    created = []
    check_map = {c.name: c for c in checks}

    def detail_says_missing(name: str, keyword: str) -> bool:
        c = check_map.get(name)
        if not c:
            return False
        return any(keyword.lower() in d.lower() for d in c.details)

    if detail_says_missing("Security", "No SECURITY.md"):
        if _write(Path("SECURITY.md"), SECURITY_MD):
            created.append("SECURITY.md")

    if detail_says_missing("Security", "No dependabot"):
        if _write(Path(".github/dependabot.yml"), DEPENDABOT_YML):
            created.append(".github/dependabot.yml")

    if detail_says_missing("Contributing Guide", "No CONTRIBUTING"):
        if _write(Path("CONTRIBUTING.md"), CONTRIBUTING_MD):
            created.append("CONTRIBUTING.md")

    if detail_says_missing("CI/CD", "No CI/CD"):
        if _write(Path(".github/workflows/ci.yml"), CI_YML):
            created.append(".github/workflows/ci.yml")

    if detail_says_missing("Test Presence", "No conventional test"):
        Path("tests").mkdir(exist_ok=True)
        created.append("tests/")
        if _write(Path("pytest.ini"), PYTEST_INI):
            created.append("pytest.ini")

    if detail_says_missing("License", "No license"):
        import datetime
        content = LICENSE_MIT.format(year=datetime.date.today().year, author="The Author")
        if _write(Path("LICENSE"), content):
            created.append("LICENSE")

    return created
