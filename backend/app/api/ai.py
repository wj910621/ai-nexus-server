"""AI 引擎 API 路由

将 Phase 2 已实现的 5 个 AI 引擎（image/tts/llm/video/character）通过 REST API 暴露给前端。
"""
import base64
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.sse import calculate_refund, sse_done, sse_error, sse_format
from app.core.deps import get_current_user, get_db
from app.core.engine_concurrency import engine_concurrency
from app.core.request_dedup import request_deduplicator
from app.core.response import ApiResponse
from app.engines.base import GenerationResult
from app.engines.manager import engine_manager
from app.models.user import User
from app.schemas.ai import (
    ChatRequest,
    ConsistentGenRequest,
    EngineInfo,
    EngineStatus,
    GenerationResponse,
    Text2ImgRequest,
    TTSRequest,
    VideoComposeRequest,
    VoiceInfo,
)
from app.services.result_cache_service import result_cache_service
from app.services.ynex_billing_service import YnexCharge, ynex_billing_service

router = APIRouter(prefix="/ai", tags=["AI 引擎"])


# === 辅助函数 ===
def _to_response(result: GenerationResult) -> GenerationResponse:
    """将引擎返回的 GenerationResult 转为 schema 的 GenerationResponse

    GenerationResult.data 可能是 bytes（图像/音频原始字节）或 str（URL/文本）。
    schema 中 data 为 str，故 bytes 时尝试 utf-8 解码，失败则返回空字符串。
    """
    data = result.data
    if isinstance(data, bytes):
        try:
            data = data.decode("utf-8")
        except UnicodeDecodeError:
            data = ""
    return GenerationResponse(
        success=result.success,
        data=data,
        content_type=result.content_type,
        metadata=result.metadata or {},
        error=result.error,
    )


def _to_engine_info(engine_type: str, info: dict) -> EngineInfo:
    """将引擎 get_info() 返回的 dict 转为 EngineInfo schema

    extra 包含 name/display_name/initialized 之外的额外字段。
    """
    name = info.get("name", engine_type)
    display_name = info.get("display_name", name)
    initialized = info.get("initialized", False)
    extra = {
        k: v
        for k, v in info.items()
        if k not in ("name", "display_name", "initialized")
    }
    return EngineInfo(
        name=name,
        display_name=display_name,
        initialized=initialized,
        extra=extra,
    )


def _decode_reference_image(reference_image: str) -> bytes:
    """将参考图字符串转为字节

    支持以下格式：
    - data URL（如 "data:image/png;base64,xxxx"）：提取 base64 部分解码
    - 纯 base64 字符串：直接解码
    - URL（http/https）：将 URL 编码为字节，由引擎内部处理下载

    简化处理：解码失败时回退为原始字符串的字节编码。
    """
    # data URL：data:image/png;base64,xxxx
    if reference_image.startswith("data:"):
        try:
            _, b64_data = reference_image.split(",", 1)
            return base64.b64decode(b64_data)
        except (ValueError, base64.binascii.Error):
            return reference_image.encode("utf-8")

    # http/https URL：直接传给 engine（编码为字节）
    if reference_image.startswith(("http://", "https://")):
        return reference_image.encode("utf-8")

    # 尝试作为纯 base64 解码
    try:
        return base64.b64decode(reference_image, validate=True)
    except Exception:
        # 解码失败，回退为字符串字节
        return reference_image.encode("utf-8")


def _require_engine(engine: Optional[object], engine_name: str):
    """检查引擎是否存在，不存在则抛 503"""
    if engine is None:
        raise HTTPException(
            status_code=503,
            detail=f"{engine_name} 引擎未初始化",
        )
    return engine


def _user_tier(user: User) -> str:
    """获取用户订阅层级（free/pro/enterprise），默认 free"""
    return getattr(user, "plan", None) or getattr(user, "role", "free") or "free"


