"""Phase 2 端到端集成测试 - 串联 5 个 AI 引擎与 API 路由

验证完整业务流程：文生图、TTS、LLM、视频合成、角色一致性。
覆盖引擎管理：初始化、健康检查、运行时切换、故障恢复。

测试策略：
- 引擎层测试：直接构造 EngineManager 实例，patch 5 个 get_default_provider
  函数返回 mock provider，验证 EngineManager 的生命周期/故障恢复/切换能力。
- API 层测试：使用 httpx.AsyncClient + ASGITransport 调用真实路由，
  通过 `app.dependency_overrides[get_current_user]` 跳过认证，
  通过 `patch("app.api.ai.engine_manager", mock_manager)` 注入 mock 引擎管理器。
- 所有外部调用（HTTP/ffmpeg/edge-tts/DeepSeek）均被 mock，零网络依赖。
"""
import base64

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch

from app.engines.base import GenerationResult
from app.engines.manager import EngineManager


# === 共享 Fixtures ===
@pytest.fixture(autouse=True)
def _mock_cache_and_dedup():
    """Patch result_cache_service + request_deduplicator for all tests in this module.

    Task 9 added cache+dedup wrappers around /text2img, /tts, /chat endpoints.
    The existing engine-mock tests don't use a real DB, so the cache service
    would try to hit PostgreSQL and fail. This fixture makes both dependencies
    no-ops: cache always misses, dedup just calls the wrapped function.
    """
    async def _passthrough(func, *args, **kwargs):
        return await func(*args, **kwargs)

    mock_cache = MagicMock()
    mock_cache.get = AsyncMock(return_value=None)  # always miss
    mock_cache.set = AsyncMock(return_value=None)
    mock_cache.LLM_TTL_SECONDS = 1800

    mock_dedup = MagicMock()
    mock_dedup.deduplicate = _passthrough  # type: ignore[assignment]

    with patch("app.api.ai.result_cache_service", mock_cache), \
         patch("app.api.ai.request_deduplicator", mock_dedup):
        yield


@pytest.fixture
def mock_user():
    """模拟已认证用户"""
    user = MagicMock()
    user.id = "test-user-id"
    user.username = "testuser"
    user.status = "active"
    # Phase 6: admin bypasses credit deduction so mocked endpoints don't touch DB
    user.role = "admin"
    user.credits = 0
    return user


@pytest.fixture
def auth_bypass(mock_user):
    """通过 FastAPI dependency_overrides 跳过认证

    必须用 dependency_overrides 而非 patch，因为 Depends(get_current_user)
    在路由注册时已绑定到原始函数对象。
    """
    from app.main import app
    from app.core.deps import get_current_user

    async def _override():
        return mock_user

    app.dependency_overrides[get_current_user] = _override
    yield
    app.dependency_overrides.pop(get_current_user, None)


# === 引擎层 mock 工具 ===
def _make_mock_engine(name: str = "mock", healthy: bool = True):
    """构造一个 mock 引擎实例

    - initialize() 为 AsyncMock，调用后 _initialized 置 True
    - health_check() 为 AsyncMock，返回 healthy
    - get_info() 返回包含 name/display_name/initialized 的字典
    """
    engine = MagicMock()
    engine.name = name
    engine.display_name = f"Mock {name}"
    engine._initialized = False
    engine.initialize = AsyncMock(
        side_effect=lambda: setattr(engine, "_initialized", True)
    )
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


