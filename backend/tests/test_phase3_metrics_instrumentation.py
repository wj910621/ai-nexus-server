"""阶段 3 - 运维健壮性：指标埋点生效验证

阶段 3 的核心诉求不是「指标存在」，而是「业务路径真正触发指标」。
本模块通过真实调用 AI API 端点 + prometheus_client registry 断言：

- /ai/text2img 成功 → engine_requests_total{image,success} +1
- /ai/text2img 引擎抛错 → engine_requests_total{image,failure} +1
- /ai/tts 成功 → engine_requests_total{tts,success} +1
- 缓存命中 → result_cache_hits_total +1（真实缓存服务 + 内存 SQLite）
- 缓存未命中 → result_cache_misses_total +1
- 扣费（非 admin）→ credits_consumed_total +1
- /ai/video/compose 非法 resolution → 422（阶段 3 新增校验）
- 熔断器状态迁移 → provider_circuit_state 0/2（failover 真实调用）

说明：采用「增量断言」（before/after 差值），避免指标被其他测试
提前 inc 导致误判；不 reload 模块，保证业务代码引用的指标对象与
REGISTRY 读取的是同一实例。
"""
import pytest
from httpx import AsyncClient, ASGITransport
from prometheus_client import REGISTRY
from unittest.mock import AsyncMock, MagicMock, patch

from app.engines.base import GenerationResult


# === Prometheus 指标读取工具 ===
def _metric_value(name: str, labels: dict) -> float:
    """从默认 REGISTRY 读取指标当前值（无则 0）"""
    for metric in REGISTRY.collect():
        if metric.name == name:
            for sample in metric.samples:
                if sample.labels == labels:
                    return sample.value
    return 0.0


def _delta(name: str, labels: dict, before: float) -> float:
    return _metric_value(name, labels) - before


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = "test-user-id"
    user.username = "testuser"
    user.status = "active"
    user.role = "admin"  # admin 绕过扣费
    user.credits = 0
    return user


@pytest.fixture
def auth_bypass(mock_user):
    from app.core.deps import get_current_user
    from app.main import app

    async def _override():
        return mock_user

    app.dependency_overrides[get_current_user] = _override
    yield mock_user
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture(autouse=True)
def _mock_cache_and_dedup():
    """Patch cache/dedup 为可控行为：默认缓存 miss"""
    async def _passthrough(func, *args, **kwargs):
        return await func(*args, **kwargs)

    mock_cache = MagicMock()
    mock_cache.get = AsyncMock(return_value=None)  # 默认 miss
    mock_cache.set = AsyncMock(return_value=None)
    mock_cache.LLM_TTL_SECONDS = 1800

    mock_dedup = MagicMock()
    mock_dedup.deduplicate = _passthrough

    with patch("app.api.ai.result_cache_service", mock_cache), \
         patch("app.api.ai.request_deduplicator", mock_dedup):
        yield mock_cache


