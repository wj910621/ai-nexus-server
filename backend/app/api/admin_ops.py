"""管理员运营 API - SLA / 备份 / 告警 (Task 14)

Endpoints:
- GET  /admin/ops/sla              — SLA 指标 (uptime / p99 / cache hit rate / error rate)
- GET  /admin/ops/backups          — 列出备份文件
- POST /admin/ops/backups/trigger  — 手动触发备份任务
"""
import os
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.models.user import User

router = APIRouter(prefix="/admin/ops", tags=["admin-ops"])


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """要求管理员角色 (403 if not admin)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def _sum_metric(metric_obj: Any) -> float:
    """Sum all sample values across labels for a Counter/Gauge."""
    total = 0.0
    for metric in metric_obj.collect():
        for sample in metric.samples:
            total += sample.value
    return total


def _sum_by_label(metric_obj: Any, label_name: str) -> dict[str, float]:
    """Sum sample values grouped by a label."""
    out: dict[str, float] = {}
    for metric in metric_obj.collect():
        for sample in metric.samples:
            val = (sample.labels or {}).get(label_name)
            if val is not None:
                out[val] = out.get(val, 0.0) + sample.value
    return out


async def compute_sla() -> dict:
    """计算 SLA 指标 - 从真实 Prometheus metrics 聚合。

    单进程内可计算: cache hit rate, error rate, current process uptime.
    历史 p99 / 30d uptime 需查询 Prometheus (histogram_quantile / increase(up))。
    """
    from app.core.metrics import (
        engine_requests_total,
        result_cache_hits_total,
        result_cache_misses_total,
    )

    # Cache hit rate (real data from result_cache counters)
    hits = _sum_metric(result_cache_hits_total)
    misses = _sum_metric(result_cache_misses_total)
    total_cache = hits + misses
    cache_hit_rate = (hits / total_cache * 100) if total_cache > 0 else 0.0

    # Error rate (real data from engine_requests_total{result=...})
    result_counts = _sum_by_label(engine_requests_total, "result")
    success = result_counts.get("success", 0.0)
    failure = result_counts.get("failure", 0.0)
    total_eng = success + failure
    error_rate = (failure / total_eng * 100) if total_eng > 0 else 0.0

    return {
        # Historical values require Prometheus query; left as None when no
        # external Prometheus is wired up.
        "uptime_percent_30d": None,
        "p99_latency_ms": None,
        "cache_hit_rate_percent": round(cache_hit_rate, 2),
        "error_rate_percent": round(error_rate, 2),
        "engine_success_total": int(success),
        "engine_failure_total": int(failure),
        "cache_hits_total": int(hits),
        "cache_misses_total": int(misses),
        "computed_at": datetime.now(UTC).isoformat(),
        "note": (
            "Historical p99 and 30d uptime require Prometheus query; "
            "current values are real-time process aggregates."
        ),
    }


async def list_backups() -> list[dict]:
    """列出备份文件 (按时间倒序，最多 50 条)."""
    backup_dir = (
        getattr(settings, "backup_dir", None)
        or os.environ.get("BACKUP_DIR", "")
        or "/var/backups/comicstudio"
    )
    backups: list[dict] = []
    if not os.path.isdir(backup_dir):
        return backups
    for f in sorted(os.listdir(backup_dir), reverse=True):
        path = os.path.join(backup_dir, f)
        if not os.path.isfile(path):
            continue
        stat = os.stat(path)
        backups.append({
            "name": f,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "type": (
                "db" if f.startswith("db-") else
                "uploads" if f.startswith("uploads-") else
                "redis" if f.startswith("redis-") else "other"
            ),
            "created_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
        })
    return backups[:50]


@router.get("/sla")
async def get_sla(
    admin: User = Depends(require_admin),
):
    """获取 SLA 指标 (uptime / p99 / cache hit rate / error rate)."""
    sla = await compute_sla()
    return {"data": sla}


@router.get("/backups")
async def get_backups(
    admin: User = Depends(require_admin),
):
    """列出备份文件."""
    backups = await list_backups()
    return {"data": {"backups": backups, "count": len(backups)}}


@router.post("/backups/trigger")
async def trigger_backup(
    admin: User = Depends(require_admin),
    backup_type: str = Query("all", pattern="^(db|uploads|redis|all)$"),
    db: AsyncSession = Depends(get_db),
):
    """手动触发备份任务 (异步执行).

    备份由 TaskService 后台执行；返回 task_id 供前端轮询。
    """
    from app.services.task_service import task_service
    task = await task_service.submit(
        db=db,
        user_id=admin.id,
        task_type="backup",
        payload={"backup_type": backup_type},
    )
    return {"data": {"task_id": task.id, "status": "queued"}}