# === API 层 mock 工具 ===
def _make_mock_engine_manager() -> MagicMock:
    """构造 mock engine_manager，覆盖 5 个引擎的所有方法

    每个生成方法返回一个成功的 GenerationResult，便于断言。
    """
    manager = MagicMock()
    manager.ENGINE_TYPES = ["image", "tts", "llm", "video", "character"]

    # 路由组件就绪（_resolve_engine 会走 get_engine_routed 分支）
    manager._router = MagicMock()
    manager._quota_guard = MagicMock()

    # get_all_info - 5 个引擎信息
    manager.get_all_info = AsyncMock(return_value={
        "image": {
            "name": "pollinations",
            "display_name": "Pollinations.ai (免费)",
            "initialized": True,
        },
        "tts": {
            "name": "edge-tts",
            "display_name": "Edge TTS (微软免费)",
            "initialized": True,
        },
        "llm": {
            "name": "deepseek",
            "display_name": "DeepSeek",
            "initialized": True,
        },
        "video": {
            "name": "ffmpeg",
            "display_name": "FFmpeg",
            "initialized": True,
        },
        "character": {
            "name": "soft-consistency",
            "display_name": "软一致性",
            "initialized": True,
        },
    })

    # get_status
    manager.get_status = AsyncMock(return_value={
        "initialized": True,
        "engine_count": 5,
        "engine_types": ["image", "tts", "llm", "video", "character"],
        "init_errors": {},
    })

    # health_check_one - 默认返回 True
    manager.health_check_one = AsyncMock(return_value=True)

    # image engine
    image_engine = AsyncMock()
    image_engine.text2img = AsyncMock(
        return_value=GenerationResult(
            success=True,
            data="/uploads/images/test.png",
            content_type="image/png",
            metadata={"model": "flux", "width": 512, "height": 512},
        )
    )
    manager.get_image_engine.return_value = image_engine

    # tts engine
    tts_engine = AsyncMock()
    tts_engine.synthesize = AsyncMock(
        return_value=GenerationResult(
            success=True,
            data="/uploads/audio/test.mp3",
            content_type="audio/mp3",
            metadata={"voice": "zh-CN-XiaoxiaoNeural"},
        )
    )
    tts_engine.list_voices = AsyncMock(
        return_value=[
            {
                "ShortName": "zh-CN-XiaoxiaoNeural",
                "FriendlyName": "Xiaoxiao (Female)",
                "Locale": "zh-CN",
            },
            {
                "ShortName": "en-US-JennyNeural",
                "FriendlyName": "Jenny (Female)",
                "Locale": "en-US",
            },
        ]
    )
    manager.get_tts_engine.return_value = tts_engine

    # llm engine
    llm_engine = AsyncMock()
    llm_engine.chat = AsyncMock(
        return_value=GenerationResult(
            success=True,
            data="enhanced prompt: a cute cat sitting on a windowsill",
            content_type="text/plain",
            metadata={"model": "deepseek-chat"},
        )
    )
    manager.get_llm_engine.return_value = llm_engine

    # video engine
    video_engine = AsyncMock()
    video_engine.compose = AsyncMock(
        return_value=GenerationResult(
            success=True,
            data="/uploads/videos/test.mp4",
            content_type="video/mp4",
            metadata={"fps": 24, "frames": 2},
        )
    )
    manager.get_video_engine.return_value = video_engine

    # character engine
    character_engine = AsyncMock()
    character_engine.generate_consistent = AsyncMock(
        return_value=GenerationResult(
            success=True,
            data="/uploads/images/char.png",
            content_type="image/png",
            metadata={"consistency_seed": 42},
        )
    )
    manager.get_character_engine.return_value = character_engine

    # get_engine_routed 按 engine_type 返回对应引擎（路由成功路径）
    _engine_by_type = {
        "image": image_engine,
        "tts": tts_engine,
        "llm": llm_engine,
        "video": video_engine,
        "character": character_engine,
    }

    async def _routed(engine_type, user_id, subscription_tier, user_preference="", force_local=False):
        return _engine_by_type.get(engine_type)

    manager.get_engine_routed = AsyncMock(side_effect=_routed)

    return manager


