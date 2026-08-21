# 工作流引擎

> 本文档详细说明节点式工作流编排引擎的设计，支持类似ComfyUI的可视化创作。

---

## 一、引擎概述

### 1.1 功能定位
工作流引擎是连接用户创意与AI执行的桥梁，提供类似ComfyUI的节点式可视化编程能力，让专业用户可以自由编排创作流程。同时支持模板化工作流，降低新手使用门槛。

### 1.2 核心能力
| 能力 | 描述 |
|------|------|
| 节点编排 | 拖拽式节点编辑，定义数据流向 |
| DAG调度 | 有向无环图依赖解析与任务调度 |
| 节点扩展 | 支持自定义节点，插件化扩展 |
| 模板系统 | 预设工作流模板，一键应用 |
| 实时预览 | 节点输出实时预览 |
| 版本管理 | 工作流版本控制与对比 |

---

## 二、节点系统设计

### 2.1 节点基类

```python
# backend/app/engines/workflow/node_base.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from enum import Enum

class NodeCategory(str, Enum):
    """节点分类"""
    INPUT = "input"           # 输入节点
    GENERATION = "generation" # 生成节点
    PROCESSING = "processing" # 处理节点
    COMPOSITE = "composite"   # 合成节点
    OUTPUT = "output"         # 输出节点
    UTILITY = "utility"       # 工具节点

class PortDefinition(BaseModel):
    """端口定义"""
    name: str
    type: str  # image/text/audio/video/any
    required: bool = True
    default: Any = None

class NodeDefinition(BaseModel):
    """节点定义"""
    type: str                        # 节点类型标识
    name: str                        # 显示名称
    category: NodeCategory           # 分类
    description: str = ""            # 描述
    icon: str = ""                   # 图标
    
    # 输入输出端口
    inputs: List[PortDefinition] = []
    outputs: List[PortDefinition] = []
    
    # 参数
    parameters: List[Dict] = []      # 可配置参数
    
    # 执行信息
    is_async: bool = True
    estimated_time: float = 1.0      # 预计执行时间（秒）

class BaseNode(ABC):
    """节点基类"""
    
    def __init__(self, node_id: str, params: dict = None):
        self.id = node_id
        self.params = params or {}
        self.status = 'idle'  # idle/running/completed/failed
        self.result = None
        self.error = None
    
    @abstractmethod
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行节点逻辑
        
        Args:
            inputs: 输入数据 {port_name: value}
        
        Returns:
            输出数据 {port_name: value}
        """
        pass
    
    @classmethod
    @abstractmethod
    def get_definition(cls) -> NodeDefinition:
        """获取节点定义"""
        pass
    
    def get_info(self) -> dict:
        """获取节点运行信息"""
        return {
            'id': self.id,
            'status': self.status,
            'has_result': self.result is not None,
            'error': self.error
        }
```

### 2.2 内置节点实现

