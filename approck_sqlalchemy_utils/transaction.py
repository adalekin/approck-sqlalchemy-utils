"""Transaction helpers layered on top of ``AsyncSession``."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

__all__ = ["atomic", "savepoint"]

#: Per-session reentrancy depth, kept in ``session.info`` so parallel sessions
#: (e.g. concurrent tasks) never share a counter.
_DEPTH_KEY = "approck_atomic_depth"


@asynccontextmanager
async def savepoint(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    """Run a block inside a SAVEPOINT so a failure rolls back only this block.

    Use this instead of ``session.rollback()`` when a partial failure must be
    contained without discarding what the caller already wrote in the same
    transaction: deduplication that retries after an ``IntegrityError``,
    translating a database error into a domain error, or a batch where one item
    failing must not roll back the others.

    An **active transaction owned by the caller is required**. On a session with
    no open transaction ``session.begin_nested()`` autobegins the outer
    transaction itself, so relying on it to signal a missing boundary does not
    work; this helper checks explicitly and raises. That keeps the guarantee that
    a savepoint always nests inside a transaction the caller controls, never one
    it silently opened.

    On success the SAVEPOINT is released; on any exception it is rolled back to
    and the exception propagates.
    """
    if not session.in_transaction():
        raise RuntimeError(
            "savepoint() requires an active transaction; the caller must open the transaction boundary first"
        )

    async with session.begin_nested():
        yield session


@asynccontextmanager
async def atomic(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    """Own the transaction boundary for a block of work, and compose safely.

    This is the boundary a caller opens so that several commit-free services
    (``autocommit=False``) commit together or not at all. Use it in the places
    that own a request or message: an HTTP orchestrator, a consumer handler, a
    scheduler tick.

    Reentrant per session:

    - **Outermost** ``atomic`` opens a transaction if the session has none, then
      commits it on success or rolls it back on any exception. It owns the whole
      transaction of that session — do not write to the session outside a boundary
      if you need that write isolated.
    - **Nested** ``atomic`` (same session, already inside one) runs as a
      ``savepoint`` instead of committing, so an inner block can fail and roll
      back without discarding the outer work, and an inner success never commits
      the caller's transaction.

    The outermost level opens the transaction explicitly (rather than leaning on
    autobegin) so that a nested savepoint always has a real transaction to nest
    in, even when no statement ran before the nested block.
    """
    depth = session.info.get(_DEPTH_KEY, 0)

    if depth > 0:
        session.info[_DEPTH_KEY] = depth + 1
        try:
            async with savepoint(session):
                yield session
        finally:
            session.info[_DEPTH_KEY] = depth
        return

    session.info[_DEPTH_KEY] = 1
    if not session.in_transaction():
        await session.begin()
    try:
        yield session
        await session.commit()
    except BaseException:
        # BaseException, not Exception: the boundary must roll back on ANY
        # interruption of the block, including CancelledError/KeyboardInterrupt,
        # or the transaction would be left open. The original error is always
        # re-raised; a secondary failure from the rollback itself (e.g. a dead
        # connection) is suppressed so it cannot mask the cause.
        try:
            await session.rollback()
        except Exception:
            pass
        raise
    finally:
        session.info[_DEPTH_KEY] = 0
