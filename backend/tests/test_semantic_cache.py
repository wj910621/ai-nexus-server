"""Tests for SemanticCache."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, UTC

from app.core.semantic_cache import SemanticCache, CacheEntry
from app.core.embedding_service import EmbeddingService


@pytest.fixture
def mock_embedding():
    """Mock EmbeddingService"""
    service = MagicMock(spec=EmbeddingService)
    service.encode = AsyncMock(return_value=[0.1] * 1024)
    return service


@pytest.fixture
def mock_chroma_collection():
    """Mock ChromaDB collection"""
    collection = MagicMock()
    collection.query = MagicMock(return_value={
        "ids": [],
        "documents": [],
        "metadatas": [],
        "distances": [],
    })
    collection.add = MagicMock()
    collection.delete = MagicMock()
    collection.get = MagicMock(return_value={
        "ids": [],
        "metadatas": [],
    })
    return collection


@pytest.fixture
def cache(mock_embedding, mock_chroma_collection):
    """SemanticCache 实例（使用 mock 依赖）"""
    c = SemanticCache(
        embedding_service=mock_embedding,
        similarity_threshold=0.90,
        ttl_seconds=1800,
        max_entries_per_user=1000,
    )
    c._collection = mock_chroma_collection
    c._initialized = True
    return c


@pytest.mark.asyncio
async def test_lookup_miss(cache, mock_chroma_collection):
    """未命中返回 None"""
    mock_chroma_collection.query.return_value = {
        "ids": [[]],
        "documents": [[]],
        "metadatas": [[]],
        "distances": [[]],
    }
    result = await cache.lookup(user_id=1, query="hello")
    assert result is None


@pytest.mark.asyncio
async def test_lookup_hit(cache, mock_chroma_collection):
    """命中返回 CacheEntry"""
    now_ts = int(datetime.now(UTC).timestamp())
    mock_chroma_collection.query.return_value = {
        "ids": [["id1"]],
        "documents": [["hello"]],
        "metadatas": [[{
            "user_id": 1,
            "system_prompt_hash": "",
            "model": "",
            "created_at": now_ts,
            "hit_count": 2,
            "response": "cached response",
        }]],
        "distances": [[0.05]],  # cosine distance < 0.10 → similarity > 0.90
    }
    result = await cache.lookup(user_id=1, query="hello")
    assert result is not None
    assert result.response == "cached response"
    assert result.hit_count == 2


@pytest.mark.asyncio
async def test_lookup_ttl_expired(cache, mock_chroma_collection):
    """TTL 过期返回 None"""
    old_ts = int((datetime.now(UTC) - timedelta(hours=1)).timestamp())
    mock_chroma_collection.query.return_value = {
        "ids": [["id1"]],
        "documents": [["hello"]],
        "metadatas": [[{
            "user_id": 1,
            "created_at": old_ts,
            "hit_count": 0,
            "response": "old response",
        }]],
        "distances": [[0.05]],
    }
    result = await cache.lookup(user_id=1, query="hello")
    assert result is None


@pytest.mark.asyncio
async def test_lookup_low_similarity_miss(cache, mock_chroma_collection):
    """相似度低于阈值返回 None"""
    now_ts = int(datetime.now(UTC).timestamp())
    mock_chroma_collection.query.return_value = {
        "ids": [["id1"]],
        "documents": [["hello"]],
        "metadatas": [[{
            "user_id": 1,
            "created_at": now_ts,
            "hit_count": 0,
            "response": "cached",
        }]],
        "distances": [[0.5]],  # similarity = 0.5 < 0.90
    }
    result = await cache.lookup(user_id=1, query="hello")
    assert result is None


@pytest.mark.asyncio
async def test_store_writes_to_chroma(cache, mock_chroma_collection):
    """store 写入 ChromaDB"""
    await cache.store(
        user_id=1,
        query="hello",
        response="world",
        system_prompt_hash="abc",
        model="qwen",
    )
    mock_chroma_collection.add.assert_called_once()
    call_kwargs = mock_chroma_collection.add.call_args[1]
    assert call_kwargs["metadatas"][0]["user_id"] == 1
    assert call_kwargs["metadatas"][0]["response"] == "world"


@pytest.mark.asyncio
async def test_store_fifo_eviction(cache, mock_chroma_collection):
    """超过 max_entries 时删除最旧的"""
    # 模拟用户已有 1000 条
    mock_chroma_collection.get.return_value = {
        "ids": [f"id_{i}" for i in range(1000)],
        "metadatas": [{"created_at": i, "user_id": 1} for i in range(1000)],
    }
    await cache.store(user_id=1, query="new", response="response")
    # 应删除最旧的（id_0）
    mock_chroma_collection.delete.assert_called()


@pytest.mark.asyncio
async def test_invalidate_user(cache, mock_chroma_collection):
    """清空用户缓存"""
    await cache.invalidate_user(user_id=123)
    mock_chroma_collection.delete.assert_called_once_with(where={"user_id": 123})


@pytest.mark.asyncio
async def test_stats(cache, mock_chroma_collection):
    """统计信息"""
    mock_chroma_collection.get.return_value = {
        "ids": ["id1", "id2", "id3"],
        "metadatas": [
            {"hit_count": 5, "user_id": 1},
            {"hit_count": 0, "user_id": 1},
            {"hit_count": 2, "user_id": 1},
        ],
    }
    stats = await cache.stats(user_id=1)
    assert stats["total_entries"] == 3
    assert stats["total_hits"] == 7


@pytest.mark.asyncio
async def test_system_prompt_isolation(cache, mock_chroma_collection):
    """不同 system_prompt_hash 不命中"""
    mock_chroma_collection.query.return_value = {
        "ids": [[]],
        "documents": [[]],
        "metadatas": [[]],
        "distances": [[]],
    }
    # system_prompt_hash="abc" 查询，ChromaDB where 过滤后无结果
    result = await cache.lookup(
        user_id=1,
        query="hello",
        system_prompt_hash="abc",
    )
    # 验证 query 调用时 where 包含 system_prompt_hash
    call_kwargs = mock_chroma_collection.query.call_args[1]
    assert call_kwargs["where"]["system_prompt_hash"] == "abc"
    assert result is None


@pytest.mark.asyncio
async def test_model_isolation(cache, mock_chroma_collection):
    """不同 model 不命中"""
    mock_chroma_collection.query.return_value = {
        "ids": [[]],
        "documents": [[]],
        "metadatas": [[]],
        "distances": [[]],
    }
    await cache.lookup(user_id=1, query="hello", model="qwen2.5-14b")
    call_kwargs = mock_chroma_collection.query.call_args[1]
    assert call_kwargs["where"]["model"] == "qwen2.5-14b"
