import os
from contextlib import asynccontextmanager
import uuid

import httpx
from fastapi import FastAPI, HTTPException, Form, UploadFile, File, Query
from sqlalchemy import select, delete
import aiofiles
import numpy as np
from urllib.parse import urlparse

from database import async_session_maker
from llm_service import ask_bot, translate_to_en, translate_to_ru
from models import Message, Document, DocumentChunk, Embedding
from utils import extract_text, split_text, create_embedding, get_user_chat, detect_lang, cosine_sim, process_file
from sentence_transformers import SentenceTransformer


documents_folder = "documents/"
os.makedirs(documents_folder, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading model...")

    app.state.model = SentenceTransformer("all-MiniLM-L6-v2")

    yield

    print("Shutting down...")


app = FastAPI(lifespan=lifespan)


@app.post("/add_document/")
async def add_document(
    tg_id: str = Form(...),
    username: str = Form(...),
    file: UploadFile = File(...),
):
    async with async_session_maker() as session:
        try:
            # 1️⃣ Сохраняем файл
            original_filename = file.filename
            unique_name = f"{uuid.uuid4()}_{file.filename}"
            file_path = os.path.join(documents_folder, unique_name)
            async with aiofiles.open(file_path, "wb") as buffer:
                content = await file.read()
                await buffer.write(content)

            doc = await process_file(file_path, original_filename, tg_id, username, session)

            return {
                "success": True,
                "id": doc.id,
                "filename": doc.filename,
                "file_path": doc.file_path,
                "file_size": doc.file_size,
                "dialog_id": doc.dialog_id,
                "created_at": doc.created_at,
            }

        except Exception as e:
            await session.rollback()
            return {"success": False, "errorMsg": str(e)}


@app.post("/add_document_by_url/")
async def add_document_by_url(
    tg_id: str = Form(...),
    username: str = Form(...),
    file_url: str = Form(...),
):
    if not file_url.startswith("http"):
        raise ValueError("Invalid URL")

    async with async_session_maker() as session:
        try:
            parsed = urlparse(file_url)
            original_filename = os.path.basename(parsed.path) or "file"
            unique_name = f"{uuid.uuid4()}_{original_filename}"
            file_path = os.path.join(documents_folder, unique_name)

            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream("GET", file_url) as response:
                    response.raise_for_status()

                    content_type = response.headers.get("content-type", "")

                    if "text/html" in content_type:
                        raise ValueError("URL does not point to a file")

                    total_size = 0
                    max_size = 10 * 1024 * 1024  # 10MB

                    with open(file_path, "wb") as f:
                        async for chunk in response.aiter_bytes():
                            total_size += len(chunk)

                            if total_size > max_size:
                                raise ValueError("File too large")

                            f.write(chunk)

            doc = await process_file(file_path, original_filename, tg_id, username, session)

            return {
                "success": True,
                "id": doc.id,
                "filename": doc.filename,
            }

        except Exception as e:
            await session.rollback()
            return {"success": False, "errorMsg": str(e)}


@app.post("/chat/")
async def chat(data: dict):
    tg_id = data.get("tg_id")
    username = data.get("username")
    message_text = data.get("message")
    chat_mode = data.get("chat_mode", "chat")
    doc_id = data.get("doc_id")

    if not message_text:
        return {"error": "Empty message"}

    async with async_session_maker() as session:
        dialog, user = await get_user_chat(session, tg_id, username)

        # 3️⃣ Сохраняем сообщение пользователя
        user_message = Message(dialog_id=dialog.id, role="user", text=message_text)
        session.add(user_message)
        await session.flush()

        if chat_mode == "document":

            # получаем все chunks и их embeddings
            # 1️⃣ Получаем язык документа отдельно
            doc_language = "ru"
            if doc_id:
                lang_result = await session.execute(
                    select(Document.language).where(Document.id == int(doc_id))
                )
                doc_language = lang_result.scalar_one_or_none() or "ru"

            # 2️⃣ Формируем запрос для chunk-ов
            query = (
                select(DocumentChunk.text, Embedding.vector, Document.language)
                .join(Embedding, Embedding.chunk_id == DocumentChunk.id)
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(Document.dialog_id == dialog.id)
            )

            if doc_id:
                query = query.where(Document.id == int(doc_id))

            # 3️⃣ Выполняем запрос и получаем все результаты
            result = await session.execute(query)
            chunks_vectors = result.all()

            if doc_language == "en":
                query_text = await translate_to_en(message_text)
            else:
                query_text = await translate_to_ru(message_text)

            query_vector = create_embedding(query_text)

            # считаем скоры
            scored_chunks = []

            for text, vector, _ in chunks_vectors:
                score = cosine_sim(vector, query_vector)
                scored_chunks.append((text, score))

            if not scored_chunks:
                context = ""
            else:
                top_chunks = [
                    text for text, _ in sorted(
                        scored_chunks,
                        key=lambda x: x[1],
                        reverse=True
                    )[:3]
                ]
                context = "\n\n".join(top_chunks)[:3000]
            # формируем prompt для модели
            messages = [
                {
                    "role": "system",
                    "content": f"""
                    Ответь строго:

                    1. Ответ на русском языке
                    2. Источник (из контекста)

                    Если нет ответа — напиши "Нет данных"
                    Используй предоставленные контекст: {context}
                    """
                },
                {"role": "user", "content": message_text},
            ]

        else:
            result = await session.execute(
                select(Message.role, Message.text)
                .where(Message.dialog_id == dialog.id)
                .order_by(Message.created_at.desc())
                .limit(20)
            )
            history = result.all()
            messages = [{"role": role, "content": text} for role, text in reversed(history) if text]
            messages.insert(0, {"role": "system", "content": "You are helpful assistant."})

        try:
            llm_answer = await ask_bot(messages)
        except Exception as e:
            return {"error": f"LLM error: {str(e)}"}

        if not llm_answer or not llm_answer.strip():
            return {"error": "Empty response"}
        # сохраняем ответ
        assistant_message = Message(dialog_id=dialog.id, role="assistant", text=llm_answer)
        session.add(assistant_message)
        await session.commit()

        result = {
            "success": True,
            "user_id": user.id,
            "dialog_id": dialog.id,
            "mode": chat_mode,
            "question": message_text,
            "answer": llm_answer,
        }
        return result


@app.get("/show_docs/")
async def show_docs(
        tg_id: str = Query(...),
        username: str = Query(None)
):
    async with async_session_maker() as session:
        dialog, user = await get_user_chat(session, tg_id, username)

        # 3️⃣ Получаем документы
        docs_result = await session.execute(
            select(Document)
            .where(Document.dialog_id == dialog.id)
            .order_by(Document.created_at.desc())
        )

        documents = docs_result.scalars().all()

        return {
            "success": True,
            "user_id": user.id,
            "dialog_id": dialog.id,
            "docs": [
                {
                    "id": doc.id,
                    "name": doc.filename,
                    # "text": doc.text,
                    "created_at": doc.created_at
                }
                for doc in documents
            ]
        }


@app.delete("/delete_doc/")
async def delete_doc(
        tg_id: str = Query(...),
        username: str = Query(None),
        doc_id: int = Query(...)
):
    async with async_session_maker() as session:
        dialog, user = await get_user_chat(session, tg_id, username)

        # Удаляем документ
        result = await session.execute(
            delete(Document).where(
                Document.id == doc_id,
                Document.dialog_id == dialog.id
            )
        )
        await session.commit()

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Document not found")

        return {
            "success": True,
            "message": "Document deleted"
        }
