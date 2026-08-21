"""测试引擎抽象基类"""
import pytest
from app.engines.base import (
    BaseEngine,
    ImageGenProvider,
    TTSProvider,
    LLMProvider,
    GenerationResult,
)
from app.core.storage import FileStorage


def test_generation_result_dataclass():
    """测试 GenerationResult 数据类"""
    result = GenerationResult(
        success=True,
        data=b"fake-image",
        content_type="image/png",
        metadata={"model": "test"},
    )
    assert result.success is True
    assert result.data == b"fake-image"
    assert result.content_type == "image/png"
    assert result.error is None


def test_generation_result_with_error():
    """测试 GenerationResult 错误情况"""
    result = GenerationResult(
        success=False,
        data=b"",
        content_type="",
        metadata={},
        error="生成失败",
    )
    assert result.success is False
    assert result.error == "生成失败"


def test_image_gen_provider_is_abstract():
    """测试 ImageGenProvider 不能直接实例化"""
    with pytest.raises(TypeError):
        ImageGenProvider()


def test_tts_provider_is_abstract():
    """测试 TTSProvider 不能直接实例化"""
    with pytest.raises(TypeError):
        TTSProvider()


def test_llm_provider_is_abstract():
    """测试 LLMProvider 不能直接实例化"""
    with pytest.raises(TypeError):
        LLMProvider()


def test_file_storage_save_and_read(tmp_path):
    """测试文件存储"""
    storage = FileStorage(base_dir=str(tmp_path))
    data = b"test content"
    url = storage.save(data, extension="txt")

    assert url.startswith("/uploads/")
    assert url.endswith(".txt")

    # 完整路径存在
    full_path = storage.get_full_path(url)
    assert full_path.exists()
    assert full_path.read_bytes() == data


def test_file_storage_exists_and_delete(tmp_path):
    """测试文件存储存在与删除"""
    storage = FileStorage(base_dir=str(tmp_path))
    url = storage.save(b"data", filename="test.txt")

    assert storage.exists(url) is True
    assert storage.delete(url) is True
    assert storage.exists(url) is False


def test_base_engine_has_init_error_field():
    """BaseEngine 应有 _init_error 字段，默认 None"""
    from app.engines.base import BaseEngine
    # 通过子类实例化（BaseEngine 是 ABC）
    class _TestEngine(BaseEngine):
        name = "test"
        async def initialize(self): pass
        async def health_check(self): return True

    e = _TestEngine()
    assert hasattr(e, "_init_error")
    assert e._init_error is None


def test_base_engine_init_error_settable():
    """_init_error 可设置"""
    from app.engines.base import BaseEngine
    class _TestEngine(BaseEngine):
        name = "test"
        async def initialize(self): pass
        async def health_check(self): return True

    e = _TestEngine()
    e._init_error = "vllm not installed"
    assert e._init_error == "vllm not installed"
