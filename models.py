from sqlalchemy import ForeignKey, text, Text
from sqlalchemy.orm import relationship, Mapped, mapped_column
from database import Base, str_uniq, int_pk, str_null_true
from datetime import date


class User(Base):
    __tablename__ = "users"
    id: Mapped[int_pk]
    tg_id: Mapped[str_uniq]
    username: Mapped[str]
    created_at: Mapped[datetime]

    dialogs: Mapped[list["Dialog"]] = relationship(back_populates="user")

    def __str__(self):
        return (f"{self.__class__.__name__}(id={self.id}, "
                f"username={self.username!r},"
                )

    def __repr__(self):
        return str(self)
#
#
# class Document(Base):
#     pass
#
#
# class DocumentChunk(Base):
#     pass
#
#
# class Embedding(Base):
#     pass
#
#
# class QueryHistory(Base):
#     pass
#
#
# class SubscriptionPlan(Base):
#     pass
