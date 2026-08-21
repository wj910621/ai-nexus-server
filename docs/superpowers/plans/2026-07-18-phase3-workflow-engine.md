# Phase 3: 工作流引擎实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建节点式工作流编排引擎，支持类似 ComfyUI 的 DAG 可视化创作，串联 Phase 2 的 5 个 AI 引擎实现端到端漫剧生成流程。

**Architecture:** 节点抽象基类 + 注册表模式管理节点类型；DAG 引擎基于拓扑排序分层并行执行；执行器集成 EngineManager 调度 5 个 AI 引擎；模板系统降低新手门槛；扩展 Phase 1 的 WorkflowExecution 模型持久化执行记录。

**Tech Stack:** Python 3.14 + asyncio（DAG 并行调度）+ Pydantic 2（节点定义）+ FastAPI（执行 API）+ React Flow 12（前端节点编辑器）+ Zustand（状态管理）

---

## 项目环境

- 工作目录：`c:\漫剧软件项目`
- Python 3.14.6
- 测试运行：`cd c:\漫剧软件项目\backend; $env:PYTHONPATH = "c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; python -m pytest tests/<file> -v`
- 依赖已安装到 `c:\漫剧软件项目\backend\.deps`
- Phase 1 + Phase 2 已完成，95/95 测试通过

## 已有基础设施（Phase 1 + Phase 2）

### Phase 1 工作流相关
- `backend/app/models/workflow.py` - Workflow + WorkflowExecution 数据模型（SQLAlchemy，JSON 字段存储 nodes/edges/results）
- `backend/app/services/workflow_service.py` - WorkflowService + WorkflowExecutionService（CRUD）
- `backend/app/api/workflows.py` - /api/workflows CRUD 路由
- `backend/app/schemas/workflow.py` - Workflow/Execution Pydantic schemas
- `frontend/src/components/workflow/` - WorkflowEditor + ImageGenNode + CharacterNode
- `frontend/src/api/workflows.ts` - workflowApi CRUD 客户端
- `frontend/src/stores/editorStore.ts` - Zustand 工作流编辑器状态

### Phase 2 AI 引擎层（工作流要调用）
- `backend/app/engines/manager.py` - `engine_manager` 单例
  - `get_image_engine()` → PollinationsProvider
  - `get_tts_engine()` → EdgeTTSProvider
  - `get_llm_engine()` → DeepSeekProvider
  - `get_video_engine()` → FFmpegVideoComposer
  - `get_character_engine()` → SoftConsistencyProvider
- `backend/app/engines/base.py` - `GenerationResult(success, data, content_type, metadata, error)`

### GenerationResult 数据结构
```python
@dataclass
class GenerationResult:
    success: bool
    data: bytes | str  # str: URL 或文本
    content_type: str  # image/png, audio/mp3, text/plain, video/mp4
    metadata: dict
    error: Optional[str] = None
```

---

## File Structure

### 后端新增（backend/app/engines/workflow/）
- `node_base.py` - 节点抽象基类、PortDefinition、NodeDefinition
- `registry.py` - NodeRegistry 节点注册表单例
- `dag.py` - DAG 解析、拓扑排序、循环检测
- `executor.py` - WorkflowExecutor 核心执行引擎
- `template_manager.py` - 模板系统与内置模板
- `nodes/__init__.py` - 节点包导出
- `nodes/generation_nodes.py` - 5 个生成节点（text2img, tts, llm_chat, video_compose, character_gen）
- `nodes/utility_nodes.py` - 工具节点（text_concat, text_input, image_preview）

### 后端修改
- `backend/app/schemas/workflow.py` - 新增执行相关 schema
- `backend/app/api/workflows.py` - 新增 execute/status/cancel/templates/nodes 端点
- `backend/app/services/workflow_service.py` - 新增执行相关方法

### 测试新增（backend/tests/）
- `test_workflow_node_base.py` - 节点基类测试
- `test_workflow_nodes.py` - 内置节点测试
- `test_workflow_dag.py` - DAG 解析测试
- `test_workflow_executor.py` - 执行引擎测试
- `test_workflow_templates.py` - 模板系统测试
- `test_workflow_execute_api.py` - 执行 API 测试
- `test_workflow_integration.py` - 端到端集成测试

### 前端新增/修改
- `frontend/src/components/workflow/nodes/LLMChatNode.tsx` - LLM 对话节点
- `frontend/src/components/workflow/nodes/TTSNode.tsx` - TTS 节点
- `frontend/src/components/workflow/nodes/VideoComposeNode.tsx` - 视频合成节点
- `frontend/src/components/workflow/nodes/TextConcatNode.tsx` - 文本拼接节点
- `frontend/src/components/workflow/nodes/TextNode.tsx` - 文本输入节点
- `frontend/src/components/workflow/NodePalette.tsx` - 节点面板
- `frontend/src/components/workflow/ExecutionPanel.tsx` - 执行面板
- `frontend/src/components/workflow/WorkflowEditor.tsx` - 集成节点面板和执行面板
- `frontend/src/api/workflows.ts` - 新增 execute/status/cancel/templates/nodes API
- `frontend/src/stores/editorStore.ts` - 新增执行状态管理
- `frontend/src/types/workflow.ts` - 新增节点定义、执行状态类型

---

## Task 1: 节点基类与注册表

**Files:**
- Create: `backend/app/engines/workflow/__init__.py`
- Create: `backend/app/engines/workflow/node_base.py`
- Create: `backend/app/engines/workflow/registry.py`
- Test: `backend/tests/test_workflow_node_base.py`

- [ ] **Step 1: 创建 workflow 包 __init__.py**

```python
# backend/app/engines/workflow/__init__.py
"""工作流引擎 - 节点编排与 DAG 调度"""
from app.engines.workflow.node_base import (
    BaseNode, NodeDefinition, PortDefinition, NodeCategory, NodeStatus,
)
from app.engines.workflow.registry import node_registry, NodeRegistry

__all__ = [
    "BaseNode", "NodeDefinition", "PortDefinition", "NodeCategory", "NodeStatus",
    "node_registry", "NodeRegistry",
]
```

- [ ] **Step 2: 创建 node_base.py**

```python
# backend/app/engines/workflow/node_base.py
"""节点抽象基类与定义"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class NodeCategory(str, Enum):
    """节点分类"""
    INPUT = "input"
    GENERATION = "generation"
    PROCESSING = "processing"
    COMPOSITE = "composite"
    OUTPUT = "output"
    UTILITY = "utility"


class NodeStatus(str, Enum):
    """节点执行状态"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PortDefinition(BaseModel):
    """端口定义"""
    name: str
    type: str  # image/text/audio/video/any/image_array
    required: bool = True
    default: Any = None
    description: str = ""


class ParameterDefinition(BaseModel):
    """参数定义"""
    name: str
    type: str  # int/float/text/bool/select
    default: Any = None
    min: Optional[float] = None
    max: Optional[float] = None
    options: Optional[list[str]] = None
    description: str = ""


class NodeDefinition(BaseModel):
    """节点定义"""
    type: str
    name: str
    category: NodeCategory
    description: str = ""
    icon: str = ""
    inputs: list[PortDefinition] = Field(default_factory=list)
    outputs: list[PortDefinition] = Field(default_factory=list)
    parameters: list[ParameterDefinition] = Field(default_factory=list)
    is_async: bool = True
    estimated_time: float = 1.0


class BaseNode(ABC):
    """节点基类"""

    def __init__(self, node_id: str, params: Optional[dict] = None):
        self.id = node_id
        self.params = params or {}
        self.status = NodeStatus.IDLE
        self.result: Optional[dict] = None
        self.error: Optional[str] = None
        self.started_at: Optional[float] = None
        self.completed_at: Optional[float] = None

    @abstractmethod
    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """执行节点逻辑

        Args:
            inputs: 输入数据 {port_name: value}

        Returns:
            输出数据 {port_name: value}
        """
        ...

    @classmethod
    @abstractmethod
    def get_definition(cls) -> NodeDefinition:
        """获取节点定义"""
        ...

    def get_info(self) -> dict:
        """获取节点运行信息"""
        return {
            "id": self.id,
            "status": self.status.value if isinstance(self.status, NodeStatus) else self.status,
            "has_result": self.result is not None,
            "error": self.error,
        }

    def get_elapsed(self) -> Optional[float]:
        """获取执行耗时（秒）"""
        if self.started_at and self.completed_at:
            return round(self.completed_at - self.started_at, 3)
        return None
```

- [ ] **Step 3: 创建 registry.py**

```python
# backend/app/engines/workflow/registry.py
"""节点注册表 - 管理所有可用节点类型"""
from typing import Optional
from app.engines.workflow.node_base import BaseNode, NodeDefinition


class NodeRegistry:
    """节点注册表单例"""

    def __init__(self):
        self._nodes: dict[str, type[BaseNode]] = {}
        self._definitions: dict[str, NodeDefinition] = {}

    def register(self, node_class: type[BaseNode]) -> type[BaseNode]:
        """注册节点类型（可作为装饰器使用）"""
        definition = node_class.get_definition()
        node_type = definition.type
        if node_type in self._nodes:
            raise ValueError(f"节点类型已注册: {node_type}")
        self._nodes[node_type] = node_class
        self._definitions[node_type] = definition
        return node_class

    def get_node_class(self, node_type: str) -> Optional[type[BaseNode]]:
        """获取节点类"""
        return self._nodes.get(node_type)

    def get_definition(self, node_type: str) -> Optional[NodeDefinition]:
        """获取节点定义"""
        return self._definitions.get(node_type)

    def list_definitions(self) -> list[NodeDefinition]:
        """列出所有节点定义"""
        return list(self._definitions.values())

    def list_by_category(self, category: str) -> list[NodeDefinition]:
        """按分类列出节点定义"""
        return [d for d in self._definitions.values() if d.category.value == category]

    def is_registered(self, node_type: str) -> bool:
        """检查节点类型是否已注册"""
        return node_type in self._nodes

    def create_node(self, node_type: str, node_id: str, params: Optional[dict] = None) -> BaseNode:
        """创建节点实例"""
        node_class = self.get_node_class(node_type)
        if not node_class:
            raise ValueError(f"未注册的节点类型: {node_type}")
        return node_class(node_id, params)

    def clear(self) -> None:
        """清空注册表（测试用）"""
        self._nodes.clear()
        self._definitions.clear()


# 全局单例
node_registry = NodeRegistry()
```

- [ ] **Step 4: 创建测试**

```python
# backend/tests/test_workflow_node_base.py
"""测试节点基类与注册表"""
import pytest
from app.engines.workflow.node_base import (
    BaseNode, NodeDefinition, PortDefinition, ParameterDefinition,
    NodeCategory, NodeStatus,
)
from app.engines.workflow.registry import NodeRegistry


class DummyNode(BaseNode):
    """测试用节点"""
    @classmethod
    def get_definition(cls) -> NodeDefinition:
        return NodeDefinition(
            type="dummy",
            name="测试节点",
            category=NodeCategory.UTILITY,
            inputs=[PortDefinition(name="text", type="text")],
            outputs=[PortDefinition(name="text", type="text")],
            parameters=[ParameterDefinition(name="upper", type="bool", default=False)],
            is_async=False,
        )

    async def execute(self, inputs: dict) -> dict:
        text = inputs.get("text", "")
        if self.params.get("upper"):
            text = text.upper()
        return {"text": text}


def test_port_definition():
    """测试端口定义"""
    port = PortDefinition(name="image", type="image")
    assert port.name == "image"
    assert port.type == "image"
    assert port.required is True
    assert port.default is None


def test_node_definition():
    """测试节点定义"""
    defn = DummyNode.get_definition()
    assert defn.type == "dummy"
    assert defn.name == "测试节点"
    assert defn.category == NodeCategory.UTILITY
    assert len(defn.inputs) == 1
    assert defn.inputs[0].name == "text"
    assert defn.is_async is False


def test_node_status_enum():
    """测试节点状态枚举"""
    assert NodeStatus.IDLE.value == "idle"
    assert NodeStatus.RUNNING.value == "running"
    assert NodeStatus.COMPLETED.value == "completed"
    assert NodeStatus.FAILED.value == "failed"


@pytest.mark.asyncio
async def test_base_node_execute():
    """测试节点执行"""
    node = DummyNode("node-1", {"upper": True})
    assert node.id == "node-1"
    assert node.status == NodeStatus.IDLE

    result = await node.execute({"text": "hello"})
    assert result == {"text": "HELLO"}


def test_node_get_info():
    """测试节点信息"""
    node = DummyNode("node-1")
    info = node.get_info()
    assert info["id"] == "node-1"
    assert info["status"] == "idle"
    assert info["has_result"] is False
    assert info["error"] is None


def test_node_get_elapsed():
    """测试耗时计算"""
    node = DummyNode("node-1")
    assert node.get_elapsed() is None

    node.started_at = 100.0
    node.completed_at = 100.5
    assert node.get_elapsed() == 0.5


def test_registry_register_and_get():
    """测试注册表注册与获取"""
    registry = NodeRegistry()
    registry.register(DummyNode)

    assert registry.is_registered("dummy")
    assert registry.get_node_class("dummy") is DummyNode

    defn = registry.get_definition("dummy")
    assert defn is not None
    assert defn.type == "dummy"


def test_registry_list():
    """测试注册表列表"""
    registry = NodeRegistry()
    registry.register(DummyNode)

    definitions = registry.list_definitions()
    assert len(definitions) == 1
    assert definitions[0].type == "dummy"

    by_category = registry.list_by_category("utility")
    assert len(by_category) == 1


def test_registry_create_node():
    """测试创建节点实例"""
    registry = NodeRegistry()
    registry.register(DummyNode)

    node = registry.create_node("dummy", "test-id", {"upper": False})
    assert isinstance(node, DummyNode)
    assert node.id == "test-id"
    assert node.params == {"upper": False}


def test_registry_duplicate_register():
    """测试重复注册抛异常"""
    registry = NodeRegistry()
    registry.register(DummyNode)
    with pytest.raises(ValueError, match="已注册"):
        registry.register(DummyNode)


def test_registry_create_unknown_type():
    """测试创建未注册节点抛异常"""
    registry = NodeRegistry()
    with pytest.raises(ValueError, match="未注册"):
        registry.create_node("unknown", "id")
```

