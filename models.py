from sqlalchemy import ForeignKey, text, Text
from sqlalchemy.orm import relationship, Mapped, mapped_column
from database import Base, str_uniq, int_pk, str_null_true
from datetime import date


class User(Base):
    id: Mapped[int_pk]
    username: Mapped[str]
    phone_number: Mapped[str_uniq]
    date_of_birth: Mapped[date]
    sex: Mapped[str]

    def __str__(self):
        return (f"{self.__class__.__name__}(id={self.id}, "
                f"username={self.username!r},"
                )

    def __repr__(self):
        return str(self)