async def _resolve_engine(
    db: AsyncSession,
    user: User,
    engine_type: str,
    engine_name: str,
    fallback_getter=None,
):
    """按订阅层级路由引擎（配额/订阅防护）

    商业化瘦身（2026-09-02）：将 API 层从"单默认引擎直调"升级为
    get_engine_routed() 智能路由——本地 Provider 走订阅层级校验，
    API Provider 走 QuotaGuard 配额检查。

    兼容策略：路由组件（_router/_quota_guard）未初始化时（如测试环境、
    路由组件初始化失败），回退到单默认引擎，保证向后兼容。
    """
    if engine_manager._router is None or engine_manager._quota_guard is None:
        # 路由组件未就绪 → 单默认引擎（旧行为）
        if fallback_getter is None:
            fallback_getter = getattr(engine_manager, f"get_{engine_type}_engine", None)
        engine = fallback_getter() if fallback_getter else None
        return _require_engine(engine, engine_name)

    tier = _user_tier(user)
    engine = await engine_manager.get_engine_routed(
        engine_type=engine_type,
        user_id=int(user.id) if isinstance(user.id, int) else user.id,
        subscription_tier=tier,
        user_preference=(user.preferences or {}).get("provider", "") if getattr(user, "preferences", None) else "",
    )
    if engine is None:
        raise HTTPException(
            status_code=429,
            detail=f"{engine_name} 配额不足或无可用的引擎，请升级订阅或稍后重试",
        )
    return engine


# === Credit costs & helpers ===
CREDIT_COSTS = {
    "text2img": 10,
    "tts": 5,
    "chat": 1,
    "video_compose": 50,
    "character_generate": 30,
}


async def check_and_deduct_credits(
    db: AsyncSession,
    user: User,
    operation: str,
) -> int | YnexCharge:
    """Check user has enough credits, deduct, and record a CreditTransaction.

    Admin users (role == "admin") bypass credit deduction.
    Raises ValueError for unknown operation.
    Raises HTTPException(402) when insufficient credits.
    Returns the user's credit balance after deduction (unchanged for admin).
    """
    from app.core.config import settings
    if settings.is_production and not settings.commercial_operations_enabled:
        # Do this before touching either the shared Y.NEX ledger or the legacy
        # local balance, so an unpublished price catalog can never charge a user.
        raise HTTPException(
            status_code=503,
            detail="Commercial model operations are temporarily unavailable",
        )
    if settings.billing_mode == "jarvis":
        if not user.external_subject:
            raise HTTPException(status_code=401, detail="Y·NEX account mapping is missing")
        # Chat runs through the Y·NEX OpenAI-compatible gateway, which already
        # meters the selected model against the main ledger. Charging the Story
        # operation endpoint as well would double-charge the user.
        if operation == "chat":
            return 0
        return await ynex_billing_service.charge(user.external_subject, operation)

    if getattr(user, "role", "user") == "admin":
        return user.credits or 0

    cost = CREDIT_COSTS.get(operation)
    if cost is None:
        raise ValueError(f"Unknown operation: {operation}")

    if (user.credits or 0) < cost:
        raise HTTPException(
            status_code=402,
            detail="积分不足",
        )

    user.credits = (user.credits or 0) - cost
    await db.flush()

    from app.models.billing import CreditTransaction
    txn = CreditTransaction(
        user_id=user.id,
        type="consumption",
        amount=cost,
        balance_after=user.credits,
        reason=operation,
        description=f"AI operation: {operation}",
        related_type="ai",
    )
    db.add(txn)
    await db.flush()
    return user.credits


async def refund_credits(
    db: AsyncSession,
    user: User,
    amount: int,
    reason: str = "failure_refund",
    charge: YnexCharge | None = None,
) -> None:
    """Refund credits to user (e.g., when an AI operation fails)."""
    from app.core.config import settings
    if settings.billing_mode == "jarvis":
        # Chat billing and failure reversal are owned by the Y·NEX gateway.
        if charge is None and reason.startswith("chat_"):
            return
        if charge is None:
            raise HTTPException(503, "Y·NEX billing receipt is missing")
        await ynex_billing_service.refund(charge, reason)
        return
    user.credits = (user.credits or 0) + amount
    await db.flush()

    from app.models.billing import CreditTransaction
    txn = CreditTransaction(
        user_id=user.id,
        type="refund",
        amount=amount,
        balance_after=user.credits,
        reason=reason,
        description=f"Refund: {reason}",
        related_type="ai",
    )
    db.add(txn)
    await db.flush()


