"""Small utilities for SQLAlchemy 2.x: models, sessions, custom types, and helpers."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("approck-sqlalchemy-utils")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = ["__version__"]
