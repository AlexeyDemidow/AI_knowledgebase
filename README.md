# 🧠 AI Knowledge Base — Backend (RAG + FastAPI)

> REST API для интеллектуальной базы знаний с поддержкой RAG (Retrieval-Augmented Generation).  
> Позволяет загружать документы, строить векторные эмбеддинги и отвечать на вопросы по содержимому документов через LLM.

**🤖 Telegram-бот для этого сервиса:** [AI_knowledgebase_tg_bot](https://github.com/AlexeyDemidow/AI_knowledgebase_tg_bot)

---

## 📋 Содержание

- [О проекте](#-о-проекте)
- [Технологии](#-технологии)
- [Архитектура](#-архитектура)
- [Установка и запуск](#-установка-и-запуск)
- [Переменные окружения](#-переменные-окружения)

---

## 📖 О проекте

AI Knowledge Base — это бэкенд-сервис на FastAPI, который реализует паттерн **RAG (Retrieval-Augmented Generation)**:

1. Пользователь загружает документ (PDF, DOCX, TXT) или указывает ссылку на файл
2. Документ разбивается на чанки и векторизуется с помощью `SentenceTransformer`
3. Эмбеддинги сохраняются в PostgreSQL с расширением `pgvector`
4. При вопросе пользователя система находит релевантные чанки через косинусное сходство и передаёт их в LLM
5. LLM генерирует ответ строго на основе предоставленного контекста

Поддерживается два режима диалога: **обычный чат** (с историей) и **режим документа** (вопросы по конкретному файлу).

---

## 🛠 Технологии

| Компонент | Технология |
|-----------|-----------|
| Веб-фреймворк | FastAPI + Uvicorn |
| База данных | PostgreSQL + pgvector |
| ORM | SQLAlchemy (async) + Alembic |
| Эмбеддинги | SentenceTransformer (`all-MiniLM-L6-v2`) |
| Обработка документов | pypdf, python-docx |
| HTTP-клиент | httpx (async) |
| Детекция языка | langdetect |
| Контейнеризация | Docker + Docker Compose |

---

## 🏗 Архитектура

```
Пользователь / Telegram-бот
        │
        ▼
   FastAPI (main.py)
        │
   ┌────┴────┐
   │         │
   ▼         ▼
Загрузка   /chat/
документа    │
   │     ┌───┴──────────────┐
   │     │                  │
   ▼     ▼                  ▼
utils  Режим чата      Режим документа (RAG)
   │   (история)       │
   │                   ├── Перевод запроса (EN/RU)
   ▼                   ├── Векторизация запроса
SentenceTransformer    ├── Косинусное сходство
   │                   └── Топ-3 чанка → LLM
   ▼
PostgreSQL + pgvector
(Document, DocumentChunk, Embedding, Message)
```

---


## 🚀 Установка и запуск

### Через Docker Compose (рекомендуется)

```bash
# Клонировать репозиторий
git clone https://github.com/AlexeyDemidow/AI_knowledgebase.git
cd AI_knowledgebase

# Настроить переменные окружения
cp .env.example .env
# Заполнить .env своими значениями

# Запустить
docker-compose up -d
```

### Локальный запуск

```bash
# Клонировать репозиторий
git clone https://github.com/AlexeyDemidow/AI_knowledgebase.git
cd AI_knowledgebase

# Создать и активировать виртуальное окружение
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Установить зависимости
pip install -r requirements.txt

# Настроить переменные окружения
cp .env.example .env
# Заполнить .env своими значениями

# Применить миграции базы данных
alembic upgrade head

# Запустить сервер
uvicorn main:app --reload
```

После запуска документация API доступна по адресу: `http://localhost:8000/docs`

---

## ⚙️ Переменные окружения

Создайте файл `.env` на основе `.env.example`:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=ai_knowledgebase
DB_USER=postgres
DB_PASSWORD=your_password
```

> **Важно:** Для работы pgvector необходимо установить расширение в PostgreSQL:
> ```sql
> CREATE EXTENSION IF NOT EXISTS vector;
> ```

---

## 🔗 Связанные проекты

- **Telegram-бот:** [AlexeyDemidow/AI_knowledgebase_tg_bot](https://github.com/AlexeyDemidow/AI_knowledgebase_tg_bot) — интерфейс для взаимодействия с этим API через Telegram