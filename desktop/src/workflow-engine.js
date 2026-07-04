/**
 * Y·NEX Desktop — Workflow Engine
 * 可视化工作流执行引擎，支持节点、连接、条件和并行
 */

const EventEmitter = require('events');
const vm = require('vm');

// ============================================================
// 工作流节点类型
// ============================================================

const NODE_TYPES = {
  START: 'start',       // 开始节点
  END: 'end',           // 结束节点
  TOOL: 'tool',         // 工具调用节点
  AGENT: 'agent',       // Agent 任务节点
  CONDITION: 'condition', // 条件分支节点
  LOOP: 'loop',         // 循环节点
  PARALLEL: 'parallel', // 并行执行节点
  DELAY: 'delay',       // 延迟节点
  TRIGGER: 'trigger',   // 触发器节点
  HTTP: 'http',         // HTTP 请求节点
  CODE: 'code',         // 代码执行节点
};

// ============================================================
// 工作流节点
// ============================================================

class WorkflowNode {
  constructor(config) {
    this.id = config.id || `node_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    this.type = config.type || NODE_TYPES.TOOL;
    this.name = config.name || this.type;
    this.config = config.config || {};
    this.position = config.position || { x: 0, y: 0 };
    this.inputs = [];   // 输入连接
    this.outputs = [];  // 输出连接
    this.status = 'idle'; // idle | running | success | error
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

// ============================================================
// 工作流连接
// ============================================================

class WorkflowConnection {
  constructor(config) {
    this.id = config.id || `conn_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    this.from = config.from;   // 源节点 ID
    this.to = config.to;       // 目标节点 ID
    this.condition = config.condition || null; // 条件表达式（用于条件分支）
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

// ============================================================
// 工作流定义
// ============================================================

class Workflow {
  constructor(config) {
    this.id = config.id || `wf_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    this.name = config.name || '未命名工作流';
    this.description = config.description || '';
    this.nodes = new Map();   // id -> WorkflowNode
    this.connections = new Map(); // id -> WorkflowConnection
    this.variables = config.variables || {}; // 工作流变量
    this.createdAt = Date.now();
    this.updatedAt = Date.now();
    this.status = 'idle'; // idle | running | paused | completed | error
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
    
    // 移除相关连接
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
    
    // 更新节点的输入输出
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

  static fromJSON(data) {
    const wf = new Workflow({ 
      id: data.id, 
      name: data.name, 
      description: data.description,
      variables: data.variables,
    });
    wf.createdAt = data.createdAt;
    wf.updatedAt = data.updatedAt;
    wf.status = data.status || 'idle';
    
    // 添加节点
    for (const nodeData of data.nodes || []) {
      const node = wf.addNode(nodeData);
      node.status = nodeData.status || 'idle';
    }
    
    // 添加连接
    for (const connData of data.connections || []) {
      wf.addConnection(connData);
    }
    
    return wf;
  }
}

// ============================================================
// 工作流执行引擎
// ============================================================

class WorkflowEngine extends EventEmitter {
  constructor(toolRegistry, agentHarness) {
    super();
    this.toolRegistry = toolRegistry;
    this.agentHarness = agentHarness;
    this.workflows = new Map(); // id -> Workflow
    this.runningWorkflows = new Map(); // id -> execution context
  }

  // ============================================================
  // 工作流管理
  // ============================================================

  createWorkflow(config) {
    const wf = new Workflow(config);
    this.workflows.set(wf.id, wf);
    this.emit('workflow:created', wf);
    return wf;
  }

  getWorkflow(id) {
    return this.workflows.get(id);
  }

  listWorkflows() {
    return Array.from(this.workflows.values()).map(wf => ({
      id: wf.id,
      name: wf.name,
      description: wf.description,
      status: wf.status,
      nodeCount: wf.nodes.size,
      updatedAt: wf.updatedAt,
    }));
  }

  deleteWorkflow(id) {
    const wf = this.workflows.get(id);
    if (!wf) return false;
    
    // 如果正在运行，先停止
    if (this.runningWorkflows.has(id)) {
      this.stopWorkflow(id);
    }
    
    this.workflows.delete(id);
    this.emit('workflow:deleted', id);
    return true;
  }

  saveWorkflow(id) {
    const wf = this.workflows.get(id);
    if (!wf) return null;
    return wf.toJSON();
  }

  loadWorkflow(data) {
    const wf = Workflow.fromJSON(data);
    this.workflows.set(wf.id, wf);
    this.emit('workflow:loaded', wf);
    return wf;
  }

  // ============================================================
  // 工作流执行
  // ============================================================

  async runWorkflow(workflowId, input = {}) {
    const wf = this.workflows.get(workflowId);
    if (!wf) {
      return { ok: false, error: '工作流不存在' };
    }

    // 检查是否已经在运行
    if (this.runningWorkflows.has(workflowId)) {
      return { ok: false, error: '工作流正在运行中' };
    }

    // 创建执行上下文
    const ctx = {
      workflow: wf,
      input,
      variables: { ...wf.variables, ...input },
      currentNode: null,
      visited: new Set(),
      results: new Map(),
      startTime: Date.now(),
      paused: false,
      stopped: false,
    };

    this.runningWorkflows.set(workflowId, ctx);
    wf.status = 'running';
    wf.executionLog = [];
    this.emit('workflow:started', wf);

    try {
      // 找到开始节点
      const startNode = this._findStartNode(wf);
      if (!startNode) {
        throw new Error('工作流没有开始节点');
      }

      // 从开始节点执行
      await this._executeNode(ctx, startNode);

      // 执行完成
      wf.status = ctx.stopped ? 'stopped' : 'completed';
      const endTime = Date.now();
      
      this.emit('workflow:completed', {
        workflowId,
        duration: endTime - ctx.startTime,
        results: Array.from(ctx.results.entries()),
      });

      this.runningWorkflows.delete(workflowId);
      
      return {
        ok: true,
        status: wf.status,
        duration: endTime - ctx.startTime,
        results: Array.from(ctx.results.entries()).map(([id, r]) => ({ nodeId: id, result: r })),
        log: wf.executionLog,
      };
    } catch (e) {
      wf.status = 'error';
      this.emit('workflow:error', { workflowId, error: e.message });
      this.runningWorkflows.delete(workflowId);
      
      return {
        ok: false,
        error: e.message,
        log: wf.executionLog,
      };
    }
  }

  pauseWorkflow(workflowId) {
    const ctx = this.runningWorkflows.get(workflowId);
    if (!ctx) return false;
    
    ctx.paused = true;
    ctx.workflow.status = 'paused';
    this.emit('workflow:paused', workflowId);
    return true;
  }

  resumeWorkflow(workflowId) {
    const ctx = this.runningWorkflows.get(workflowId);
    if (!ctx) return false;
    
    ctx.paused = false;
    ctx.workflow.status = 'running';
    this.emit('workflow:resumed', workflowId);
    return true;
  }

  stopWorkflow(workflowId) {
    const ctx = this.runningWorkflows.get(workflowId);
    if (!ctx) return false;
    
    ctx.stopped = true;
    ctx.paused = false;
    ctx.workflow.status = 'stopped';
    this.emit('workflow:stopped', workflowId);
    this.runningWorkflows.delete(workflowId);
    return true;
  }

  // ============================================================
  // 节点执行
  // ============================================================

  async _executeNode(ctx, node) {
    if (ctx.stopped) return;
    
    // 等待暂停恢复
    while (ctx.paused && !ctx.stopped) {
      await new Promise(r => setTimeout(r, 500));
    }
    if (ctx.stopped) return;

    node.status = 'running';
    ctx.currentNode = node;
    this.emit('node:started', { workflowId: ctx.workflow.id, nodeId: node.id });

    ctx.workflow.executionLog.push({
      time: Date.now(),
      nodeId: node.id,
      type: 'start',
      name: node.name,
    });

    try {
      let result;
      
      switch (node.type) {
        case NODE_TYPES.START:
          result = ctx.input;
          break;
        case NODE_TYPES.END:
          result = ctx.results.get(node.inputs[0]?.from) || ctx.input;
          ctx.stopped = true; // 结束节点停止执行
          break;
        case NODE_TYPES.TOOL:
          result = await this._executeTool(ctx, node);
          break;
        case NODE_TYPES.AGENT:
          result = await this._executeAgent(ctx, node);
          break;
        case NODE_TYPES.CONDITION:
          result = await this._executeCondition(ctx, node);
          break;
        case NODE_TYPES.LOOP:
          result = await this._executeLoop(ctx, node);
          break;
        case NODE_TYPES.PARALLEL:
          result = await this._executeParallel(ctx, node);
          break;
        case NODE_TYPES.DELAY:
          result = await this._executeDelay(ctx, node);
          break;
        case NODE_TYPES.HTTP:
          result = await this._executeHttp(ctx, node);
          break;
        case NODE_TYPES.CODE:
          result = await this._executeCode(ctx, node);
          break;
        default:
          result = null;
      }

      node.status = 'success';
      node.result = result;
      ctx.results.set(node.id, result);
      
      ctx.workflow.executionLog.push({
        time: Date.now(),
        nodeId: node.id,
        type: 'success',
        result: typeof result === 'object' ? JSON.stringify(result).substring(0, 200) : String(result).substring(0, 200),
      });

      this.emit('node:completed', { workflowId: ctx.workflow.id, nodeId: node.id, result });

      // 执行后续节点（除非是结束节点或条件分支）
      if (node.type !== NODE_TYPES.END && node.type !== NODE_TYPES.CONDITION && node.type !== NODE_TYPES.LOOP) {
        for (const conn of node.outputs) {
          const nextNode = ctx.workflow.nodes.get(conn.to);
          if (nextNode && !ctx.visited.has(nextNode.id)) {
            ctx.visited.add(nextNode.id);
            await this._executeNode(ctx, nextNode);
          }
        }
      }
    } catch (e) {
      node.status = 'error';
      node.error = e.message;
      
      ctx.workflow.executionLog.push({
        time: Date.now(),
        nodeId: node.id,
        type: 'error',
        error: e.message,
      });

      this.emit('node:error', { workflowId: ctx.workflow.id, nodeId: node.id, error: e.message });
      throw e;
    }
  }

  async _executeTool(ctx, node) {
    const toolName = node.config.tool;
    const args = this._resolveVariables(ctx, node.config.args || {});
    
    if (!this.toolRegistry) {
      throw new Error('工具注册中心未初始化');
    }

    const result = await this.toolRegistry.callTool(toolName, args, { workflowId: ctx.workflow.id });
    return result;
  }

  async _executeAgent(ctx, node) {
    const task = this._resolveVariables(ctx, node.config.task || '');
    const model = node.config.model || 'deepseekv3';
    
    if (!this.agentHarness) {
      throw new Error('Agent 引擎未初始化');
    }

    const result = await this.agentHarness.run(task, { model });
    return result;
  }

  async _executeCondition(ctx, node) {
    const condition = node.config.condition || 'true';
    const result = this._evaluateCondition(ctx, condition);
    
    // 执行对应的分支
    for (const conn of node.outputs) {
      if (conn.condition === result || (!conn.condition && result)) {
        const nextNode = ctx.workflow.nodes.get(conn.to);
        if (nextNode && !ctx.visited.has(nextNode.id)) {
          ctx.visited.add(nextNode.id);
          await this._executeNode(ctx, nextNode);
        }
      }
    }
    
    return { condition, result };
  }

  async _executeLoop(ctx, node) {
    const items = this._resolveVariables(ctx, node.config.items || []);
    const maxIterations = node.config.maxIterations || 10;
    const results = [];

    for (let i = 0; i < Math.min(items.length, maxIterations); i++) {
      if (ctx.stopped) break;
      
      ctx.variables.item = items[i];
      ctx.variables.index = i;
      
      // 执行循环体内的节点
      for (const conn of node.outputs) {
        if (conn.label === 'body') {
          const bodyNode = ctx.workflow.nodes.get(conn.to);
          if (bodyNode) {
            await this._executeNode(ctx, bodyNode);
            results.push(ctx.results.get(bodyNode.id));
          }
        }
      }
    }

    return results;
  }

  async _executeParallel(ctx, node) {
    const tasks = [];
    
    for (const conn of node.outputs) {
      const nextNode = ctx.workflow.nodes.get(conn.to);
      if (nextNode) {
        tasks.push(this._executeNode(ctx, nextNode));
      }
    }

    const results = await Promise.allSettled(tasks);
    return results.map(r => r.status === 'fulfilled' ? r.value : { error: r.reason?.message });
  }

  async _executeDelay(ctx, node) {
    const ms = node.config.duration || 1000;
    await new Promise(r => setTimeout(r, ms));
    return { delayed: ms };
  }

  async _executeHttp(ctx, node) {
    const http = require('http');
    const url = this._resolveVariables(ctx, node.config.url);
    const method = node.config.method || 'GET';
    const body = node.config.body ? this._resolveVariables(ctx, node.config.body) : null;

    return new Promise((resolve, reject) => {
      const req = http.request(url, { method }, (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => resolve({ status: res.statusCode, data }));
      });
      req.on('error', reject);
      if (body) req.write(JSON.stringify(body));
      req.end();
    });
  }

  async _executeCode(ctx, node) {
    const code = node.config.code || '';
    const language = node.config.language || 'javascript';
    
    // 安全执行 JavaScript — 使用 vm 沙箱隔离
    if (language === 'javascript') {
      // 构建受限的沙箱上下文，仅暴露安全的 API
      const sandbox = {
        // 工作流上下文（只读）
        context: { workflowId: ctx.workflow.id },
        variables: ctx.variables,
        // 安全的工具函数
        console: {
          log: (...args) => this.emit('log', { level: 'log', message: args.join(' ') }),
          warn: (...args) => this.emit('log', { level: 'warn', message: args.join(' ') }),
          error: (...args) => this.emit('log', { level: 'error', message: args.join(' ') }),
        },
        JSON: JSON,
        Math: Math,
        Date: Date,
        String: String,
        Number: Number,
        Boolean: Boolean,
        Array: Array,
        Object: Object,
        parseInt: parseInt,
        parseFloat: parseFloat,
        isNaN: isNaN,
        encodeURIComponent: encodeURIComponent,
        decodeURIComponent: decodeURIComponent,
        // 显式不暴露 require, process, fs, child_process 等
      };
      
      try {
        // 用函数包裹用户代码，支持 return 语句
        const wrappedCode = `(function(context, variables) { ${code} })(context, variables)`;
        const script = new vm.Script(wrappedCode, { filename: 'workflow-code.js', timeout: 5000 });
        const context = vm.createContext(sandbox);
        const result = script.runInContext(context);
        return result;
      } catch (e) {
        throw new Error(`代码执行失败: ${e.message}`);
      }
    }
    
    throw new Error(`不支持的语言: ${language}`);
  }

  // ============================================================
  // 辅助方法
  // ============================================================

  _findStartNode(wf) {
    for (const node of wf.nodes.values()) {
      if (node.type === NODE_TYPES.START) {
        return node;
      }
    }
    return null;
  }

  _resolveVariables(ctx, value) {
    if (typeof value === 'string') {
      // 替换变量引用 {{var}}
      return value.replace(/\{\{(\w+)\}\}/g, (_, key) => ctx.variables[key] || '');
    }
    if (typeof value === 'object' && value !== null) {
      const resolved = {};
      for (const [k, v] of Object.entries(value)) {
        resolved[k] = this._resolveVariables(ctx, v);
      }
      return resolved;
    }
    return value;
  }

  _evaluateCondition(ctx, condition) {
    // 安全条件评估 — 使用 vm 沙箱
    try {
      const sandbox = {
        variables: ctx.variables,
        JSON: JSON,
        Math: Math,
        Date: Date,
        String: String,
        Number: Number,
        Boolean: Boolean,
        Array: Array,
        Object: Object,
        parseInt: parseInt,
        parseFloat: parseFloat,
        isNaN: isNaN,
      };
      // 用表达式包裹，避免顶层 return 语句报错
      const script = new vm.Script(`(${condition})`, { filename: 'workflow-condition.js', timeout: 3000 });
      const context = vm.createContext(sandbox);
      return script.runInContext(context);
    } catch (e) {
      console.warn('[WorkflowEngine] 条件评估失败:', e.message);
      return false;
    }
  }
}

module.exports = {
  WorkflowEngine,
  Workflow,
  WorkflowNode,
  WorkflowConnection,
  NODE_TYPES,
};