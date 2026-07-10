"""
向量搜索服务单元测试
覆盖余弦相似度计算和文档相似性搜索
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestVectorService:
    def test_cosine_similarity_identical(self):
        from app.services.vector import cosine
        a = [1.0, 0.0, 0.0]
        b = [1.0, 0.0, 0.0]
        result = cosine(a, b)
        assert abs(result - 1.0) < 0.0001

    def test_cosine_similarity_opposite(self):
        from app.services.vector import cosine
        a = [1.0, 0.0, 0.0]
        b = [-1.0, 0.0, 0.0]
        result = cosine(a, b)
        assert abs(result + 1.0) < 0.0001

    def test_cosine_similarity_perpendicular(self):
        from app.services.vector import cosine
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        result = cosine(a, b)
        assert abs(result) < 0.0001

    def test_cosine_similarity_empty(self):
        from app.services.vector import cosine
        result = cosine([], [])
        assert result == 0.0

    def test_cosine_similarity_zero_norm(self):
        from app.services.vector import cosine
        result = cosine([0.0, 0.0], [0.0, 0.0])
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_search_similar_empty_docs(self):
        with patch("app.services.vector.get_embeddings", new=AsyncMock(return_value=[1.0, 0.0, 0.0])):
            from app.services.vector import search_similar
            results = await search_similar("test query", [], top_k=3)
            assert results == []

    @pytest.mark.asyncio
    async def test_search_similar_no_embedding(self):
        with patch("app.services.vector.get_embeddings", new=AsyncMock(return_value=[1.0, 0.0, 0.0])):
            from app.services.vector import search_similar
            doc1 = MagicMock()
            doc1.embedding = None
            doc2 = MagicMock()
            doc2.embedding = None
            results = await search_similar("test query", [doc1, doc2], top_k=3)
            assert results == []

    @pytest.mark.asyncio
    async def test_search_similar_with_docs(self):
        with patch("app.services.vector.get_embeddings", new=AsyncMock(return_value=[1.0, 0.0, 0.0])):
            from app.services.vector import search_similar
            doc1 = MagicMock()
            doc1.embedding = '[1.0, 0.0, 0.0]'
            doc2 = MagicMock()
            doc2.embedding = '[0.5, 0.0, 0.0]'
            doc3 = MagicMock()
            doc3.embedding = '[0.0, 1.0, 0.0]'
            results = await search_similar("test query", [doc1, doc2, doc3], top_k=2)
            assert len(results) == 2
            assert results[0][0] == doc1
            assert results[1][0] == doc2

    @pytest.mark.asyncio
    async def test_search_similar_invalid_embedding(self):
        with patch("app.services.vector.get_embeddings", new=AsyncMock(return_value=[1.0, 0.0, 0.0])):
            from app.services.vector import search_similar
            doc1 = MagicMock()
            doc1.embedding = 'invalid_json'
            results = await search_similar("test query", [doc1], top_k=3)
            assert results == []

    @pytest.mark.asyncio
    async def test_search_similar_no_query_embedding(self):
        with patch("app.services.vector.get_embeddings", new=AsyncMock(return_value=[])):
            from app.services.vector import search_similar
            doc1 = MagicMock()
            doc1.embedding = '[1.0, 0.0, 0.0]'
            results = await search_similar("test query", [doc1], top_k=3)
            assert results == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
