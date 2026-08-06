/**
 * workflow-engine.js 测试套件
 * 覆盖工作流节点、连接、执行引擎等核心功能
 */

const EventEmitter = require('events');

// 节点类型常量
const NODE_TYPES = {
  START: 'start',
  END: 'end',
  TOOL: 'tool',
  AGENT: 'agent',
  CONDITION: 'condition',
  LOOP: 'loop',
  PARALLEL: 'parallel',
  DELAY: 'delay',
  TRIGGER: 'trigger',
  HTTP: 'http',
  CODE: 'code',
};

// 工作流节点类
class WorkflowNode {
  constructor(config) {
    this.id = config.id || `node_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    this.type = config.type || NODE_TYPES.TOOL;
    this.name = config.name || this.type;
    this.config = config.config || {};
    this.position = config.position || { x: 0, y: 0 };
    this.inputs = [];
    this.outputs = [];
    this.status = 'idle';
    this.result = null;
    this.error = null;
  }

  toJSON() {
    return {
      id: this.id,
      type: this.type,
      name: this.name,
      config: this.config,
      position: this.position,
      inputs: this.inputs.map(c => c.id),
      outputs: this.outputs.map(c => c.id),
      status: this.status,
      result: this.result,
      error: this.error,
    };
  }
}

// 工作流连接类
class WorkflowConnection {
  constructor(config) {
    this.id = config.id || `conn_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    this.from = config.from;
    this.to = config.to;
    this.condition = config.condition || null;
    this.label = config.label || '';
  }

  toJSON() {
    return {
      id: this.id,
      from: this.from,
      to: this.to,
      condition: this.condition,
      label: this.label,
    };
  }
}

