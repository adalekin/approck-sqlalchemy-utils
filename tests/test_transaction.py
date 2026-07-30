"""Behaviour of ``savepoint()`` and ``atomic()``: boundaries, nesting, visibility."""

import uuid

import pytest
from sqlalchemy import delete, select

import approck_sqlalchemy_utils.session as db
from approck_sqlalchemy_utils.transaction import atomic, savepoint
from tests.models import Author


def _marker() -> str:
    return uuid.uuid4().hex[:12]


async def _purge(marker: str) -> None:
    async with db.context_session() as session:
        await session.execute(delete(Author).where(Author.last_name == marker))
        await session.commit()


@pytest.mark.asyncio
async def test_savepoint_rollback_preserves_outer_writes() -> None:
    marker = _marker()
    try:
        async with db.context_session() as session:
            # Open the outer transaction the caller owns (autobegin on first write).
            session.add(Author(first_name="outer", last_name=marker, email="outer@example.com"))
            await session.flush()
            assert session.in_transaction()

            with pytest.raises(ValueError):
                async with savepoint(session):
                    session.add(Author(first_name="inner", last_name=marker, email="inner@example.com"))
                    await session.flush()
                    raise ValueError("boom")

            # The savepoint rolled back only the inner write; the outer one survives.
            await session.commit()

        async with db.context_session() as other:
            names = (await other.scalars(select(Author.first_name).where(Author.last_name == marker))).all()
        assert "outer" in names
        assert "inner" not in names
    finally:
        await _purge(marker)


@pytest.mark.asyncio
async def test_savepoint_requires_active_transaction() -> None:
    async with db.context_session() as session:
        assert not session.in_transaction()
        with pytest.raises(RuntimeError, match="active transaction"):
            async with savepoint(session):
                pass


@pytest.mark.asyncio
async def test_savepoint_success_visible_in_session_not_committed() -> None:
    marker = _marker()
    try:
        async with db.context_session() as session:
            session.add(Author(first_name="seed", last_name=marker, email="seed@example.com"))
            await session.flush()

            async with savepoint(session):
                session.add(Author(first_name="sp", last_name=marker, email="sp@example.com"))
                await session.flush()

            # Released savepoint: the write is visible to later reads in the same session.
            same = await session.scalar(select(Author).where(Author.first_name == "sp", Author.last_name == marker))
            assert same is not None

            # Not committed: an independent session must not see it yet.
            async with db.context_session() as other:
                unseen = await other.scalar(select(Author).where(Author.first_name == "sp", Author.last_name == marker))
                assert unseen is None

            await session.commit()
    finally:
        await _purge(marker)


@pytest.mark.asyncio
async def test_atomic_commits_on_success() -> None:
    marker = _marker()
    try:
        async with db.context_session() as session:
            async with atomic(session):
                session.add(Author(first_name="ok", last_name=marker, email="ok@example.com"))

        # Boundary committed on exit: an independent session sees the row.
        async with db.context_session() as other:
            found = await other.scalar(select(Author).where(Author.last_name == marker))
            assert found is not None
    finally:
        await _purge(marker)


@pytest.mark.asyncio
async def test_atomic_rolls_back_on_exception() -> None:
    marker = _marker()
    try:
        async with db.context_session() as session:
            with pytest.raises(ValueError):
                async with atomic(session):
                    session.add(Author(first_name="bad", last_name=marker, email="bad@example.com"))
                    await session.flush()
                    raise ValueError("boom")

        # Boundary rolled back: nothing persisted.
        async with db.context_session() as other:
            found = await other.scalar(select(Author).where(Author.last_name == marker))
            assert found is None
    finally:
        await _purge(marker)


@pytest.mark.asyncio
async def test_atomic_nested_commits_together() -> None:
    marker = _marker()
    try:
        async with db.context_session() as session:
            async with atomic(session):
                session.add(Author(first_name="outer", last_name=marker, email="outer@example.com"))
                async with atomic(session):
                    session.add(Author(first_name="inner", last_name=marker, email="inner@example.com"))

        async with db.context_session() as other:
            names = (await other.scalars(select(Author.first_name).where(Author.last_name == marker))).all()
        assert set(names) == {"outer", "inner"}
    finally:
        await _purge(marker)


@pytest.mark.asyncio
async def test_atomic_nested_failure_isolated_from_outer() -> None:
    marker = _marker()
    try:
        async with db.context_session() as session:
            async with atomic(session):
                session.add(Author(first_name="outer", last_name=marker, email="outer@example.com"))

                # Nested boundary runs as a savepoint; its failure, caught here,
                # rolls back only the inner write and leaves the outer intact.
                with pytest.raises(ValueError):
                    async with atomic(session):
                        session.add(Author(first_name="inner", last_name=marker, email="inner@example.com"))
                        await session.flush()
                        raise ValueError("boom")

        async with db.context_session() as other:
            names = (await other.scalars(select(Author.first_name).where(Author.last_name == marker))).all()
        assert "outer" in names
        assert "inner" not in names
    finally:
        await _purge(marker)


@pytest.mark.asyncio
async def test_atomic_nested_without_prior_statement() -> None:
    # The outermost boundary must open the transaction even when nothing ran yet,
    # so a nested savepoint has a real transaction to nest in.
    marker = _marker()
    try:
        async with db.context_session() as session:
            async with atomic(session):
                async with atomic(session):
                    session.add(Author(first_name="nested", last_name=marker, email="nested@example.com"))
                    await session.flush()

        async with db.context_session() as other:
            found = await other.scalar(select(Author).where(Author.last_name == marker))
            assert found is not None
    finally:
        await _purge(marker)


@pytest.mark.asyncio
async def test_atomic_owns_preexisting_transaction() -> None:
    marker = _marker()
    try:
        async with db.context_session() as session:
            # A write before the boundary autobegins a transaction.
            session.add(Author(first_name="before", last_name=marker, email="before@example.com"))
            await session.flush()
            assert session.in_transaction()

            async with atomic(session):
                session.add(Author(first_name="inside", last_name=marker, email="inside@example.com"))

            # The outermost boundary owns the whole transaction and commits both.
        async with db.context_session() as other:
            names = (await other.scalars(select(Author.first_name).where(Author.last_name == marker))).all()
        assert set(names) == {"before", "inside"}
    finally:
        await _purge(marker)


@pytest.mark.asyncio
async def test_atomic_depth_reset_after_use() -> None:
    marker = _marker()
    try:
        async with db.context_session() as session:
            async with atomic(session):
                session.add(Author(first_name="first", last_name=marker, email="first@example.com"))
            # Depth must return to zero so the next boundary on the same session is outermost.
            from approck_sqlalchemy_utils.transaction import _DEPTH_KEY

            assert session.info.get(_DEPTH_KEY, 0) == 0
    finally:
        await _purge(marker)
