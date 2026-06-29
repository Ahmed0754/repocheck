import pytest

from repocheck.github_client import parse_repo_arg, RepoRef


@pytest.mark.parametrize(
    "arg,expected_owner,expected_name",
    [
        ("pallets/flask", "pallets", "flask"),
        ("https://github.com/psf/requests", "psf", "requests"),
        ("https://github.com/psf/requests.git", "psf", "requests"),
        ("git@github.com:torvalds/linux.git", "torvalds", "linux"),
        ("github.com/Ahmed0754/repocheck", "Ahmed0754", "repocheck"),
        ("github.com/Ahmed0754/repocheck/", "Ahmed0754", "repocheck"),
    ],
)
def test_parse_repo_arg_valid(arg, expected_owner, expected_name):
    ref = parse_repo_arg(arg)
    assert ref.owner == expected_owner
    assert ref.name == expected_name


def test_parse_repo_arg_full_name():
    ref = parse_repo_arg("octocat/Hello-World")
    assert ref.full_name == "octocat/Hello-World"


@pytest.mark.parametrize("bad_arg", ["", "not a repo", "just-a-word", "http://example.com/foo/bar"])
def test_parse_repo_arg_invalid(bad_arg):
    with pytest.raises(ValueError):
        parse_repo_arg(bad_arg)
