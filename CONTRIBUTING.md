# Contributing

Thank you for improving this project. Short guidelines below.

## Setup

1. Install [uv](https://docs.astral.sh/uv/).
2. Run `uv sync --all-extras`.
3. Start PostgreSQL locally (see the Development section in `README.md`). The test suite uses the URL defined in `tests/conftest.py`.

## Before you open a pull request

- Run `uv run ruff check .` and `uv run ruff format .`.
- Run `uv run pytest` with PostgreSQL available.
- Keep changes focused on one concern per PR when possible.

## Releases

PyPI uploads run from GitHub Actions when a SemVer tag is pushed (see `README.md`, section **Publishing to PyPI**). Configure PyPI **trusted publishing** and the GitHub **`pypi`** environment before the first release.

## Reporting issues

Use the issue tracker linked in `pyproject.toml` under `[project.urls]`. If that URL is outdated after a repository move, open a discussion in the new home of the project.

## Security

Please do not report security vulnerabilities in public issues. See [SECURITY.md](SECURITY.md).
