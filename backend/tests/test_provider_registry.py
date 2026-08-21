"""Tests for ProviderRegistry."""
import pytest
from app.engines.registry import ProviderRegistry
from app.engines.base import BaseEngine


class _FakeProvider(BaseEngine):
    name = "fake"
    display_name = "Fake Provider"

    async def initialize(self):
        pass

    async def health_check(self):
        return True


@pytest.fixture(autouse=True)
def _reset_registry():
    """每个测试前后清空注册表，保证隔离"""
    for engine_type in list(ProviderRegistry._registry.keys()):
        ProviderRegistry._registry[engine_type] = {}
    yield
    for engine_type in list(ProviderRegistry._registry.keys()):
        ProviderRegistry._registry[engine_type] = {}


def test_register_and_get():
    """注册 Provider 后能按 engine_type + name 获取"""
    ProviderRegistry.register("image", "fake", _FakeProvider)
    cls = ProviderRegistry.get("image", "fake")
    assert cls is _FakeProvider


def test_list_providers_by_engine_type():
    """list_providers 返回指定引擎类型的所有 Provider 名"""
    ProviderRegistry.register("image", "fake", _FakeProvider)
    ProviderRegistry.register("image", "another", _FakeProvider)
    names = ProviderRegistry.list_providers("image")
    assert sorted(names) == ["another", "fake"]


def test_list_all_returns_all_engine_types():
    """list_all 返回所有引擎类型的 Provider 名字典"""
    ProviderRegistry.register("image", "fake", _FakeProvider)
    ProviderRegistry.register("llm", "fake-llm", _FakeProvider)
    result = ProviderRegistry.list_all()
    assert "image" in result
    assert "llm" in result
    assert "fake" in result["image"]
    assert "fake-llm" in result["llm"]


def test_register_unknown_engine_type_raises():
    """未知 engine_type 注册时抛 ValueError"""
    with pytest.raises(ValueError, match="未知引擎类型"):
        ProviderRegistry.register("unknown", "fake", _FakeProvider)


def test_get_unknown_provider_raises_keyerror():
    """获取未注册的 Provider 抛 KeyError"""
    with pytest.raises(KeyError, match="未注册的 Provider"):
        ProviderRegistry.get("image", "nonexistent")


def test_get_unknown_engine_type_returns_empty():
    """未知 engine_type 的 get 抛 KeyError"""
    with pytest.raises(KeyError):
        ProviderRegistry.get("unknown", "fake")


def test_list_providers_unknown_engine_type_returns_empty():
    """未知 engine_type 的 list_providers 返回空列表"""
    assert ProviderRegistry.list_providers("unknown") == []


def test_register_overwrites_existing():
    """重复注册同名 Provider 覆盖旧的"""
    ProviderRegistry.register("image", "fake", _FakeProvider)

    class _NewProvider(_FakeProvider):
        name = "new-fake"

    ProviderRegistry.register("image", "fake", _NewProvider)
    assert ProviderRegistry.get("image", "fake") is _NewProvider