def _make_engine_manager(raise_image=False):
    """构造 mock engine_manager（对齐 test_ai_api 结构）"""
    manager = MagicMock()
    manager.ENGINE_TYPES = ["image", "tts", "llm", "video", "character"]
    manager._router = MagicMock()
    manager._quota_guard = MagicMock()

    manager.get_all_info = AsyncMock(return_value={
        "image": {"name": "pollinations", "initialized": True},
        "tts": {"name": "edge-tts", "initialized": True},
        "llm": {"name": "deepseek", "initialized": True},
        "video": {"name": "ffmpeg", "initialized": True},
        "character": {"name": "soft-consistency", "initialized": True},
    })
    manager.get_status = AsyncMock(return_value={
        "initialized": True, "engine_count": 5,
        "engine_types": ["image", "tts", "llm", "video", "character"],
        "init_errors": {},
    })
    manager.health_check_one = AsyncMock(return_value=True)

    # image
    image_engine = AsyncMock()
    if raise_image:
        async def _boom(*a, **k):
            raise RuntimeError("engine exploded")
        image_engine.text2img = _boom
    else:
        image_engine.text2img = AsyncMock(return_value=GenerationResult(
            success=True, data="/uploads/images/test.png",
            content_type="image/png", metadata={"model": "flux"},
        ))
    manager.get_image_engine.return_value = image_engine

    # tts
    tts_engine = AsyncMock()
    tts_engine.synthesize = AsyncMock(return_value=GenerationResult(
        success=True, data="/uploads/audio/test.mp3",
        content_type="audio/mp3", metadata={"voice": "zh-CN-XiaoxiaoNeural"},
    ))
    tts_engine.list_voices = AsyncMock(return_value=[])
    manager.get_tts_engine.return_value = tts_engine

    # llm
    llm_engine = AsyncMock()
    llm_engine.chat = AsyncMock(return_value=GenerationResult(
        success=True, data="hi", content_type="text/plain", metadata={},
    ))
    manager.get_llm_engine.return_value = llm_engine

    # video
    video_engine = AsyncMock()
    video_engine.compose = AsyncMock(return_value=GenerationResult(
        success=True, data="/uploads/videos/test.mp4",
        content_type="video/mp4", metadata={},
    ))
    manager.get_video_engine.return_value = video_engine

    # character
    character_engine = AsyncMock()
    character_engine.generate_consistent = AsyncMock(return_value=GenerationResult(
        success=True, data="/uploads/chars/test.png",
        content_type="image/png", metadata={},
    ))
    manager.get_character_engine.return_value = character_engine

    # get_engine_routed 按 engine_type 返回对应引擎（对齐 test_ai_api 结构）
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


# === 测试 ===
@pytest.mark.asyncio
async def test_text2img_success_counts_engine_request(auth_bypass):
    """text2img 成功 → engine_requests_total{image,success} +1"""
    before = _metric_value("engine_requests_total", {"engine_type": "image", "result": "success"})
    manager = _make_engine_manager()
    with patch("app.api.ai.engine_manager", manager):
        from app.main import app
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/api/v1/ai/text2img", json={
                "prompt": "a cat", "width": 512, "height": 512,
            })
    assert resp.status_code == 200
    assert _delta("engine_requests_total", {"engine_type": "image", "result": "success"}, before) == 1


@pytest.mark.asyncio
async def test_text2img_failure_counts_engine_failure(auth_bypass):
    """text2img 引擎抛错 → engine_requests_total{image,failure} +1"""
    before = _metric_value("engine_requests_total", {"engine_type": "image", "result": "failure"})
    manager = _make_engine_manager(raise_image=True)
    with patch("app.api.ai.engine_manager", manager):
        from app.main import app
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/api/v1/ai/text2img", json={
                "prompt": "a cat", "width": 512, "height": 512,
            })
    assert resp.status_code == 500
    assert _delta("engine_requests_total", {"engine_type": "image", "result": "failure"}, before) == 1


@pytest.mark.asyncio
async def test_tts_success_counts_engine_request(auth_bypass):
    """tts 成功 → engine_requests_total{tts,success} +1"""
    before = _metric_value("engine_requests_total", {"engine_type": "tts", "result": "success"})
    manager = _make_engine_manager()
    with patch("app.api.ai.engine_manager", manager):
        from app.main import app
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/api/v1/ai/tts", json={
                "text": "你好", "voice": "zh-CN-XiaoxiaoNeural",
            })
    assert resp.status_code == 200
    assert _delta("engine_requests_total", {"engine_type": "tts", "result": "success"}, before) == 1


@pytest.mark.asyncio
async def test_credits_consumed_counted_for_non_admin(auth_bypass, mock_user):
    """非 admin 扣费 → credits_consumed_total{text2img} +1"""
    mock_user.role = "user"
    mock_user.credits = 100

    from app.core.config import settings
    original_billing_mode = settings.billing_mode
    settings.billing_mode = "local"

    before = _metric_value("credits_consumed_total", {"operation": "text2img"})
    manager = _make_engine_manager()
    try:
        with patch("app.api.ai.engine_manager", manager), \
             patch("app.api.ai.CREDIT_COSTS", {"text2img": 10}):
            from app.main import app
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post("/api/v1/ai/text2img", json={
                    "prompt": "a cat", "width": 512, "height": 512,
                })
            assert resp.status_code == 200
    finally:
        settings.billing_mode = original_billing_mode

    assert _delta("credits_consumed_total", {"operation": "text2img"}, before) == 1
    assert mock_user.credits == 90  # 扣了 10


