# approck-sqlalchemy-utils

[![CI](https://github.com/adalekin/approck-sqlalchemy-utils/actions/workflows/ci.yml/badge.svg)](https://github.com/adalekin/approck-sqlalchemy-utils/actions/workflows/ci.yml)

Small helpers for **SQLAlchemy 2.x**: configure async + sync database access in one step, plug a stable FastAPI dependency, and optionally reuse a compact `Base`, column types, timestamps mixin, and Alembic utilities. **Use only the pieces you need** — many projects start with sessions and keep their own declarative base.

## Requirements

- Python 3.10+
- Runtime: SQLAlchemy 2.x, Alembic, `cryptography` (for encrypted column types)

Optional extras:

- `postgres` — `psycopg2-binary` and `asyncpg` for PostgreSQL sync/async drivers
- `dev` — pytest, ruff, mypy, pre-commit

## Installation

```bash
uv add approck-sqlalchemy-utils
```

Or with pip:

```bash
pip install approck-sqlalchemy-utils
```

PostgreSQL (async + sync drivers for this library’s session helpers):

```bash
uv add "approck-sqlalchemy-utils[postgres]"
```

## Getting started

### 1. Install the package

See [Installation](#installation). For Postgres async URLs you typically want the `postgres` extra.

### 2. Call `session.init()` once when the app starts

Pass your **async** URL (`postgresql+asyncpg://…`). The library builds the async engine and a matching **sync** engine (same URL with `+asyncpg` removed for `psycopg2`). Pool and session defaults are set for you (`pool_pre_ping`, `autoflush=False`, `expire_on_commit=False`).

Call `init` from FastAPI `lifespan`, a factory, `main` before workers start, test `conftest`, etc. — wherever you already bootstrap configuration.

```python
import os

import approck_sqlalchemy_utils.session as db

db.init(os.environ["DATABASE_URL"], pool_pre_ping=True)
```

FastAPI example with `lifespan`:

```python
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

import approck_sqlalchemy_utils.session as db


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init(os.environ["DATABASE_URL"], pool_pre_ping=True)
    yield


app = FastAPI(lifespan=lifespan)
```

### 3. Use `get_session` from `mocks` in route handlers

Import **`get_session` from `approck_sqlalchemy_utils.mocks`** (not from `session`) so the symbol FastAPI’s `Depends` uses is the same one `init()` rebinds internally.

```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from approck_sqlalchemy_utils.mocks import get_session


@app.get("/items")
async def list_items(session: AsyncSession = Depends(get_session)):
    ...
```

### What to read next

| Goal | Section |
|------|---------|
| Async `async with` session (scripts, workers, pytest-asyncio) | [Sessions → `context_session`](#sessions) |
| Sync `with` session (`create_all`, CLI, blocking code) | [Sessions → `current_session`](#sessions) |
| Optional `Base`, encrypted fields, timestamps | [ORM example](#orm-example) and [What is included](#what-is-included) |
| Alembic numeric revisions, JSON/list types, etc. | [What is included](#what-is-included) |

## What is included

| Area | Module | Purpose |
|------|--------|---------|
| ORM base | `approck_sqlalchemy_utils.model` | `Base` with `__tablename__` from class name (snake_case) and integer `id` primary key |
| Sessions | `approck_sqlalchemy_utils.session` | `init()`: dual async/sync engines; routes use `get_session` from `mocks` with `Depends(get_session)` |
| Timestamps | `approck_sqlalchemy_utils.mixins.auto_now` | `MixinWithAutoNow` — timezone-aware `created_at` / `updated_at` with server defaults |
| JSON column | `approck_sqlalchemy_utils.types.json` | `JSONType` — PostgreSQL `json` where available, otherwise text + JSON encode/decode |
| List in one column | `approck_sqlalchemy_utils.types.scalar_list` | `ScalarListType` — Python list ↔ delimiter-separated text |
| Encrypted text | `approck_sqlalchemy_utils.types.encrypted.encrypted_type` | `StringEncryptedType` and AES / AES-GCM / Fernet-style engines |
| Sorting helper | `approck_sqlalchemy_utils.parsers.order_by` | `parse()` — turn `["column:asc", ...]` into SQLAlchemy `text()` fragments |
| Alembic | `approck_sqlalchemy_utils.alembic.humanreadable` | `process_revision_directives` for zero-padded numeric revision ids (`0001`, `0002`, …) |

## ORM example

Optional — use your own `DeclarativeBase` if you prefer. This shows this package’s `Base`, encrypted column, and auto timestamps:

```python
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from approck_sqlalchemy_utils.mixins.auto_now import MixinWithAutoNow
from approck_sqlalchemy_utils.model import Base
from approck_sqlalchemy_utils.types.encrypted.encrypted_type import StringEncryptedType

SECRET = "your-app-secret"  # use env / KMS in production


class Author(Base):
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(StringEncryptedType(String(255), SECRET), nullable=False)


class Book(Base, MixinWithAutoNow):
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    author_id: Mapped[int] = mapped_column(ForeignKey("author.id"))
    author: Mapped["Author"] = relationship("Author", lazy="selectin")
    description: Mapped[str | None] = mapped_column(Text())
```

## Sessions

Most async services still need **sync** database access sometimes (`create_all` in tests, scripts, legacy code). Without helpers you duplicate engines, URLs, and `sessionmaker` settings.

**`session.init(url, **engine_kwargs)`** does that once: one async URL, shared options on both engines, and these entry points on `approck_sqlalchemy_utils.session` after `init()`:

| Callable | When to use it |
|----------|----------------|
| `get_session` (from **`mocks`**) | FastAPI `Depends(get_session)` — see [Getting started](#getting-started). |
| `override_session` | After `init()`, a `(Depends symbol, async dependency)` tuple for `app.dependency_overrides.setdefault(*override_session)`. The first element is the pre-init `mocks.get_session` callable imported at module load time. |
| `context_session` | `async with context_session() as session:` — async tests, tasks, scripts. |
| `current_session` | `with current_session() as session:` — sync ORM, `create_all`, CLI. |

### `init()` parameters

Extra keyword arguments are forwarded to **both** `create_async_engine` and `create_engine` (for example `pool_recycle=600`, `pool_size=5`).

```python
import approck_sqlalchemy_utils.session as db

db.init(
    "postgresql+asyncpg://user:pass@localhost:5432/mydb",
    pool_pre_ping=True,
    pool_recycle=600,
)
```

### Async code — `context_session`

```python
from approck_sqlalchemy_utils.session import context_session

async def load_row():
    async with context_session() as session:
        result = await session.execute(...)
        return result.scalar_one_or_none()
```

### Sync code — `current_session`

```python
import approck_sqlalchemy_utils.session as db
from approck_sqlalchemy_utils.model import Base

with db.current_session() as session:
    Base.metadata.create_all(session.get_bind())
```

This repository’s `tests/conftest.py` shows `init`, `context_session`, and `current_session` together with pytest-asyncio.

## Transaction boundaries

`approck_sqlalchemy_utils.transaction` gives the caller-side pieces for owning a transaction across several writes, instead of letting each write commit on its own.

### `atomic(session)` — own the boundary, compose safely

Open a boundary once, at the place that owns a request or message (an HTTP orchestrator, a consumer handler, a scheduler tick). Everything inside commits together or not at all.

```python
from approck_sqlalchemy_utils.transaction import atomic

async with atomic(session):
    user = await UserService(session).create(user_dto)
    await ProfileService(session).create(profile_for(user))
# committed here on success; rolled back if the block raised
```

`atomic` is **reentrant per session**. The outermost `atomic` opens the transaction (if none is open yet) and commits or rolls back on exit. A nested `atomic` on the same session runs as a **savepoint**: an inner block can fail and roll back without discarding the outer work, and an inner success never commits the caller's transaction. This is what lets two services, each wrapping its own work in `atomic`, compose into one transaction when called together.

The outermost level opens the transaction explicitly rather than relying on autobegin, so a nested savepoint always has a real transaction to nest in.

The outermost `atomic` owns the **whole** transaction of that session, including any rows written to the session *before* the boundary was entered — those commit or roll back with the boundary too. Don't write to a session outside a boundary if you need that write isolated from it.

### `savepoint(session)` — contain a partial failure

Use `savepoint` directly when you need to contain a failure inside an already-open transaction without discarding earlier writes: dedup that retries after an `IntegrityError`, translating a database error into a domain error, or a batch where one item failing must not roll back the rest.

```python
from approck_sqlalchemy_utils.transaction import savepoint

try:
    async with savepoint(session):
        session.add(row)
        await session.flush()
except IntegrityError:
    existing = await find_existing(session)  # outer transaction is still intact
```

`savepoint` requires an active transaction and raises if there is none — a savepoint must nest inside a boundary the caller controls, never one it silently opened.

## Development

Clone the repository and install with dev dependencies:

```bash
uv sync --all-extras
```

Tests expect **PostgreSQL** on `localhost:5432` with user/password `postgres`, database `postgres` (same URL as in `tests/conftest.py`). For example:

```bash
docker run -d --name approck-pg-test \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  postgres:16-alpine
```

Run tests:

```bash
uv run pytest
```

Lint:

```bash
uv run ruff check .
uv run ruff format --check .
```

Type-check (uses `mypy.ini`):

```bash
uv run mypy approck_sqlalchemy_utils
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for pull requests and release notes.

## Publishing to PyPI

Releases are built and uploaded by [`.github/workflows/release.yml`](.github/workflows/release.yml) when you push a **version tag** (for example `0.1.6` or `v0.1.6`). The version in `pyproject.toml` must match what you intend to ship.

### One-time PyPI setup (trusted publishing)

1. On GitHub: **Settings → Environments → New environment** → name **`pypi`** (exactly this name unless you change both GitHub and PyPI).
2. On [PyPI](https://pypi.org/manage/account/publishing/): add a **trusted publisher** for this project:
   - Owner: your GitHub user or organization  
   - Repository name: `adalekin/approck-sqlalchemy-utils` (adjust if the repo path differs)  
   - Workflow name: `release.yml`  
   - Environment name: `pypi`  
3. After the first successful upload, the PyPI project is created; for later releases, edit the project’s **Publishing** settings if the workflow or environment name changes.

The workflow uses **OpenID Connect** (`id-token: write`); a long-lived PyPI API token in GitHub Secrets is not required.

### Release checklist

1. Bump `version` in `pyproject.toml` (and commit).
2. `git tag 0.1.6` (or `v0.1.6`) and `git push origin <tag>`.

## License

MIT — see [LICENSE](LICENSE).

## Repository URLs

PyPI metadata points to this GitHub repository. If you fork or move the project, update `[project.urls]` in `pyproject.toml` and the CI badge in this README.