```python
# backend/app/engines/workflow/nodes/generation_nodes.py
from typing import Any, Dict
from .node_base import BaseNode, NodeDefinition, NodeCategory, PortDefinition

class TextToImageNode(BaseNode):
    """文生图节点"""
    
    @classmethod
    def get_definition(cls) -> NodeDefinition:
        return NodeDefinition(
            type="text_to_image",
            name="文生图",
            category=NodeCategory.GENERATION,
            description="文本提示词生成图像",
            icon="image",
            inputs=[
                PortDefinition(name="prompt", type="text", required=True),
                PortDefinition(name="negative_prompt", type="text", required=False),
            ],
            outputs=[
                PortDefinition(name="image", type="image")
            ],
            parameters=[
                {"name": "width", "type": "int", "default": 1024, "min": 512, "max": 2048},
                {"name": "height", "type": "int", "default": 1024, "min": 512, "max": 2048},
                {"name": "steps", "type": "int", "default": 30, "min": 10, "max": 100},
                {"name": "guidance_scale", "type": "float", "default": 7.5, "min": 1, "max": 20},
                {"name": "seed", "type": "int", "default": -1},
                {"name": "model", "type": "select", "default": "sdxl", 
                 "options": ["sd15", "sdxl", "sdxl_lightning"]},
            ],
            is_async=True,
            estimated_time=5.0
        )
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        from app.engines.image_gen_engine import ImageGenEngine
        
        engine = ImageGenEngine()
        await engine.load_model(self.params.get('model', 'sdxl'))
        
        seed = self.params.get('seed', -1)
        if seed == -1:
            import random
            seed = random.randint(0, 2**32)
        
        image = await engine.generate(
            prompt=inputs.get('prompt', ''),
            negative_prompt=inputs.get('negative_prompt', ''),
            width=self.params.get('width', 1024),
            height=self.params.get('height', 1024),
            num_inference_steps=self.params.get('steps', 30),
            guidance_scale=self.params.get('guidance_scale', 7.5),
            seed=seed if seed > 0 else None
        )
        
        return {'image': image}

class CharacterGenNode(BaseNode):
    """角色生成节点"""
    
    @classmethod
    def get_definition(cls) -> NodeDefinition:
        return NodeDefinition(
            type="character_gen",
            name="角色生成",
            category=NodeCategory.GENERATION,
            description="生成保持一致性的角色图像",
            inputs=[
                PortDefinition(name="character_id", type="text", required=True),
                PortDefinition(name="scene_prompt", type="text", required=True),
                PortDefinition(name="reference_image", type="image", required=False),
            ],
            outputs=[
                PortDefinition(name="image", type="image")
            ],
            parameters=[
                {"name": "consistency_weight", "type": "float", "default": 0.8, "min": 0, "max": 1},
                {"name": "use_lora", "type": "bool", "default": True},
                {"name": "use_ip_adapter", "type": "bool", "default": True},
            ]
        )
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        from app.engines.character_consistency_engine import CharacterConsistencyEngine
        from app.engines.image_gen_engine import ImageGenEngine
        from app.services.character_service import CharacterService
        
        # 获取角色信息
        db = get_db()
        char_service = CharacterService(db)
        character = await char_service.get_character(inputs['character_id'])
        
        # 生成一致角色
        engine = ImageGenEngine()
        consistency_engine = CharacterConsistencyEngine(engine)
        await consistency_engine.initialize()
        
        image = await consistency_engine.generate_consistent(
            character={
                'id': str(character.id),
                'reference_image': character.main_image_url,
                'lora_path': character.lora_model_path,
                'description': character.description
            },
            prompt=inputs['scene_prompt'],
            consistency_weight=self.params.get('consistency_weight', 0.8)
        )
        
        return {'image': image}

class ImageToImageNode(BaseNode):
    """图生图节点"""
    
    @classmethod
    def get_definition(cls) -> NodeDefinition:
        return NodeDefinition(
            type="img2img",
            name="图生图",
            category=NodeCategory.GENERATION,
            inputs=[
                PortDefinition(name="image", type="image", required=True),
                PortDefinition(name="prompt", type="text", required=True),
            ],
            outputs=[PortDefinition(name="image", type="image")],
            parameters=[
                {"name": "strength", "type": "float", "default": 0.6, "min": 0, "max": 1},
                {"name": "steps", "type": "int", "default": 30},
            ]
        )
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        from app.engines.image_gen_engine import ImageGenEngine
        
        engine = ImageGenEngine()
        image = await engine.img2img(
            init_image=inputs['image'],
            prompt=inputs['prompt'],
            strength=self.params.get('strength', 0.6)
        )
        return {'image': image}

class TextConcatNode(BaseNode):
    """文本拼接节点"""
    
    @classmethod
    def get_definition(cls) -> NodeDefinition:
        return NodeDefinition(
            type="text_concat",
            name="文本拼接",
            category=NodeCategory.UTILITY,
            inputs=[
                PortDefinition(name="text1", type="text", required=False),
                PortDefinition(name="text2", type="text", required=False),
                PortDefinition(name="text3", type="text", required=False),
            ],
            outputs=[PortDefinition(name="text", type="text")],
            parameters=[
                {"name": "separator", "type": "text", "default": ", "},
            ],
            is_async=False,
            estimated_time=0.01
        )
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        texts = [v for v in inputs.values() if v]
        separator = self.params.get('separator', ', ')
        return {'text': separator.join(texts)}

class ImagePreviewNode(BaseNode):
    """图像预览节点"""
    
    @classmethod
    def get_definition(cls) -> NodeDefinition:
        return NodeDefinition(
            type="image_preview",
            name="图像预览",
            category=NodeCategory.OUTPUT,
            inputs=[PortDefinition(name="image", type="image", required=True)],
            outputs=[],
            is_async=False,
            estimated_time=0.1
        )
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        # 保存预览图，返回URL
        image_url = await upload_to_storage(inputs['image'])
        return {'preview_url': image_url}

class VideoOutputNode(BaseNode):
    """视频输出节点"""
    
    @classmethod
    def get_definition(cls) -> NodeDefinition:
        return NodeDefinition(
            type="video_output",
            name="视频输出",
            category=NodeCategory.OUTPUT,
            inputs=[
                PortDefinition(name="frames", type="image_array", required=True),
                PortDefinition(name="audio", type="audio", required=False),
            ],
            outputs=[PortDefinition(name="video", type="video")],
            parameters=[
                {"name": "fps", "type": "int", "default": 24},
                {"name": "format", "type": "select", "default": "mp4", 
                 "options": ["mp4", "webm", "gif"]},
                {"name": "resolution", "type": "select", "default": "1080p",
                 "options": ["720p", "1080p", "4k"]},
            ]
        )
    
    async def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        from app.engines.video_engine import VideoComposer
        
        composer = VideoComposer()
        # 合成视频
        video_url = await composer.compose_from_frames(
            frames=inputs['frames'],
            audio=inputs.get('audio'),
            fps=self.params.get('fps', 24),
            format=self.params.get('format', 'mp4')
        )
        return {'video': video_url}
```

