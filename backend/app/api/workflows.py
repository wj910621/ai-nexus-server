"""工作流路由"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.response import ApiResponse, PaginatedData, PaginatedResponse
from app.engines.workflow.executor import workflow_executor
from app.engines.workflow.nodes import register_all_nodes
from app.engines.workflow.registry import node_registry
from app.engines.workflow.template_manager import template_manager
from app.models.base import utc_now
from app.models.user import User
from app.schemas.workflow import (
    ApplyTemplateRequest,
    ExecutionDetailResponse,
    ExecutionProgressResponse,
    NodeDefinitionResponse,
    TemplateResponse,
    WorkflowCreate,
    WorkflowExecuteRequest,
    WorkflowResponse,
    WorkflowUpdate,
)
from app.services.workflow_service import WorkflowExecutionService, WorkflowService

router = APIRouter(prefix="/workflows", tags=["工作流"])

# 启动时注册所有节点
register_all_nodes(node_registry)


@router.get("", response_model=PaginatedResponse[WorkflowResponse])
async def list_workflows(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = WorkflowService(db)
    skip = (page - 1) * page_size
    items = await service.list_by_user(current_user.id, skip=skip, limit=page_size)
    total = await service.count(filters={"user_id": current_user.id})
    return PaginatedResponse(
        data=PaginatedData(
            items=[WorkflowResponse.model_validate(w) for w in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post("", response_model=ApiResponse[WorkflowResponse])
async def create_workflow(
    payload: WorkflowCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = WorkflowService(db)
    data = payload.model_dump()
    data["user_id"] = current_user.id
    workflow = await service.create(data)
    return ApiResponse.success(data=WorkflowResponse.model_validate(workflow), message="创建成功")


@router.post("/execute", response_model=ApiResponse[ExecutionDetailResponse])
async def execute_workflow(
    payload: WorkflowExecuteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """执行工作流"""
    # 获取工作流数据
    if payload.workflow_id:
        service = WorkflowService(db)
        workflow = await service.get_by_id(payload.workflow_id)
        if not workflow or workflow.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="工作流不存在")
        workflow_data = {"nodes": workflow.nodes, "edges": workflow.edges}
    else:
        if not payload.nodes:
            raise HTTPException(status_code=400, detail="必须提供 workflow_id 或 nodes/edges")
        workflow_data = {"nodes": payload.nodes, "edges": payload.edges or []}

    # Persist ownership before execution starts. The engine and database share
    # the same public ID so authorization survives process restarts.
    execution_id = str(uuid4())
    exec_service = WorkflowExecutionService(db)
    started_at_dt = utc_now()
    await exec_service.create({
        "id": UUID(execution_id),
        "workflow_id": UUID(payload.workflow_id) if payload.workflow_id else None,
        "user_id": current_user.id,
        "status": "running",
        "inputs": payload.inputs,
        "results": {},
        "errors": {},
        "started_at": started_at_dt,
        "node_executions": [],
    })
    # Make the authorization row visible to the WebSocket's independent session.
    await db.commit()

    # 执行
    execution = await workflow_executor.execute(
        workflow_data=workflow_data,
        external_inputs=payload.inputs,
        execution_id=execution_id,
        user_id=str(current_user.id),
    )

    # 持久化最终执行结果
    started_at = execution.started_at
    completed_at = execution.completed_at
    await exec_service.update(execution_id, {
        "status": execution.status.value,
        "results": execution.results,
        "errors": execution.errors,
        "started_at": datetime.fromtimestamp(started_at) if started_at else None,
        "completed_at": datetime.fromtimestamp(completed_at) if completed_at else None,
        "duration": execution.duration,
        "node_executions": [r.to_dict() for r in execution.node_records.values()],
    })
    await db.commit()

    return ApiResponse.success(
        data=ExecutionDetailResponse(
            execution_id=execution.execution_id,
            status=execution.status.value,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            duration=execution.duration,
            results=execution.results,
            errors=execution.errors,
            node_executions=[r.to_dict() for r in execution.node_records.values()],
            error=execution.error,
            progress=execution.get_progress(),
        ),
        message="工作流执行完成"
    )


@router.get("/executions/{execution_id}/status", response_model=ApiResponse[ExecutionProgressResponse])
async def get_execution_status(
    execution_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取执行状态"""
    execution = workflow_executor.get_execution(execution_id)
    if execution is not None:
        if execution.user_id != str(current_user.id):
            raise HTTPException(status_code=404, detail="执行记录不存在")
        progress = execution.get_progress()
    else:
        persisted = await WorkflowExecutionService(db).get_owned(
            execution_id, current_user.id
        )
        if persisted is None:
            raise HTTPException(status_code=404, detail="执行记录不存在")
        records = persisted.node_executions or []
        completed = sum(
            1 for record in records
            if record.get("status") in ("completed", "failed", "skipped")
        )
        total = len(records)
        progress = {
            "execution_id": str(persisted.id),
            "status": persisted.status,
            "total": total,
            "completed": completed,
            "progress": completed / total if total else 0,
            "started_at": persisted.started_at.timestamp() if persisted.started_at else None,
            "completed_at": persisted.completed_at.timestamp() if persisted.completed_at else None,
            "duration": persisted.duration,
        }

    return ApiResponse.success(data=ExecutionProgressResponse(
        execution_id=progress["execution_id"],
        status=progress["status"],
        total=progress["total"],
        completed=progress["completed"],
        progress=progress["progress"],
        started_at=progress["started_at"],
        completed_at=progress["completed_at"],
        duration=progress["duration"],
    ))


