from contextlib import asynccontextmanager
from typing import Any, AsyncContextManager, AsyncGenerator, Callable, cast

from sqlalchemy import create_engine, orm
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from . import mocks

AsyncSessionGenerator = AsyncGenerator[AsyncSession, None]

# Aliased to mocks.get_session until init(). Application routes should use
# ``from approck_sqlalchemy_utils.mocks import get_session`` for Depends (see README).
get_session = mocks.get_session
override_session = mocks.get_session


def async_session(
    url: str,
    *,
    wrap: Callable[..., Any] | None = None,
    **engine_kwargs: Any,
) -> Callable[..., AsyncSessionGenerator] | AsyncContextManager[Any]:
    engine = create_async_engine(
        url,
        pool_pre_ping=True,
        future=True,
        **engine_kwargs,
    )
    factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        autoflush=False,
        expire_on_commit=False,
    )

    async def _async_session_dependency() -> AsyncSessionGenerator:
        async with factory() as session:
            yield session

    return _async_session_dependency if wrap is None else wrap(_async_session_dependency)


def sync_session(url: str, **engine_kwargs: Any) -> orm.scoped_session:
    engine = create_engine(
        url,
        pool_pre_ping=True,
        future=True,
        **engine_kwargs,
    )
    factory = orm.sessionmaker(
        engine,
        autoflush=False,
        expire_on_commit=False,
    )
    return orm.scoped_session(factory)


def init(url: str, **engine_kwargs: Any) -> None:
    """Initialize session factories with the given database URL and optional engine options.

    Engine kwargs are passed to both async and sync engines. Useful options include:
    - pool_recycle: recycle connections after N seconds (e.g. 300–600 for PgBouncer)
    - pool_size: size of the connection pool
    - max_overflow: max overflow connections beyond pool_size
    """
    sync_url = url.replace("+asyncpg", "")
    async_dep = async_session(url, **engine_kwargs)
    # Capture the pre-init symbol before patching mocks — key for dependency_overrides
    # when routes use ``from approck_sqlalchemy_utils.mocks import get_session``.
    override_pair = (mocks.get_session, async_dep)
    mocks.get_session = cast(Callable[..., Any], async_dep)
    _session_map = {
        "get_session": async_dep,
        "override_session": override_pair,
        "current_session": sync_session(sync_url, **engine_kwargs),
        "context_session": async_session(url, wrap=asynccontextmanager, **engine_kwargs),
    }

    for _key, _session in _session_map.items():
        globals()[_key] = _session