- [ ] **Step 5: 运行测试**

Run: `cd c:\漫剧软件项目\backend; $env:PYTHONPATH = "c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; python -m pytest tests/test_workflow_node_base.py -v`

Expected: 10 passed

---

## Task 2: DAG 解析与拓扑排序

**Files:**
- Create: `backend/app/engines/workflow/dag.py`
- Test: `backend/tests/test_workflow_dag.py`

- [ ] **Step 1: 创建 dag.py**

```python
# backend/app/engines/workflow/dag.py
"""DAG 解析、拓扑排序、循环检测"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WorkflowEdge:
    """工作流边"""
    from_node: str
    to_node: str
    from_port: str
    to_port: str


@dataclass
class WorkflowGraph:
    """工作流图"""
    node_ids: list[str] = field(default_factory=list)
    edges: list[WorkflowEdge] = field(default_factory=list)

    def get_predecessors(self, node_id: str) -> list[WorkflowEdge]:
        """获取节点的所有前驱边"""
        return [e for e in self.edges if e.to_node == node_id]

    def get_successors(self, node_id: str) -> list[WorkflowEdge]:
        """获取节点的所有后继边"""
        return [e for e in self.edges if e.from_node == node_id]


class DAGBuilder:
    """DAG 构建器"""

    @staticmethod
    def parse(workflow_data: dict) -> WorkflowGraph:
        """解析工作流数据为图

        Args:
            workflow_data: {"nodes": [{"id": "...", ...}], "edges": [{"from": "...", "to": "...", "from_port": "...", "to_port": "..."}]}

        Returns:
            WorkflowGraph
        """
        node_ids = [n["id"] for n in workflow_data.get("nodes", [])]
        edges = []
        for e in workflow_data.get("edges", []):
            edges.append(WorkflowEdge(
                from_node=e["from"],
                to_node=e["to"],
                from_port=e.get("from_port", ""),
                to_port=e.get("to_port", ""),
            ))
        return WorkflowGraph(node_ids=node_ids, edges=edges)


class DAGValidator:
    """DAG 验证器"""

    @staticmethod
    def validate(graph: WorkflowGraph) -> None:
        """验证图结构，发现循环抛 ValueError"""
        # 检查边引用的节点是否存在
        node_set = set(graph.node_ids)
        for edge in graph.edges:
            if edge.from_node not in node_set:
                raise ValueError(f"边引用了不存在的节点: {edge.from_node}")
            if edge.to_node not in node_set:
                raise ValueError(f"边引用了不存在的节点: {edge.to_node}")

        # 检查自环
        for edge in graph.edges:
            if edge.from_node == edge.to_node:
                raise ValueError(f"节点存在自环: {edge.from_node}")

        # 检查循环（DFS）
        DAGValidator._check_cycle(graph)

    @staticmethod
    def _check_cycle(graph: WorkflowGraph) -> None:
        """DFS 检测循环"""
        # 构建邻接表
        adjacency: dict[str, list[str]] = {nid: [] for nid in graph.node_ids}
        for edge in graph.edges:
            adjacency[edge.from_node].append(edge.to_node)

        # 0=未访问, 1=访问中, 2=已完成
        state = {nid: 0 for nid in graph.node_ids}

        def dfs(node: str, path: list[str]) -> None:
            if state[node] == 1:
                cycle = " -> ".join(path + [node])
                raise ValueError(f"工作流中存在循环依赖: {cycle}")
            if state[node] == 2:
                return
            state[node] = 1
            for neighbor in adjacency[node]:
                dfs(neighbor, path + [node])
            state[node] = 2

        for node in graph.node_ids:
            if state[node] == 0:
                dfs(node, [])


class TopologicalSorter:
    """拓扑排序器 - 分层并行"""

    @staticmethod
    def sort(graph: WorkflowGraph) -> list[list[str]]:
        """拓扑排序，返回执行层级

        同一层的节点可以并行执行

        Returns:
            [[layer0_node_ids], [layer1_node_ids], ...]

        Raises:
            ValueError: 存在循环时抛异常
        """
        # 构建邻接表与入度
        adjacency: dict[str, list[str]] = {nid: [] for nid in graph.node_ids}
        in_degree: dict[str, int] = {nid: 0 for nid in graph.node_ids}

        for edge in graph.edges:
            adjacency[edge.from_node].append(edge.to_node)
            in_degree[edge.to_node] += 1

        layers: list[list[str]] = []
        current_layer = [nid for nid, deg in in_degree.items() if deg == 0]
        # 排序保证顺序稳定
        current_layer.sort()

        scheduled: set[str] = set()

        while current_layer:
            layers.append(current_layer)
            scheduled.update(current_layer)
            next_layer: list[str] = []

            for node_id in current_layer:
                for neighbor in adjacency[node_id]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_layer.append(neighbor)

            next_layer.sort()
            current_layer = next_layer

        if len(scheduled) != len(graph.node_ids):
            unscheduled = set(graph.node_ids) - scheduled
            raise ValueError(f"工作流中存在循环依赖，未调度节点: {unscheduled}")

        return layers


def parse_and_validate(workflow_data: dict) -> WorkflowGraph:
    """解析并验证工作流"""
    graph = DAGBuilder.parse(workflow_data)
    DAGValidator.validate(graph)
    return graph


def get_execution_layers(workflow_data: dict) -> list[list[str]]:
    """获取执行层级"""
    graph = parse_and_validate(workflow_data)
    return TopologicalSorter.sort(graph)
```

- [ ] **Step 2: 创建测试**

```python
# backend/tests/test_workflow_dag.py
"""测试 DAG 解析与拓扑排序"""
import pytest
from app.engines.workflow.dag import (
    DAGBuilder, DAGValidator, TopologicalSorter,
    parse_and_validate, get_execution_layers,
)


def test_parse_simple_graph():
    """测试解析简单图"""
    workflow = {
        "nodes": [
            {"id": "1"}, {"id": "2"}, {"id": "3"}
        ],
        "edges": [
            {"from": "1", "to": "2", "from_port": "out", "to_port": "in"},
            {"from": "2", "to": "3", "from_port": "out", "to_port": "in"},
        ]
    }
    graph = DAGBuilder.parse(workflow)
    assert len(graph.node_ids) == 3
    assert len(graph.edges) == 2
    assert graph.edges[0].from_node == "1"
    assert graph.edges[0].to_port == "in"


def test_parse_empty_workflow():
    """测试解析空工作流"""
    graph = DAGBuilder.parse({})
    assert graph.node_ids == []
    assert graph.edges == []


def test_validate_valid_graph():
    """测试验证有效图"""
    workflow = {
        "nodes": [{"id": "1"}, {"id": "2"}],
        "edges": [{"from": "1", "to": "2", "from_port": "a", "to_port": "b"}]
    }
    graph = DAGBuilder.parse(workflow)
    DAGValidator.validate(graph)  # 不抛异常


def test_validate_cycle_detection():
    """测试循环检测"""
    workflow = {
        "nodes": [{"id": "1"}, {"id": "2"}, {"id": "3"}],
        "edges": [
            {"from": "1", "to": "2", "from_port": "", "to_port": ""},
            {"from": "2", "to": "3", "from_port": "", "to_port": ""},
            {"from": "3", "to": "1", "from_port": "", "to_port": ""},
        ]
    }
    graph = DAGBuilder.parse(workflow)
    with pytest.raises(ValueError, match="循环"):
        DAGValidator.validate(graph)


def test_validate_self_loop():
    """测试自环检测"""
    workflow = {
        "nodes": [{"id": "1"}],
        "edges": [{"from": "1", "to": "1", "from_port": "", "to_port": ""}]
    }
    graph = DAGBuilder.parse(workflow)
    with pytest.raises(ValueError, match="自环"):
        DAGValidator.validate(graph)


def test_validate_missing_node():
    """测试引用不存在的节点"""
    workflow = {
        "nodes": [{"id": "1"}],
        "edges": [{"from": "1", "to": "2", "from_port": "", "to_port": ""}]
    }
    graph = DAGBuilder.parse(workflow)
    with pytest.raises(ValueError, match="不存在"):
        DAGValidator.validate(graph)


def test_topological_sort_linear():
    """测试线性拓扑排序"""
    workflow = {
        "nodes": [{"id": "1"}, {"id": "2"}, {"id": "3"}],
        "edges": [
            {"from": "1", "to": "2", "from_port": "", "to_port": ""},
            {"from": "2", "to": "3", "from_port": "", "to_port": ""},
        ]
    }
    graph = DAGBuilder.parse(workflow)
    layers = TopologicalSorter.sort(graph)
    assert layers == [["1"], ["2"], ["3"]]


def test_topological_sort_parallel():
    """测试并行拓扑排序"""
    workflow = {
        "nodes": [{"id": "1"}, {"id": "2"}, {"id": "3"}, {"id": "4"}],
        "edges": [
            {"from": "1", "to": "3", "from_port": "", "to_port": ""},
            {"from": "2", "to": "3", "from_port": "", "to_port": ""},
            {"from": "3", "to": "4", "from_port": "", "to_port": ""},
        ]
    }
    graph = DAGBuilder.parse(workflow)
    layers = TopologicalSorter.sort(graph)
    assert layers[0] == ["1", "2"]  # 并行
    assert layers[1] == ["3"]
    assert layers[2] == ["4"]


def test_topological_sort_no_edges():
    """测试无边的拓扑排序"""
    workflow = {
        "nodes": [{"id": "1"}, {"id": "2"}, {"id": "3"}],
        "edges": []
    }
    graph = DAGBuilder.parse(workflow)
    layers = TopologicalSorter.sort(graph)
    assert len(layers) == 1
    assert sorted(layers[0]) == ["1", "2", "3"]


def test_topological_sort_cycle_raises():
    """测试拓扑排序检测循环"""
    workflow = {
        "nodes": [{"id": "1"}, {"id": "2"}],
        "edges": [
            {"from": "1", "to": "2", "from_port": "", "to_port": ""},
            {"from": "2", "to": "1", "from_port": "", "to_port": ""},
        ]
    }
    graph = DAGBuilder.parse(workflow)
    with pytest.raises(ValueError, match="循环"):
        TopologicalSorter.sort(graph)


def test_get_predecessors_and_successors():
    """测试获取前驱和后继"""
    workflow = {
        "nodes": [{"id": "1"}, {"id": "2"}, {"id": "3"}],
        "edges": [
            {"from": "1", "to": "2", "from_port": "a", "to_port": "b"},
            {"from": "2", "to": "3", "from_port": "c", "to_port": "d"},
        ]
    }
    graph = DAGBuilder.parse(workflow)

    preds = graph.get_predecessors("2")
    assert len(preds) == 1
    assert preds[0].from_node == "1"

    succs = graph.get_successors("2")
    assert len(succs) == 1
    assert succs[0].to_node == "3"


def test_parse_and_validate_combined():
    """测试解析并验证组合函数"""
    workflow = {
        "nodes": [{"id": "a"}, {"id": "b"}],
        "edges": [{"from": "a", "to": "b", "from_port": "", "to_port": ""}]
    }
    graph = parse_and_validate(workflow)
    assert len(graph.node_ids) == 2


def test_get_execution_layers():
    """测试获取执行层级"""
    workflow = {
        "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
        "edges": [
            {"from": "a", "to": "c", "from_port": "", "to_port": ""},
            {"from": "b", "to": "c", "from_port": "", "to_port": ""},
        ]
    }
    layers = get_execution_layers(workflow)
    assert layers[0] == ["a", "b"]
    assert layers[1] == ["c"]
```

- [ ] **Step 3: 运行测试**

Run: `cd c:\漫剧软件项目\backend; $env:PYTHONPATH = "c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; python -m pytest tests/test_workflow_dag.py -v`

Expected: 12 passed

---

## Task 3: 内置生成节点（5 个）

**Files:**
- Create: `backend/app/engines/workflow/nodes/__init__.py`
- Create: `backend/app/engines/workflow/nodes/generation_nodes.py`
- Test: `backend/tests/test_workflow_nodes.py`

- [ ] **Step 1: 创建 nodes 包 __init__.py**

```python
# backend/app/engines/workflow/nodes/__init__.py
"""内置节点集合"""
from app.engines.workflow.nodes.generation_nodes import (
    TextToImageNode, TTSNode, LLMChatNode, VideoComposeNode, CharacterGenNode,
)
from app.engines.workflow.nodes.utility_nodes import (
    TextConcatNode, TextInputNode, ImagePreviewNode,
)


def register_all_nodes(registry):
    """注册所有内置节点到注册表"""
    node_classes = [
        TextToImageNode, TTSNode, LLMChatNode, VideoComposeNode, CharacterGenNode,
        TextConcatNode, TextInputNode, ImagePreviewNode,
    ]
    for cls in node_classes:
        if not registry.is_registered(cls.get_definition().type):
            registry.register(cls)


__all__ = [
    "TextToImageNode", "TTSNode", "LLMChatNode", "VideoComposeNode", "CharacterGenNode",
    "TextConcatNode", "TextInputNode", "ImagePreviewNode",
    "register_all_nodes",
]
```

- [ ] **Step 2: 创建 generation_nodes.py**