@router.post("/executions/{execution_id}/cancel", response_model=ApiResponse)
async def cancel_execution(
    execution_id: str,
    current_user: User = Depends(get_current_user),
):
    """取消执行"""
    execution = workflow_executor.get_execution(execution_id)
    if execution is None or execution.user_id != str(current_user.id):
        raise HTTPException(status_code=404, detail="执行记录不存在或已完成")
    success = workflow_executor.cancel(execution_id)
    if not success:
        raise HTTPException(status_code=404, detail="执行记录不存在或已完成")
    return ApiResponse.success(message="取消请求已发送")


@router.get("/nodes", response_model=ApiResponse[list[NodeDefinitionResponse]])
async def list_available_nodes(
    current_user: User = Depends(get_current_user),
):
    """列出所有可用节点"""
    definitions = node_registry.list_definitions()
    return ApiResponse.success(data=[
        NodeDefinitionResponse(
            type=d.type, name=d.name, category=d.category.value,
            description=d.description, icon=d.icon,
            inputs=[p.model_dump() for p in d.inputs],
            outputs=[p.model_dump() for p in d.outputs],
            parameters=[p.model_dump() for p in d.parameters],
            is_async=d.is_async, estimated_time=d.estimated_time,
        ) for d in definitions
    ])


@router.get("/templates", response_model=ApiResponse[list[TemplateResponse]])
async def list_templates(
    category: Optional[str] = Query(None),
    include_premium: bool = Query(True),
    current_user: User = Depends(get_current_user),
):
    """列出工作流模板"""
    templates = template_manager.list_templates(
        category=category, include_premium=include_premium
    )
    return ApiResponse.success(data=[TemplateResponse(**t.to_dict()) for t in templates])


@router.post("/apply-template", response_model=ApiResponse[dict])
async def apply_template(
    payload: ApplyTemplateRequest,
    current_user: User = Depends(get_current_user),
):
    """应用模板，返回定制后的工作流"""
    try:
        workflow = template_manager.apply_template(
            payload.template_id, payload.customizations
        )
        return ApiResponse.success(data=workflow, message="模板应用成功")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{workflow_id}", response_model=ApiResponse[WorkflowResponse])
async def get_workflow(
    workflow_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = WorkflowService(db)
    workflow = await service.get_by_id(workflow_id)
    if not workflow or workflow.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="工作流不存在")
    return ApiResponse.success(data=WorkflowResponse.model_validate(workflow))


@router.put("/{workflow_id}", response_model=ApiResponse[WorkflowResponse])
async def update_workflow(
    workflow_id: UUID,
    payload: WorkflowUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = WorkflowService(db)
    workflow = await service.get_by_id(workflow_id)
    if not workflow or workflow.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="工作流不存在")
    updated = await service.update(workflow_id, payload.model_dump(exclude_unset=True))
    return ApiResponse.success(data=WorkflowResponse.model_validate(updated), message="更新成功")


@router.delete("/{workflow_id}", response_model=ApiResponse)
async def delete_workflow(
    workflow_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = WorkflowService(db)
    workflow = await service.get_by_id(workflow_id)
    if not workflow or workflow.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="工作流不存在")
    await service.delete(workflow_id, soft=True)
    return ApiResponse.success(message="删除成功")