---

## 三、工作流执行引擎

```python
# backend/app/engines/workflow/workflow_engine.py
from typing import Dict, List, Any, Optional
from collections import defaultdict, deque
import asyncio
from datetime import datetime

class WorkflowEngine:
    """
    工作流执行引擎
    
    功能：
    - DAG解析与拓扑排序
    - 节点并行执行
    - 数据传递与类型检查
    - 执行状态追踪
    - 错误处理与重试
    """
    
    def __init__(self):
        self.node_registry: Dict[str, type] = {}  # 节点类型注册
        self.executions: Dict[str, WorkflowExecution] = {}  # 执行记录
    
    def register_node(self, node_type: str, node_class: type):
        """注册节点类型"""
        self.node_registry[node_type] = node_class
    
    async def execute_workflow(
        self,
        workflow_data: dict,
        inputs: Optional[dict] = None
    ) -> dict:
        """
        执行工作流
        
        Args:
            workflow_data: 工作流定义
                {
                    "nodes": [
                        {"id": "1", "type": "text_to_image", "params": {...}}
                    ],
                    "edges": [
                        {"from": "1", "to": "2", "from_port": "image", "to_port": "image"}
                    ]
                }
            inputs: 外部输入
        
        Returns:
            执行结果 {node_id: output_data}
        """
        # 1. 解析工作流
        graph = self._parse_workflow(workflow_data)
        
        # 2. 拓扑排序
        execution_order = self._topological_sort(graph)
        
        # 3. 创建执行记录
        execution = WorkflowExecution(
            workflow_data=workflow_data,
            started_at=datetime.utcnow()
        )
        
        # 4. 逐层执行（同层并行）
        for layer in execution_order:
            layer_tasks = []
            for node_id in layer:
                task = self._execute_node(
                    graph, node_id, execution, inputs
                )
                layer_tasks.append(task)
            
            await asyncio.gather(*layer_tasks)
        
        execution.completed_at = datetime.utcnow()
        execution.status = 'completed'
        
        return execution.results
    
    def _parse_workflow(self, workflow_data: dict) -> 'WorkflowGraph':
        """解析工作流数据为图结构"""
        nodes = {}
        edges = defaultdict(list)  # 邻接表
        
        for node_data in workflow_data['nodes']:
            node_id = node_data['id']
            node_type = node_data['type']
            params = node_data.get('params', {})
            
            # 实例化节点
            node_class = self.node_registry.get(node_type)
            if not node_class:
                raise ValueError(f"未注册的节点类型: {node_type}")
            
            node = node_class(node_id, params)
            nodes[node_id] = node
        
        for edge in workflow_data['edges']:
            edges[edge['from']].append({
                'to': edge['to'],
                'from_port': edge['from_port'],
                'to_port': edge['to_port']
            })
        
        return WorkflowGraph(nodes=nodes, edges=edges)
    
    def _topological_sort(self, graph: 'WorkflowGraph') -> List[List[str]]:
        """
        拓扑排序，返回执行层级
        
        同一层的节点可以并行执行
        """
        # 计算入度
        in_degree = {node_id: 0 for node_id in graph.nodes}
        for from_id, edges in graph.edges.items():
            for edge in edges:
                in_degree[edge['to']] += 1
        
        # BFS分层
        layers = []
        current_layer = [nid for nid, deg in in_degree.items() if deg == 0]
        
        while current_layer:
            layers.append(current_layer)
            next_layer = []
            
            for node_id in current_layer:
                for edge in graph.edges.get(node_id, []):
                    in_degree[edge['to']] -= 1
                    if in_degree[edge['to']] == 0:
                        next_layer.append(edge['to'])
            
            current_layer = next_layer
        
        # 检查是否有环
        total_scheduled = sum(len(layer) for layer in layers)
        if total_scheduled != len(graph.nodes):
            raise ValueError("工作流中存在循环依赖")
        
        return layers
    
    async def _execute_node(
        self,
        graph: 'WorkflowGraph',
        node_id: str,
        execution: 'WorkflowExecution',
        external_inputs: Optional[dict]
    ) -> None:
        """执行单个节点"""
        node = graph.nodes[node_id]
        node.status = 'running'
        
        try:
            # 收集输入数据
            inputs = {}
            
            # 从上游节点获取数据
            for from_id, edges in graph.edges.items():
                for edge in edges:
                    if edge['to'] == node_id:
                        upstream_result = execution.results.get(from_id, {})
                        inputs[edge['to_port']] = upstream_result.get(edge['from_port'])
            
            # 合并外部输入
            if external_inputs and node_id in external_inputs:
                inputs.update(external_inputs[node_id])
            
            # 执行节点
            result = await node.execute(inputs)
            
            # 保存结果
            execution.results[node_id] = result
            node.status = 'completed'
            node.result = result
            
        except Exception as e:
            node.status = 'failed'
            node.error = str(e)
            execution.errors[node_id] = str(e)
            raise

class WorkflowGraph:
    """工作流图"""
    def __init__(self, nodes: dict, edges: dict):
        self.nodes = nodes
        self.edges = edges

class WorkflowExecution:
    """工作流执行记录"""
    def __init__(self, workflow_data: dict, started_at: datetime):
        self.workflow_data = workflow_data
        self.started_at = started_at
        self.completed_at: Optional[datetime] = None
        self.status: str = 'running'
        self.results: Dict[str, dict] = {}
        self.errors: Dict[str, str] = {}
    
    def get_progress(self) -> dict:
        total = len(self.workflow_data['nodes'])
        completed = len(self.results)
        return {
            'total': total,
            'completed': completed,
            'progress': completed / total if total > 0 else 0,
            'status': self.status
        }
```

