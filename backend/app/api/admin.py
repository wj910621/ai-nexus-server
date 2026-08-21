"""Admin API - system administration endpoints (admin role required)."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin, get_db
from app.core.response import ApiResponse
from app.models.user import User
from app.schemas.user import UserResponse
from app.services.admin_service import AdminService

router = APIRouter(prefix="/admin", tags=["管理"])


@router.get("/users", response_model=ApiResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    role: str | None = None,
    status: str | None = None,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all users (admin only)."""
    svc = AdminService(db)
    offset = (page - 1) * page_size
    users = await svc.list_users(limit=page_size, offset=offset, role=role, status_filter=status)
    return ApiResponse.success(
        data={"items": [UserResponse.model_validate(u) for u in users], "page": page, "page_size": page_size}
    )


@router.get("/stats", response_model=ApiResponse)
async def get_stats(
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Get system statistics (admin only)."""
    svc = AdminService(db)
    stats = await svc.get_stats()
    return ApiResponse.success(data=stats)


@router.post("/users/{user_id}/ban", response_model=ApiResponse)
async def ban_user(
    user_id: UUID,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Ban a user (admin only)."""
    svc = AdminService(db)
    ok = await svc.ban_user(user_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return ApiResponse.success(message="用户已封禁")


@router.post("/users/{user_id}/unban", response_model=ApiResponse)
async def unban_user(
    user_id: UUID,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Unban a user (admin only)."""
    svc = AdminService(db)
    ok = await svc.unban_user(user_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return ApiResponse.success(message="用户已解封")


@router.post("/users/{user_id}/credits", response_model=ApiResponse)
async def grant_credits(
    user_id: UUID,
    amount: int,
    reason: str = "admin_grant",
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Grant credits to a user (admin only)."""
    if amount <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="amount must be positive")
    svc = AdminService(db)
    try:
        new_balance = await svc.grant_credits(user_id, amount, reason, f"Admin grant by {admin.username}")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return ApiResponse.success(data={"new_balance": new_balance}, message="积分发放成功")


@router.post("/users/{user_id}/promote-admin", response_model=ApiResponse)
async def promote_admin(
    user_id: UUID,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Promote a user to admin role (admin only)."""
    svc = AdminService(db)
    ok = await svc.promote_admin(user_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return ApiResponse.success(message="已提升为管理员")


@router.post("/users/{user_id}/demote-admin", response_model=ApiResponse)
async def demote_admin(
    user_id: UUID,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Demote an admin to regular user (admin only)."""
    svc = AdminService(db)
    ok = await svc.demote_admin(user_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    return ApiResponse.success(message="已降级为普通用户")


@router.get("/audit-logs", response_model=ApiResponse)
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    action: str | None = None,
    actor_id: UUID | None = None,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """List audit logs (admin only)."""
    from app.schemas.audit import AuditLogResponse
    from app.services.audit_service import AuditService
    svc = AuditService(db)
    offset = (page - 1) * page_size
    if actor_id:
        logs = await svc.list_by_actor(actor_id, limit=page_size, offset=offset)
    elif action:
        logs = await svc.list_by_action(action, limit=page_size, offset=offset)
    else:
        logs = await svc.list_all(limit=page_size, offset=offset)
    total = await svc.count()
    return ApiResponse.success(
        data={
            "items": [AuditLogResponse.model_validate(log) for log in logs],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.post("/benchmark", response_model=ApiResponse)
async def run_benchmark(
    force: bool = Query(False, description="强制重新运行（忽略缓存）"),
    admin: User = Depends(get_current_admin),
):
    """P2 Task 15: 运行硬件基准测试

    调用 DeviceManager.benchmark() 执行 LLM / Image / VRAM 三类基准测试，
    返回结构化结果供前端 BenchmarkCard 展示。

    - 默认使用 1 小时缓存（force=False）
    - force=True 时强制重新运行
    - 仅 admin 角色可访问
    """
    from app.core.device_manager import DeviceManager

    dm = DeviceManager.get_instance()
    try:
        result = await dm.benchmark(force=force)
        return ApiResponse.success(data=result, message="基准测试完成")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"基准测试失败：{type(exc).__name__}: {exc}",
        )