# === 测试用例 ===
@pytest.mark.asyncio
async def test_engine_manager_full_lifecycle():
    """1. EngineManager 完整生命周期

    场景：创建新的 EngineManager 实例（不用全局单例），
    patch 5 个 get_default_provider 返回 mock provider，
    验证 initialize() / health_check_all() / get_all_info() / get_status() 串联通畅。
    """
    manager = EngineManager()
    patches = _patch_all_providers()
    for p in patches.values():
        p.start()
    try:
        # 初始化前状态
        assert manager._initialized is False
        assert len(manager._engines) == 0

        # 执行初始化
        await manager.initialize()

        # 验证 5 个引擎都创建并初始化
        assert len(manager._engines) == 5
        for engine_type in manager.ENGINE_TYPES:
            assert engine_type in manager._engines
            engine = manager._engines[engine_type]
            engine.initialize.assert_awaited_once()

        # 健康检查 - 全部 True
        health_results = await manager.health_check_all()
        assert len(health_results) == 5
        for engine_type in manager.ENGINE_TYPES:
            assert health_results[engine_type] is True
            engine = manager._engines[engine_type]
            engine.health_check.assert_awaited_once()

        # 引擎信息
        all_info = await manager.get_all_info()
        assert len(all_info) == 5
        for engine_type in manager.ENGINE_TYPES:
            assert engine_type in all_info
            info = all_info[engine_type]
            assert "name" in info
            assert "display_name" in info
            assert info["initialized"] is True

        # 整体状态
        status = await manager.get_status()
        assert status["initialized"] is True
        assert status["engine_count"] == 5
        assert sorted(status["engine_types"]) == sorted(manager.ENGINE_TYPES)
        assert status["init_errors"] == {}
    finally:
        for p in patches.values():
            p.stop()


@pytest.mark.asyncio
async def test_engine_manager_partial_failure_recovery():
    """2. 引擎故障恢复

    场景：image provider 的 initialize 抛异常，
    验证其他 4 个引擎仍初始化成功，错误被记录到 _init_errors，
    调用 set_engine 替换失败的引擎后，新引擎正常工作。
    """
    manager = EngineManager()

    # 让 image provider 的 initialize 抛异常
    bad_image = _make_mock_engine("pollinations-broken")
    bad_image.initialize = AsyncMock(side_effect=RuntimeError("image init failed"))

    patches = _patch_all_providers(image_engine=bad_image)
    for p in patches.values():
        p.start()
    try:
        # 初始化 - image 失败，其他 4 个成功
        await manager.initialize()
        assert len(manager._engines) == 4
        assert "image" not in manager._engines
        for engine_type in ["tts", "llm", "video", "character"]:
            assert engine_type in manager._engines

        # 错误被记录
        init_errors = manager.get_init_errors()
        assert "image" in init_errors
        assert "image init failed" in init_errors["image"]

        # 整体初始化标志仍为 True（容错策略）
        assert manager._initialized is True

        # 故障恢复：替换为新引擎
        new_image = _make_mock_engine("pollinations-recovered", healthy=True)
        await manager.set_engine("image", new_image)

        # 验证新引擎已就位
        assert "image" in manager._engines
        assert manager.get_image_engine() is new_image
        new_image.initialize.assert_awaited_once()

        # 错误记录被清除
        init_errors = manager.get_init_errors()
        assert "image" not in init_errors

        # 新引擎健康检查通过
        healthy = await manager.health_check_one("image")
        assert healthy is True

        # 现在所有 5 个引擎都在线
        assert len(manager._engines) == 5
        health_results = await manager.health_check_all()
        assert all(health_results.values())
    finally:
        for p in patches.values():
            p.stop()


@pytest.mark.asyncio
async def test_api_text2img_full_flow(auth_bypass):
    """3. 完整文生图流程

    场景：用户提交 prompt 调用 POST /api/ai/text2img，
    mock image_engine.text2img 返回成功，验证响应结构及参数传递。
    """
    from app.main import app

    mock_manager = _make_mock_engine_manager()
    with patch("app.api.ai.engine_manager", mock_manager):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/ai/text2img",
                json={
                    "prompt": "a cute cat sitting on a windowsill",
                    "negative_prompt": "blurry, low quality",
                    "width": 768,
                    "height": 512,
                    "seed": 42,
                    "model": "flux",
                },
            )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["success"] is True
    assert "/uploads/images/" in data["data"]
    assert data["content_type"] == "image/png"
    assert data["error"] is None

    # 验证 mock 被正确调用
    image_engine = mock_manager.get_image_engine.return_value
    image_engine.text2img.assert_awaited_once()
    call_kwargs = image_engine.text2img.call_args.kwargs
    assert call_kwargs["prompt"] == "a cute cat sitting on a windowsill"
    assert call_kwargs["negative_prompt"] == "blurry, low quality"
    assert call_kwargs["width"] == 768
    assert call_kwargs["height"] == 512
    assert call_kwargs["seed"] == 42
    assert call_kwargs["model"] == "flux"