---

## 四、工作流模板系统

```python
# backend/app/engines/workflow/template_manager.py
from typing import List, Dict, Optional
import json
from pathlib import Path

class WorkflowTemplate:
    """工作流模板"""
    
    def __init__(
        self,
        template_id: str,
        name: str,
        description: str,
        workflow_data: dict,
        category: str = "general",
        is_premium: bool = False
    ):
        self.id = template_id
        self.name = name
        self.description = description
        self.workflow_data = workflow_data
        self.category = category
        self.is_premium = is_premium

class TemplateManager:
    """模板管理器"""
    
    # 内置模板
    BUILTIN_TEMPLATES = [
        WorkflowTemplate(
            template_id="basic_comic",
            name="基础漫剧",
            description="简单的漫剧生成流程：剧本→分镜→画面→合成",
            category="basic",
            workflow_data={
                "nodes": [
                    {"id": "script", "type": "script_input", "params": {}},
                    {"id": "storyboard", "type": "auto_storyboard", "params": {}},
                    {"id": "image_gen", "type": "batch_image_gen", "params": {"model": "sdxl"}},
                    {"id": "tts", "type": "batch_tts", "params": {"engine": "edge_tts"}},
                    {"id": "compose", "type": "video_compose", "params": {"fps": 24}},
                    {"id": "output", "type": "video_output", "params": {"format": "mp4"}}
                ],
                "edges": [
                    {"from": "script", "to": "storyboard", "from_port": "script", "to_port": "script"},
                    {"from": "storyboard", "to": "image_gen", "from_port": "frames", "to_port": "frames"},
                    {"from": "storyboard", "to": "tts", "from_port": "dialogues", "to_port": "dialogues"},
                    {"from": "image_gen", "to": "compose", "from_port": "images", "to_port": "frames"},
                    {"from": "tts", "to": "compose", "from_port": "audios", "to_port": "audio"},
                    {"from": "compose", "to": "output", "from_port": "video", "to_port": "video"}
                ]
            }
        ),
        WorkflowTemplate(
            template_id="consistent_character",
            name="角色一致性漫剧",
            description="使用LoRA+IP-Adapter保持角色一致性",
            category="advanced",
            is_premium=True,
            workflow_data={
                # 高级工作流定义...
            }
        ),
    ]
    
    def __init__(self):
        self.templates: Dict[str, WorkflowTemplate] = {
            t.id: t for t in self.BUILTIN_TEMPLATES
        }
    
    def list_templates(
        self,
        category: Optional[str] = None,
        include_premium: bool = True
    ) -> List[WorkflowTemplate]:
        """列出模板"""
        templates = list(self.templates.values())
        
        if category:
            templates = [t for t in templates if t.category == category]
        
        if not include_premium:
            templates = [t for t in templates if not t.is_premium]
        
        return templates
    
    def get_template(self, template_id: str) -> Optional[WorkflowTemplate]:
        """获取模板"""
        return self.templates.get(template_id)
    
    def apply_template(
        self,
        template_id: str,
        customizations: Optional[dict] = None
    ) -> dict:
        """
        应用模板，返回定制化后的工作流
        
        Args:
            template_id: 模板ID
            customizations: 定制参数
                {
                    "node_params": {
                        "image_gen": {"model": "sdxl_lightning"}
                    }
                }
        """
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"模板不存在: {template_id}")
        
        workflow = json.loads(json.dumps(template.workflow_data))  # 深拷贝
        
        # 应用定制
        if customizations and 'node_params' in customizations:
            for node in workflow['nodes']:
                node_id = node['id']
                if node_id in customizations['node_params']:
                    node['params'].update(customizations['node_params'][node_id])
        
        return workflow
```

