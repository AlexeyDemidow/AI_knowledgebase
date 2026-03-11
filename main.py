import os
from os.path import join, dirname
import json
from datetime import date, datetime, timezone
import uuid

from fastapi import FastAPI, HTTPException, Path, Query, Body, Depends, Response, Request, UploadFile, File, Form
from typing import Optional
from sqlalchemy import select
import aiofiles

from dotenv import load_dotenv
from sqlalchemy.sql.functions import user

from database import async_session_maker, Base, engine
from llm_service import ask_bot
from schemas import UserCreate, ChatRequest
from models import User, Message, Dialog, Document

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

app = FastAPI()


# @app.on_event("startup")
# async def on_startup():
#     async with engine.begin() as conn:
#         await conn.run_sync(Base.metadata.create_all)


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
            )
            session.add(dialog)
            await session.flush()

        # 5️⃣ Сохраняем сообщение пользователя
        user_message = Message(
            dialog_id=dialog.id,
            role="user",
            text=data.message,
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



documents_folder = "documents/"
os.makedirs(documents_folder, exist_ok=True)

@app.on_event("startup")
async def load_model():
    global model
    model = SentenceTransformer("all-MiniLM-L6-v2")


@app.post("/add_document/")
async def add_document(
        tg_id: str = Form(...),
        username: str = Form(...),
        file: UploadFile = File(...)
):

    async with async_session_maker() as session:
        try:
            unique_name = f"{uuid.uuid4()}_{file.filename}"
            file_path = os.path.join(documents_folder, unique_name)

            if os.path.exists(file_path):
                raise ValueError("Файл уже существует")

            allowed = {"pdf", "docx", "txt"}

            ext = file.filename.split(".")[-1].lower()

            if ext not in allowed:
                raise ValueError("Неподдерживаемый формат файла")

            # сохраняем файл
            async with aiofiles.open(file_path, "wb") as buffer:
                content = await file.read()
                await buffer.write(content)

            file_size = os.path.getsize(file_path)

            # пользователь
            result = await session.execute(
                select(User).where(User.tg_id == tg_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                user = User(tg_id=tg_id, username=username)
                session.add(user)
                await session.flush()

            # диалог
            result = await session.execute(
                select(Dialog)
                .where(Dialog.user_id == user.id)
                .order_by(Dialog.created_at.desc())
                .limit(1)
            )
            dialog = result.scalar_one_or_none()

            if not dialog:
                dialog = Dialog(user_id=user.id)
                session.add(dialog)
                await session.flush()

            # документ
            doc = Document(
                filename=file.filename,
                file_path=file_path,
                file_size=file_size,
                dialog_id=dialog.id
            )

            session.add(doc)
            await session.commit()
            await session.refresh(doc)

            return {
                "success": True,
                "id": doc.id,
                "filename": doc.filename,
                "file_path": doc.file_path,
                "file_size": doc.file_size,
                "dialog_id": doc.dialog_id,
                "created_at": doc.created_at
            }

        except Exception as e:
            await session.rollback()
            return {
                "success": False,
                "errorMsg": str(e)
            }