@pytest.mark.asyncio
async def test_api_chat_to_text2img_workflow(auth_bypass):
    """4. LLM 增强 + 图像生成协作

    场景：用户输入简单描述，先用 LLM 增强提示词，再用增强后的 prompt 生成图像。
    Step 1: POST /api/ai/chat 调用 LLM，返回增强 prompt
    Step 2: 用 LLM 返回的 prompt 调用 POST /api/ai/text2img，生成图像
    验证两次调用都成功，最终图像生成且 prompt 来自 LLM 输出。
    """
    from app.main import app

    mock_manager = _make_mock_engine_manager()
    # LLM 返回的增强 prompt
    enhanced_prompt = "a fluffy orange cat sitting on a sunlit windowsill, " \
                      "soft bokeh background, cinematic lighting"
    mock_manager.get_llm_engine.return_value.chat = AsyncMock(
        return_value=GenerationResult(
            success=True,
            data=enhanced_prompt,
            content_type="text/plain",
            metadata={"model": "deepseek-chat", "tokens": 50},
        )
    )
    # image engine 用 call_args 捕获 prompt，便于断言
    mock_manager.get_image_engine.return_value.text2img = AsyncMock(
        return_value=GenerationResult(
            success=True,
            data="/uploads/images/enhanced_cat.png",
            content_type="image/png",
            metadata={"model": "flux", "enhanced": True},
        )
    )

    with patch("app.api.ai.engine_manager", mock_manager):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Step 1: LLM 增强 prompt
            chat_response = await client.post(
                "/api/ai/chat",
                json={
                    "messages": [
                        {
                            "role": "system",
                            "content": "你是 prompt 增强助手，请将用户输入扩展为详细的图像生成 prompt",
                        },
                        {"role": "user", "content": "a cat on a windowsill"},
                    ],
                    "model": "deepseek-chat",
                    "temperature": 0.7,
                    "max_tokens": 200,
                },
            )
            assert chat_response.status_code == 200
            chat_body = chat_response.json()
            assert chat_body["code"] == 0
            assert chat_body["data"]["success"] is True
            enhanced = chat_body["data"]["data"]
            assert enhanced == enhanced_prompt

            # Step 2: 用 LLM 增强后的 prompt 调用 text2img
            text2img_response = await client.post(
                "/api/ai/text2img",
                json={
                    "prompt": enhanced,
                    "width": 1024,
                    "height": 1024,
                },
            )
            assert text2img_response.status_code == 200
            img_body = text2img_response.json()
            assert img_body["code"] == 0
            assert img_body["data"]["success"] is True
            assert img_body["data"]["data"] == "/uploads/images/enhanced_cat.png"
            assert img_body["data"]["content_type"] == "image/png"

    # 验证 LLM 被正确调用
    llm_engine = mock_manager.get_llm_engine.return_value
    llm_engine.chat.assert_awaited_once()
    llm_kwargs = llm_engine.chat.call_args.kwargs
    assert llm_kwargs["model"] == "deepseek-chat"
    assert llm_kwargs["messages"][0]["role"] == "system"

    # 验证 image engine 收到的是 LLM 增强后的 prompt
    image_engine = mock_manager.get_image_engine.return_value
    image_engine.text2img.assert_awaited_once()
    img_kwargs = image_engine.text2img.call_args.kwargs
    assert img_kwargs["prompt"] == enhanced_prompt
    assert img_kwargs["width"] == 1024


