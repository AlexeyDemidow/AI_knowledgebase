from pydantic import BaseModel, Field

class UserCreate(BaseModel):
    # id: int = Field(
    #     description="ID пользователя",
    #     examples=[0]
    # )
    username: str = Field(
        description="Имя пользователя",
        examples=["Иван"]
    )
    tg_id: str = Field(
        description="Telegram ID",
        examples=["123456789"]
    )