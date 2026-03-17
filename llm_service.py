import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://openrouter.ai/api/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {os.getenv('OPEN_ROUTER_TOKEN')}",
}

async def ask_bot(messages: list):
    payload = {
        "model": "minimax/minimax-m2.5",
        "messages": messages,
        "max_tokens": 500
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(API_URL, headers=headers, json=payload) as response:
            result = await response.json()

    # Проверяем, есть ли choices
    if "choices" in result and len(result["choices"]) > 0:
        return result["choices"][0]["message"]["content"]
    elif "error" in result:
        # Если вернул ошибку
        raise Exception(f"LLM Error: {result['error']}")
    else:
        # Логируем весь результат для отладки
        print("Unexpected response from HF API:", result)
        raise Exception("Unexpected response format from Hugging Face API")