import os
from os.path import join, dirname
import json
from datetime import date, datetime, timezone

from fastapi import FastAPI, HTTPException, Path, Query, Body, Depends, Response, Request
from typing import Optional
from sqlalchemy import select

from dotenv import load_dotenv
from sqlalchemy.sql.functions import user

from database import async_session_maker, Base, engine
from llm_service import ask_bot
from schemas import UserCreate, ChatRequest
from models import User, Message, Dialog

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

app = FastAPI()


@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.post(
    "/user_create/",
    tags=["Пользователи"],
    summary="Создание пользователя.",
    responses={
        201: {
            "description": "Пользователь создан.",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "id": 0,
                        "username": "USERNAME",
                        "tg_id": "0000000"
                    }
                }
            }
        },
        400: {
            "description": "Пользователь не создан.",
            "content": {
                "application/json": {
                    "example": {
                        "success": False, 'errorMsg': "Error message"
                    }
                }
            }
        }
    },
    status_code=201,
)
async def user_create(user: UserCreate):
    async with async_session_maker() as session:
        # Проверяем, существует ли пользователь
        result = await session.execute(
            select(User).where(User.tg_id == user.tg_id)
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="Пользователь уже существует"
            )

        new_user = User(
            username=user.username,
            tg_id=user.tg_id,
            created_at=datetime.utcnow()
        )

        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)
    return {
        "success": True,
        "id": new_user.id,
        "username": new_user.username,
        "tg_id": new_user.tg_id
    }


@app.post(
    "/chat/",
    tags=["Чаты"],
    summary="Чат с LLM и сохранением истории",
    responses={
        201: {
            "description": "Чат записывается",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "id": 0,
                        "username": "USERNAME",
                        "tg_id": "0000000",
                        "message": "text"
                    }
                }
            }
        },
        400: {
            "description": "Чат не записывается.",
            "content": {
                "application/json": {
                    "example": {
                        "success": False, 'errorMsg': "Error message"
                    }
                }
            }
        }
    },
    status_code=201,
)
async def chat(data: ChatRequest):

    async with async_session_maker() as session:

        # 1️⃣ Получаем пользователя
        result = await session.execute(
            select(User).where(User.tg_id == data.tg_id)
        )
        user = result.scalar_one_or_none()

        # 2️⃣ Создаем пользователя если нет
        if not user:
            user = User(
                tg_id=data.tg_id,
                username=data.username,
                created_at=datetime.utcnow()
            )
            session.add(user)
            await session.flush()

        # 3️⃣ Получаем активный диалог
        result = await session.execute(
            select(Dialog)
            .where(Dialog.user_id == user.id)
            .order_by(Dialog.created_at.desc())
            .limit(1)
        )
        dialog = result.scalar_one_or_none()

        # 4️⃣ Создаем диалог если нет
        if not dialog:
            dialog = Dialog(
                user_id=user.id,
                created_at=datetime.utcnow()
            )
            session.add(dialog)
            await session.flush()

        # 5️⃣ Сохраняем сообщение пользователя
        user_message = Message(
            dialog_id=dialog.id,
            role="user",
            text=data.message,
            created_at=datetime.utcnow()
        )

        session.add(user_message)
        await session.flush()

        # 6️⃣ Получаем последние сообщения (контекст)
        result = await session.execute(
            select(Message.role, Message.text)
            .where(Message.dialog_id == dialog.id)
            .order_by(Message.created_at.desc())
            .limit(20)
        )

        history = result.all()

        messages = [
            {"role": role, "content": text}
            for role, text in reversed(history)
        ]

        # system prompt
        messages.insert(0, {
            "role": "system",
            "content": "You are helpful Telegram AI assistant"
        })

        # 7️⃣ Отправляем в LLM
        llm_answer = await ask_bot(messages)

        # 8️⃣ Сохраняем ответ LLM
        assistant_message = Message(
            dialog_id=dialog.id,
            role="assistant",
            text=llm_answer,
            created_at=datetime.utcnow()
        )

        session.add(assistant_message)

        # 9️⃣ commit один раз
        await session.commit()

        return {
            "success": True,
            "user_id": user.id,
            "dialog_id": dialog.id,
            "question": data.message,
            "answer": llm_answer
        }


