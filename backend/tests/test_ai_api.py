"""AI API 路由测试

测试覆盖 9 个端点 + 1 个未认证场景，共 10 个测试用例。
所有引擎层均通过 mock 注入，不依赖真实网络/外部资源。

Mock 策略：
- 认证：通过 `app.dependency_overrides[get_current_user]` 覆盖依赖
  （`Depends(get_current_user)` 在路由注册时已捕获函数引用，
  仅 patch 模块属性不会生效）
- 引擎管理器：通过 `patch("app.api.ai.engine_manager", mock_manager)` 注入
  （`engine_manager` 在路由函数体内运行时访问，可直接 patch）
- Task 9: cache 与 dedup 也需 patch，避免命中真实 PostgreSQL
  （`result_cache_service` 在路由函数体内运行时访问，可直接 patch）
"""
import base64

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch

from app.engines.base import GenerationResult


# === Fixtures ===
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


def _make_mock_engine_manager() -> MagicMock:
    """构造 mock engine_manager，覆盖 5 个引擎的所有方法

    每个生成方法返回一个成功的 GenerationResult，便于断言。
    商业化瘦身（2026-09-02）：mock 路由组件与 get_engine_routed。
    默认 get_engine_routed 返回 None（路由未命中）→ _resolve_engine
    回退到单例引擎，保持各端点行为不变。
    """
    manager = MagicMock()
    manager.ENGINE_TYPES = ["image", "tts", "llm", "video", "character"]
    # 路由组件就绪（_resolve_engine 会走 get_engine_routed 分支）
    manager._router = MagicMock()
    manager._quota_guard = MagicMock()
    # get_engine_routed 按 engine_type 返回对应引擎（定义见文件底部 fixture）

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
            data="你好！我是 AI 助手。",
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
async def test_get_engines_without_auth():
    """1. 无 token 访问 /ai/engines 返回 401"""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/ai/engines")
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_engines(auth_bypass):
    """2. 跳过认证，mock get_all_info，验证返回引擎列表"""
    from app.main import app
    mock_manager = _make_mock_engine_manager()
    with patch("app.api.ai.engine_manager", mock_manager):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/ai/engines")
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert isinstance(data["data"], list)
            assert len(data["data"]) == 5
            names = [item["name"] for item in data["data"]]
            assert "pollinations" in names
            assert "edge-tts" in names
            # 验证字段结构
            for item in data["data"]:
                assert "name" in item
                assert "display_name" in item
                assert "initialized" in item
                assert "extra" in item
                assert item["initialized"] is True
            mock_manager.get_all_info.assert_called_once()


@pytest.mark.asyncio
async def test_get_engine_status(auth_bypass):
    """3. 验证 /ai/engines/status 返回引擎整体状态"""
    from app.main import app
    mock_manager = _make_mock_engine_manager()
    with patch("app.api.ai.engine_manager", mock_manager):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/ai/engines/status")
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            status = data["data"]
            assert status["initialized"] is True
            assert status["engine_count"] == 5
            assert sorted(status["engine_types"]) == sorted(
                ["image", "tts", "llm", "video", "character"]
            )
            assert status["init_errors"] == {}
            mock_manager.get_status.assert_called_once()


@pytest.mark.asyncio
async def test_engine_health_check(auth_bypass):
    """4. mock health_check_one 返回 True，验证 /ai/engines/image/health"""
    from app.main import app
    mock_manager = _make_mock_engine_manager()
    with patch("app.api.ai.engine_manager", mock_manager):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/ai/engines/image/health")
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert data["data"]["engine_type"] == "image"
            assert data["data"]["healthy"] is True
            mock_manager.health_check_one.assert_awaited_once_with("image")


