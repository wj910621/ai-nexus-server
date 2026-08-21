# backend/app/engines/workflow/executor.py
"""工作流执行引擎 - DAG 调度核心"""
import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Optional

from app.core.ws_manager import ws_manager
from app.engines.workflow.dag import (
    DAGBuilder,
    DAGValidator,
    TopologicalSorter,
    WorkflowGraph,
)
from app.engines.workflow.node_base import BaseNode, NodeStatus
from app.engines.workflow.registry import node_registry


class ExecutionStatus(str, Enum):
    """工作流执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class NodeExecutionRecord:
    """节点执行记录"""
    node_id: str
    node_type: str = ""
    status: str = "idle"
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    duration: Optional[float] = None
    result: Optional[dict] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration": self.duration,
            "result": self.result,
            "error": self.error,
        }


@dataclass
class WorkflowExecution:
    """工作流执行记录"""
    execution_id: str
    workflow_data: dict
    user_id: Optional[str] = None
    status: ExecutionStatus = ExecutionStatus.PENDING
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    duration: Optional[float] = None
    results: dict[str, dict] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    node_records: dict[str, NodeExecutionRecord] = field(default_factory=dict)
    error: Optional[str] = None

    def get_progress(self) -> dict:
        total = len(self.workflow_data.get("nodes", []))
        completed = len([r for r in self.node_records.values()
                         if r.status in ("completed", "failed", "skipped")])
        return {
            "execution_id": self.execution_id,
            "status": self.status.value,
            "total": total,
            "completed": completed,
            "progress": (completed / total) if total > 0 else 0,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration": self.duration,
        }

    def to_dict(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration": self.duration,
            "results": self.results,
            "errors": self.errors,
            "node_executions": [r.to_dict() for r in self.node_records.values()],
            "error": self.error,
            "progress": self.get_progress(),
        }


class WorkflowExecutor:
    """工作流执行器

    功能：
    - 解析工作流为 DAG
    - 拓扑排序分层并行执行
    - 数据在节点间按边传递
    - 状态追踪与错误处理
    - 支持取消执行
    """

    def __init__(self, registry=None):
        self.registry = registry or node_registry
        self._active_executions: dict[str, WorkflowExecution] = {}
        self._cancel_flags: set[str] = set()

    async def execute(
        self,
        workflow_data: dict,
        external_inputs: Optional[dict] = None,
        execution_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> WorkflowExecution:
        """执行工作流

        Args:
            workflow_data: {"nodes": [...], "edges": [...]}
            external_inputs: {node_id: {port_name: value}} 外部输入
            execution_id: 执行 ID（不传则自动生成）

        Returns:
            WorkflowExecution
        """
        execution_id = execution_id or str(uuid.uuid4())
        external_inputs = external_inputs or {}

        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_data=workflow_data,
            user_id=str(user_id) if user_id is not None else None,
            status=ExecutionStatus.RUNNING,
            started_at=time.time(),
        )
        self._active_executions[execution_id] = execution

        try:
            # 1. 解析与验证
            graph = DAGBuilder.parse(workflow_data)
            DAGValidator.validate(graph)

            # 2. 拓扑排序
            layers = TopologicalSorter.sort(graph)

            # 3. 初始化节点记录
            node_map = self._instantiate_nodes(graph, execution)

            # 4. 逐层执行
            total_nodes = len(execution.workflow_data.get("nodes", []))
            for layer in layers:
                if execution_id in self._cancel_flags:
                    execution.status = ExecutionStatus.CANCELLED
                    execution.completed_at = time.time()
                    execution.duration = execution.completed_at - execution.started_at
                    return execution

                layer_tasks = [
                    self._execute_node(graph, node_map, node_id, execution, external_inputs)
                    for node_id in layer
                ]
                await asyncio.gather(*layer_tasks, return_exceptions=True)

                # 发布进度事件
                completed = len([r for r in execution.node_records.values()
                                 if r.status in ("completed", "failed", "skipped")])
                try:
                    await ws_manager.publish(f"workflow:{execution_id}", {
                        "type": "progress",
                        "completed": completed,
                        "total": total_nodes,
                        "progress": (completed / total_nodes) if total_nodes > 0 else 0,
                    })
                except Exception:
                    pass

                # 检查本层是否有失败
                failed_in_layer = [
                    nid for nid in layer
                    if execution.node_records[nid].status == "failed"
                ]
                if failed_in_layer:
                    execution.status = ExecutionStatus.FAILED
                    execution.error = f"节点执行失败: {failed_in_layer}"
                    break

            if execution.status == ExecutionStatus.RUNNING:
                execution.status = ExecutionStatus.COMPLETED

        except Exception as e:
            execution.status = ExecutionStatus.FAILED
            execution.error = str(e)
        finally:
            execution.completed_at = time.time()
            execution.duration = round(execution.completed_at - execution.started_at, 3)
            # 移除活跃执行（保留在 _active_executions 用于查询）
            self._cancel_flags.discard(execution_id)

        # 发布执行完成事件
        try:
            await ws_manager.publish(f"workflow:{execution_id}", {
                "type": "execution_complete",
                "status": "success" if execution.status == ExecutionStatus.COMPLETED else "failed",
                "total_duration_ms": int(execution.duration * 1000) if execution.duration else 0,
            })
        except Exception:
            pass

        return execution

    def _instantiate_nodes(
        self, graph: WorkflowGraph, execution: WorkflowExecution
    ) -> dict[str, BaseNode]:
        """实例化所有节点"""
        node_map: dict[str, BaseNode] = {}
        for node_data in execution.workflow_data.get("nodes", []):
            node_id = node_data["id"]
            node_type = node_data.get("type", "")
            params = node_data.get("params", {})
            node = self.registry.create_node(node_type, node_id, params)
            node_map[node_id] = node
            execution.node_records[node_id] = NodeExecutionRecord(
                node_id=node_id, node_type=node_type, status="idle"
            )
        return node_map

    async def _execute_node(
        self,
        graph: WorkflowGraph,
        node_map: dict[str, BaseNode],
        node_id: str,
        execution: WorkflowExecution,
        external_inputs: dict,
    ) -> None:
        """执行单个节点"""
        node = node_map[node_id]
        record = execution.node_records[node_id]
        record.status = "running"
        record.started_at = time.time()
        node.status = NodeStatus.RUNNING

        channel = f"workflow:{execution.execution_id}"
        node_start_time = datetime.now(UTC)
        try:
            await ws_manager.publish(channel, {
                "type": "node_start",
                "node_id": node_id,
                "node_type": record.node_type,
                "timestamp": node_start_time.isoformat(),
            })
        except Exception:
            pass

        try:
            # 收集输入数据
            inputs: dict[str, any] = {}
            for edge in graph.get_predecessors(node_id):
                upstream_result = execution.results.get(edge.from_node, {})
                inputs[edge.to_port] = upstream_result.get(edge.from_port)

            # 合并外部输入
            if node_id in external_inputs:
                inputs.update(external_inputs[node_id])

            # 执行节点
            result = await node.execute(inputs)

            # 保存结果
            execution.results[node_id] = result
            record.result = result
            record.status = "completed"
            node.status = NodeStatus.COMPLETED

            try:
                await ws_manager.publish(channel, {
                    "type": "node_complete",
                    "node_id": node_id,
                    "result": result,
                    "duration_ms": int((datetime.now(UTC) - node_start_time).total_seconds() * 1000),
                })
            except Exception:
                pass

        except Exception as e:
            error_msg = str(e)
            execution.errors[node_id] = error_msg
            record.error = error_msg
            record.status = "failed"
            node.status = NodeStatus.FAILED

            try:
                await ws_manager.publish(channel, {
                    "type": "node_error",
                    "node_id": node_id,
                    "error": error_msg,
                })
            except Exception:
                pass
        finally:
            record.completed_at = time.time()
            if record.started_at:
                record.duration = round(record.completed_at - record.started_at, 3)

    def cancel(self, execution_id: str) -> bool:
        """取消执行"""
        if execution_id in self._active_executions:
            self._cancel_flags.add(execution_id)
            return True
        return False

    def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """获取执行记录"""
        return self._active_executions.get(execution_id)


# 全局执行器单例
workflow_executor = WorkflowExecutor()