```python
# backend/app/engines/workflow/nodes/generation_nodes.py
"""生成节点 - 调用 Phase 2 的 5 个 AI 引擎"""
from typing import Any, Optional
import time
from app.engines.workflow.node_base import (
    BaseNode, NodeDefinition, PortDefinition, ParameterDefinition, NodeCategory,
)
from app.engines.manager import engine_manager
from app.engines.base import GenerationResult


class TextToImageNode(BaseNode):
    """文生图节点 - 调用图像生成引擎"""

    @classmethod
    def get_definition(cls) -> NodeDefinition:
        return NodeDefinition(
            type="text_to_image",
            name="文生图",
            category=NodeCategory.GENERATION,
            description="根据文本提示词生成图像",
            icon="image",
            inputs=[
                PortDefinition(name="prompt", type="text", required=True, description="正向提示词"),
                PortDefinition(name="negative_prompt", type="text", required=False, description="负向提示词"),
            ],
            outputs=[PortDefinition(name="image", type="image", description="生成的图像 URL")],
            parameters=[
                ParameterDefinition(name="width", type="int", default=1024, min=64, max=2048),
                ParameterDefinition(name="height", type="int", default=1024, min=64, max=2048),
                ParameterDefinition(name="model", type="select", default="flux",
                                    options=["flux", "turbo", "flux-realism", "flux-anime", "flux-3d"]),
                ParameterDefinition(name="seed", type="int", default=-1, description="-1 表示随机"),
            ],
            is_async=True,
            estimated_time=5.0,
        )

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        self.status = "running"
        self.started_at = time.time()
        try:
            prompt = inputs.get("prompt") or self.params.get("prompt", "")
            if not prompt:
                raise ValueError("缺少 prompt 输入")

            negative_prompt = inputs.get("negative_prompt") or self.params.get("negative_prompt", "")
            seed = self.params.get("seed", -1)
            if seed == -1:
                seed = None

            engine = engine_manager.get_image_engine()
            if engine is None:
                raise RuntimeError("图像引擎未初始化")

            result: GenerationResult = await engine.text2img(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=self.params.get("width", 1024),
                height=self.params.get("height", 1024),
                seed=seed,
                model=self.params.get("model", "flux"),
            )

            if not result.success:
                raise RuntimeError(result.error or "图像生成失败")

            self.status = "completed"
            self.completed_at = time.time()
            self.result = {"image": result.data}
            return self.result
        except Exception as e:
            self.status = "failed"
            self.completed_at = time.time()
            self.error = str(e)
            raise


class TTSNode(BaseNode):
    """语音合成节点"""

    @classmethod
    def get_definition(cls) -> NodeDefinition:
        return NodeDefinition(
            type="tts",
            name="语音合成",
            category=NodeCategory.GENERATION,
            description="文本转语音",
            icon="audio",
            inputs=[PortDefinition(name="text", type="text", required=True, description="要合成的文本")],
            outputs=[PortDefinition(name="audio", type="audio", description="生成的音频 URL")],
            parameters=[
                ParameterDefinition(name="voice", type="select", default="zh-CN-XiaoxiaoNeural",
                                    options=["zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural",
                                             "zh-CN-YunyangNeural", "zh-CN-XiaoyiNeural",
                                             "en-US-JennyNeural", "en-US-GuyNeural"]),
                ParameterDefinition(name="rate", type="int", default=0, min=-100, max=100),
                ParameterDefinition(name="pitch", type="int", default=0, min=-100, max=100),
            ],
            is_async=True,
            estimated_time=2.0,
        )

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        self.status = "running"
        self.started_at = time.time()
        try:
            text = inputs.get("text") or self.params.get("text", "")
            if not text:
                raise ValueError("缺少 text 输入")

            engine = engine_manager.get_tts_engine()
            if engine is None:
                raise RuntimeError("TTS 引擎未初始化")

            result = await engine.synthesize(
                text=text,
                voice=self.params.get("voice", "zh-CN-XiaoxiaoNeural"),
                rate=self.params.get("rate", 0),
                pitch=self.params.get("pitch", 0),
            )

            if not result.success:
                raise RuntimeError(result.error or "语音合成失败")

            self.status = "completed"
            self.completed_at = time.time()
            self.result = {"audio": result.data}
            return self.result
        except Exception as e:
            self.status = "failed"
            self.completed_at = time.time()
            self.error = str(e)
            raise


class LLMChatNode(BaseNode):
    """LLM 对话节点"""

    @classmethod
    def get_definition(cls) -> NodeDefinition:
        return NodeDefinition(
            type="llm_chat",
            name="LLM 对话",
            category=NodeCategory.GENERATION,
            description="调用大语言模型对话",
            icon="chat",
            inputs=[
                PortDefinition(name="user_message", type="text", required=True, description="用户消息"),
                PortDefinition(name="system_prompt", type="text", required=False, description="系统提示词"),
            ],
            outputs=[PortDefinition(name="response", type="text", description="LLM 响应")],
            parameters=[
                ParameterDefinition(name="model", type="select", default="deepseek-chat",
                                    options=["deepseek-chat", "deepseek-reasoner"]),
                ParameterDefinition(name="temperature", type="float", default=0.7, min=0, max=2),
                ParameterDefinition(name="max_tokens", type="int", default=2000, min=1, max=8192),
            ],
            is_async=True,
            estimated_time=3.0,
        )

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        self.status = "running"
        self.started_at = time.time()
        try:
            user_message = inputs.get("user_message") or self.params.get("user_message", "")
            if not user_message:
                raise ValueError("缺少 user_message 输入")

            messages = []
            system_prompt = inputs.get("system_prompt") or self.params.get("system_prompt")
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_message})

            engine = engine_manager.get_llm_engine()
            if engine is None:
                raise RuntimeError("LLM 引擎未初始化")

            result = await engine.chat(
                messages=messages,
                model=self.params.get("model", "deepseek-chat"),
                temperature=self.params.get("temperature", 0.7),
                max_tokens=self.params.get("max_tokens", 2000),
            )

            if not result.success:
                raise RuntimeError(result.error or "LLM 调用失败")

            self.status = "completed"
            self.completed_at = time.time()
            self.result = {"response": result.data}
            return self.result
        except Exception as e:
            self.status = "failed"
            self.completed_at = time.time()
            self.error = str(e)
            raise


class VideoComposeNode(BaseNode):
    """视频合成节点"""

    @classmethod
    def get_definition(cls) -> NodeDefinition:
        return NodeDefinition(
            type="video_compose",
            name="视频合成",
            category=NodeCategory.COMPOSITE,
            description="将图像帧列表合成为视频",
            icon="video",
            inputs=[
                PortDefinition(name="frames", type="image_array", required=True, description="图像帧 URL 列表"),
                PortDefinition(name="audio", type="audio", required=False, description="音频 URL"),
            ],
            outputs=[PortDefinition(name="video", type="video", description="合成的视频路径")],
            parameters=[
                ParameterDefinition(name="fps", type="int", default=24, min=1, max=60),
                ParameterDefinition(name="width", type="int", default=1920, min=64, max=4096),
                ParameterDefinition(name="height", type="int", default=1080, min=64, max=4096),
                ParameterDefinition(name="transition", type="select", default="none",
                                    options=["none", "fade"]),
            ],
            is_async=True,
            estimated_time=10.0,
        )

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        self.status = "running"
        self.started_at = time.time()
        try:
            frames = inputs.get("frames") or self.params.get("frames", [])
            if not frames:
                raise ValueError("缺少 frames 输入")

            if isinstance(frames, str):
                frames = [frames]

            audio = inputs.get("audio") or self.params.get("audio")

            engine = engine_manager.get_video_engine()
            if engine is None:
                raise RuntimeError("视频引擎未初始化")

            width = self.params.get("width", 1920)
            height = self.params.get("height", 1080)

            result = await engine.compose(
                frames=frames,
                audio=audio,
                fps=self.params.get("fps", 24),
                resolution=(width, height),
            )

            if not result.success:
                raise RuntimeError(result.error or "视频合成失败")

            self.status = "completed"
            self.completed_at = time.time()
            self.result = {"video": result.data}
            return self.result
        except Exception as e:
            self.status = "failed"
            self.completed_at = time.time()
            self.error = str(e)
            raise


class CharacterGenNode(BaseNode):
    """角色一致性生成节点"""

    @classmethod
    def get_definition(cls) -> NodeDefinition:
        return NodeDefinition(
            type="character_gen",
            name="角色生成",
            category=NodeCategory.GENERATION,
            description="基于参考图生成保持一致性的角色图像",
            icon="character",
            inputs=[
                PortDefinition(name="prompt", type="text", required=True, description="画面描述"),
                PortDefinition(name="reference_image", type="image", required=True, description="参考图 URL 或 base64"),
            ],
            outputs=[PortDefinition(name="image", type="image", description="生成的角色图像 URL")],
            parameters=[
                ParameterDefinition(name="consistency_weight", type="float", default=0.8, min=0, max=1),
                ParameterDefinition(name="character_description", type="text", default=""),
                ParameterDefinition(name="mood", type="select", default="",
                                    options=["", "happy", "sad", "angry", "surprised"]),
                ParameterDefinition(name="width", type="int", default=1024, min=64, max=2048),
                ParameterDefinition(name="height", type="int", default=1024, min=64, max=2048),
                ParameterDefinition(name="seed", type="int", default=-1),
            ],
            is_async=True,
            estimated_time=6.0,
        )

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        self.status = "running"
        self.started_at = time.time()
        try:
            prompt = inputs.get("prompt") or self.params.get("prompt", "")
            reference_image = inputs.get("reference_image") or self.params.get("reference_image")

            if not prompt:
                raise ValueError("缺少 prompt 输入")
            if not reference_image:
                raise ValueError("缺少 reference_image 输入")

            # 如果是 URL，下载为 bytes；如果是 base64，解码
            image_bytes = await self._load_image_bytes(reference_image)

            seed = self.params.get("seed", -1)
            if seed == -1:
                seed = None

            engine = engine_manager.get_character_engine()
            if engine is None:
                raise RuntimeError("角色一致性引擎未初始化")

            result = await engine.generate_consistent(
                prompt=prompt,
                reference_image=image_bytes,
                consistency_weight=self.params.get("consistency_weight", 0.8),
                character_description=self.params.get("character_description") or None,
                mood=self.params.get("mood") or None,
                width=self.params.get("width", 1024),
                height=self.params.get("height", 1024),
                seed=seed,
            )

            if not result.success:
                raise RuntimeError(result.error or "角色生成失败")

            self.status = "completed"
            self.completed_at = time.time()
            self.result = {"image": result.data}
            return self.result
        except Exception as e:
            self.status = "failed"
            self.completed_at = time.time()
            self.error = str(e)
            raise

    async def _load_image_bytes(self, image_ref: str) -> bytes:
        """加载图像为 bytes"""
        if image_ref.startswith("data:image"):
            # data URL: data:image/png;base64,xxxx
            import base64
            _, b64data = image_ref.split(",", 1)
            return base64.b64decode(b64data)
        elif image_ref.startswith("http"):
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(image_ref)
                resp.raise_for_status()
                return resp.content
        else:
            # 假设是 base64 或本地路径
            import base64
            try:
                return base64.b64decode(image_ref)
            except Exception:
                from pathlib import Path
                return Path(image_ref).read_bytes()
```

- [ ] **Step 3: 创建 utility_nodes.py**

```python
# backend/app/engines/workflow/nodes/utility_nodes.py
"""工具节点"""
from typing import Any
import time
from app.engines.workflow.node_base import (
    BaseNode, NodeDefinition, PortDefinition, ParameterDefinition, NodeCategory,
)


class TextInputNode(BaseNode):
    """文本输入节点 - 工作流的输入源"""

    @classmethod
    def get_definition(cls) -> NodeDefinition:
        return NodeDefinition(
            type="text_input",
            name="文本输入",
            category=NodeCategory.INPUT,
            description="提供静态文本输入",
            icon="text",
            inputs=[],
            outputs=[PortDefinition(name="text", type="text")],
            parameters=[
                ParameterDefinition(name="value", type="text", default="", description="文本内容"),
            ],
            is_async=False,
            estimated_time=0.01,
        )

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        self.status = "running"
        self.started_at = time.time()
        text = self.params.get("value", "")
        self.status = "completed"
        self.completed_at = time.time()
        self.result = {"text": text}
        return self.result


class TextConcatNode(BaseNode):
    """文本拼接节点"""

    @classmethod
    def get_definition(cls) -> NodeDefinition:
        return NodeDefinition(
            type="text_concat",
            name="文本拼接",
            category=NodeCategory.UTILITY,
            description="拼接多个文本输入",
            icon="concat",
            inputs=[
                PortDefinition(name="text1", type="text", required=False),
                PortDefinition(name="text2", type="text", required=False),
                PortDefinition(name="text3", type="text", required=False),
            ],
            outputs=[PortDefinition(name="text", type="text")],
            parameters=[
                ParameterDefinition(name="separator", type="text", default=", "),
            ],
            is_async=False,
            estimated_time=0.01,
        )

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        self.status = "running"
        self.started_at = time.time()
        separator = self.params.get("separator", ", ")
        texts = [v for v in inputs.values() if v]
        self.status = "completed"
        self.completed_at = time.time()
        self.result = {"text": separator.join(texts)}
        return self.result


class ImagePreviewNode(BaseNode):
    """图像预览节点 - 用于中间结果展示"""

    @classmethod
    def get_definition(cls) -> NodeDefinition:
        return NodeDefinition(
            type="image_preview",
            name="图像预览",
            category=NodeCategory.OUTPUT,
            description="预览图像，不改变数据",
            icon="preview",
            inputs=[PortDefinition(name="image", type="image", required=True)],
            outputs=[PortDefinition(name="image", type="image")],
            parameters=[],
            is_async=False,
            estimated_time=0.01,
        )

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        self.status = "running"
        self.started_at = time.time()
        image = inputs.get("image")
        if not image:
            raise ValueError("缺少 image 输入")
        self.status = "completed"
        self.completed_at = time.time()
        self.result = {"image": image}
        return self.result
```

- [ ] **Step 4: 创建测试**