@pytest.mark.asyncio
async def test_api_tts_full_flow(auth_bypass):
    """5. 语音合成完整流程

    场景：用户提交文本调用 POST /api/ai/tts，
    mock tts_engine.synthesize 返回成功，验证响应结构及参数传递。
    """
    from app.main import app

    mock_manager = _make_mock_engine_manager()
    with patch("app.api.ai.engine_manager", mock_manager):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/ai/tts",
                json={
                    "text": "你好世界，欢迎使用漫剧生成软件。",
                    "voice": "zh-CN-XiaoxiaoNeural",
                    "rate": 10,
                    "pitch": 0,
                },
            )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["success"] is True
    assert data["content_type"] == "audio/mp3"
    assert "/uploads/audio/" in data["data"]
    assert data["error"] is None

    # 验证 mock 被正确调用
    tts_engine = mock_manager.get_tts_engine.return_value
    tts_engine.synthesize.assert_awaited_once()
    call_kwargs = tts_engine.synthesize.call_args.kwargs
    assert call_kwargs["text"] == "你好世界，欢迎使用漫剧生成软件。"
    assert call_kwargs["voice"] == "zh-CN-XiaoxiaoNeural"
    assert call_kwargs["rate"] == 10
    assert call_kwargs["pitch"] == 0


@pytest.mark.asyncio
async def test_api_video_compose_full_flow(auth_bypass):
    """6. 视频合成完整流程

    场景：用户提交 frames 列表调用 POST /api/ai/video/compose，
    mock video_engine.compose 返回成功，验证响应结构及参数传递。
    """
    from app.main import app

    mock_manager = _make_mock_engine_manager()
    with patch("app.api.ai.engine_manager", mock_manager):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/ai/video/compose",
                json={
                    "frames": [
                        "/uploads/images/frame1.png",
                        "/uploads/images/frame2.png",
                        "/uploads/images/frame3.png",
                    ],
                    "audio": "/uploads/audio/bgm.mp3",
                    "output_path": "/uploads/videos/scene1.mp4",
                    "fps": 30,
                    "resolution": [1280, 720],
                },
            )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["success"] is True
    assert data["content_type"] == "video/mp4"
    assert "/uploads/videos/" in data["data"]
    assert data["error"] is None

    # 验证 mock 被正确调用
    video_engine = mock_manager.get_video_engine.return_value
    video_engine.compose.assert_awaited_once()
    call_kwargs = video_engine.compose.call_args.kwargs
    assert call_kwargs["frames"] == [
        "/uploads/images/frame1.png",
        "/uploads/images/frame2.png",
        "/uploads/images/frame3.png",
    ]
    assert call_kwargs["audio"] == "/uploads/audio/bgm.mp3"
    assert call_kwargs["output_path"] == "/uploads/videos/scene1.mp4"
    assert call_kwargs["fps"] == 30
    # resolution 应从 list 转为 tuple
    assert call_kwargs["resolution"] == (1280, 720)
    assert isinstance(call_kwargs["resolution"], tuple)


@pytest.mark.asyncio
async def test_api_character_consistency_flow(auth_bypass):
    """7. 角色一致性生成流程

    场景：用户提交 prompt + 参考图调用 POST /api/ai/character/generate，
    mock character_engine.generate_consistent 返回成功，
    验证响应结构及参数传递（reference_image 应被解码为 bytes）。
    """
    from app.main import app

    mock_manager = _make_mock_engine_manager()
    with patch("app.api.ai.engine_manager", mock_manager):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 使用 data URL 格式的 base64 参考图
            b64_data = base64.b64encode(b"fake-reference-image-bytes").decode("ascii")
            response = await client.post(
                "/api/ai/character/generate",
                json={
                    "prompt": "a cute girl with red hair, smiling",
                    "reference_image": f"data:image/png;base64,{b64_data}",
                    "consistency_weight": 0.9,
                    "character_description": "red-haired cheerful girl",
                    "mood": "happy",
                    "width": 768,
                    "height": 768,
                    "seed": 100,
                },
            )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["success"] is True
    assert data["content_type"] == "image/png"
    assert "/uploads/images/" in data["data"]
    assert data["error"] is None

    # 验证 mock 被正确调用
    character_engine = mock_manager.get_character_engine.return_value
    character_engine.generate_consistent.assert_awaited_once()
    call_kwargs = character_engine.generate_consistent.call_args.kwargs
    assert call_kwargs["prompt"] == "a cute girl with red hair, smiling"
    # reference_image 应被解码为 bytes
    assert isinstance(call_kwargs["reference_image"], bytes)
    assert call_kwargs["reference_image"] == b"fake-reference-image-bytes"
    assert call_kwargs["consistency_weight"] == 0.9
    assert call_kwargs["character_description"] == "red-haired cheerful girl"
    assert call_kwargs["mood"] == "happy"
    assert call_kwargs["width"] == 768
    assert call_kwargs["height"] == 768
    assert call_kwargs["seed"] == 100


