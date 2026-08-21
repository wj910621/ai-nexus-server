"""测试 EngineManager 引擎管理器（使用 mock，不依赖真实网络/外部资源）"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.engines.manager import EngineManager


def _make_mock_engine(name: str = "mock", healthy: bool = True):
    """构造一个 mock 引擎实例

    - initialize() 为 AsyncMock
    - health_check() 为 AsyncMock，默认返回 healthy
    - get_info() 返回包含 name 的字典
    """
    engine = MagicMock()
    engine.name = name
    engine.display_name = f"Mock {name}"
    engine._initialized = False
    engine.initialize = AsyncMock(side_effect=lambda: setattr(engine, "_initialized", True))
    engine.health_check = AsyncMock(return_value=healthy)
    engine.get_info = MagicMock(
        return_value={
            "name": name,
            "display_name": f"Mock {name}",
            "initialized": True,
        }
    )
    return engine


def _patch_all_providers(
    image_engine=None,
    tts_engine=None,
    llm_engine=None,
    video_engine=None,
    character_engine=None,
):
    """返回一个 dict，包含对 5 个 get_default_provider 的 patcher

    用法：
        patches = _patch_all_providers()
        for p in patches.values():
            p.start()
        try:
            ...
        finally:
            for p in patches.values():
                p.stop()
    """
    return {
        "image": patch(
            "app.engines.manager.get_default_image_provider",
            return_value=image_engine or _make_mock_engine("pollinations"),
        ),
        "tts": patch(
            "app.engines.manager.get_default_tts_provider",
            return_value=tts_engine or _make_mock_engine("edge-tts"),
        ),
        "llm": patch(
            "app.engines.manager.get_default_llm_provider",
            return_value=llm_engine or _make_mock_engine("deepseek"),
        ),
        "video": patch(
            "app.engines.manager.get_default_video_provider",
            return_value=video_engine or _make_mock_engine("ffmpeg"),
        ),
        "character": patch(
            "app.engines.manager.get_default_character_provider",
            return_value=character_engine or _make_mock_engine("soft-consistency"),
        ),
    }


def test_manager_init():
    """测试 EngineManager 初始化状态"""
    manager = EngineManager()
    assert manager.ENGINE_TYPES == ["image", "tts", "llm", "video", "character"]
    assert len(manager.ENGINE_TYPES) == 5
    assert manager._engines == {}
    assert manager._initialized is False
    assert manager._init_errors == {}


@pytest.mark.asyncio
async def test_manager_initialize():
    """测试 initialize 后 5 个引擎都创建并初始化"""
    manager = EngineManager()
    patches = _patch_all_providers()
    for p in patches.values():
        p.start()
    try:
        await manager.initialize()
        # 5 个引擎都创建
        assert len(manager._engines) == 5
        for engine_type in manager.ENGINE_TYPES:
            assert engine_type in manager._engines
            engine = manager._engines[engine_type]
            # initialize 被调用一次
            engine.initialize.assert_awaited_once()
        # 状态正确
        assert manager._initialized is True
        assert manager._init_errors == {}
    finally:
        for p in patches.values():
            p.stop()


@pytest.mark.asyncio
async def test_initialize_with_partial_failure():
    """测试单个引擎初始化失败不影响其他引擎"""
    manager = EngineManager()

    # 让 image provider 的 initialize 抛异常
    bad_image = _make_mock_engine("pollinations")
    bad_image.initialize = AsyncMock(side_effect=RuntimeError("image init failed"))

    patches = _patch_all_providers(image_engine=bad_image)
    for p in patches.values():
        p.start()
    try:
        await manager.initialize()
        # image 失败，其他 4 个成功
        assert len(manager._engines) == 4
        assert "image" not in manager._engines
        for engine_type in ["tts", "llm", "video", "character"]:
            assert engine_type in manager._engines
        # 错误被记录
        assert "image" in manager._init_errors
        assert "image init failed" in manager._init_errors["image"]
        # 整体初始化标志仍为 True
        assert manager._initialized is True
    finally:
        for p in patches.values():
            p.stop()


@pytest.mark.asyncio
async def test_get_engine():
    """测试 get_engine 方法"""
    manager = EngineManager()
    patches = _patch_all_providers()
    for p in patches.values():
        p.start()
    try:
        await manager.initialize()
        assert manager.get_engine("image") is not None
        assert manager.get_engine("nonexistent") is None
    finally:
        for p in patches.values():
            p.stop()


@pytest.mark.asyncio
async def test_get_engine_shortcuts():
    """测试便捷方法 get_image_engine 等"""
    manager = EngineManager()
    patches = _patch_all_providers()
    for p in patches.values():
        p.start()
    try:
        await manager.initialize()
        assert manager.get_image_engine() is manager._engines["image"]
        assert manager.get_tts_engine() is manager._engines["tts"]
        assert manager.get_llm_engine() is manager._engines["llm"]
        assert manager.get_video_engine() is manager._engines["video"]
        assert manager.get_character_engine() is manager._engines["character"]
    finally:
        for p in patches.values():
            p.stop()


@pytest.mark.asyncio
async def test_set_engine():
    """测试运行时切换 Provider"""
    manager = EngineManager()
    patches = _patch_all_providers()
    for p in patches.values():
        p.start()
    try:
        await manager.initialize()
        original = manager.get_engine("image")

        # 切换为新引擎
        new_engine = _make_mock_engine("custom-image")
        await manager.set_engine("image", new_engine)

        # 替换成功
        assert manager.get_engine("image") is new_engine
        assert manager.get_engine("image") is not original
        # 新引擎的 initialize 被调用
        new_engine.initialize.assert_awaited_once()
    finally:
        for p in patches.values():
            p.stop()


@pytest.mark.asyncio
async def test_health_check_all():
    """测试 health_check_all 返回正确字典"""
    manager = EngineManager()

    # 构造已知健康状态的 mock 引擎
    image = _make_mock_engine("pollinations", healthy=True)
    tts = _make_mock_engine("edge-tts", healthy=True)
    llm = _make_mock_engine("deepseek", healthy=False)
    video = _make_mock_engine("ffmpeg", healthy=True)
    character = _make_mock_engine("soft-consistency", healthy=True)

    patches = _patch_all_providers(
        image_engine=image,
        tts_engine=tts,
        llm_engine=llm,
        video_engine=video,
        character_engine=character,
    )
    for p in patches.values():
        p.start()
    try:
        await manager.initialize()
        results = await manager.health_check_all()
        assert results == {
            "image": True,
            "tts": True,
            "llm": False,
            "video": True,
            "character": True,
        }
    finally:
        for p in patches.values():
            p.stop()


@pytest.mark.asyncio
async def test_get_all_info():
    """测试 get_all_info 返回所有引擎信息"""
    manager = EngineManager()
    patches = _patch_all_providers()
    for p in patches.values():
        p.start()
    try:
        await manager.initialize()
        all_info = await manager.get_all_info()
        # 5 个引擎信息都在
        assert len(all_info) == 5
        for engine_type in manager.ENGINE_TYPES:
            assert engine_type in all_info
            info = all_info[engine_type]
            assert "name" in info
            assert "display_name" in info
            assert "initialized" in info
    finally:
        for p in patches.values():
            p.stop()


@pytest.mark.asyncio
async def test_get_status():
    """测试 get_status 返回正确的状态摘要"""
    manager = EngineManager()
    patches = _patch_all_providers()
    for p in patches.values():
        p.start()
    try:
        # 初始化前
        status = await manager.get_status()
        assert status["initialized"] is False
        assert status["engine_count"] == 0
        assert status["engine_types"] == []
        assert status["init_errors"] == {}

        await manager.initialize()

        # 初始化后
        status = await manager.get_status()
        assert status["initialized"] is True
        assert status["engine_count"] == 5
        assert sorted(status["engine_types"]) == sorted(
            ["image", "tts", "llm", "video", "character"]
        )
        assert status["init_errors"] == {}
    finally:
        for p in patches.values():
            p.stop()
