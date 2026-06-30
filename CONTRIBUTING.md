# Contributing to repocheck

Thanks for your interest in contributing!

## Running locally

```bash
git clone https://github.com/Ahmed0754/repocheck
cd repocheck
pip install -e "."
pip install pytest
```

Set a GitHub token for higher API rate limits:

```bash
export GITHUB_TOKEN=your_token_here
```

Run the tool:

```bash
repocheck pallets/flask
```

## Running tests

```bash
pytest tests/
```

All 33 tests should pass. Add tests for any new checks you write.

## Adding a new check

1. Write a function `check_something(client, ref) -> CheckResult` in `repocheck/checks.py`
2. Add fix hints for it in the `FIX_HINTS` dict in `repocheck/report.py`
3. Append it to the `CHECKS` list at the bottom of `checks.py`
4. Add tests in `tests/test_checks.py`

## Opening a pull request

- Keep PRs focused — one feature or fix per PR
- Make sure all tests pass before submitting
- Update the version in `pyproject.toml` if adding a new feature
