from typing import Iterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.pool import NullPool

import approck_sqlalchemy_utils.session
from tests.models import Author, Base, Book

# NullPool: pytest-asyncio gives each test function its own event loop, and a pooled
# asyncpg connection is bound to the loop that opened it. Reusing one across loops
# raises "attached to a different loop". NullPool opens a fresh connection per use,
# which is what lets tests that open several sessions run under the full suite.
approck_sqlalchemy_utils.session.init(
    url="postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
    poolclass=NullPool,
)


@pytest.fixture(autouse=True, scope="session")
def fx_apply_migrations():
    with approck_sqlalchemy_utils.session.current_session() as session:
        Base.metadata.create_all(session.get_bind())
        yield
        session.rollback()


@pytest_asyncio.fixture(name="fx_session", autouse=True)
async def fx_session_impl() -> Iterator[AsyncSession]:
    async with approck_sqlalchemy_utils.session.context_session() as session:
        yield session


@pytest_asyncio.fixture(name="fx_author")
async def fx_author_impl(fx_session: AsyncSession) -> Author:
    author = Author(first_name="Paulo", last_name="Coelho", email="paulo_coelho@gmail.com")

    fx_session.add(author)
    await fx_session.commit()

    return author


@pytest_asyncio.fixture(name="fx_book")
async def fx_book_impl(fx_session: AsyncSession, fx_author: Author) -> Book:
    book = Book(slug="alchemist", title="The Alchemist", author=fx_author)

    fx_session.add(book)
    await fx_session.commit()

    return book