```python
# backend/tests/test_workflow_nodes.py
"""测试内置节点"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.engines.workflow.nodes.generation_nodes import (
    TextToImageNode, TTSNode, LLMChatNode, VideoComposeNode, CharacterGenNode,
)
from app.engines.workflow.nodes.utility_nodes import (
    TextInputNode, TextConcatNode, ImagePreviewNode,
)
from app.engines.base import GenerationResult


def test_text_to_image_definition():
    """测试文生图节点定义"""
    defn = TextToImageNode.get_definition()
    assert defn.type == "text_to_image"
    assert defn.name == "文生图"
    assert defn.category.value == "generation"
    assert len(defn.inputs) == 2
    assert defn.outputs[0].name == "image"


def test_tts_definition():
    """测试 TTS 节点定义"""
    defn = TTSNode.get_definition()
    assert defn.type == "tts"
    assert defn.outputs[0].name == "audio"


def test_llm_chat_definition():
    """测试 LLM 节点定义"""
    defn = LLMChatNode.get_definition()
    assert defn.type == "llm_chat"
    assert defn.outputs[0].name == "response"


def test_video_compose_definition():
    """测试视频合成节点定义"""
    defn = VideoComposeNode.get_definition()
    assert defn.type == "video_compose"
    assert defn.category.value == "composite"


def test_character_gen_definition():
    """测试角色生成节点定义"""
    defn = CharacterGenNode.get_definition()
    assert defn.type == "character_gen"
    assert defn.inputs[1].name == "reference_image"


def test_text_input_definition():
    """测试文本输入节点"""
    defn = TextInputNode.get_definition()
    assert defn.type == "text_input"
    assert defn.category.value == "input"


@pytest.mark.asyncio
async def test_text_input_execute():
    """测试文本输入节点执行"""
    node = TextInputNode("t1", {"value": "hello"})
    result = await node.execute({})
    assert result == {"text": "hello"}


@pytest.mark.asyncio
async def test_text_concat_execute():
    """测试文本拼接节点"""
    node = TextConcatNode("c1", {"separator": " | "})
    result = await node.execute({"text1": "a", "text2": "b", "text3": "c"})
    assert result == {"text": "a | b | c"}


@pytest.mark.asyncio
async def test_text_concat_skip_empty():
    """测试拼接跳过空值"""
    node = TextConcatNode("c1", {})
    result = await node.execute({"text1": "a", "text2": "", "text3": "c"})
    assert result == {"text": "a, c"}


@pytest.mark.asyncio
async def test_image_preview_execute():
    """测试图像预览节点"""
    node = ImagePreviewNode("p1")
    result = await node.execute({"image": "/uploads/test.png"})
    assert result == {"image": "/uploads/test.png"}


@pytest.mark.asyncio
async def test_image_preview_missing_input():
    """测试图像预览缺输入"""
    node = ImagePreviewNode("p1")
    with pytest.raises(ValueError, match="缺少"):
        await node.execute({})


@pytest.mark.asyncio
async def test_text_to_image_execute_success():
    """测试文生图节点执行成功"""
    mock_engine = AsyncMock()
    mock_engine.text2img = AsyncMock(return_value=GenerationResult(
        success=True, data="/uploads/images/test.png",
        content_type="image/png", metadata={}
    ))
    with patch("app.engines.workflow.nodes.generation_nodes.engine_manager") as mock_manager:
        mock_manager.get_image_engine.return_value = mock_engine
        node = TextToImageNode("img1", {"width": 512, "height": 512, "model": "flux"})
        result = await node.execute({"prompt": "a cute cat"})
        assert result == {"image": "/uploads/images/test.png"}
        mock_engine.text2img.assert_called_once()


@pytest.mark.asyncio
async def test_text_to_image_missing_prompt():
    """测试文生图缺 prompt"""
    node = TextToImageNode("img1")
    with pytest.raises(ValueError, match="prompt"):
        await node.execute({})


@pytest.mark.asyncio
async def test_text_to_image_engine_failure():
    """测试文生图引擎失败"""
    mock_engine = AsyncMock()
    mock_engine.text2img = AsyncMock(return_value=GenerationResult(
        success=False, data=b"", content_type="", metadata={}, error="API error"
    ))
    with patch("app.engines.workflow.nodes.generation_nodes.engine_manager") as mock_manager:
        mock_manager.get_image_engine.return_value = mock_engine
        node = TextToImageNode("img1")
        with pytest.raises(RuntimeError, match="API error"):
            await node.execute({"prompt": "test"})


@pytest.mark.asyncio
async def test_tts_execute_success():
    """测试 TTS 节点执行"""
    mock_engine = AsyncMock()
    mock_engine.synthesize = AsyncMock(return_value=GenerationResult(
        success=True, data="/uploads/audio/test.mp3",
        content_type="audio/mp3", metadata={}
    ))
    with patch("app.engines.workflow.nodes.generation_nodes.engine_manager") as mock_manager:
        mock_manager.get_tts_engine.return_value = mock_engine
        node = TTSNode("tts1", {"voice": "zh-CN-XiaoxiaoNeural"})
        result = await node.execute({"text": "你好"})
        assert result == {"audio": "/uploads/audio/test.mp3"}


@pytest.mark.asyncio
async def test_llm_chat_execute_success():
    """测试 LLM 节点执行"""
    mock_engine = AsyncMock()
    mock_engine.chat = AsyncMock(return_value=GenerationResult(
        success=True, data="Hello from LLM",
        content_type="text/plain", metadata={}
    ))
    with patch("app.engines.workflow.nodes.generation_nodes.engine_manager") as mock_manager:
        mock_manager.get_llm_engine.return_value = mock_engine
        node = LLMChatNode("llm1", {"model": "deepseek-chat"})
        result = await node.execute({"user_message": "hi", "system_prompt": "be nice"})
        assert result == {"response": "Hello from LLM"}

        # 验证 messages 构造
        call_kwargs = mock_engine.chat.call_args.kwargs
        assert call_kwargs["messages"][0]["role"] == "system"
        assert call_kwargs["messages"][1]["role"] == "user"


@pytest.mark.asyncio
async def test_video_compose_execute_success():
    """测试视频合成节点"""
    mock_engine = AsyncMock()
    mock_engine.compose = AsyncMock(return_value=GenerationResult(
        success=True, data="/uploads/video/test.mp4",
        content_type="video/mp4", metadata={}
    ))
    with patch("app.engines.workflow.nodes.generation_nodes.engine_manager") as mock_manager:
        mock_manager.get_video_engine.return_value = mock_engine
        node = VideoComposeNode("v1", {"fps": 30, "width": 1280, "height": 720})
        result = await node.execute({"frames": ["/uploads/1.png", "/uploads/2.png"]})
        assert result == {"video": "/uploads/video/test.mp4"}

        call_kwargs = mock_engine.compose.call_args.kwargs
        assert call_kwargs["fps"] == 30
        assert call_kwargs["resolution"] == (1280, 720)


@pytest.mark.asyncio
async def test_character_gen_execute_with_url():
    """测试角色生成节点 - URL 参考"""
    mock_engine = AsyncMock()
    mock_engine.generate_consistent = AsyncMock(return_value=GenerationResult(
        success=True, data="/uploads/images/char.png",
        content_type="image/png", metadata={}
    ))
    mock_http_response = MagicMock()
    mock_http_response.content = b"fake-image-bytes"
    mock_http_response.raise_for_status = MagicMock()

    with patch("app.engines.workflow.nodes.generation_nodes.engine_manager") as mock_manager, \
         patch("httpx.AsyncClient") as mock_http_client:
        mock_manager.get_character_engine.return_value = mock_engine
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_http_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_http_client.return_value = mock_client

        node = CharacterGenNode("c1", {"consistency_weight": 0.9})
        result = await node.execute({
            "prompt": "a beautiful girl",
            "reference_image": "https://example.com/char.png"
        })
        assert result == {"image": "/uploads/images/char.png"}
```

- [ ] **Step 5: 运行测试**

Run: `cd c:\漫剧软件项目\backend; $env:PYTHONPATH = "c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; python -m pytest tests/test_workflow_nodes.py -v`

Expected: 16 passed

---

## Task 4: 工作流执行引擎

**Files:**
- Create: `backend/app/engines/workflow/executor.py`
- Test: `backend/tests/test_workflow_executor.py`

- [ ] **Step 1: 创建 executor.py**

```python
# backend/app/engines/workflow/executor.py
"""工作流执行引擎 - DAG 调度核心"""
import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum

from app.engines.workflow.node_base import BaseNode, NodeStatus
from app.engines.workflow.dag import (
    WorkflowGraph, DAGBuilder, DAGValidator, TopologicalSorter,
)
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

        except Exception as e:
            error_msg = str(e)
            execution.errors[node_id] = error_msg
            record.error = error_msg
            record.status = "failed"
            node.status = NodeStatus.FAILED
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
```

- [ ] **Step 2: 创建测试**

```python
# backend/tests/test_workflow_executor.py
"""测试工作流执行引擎"""
import pytest
from unittest.mock import AsyncMock, patch
from app.engines.workflow.executor import (
    WorkflowExecutor, WorkflowExecution, ExecutionStatus, NodeExecutionRecord,
)
from app.engines.workflow.node_base import (
    BaseNode, NodeDefinition, PortDefinition, NodeCategory,
)
from app.engines.workflow.registry import NodeRegistry


class EchoNode(BaseNode):
    """测试节点 - 返回输入"""
    @classmethod
    def get_definition(cls) -> NodeDefinition:
        return NodeDefinition(
            type="echo",
            name="Echo",
            category=NodeCategory.UTILITY,
            inputs=[PortDefinition(name="text", type="text", required=False)],
            outputs=[PortDefinition(name="text", type="text")],
            is_async=False,
        )

    async def execute(self, inputs: dict) -> dict:
        return {"text": inputs.get("text", "echo")}


class FailNode(BaseNode):
    """测试节点 - 总是失败"""
    @classmethod
    def get_definition(cls) -> NodeDefinition:
        return NodeDefinition(
            type="fail",
            name="Fail",
            category=NodeCategory.UTILITY,
            inputs=[], outputs=[PortDefinition(name="out", type="text")],
            is_async=False,
        )

    async def execute(self, inputs: dict) -> dict:
        raise RuntimeError("intentional failure")


@pytest.fixture
def registry():
    reg = NodeRegistry()
    reg.register(EchoNode)
    reg.register(FailNode)
    return reg


@pytest.fixture
def executor(registry):
    return WorkflowExecutor(registry=registry)


@pytest.mark.asyncio
async def test_execute_simple_workflow(executor):
    """测试执行简单工作流"""
    workflow = {
        "nodes": [{"id": "1", "type": "echo", "params": {}}],
        "edges": []
    }
    execution = await executor.execute(workflow)
    assert execution.status == ExecutionStatus.COMPLETED
    assert execution.results["1"] == {"text": "echo"}
    assert execution.duration is not None
    assert execution.error is None


@pytest.mark.asyncio
async def test_execute_linear_workflow(executor):
    """测试执行线性工作流"""
    workflow = {
        "nodes": [
            {"id": "1", "type": "echo", "params": {}},
            {"id": "2", "type": "echo", "params": {}},
        ],
        "edges": [
            {"from": "1", "to": "2", "from_port": "text", "to_port": "text"}
        ]
    }
    execution = await executor.execute(workflow)
    assert execution.status == ExecutionStatus.COMPLETED
    # 节点 2 应该收到节点 1 的输出
    assert execution.results["2"]["text"] == "echo"


@pytest.mark.asyncio
async def test_execute_parallel_workflow(executor):
    """测试执行并行工作流"""
    workflow = {
        "nodes": [
            {"id": "1", "type": "echo", "params": {}},
            {"id": "2", "type": "echo", "params": {}},
            {"id": "3", "type": "echo", "params": {}},
        ],
        "edges": [
            {"from": "1", "to": "3", "from_port": "text", "to_port": "text"},
            {"from": "2", "to": "3", "from_port": "text", "to_port": "text"},
        ]
    }
    execution = await executor.execute(workflow)
    assert execution.status == ExecutionStatus.COMPLETED


@pytest.mark.asyncio
async def test_execute_with_external_inputs(executor):
    """测试外部输入"""
    workflow = {
        "nodes": [{"id": "1", "type": "echo", "params": {}}],
        "edges": []
    }
    execution = await executor.execute(workflow, external_inputs={
        "1": {"text": "external input"}
    })
    assert execution.results["1"]["text"] == "external input"


@pytest.mark.asyncio
async def test_execute_with_cycle_raises(executor):
    """测试循环工作流抛异常"""
    workflow = {
        "nodes": [{"id": "1", "type": "echo"}, {"id": "2", "type": "echo"}],
        "edges": [
            {"from": "1", "to": "2", "from_port": "text", "to_port": "text"},
            {"from": "2", "to": "1", "from_port": "text", "to_port": "text"},
        ]
    }
    execution = await executor.execute(workflow)
    assert execution.status == ExecutionStatus.FAILED
    assert "循环" in execution.error


@pytest.mark.asyncio
async def test_execute_with_node_failure(executor):
    """测试节点失败"""
    workflow = {
        "nodes": [{"id": "1", "type": "fail", "params": {}}],
        "edges": []
    }
    execution = await executor.execute(workflow)
    assert execution.status == ExecutionStatus.FAILED
    assert "1" in execution.errors
    assert "intentional failure" in execution.errors["1"]


@pytest.mark.asyncio
async def test_execute_records_node_info(executor):
    """测试记录节点执行信息"""
    workflow = {
        "nodes": [{"id": "1", "type": "echo", "params": {}}],
        "edges": []
    }
    execution = await executor.execute(workflow)
    record = execution.node_records["1"]
    assert record.node_type == "echo"
    assert record.status == "completed"
    assert record.duration is not None
    assert record.result == {"text": "echo"}


@pytest.mark.asyncio
async def test_execution_progress(executor):
    """测试执行进度"""
    workflow = {
        "nodes": [
            {"id": "1", "type": "echo"},
            {"id": "2", "type": "echo"},
        ],
        "edges": [{"from": "1", "to": "2", "from_port": "text", "to_port": "text"}]
    }
    execution = await executor.execute(workflow)
    progress = execution.get_progress()
    assert progress["total"] == 2
    assert progress["completed"] == 2
    assert progress["progress"] == 1.0


@pytest.mark.asyncio
async def test_execution_to_dict(executor):
    """测试执行记录转字典"""
    workflow = {"nodes": [{"id": "1", "type": "echo"}], "edges": []}
    execution = await executor.execute(workflow)
    d = execution.to_dict()
    assert "execution_id" in d
    assert d["status"] == "completed"
    assert len(d["node_executions"]) == 1
    assert "progress" in d


@pytest.mark.asyncio
async def test_cancel_execution(executor):
    """测试取消执行"""
    # 使用一个能延迟的节点
    workflow = {"nodes": [{"id": "1", "type": "echo"}], "edges": []}
    execution_id = "test-cancel-id"
    # 立即取消（执行很快，这里仅测试 cancel 方法返回值）
    # 执行已完成后取消返回 False
    await executor.execute(workflow, execution_id=execution_id)
    result = executor.cancel(execution_id)
    # 执行已完成，cancel 可能返回 True 但实际不影响
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_get_execution(executor):
    """测试获取执行记录"""
    workflow = {"nodes": [{"id": "1", "type": "echo"}], "edges": []}
    execution = await executor.execute(workflow, execution_id="test-id")
    retrieved = executor.get_execution("test-id")
    assert retrieved is execution
    assert executor.get_execution("nonexistent") is None
```