---

## 五、前端节点编辑器

```typescript
// frontend/src/features/workflow/WorkflowEditor.tsx
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  Node,
  Edge,
  Connection,
  addEdge,
  useNodesState,
  useEdgesState,
} from 'reactflow';
import 'reactflow/dist/style.css';

const nodeTypes = {
  text_to_image: TextToImageNode,
  character_gen: CharacterGenNode,
  img2img: ImageToImageNode,
  text_concat: TextConcatNode,
  image_preview: ImagePreviewNode,
  video_output: VideoOutputNode,
};

export function WorkflowEditor() {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  
  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );
  
  const onExecute = async () => {
    const workflow = {
      nodes: nodes.map(n => ({
        id: n.id,
        type: n.type,
        params: n.data.params || {}
      })),
      edges: edges.map(e => ({
        from: e.source,
        to: e.target,
        from_port: e.sourceHandle,
        to_port: e.targetHandle
      }))
    };
    
    await workflowApi.execute(workflow);
  };
  
  return (
    <div className="workflow-editor h-screen">
      <div className="toolbar">
        <button onClick={onExecute}>执行工作流</button>
      </div>
      
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        fitView
      >
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
      
      <NodePalette />  {/* 节点面板 */}
    </div>
  );
}
```

---

## 六、API接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/v1/workflows/execute | 执行工作流 |
| GET | /api/v1/workflows/executions/{id} | 获取执行状态 |
| GET | /api/v1/workflows/templates | 获取模板列表 |
| POST | /api/v1/workflows/apply-template | 应用模板 |
| GET | /api/v1/workflows/nodes | 获取可用节点列表 |
| POST | /api/v1/workflows/save | 保存工作流 |
| GET | /api/v1/workflows/{id} | 获取工作流详情 |

---

*本文档最后更新：2026-07-18*
