import re

from sqlalchemy import MetaData
from sqlalchemy.orm import Mapped, as_declarative, declared_attr, mapped_column

SNAKE_CASE_RE = re.compile(r"(?<!^)(?=[A-Z])")


@as_declarative()
class Base:
    __name__: str
    metadata: MetaData

    @classmethod
    @declared_attr
    def __tablename__(cls):  # noqa: N805
        return SNAKE_CASE_RE.sub("_", cls.__name__).lower()

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.id}>"
