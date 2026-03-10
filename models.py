from sqlalchemy import ForeignKey, text as sql_text, Text
from sqlalchemy.orm import relationship, Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from database import Base, str_uniq, int_pk, str_null_true
from datetime import date, datetime


class User(Base):
    __tablename__ = "users"
    id: Mapped[int_pk]
    tg_id: Mapped[str_uniq]
    username: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=sql_text("now()"))

    dialogs: Mapped[list["Dialog"]] = relationship(back_populates="user")

    def __str__(self):
        return (f"{self.__class__.__name__}(id={self.id}, "
                f"username={self.username!r},"
                )

    def __repr__(self):
        return str(self)


class Dialog(Base):
    __tablename__ = "dialogs"
    id: Mapped[int_pk]

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=sql_text("now()"))

    user: Mapped["User"] = relationship(back_populates="dialogs")
    messages: Mapped[list["Message"]] = relationship(back_populates="dialog", cascade="all, delete-orphan")
    documents: Mapped[list["Document"]] = relationship(back_populates="dialog", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int_pk]

    dialog_id: Mapped[int] = mapped_column(ForeignKey("dialogs.id"))

    role: Mapped[str]
    text: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(server_default=sql_text("now()"))

    dialog: Mapped["Dialog"] = relationship(back_populates="messages")


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int_pk]
    dialog_id: Mapped[int] = mapped_column(ForeignKey("dialogs.id"))

    filename: Mapped[str]
    file_path: Mapped[str]
    file_size: Mapped[int]

    created_at: Mapped[datetime] = mapped_column(server_default=sql_text("now()"))

    dialog: Mapped["Dialog"] = relationship(back_populates="documents")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int_pk]
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))

    text: Mapped[str]
    chunk_index: Mapped[int]


class Embedding(Base):
    __tablename__ = "embeddings"

    id: Mapped[int_pk]
    chunk_id: Mapped[int] = mapped_column(ForeignKey("document_chunks.id"))

    vector: Mapped[list[float]] = mapped_column(Vector(384))
#
# class QueryHistory(Base):
#     pass
#
#
# class SubscriptionPlan(Base):
#     pass
