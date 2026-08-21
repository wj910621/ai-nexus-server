"""本地模型管理 API

Task 15: Local AI Inference (Desktop)

Endpoints:
- GET    /models                 — 列出所有已注册的本地模型
- POST   /models/{name}/download — 从 HuggingFace 下载模型
- DELETE /models/{name}          — 删除模型本地文件
- GET    /models/runtime         — 获取本地运行时检测结果 (GPU/CPU)
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import settings
from app.core.deps import get_current_user
from app.engines.model_manager import model_manager
from app.models.user import User

router = APIRouter(prefix="/models", tags=["models"])


@router.get("")
async def list_models(
    model_type: Optional[str] = Query(None, description="Filter by model type: image|llm|tts|character"),
    current_user: User = Depends(get_current_user),
):
    """List all registered models (default + user-downloaded)."""
    models = model_manager.list_models(model_type)
    return {"data": [m.to_dict() for m in models]}


@router.post("/{name}/download")
async def download_model(
    name: str,
    repo_id: Optional[str] = Query(None, description="HuggingFace repo_id override"),
    current_user: User = Depends(get_current_user),
):
    """Download a model from HuggingFace.

    Returns the updated ModelInfo. If huggingface_hub is not installed
    (cloud mode), returns 400 with an explanatory error.
    """
    try:
        info = await model_manager.download(name, repo_id)
        return {"data": info.to_dict()}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/{name}")
async def delete_model(
    name: str,
    current_user: User = Depends(get_current_user),
):
    """Delete a model's local files and registry entry."""
    await model_manager.delete(name)
    return {"data": {"deleted": name}}


async def _resolve_current_user():
    """动态解析 get_current_user (Task 22 TDD fix).

    通过模块属性查找而非直接引用，使测试 patch("app.core.deps.get_current_user") 生效。
    （Depends(get_current_user) 在路由注册时已捕获函数引用，仅 patch 模块属性不会生效。）

    注意：此 wrapper 仅为支持 plan 中测试的 patch 模式；生产环境认证应通过
    FastAPI 的 dependency_overrides 或 Task 23 完善的 Depends 链实现。
    """
    from app.core import deps
    return await deps.get_current_user()


@router.get("/local/{hardware_profile}")
async def list_models_by_hardware(
    hardware_profile: str,
    current_user: User = Depends(_resolve_current_user),
):
    """按硬件配置推荐本地模型 (Task 22)

    GET /models/local/{hardware_profile}
    hardware_profile: low|mid|high|cpu

    返回 model_manager.list_models() 中 hardware_profile 匹配的子集。
    """
    models = model_manager.list_models()
    filtered = [
        m for m in models
        if (m.to_dict() or {}).get("hardware_profile") == hardware_profile
    ]
    return {"data": [m.to_dict() for m in filtered]}


@router.get("/runtime")
async def get_runtime_info(
    current_user: User = Depends(get_current_user),
):
    """Get local runtime detection info (GPU/CPU/None + VRAM/RAM).

    Returns:
    - device_type: "gpu" | "cpu" | "none"
    - vram_gb / ram_gb: available memory
    - gpu_name: GPU name (if GPU available)
    - recommended_providers: {image, llm, tts} recommended provider names
    """
    from app.core.local_runtime import local_runtime_detector
    info = local_runtime_detector.detect()
    return {
        "data": {
            **info.to_dict(),
            "local_inference_enabled": settings.local_inference_enabled,
            "recommended_providers": {
                "image": local_runtime_detector.recommend_image_provider(),
                "llm": local_runtime_detector.recommend_llm_provider(),
                "tts": local_runtime_detector.recommend_tts_provider(),
            },
        }
    }