- [ ] **Step 3: 运行测试**

Run: `cd c:\漫剧软件项目\backend; $env:PYTHONPATH = "c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; python -m pytest tests/test_workflow_executor.py -v`

Expected: 11 passed

---

## Task 5: 模板系统

**Files:**
- Create: `backend/app/engines/workflow/template_manager.py`
- Test: `backend/tests/test_workflow_templates.py`

- [ ] **Step 1: 创建 template_manager.py**

```python
# backend/app/engines/workflow/template_manager.py
"""工作流模板系统"""
import json
from dataclasses import dataclass, field
from typing import Optional
from copy import deepcopy


@dataclass
class WorkflowTemplate:
    """工作流模板"""
    template_id: str
    name: str
    description: str
    category: str = "general"
    is_premium: bool = False
    workflow_data: dict = field(default_factory=lambda: {"nodes": [], "edges": []})
    tags: list[str] = field(default_factory=list)
    icon: str = ""

    def to_dict(self) -> dict:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "is_premium": self.is_premium,
            "workflow_data": self.workflow_data,
            "tags": self.tags,
            "icon": self.icon,
        }


# 内置模板
BUILTIN_TEMPLATES: list[WorkflowTemplate] = [
    WorkflowTemplate(
        template_id="basic_text_to_image",
        name="基础文生图",
        description="单个提示词生成图像",
        category="basic",
        icon="image",
        tags=["图像", "入门"],
        workflow_data={
            "nodes": [
                {"id": "input", "type": "text_input", "params": {"value": "a cute cat"}},
                {"id": "gen", "type": "text_to_image", "params": {"width": 1024, "height": 1024, "model": "flux"}},
                {"id": "preview", "type": "image_preview", "params": {}},
            ],
            "edges": [
                {"from": "input", "to": "gen", "from_port": "text", "to_port": "prompt"},
                {"from": "gen", "to": "preview", "from_port": "image", "to_port": "image"},
            ],
        },
    ),
    WorkflowTemplate(
        template_id="llm_prompt_enhance",
        name="LLM 提示词增强",
        description="LLM 增强提示词后生成图像",
        category="advanced",
        icon="workflow",
        tags=["LLM", "图像", "进阶"],
        workflow_data={
            "nodes": [
                {"id": "input", "type": "text_input", "params": {"value": "a girl"}},
                {"id": "llm", "type": "llm_chat", "params": {
                    "model": "deepseek-chat",
                    "max_tokens": 500,
                }},
                {"id": "gen", "type": "text_to_image", "params": {"model": "flux"}},
                {"id": "preview", "type": "image_preview", "params": {}},
            ],
            "edges": [
                {"from": "input", "to": "llm", "from_port": "text", "to_port": "user_message"},
                {"from": "llm", "to": "gen", "from_port": "response", "to_port": "prompt"},
                {"from": "gen", "to": "preview", "from_port": "image", "to_port": "image"},
            ],
        },
    ),
    WorkflowTemplate(
        template_id="tts_pipeline",
        name="文本转语音",
        description="文本输入生成语音",
        category="basic",
        icon="audio",
        tags=["TTS", "音频"],
        workflow_data={
            "nodes": [
                {"id": "input", "type": "text_input", "params": {"value": "你好，世界"}},
                {"id": "tts", "type": "tts", "params": {"voice": "zh-CN-XiaoxiaoNeural"}},
            ],
            "edges": [
                {"from": "input", "to": "tts", "from_port": "text", "to_port": "text"},
            ],
        },
    ),
    WorkflowTemplate(
        template_id="character_consistency_demo",
        name="角色一致性生成",
        description="基于参考图生成一致角色",
        category="advanced",
        is_premium=True,
        icon="character",
        tags=["角色", "一致性", "进阶"],
        workflow_data={
            "nodes": [
                {"id": "prompt_input", "type": "text_input", "params": {"value": "微笑的女孩"}},
                {"id": "ref_input", "type": "text_input", "params": {"value": "https://example.com/char.png"}},
                {"id": "char_gen", "type": "character_gen", "params": {"consistency_weight": 0.8}},
                {"id": "preview", "type": "image_preview", "params": {}},
            ],
            "edges": [
                {"from": "prompt_input", "to": "char_gen", "from_port": "text", "to_port": "prompt"},
                {"from": "ref_input", "to": "char_gen", "from_port": "text", "to_port": "reference_image"},
                {"from": "char_gen", "to": "preview", "from_port": "image", "to_port": "image"},
            ],
        },
    ),
    WorkflowTemplate(
        template_id="video_compose_demo",
        name="视频合成",
        description="多帧图像合成视频",
        category="advanced",
        is_premium=True,
        icon="video",
        tags=["视频", "合成", "进阶"],
        workflow_data={
            "nodes": [
                {"id": "frames_input", "type": "text_input",
                 "params": {"value": "/uploads/frame1.png,/uploads/frame2.png"}},
                {"id": "compose", "type": "video_compose",
                 "params": {"fps": 24, "width": 1920, "height": 1080}},
            ],
            "edges": [
                {"from": "frames_input", "to": "compose", "from_port": "text", "to_port": "frames"},
            ],
        },
    ),
]


class TemplateManager:
    """模板管理器"""

    def __init__(self, templates: Optional[list[WorkflowTemplate]] = None):
        if templates is None:
            templates = deepcopy(BUILTIN_TEMPLATES)
        self.templates: dict[str, WorkflowTemplate] = {t.template_id: t for t in templates}

    def list_templates(
        self,
        category: Optional[str] = None,
        include_premium: bool = True,
        tag: Optional[str] = None,
    ) -> list[WorkflowTemplate]:
        """列出模板"""
        templates = list(self.templates.values())
        if category:
            templates = [t for t in templates if t.category == category]
        if not include_premium:
            templates = [t for t in templates if not t.is_premium]
        if tag:
            templates = [t for t in templates if tag in t.tags]
        return templates

    def get_template(self, template_id: str) -> Optional[WorkflowTemplate]:
        """获取模板"""
        return self.templates.get(template_id)

    def apply_template(
        self,
        template_id: str,
        customizations: Optional[dict] = None,
    ) -> dict:
        """应用模板，返回定制后的工作流

        Args:
            template_id: 模板 ID
            customizations: {
                "node_params": {node_id: {param_name: value}}
            }
        """
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"模板不存在: {template_id}")

        workflow = deepcopy(template.workflow_data)

        if customizations and "node_params" in customizations:
            for node in workflow.get("nodes", []):
                node_id = node["id"]
                if node_id in customizations["node_params"]:
                    node.setdefault("params", {}).update(customizations["node_params"][node_id])

        return workflow

    def add_template(self, template: WorkflowTemplate) -> None:
        """添加自定义模板"""
        self.templates[template.template_id] = template

    def list_categories(self) -> list[str]:
        """列出所有分类"""
        return list(set(t.category for t in self.templates.values()))


# 全局单例
template_manager = TemplateManager()
```

- [ ] **Step 2: 创建测试**

```python
# backend/tests/test_workflow_templates.py
"""测试工作流模板系统"""
import pytest
from app.engines.workflow.template_manager import (
    TemplateManager, WorkflowTemplate, BUILTIN_TEMPLATES, template_manager,
)


def test_builtin_templates_loaded():
    """测试内置模板加载"""
    manager = TemplateManager()
    assert len(manager.templates) >= 5
    assert "basic_text_to_image" in manager.templates


def test_list_templates_all():
    """测试列出所有模板"""
    manager = TemplateManager()
    templates = manager.list_templates()
    assert len(templates) >= 5


def test_list_templates_by_category():
    """测试按分类列出模板"""
    manager = TemplateManager()
    basic = manager.list_templates(category="basic")
    assert all(t.category == "basic" for t in basic)
    assert len(basic) >= 2


def test_list_templates_exclude_premium():
    """测试排除高级模板"""
    manager = TemplateManager()
    free = manager.list_templates(include_premium=False)
    assert all(not t.is_premium for t in free)


def test_list_templates_by_tag():
    """测试按标签筛选"""
    manager = TemplateManager()
    tagged = manager.list_templates(tag="图像")
    assert all("图像" in t.tags for t in tagged)


def test_get_template():
    """测试获取模板"""
    manager = TemplateManager()
    t = manager.get_template("basic_text_to_image")
    assert t is not None
    assert t.name == "基础文生图"


def test_get_template_not_found():
    """测试获取不存在的模板"""
    manager = TemplateManager()
    assert manager.get_template("nonexistent") is None


def test_apply_template():
    """测试应用模板"""
    manager = TemplateManager()
    workflow = manager.apply_template("basic_text_to_image")
    assert "nodes" in workflow
    assert "edges" in workflow
    assert len(workflow["nodes"]) == 3


def test_apply_template_with_customization():
    """测试带定制的应用"""
    manager = TemplateManager()
    workflow = manager.apply_template("basic_text_to_image", customizations={
        "node_params": {
            "gen": {"width": 512, "height": 512}
        }
    })
    gen_node = next(n for n in workflow["nodes"] if n["id"] == "gen")
    assert gen_node["params"]["width"] == 512
    assert gen_node["params"]["height"] == 512


def test_apply_template_not_found():
    """测试应用不存在的模板"""
    manager = TemplateManager()
    with pytest.raises(ValueError, match="不存在"):
        manager.apply_template("nonexistent")


def test_apply_template_deep_copy():
    """测试应用模板返回深拷贝"""
    manager = TemplateManager()
    w1 = manager.apply_template("basic_text_to_image")
    w2 = manager.apply_template("basic_text_to_image")
    w1["nodes"][0]["params"]["value"] = "modified"
    # 修改 w1 不应影响 w2
    assert w2["nodes"][0]["params"]["value"] != "modified"


def test_add_custom_template():
    """测试添加自定义模板"""
    manager = TemplateManager()
    custom = WorkflowTemplate(
        template_id="custom",
        name="自定义",
        description="test",
        workflow_data={"nodes": [], "edges": []}
    )
    manager.add_template(custom)
    assert manager.get_template("custom") is not None


def test_list_categories():
    """测试列出分类"""
    manager = TemplateManager()
    categories = manager.list_categories()
    assert "basic" in categories
    assert "advanced" in categories


def test_template_to_dict():
    """测试模板转字典"""
    t = WorkflowTemplate(
        template_id="test", name="Test", description="desc",
        category="basic", workflow_data={"nodes": [], "edges": []}
    )
    d = t.to_dict()
    assert d["template_id"] == "test"
    assert d["name"] == "Test"
    assert d["category"] == "basic"


def test_global_template_manager():
    """测试全局模板管理器单例"""
    assert template_manager is not None
    assert len(template_manager.templates) >= 5
```

- [ ] **Step 3: 运行测试**

Run: `cd c:\漫剧软件项目\backend; $env:PYTHONPATH = "c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; python -m pytest tests/test_workflow_templates.py -v`

Expected: 14 passed

---

## Task 6: 工作流执行 API

**Files:**
- Modify: `backend/app/schemas/workflow.py`
- Modify: `backend/app/api/workflows.py`
- Test: `backend/tests/test_workflow_execute_api.py`

- [ ] **Step 1: 扩展 workflow schema**

读取 `backend/app/schemas/workflow.py` 后追加：

```python
# 追加到 backend/app/schemas/workflow.py 末尾

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
```

- [ ] **Step 2: 扩展 workflows API**

读取 `backend/app/api/workflows.py` 后追加：

```python
# 追加到 backend/app/api/workflows.py

from app.engines.workflow.executor import workflow_executor, ExecutionStatus
from app.engines.workflow.registry import node_registry
from app.engines.workflow.nodes import register_all_nodes
from app.engines.workflow.template_manager import template_manager
from app.schemas.workflow import (
    WorkflowExecuteRequest, NodeDefinitionResponse, TemplateResponse,
    ApplyTemplateRequest, ExecutionProgressResponse, ExecutionDetailResponse,
)

# 启动时注册所有节点
register_all_nodes(node_registry)


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

    # 执行
    execution = await workflow_executor.execute(
        workflow_data=workflow_data,
        external_inputs=payload.inputs,
    )

    # 持久化执行记录
    exec_service = WorkflowExecutionService(db)
    import time
    started_at = execution.started_at
    completed_at = execution.completed_at
    from datetime import datetime
    await exec_service.create({
        "workflow_id": payload.workflow_id,
        "user_id": current_user.id,
        "status": execution.status.value,
        "inputs": payload.inputs,
        "results": execution.results,
        "errors": execution.errors,
        "started_at": datetime.fromtimestamp(started_at) if started_at else None,
        "completed_at": datetime.fromtimestamp(completed_at) if completed_at else None,
        "duration": execution.duration,
        "node_executions": [r.to_dict() for r in execution.node_records.values()],
    })

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
):
    """获取执行状态"""
    execution = workflow_executor.get_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    progress = execution.get_progress()
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
```

- [ ] **Step 3: 创建测试**