@pytest.mark.asyncio
async def test_api_engines_management(auth_bypass):
    """8. 引擎管理端到端

    场景：通过 API 调用引擎管理端点，
    - GET /api/ai/engines 验证返回 5 个引擎信息
    - GET /api/ai/engines/status 验证状态正确
    - GET /api/ai/engines/image/health 验证健康检查
    - GET /api/ai/engines/nonexistent/health 验证返回 400
    """
    from app.main import app

    mock_manager = _make_mock_engine_manager()
    with patch("app.api.ai.engine_manager", mock_manager):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1) 获取所有引擎信息
            engines_response = await client.get("/api/ai/engines")
            assert engines_response.status_code == 200
            engines_body = engines_response.json()
            assert engines_body["code"] == 0
            engines = engines_body["data"]
            assert isinstance(engines, list)
            assert len(engines) == 5
            names = [item["name"] for item in engines]
            assert "pollinations" in names
            assert "edge-tts" in names
            assert "deepseek" in names
            assert "ffmpeg" in names
            assert "soft-consistency" in names
            for item in engines:
                assert item["initialized"] is True
                assert "display_name" in item
                assert "extra" in item

            # 2) 获取引擎状态
            status_response = await client.get("/api/ai/engines/status")
            assert status_response.status_code == 200
            status_body = status_response.json()
            assert status_body["code"] == 0
            status = status_body["data"]
            assert status["initialized"] is True
            assert status["engine_count"] == 5
            assert sorted(status["engine_types"]) == sorted(
                ["image", "tts", "llm", "video", "character"]
            )
            assert status["init_errors"] == {}

            # 3) 单引擎健康检查 - image
            health_response = await client.get("/api/ai/engines/image/health")
            assert health_response.status_code == 200
            health_body = health_response.json()
            assert health_body["code"] == 0
            assert health_body["data"]["engine_type"] == "image"
            assert health_body["data"]["healthy"] is True

            # 4) 不存在的引擎类型 - 返回 400
            invalid_response = await client.get(
                "/api/ai/engines/nonexistent/health"
            )
            assert invalid_response.status_code == 400

    # 验证 mock 调用次数
    mock_manager.get_all_info.assert_called_once()
    mock_manager.get_status.assert_called_once()
    # health_check_one 应只被调用 1 次（针对 image），invalid 不应调用
    mock_manager.health_check_one.assert_awaited_once_with("image")


@pytest.mark.asyncio
async def test_engine_runtime_switch():
    """9. 运行时切换 Provider

    场景：创建新的 EngineManager 并初始化，
    mock 一个新的 ImageGenProvider 实例，
    调用 set_engine("image", new_provider) 切换，
    验证 get_image_engine() 返回新实例且新引擎 initialize 被调用。
    """
    manager = EngineManager()
    patches = _patch_all_providers()
    for p in patches.values():
        p.start()
    try:
        await manager.initialize()
        original_image = manager.get_image_engine()
        assert original_image is not None

        # 切换为新引擎
        new_image = _make_mock_engine("custom-image-provider", healthy=True)
        await manager.set_engine("image", new_image)

        # 验证 get_image_engine 返回新实例
        assert manager.get_image_engine() is new_image
        assert manager.get_image_engine() is not original_image
        # 新引擎的 initialize 被调用
        new_image.initialize.assert_awaited_once()

        # 引擎总数仍为 5
        assert len(manager._engines) == 5

        # 切换后健康检查通过
        healthy = await manager.health_check_one("image")
        assert healthy is True

        # 整体健康检查全部通过
        all_health = await manager.health_check_all()
        assert all_health["image"] is True
        assert all(all_health.values())

        # 错误记录为空
        assert manager.get_init_errors() == {}
    finally:
        for p in patches.values():
            p.stop()


