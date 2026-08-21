"""语义缓存 - 基于 embedding 相似度

P1: 多 Provider 抽象层

仅适用于 LLM 引擎。每用户独立缓存（user_id 过滤）。
- cosine 相似度 ≥ threshold (默认 0.90) 命中
- TTL 30min（LLM 结果可能随时间变化）
- 每用户最多 1000 条（FIFO 淘汰）
- system_prompt_hash + model 隔离
"""
import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.core.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """缓存条目"""
    query: str
    response: str
    embedding: list[float]
    created_at: datetime
    hit_count: int = 0


class SemanticCache:
    """语义缓存 - 基于 bge-m3 embedding + ChromaDB"""

    def __init__(
        self,
        embedding_service: "EmbeddingService",
        collection_name: str = "llm_semantic_cache",
        similarity_threshold: float = 0.90,
        ttl_seconds: int = 1800,
        max_entries_per_user: int = 1000,
        chroma_path: str = "data/chroma_semantic",
    ):
        self._embedding = embedding_service
        self._collection_name = collection_name
        self._threshold = similarity_threshold
        self._ttl = ttl_seconds
        self._max_entries = max_entries_per_user
        self._chroma_path = chroma_path
        self._chroma_client = None
        self._collection = None
        self._initialized = False

    async def initialize(self) -> None:
        """初始化 ChromaDB 客户端 + collection"""
        if self._initialized:
            return
        import chromadb
        self._chroma_client = chromadb.PersistentClient(path=self._chroma_path)
        self._collection = self._chroma_client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._initialized = True
        logger.info(f"SemanticCache initialized at {self._chroma_path}")

    async def lookup(
        self,
        user_id: int,
        query: str,
        system_prompt_hash: str = "",
        model: str = "",
    ) -> Optional[CacheEntry]:
        """查询缓存

        Returns:
            命中返回 CacheEntry，未命中返回 None
        """
        await self.initialize()
        query_embedding = await self._embedding.encode(query)

        # ChromaDB where 过滤
        where: dict = {"user_id": user_id}
        if system_prompt_hash:
            where["system_prompt_hash"] = system_prompt_hash
        if model:
            where["model"] = model

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=1,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        if not results["ids"][0]:
            return None

        distance = results["distances"][0][0]
        # cosine distance: 0=完全相同, 2=完全相反
        # similarity = 1 - distance, threshold 0.90 → distance < 0.10
        similarity = 1.0 - distance
        if similarity < self._threshold:
            return None

        metadata = results["metadatas"][0][0]
        # TTL 检查
        created_at_ts = metadata.get("created_at", 0)
        now_ts = int(datetime.now(UTC).timestamp())
        if now_ts - created_at_ts > self._ttl:
            return None  # TTL 过期

        # hit_count++（更新存储，但返回原始计数值）
        doc_id = results["ids"][0][0]
        original_hit_count = metadata.get("hit_count", 0)
        new_hit_count = original_hit_count + 1
        self._collection.update(
            ids=[doc_id],
            metadatas=[{**metadata, "hit_count": new_hit_count}],
        )

        return CacheEntry(
            query=results["documents"][0][0],
            response=metadata.get("response", ""),
            embedding=query_embedding,
            created_at=datetime.fromtimestamp(created_at_ts),
            hit_count=original_hit_count,
        )

    async def store(
        self,
        user_id: int,
        query: str,
        response: str,
        system_prompt_hash: str = "",
        model: str = "",
    ) -> None:
        """存储缓存"""
        await self.initialize()
        query_embedding = await self._embedding.encode(query)

        # FIFO 淘汰：检查用户缓存条目数
        user_entries = self._collection.get(
            where={"user_id": user_id},
            include=["metadatas"],
        )
        if len(user_entries["ids"]) >= self._max_entries:
            # 删除最旧的（按 created_at 排序）
            sorted_entries = sorted(
                zip(user_entries["ids"], user_entries["metadatas"]),
                key=lambda x: x[1].get("created_at", 0),
            )
            oldest_ids = [eid for eid, _ in sorted_entries[: len(sorted_entries) - self._max_entries + 1]]
            if oldest_ids:
                self._collection.delete(ids=oldest_ids)

        # 写入
        doc_id = f"{user_id}:{hashlib.sha256(query.encode()).hexdigest()[:16]}"
        now_ts = int(datetime.now(UTC).timestamp())
        self._collection.add(
            ids=[doc_id],
            documents=[query],
            embeddings=[query_embedding],
            metadatas=[{
                "user_id": user_id,
                "system_prompt_hash": system_prompt_hash,
                "model": model,
                "created_at": now_ts,
                "hit_count": 0,
                "response": response,
            }],
        )

    async def invalidate_user(self, user_id: int) -> None:
        """清空指定用户的所有缓存"""
        await self.initialize()
        self._collection.delete(where={"user_id": user_id})

    async def stats(self, user_id: int) -> dict:
        """返回用户缓存统计"""
        await self.initialize()
        entries = self._collection.get(
            where={"user_id": user_id},
            include=["metadatas"],
        )
        total_entries = len(entries["ids"])
        total_hits = sum(m.get("hit_count", 0) for m in entries["metadatas"])
        return {
            "total_entries": total_entries,
            "total_hits": total_hits,
            "hit_rate": total_hits / (total_entries + total_hits) if (total_entries + total_hits) > 0 else 0.0,
        }
