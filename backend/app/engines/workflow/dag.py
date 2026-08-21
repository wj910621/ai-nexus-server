# backend/app/engines/workflow/dag.py
"""DAG 解析、拓扑排序、循环检测"""
from dataclasses import dataclass, field


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
