"""Tests for EmbeddingService (bge-m3 lazy loading)."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from app.core.embedding_service import EmbeddingService


@pytest.fixture
def service():
    return EmbeddingService(model_cache_dir="data/test-models/bge-m3")


@pytest.mark.asyncio
async def test_lazy_loading(service):
    """模型懒加载：首次调用 initialize 才加载"""
    assert service._model is None
    with patch("app.core.embedding_service.SentenceTransformer") as mock_st:
        mock_st.return_value = MagicMock()
        await service.initialize()
        mock_st.assert_called_once()
        assert service._model is not None


@pytest.mark.asyncio
async def test_encode_single_text(service):
    """编码单个文本返回 1024 维向量"""
    with patch("app.core.embedding_service.SentenceTransformer") as mock_st:
        mock_model = MagicMock()
        mock_model.encode.return_value = MagicMock(
            tolist=lambda: [0.1] * 1024
        )
        mock_st.return_value = mock_model
        await service.initialize()
        vec = await service.encode("hello world")
        assert len(vec) == 1024
        mock_model.encode.assert_called_once()


@pytest.mark.asyncio
async def test_encode_batch(service):
    """批量编码多个文本"""
    with patch("app.core.embedding_service.SentenceTransformer") as mock_st:
        mock_model = MagicMock()
        mock_model.encode.return_value = MagicMock(
            tolist=lambda: [[0.1] * 1024, [0.2] * 1024]
        )
        mock_st.return_value = mock_model
        await service.initialize()
        vecs = await service.encode_batch(["hello", "world"])
        assert len(vecs) == 2
        assert len(vecs[0]) == 1024


@pytest.mark.asyncio
async def test_health_check_success(service):
    """健康检查成功"""
    with patch("app.core.embedding_service.SentenceTransformer") as mock_st:
        mock_st.return_value = MagicMock()
        result = await service.health_check()
        assert result is True


@pytest.mark.asyncio
async def test_health_check_failure(service):
    """模型加载失败时健康检查返回 False"""
    with patch("app.core.embedding_service.SentenceTransformer", side_effect=RuntimeError("download failed")):
        result = await service.health_check()
        assert result is False