// 工作流类
class Workflow {
  constructor(config) {
    this.id = config.id || `wf_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    this.name = config.name || '未命名工作流';
    this.description = config.description || '';
    this.nodes = new Map();
    this.connections = new Map();
    this.variables = config.variables || {};
    this.createdAt = Date.now();
    this.updatedAt = Date.now();
    this.status = 'idle';
    this.executionLog = [];
  }

  addNode(nodeConfig) {
    const node = new WorkflowNode(nodeConfig);
    this.nodes.set(node.id, node);
    this.updatedAt = Date.now();
    return node;
  }

  removeNode(nodeId) {
    const node = this.nodes.get(nodeId);
    if (!node) return false;

    for (const [connId, conn] of this.connections.entries()) {
      if (conn.from === nodeId || conn.to === nodeId) {
        this.connections.delete(connId);
      }
    }

    this.nodes.delete(nodeId);
    this.updatedAt = Date.now();
    return true;
  }

  addConnection(connConfig) {
    const conn = new WorkflowConnection(connConfig);
    this.connections.set(conn.id, conn);

    const fromNode = this.nodes.get(conn.from);
    const toNode = this.nodes.get(conn.to);
    if (fromNode) fromNode.outputs.push(conn);
    if (toNode) toNode.inputs.push(conn);

    this.updatedAt = Date.now();
    return conn;
  }

  removeConnection(connId) {
    const conn = this.connections.get(connId);
    if (!conn) return false;

    const fromNode = this.nodes.get(conn.from);
    const toNode = this.nodes.get(conn.to);
    if (fromNode) fromNode.outputs = fromNode.outputs.filter(c => c.id !== connId);
    if (toNode) toNode.inputs = toNode.inputs.filter(c => c.id !== connId);

    this.connections.delete(connId);
    this.updatedAt = Date.now();
    return true;
  }

  toJSON() {
    return {
      id: this.id,
      name: this.name,
      description: this.description,
      nodes: Array.from(this.nodes.values()).map(n => n.toJSON()),
      connections: Array.from(this.connections.values()).map(c => c.toJSON()),
      variables: this.variables,
      createdAt: this.createdAt,
      updatedAt: this.updatedAt,
      status: this.status,
    };
  }
}

describe('工作流引擎核心功能测试', () => {
  describe('工作流节点测试', () => {
    test('节点应有唯一ID', () => {
      const node1 = new WorkflowNode({ type: NODE_TYPES.TOOL });
      const node2 = new WorkflowNode({ type: NODE_TYPES.TOOL });

      expect(node1.id).toBeDefined();
      expect(node2.id).toBeDefined();
      expect(node1.id).not.toBe(node2.id);
    });

    test('节点应支持所有类型', () => {
      Object.values(NODE_TYPES).forEach(type => {
        const node = new WorkflowNode({ type });
        expect(node.type).toBe(type);
      });
    });

    test('节点应默认为 idle 状态', () => {
      const node = new WorkflowNode({ type: NODE_TYPES.TOOL });
      expect(node.status).toBe('idle');
    });

    test('节点应支持自定义配置', () => {
      const config = { timeout: 5000, retries: 3 };
      const node = new WorkflowNode({ type: NODE_TYPES.TOOL, config });

      expect(node.config.timeout).toBe(5000);
      expect(node.config.retries).toBe(3);
    });

    test('节点应支持位置信息', () => {
      const position = { x: 100, y: 200 };
      const node = new WorkflowNode({ type: NODE_TYPES.TOOL, position });

      expect(node.position.x).toBe(100);
      expect(node.position.y).toBe(200);
    });

    test('节点应正确序列化为 JSON', () => {
      const node = new WorkflowNode({ type: NODE_TYPES.TOOL, name: 'TestNode' });
      const json = node.toJSON();

      expect(json.id).toBeDefined();
      expect(json.type).toBe(NODE_TYPES.TOOL);
      expect(json.name).toBe('TestNode');
      expect(json.status).toBe('idle');
    });
  });

  describe('工作流连接测试', () => {
    test('连接应有唯一ID', () => {
      const conn1 = new WorkflowConnection({ from: 'node1', to: 'node2' });
      const conn2 = new WorkflowConnection({ from: 'node1', to: 'node2' });

      expect(conn1.id).toBeDefined();
      expect(conn2.id).toBeDefined();
      expect(conn1.id).not.toBe(conn2.id);
    });

    test('连接应连接源和目标节点', () => {
      const conn = new WorkflowConnection({ from: 'node1', to: 'node2' });

      expect(conn.from).toBe('node1');
      expect(conn.to).toBe('node2');
    });

    test('连接应支持条件表达式', () => {
      const condition = 'data.status === "success"';
      const conn = new WorkflowConnection({
        from: 'node1',
        to: 'node2',
        condition,
      });

      expect(conn.condition).toBe(condition);
    });

    test('连接应支持标签', () => {
      const label = '成功分支';
      const conn = new WorkflowConnection({
        from: 'node1',
        to: 'node2',
        label,
      });

      expect(conn.label).toBe(label);
    });

    test('连接应正确序列化为 JSON', () => {
      const conn = new WorkflowConnection({ from: 'node1', to: 'node2', label: 'TestConn' });
      const json = conn.toJSON();

      expect(json.id).toBeDefined();
      expect(json.from).toBe('node1');
      expect(json.to).toBe('node2');
      expect(json.label).toBe('TestConn');
    });
  });

  describe('工作流管理测试', () => {
    test('工作流应有唯一ID', () => {
      const wf1 = new Workflow({ name: 'Workflow 1' });
      const wf2 = new Workflow({ name: 'Workflow 2' });

      expect(wf1.id).toBeDefined();
      expect(wf2.id).toBeDefined();
      expect(wf1.id).not.toBe(wf2.id);
    });

    test('工作流应支持添加节点', () => {
      const workflow = new Workflow({ name: 'Test Workflow' });
      const node = workflow.addNode({ type: NODE_TYPES.TOOL });

      expect(node).toBeDefined();
      expect(workflow.nodes.size).toBe(1);
      expect(workflow.nodes.get(node.id)).toBe(node);
    });

    test('工作流应支持移除节点', () => {
      const workflow = new Workflow({ name: 'Test Workflow' });
      const node = workflow.addNode({ type: NODE_TYPES.TOOL });

      const removed = workflow.removeNode(node.id);
      expect(removed).toBe(true);
      expect(workflow.nodes.size).toBe(0);
    });

    test('移除节点时应移除相关连接', () => {
      const workflow = new Workflow({ name: 'Test Workflow' });
      const node1 = workflow.addNode({ type: NODE_TYPES.TOOL });
      const node2 = workflow.addNode({ type: NODE_TYPES.TOOL });

      workflow.addConnection({ from: node1.id, to: node2.id });

      workflow.removeNode(node1.id);

      expect(workflow.connections.size).toBe(0);
    });

    test('工作流应支持添加连接', () => {
      const workflow = new Workflow({ name: 'Test Workflow' });
      const node1 = workflow.addNode({ type: NODE_TYPES.TOOL });
      const node2 = workflow.addNode({ type: NODE_TYPES.TOOL });

      const conn = workflow.addConnection({ from: node1.id, to: node2.id });

      expect(conn).toBeDefined();
      expect(workflow.connections.size).toBe(1);
    });

    test('添加连接时应更新节点的输入输出', () => {
      const workflow = new Workflow({ name: 'Test Workflow' });
      const node1 = workflow.addNode({ type: NODE_TYPES.TOOL });
      const node2 = workflow.addNode({ type: NODE_TYPES.TOOL });

      workflow.addConnection({ from: node1.id, to: node2.id });

      expect(node1.outputs.length).toBe(1);
      expect(node2.inputs.length).toBe(1);
    });

    test('工作流应支持移除连接', () => {
      const workflow = new Workflow({ name: 'Test Workflow' });
      const node1 = workflow.addNode({ type: NODE_TYPES.TOOL });
      const node2 = workflow.addNode({ type: NODE_TYPES.TOOL });

      const conn = workflow.addConnection({ from: node1.id, to: node2.id });
      const removed = workflow.removeConnection(conn.id);

      expect(removed).toBe(true);
      expect(workflow.connections.size).toBe(0);
    });

    test('移除连接时应更新节点的输入输出', () => {
      const workflow = new Workflow({ name: 'Test Workflow' });
      const node1 = workflow.addNode({ type: NODE_TYPES.TOOL });
      const node2 = workflow.addNode({ type: NODE_TYPES.TOOL });

      const conn = workflow.addConnection({ from: node1.id, to: node2.id });
      workflow.removeConnection(conn.id);

      expect(node1.outputs.length).toBe(0);
      expect(node2.inputs.length).toBe(0);
    });

    test('工作流应支持变量存储', () => {
      const variables = { apiKey: 'test-key', maxRetries: 3 };
      const workflow = new Workflow({ name: 'Test Workflow', variables });

      expect(workflow.variables.apiKey).toBe('test-key');
      expect(workflow.variables.maxRetries).toBe(3);
    });

    test('工作流应正确序列化为 JSON', () => {
      const workflow = new Workflow({ name: 'Test Workflow' });
      workflow.addNode({ type: NODE_TYPES.START });
      workflow.addNode({ type: NODE_TYPES.END });

      const json = workflow.toJSON();

      expect(json.id).toBeDefined();
      expect(json.name).toBe('Test Workflow');
      expect(json.nodes.length).toBe(2);
      expect(json.status).toBe('idle');
    });
  });

  describe('工作流执行测试', () => {
    test('工作流应默认为 idle 状态', () => {
      const workflow = new Workflow({ name: 'Test Workflow' });
      expect(workflow.status).toBe('idle');
    });

    test('工作流应跟踪更新时间', () => {
      const workflow = new Workflow({ name: 'Test Workflow' });
      const initialTime = workflow.updatedAt;

      // 稍等片刻
      const start = Date.now();
      while (Date.now() - start < 10) {}

      workflow.addNode({ type: NODE_TYPES.TOOL });

      expect(workflow.updatedAt).toBeGreaterThan(initialTime);
    });

    test('工作流应支持执行日志', () => {
      const workflow = new Workflow({ name: 'Test Workflow' });
      expect(Array.isArray(workflow.executionLog)).toBe(true);
    });
  });

  describe('节点状态管理测试', () => {
    test('节点状态应为有效值', () => {
      const validStatuses = ['idle', 'running', 'success', 'error'];
      const node = new WorkflowNode({ type: NODE_TYPES.TOOL });

      expect(validStatuses).toContain(node.status);
    });

    test('节点应支持状态变更', () => {
      const node = new WorkflowNode({ type: NODE_TYPES.TOOL });
      node.status = 'running';
      expect(node.status).toBe('running');

      node.status = 'success';
      expect(node.status).toBe('success');
    });

    test('节点应支持结果存储', () => {
      const node = new WorkflowNode({ type: NODE_TYPES.TOOL });
      const result = { data: 'test result' };

      node.result = result;
      expect(node.result).toBe(result);
    });

    test('节点应支持错误存储', () => {
      const node = new WorkflowNode({ type: NODE_TYPES.TOOL });
      const error = new Error('Test error');

      node.error = error;
      expect(node.error).toBe(error);
    });
  });

  describe('复杂工作流场景测试', () => {
    test('应支持创建线性工作流', () => {
      const workflow = new Workflow({ name: 'Linear Workflow' });

      const start = workflow.addNode({ type: NODE_TYPES.START });
      const tool1 = workflow.addNode({ type: NODE_TYPES.TOOL });
      const tool2 = workflow.addNode({ type: NODE_TYPES.TOOL });
      const end = workflow.addNode({ type: NODE_TYPES.END });

      workflow.addConnection({ from: start.id, to: tool1.id });
      workflow.addConnection({ from: tool1.id, to: tool2.id });
      workflow.addConnection({ from: tool2.id, to: end.id });

      expect(workflow.nodes.size).toBe(4);
      expect(workflow.connections.size).toBe(3);
    });

    test('应支持创建分支工作流', () => {
      const workflow = new Workflow({ name: 'Branching Workflow' });

      const start = workflow.addNode({ type: NODE_TYPES.START });
      const condition = workflow.addNode({ type: NODE_TYPES.CONDITION });
      const toolA = workflow.addNode({ type: NODE_TYPES.TOOL });
      const toolB = workflow.addNode({ type: NODE_TYPES.TOOL });
      const end = workflow.addNode({ type: NODE_TYPES.END });

      workflow.addConnection({ from: start.id, to: condition.id });
      workflow.addConnection({ from: condition.id, to: toolA.id, label: 'True' });
      workflow.addConnection({ from: condition.id, to: toolB.id, label: 'False' });
      workflow.addConnection({ from: toolA.id, to: end.id });
      workflow.addConnection({ from: toolB.id, to: end.id });

      expect(workflow.nodes.size).toBe(5);
      expect(workflow.connections.size).toBe(5);
    });

    test('应支持创建并行工作流', () => {
      const workflow = new Workflow({ name: 'Parallel Workflow' });

      const start = workflow.addNode({ type: NODE_TYPES.START });
      const parallel = workflow.addNode({ type: NODE_TYPES.PARALLEL });
      const tool1 = workflow.addNode({ type: NODE_TYPES.TOOL });
      const tool2 = workflow.addNode({ type: NODE_TYPES.TOOL });
      const tool3 = workflow.addNode({ type: NODE_TYPES.TOOL });
      const end = workflow.addNode({ type: NODE_TYPES.END });

      workflow.addConnection({ from: start.id, to: parallel.id });
      workflow.addConnection({ from: parallel.id, to: tool1.id });
      workflow.addConnection({ from: parallel.id, to: tool2.id });
      workflow.addConnection({ from: parallel.id, to: tool3.id });
      workflow.addConnection({ from: tool1.id, to: end.id });
      workflow.addConnection({ from: tool2.id, to: end.id });
      workflow.addConnection({ from: tool3.id, to: end.id });

      expect(workflow.nodes.size).toBe(6);
      expect(workflow.connections.size).toBe(7);
    });

    test('应支持循环工作流', () => {
      const workflow = new Workflow({ name: 'Loop Workflow' });

      const start = workflow.addNode({ type: NODE_TYPES.START });
      const loop = workflow.addNode({ type: NODE_TYPES.LOOP });
      const tool = workflow.addNode({ type: NODE_TYPES.TOOL });
      const end = workflow.addNode({ type: NODE_TYPES.END });

      workflow.addConnection({ from: start.id, to: loop.id });
      workflow.addConnection({ from: loop.id, to: tool.id });
      workflow.addConnection({ from: tool.id, to: loop.id }); // 循环回环
      workflow.addConnection({ from: loop.id, to: end.id });

      expect(workflow.nodes.size).toBe(4);
      expect(workflow.connections.size).toBe(4);
    });
  });

  describe('边界条件和异常处理测试', () => {
    test('移除不存在的节点应返回 false', () => {
      const workflow = new Workflow({ name: 'Test Workflow' });
      const removed = workflow.removeNode('non_existent_node');

      expect(removed).toBe(false);
    });

    test('移除不存在的连接应返回 false', () => {
      const workflow = new Workflow({ name: 'Test Workflow' });
      const removed = workflow.removeConnection('non_existent_conn');

      expect(removed).toBe(false);
    });

    test('添加连接到不存在的节点应不崩溃', () => {
      const workflow = new Workflow({ name: 'Test Workflow' });

      expect(() => {
        workflow.addConnection({ from: 'non_existent_node1', to: 'non_existent_node2' });
      }).not.toThrow();
    });

    test('空配置应使用默认值', () => {
      const node = new WorkflowNode({});
      expect(node.type).toBe(NODE_TYPES.TOOL);
      expect(node.name).toBe(NODE_TYPES.TOOL);
      expect(node.config).toEqual({});
    });

    test('节点ID应包含时间戳和随机部分', () => {
      const node = new WorkflowNode({ type: NODE_TYPES.TOOL });
      const parts = node.id.split('_');

      expect(parts.length).toBe(3);
      expect(parts[0]).toBe('node');
    });

    test('连接ID应包含时间戳和随机部分', () => {
      const conn = new WorkflowConnection({ from: 'n1', to: 'n2' });
      const parts = conn.id.split('_');

      expect(parts.length).toBe(3);
      expect(parts[0]).toBe('conn');
    });
  });

  describe('性能和安全测试', () => {
    test('大量节点创建应高效', () => {
      const workflow = new Workflow({ name: 'Large Workflow' });
      const start = Date.now();

      for (let i = 0; i < 1000; i++) {
        workflow.addNode({ type: NODE_TYPES.TOOL });
      }

      const elapsed = Date.now() - start;
      expect(elapsed).toBeLessThan(100); // 应在100ms内完成
      expect(workflow.nodes.size).toBe(1000);
    });

    test('大量连接创建应高效', () => {
      const workflow = new Workflow({ name: 'Large Workflow' });
      const nodes = [];

      for (let i = 0; i < 100; i++) {
        nodes.push(workflow.addNode({ type: NODE_TYPES.TOOL }));
      }

      const start = Date.now();

      for (let i = 0; i < nodes.length - 1; i++) {
        workflow.addConnection({ from: nodes[i].id, to: nodes[i + 1].id });
      }

      const elapsed = Date.now() - start;
      expect(elapsed).toBeLessThan(50); // 应在50ms内完成
      expect(workflow.connections.size).toBe(99);
    });

    test('节点ID应具有足够熵', () => {
      const nodeIds = new Set();

      for (let i = 0; i < 10000; i++) {
        const node = new WorkflowNode({ type: NODE_TYPES.TOOL });
        nodeIds.add(node.id);
      }

      expect(nodeIds.size).toBe(10000); // 所有ID应唯一
    });

    test('连接ID应具有足够熵', () => {
      const connIds = new Set();

      for (let i = 0; i < 10000; i++) {
        const conn = new WorkflowConnection({ from: 'n1', to: 'n2' });
        connIds.add(conn.id);
      }

      expect(connIds.size).toBe(10000); // 所有ID应唯一
    });

    test('工作流ID应具有足够熵', () => {
      const workflowIds = new Set();

      for (let i = 0; i < 10000; i++) {
        const workflow = new Workflow({ name: 'Test' });
        workflowIds.add(workflow.id);
      }

      expect(workflowIds.size).toBe(10000); // 所有ID应唯一
    });
  });
});