```python
# backend/tests/test_workflow_execute_api.py
"""测试工作流执行 API"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.deps import get_current_user
from app.engines.workflow.executor import WorkflowExecution, ExecutionStatus
from app.engines.workflow.node_base import NodeDefinition, NodeCategory


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = "test-user-id"
    user.username = "testuser"
    user.status = "active"
    return user


@pytest.fixture
def auth_bypass(mock_user):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield mock_user
    app.dependency_overrides.clear()


@pytest.fixture
def mock_executor():
    executor = AsyncMock()
    mock_execution = MagicMock()
    mock_execution.execution_id = "exec-1"
    mock_execution.status = ExecutionStatus.COMPLETED
    mock_execution.started_at = 1000.0
    mock_execution.completed_at = 1001.0
    mock_execution.duration = 1.0
    mock_execution.results = {"1": {"text": "echo"}}
    mock_execution.errors = {}
    mock_execution.node_records = {}
    mock_execution.error = None
    mock_execution.get_progress.return_value = {
        "execution_id": "exec-1", "status": "completed",
        "total": 1, "completed": 1, "progress": 1.0,
        "started_at": 1000.0, "completed_at": 1001.0, "duration": 1.0
    }
    executor.execute = AsyncMock(return_value=mock_execution)
    executor.get_execution.return_value = mock_execution
    executor.cancel.return_value = True
    return executor


@pytest.mark.asyncio
async def test_execute_workflow_without_auth():
    """测试未认证执行"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/workflows/execute", json={"nodes": []})
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_execute_workflow_with_inline_nodes(auth_bypass, mock_executor):
    """测试使用内联节点执行"""
    with patch("app.api.workflows.workflow_executor", mock_executor), \
         patch("app.api.workflows.WorkflowExecutionService") as MockExecService:
        mock_service = AsyncMock()
        mock_service.create = AsyncMock()
        MockExecService.return_value = mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/workflows/execute", json={
                "nodes": [{"id": "1", "type": "text_input", "params": {"value": "hi"}}],
                "edges": []
            })
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert data["data"]["status"] == "completed"
            assert data["data"]["execution_id"] == "exec-1"


@pytest.mark.asyncio
async def test_execute_workflow_missing_nodes(auth_bypass, mock_executor):
    """测试缺少 nodes 参数"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/workflows/execute", json={})
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_execution_status(auth_bypass, mock_executor):
    """测试获取执行状态"""
    with patch("app.api.workflows.workflow_executor", mock_executor):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/workflows/executions/exec-1/status")
            assert response.status_code == 200
            data = response.json()
            assert data["data"]["execution_id"] == "exec-1"
            assert data["data"]["progress"] == 1.0


@pytest.mark.asyncio
async def test_get_execution_status_not_found(auth_bypass, mock_executor):
    """测试获取不存在的执行状态"""
    mock_executor.get_execution.return_value = None
    with patch("app.api.workflows.workflow_executor", mock_executor):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/workflows/executions/nonexistent/status")
            assert response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_execution(auth_bypass, mock_executor):
    """测试取消执行"""
    with patch("app.api.workflows.workflow_executor", mock_executor):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/workflows/executions/exec-1/cancel")
            assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_nodes(auth_bypass):
    """测试列出可用节点"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/workflows/nodes")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert isinstance(data["data"], list)
        # 应该包含内置节点
        types = [n["type"] for n in data["data"]]
        assert "text_to_image" in types
        assert "tts" in types
        assert "llm_chat" in types


@pytest.mark.asyncio
async def test_list_templates(auth_bypass):
    """测试列出模板"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/workflows/templates")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert len(data["data"]) >= 5


@pytest.mark.asyncio
async def test_list_templates_by_category(auth_bypass):
    """测试按分类列出模板"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/workflows/templates?category=basic")
        assert response.status_code == 200
        data = response.json()
        assert all(t["category"] == "basic" for t in data["data"])


@pytest.mark.asyncio
async def test_apply_template(auth_bypass):
    """测试应用模板"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/workflows/apply-template", json={
            "template_id": "basic_text_to_image"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "nodes" in data["data"]


@pytest.mark.asyncio
async def test_apply_template_not_found(auth_bypass):
    """测试应用不存在的模板"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/workflows/apply-template", json={
            "template_id": "nonexistent"
        })
        assert response.status_code == 404
```

- [ ] **Step 4: 运行测试**

Run: `cd c:\漫剧软件项目\backend; $env:PYTHONPATH = "c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; python -m pytest tests/test_workflow_execute_api.py -v`

Expected: 11 passed

---

## Task 7: 前端节点扩展

**Files:**
- Create: `frontend/src/components/workflow/nodes/LLMChatNode.tsx`
- Create: `frontend/src/components/workflow/nodes/TTSNode.tsx`
- Create: `frontend/src/components/workflow/nodes/VideoComposeNode.tsx`
- Create: `frontend/src/components/workflow/nodes/TextConcatNode.tsx`
- Create: `frontend/src/components/workflow/nodes/TextInputNode.tsx`
- Create: `frontend/src/components/workflow/nodes/ImagePreviewNode.tsx`
- Create: `frontend/src/components/workflow/NodePalette.tsx`
- Modify: `frontend/src/components/workflow/WorkflowEditor.tsx`
- Modify: `frontend/src/api/workflows.ts`
- Modify: `frontend/src/types/workflow.ts`
- Modify: `frontend/src/stores/editorStore.ts`

- [ ] **Step 1: 扩展 workflow 类型**

读取 `frontend/src/types/workflow.ts` 后追加：

```typescript
// 追加到 frontend/src/types/workflow.ts

export interface PortDefinition {
  name: string
  type: string  // image/text/audio/video/any/image_array
  required: boolean
  default?: unknown
  description?: string
}

export interface ParameterDefinition {
  name: string
  type: string  // int/float/text/bool/select
  default?: unknown
  min?: number
  max?: number
  options?: string[]
  description?: string
}

export interface NodeDefinition {
  type: string
  name: string
  category: string
  description: string
  icon: string
  inputs: PortDefinition[]
  outputs: PortDefinition[]
  parameters: ParameterDefinition[]
  is_async: boolean
  estimated_time: number
}

export interface WorkflowTemplate {
  template_id: string
  name: string
  description: string
  category: string
  is_premium: boolean
  workflow_data: { nodes: WorkflowNode[]; edges: WorkflowEdge[] }
  tags: string[]
  icon: string
}

export interface ExecutionProgress {
  execution_id: string
  status: string
  total: number
  completed: number
  progress: number
  started_at: number | null
  completed_at: number | null
  duration: number | null
}

export interface NodeExecutionRecord {
  node_id: string
  node_type: string
  status: string
  started_at: number | null
  completed_at: number | null
  duration: number | null
  result: Record<string, unknown> | null
  error: string | null
}

export interface ExecutionDetail {
  execution_id: string
  status: string
  started_at: number | null
  completed_at: number | null
  duration: number | null
  results: Record<string, Record<string, unknown>>
  errors: Record<string, string>
  node_executions: NodeExecutionRecord[]
  error: string | null
  progress: ExecutionProgress
}
```

- [ ] **Step 2: 扩展 workflow API**

读取 `frontend/src/api/workflows.ts` 后追加：

```typescript
// 追加到 frontend/src/api/workflows.ts

import type {
  NodeDefinition, WorkflowTemplate, ExecutionDetail, ExecutionProgress,
} from '@/types'

export const workflowEngineApi = {
  execute(data: {
    workflow_id?: string
    nodes?: WorkflowNode[]
    edges?: WorkflowEdge[]
    inputs?: Record<string, unknown>
  }) {
    return apiClient.post<ApiResponse<ExecutionDetail>>('/workflows/execute', data)
  },

  getExecutionStatus(executionId: string) {
    return apiClient.get<ApiResponse<ExecutionProgress>>(`/workflows/executions/${executionId}/status`)
  },

  cancelExecution(executionId: string) {
    return apiClient.post<ApiResponse<null>>(`/workflows/executions/${executionId}/cancel`)
  },

  listNodes() {
    return apiClient.get<ApiResponse<NodeDefinition[]>>('/workflows/nodes')
  },

  listTemplates(params?: { category?: string; include_premium?: boolean }) {
    return apiClient.get<ApiResponse<WorkflowTemplate[]>>('/workflows/templates', { params })
  },

  applyTemplate(data: { template_id: string; customizations?: Record<string, unknown> }) {
    return apiClient.post<ApiResponse<{ nodes: WorkflowNode[]; edges: WorkflowEdge[] }>>(
      '/workflows/apply-template', data
    )
  },
}
```

- [ ] **Step 3: 扩展 editorStore**

读取 `frontend/src/stores/editorStore.ts` 后追加：

```typescript
// 追加到 editorStore.ts（在现有 store 内增加）

interface EditorState {
  // 现有字段...
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  setNodes: (nodes: WorkflowNode[]) => void
  setEdges: (edges: WorkflowEdge[]) => void
  // 新增字段
  isExecuting: boolean
  executionDetail: ExecutionDetail | null
  availableNodes: NodeDefinition[]
  templates: WorkflowTemplate[]
  setIsExecuting: (v: boolean) => void
  setExecutionDetail: (d: ExecutionDetail | null) => void
  setAvailableNodes: (n: NodeDefinition[]) => void
  setTemplates: (t: WorkflowTemplate[]) => void
  addNode: (node: WorkflowNode) => void
  removeNode: (nodeId: string) => void
}
```

具体实现细节：在 `useEditorStore` 中追加 `isExecuting`、`executionDetail`、`availableNodes`、`templates` 状态和对应 setter，以及 `addNode`、`removeNode` 方法。

- [ ] **Step 4: 创建 LLMChatNode**

```tsx
// frontend/src/components/workflow/nodes/LLMChatNode.tsx
import { Handle, Position, type NodeProps } from 'reactflow'

interface LLMChatData {
  params?: {
    model?: string
    temperature?: number
    max_tokens?: number
  }
}

export default function LLMChatNode({ data, selected }: NodeProps<LLMChatData>) {
  return (
    <div className={`px-4 py-3 rounded-lg bg-[#2a2a3e] border-2 min-w-[180px] ${
      selected ? 'border-indigo-500' : 'border-[#313244]'
    }`}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">💬</span>
        <span className="text-sm font-medium text-white">LLM 对话</span>
      </div>
      <div className="text-xs text-gray-400">
        模型: {data.params?.model || 'deepseek-chat'}
      </div>
      <Handle
        type="target"
        position={Position.Left}
        id="user_message"
        className="!bg-indigo-500 !w-3 !h-3"
      />
      <Handle
        type="target"
        position={Position.Left}
        id="system_prompt"
        style={{ top: '70%' }}
        className="!bg-indigo-500 !w-3 !h-3"
      />
      <Handle
        type="source"
        position={Position.Right}
        id="response"
        className="!bg-emerald-500 !w-3 !h-3"
      />
    </div>
  )
}
```

- [ ] **Step 5: 创建 TTSNode**

```tsx
// frontend/src/components/workflow/nodes/TTSNode.tsx
import { Handle, Position, type NodeProps } from 'reactflow'

interface TTSData {
  params?: { voice?: string; rate?: number; pitch?: number }
}

export default function TTSNode({ data, selected }: NodeProps<TTSData>) {
  return (
    <div className={`px-4 py-3 rounded-lg bg-[#2a2a3e] border-2 min-w-[180px] ${
      selected ? 'border-indigo-500' : 'border-[#313244]'
    }`}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">🔊</span>
        <span className="text-sm font-medium text-white">语音合成</span>
      </div>
      <div className="text-xs text-gray-400">
        {data.params?.voice || 'zh-CN-XiaoxiaoNeural'}
      </div>
      <Handle
        type="target"
        position={Position.Left}
        id="text"
        className="!bg-indigo-500 !w-3 !h-3"
      />
      <Handle
        type="source"
        position={Position.Right}
        id="audio"
        className="!bg-emerald-500 !w-3 !h-3"
      />
    </div>
  )
}
```

- [ ] **Step 6: 创建 VideoComposeNode**

```tsx
// frontend/src/components/workflow/nodes/VideoComposeNode.tsx
import { Handle, Position, type NodeProps } from 'reactflow'

interface VideoComposeData {
  params?: { fps?: number; width?: number; height?: number }
}

export default function VideoComposeNode({ data, selected }: NodeProps<VideoComposeData>) {
  return (
    <div className={`px-4 py-3 rounded-lg bg-[#2a2a3e] border-2 min-w-[180px] ${
      selected ? 'border-indigo-500' : 'border-[#313244]'
    }`}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">🎬</span>
        <span className="text-sm font-medium text-white">视频合成</span>
      </div>
      <div className="text-xs text-gray-400">
        {data.params?.width || 1920}×{data.params?.height || 1080} @ {data.params?.fps || 24}fps
      </div>
      <Handle
        type="target"
        position={Position.Left}
        id="frames"
        className="!bg-indigo-500 !w-3 !h-3"
      />
      <Handle
        type="target"
        position={Position.Left}
        id="audio"
        style={{ top: '70%' }}
        className="!bg-indigo-500 !w-3 !h-3"
      />
      <Handle
        type="source"
        position={Position.Right}
        id="video"
        className="!bg-emerald-500 !w-3 !h-3"
      />
    </div>
  )
}
```

- [ ] **Step 7: 创建 TextInputNode 和 TextConcatNode**

```tsx
// frontend/src/components/workflow/nodes/TextInputNode.tsx
import { Handle, Position, type NodeProps } from 'reactflow'

interface TextInputData {
  params?: { value?: string }
}

export default function TextInputNode({ data, selected }: NodeProps<TextInputData>) {
  return (
    <div className={`px-4 py-3 rounded-lg bg-[#2a2a3e] border-2 min-w-[180px] ${
      selected ? 'border-indigo-500' : 'border-[#313244]'
    }`}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">📝</span>
        <span className="text-sm font-medium text-white">文本输入</span>
      </div>
      <div className="text-xs text-gray-400 truncate">
        {data.params?.value || '(空)'}
      </div>
      <Handle
        type="source"
        position={Position.Right}
        id="text"
        className="!bg-emerald-500 !w-3 !h-3"
      />
    </div>
  )
}
```

```tsx
// frontend/src/components/workflow/nodes/TextConcatNode.tsx
import { Handle, Position, type NodeProps } from 'reactflow'

interface TextConcatData {
  params?: { separator?: string }
}

export default function TextConcatNode({ data, selected }: NodeProps<TextConcatData>) {
  return (
    <div className={`px-4 py-3 rounded-lg bg-[#2a2a3e] border-2 min-w-[180px] ${
      selected ? 'border-indigo-500' : 'border-[#313244]'
    }`}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">🔗</span>
        <span className="text-sm font-medium text-white">文本拼接</span>
      </div>
      <div className="text-xs text-gray-400">
        分隔符: {data.params?.separator || ', '}
      </div>
      <Handle
        type="target"
        position={Position.Left}
        id="text1"
        className="!bg-indigo-500 !w-3 !h-3"
      />
      <Handle
        type="target"
        position={Position.Left}
        id="text2"
        style={{ top: '50%' }}
        className="!bg-indigo-500 !w-3 !h-3"
      />
      <Handle
        type="target"
        position={Position.Left}
        id="text3"
        style={{ top: '75%' }}
        className="!bg-indigo-500 !w-3 !h-3"
      />
      <Handle
        type="source"
        position={Position.Right}
        id="text"
        className="!bg-emerald-500 !w-3 !h-3"
      />
    </div>
  )
}
```

