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
