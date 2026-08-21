"""工作流 Schema"""
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class WorkflowBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    nodes: List[dict] = []
    edges: List[dict] = []
    category: str = "custom"


class WorkflowCreate(WorkflowBase):
    project_id: Optional[str] = None


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    nodes: Optional[List[dict]] = None
    edges: Optional[List[dict]] = None
    category: Optional[str] = None
    is_public: Optional[bool] = None


class WorkflowResponse(ORMModel):
    id: str
    user_id: str
    project_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    nodes: Any
    edges: Any
    category: str
    is_template: bool
    is_public: bool
    version: int
    created_at: datetime
    updated_at: datetime


class WorkflowExecutionCreate(BaseModel):
    workflow_id: str
    inputs: Optional[dict] = None


class WorkflowExecutionResponse(ORMModel):
    id: str
    workflow_id: str
    user_id: str
    status: str
    inputs: Optional[Any] = None
    results: Optional[Any] = None
    errors: Optional[Any] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration: Optional[float] = None
    node_executions: Optional[Any] = None


class WorkflowExecuteRequest(BaseModel):
    """工作流执行请求"""
    workflow_id: Optional[str] = None
    nodes: Optional[List[dict]] = None
    edges: Optional[List[dict]] = None
    inputs: Optional[dict] = None


class NodeDefinitionResponse(BaseModel):
    """节点定义响应"""
    type: str
    name: str
    category: str
    description: str = ""
    icon: str = ""
    inputs: List[dict] = []
    outputs: List[dict] = []
    parameters: List[dict] = []
    is_async: bool = True
    estimated_time: float = 1.0


class TemplateResponse(BaseModel):
    """模板响应"""
    template_id: str
    name: str
    description: str
    category: str = "general"
    is_premium: bool = False
    workflow_data: dict = {}
    tags: List[str] = []
    icon: str = ""


class ApplyTemplateRequest(BaseModel):
    """应用模板请求"""
    template_id: str
    customizations: Optional[dict] = None


class ExecutionProgressResponse(BaseModel):
    """执行进度响应"""
    execution_id: str
    status: str
    total: int = 0
    completed: int = 0
    progress: float = 0.0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    duration: Optional[float] = None


class ExecutionDetailResponse(BaseModel):
    """执行详情响应"""
    execution_id: str
    status: str
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    duration: Optional[float] = None
    results: dict = {}
    errors: dict = {}
    node_executions: List[dict] = []
    error: Optional[str] = None
    progress: dict = {}