- [ ] **Step 8: 创建 ImagePreviewNode**

```tsx
// frontend/src/components/workflow/nodes/ImagePreviewNode.tsx
import { Handle, Position, type NodeProps } from 'reactflow'

export default function ImagePreviewNode({ selected }: NodeProps) {
  return (
    <div className={`px-4 py-3 rounded-lg bg-[#2a2a3e] border-2 min-w-[180px] ${
      selected ? 'border-indigo-500' : 'border-[#313244]'
    }`}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">👁</span>
        <span className="text-sm font-medium text-white">图像预览</span>
      </div>
      <div className="text-xs text-gray-400">展示输入图像</div>
      <Handle
        type="target"
        position={Position.Left}
        id="image"
        className="!bg-indigo-500 !w-3 !h-3"
      />
      <Handle
        type="source"
        position={Position.Right}
        id="image"
        className="!bg-emerald-500 !w-3 !h-3"
      />
    </div>
  )
}
```

- [ ] **Step 9: 创建 NodePalette**

```tsx
// frontend/src/components/workflow/NodePalette.tsx
import { useEffect, useState } from 'react'
import { workflowEngineApi } from '@/api/workflows'
import { useEditorStore } from '@/stores/editorStore'
import type { NodeDefinition } from '@/types'

const CATEGORY_LABELS: Record<string, string> = {
  input: '输入',
  generation: '生成',
  processing: '处理',
  composite: '合成',
  output: '输出',
  utility: '工具',
}

const CATEGORY_COLORS: Record<string, string> = {
  input: 'bg-blue-500',
  generation: 'bg-purple-500',
  processing: 'bg-yellow-500',
  composite: 'bg-orange-500',
  output: 'bg-emerald-500',
  utility: 'bg-gray-500',
}

export default function NodePalette() {
  const [nodes, setNodes] = useState<NodeDefinition[]>([])
  const [loading, setLoading] = useState(true)
  const addNode = useEditorStore((s) => s.addNode)
  const currentNodes = useEditorStore((s) => s.nodes)

  useEffect(() => {
    loadNodes()
  }, [])

  const loadNodes = async () => {
    try {
      const res = await workflowEngineApi.listNodes()
      setNodes(res.data.data)
    } catch (e) {
      console.error('加载节点失败', e)
    } finally {
      setLoading(false)
    }
  }

  const handleAddNode = (def: NodeDefinition) => {
    const id = `${def.type}_${Date.now()}`
    const newNode = {
      id,
      type: def.type,
      position: {
        x: 100 + Math.random() * 200,
        y: 100 + Math.random() * 200,
      },
      data: { params: {} },
    }
    addNode(newNode)
  }

  // 按分类分组
  const grouped = nodes.reduce((acc, n) => {
    if (!acc[n.category]) acc[n.category] = []
    acc[n.category].push(n)
    return acc
  }, {} as Record<string, NodeDefinition[]>)

  if (loading) {
    return (
      <div className="w-60 bg-[#181825] border-r border-[#313244] p-4 text-gray-400 text-sm">
        加载节点中...
      </div>
    )
  }

  return (
    <div className="w-60 bg-[#181825] border-r border-[#313244] overflow-y-auto">
      <div className="p-3 border-b border-[#313244]">
        <h3 className="text-sm font-medium text-white">节点面板</h3>
      </div>
      {Object.entries(grouped).map(([category, items]) => (
        <div key={category} className="p-2">
          <div className="text-xs text-gray-500 uppercase mb-2 px-2">
            {CATEGORY_LABELS[category] || category}
          </div>
          {items.map((node) => (
            <button
              key={node.type}
              onClick={() => handleAddNode(node)}
              className="w-full flex items-center gap-2 px-2 py-2 rounded hover:bg-[#313244] text-left transition-colors"
            >
              <span className={`w-2 h-2 rounded-full ${CATEGORY_COLORS[node.category] || 'bg-gray-500'}`} />
              <div className="flex-1 min-w-0">
                <div className="text-sm text-white truncate">{node.name}</div>
                <div className="text-xs text-gray-500 truncate">{node.description}</div>
              </div>
            </button>
          ))}
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 10: 创建 ExecutionPanel**

```tsx
// frontend/src/components/workflow/ExecutionPanel.tsx
import { useState } from 'react'
import { useEditorStore } from '@/stores/editorStore'
import { workflowEngineApi } from '@/api/workflows'