# === 引擎管理端点 ===
@router.get("/engines", response_model=ApiResponse[list[EngineInfo]])
async def get_engines(current_user: User = Depends(get_current_user)):
    """获取所有已注册引擎的信息"""
    all_info = await engine_manager.get_all_info()
    infos = [_to_engine_info(etype, info) for etype, info in all_info.items()]
    return ApiResponse.success(data=infos)


@router.get("/engines/status", response_model=ApiResponse[EngineStatus])
async def get_engine_status(current_user: User = Depends(get_current_user)):
    """获取引擎整体状态"""
    status = await engine_manager.get_status()
    engine_status = EngineStatus(
        initialized=status.get("initialized", False),
        engine_count=status.get("engine_count", 0),
        engine_types=status.get("engine_types", []),
        init_errors=status.get("init_errors", {}),
    )
    return ApiResponse.success(data=engine_status)


@router.get(
    "/engines/{engine_type}/health",
    response_model=ApiResponse[dict],
)
async def check_engine_health(
    engine_type: str,
    current_user: User = Depends(get_current_user),
):
    """单个引擎健康检查"""
    if engine_type not in engine_manager.ENGINE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"未知的引擎类型: {engine_type}，"
            f"支持的类型: {engine_manager.ENGINE_TYPES}",
        )
    healthy = await engine_manager.health_check_one(engine_type)
    return ApiResponse.success(
        data={"engine_type": engine_type, "healthy": healthy},
        message="健康检查完成",
    )


