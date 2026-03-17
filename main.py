import os
from os.path import join, dirname
import uuid
from datetime import datetime

from fastapi import FastAPI, HTTPException, Form, UploadFile, File
from sqlalchemy import select
import aiofiles
import numpy as np

from database import async_session_maker
from llm_service import ask_bot
from models import User, Dialog, Message, Document, DocumentChunk, Embedding
from utils import extract_text, split_text, create_embedding
from sentence_transformers import SentenceTransformer

app = FastAPI()

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
    file: UploadFile = File(...),
):
    async with async_session_maker() as session:
        try:
            # 1️⃣ Сохраняем файл
            unique_name = f"{uuid.uuid4()}_{file.filename}"
            file_path = os.path.join(documents_folder, unique_name)
            async with aiofiles.open(file_path, "wb") as buffer:
                content = await file.read()
                await buffer.write(content)
            file_size = os.path.getsize(file_path)

            # 2️⃣ Получаем пользователя
            result = await session.execute(select(User).where(User.tg_id == tg_id))
            user = result.scalar_one_or_none()
            if not user:
                user = User(tg_id=tg_id, username=username)
                session.add(user)
                await session.flush()

            # 3️⃣ Получаем диалог
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

            # 4️⃣ Создаём документ
            doc = Document(
                filename=file.filename,
                file_path=file_path,
                file_size=file_size,
                dialog_id=dialog.id,
            )
            session.add(doc)
            await session.commit()
            await session.refresh(doc)

            # 5️⃣ Извлекаем текст и создаем chunks + embeddings
            text = extract_text(file_path)
            chunks = split_text(text)

            for i, chunk in enumerate(chunks):
                doc_chunk = DocumentChunk(
                    document_id=doc.id,
                    text=chunk,
                    chunk_index=i,
                )
                session.add(doc_chunk)
                await session.flush()

                vector = create_embedding(chunk)
                embedding = Embedding(
                    chunk_id=doc_chunk.id,
                    vector=vector,
                )
                session.add(embedding)

            await session.commit()

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


@app.post("/chat/")
async def chat(data: dict):
    tg_id = data.get("tg_id")
    username = data.get("username")
    message_text = data.get("message")
    chat_mode = data.get("chat_mode", "chat")

    async with async_session_maker() as session:
        # 1️⃣ Получаем пользователя
        result = await session.execute(select(User).where(User.tg_id == tg_id))
        user = result.scalar_one_or_none()
        if not user:
            user = User(tg_id=tg_id, username=username)
            session.add(user)
            await session.flush()

        # 2️⃣ Получаем или создаем диалог
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

        # 3️⃣ Сохраняем сообщение пользователя
        user_message = Message(dialog_id=dialog.id, role="user", text=message_text)
        session.add(user_message)
        await session.flush()

        if chat_mode == "document":
            query_embedding = create_embedding(message_text)

            # получаем все chunks и их embeddings
            result = await session.execute(
                select(DocumentChunk.text, Embedding.vector)
                .join(Embedding, Embedding.chunk_id == DocumentChunk.id)
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(Document.dialog_id == dialog.id)
            )
            chunks_vectors = result.all()

            # считаем cosine similarity
            def cosine_sim(a, b):
                a, b = np.array(a), np.array(b)
                return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

            scored_chunks = [
                (text, cosine_sim(vector, query_embedding))
                for text, vector in chunks_vectors
            ]
            # берём top-5
            top_chunks = [text for text, _ in sorted(scored_chunks, key=lambda x: x[1], reverse=True)[:5]]
            context = "\n\n".join(top_chunks)
            # формируем prompt для модели
            messages = [
                {"role": "system", "content": f"You are helpful assistant. Use the following context:\n{context}"},
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
            messages = [{"role": role, "content": text} for role, text in reversed(history)]
            messages.insert(0, {"role": "system", "content": "You are helpful assistant."})

        llm_answer = await ask_bot(messages)  # ask_bot должна возвращать строку

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