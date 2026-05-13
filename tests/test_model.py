import pytest

from tests.models import Book


@pytest.mark.asyncio
async def test_model_auto_now(fx_book: Book):
    assert fx_book.created_at == fx_book.updated_at
    assert fx_book.created_at.tzinfo is not None
