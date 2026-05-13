from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from approck_sqlalchemy_utils.mixins.auto_now import MixinWithAutoNow
from approck_sqlalchemy_utils.model import Base
from approck_sqlalchemy_utils.types.encrypted.encrypted_type import StringEncryptedType

secret_key = "123"


class Author(Base):
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(StringEncryptedType(String(255), secret_key), nullable=False)


class Book(Base, MixinWithAutoNow):
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)

    author_id: Mapped[int] = mapped_column(ForeignKey("author.id"))
    author: Mapped["Author"] = relationship("Author", lazy="selectin")

    description: Mapped[Optional[str]] = mapped_column(Text())