# === 生成端点 ===
@router.post("/text2img", response_model=ApiResponse[GenerationResponse])
async def text2img(
    payload: Text2ImgRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """文生图 (带结果缓存 + 请求去重)"""
    # 1. 先查缓存
    cache_params = payload.model_dump()
    cached = await result_cache_service.get(
        engine_type="image",
        params=cache_params,
        user_id=str(current_user.id),
    )
    if cached is not None:
        return ApiResponse.success(data=GenerationResponse(**cached))

    # 2. 扣点 + 去重执行
    charge = await check_and_deduct_credits(db, current_user, "text2img")
    image_engine = await _resolve_engine(
        db, current_user, "image", "image",
        fallback_getter=engine_manager.get_image_engine,
    )

    async def _do_generate():
        async with engine_concurrency.acquire("image"):
            return await image_engine.text2img(
                prompt=payload.prompt,
                negative_prompt=payload.negative_prompt,
                width=payload.width,
                height=payload.height,
                seed=payload.seed,
                model=payload.model,
            )

    try:
        result = await request_deduplicator.deduplicate(_do_generate)
    except TimeoutError:
        await refund_credits(
            db, current_user, CREDIT_COSTS["text2img"], reason="text2img_concurrency_timeout",
            charge=charge if isinstance(charge, YnexCharge) else None,
        )
        raise HTTPException(
            status_code=503,
            detail="图像引擎忙碌，请稍后重试。",
        )
    except Exception:
        await refund_credits(
            db, current_user, CREDIT_COSTS["text2img"], reason="text2img_failure",
            charge=charge if isinstance(charge, YnexCharge) else None,
        )
        raise

    # 3. 写入缓存
    response_data = _to_response(result)
    await result_cache_service.set(
        engine_type="image",
        params=cache_params,
        result=response_data.model_dump(),
        user_id=str(current_user.id),
    )
    return ApiResponse.success(data=response_data)


@router.post("/tts", response_model=ApiResponse[GenerationResponse])
async def tts(
    payload: TTSRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """语音合成 (带结果缓存 + 请求去重)"""
    # 1. 先查缓存
    cache_params = payload.model_dump()
    cached = await result_cache_service.get(
        engine_type="tts",
        params=cache_params,
        user_id=str(current_user.id),
    )
    if cached is not None:
        return ApiResponse.success(data=GenerationResponse(**cached))

    # 2. 扣点 + 去重执行
    charge = await check_and_deduct_credits(db, current_user, "tts")
    tts_engine = await _resolve_engine(
        db, current_user, "tts", "tts",
        fallback_getter=engine_manager.get_tts_engine,
    )

    async def _do_synthesize():
        async with engine_concurrency.acquire("tts"):
            return await tts_engine.synthesize(
                text=payload.text,
                voice=payload.voice,
                rate=payload.rate,
                pitch=payload.pitch,
            )

    try:
        result = await request_deduplicator.deduplicate(_do_synthesize)
    except TimeoutError:
        await refund_credits(
            db, current_user, CREDIT_COSTS["tts"], reason="tts_concurrency_timeout",
            charge=charge if isinstance(charge, YnexCharge) else None,
        )
        raise HTTPException(
            status_code=503,
            detail="TTS 引擎忙碌，请稍后重试。",
        )
    except Exception:
        await refund_credits(
            db, current_user, CREDIT_COSTS["tts"], reason="tts_failure",
            charge=charge if isinstance(charge, YnexCharge) else None,
        )
        raise

    # 3. 写入缓存
    response_data = _to_response(result)
    await result_cache_service.set(
        engine_type="tts",
        params=cache_params,
        result=response_data.model_dump(),
        user_id=str(current_user.id),
    )
    return ApiResponse.success(data=response_data)


@router.get("/voices", response_model=ApiResponse[list[VoiceInfo]])
async def list_voices(
    language: Optional[str] = Query(default=None, description="语言前缀过滤"),
    current_user: User = Depends(get_current_user),
):
    """获取可用声音列表"""
    tts_engine = _require_engine(engine_manager.get_tts_engine(), "tts")
    voices = await tts_engine.list_voices(language)
    infos = [
        VoiceInfo(
            name=v.get("ShortName") or v.get("Name") or v.get("name", ""),
            display_name=v.get("FriendlyName") or v.get("display_name", ""),
            language=v.get("Locale") or v.get("language", ""),
        )
        for v in voices
    ]
    return ApiResponse.success(data=infos)


@router.post("/chat", response_model=ApiResponse[GenerationResponse])
async def chat(
    payload: ChatRequest,
    stream: bool = Query(default=False, description="启用 SSE 流式输出"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """LLM 对话 (带结果缓存 + 请求去重；支持 SSE 流式输出)

    - `stream=false` (默认): 返回 JSON `ApiResponse[GenerationResponse]`，
      命中缓存、走去重、扣点退款逻辑同其他端点。
    - `stream=true`: 返回 `text/event-stream`，逐 token 推送 `event: token`
      事件，结束发送 `data: [DONE]`；客户端断开或上游异常时按未使用比例
      退款（断开估算 30% 已使用）。
    """
    if not stream:
        # Backward compat: 同步 JSON 响应 (带缓存 + 去重)
        cache_params = payload.model_dump()
        cached = await result_cache_service.get(
            engine_type="llm",
            params=cache_params,
            user_id=str(current_user.id),
        )
        if cached is not None:
            return ApiResponse.success(data=GenerationResponse(**cached))

        charge = await check_and_deduct_credits(db, current_user, "chat")
        llm_engine = await _resolve_engine(
            db, current_user, "llm", "llm",
            fallback_getter=engine_manager.get_llm_engine,
        )
        messages = [m.model_dump() for m in payload.messages]

        async def _do_chat():
            async with engine_concurrency.acquire("llm"):
                return await llm_engine.chat(
                    messages=messages,
                    model=payload.model,
                    temperature=payload.temperature,
                    max_tokens=payload.max_tokens,
                )

        try:
            result = await request_deduplicator.deduplicate(_do_chat)
        except TimeoutError:
            await refund_credits(
                db, current_user, CREDIT_COSTS["chat"], reason="chat_concurrency_timeout",
                charge=charge if isinstance(charge, YnexCharge) else None,
            )
            raise HTTPException(
                status_code=503,
                detail="LLM 引擎忙碌，请稍后重试。",
            )
        except Exception:
            await refund_credits(
                db, current_user, CREDIT_COSTS["chat"], reason="chat_failure",
                charge=charge if isinstance(charge, YnexCharge) else None,
            )
            raise

        response_data = _to_response(result)
        await result_cache_service.set(
            engine_type="llm",
            params=cache_params,
            result=response_data.model_dump(),
            user_id=str(current_user.id),
            ttl_seconds=result_cache_service.LLM_TTL_SECONDS,
        )
        return ApiResponse.success(data=response_data)

    # === SSE 流式分支 ===
    # 注：流式不查缓存、不去重（每个 token 都是实时增量），但仍扣点；
    # 异常 / 客户端断开时按未使用比例退款。
    charge = await check_and_deduct_credits(db, current_user, "chat")
    llm_engine = await _resolve_engine(
        db, current_user, "llm", "llm",
        fallback_getter=engine_manager.get_llm_engine,
    )
    messages = [m.model_dump() for m in payload.messages]
    estimated_tokens = payload.max_tokens or 1000

    async def on_abort():
        """客户端断开 - 按估算的 30% 已使用计算退款"""
        refund = calculate_refund(
            used_tokens=int(estimated_tokens * 0.3),
            total_tokens=estimated_tokens,
            cost=CREDIT_COSTS["chat"],
        )
        if refund > 0:
            await refund_credits(
                db, current_user, refund, reason="chat_stream_abort",
                charge=charge if isinstance(charge, YnexCharge) else None,
            )

    async def generate():
        try:
            async for chunk in llm_engine.chat_stream(
                messages=messages,
                model=payload.model,
                temperature=payload.temperature,
                max_tokens=estimated_tokens,
            ):
                yield sse_format({"text": chunk}, event="token")
            yield sse_done()
        except Exception as exc:
            yield sse_error(str(exc))
            await refund_credits(
                db, current_user, CREDIT_COSTS["chat"], reason="chat_stream_error",
                charge=charge if isinstance(charge, YnexCharge) else None,
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲，确保 token 即时推送
            "Connection": "keep-alive",
        },
    )


@router.post("/video/compose", response_model=ApiResponse[GenerationResponse])
async def video_compose(
    payload: VideoComposeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """视频合成"""
    charge = await check_and_deduct_credits(db, current_user, "video_compose")
    video_engine = await _resolve_engine(
        db, current_user, "video", "video",
        fallback_getter=engine_manager.get_video_engine,
    )
    # resolution 是 list[int]，引擎期望 tuple[int, int]
    resolution = (
        tuple(payload.resolution) if payload.resolution else (1920, 1080)
    )
    try:
        async with engine_concurrency.acquire("video"):
            result = await video_engine.compose(
                frames=payload.frames,
                audio=payload.audio,
                output_path=payload.output_path,
                fps=payload.fps,
                resolution=resolution,
            )
    except TimeoutError:
        await refund_credits(
            db, current_user, CREDIT_COSTS["video_compose"], reason="video_compose_concurrency_timeout",
            charge=charge if isinstance(charge, YnexCharge) else None,
        )
        raise HTTPException(
            status_code=503,
            detail="视频引擎忙碌，请稍后重试。",
        )
    except Exception:
        await refund_credits(
            db, current_user, CREDIT_COSTS["video_compose"], reason="video_compose_failure",
            charge=charge if isinstance(charge, YnexCharge) else None,
        )
        raise
    return ApiResponse.success(data=_to_response(result))


@router.post(
    "/character/generate",
    response_model=ApiResponse[GenerationResponse],
)
async def character_generate(
    payload: ConsistentGenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """角色一致性生成"""
    charge = await check_and_deduct_credits(db, current_user, "character_generate")
    character_engine = await _resolve_engine(
        db, current_user, "character", "character",
        fallback_getter=engine_manager.get_character_engine,
    )
    # reference_image 可能是 base64 或 URL，统一转为 bytes
    reference_bytes = _decode_reference_image(payload.reference_image)
    try:
        async with engine_concurrency.acquire("character"):
            result = await character_engine.generate_consistent(
                prompt=payload.prompt,
                reference_image=reference_bytes,
                consistency_weight=payload.consistency_weight,
                character_description=payload.character_description,
                mood=payload.mood,
                width=payload.width,
                height=payload.height,
                seed=payload.seed,
            )
    except TimeoutError:
        await refund_credits(
            db, current_user, CREDIT_COSTS["character_generate"], reason="character_generate_concurrency_timeout",
            charge=charge if isinstance(charge, YnexCharge) else None,
        )
        raise HTTPException(
            status_code=503,
            detail="角色生成引擎忙碌，请稍后重试。",
        )
    except Exception:
        await refund_credits(
            db, current_user, CREDIT_COSTS["character_generate"], reason="character_generate_failure",
            charge=charge if isinstance(charge, YnexCharge) else None,
        )
        raise
    return ApiResponse.success(data=_to_response(result))