@pytest.mark.asyncio
async def test_engine_health_check_invalid_type(auth_bypass):
    """5. 访问 /ai/engines/nonexistent/health 返回 400"""
    from app.main import app
    mock_manager = _make_mock_engine_manager()
    with patch("app.api.ai.engine_manager", mock_manager):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/ai/engines/nonexistent/health")
            assert response.status_code == 400
            # 不应调用 health_check_one
            mock_manager.health_check_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_text2img(auth_bypass):
    """6. mock image_engine.text2img 返回成功，验证 /ai/text2img"""
    from app.main import app
    mock_manager = _make_mock_engine_manager()
    with patch("app.api.ai.engine_manager", mock_manager):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/ai/text2img",
                json={
                    "prompt": "a cute cat",
                    "negative_prompt": "blurry",
                    "width": 512,
                    "height": 512,
                    "seed": 42,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert data["data"]["success"] is True
            assert data["data"]["content_type"] == "image/png"
            assert data["data"]["data"] == "/uploads/images/test.png"
            assert data["data"]["error"] is None
            mock_manager.get_image_engine.return_value.text2img.assert_awaited_once()
            # 验证传入参数
            call_kwargs = mock_manager.get_image_engine.return_value.text2img.call_args
            assert call_kwargs.kwargs["prompt"] == "a cute cat"
            assert call_kwargs.kwargs["width"] == 512
            assert call_kwargs.kwargs["height"] == 512
            assert call_kwargs.kwargs["seed"] == 42


@pytest.mark.asyncio
async def test_tts(auth_bypass):
    """7. mock tts_engine.synthesize 返回成功，验证 /ai/tts"""
    from app.main import app
    mock_manager = _make_mock_engine_manager()
    with patch("app.api.ai.engine_manager", mock_manager):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/ai/tts",
                json={
                    "text": "你好世界",
                    "voice": "zh-CN-XiaoxiaoNeural",
                    "rate": 10,
                    "pitch": 0,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert data["data"]["success"] is True
            assert data["data"]["content_type"] == "audio/mp3"
            assert data["data"]["data"] == "/uploads/audio/test.mp3"
            mock_manager.get_tts_engine.return_value.synthesize.assert_awaited_once()
            call_kwargs = (
                mock_manager.get_tts_engine.return_value.synthesize.call_args.kwargs
            )
            assert call_kwargs["text"] == "你好世界"
            assert call_kwargs["voice"] == "zh-CN-XiaoxiaoNeural"
            assert call_kwargs["rate"] == 10


@pytest.mark.asyncio
async def test_chat(auth_bypass):
    """8. mock llm_engine.chat 返回成功，验证 /ai/chat"""
    from app.main import app
    mock_manager = _make_mock_engine_manager()
    with patch("app.api.ai.engine_manager", mock_manager):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/ai/chat",
                json={
                    "messages": [
                        {"role": "system", "content": "你是助手"},
                        {"role": "user", "content": "你好"},
                    ],
                    "model": "deepseek-chat",
                    "temperature": 0.5,
                    "max_tokens": 1000,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert data["data"]["success"] is True
            assert data["data"]["content_type"] == "text/plain"
            assert data["data"]["data"] == "你好！我是 AI 助手。"
            mock_manager.get_llm_engine.return_value.chat.assert_awaited_once()
            call_kwargs = mock_manager.get_llm_engine.return_value.chat.call_args.kwargs
            # messages 应转为 list[dict]
            assert isinstance(call_kwargs["messages"], list)
            assert call_kwargs["messages"][0] == {"role": "system", "content": "你是助手"}
            assert call_kwargs["messages"][1] == {"role": "user", "content": "你好"}
            assert call_kwargs["model"] == "deepseek-chat"
            assert call_kwargs["temperature"] == 0.5
            assert call_kwargs["max_tokens"] == 1000


@pytest.mark.asyncio
async def test_video_compose(auth_bypass):
    """9. mock video_engine.compose 返回成功，验证 /ai/video/compose"""
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
                    ],
                    "audio": "/uploads/audio/bgm.mp3",
                    "fps": 30,
                    "resolution": [1280, 720],
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert data["data"]["success"] is True
            assert data["data"]["content_type"] == "video/mp4"
            assert data["data"]["data"] == "/uploads/videos/test.mp4"
            mock_manager.get_video_engine.return_value.compose.assert_awaited_once()
            call_kwargs = (
                mock_manager.get_video_engine.return_value.compose.call_args.kwargs
            )
            assert call_kwargs["frames"] == [
                "/uploads/images/frame1.png",
                "/uploads/images/frame2.png",
            ]
            assert call_kwargs["fps"] == 30
            # resolution 应转为 tuple
            assert call_kwargs["resolution"] == (1280, 720)
            assert isinstance(call_kwargs["resolution"], tuple)


@pytest.mark.asyncio
async def test_character_generate(auth_bypass):
    """10. mock character_engine.generate_consistent 返回成功，验证 /ai/character/generate"""
    from app.main import app
    mock_manager = _make_mock_engine_manager()
    with patch("app.api.ai.engine_manager", mock_manager):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 使用 data URL 格式的 base64 参考图
            b64_data = base64.b64encode(b"fake-image-bytes").decode("ascii")
            response = await client.post(
                "/api/ai/character/generate",
                json={
                    "prompt": "a cute girl with red hair",
                    "reference_image": f"data:image/png;base64,{b64_data}",
                    "consistency_weight": 0.9,
                    "character_description": "red-haired girl",
                    "mood": "happy",
                    "width": 768,
                    "height": 768,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert data["data"]["success"] is True
            assert data["data"]["content_type"] == "image/png"
            assert data["data"]["data"] == "/uploads/images/char.png"
            mock_manager.get_character_engine.return_value.generate_consistent.assert_awaited_once()
            call_kwargs = (
                mock_manager.get_character_engine.return_value.generate_consistent.call_args.kwargs
            )
            assert call_kwargs["prompt"] == "a cute girl with red hair"
            # reference_image 应被解码为 bytes
            assert isinstance(call_kwargs["reference_image"], bytes)
            assert call_kwargs["reference_image"] == b"fake-image-bytes"
            assert call_kwargs["consistency_weight"] == 0.9
            assert call_kwargs["character_description"] == "red-haired girl"
            assert call_kwargs["mood"] == "happy"
            assert call_kwargs["width"] == 768
            assert call_kwargs["height"] == 768
