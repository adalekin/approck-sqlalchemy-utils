"""Stable FastAPI dependency symbol: ``get_session`` for ``Depends(get_session)``.

Import ``get_session`` from this module in route code. During bootstrap,
``approck_sqlalchemy_utils.session.init(...)`` replaces this callable with the
real async session generator.
"""

from typing import Any, Callable

from approck_sqlalchemy_utils.exceptions import ImproperlyConfigured

get_session: Callable[..., Any]


async def _unconfigured_get_session() -> Any:
    """Replaced by ``session.init`` with the real async session dependency."""
    raise ImproperlyConfigured(
        "Database is not configured: call approck_sqlalchemy_utils.session.init() before handling requests."
    )
    if False:  # pragma: no cover — async generator shape for FastAPI
        yield


get_session = _unconfigured_get_session
