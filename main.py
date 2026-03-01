import os
from os.path import join, dirname
import json
from datetime import date

from fastapi import FastAPI, HTTPException, Path, Query, Body, Depends, Response, Request
from typing import Optional

from dotenv import load_dotenv

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

app = FastAPI()


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
                        'success': True, 'id': 0
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
async def customer_create(
        username: str = Query(..., description="Имя пользователя", examples="Иван"),
        birthday: Optional[date] = Query(None, description="Дата рождения в формате ГГГГ-ММ-ДД", examples="2023-01-01"),
        sex: Optional[str] = Query(None, description="Пол (выбор между male/female).", examples="male"),
        number: str = Query(..., description="Номер телефона", examples="+375291234567"),
):
    if birthday:
        birthday =  birthday.isoformat()
    else:
        birthday = None

    data = {
        'username': username,
        'birthday': birthday,
        'sex': sex,
        'phone_number': number,
    }

    return data
