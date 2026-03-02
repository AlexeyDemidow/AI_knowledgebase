import os
from os.path import join, dirname
import json
from datetime import date

from fastapi import FastAPI, HTTPException, Path, Query, Body, Depends, Response, Request
from typing import Optional
from sqlalchemy import select

from dotenv import load_dotenv

from database import async_session_maker, Base, engine
from schemas import UserCreate
from models import User

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
            tg_id=user.tg_id
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


