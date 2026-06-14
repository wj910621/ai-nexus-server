import httpx, json
from typing import AsyncGenerator
from app.config import settings


async def stream_chat(model: str, messages: list, temp: float = 0.7, mt: int = 4096) -> AsyncGenerator[str, None]:
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream('POST', f'{settings.api_base_url}/api/chat', json={
            'model': model, 'messages': messages, 'temperature': temp, 'max_tokens': mt, 'stream': True
        }) as resp:
            async for line in resp.aiter_lines():
                if line.startswith('data: ') and line.strip() != 'data: [DONE]':
                    try:
                        d = json.loads(line[6:])
                        c = d.get('choices', [{}])[0].get('delta', {}).get('content', '')
                        if c: yield c
                    except: pass


async def chat(model: str, messages: list, temp: float = 0.3, mt: int = 2048) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f'{settings.api_base_url}/api/chat', json={
            'model': model, 'messages': messages, 'temperature': temp, 'max_tokens': mt, 'stream': False
        })
        return r.json().get('choices', [{}])[0].get('message', {}).get('content', '')


async def get_embeddings(text: str) -> list:
    if not settings.openai_api_key: return []
    headers = {'Authorization': f'Bearer {settings.openai_api_key}', 'Content-Type': 'application/json'}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post('https://api.openai.com/v1/embeddings', json={'input': text, 'model': 'text-embedding-3-small'}, headers=headers)
        return r.json().get('data', [{}])[0].get('embedding', [])
