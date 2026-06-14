import json, numpy as np
from typing import Optional
from app.services.llm import get_embeddings


def cosine(a: list, b: list) -> float:
    an, bn = np.array(a), np.array(b)
    return float(np.dot(an, bn) / (np.linalg.norm(an) * np.linalg.norm(bn) + 1e-10))


async def search_similar(query: str, docs: list, top_k: int = 5) -> list:
    qe = await get_embeddings(query)
    if not qe or not docs: return []
    scored = []
    for d in docs:
        if not d.embedding: continue
        try:
            e = json.loads(d.embedding) if isinstance(d.embedding, str) else d.embedding
            scored.append((d, cosine(qe, e)))
        except: pass
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]