@pytest.mark.asyncio
async def test_video_compose_invalid_resolution_422(auth_bypass):
    """非法 resolution → 422（阶段 3 新增校验）"""
    manager = _make_engine_manager()
    with patch("app.api.ai.engine_manager", manager):
        from app.main import app
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # 负数宽度
            resp1 = await client.post("/api/v1/ai/video/compose", json={
                "frames": ["/a.png", "/b.png"],
                "resolution": [-1, 1080],
            })
            assert resp1.status_code == 422
            # 超过 8K
            resp2 = await client.post("/api/v1/ai/video/compose", json={
                "frames": ["/a.png", "/b.png"],
                "resolution": [10000, 1080],
            })
            assert resp2.status_code == 422
            # 非整数
            resp3 = await client.post("/api/v1/ai/video/compose", json={
                "frames": ["/a.png", "/b.png"],
                "resolution": [1920.5, 1080],
            })
            assert resp3.status_code == 422


@pytest.mark.asyncio
async def test_video_compose_valid_resolution_200(auth_bypass):
    """合法 resolution → 200 且 engine_requests_total{video,success} +1"""
    before = _metric_value("engine_requests_total", {"engine_type": "video", "result": "success"})
    manager = _make_engine_manager()
    with patch("app.api.ai.engine_manager", manager):
        from app.main import app
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/api/v1/ai/video/compose", json={
                "frames": ["/a.png", "/b.png"],
                "resolution": [1920, 1080],
                "fps": 24,
            })
    assert resp.status_code == 200
    assert _delta("engine_requests_total", {"engine_type": "video", "result": "success"}, before) == 1


@pytest.mark.asyncio
async def test_failover_circuit_state_transitions():
    """熔断器真实调用 → provider_circuit_state 0→2→0 + fallback 计数"""
    from app.engines.provider_failover import ProviderFailover

    before_state = _metric_value("provider_circuit_state", {"provider": "unknown"})
    before_calls = _metric_value("provider_calls_total", {"provider": "unknown", "result": "fallback"})

    async def ok():
        return "ok"

    async def boom():
        raise RuntimeError("boom")

    cb = ProviderFailover(threshold=2, reset_seconds=1)
    # 失败 2 次 → OPEN (2)
    await cb.record_failure("unknown")
    await cb.record_failure("unknown")
    assert _delta("provider_circuit_state", {"provider": "unknown"}, before_state) == 2.0
    # 成功 → CLOSED (0)
    await cb.record_success()
    assert _delta("provider_circuit_state", {"provider": "unknown"}, before_state) == 0.0

    # 熔断中 fallback 调用 → provider_calls_total{fallback} +1
    cb2 = ProviderFailover(threshold=1, reset_seconds=60)
    await cb2.record_failure("timeout")
    await cb2.call_with_failover(primary=boom, secondary=ok)
    assert _delta("provider_calls_total", {"provider": "unknown", "result": "fallback"}, before_calls) == 1


@pytest.mark.asyncio
async def test_cache_hit_and_miss_counted(db_session):
    """缓存未命中 → misses+1；命中 → hits+1（真实 ResultCacheService + 内存 SQLite）"""
    from app.core import metrics as metrics_module
    assert metrics_module.result_cache_hits_total is not None
    assert metrics_module.result_cache_misses_total is not None

    before_miss = _metric_value("result_cache_misses_total", {"engine_type": "image"})
    before_hit = _metric_value("result_cache_hits_total", {"engine_type": "image"})

    from app.services.result_cache_service import ResultCacheService
    svc = ResultCacheService()
    params = {"prompt": "hello world"}

    # 未命中
    miss = await svc.get(engine_type="image", params=params, user_id="u1")
    assert miss is None
    assert _delta("result_cache_misses_total", {"engine_type": "image"}, before_miss) == 1

    # 写入后命中
    await svc.set(engine_type="image", params=params, result={"data": "x"}, user_id="u1")
    got = await svc.get(engine_type="image", params=params, user_id="u1")
    assert got == {"data": "x"}
    assert _delta("result_cache_hits_total", {"engine_type": "image"}, before_hit) == 1
