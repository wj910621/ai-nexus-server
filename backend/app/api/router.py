"""路由聚合 - 注册所有 API 路由"""
from fastapi import APIRouter

from app.api import (
    admin,
    admin_ops,
    ai,
    audio,
    auth,
    billing,
    characters,
    datasets,
    models,
    payments,
    projects,
    render,
    scripts,
    storyboards,
    subscriptions,
    tasks,
    training,
    users,
    workflows,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(projects.router)
api_router.include_router(characters.router)
api_router.include_router(scripts.router)
api_router.include_router(storyboards.router)
api_router.include_router(audio.router)
api_router.include_router(render.router)
api_router.include_router(workflows.router)
api_router.include_router(ai.router)
api_router.include_router(billing.router)
api_router.include_router(subscriptions.router)
api_router.include_router(admin.router)
api_router.include_router(payments.router)
api_router.include_router(tasks.router)
# admin_ops.router has prefix="/admin/ops" — register without extra prefix
# so the path becomes /api/admin/ops/sla (and /api/v1/admin/ops/sla on v1_router).
api_router.include_router(admin_ops.router)
# Task 15: Local models management
api_router.include_router(models.router)
# Task 11: Datasets API
api_router.include_router(datasets.router)
# Task 12: Training API
api_router.include_router(training.router)

# v1 alias — same sub-routers, different prefix (Task 7)
# /api/* legacy endpoints continue to work; /api/v1/* is the versioned alias.
v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth.router)
v1_router.include_router(users.router)
v1_router.include_router(projects.router)
v1_router.include_router(characters.router)
v1_router.include_router(scripts.router)
v1_router.include_router(storyboards.router)
v1_router.include_router(audio.router)
v1_router.include_router(render.router)
v1_router.include_router(workflows.router)
v1_router.include_router(ai.router)
v1_router.include_router(billing.router)
v1_router.include_router(subscriptions.router)
v1_router.include_router(admin.router)
v1_router.include_router(payments.router)
v1_router.include_router(tasks.router)
v1_router.include_router(admin_ops.router)
v1_router.include_router(models.router)
v1_router.include_router(datasets.router)
v1_router.include_router(training.router)
