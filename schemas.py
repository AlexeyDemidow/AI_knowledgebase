from typing import Literal

from pydantic import BaseModel, Field

class UserCreate(BaseModel):
    username: str = Field(
        description="Имя пользователя",
        examples=["Иван"]
    )
    tg_id: str = Field(
        description="Telegram ID",
        examples=["123456789"]
    )


class ChatRequest(BaseModel):
    username: str = Field(
        description="Имя пользователя",
        examples=["Иван"]
    )
    tg_id: str = Field(
        description="Telegram ID",
        examples=["123456789"]
    )
    message: str = Field(
        description="Сообщение",
        examples=["Привет"]
    ),
    chat_mode: Literal["chat", "document"] = Field(
        default="chat",
        description="Вид чата. 'chat' - обычный чат, 'document' - чат с поиском по документам"
    )