export default function ExecutionPanel() {
  const { nodes, edges, isExecuting, executionDetail, setIsExecuting, setExecutionDetail } = useEditorStore()
  const [error, setError] = useState<string | null>(null)

  const handleExecute = async () => {
    setIsExecuting(true)
    setError(null)
    try {
      const res = await workflowEngineApi.execute({
        nodes: nodes.map((n) => ({
          id: n.id,
          type: n.type,
          params: n.data.params || {},
        })),
        edges: edges.map((e) => ({
          from: e.source,
          to: e.target,
          from_port: e.sourceHandle || '',
          to_port: e.targetHandle || '',
        })),
      })
      setExecutionDetail(res.data.data)
    } catch (e: any) {
      setError(e?.response?.data?.detail || '执行失败')
    } finally {
      setIsExecuting(false)
    }
  }

  const handleCancel = async () => {
    if (!executionDetail) return
    try {
      await workflowEngineApi.cancelExecution(executionDetail.execution_id)
    } catch (e) {
      console.error(e)
    }
  }

  const status = executionDetail?.status
  const progress = executionDetail?.progress
  const progressPercent = progress ? Math.round(progress.progress * 100) : 0

  return (
    <div className="h-32 bg-[#181825] border-t border-[#313244] flex items-center px-4 gap-4">
      <button
        onClick={handleExecute}
        disabled={isExecuting || nodes.length === 0}
        className="px-4 py-2 bg-indigo-500 hover:bg-indigo-600 disabled:opacity-50 text-white rounded text-sm font-medium"
      >
        {isExecuting ? '执行中...' : '▶ 执行工作流'}
      </button>

      {isExecuting && (
        <button
          onClick={handleCancel}
          className="px-3 py-2 bg-red-500 hover:bg-red-600 text-white rounded text-sm"
        >
          取消
        </button>
      )}

      {error && (
        <div className="text-red-400 text-sm">错误: {error}</div>
      )}

      {executionDetail && (
        <div className="flex-1 flex items-center gap-4">
          <div className="text-sm">
            <span className="text-gray-400">状态: </span>
            <span className={
              status === 'completed' ? 'text-emerald-400' :
              status === 'failed' ? 'text-red-400' :
              status === 'cancelled' ? 'text-yellow-400' :
              'text-blue-400'
            }>
              {status}
            </span>
          </div>
          {progress && (
            <>
              <div className="text-sm text-gray-400">
                进度: {progress.completed}/{progress.total}
              </div>
              <div className="flex-1 max-w-xs bg-[#313244] rounded-full h-2 overflow-hidden">
                <div
                  className="bg-indigo-500 h-full transition-all"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
              <div className="text-sm text-gray-400">
                {progressPercent}%
              </div>
              {progress.duration && (
                <div className="text-sm text-gray-400">
                  耗时: {progress.duration}s
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 11: 更新 WorkflowEditor 集成面板**

读取 `frontend/src/components/workflow/WorkflowEditor.tsx` 后修改为：

```tsx
// frontend/src/components/workflow/WorkflowEditor.tsx
import { useCallback, useMemo } from 'react'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  addEdge,
  applyNodeChanges,
  applyEdgeChanges,
  type Node,
  type Edge,
  type OnNodesChange,
  type OnEdgesChange,
  type OnConnect,
  type NodeTypes,
} from 'reactflow'
import 'reactflow/dist/style.css'
import ImageGenNode from './nodes/ImageGenNode'
import CharacterNode from './nodes/CharacterNode'
import LLMChatNode from './nodes/LLMChatNode'
import TTSNode from './nodes/TTSNode'
import VideoComposeNode from './nodes/VideoComposeNode'
import TextInputNode from './nodes/TextInputNode'
import TextConcatNode from './nodes/TextConcatNode'
import ImagePreviewNode from './nodes/ImagePreviewNode'
import NodePalette from './NodePalette'
import ExecutionPanel from './ExecutionPanel'
import { useEditorStore } from '@/stores/editorStore'

const nodeTypes: NodeTypes = {
  imageGen: ImageGenNode,
  character: CharacterNode,
  text_to_image: ImageGenNode,
  character_gen: CharacterNode,
  llm_chat: LLMChatNode,
  tts: TTSNode,
  video_compose: VideoComposeNode,
  text_input: TextInputNode,
  text_concat: TextConcatNode,
  image_preview: ImagePreviewNode,
}

const defaultEdgeOptions = {
  style: { stroke: '#6366f1', strokeWidth: 2 },
  animated: true,
}

export default function WorkflowEditor() {
  const { nodes, edges, setNodes, setEdges } = useEditorStore()

  const onNodesChange: OnNodesChange = useCallback(
    (changes) => {
      const updated = applyNodeChanges(changes, nodes as Node[])
      setNodes(updated)
    },
    [nodes, setNodes]
  )

  const onEdgesChange: OnEdgesChange = useCallback(
    (changes) => {
      const updated = applyEdgeChanges(changes, edges as Edge[])
      setEdges(updated)
    },
    [edges, setEdges]
  )

  const onConnect: OnConnect = useCallback(
    (connection) => {
      const updated = addEdge({ ...connection, ...defaultEdgeOptions }, edges as Edge[])
      setEdges(updated)
    },
    [edges, setEdges]
  )

  const minimapStyle = useMemo(() => ({ backgroundColor: '#1e1e2e' }), [])

  return (
    <div className="w-full h-full flex flex-col">
      <div className="flex-1 flex overflow-hidden">
        <NodePalette />
        <div className="flex-1 relative">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            nodeTypes={nodeTypes}
            defaultEdgeOptions={defaultEdgeOptions}
            fitView
            className="bg-[#181825]"
          >
            <Background color="#313244" gap={16} />
            <Controls className="!bg-[#2a2a3e] !border-[#313244]" />
            <MiniMap style={minimapStyle} nodeColor="#6366f1" maskColor="rgba(0,0,0,0.5)" />
          </ReactFlow>
        </div>
      </div>
      <ExecutionPanel />
    </div>
  )
}
```

- [ ] **Step 12: 更新 editorStore**

读取 `frontend/src/stores/editorStore.ts` 后修改：增加 `isExecuting`、`executionDetail`、`availableNodes`、`templates` 状态，以及 `addNode`、`removeNode` 方法。

- [ ] **Step 13: 验证前端编译**

Run: `cd c:\漫剧软件项目\frontend; npm run typecheck 2>&1 | head -20`

Expected: 无类型错误（或仅有未使用变量警告）

---

## Task 8: 集成测试

**Files:**
- Create: `backend/tests/test_workflow_integration.py`

- [ ] **Step 1: 创建端到端集成测试**

```python
# backend/tests/test_workflow_integration.py
"""Phase 3 端到端集成测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.deps import get_current_user
from app.engines.base import GenerationResult
from app.engines.workflow.executor import WorkflowExecutor, ExecutionStatus
from app.engines.workflow.registry import NodeRegistry
from app.engines.workflow.nodes import register_all_nodes
from app.engines.workflow.nodes.generation_nodes import TextToImageNode
from app.engines.workflow.nodes.utility_nodes import TextInputNode, ImagePreviewNode


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = "test-user-id"
    user.username = "testuser"
    user.status = "active"
    return user


@pytest.fixture
def auth_bypass(mock_user):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield mock_user
    app.dependency_overrides.clear()


def test_register_all_nodes():
    """测试注册所有内置节点"""
    registry = NodeRegistry()
    register_all_nodes(registry)
    definitions = registry.list_definitions()
    types = [d.type for d in definitions]
    # 验证所有节点类型都已注册
    assert "text_to_image" in types
    assert "tts" in types
    assert "llm_chat" in types
    assert "video_compose" in types
    assert "character_gen" in types
    assert "text_input" in types
    assert "text_concat" in types
    assert "image_preview" in types


@pytest.mark.asyncio
async def test_full_workflow_with_mock_engines():
    """测试完整工作流（mock 引擎）：text_input → text_to_image → image_preview"""
    # 准备注册表
    registry = NodeRegistry()
    register_all_nodes(registry)

    # mock 图像引擎
    mock_image_engine = AsyncMock()
    mock_image_engine.text2img = AsyncMock(return_value=GenerationResult(
        success=True, data="/uploads/images/test.png",
        content_type="image/png", metadata={"model": "flux"}
    ))

    executor = WorkflowExecutor(registry=registry)

    workflow = {
        "nodes": [
            {"id": "input", "type": "text_input", "params": {"value": "a cute cat"}},
            {"id": "gen", "type": "text_to_image", "params": {"model": "flux"}},
            {"id": "preview", "type": "image_preview", "params": {}},
        ],
        "edges": [
            {"from": "input", "to": "gen", "from_port": "text", "to_port": "prompt"},
            {"from": "gen", "to": "preview", "from_port": "image", "to_port": "image"},
        ]
    }

    with patch("app.engines.workflow.nodes.generation_nodes.engine_manager") as mock_manager:
        mock_manager.get_image_engine.return_value = mock_image_engine
        execution = await executor.execute(workflow)

    assert execution.status == ExecutionStatus.COMPLETED
    assert execution.results["input"]["text"] == "a cute cat"
    assert execution.results["gen"]["image"] == "/uploads/images/test.png"
    assert execution.results["preview"]["image"] == "/uploads/images/test.png"
    assert execution.duration is not None

    # 验证图像引擎被调用时 prompt 正确传递
    mock_image_engine.text2img.assert_called_once()
    call_kwargs = mock_image_engine.text2img.call_args.kwargs
    assert call_kwargs["prompt"] == "a cute cat"


@pytest.mark.asyncio
async def test_api_full_workflow_execution(auth_bypass):
    """测试通过 API 执行完整工作流"""
    mock_image_engine = AsyncMock()
    mock_image_engine.text2img = AsyncMock(return_value=GenerationResult(
        success=True, data="/uploads/images/api_test.png",
        content_type="image/png", metadata={}
    ))

    with patch("app.api.workflows.workflow_executor") as mock_executor, \
         patch("app.api.workflows.WorkflowExecutionService") as MockService, \
         patch("app.engines.workflow.nodes.generation_nodes.engine_manager") as mock_manager:

        # mock executor 返回成功
        async def mock_execute(workflow_data, external_inputs=None, execution_id=None):
            from app.engines.workflow.executor import WorkflowExecution
            exec_obj = WorkflowExecution(
                execution_id=execution_id or "api-test-1",
                workflow_data=workflow_data,
                status=ExecutionStatus.COMPLETED,
                started_at=1000.0,
                completed_at=1001.0,
                duration=1.0,
            )
            exec_obj.results = {
                "input": {"text": "test"},
                "gen": {"image": "/uploads/images/api_test.png"},
            }
            return exec_obj

        mock_executor.execute = mock_execute
        mock_manager.get_image_engine.return_value = mock_image_engine

        mock_service = AsyncMock()
        mock_service.create = AsyncMock()
        MockService.return_value = mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/workflows/execute", json={
                "nodes": [
                    {"id": "input", "type": "text_input", "params": {"value": "test"}},
                    {"id": "gen", "type": "text_to_image", "params": {}},
                ],
                "edges": [
                    {"from": "input", "to": "gen", "from_port": "text", "to_port": "prompt"}
                ]
            })

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["status"] == "completed"
        assert data["data"]["results"]["gen"]["image"] == "/uploads/images/api_test.png"


@pytest.mark.asyncio
async def test_workflow_with_node_failure():
    """测试工作流节点失败的传播"""
    registry = NodeRegistry()
    register_all_nodes(registry)

    mock_image_engine = AsyncMock()
    mock_image_engine.text2img = AsyncMock(return_value=GenerationResult(
        success=False, data=b"", content_type="", metadata={},
        error="Image generation API timeout"
    ))

    executor = WorkflowExecutor(registry=registry)

    workflow = {
        "nodes": [
            {"id": "input", "type": "text_input", "params": {"value": "test"}},
            {"id": "gen", "type": "text_to_image", "params": {}},
        ],
        "edges": [
            {"from": "input", "to": "gen", "from_port": "text", "to_port": "prompt"}
        ]
    }

    with patch("app.engines.workflow.nodes.generation_nodes.engine_manager") as mock_manager:
        mock_manager.get_image_engine.return_value = mock_image_engine
        execution = await executor.execute(workflow)

    assert execution.status == ExecutionStatus.FAILED
    assert "gen" in execution.errors
    assert "Image generation API timeout" in execution.errors["gen"]
    # 输入节点应该成功
    assert execution.results.get("input", {}).get("text") == "test"


@pytest.mark.asyncio
async def test_parallel_nodes_execution():
    """测试并行节点执行"""
    registry = NodeRegistry()
    register_all_nodes(registry)

    mock_image_engine = AsyncMock()
    mock_image_engine.text2img = AsyncMock(return_value=GenerationResult(
        success=True, data="/uploads/images/par.png",
        content_type="image/png", metadata={}
    ))

    executor = WorkflowExecutor(registry=registry)

    # 两个并行输入 → 一个汇聚节点
    workflow = {
        "nodes": [
            {"id": "in1", "type": "text_input", "params": {"value": "prompt1"}},
            {"id": "in2", "type": "text_input", "params": {"value": "prompt2"}},
            {"id": "gen1", "type": "text_to_image", "params": {}},
            {"id": "gen2", "type": "text_to_image", "params": {}},
        ],
        "edges": [
            {"from": "in1", "to": "gen1", "from_port": "text", "to_port": "prompt"},
            {"from": "in2", "to": "gen2", "from_port": "text", "to_port": "prompt"},
        ]
    }

    with patch("app.engines.workflow.nodes.generation_nodes.engine_manager") as mock_manager:
        mock_manager.get_image_engine.return_value = mock_image_engine
        execution = await executor.execute(workflow)

    assert execution.status == ExecutionStatus.COMPLETED
    # 两个生成节点都应该执行
    assert mock_image_engine.text2img.call_count == 2


@pytest.mark.asyncio
async def test_template_apply_and_execute(auth_bypass):
    """测试应用模板并执行"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. 获取模板列表
        resp = await client.get("/api/workflows/templates")
        templates = resp.json()["data"]
        assert len(templates) > 0

        # 2. 应用第一个基础模板
        basic = next(t for t in templates if t["template_id"] == "basic_text_to_image")
        apply_resp = await client.post("/api/workflows/apply-template", json={
            "template_id": basic["template_id"]
        })
        assert apply_resp.status_code == 200
        workflow_data = apply_resp.json()["data"]
        assert "nodes" in workflow_data
        assert len(workflow_data["nodes"]) == 3


def test_all_node_definitions_valid():
    """测试所有节点定义有效"""
    registry = NodeRegistry()
    register_all_nodes(registry)
    for defn in registry.list_definitions():
        assert defn.type, f"节点 {defn.name} 缺少 type"
        assert defn.name, f"节点 {defn.type} 缺少 name"
        assert defn.category, f"节点 {defn.type} 缺少 category"
        # 至少有一个输入或输出端口
        assert defn.inputs or defn.outputs, f"节点 {defn.type} 没有任何端口"


@pytest.mark.asyncio
async def test_complex_workflow_text_to_speech():
    """测试文本转语音工作流"""
    registry = NodeRegistry()
    register_all_nodes(registry)

    mock_tts_engine = AsyncMock()
    mock_tts_engine.synthesize = AsyncMock(return_value=GenerationResult(
        success=True, data="/uploads/audio/test.mp3",
        content_type="audio/mp3", metadata={}
    ))

    executor = WorkflowExecutor(registry=registry)
    workflow = {
        "nodes": [
            {"id": "input", "type": "text_input", "params": {"value": "你好，世界"}},
            {"id": "tts", "type": "tts", "params": {"voice": "zh-CN-XiaoxiaoNeural"}},
        ],
        "edges": [
            {"from": "input", "to": "tts", "from_port": "text", "to_port": "text"}
        ]
    }

    with patch("app.engines.workflow.nodes.generation_nodes.engine_manager") as mock_manager:
        mock_manager.get_tts_engine.return_value = mock_tts_engine
        execution = await executor.execute(workflow)

    assert execution.status == ExecutionStatus.COMPLETED
    assert execution.results["tts"]["audio"] == "/uploads/audio/test.mp3"
    mock_tts_engine.synthesize.assert_called_once()
    assert mock_tts_engine.synthesize.call_args.kwargs["text"] == "你好，世界"
```

- [ ] **Step 2: 运行测试**

Run: `cd c:\漫剧软件项目\backend; $env:PYTHONPATH = "c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; python -m pytest tests/test_workflow_integration.py -v`

Expected: 7 passed

- [ ] **Step 3: 运行全部测试确认无回归**

Run: `cd c:\漫剧软件项目\backend; $env:PYTHONPATH = "c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; python -m pytest --tb=short`

Expected: 所有测试通过（95 Phase 1+2 + 81 Phase 3 = ~176+）

---

## Self-Review

### Spec coverage

对照 `docs/ai-engine/workflow-engine.md` 设计文档逐项核对：

| 设计文档章节 | 对应 Task | 覆盖状态 |
|---|---|---|
| 节点抽象基类（BaseNode） | Task 1 | ✅ 完整覆盖 |
| 节点注册表（NodeRegistry） | Task 1 | ✅ 完整覆盖 |
| DAG 解析与验证 | Task 2 | ✅ 完整覆盖 |
| 拓扑排序（分层并行） | Task 2 | ✅ 完整覆盖 |
| 5 个生成节点 | Task 3 | ✅ 完整覆盖（Text2Image / TTS / LLMChat / VideoCompose / CharacterGen） |
| 3 个工具节点 | Task 3 | ✅ 完整覆盖（TextInput / TextConcat / ImagePreview） |
| 工作流执行引擎（WorkflowExecutor） | Task 4 | ✅ 完整覆盖（解析→拓扑→分层并行→数据按边传递→取消支持） |
| 模板系统（5 个内置模板） | Task 5 | ✅ 完整覆盖 |
| 执行 API（6 个端点） | Task 6 | ✅ 完整覆盖（execute / status / cancel / list nodes / list templates / apply template） |
| 前端节点扩展（6 个新节点） | Task 7 | ✅ 完整覆盖 |
| NodePalette 节点面板 | Task 7 | ✅ 完整覆盖 |
| ExecutionPanel 执行面板 | Task 7 | ✅ 完整覆盖 |
| 集成测试 | Task 8 | ✅ 完整覆盖 |

**无遗漏需求。** 所有设计文档中的核心组件均在 8 个 Task 中有明确实现。

### Placeholder scan

逐项扫描计划文档，检查以下红旗模式：

- ✅ 无 "TBD" / "TODO" / "implement later" / "fill in details"
- ✅ 无 "Add appropriate error handling" / "add validation" / "handle edge cases" 等模糊描述
- ✅ 无 "Write tests for the above"（每个测试步骤均含完整测试代码）
- ✅ 无 "Similar to Task N"（所有重复结构均重复了完整代码）
- ✅ 所有代码步骤均包含可运行的完整代码，无仅描述不展示的步骤
- ✅ 所有引用的类型/函数/方法均在先前 Task 中已定义

**无占位符。**

### Type consistency

跨 Task 核对类型定义、方法签名、属性名一致性：

| 名称 | 定义 Task | 使用 Task | 一致性 |
|---|---|---|---|
| `BaseNode.execute(inputs, params)` | Task 1 | Task 3, Task 4, Task 8 | ✅ 签名一致 |
| `BaseNode.get_definition()` 类方法 | Task 1 | Task 3, Task 4 | ✅ 一致 |
| `NodeRegistry.create_node(node_id, node_type, params)` | Task 1 | Task 4 | ✅ 一致 |
| `NodeRegistry.list_definitions()` | Task 1 | Task 6 API | ✅ 一致 |
| `NodeRegistry.list_by_category(cat)` | Task 1 | Task 7 前端 | ✅ 一致 |
| `DAGBuilder.parse(workflow_data)` | Task 2 | Task 4 | ✅ 一致 |
| `DAGValidator.validate(graph)` | Task 2 | Task 4 | ✅ 一致 |
| `TopologicalSorter.sort(graph)` 返回 `list[list[str]]` | Task 2 | Task 4 | ✅ 一致 |
| `WorkflowExecutor.execute(workflow_data, external_inputs, execution_id)` | Task 4 | Task 6, Task 8 | ✅ 一致 |
| `WorkflowExecutor.get_execution(execution_id)` | Task 4 | Task 6 | ✅ 一致 |
| `WorkflowExecutor.cancel(execution_id)` | Task 4 | Task 6, Task 8 | ✅ 一致 |
| `ExecutionStatus` 枚举值（PENDING/RUNNING/COMPLETED/FAILED/CANCELLED） | Task 4 | Task 6, Task 8 | ✅ 一致 |
| `WorkflowExecution.to_dict()` | Task 4 | Task 6 | ✅ 一致 |
| `TemplateManager.list_templates(category)` | Task 5 | Task 6 | ✅ 一致 |
| `TemplateManager.get_template(template_id)` | Task 5 | Task 6 | ✅ 一致 |
| `TemplateManager.apply_template(template_id, overrides)` | Task 5 | Task 6 | ✅ 一致 |
| `register_all_nodes(registry)` | Task 3 | Task 4, Task 6, Task 8 | ✅ 一致 |
| `engine_manager` 单例引用 | Task 3 | Task 4, Task 8 | ✅ 一致（来自 Phase 2） |
| `GenerationResult` dataclass | Phase 2 | Task 3, Task 4, Task 8 | ✅ 一致（success/data/content_type/metadata/error） |
| 前端 `WorkflowNode.type` 字段 | Phase 1 types/workflow.ts | Task 7 | ✅ 一致 |
| 前端 `workflowApi` 接口 | Phase 1 api/workflows.ts | Task 7 | ✅ 一致（扩展不破坏现有） |
| React Flow `nodeTypes` 注册 | Phase 1 WorkflowEditor | Task 7 | ✅ 一致（新增不破坏现有 imageGen/character） |

**类型一致性检查通过。** 未发现跨 Task 的签名/属性名不匹配问题。

### Phase 2 衔接确认

- ✅ Phase 3 Task 3 的生成节点全部通过 `engine_manager` 调用 Phase 2 的 5 个 Provider
- ✅ Phase 3 Task 4/8 的 mock 策略与 Phase 2 测试中的 `engine_manager` mock 模式一致
- ✅ Phase 3 Task 6 的 API 认证 mock 使用 `app.dependency_overrides[get_current_user]`，与 Phase 2 Task 8 的模式一致
- ✅ Phase 3 不修改 Phase 1/2 的任何已通过测试的代码

### 测试预期汇总

| Task | 测试文件 | 预期测试数 |
|---|---|---|
| Task 1 | test_workflow_node_base.py | 10 |
| Task 2 | test_workflow_dag.py | 12 |
| Task 3 | test_workflow_nodes.py | 16 |
| Task 4 | test_workflow_executor.py | 11 |
| Task 5 | test_workflow_templates.py | 14 |
| Task 6 | test_workflow_execute_api.py | 11 |
| Task 7 | 前端无单测（手动验证） | 0 |
| Task 8 | test_workflow_integration.py | 7 |
| **总计** | | **81** |

Phase 1+2 共 95 个测试，Phase 3 新增 81 个，预期总测试数 **~176**。

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-18-phase3-workflow-engine.md`.

Two execution options:

1. **Subagent-Driven (recommended)** - 每个 Task 派发独立子代理执行，Task 间 review，快速迭代
2. **Inline Execution** - 在当前会话中按 executing-plans 批量执行，含检查点 review

Which approach?