@pytest.mark.asyncio
async def test_generation_result_data_consistency(auth_bypass):
    """10. GenerationResult 数据一致性

    场景：mock 5 个引擎返回结构一致的 GenerationResult，
    通过 API 调用各生成端点，验证响应 schema 一致
    （都包含 success, data, content_type, metadata, error 字段）。
    """
    from app.main import app

    mock_manager = _make_mock_engine_manager()
    with patch("app.api.ai.engine_manager", mock_manager):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1) text2img
            r1 = await client.post(
                "/api/ai/text2img",
                json={"prompt": "test image", "width": 512, "height": 512},
            )
            assert r1.status_code == 200
            d1 = r1.json()["data"]
            assert set(d1.keys()) >= {
                "success", "data", "content_type", "metadata", "error"
            }
            assert d1["success"] is True
            assert d1["content_type"] == "image/png"
            assert isinstance(d1["metadata"], dict)

            # 2) tts
            r2 = await client.post(
                "/api/ai/tts",
                json={"text": "hello", "voice": "zh-CN-XiaoxiaoNeural"},
            )
            assert r2.status_code == 200
            d2 = r2.json()["data"]
            assert set(d2.keys()) >= {
                "success", "data", "content_type", "metadata", "error"
            }
            assert d2["success"] is True
            assert d2["content_type"] == "audio/mp3"
            assert isinstance(d2["metadata"], dict)

            # 3) chat
            r3 = await client.post(
                "/api/ai/chat",
                json={"messages": [{"role": "user", "content": "hi"}]},
            )
            assert r3.status_code == 200
            d3 = r3.json()["data"]
            assert set(d3.keys()) >= {
                "success", "data", "content_type", "metadata", "error"
            }
            assert d3["success"] is True
            assert d3["content_type"] == "text/plain"
            assert isinstance(d3["metadata"], dict)

            # 4) video/compose
            r4 = await client.post(
                "/api/ai/video/compose",
                json={"frames": ["/uploads/images/f1.png"]},
            )
            assert r4.status_code == 200
            d4 = r4.json()["data"]
            assert set(d4.keys()) >= {
                "success", "data", "content_type", "metadata", "error"
            }
            assert d4["success"] is True
            assert d4["content_type"] == "video/mp4"
            assert isinstance(d4["metadata"], dict)

            # 5) character/generate
            b64_data = base64.b64encode(b"ref").decode("ascii")
            r5 = await client.post(
                "/api/ai/character/generate",
                json={
                    "prompt": "a character",
                    "reference_image": f"data:image/png;base64,{b64_data}",
                },
            )
            assert r5.status_code == 200
            d5 = r5.json()["data"]
            assert set(d5.keys()) >= {
                "success", "data", "content_type", "metadata", "error"
            }
            assert d5["success"] is True
            assert d5["content_type"] == "image/png"
            assert isinstance(d5["metadata"], dict)

    # 验证所有 5 个引擎都被调用过
    mock_manager.get_image_engine.return_value.text2img.assert_awaited_once()
    mock_manager.get_tts_engine.return_value.synthesize.assert_awaited_once()
    mock_manager.get_llm_engine.return_value.chat.assert_awaited_once()
    mock_manager.get_video_engine.return_value.compose.assert_awaited_once()
    mock_manager.get_character_engine.return_value.generate_consistent.assert_awaited_once()
