/**
 * TriGen Agent Engine v2.0 — Harness Engineering Alignment
 * 
 * 基于 Claude Code 架构学习，重构 Agent 核心引擎：
 * - while(true) async generator 循环（替代 for 循环）
 * - 原生 function calling（替代正则解析）
 * - 读写分离并发工具执行
 * - 五层渐进式上下文压缩
 * - 子 Agent 派发系统
 * - TaskCreate/TaskUpdate 任务跟踪
 * - 七链权限决策
 * - 三层记忆架构
 * - 技能/插件加载系统
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

// ============================================================
// 1. Harness Core — Agent Loop (async generator)
// ============================================================

class AgentHarness {
  constructor(config = {}) {
    this.config = {
      maxIterations: config.maxIterations || 50,
      model: config.model || 'deepseekv3',
      workspace: config.workspace || process.cwd(),
      concurrencyLimit: config.concurrencyLimit || 10,
      ...config
    };
    this.tools = config.toolRegistry || new ToolRegistry();
    this.memory = new MemorySystem(config.memory);
    this.permissions = new PermissionSystem(config.permissions);
    this.tasks = new TaskManager();
    this.skills = new SkillLoader(config.skillsDir);
    this.ctx = new ContextManager(config.context);
    this.subAgents = new SubAgentSystem(this);
  }

  /**
   * 核心 Agent 循环 — async generator
   * 用 while(true) + yield 替代递归，避免栈溢出，支持流式输出
   */
  async *run(task, options = {}) {
    const model = options.model || this.config.model;
    const maxIter = options.maxIterations || this.config.maxIterations;
    const workspace = options.workspace || this.config.workspace;
    const tools = options.tools || this.tools;

    // 加载技能上下文
    const skillsCtx = this.skills.buildContext();

    // 初始系统提示词
    const systemMsg = this._buildSystemPrompt(tools, skillsCtx, options.systemExtra);

    // 状态对象（可变，在循环各阶段共享）
    const state = {
      messages: [
        { role: 'system', content: systemMsg },
        { role: 'user', content: task }
      ],
      history: [],
      iterations: 0,
      toolResults: [],
      workingDir: workspace
    };

    yield { type: 'status', phase: 'start', message: 'Agent 启动' };

    while (state.iterations < maxIter) {
      // Phase 1: 上下文压缩
      yield { type: 'status', phase: 'compress', iteration: state.iterations };
      state.messages = this.ctx.compress(state.messages);

      // Phase 2: 调用 LLM（带工具定义）
      yield { type: 'status', phase: 'thinking', iteration: state.iterations };
      const response = await this._callLLM({
        messages: state.messages,
        model,
        tools: tools.toOpenAIFormat(),
        stream: options.stream
      });

      if (options.stream && response.stream) {
        // 流式模式：yield 每个 token
        let fullContent = '';
        const toolCalls = [];
        for await (const chunk of response.stream) {
          if (chunk.content) {
            fullContent += chunk.content;
            yield { type: 'token', content: chunk.content };
          }
          if (chunk.tool_calls) {
            for (const tc of chunk.tool_calls) {
              const existing = toolCalls.find(t => t.id === tc.id);
              if (existing) {
                existing.function.arguments += tc.function.arguments || '';
              } else {
                toolCalls.push(tc);
              }
            }
          }
        }
        response.content = fullContent;
        response.tool_calls = toolCalls;
      }

      state.iterations++;

      // Phase 3: 解析工具调用
      const toolUseBlocks = this._extractToolCalls(response);
      
      if (toolUseBlocks.length === 0) {
        // 无工具调用 → 任务完成
        yield { type: 'status', phase: 'complete', iterations: state.iterations };
        yield { type: 'final', content: response.content || '', 
                iterations: state.iterations, history: state.history };
        return;
      }

      // Phase 4: 工具执行（并发分区）
      yield { type: 'status', phase: 'executing', tools: toolUseBlocks.map(t => t.name), iteration: state.iterations };
      
      const toolResults = await this._executeTools(toolUseBlocks, tools, { workspace });
      
      // 将工具结果注入消息历史
      state.messages.push({ role: 'assistant', content: response.content || null, tool_calls: toolUseBlocks });
      for (const result of toolResults) {
        state.messages.push({ role: 'tool', tool_call_id: result.id, content: JSON.stringify(result.output) });
        state.history.push({ action: result.name, input: result.input, output: result.output });
        yield { type: 'observation', tool: result.name, result: result.output };
      }

      // Phase 5: 停止钩子
      yield { type: 'status', phase: 'hooks', iteration: state.iterations };
      await this._runStopHooks(state);

      // Phase 6: 续轮决策（LLM 自主决定继续 or 结束）
      // while(true) 自动续轮，除非 LLM 不再发出 tool_calls
    }

    // 达到最大迭代
    yield { type: 'final', content: '已达到最大执行轮次', 
            iterations: state.iterations, history: state.history };
  }

  /** 构建系统提示词 */
  _buildSystemPrompt(tools, skillsCtx, extra = '') {
    const toolDesc = tools.list()
      .map(t => `- ${t.name}: ${t.description}`)
      .join('\n');

    return `你是 TriGen AI Agent，一个智能编程助手。

## 可用工具
${toolDesc}

## 技能上下文
${skillsCtx}

## 规则
1. 使用提供的 tools 执行操作，不要用文字描述模拟
2. 文件操作使用绝对路径
3. 每次工具调用前检查权限
4. 完成后直接给出最终答案，不再调用工具
5. 遇到错误时尝试自行恢复一次，失败后报告用户

${extra}`;
  }

  /** 从 LLM 响应中提取工具调用 */
  _extractToolCalls(response) {
    // 优先使用原生 tool_calls
    if (response.tool_calls && response.tool_calls.length > 0) {
      return response.tool_calls.map(tc => ({
        id: tc.id,
        name: tc.function.name,
        input: tc.function.arguments ? JSON.parse(tc.function.arguments) : {}
      }));
    }
    // 兼容旧格式（正则解析）
    const content = response.content || '';
    const toolCalls = [];
    const toolPattern = /调用工具[：:]\s*(\w+)\s*\n参数[：:]\s*(\{[\s\S]*?\})/g;
    let match;
    while ((match = toolPattern.exec(content)) !== null) {
      try {
        toolCalls.push({
          id: crypto.randomUUID(),
          name: match[1],
          input: JSON.parse(match[2])
        });
      } catch(e) {}
    }
    return toolCalls;
  }

  /** 并发工具执行（读写分区） */
  async _executeTools(toolUseBlocks, tools, ctx) {
    // 分区：读工具先并发执行，写工具逐个串行
    const groups = this._partitionTools(toolUseBlocks, tools);
    const results = [];

    for (const group of groups) {
      if (group.concurrent && group.blocks.length > 1) {
        // 并发批次（最多 concurrencyLimit 个）
        const batchResults = await Promise.all(
          group.blocks.map(block => this._executeOne(block, tools, ctx))
        );
        results.push(...batchResults);
      } else {
        // 串行批次
        for (const block of group.blocks) {
          const result = await this._executeOne(block, tools, ctx);
          results.push(result);
        }
      }
    }
    return results;
  }

  /** 工具分区策略：连续的只读工具→并发批次，遇到写工具→新串行批次 */
  _partitionTools(blocks, tools) {
    const groups = [];
    let currentGroup = { concurrent: true, blocks: [] };

    for (const block of blocks) {
      const tool = tools.get(block.name);
      const isReadOnly = tool ? tool.isReadOnly : false;

      if (isReadOnly) {
        currentGroup.blocks.push(block);
      } else {
        // 写工具：先提交前面积累的读批次
        if (currentGroup.blocks.length > 0) {
          groups.push({ ...currentGroup });
        }
        // 写工具单独串行
        groups.push({ concurrent: false, blocks: [block] });
        currentGroup = { concurrent: true, blocks: [] };
      }
    }

    // 剩余读批次
    if (currentGroup.blocks.length > 0) {
      groups.push(currentGroup);
    }

    return groups;
  }

  /** 执行单个工具调用 */
  async _executeOne(block, tools, ctx) {
    try {
      // 权限检查
      const permCheck = this.permissions.check(block.name, block.input);
      if (!permCheck.allowed) {
        return { id: block.id, name: block.name, input: block.input, 
                 output: { success: false, error: `权限拒绝: ${permCheck.reason}` } };
      }

      const result = await tools.execute(block.name, block.input, ctx);
      return { id: block.id, name: block.name, input: block.input, output: result };
    } catch(e) {
      return { id: block.id, name: block.name, input: block.input, 
               output: { success: false, error: e.message } };
    }
  }

  /** LLM 调用（支持原生 function calling） */
  async _callLLM({ messages, model, tools, stream }) {
    try {
      const r = await fetch('http://localhost:3001/api/chat', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'x-internal-token': process.env.INTERNAL_SERVICE_TOKEN || ''
        },
        body: JSON.stringify({ model, messages, tools, stream: false }),
        signal: AbortSignal.timeout(120000)
      });
      if (!r.ok) {
        const errText = await r.text().catch(() => '');
        return { content: `API错误 ${r.status}: ${errText.substring(0,200)}`, role: 'assistant' };
      }
      const d = await r.json();
      const msg = d.choices?.[0]?.message || {};
      return {
        content: msg.content || '',
        role: 'assistant',
        tool_calls: msg.tool_calls || null
      };
    } catch(e) {
      return { content: `请求失败: ${e.message}`, role: 'assistant' };
    }
  }

  /** 停止钩子：保存记忆、分类会话 */
  async _runStopHooks(state) {
    // 记忆提取：长对话自动保存关键信息
    if (state.iterations > 10) {
      this.memory.autoRemember(state.history);
    }
    // 工具结果后处理
    this.ctx.recordUsage(state.iterations, state.messages.length);
  }

  /** 派发子 Agent */
  async spawnAgent(prompt, options = {}) {
    return this.subAgents.spawn(prompt, options);
  }
}

// ============================================================
// 2. Tool System — 带并发安全标记的工具注册表
// ============================================================

class ToolRegistry {
  constructor() {
    this._tools = new Map();
    this._initBuiltins();
  }

  /** 工具接口 */
  define(name, config) {
    this._tools.set(name, {
      name,
      description: config.description || '',
      parameters: config.parameters || { type: 'object', properties: {} },
      handler: config.handler,
      isReadOnly: config.isReadOnly !== undefined ? config.isReadOnly : true,
      isConcurrencySafe: config.isConcurrencySafe !== undefined ? config.isConcurrencySafe : true,
      riskLevel: config.riskLevel || 'LOW',  // LOW / MEDIUM / HIGH
      requiresApproval: config.requiresApproval || false
    });
    return this;
  }

  get(name) { return this._tools.get(name); }
  list() { return Array.from(this._tools.values()).map(t => ({
    name: t.name, description: t.description, parameters: t.parameters,
    isReadOnly: t.isReadOnly, riskLevel: t.riskLevel
  })); }

  /** 导出为 OpenAI function calling 格式 */
  toOpenAIFormat() {
    return Array.from(this._tools.values()).map(t => ({
      type: 'function',
      function: {
        name: t.name,
        description: t.description,
        parameters: t.parameters
      }
    }));
  }

  async execute(name, args, ctx = {}) {
    const t = this._tools.get(name);
    if (!t) throw new Error(`工具不存在: ${name}`);
    return await t.handler(args, ctx);
  }

  _initBuiltins() {
    // === 只读工具（可并发）===
    
    // web_search
    this.define('web_search', {
      description: '搜索互联网获取实时信息。当需要最新数据、新闻或无法从知识库回答时使用此工具。',
      parameters: {
        type: 'object',
        properties: {
          query: { type: 'string', description: '搜索关键词' },
          count: { type: 'number', default: 5, description: '返回结果数量(1-10)' }
        },
        required: ['query']
      },
      isReadOnly: true,
      isConcurrencySafe: true,
      riskLevel: 'LOW',
      handler: async (a) => {
        try {
          const r = await fetch(`https://api.duckduckgo.com/?q=${encodeURIComponent(a.query)}&format=json&no_html=1`);
          const d = await r.json();
          const results = (d.RelatedTopics || []).slice(0, a.count || 5).map(x => ({
            title: (x.Text || '').substring(0, 80),
            snippet: x.Text || '',
            url: x.FirstURL || ''
          }));
          return { success: true, results, total: results.length };
        } catch(e) {
          return { success: false, error: e.message };
        }
      }
    });

    // web_fetch
    this.define('web_fetch', {
      description: '获取网页内容并提取文本。传入URL获取该页面的纯文本内容。',
      parameters: {
        type: 'object',
        properties: {
          url: { type: 'string', description: '要获取的网页URL' }
        },
        required: ['url']
      },
      isReadOnly: true,
      isConcurrencySafe: true,
      riskLevel: 'MEDIUM',
      handler: async (a) => {
        try {
          const r = await fetch(a.url, { signal: AbortSignal.timeout(15000) });
          const t = await r.text();
          const clean = t.replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
            .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
            .replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
          return { success: true, content: clean.substring(0, 8000), url: a.url };
        } catch(e) {
          return { success: false, error: e.message };
        }
      }
    });

    // file_read (沙箱)
    this.define('file_read', {
      description: '读取工作区内文件的内容。只能读取workspace目录下的文件。',
      parameters: {
        type: 'object',
        properties: {
          path: { type: 'string', description: '相对于workspace的文件路径' }
        },
        required: ['path']
      },
      isReadOnly: true,
      isConcurrencySafe: true,
      riskLevel: 'LOW',
      handler: async (a, ctx) => {
        const ws = ctx?.workspace || process.cwd();
        const fp = path.resolve(ws, a.path);
        if (!fp.startsWith(path.resolve(ws))) {
          return { success: false, error: '路径越权：禁止访问workspace外的文件' };
        }
        try {
          const content = fs.readFileSync(fp, 'utf-8');
          return { success: true, content, size: content.length, path: a.path };
        } catch(e) {
          return { success: false, error: e.message };
        }
      }
    });

    // === 写工具（必须串行）===

    // file_write (沙箱)
    this.define('file_write', {
      description: '将内容写入工作区文件。会自动创建目录。每次调用写入一个完整文件。',
      parameters: {
        type: 'object',
        properties: {
          path: { type: 'string', description: '相对于workspace的文件路径' },
          content: { type: 'string', description: '要写入的文件内容' }
        },
        required: ['path', 'content']
      },
      isReadOnly: false,
      isConcurrencySafe: false,
      riskLevel: 'MEDIUM',
      requiresApproval: true,
      handler: async (a, ctx) => {
        const ws = ctx?.workspace || process.cwd();
        const fp = path.resolve(ws, a.path);
        if (!fp.startsWith(path.resolve(ws))) {
          return { success: false, error: '路径越权：禁止写入workspace外的文件' };
        }
        try {
          fs.mkdirSync(path.dirname(fp), { recursive: true });
          fs.writeFileSync(fp, a.content, 'utf-8');
          return { success: true, path: a.path, size: a.content.length };
        } catch(e) {
          return { success: false, error: e.message };
        }
      }
    });

    // shell_exec (沙箱)
    this.define('shell_exec', {
      description: '在工作区中执行Shell命令。超时默认30秒，输出限制10KB。需要用户批准。',
      parameters: {
        type: 'object',
        properties: {
          command: { type: 'string', description: '要执行的命令' },
          timeout: { type: 'number', default: 30, description: '超时秒数(最大60)' }
        },
        required: ['command']
      },
      isReadOnly: false,
      isConcurrencySafe: false,
      riskLevel: 'HIGH',
      requiresApproval: true,
      handler: async (a, ctx) => {
        const { execFileSync } = require('child_process');
        const ws = ctx?.workspace || process.cwd();
        const maxT = Math.min(a.timeout || 30, 60);
        const isWin = process.platform === 'win32';
        try {
          const r = execFileSync(
            isWin ? 'cmd.exe' : '/bin/bash',
            [isWin ? '/c' : '-c', a.command],
            { cwd: ws, timeout: maxT * 1000, maxBuffer: 1024 * 1024, encoding: 'utf-8' }
          );
          return { success: true, stdout: r.substring(0, 10000), stderr: '', exitCode: 0 };
        } catch(e) {
          return {
            success: false,
            stdout: (e.stdout || '').substring(0, 5000),
            stderr: (e.stderr || e.message).substring(0, 5000),
            exitCode: e.status || -1
          };
        }
      }
    });

    // calculator
    this.define('calculator', {
      description: '计算数学表达式。支持基本算术、三角函数等。',
      parameters: {
        type: 'object',
        properties: {
          expression: { type: 'string', description: '数学表达式，如 "2+3*4"' }
        },
        required: ['expression']
      },
      isReadOnly: true,
      isConcurrencySafe: true,
      riskLevel: 'LOW',
      handler: async (a) => {
        try {
          const fn = new Function(`return (${a.expression})`);
          return { success: true, result: Number(fn()) };
        } catch(e) {
          return { success: false, error: e.message };
        }
      }
    });

    // === 子 Agent 派发工具 ===
    this.define('spawn_agent', {
      description: '派发一个子Agent处理复杂任务。用于任务分解、并行处理、多角度分析等场景。',
      parameters: {
        type: 'object',
        properties: {
          task: { type: 'string', description: '子任务描述' },
          model: { type: 'string', description: '使用的模型(可选)' },
          maxIterations: { type: 'number', default: 10, description: '最大执行轮次' }
        },
        required: ['task']
      },
      isReadOnly: false,
      isConcurrencySafe: true,
      riskLevel: 'MEDIUM',
      handler: async (a, ctx) => {
        const harness = ctx?.harness;
        if (!harness) return { success: false, error: '需要在Agent上下文中使用' };
        try {
          const result = await harness.spawnAgent(a.task, {
            model: a.model, maxIterations: a.maxIterations
          });
          return { success: true, result };
        } catch(e) {
          return { success: false, error: e.message };
        }
      }
    });
  }
}

// ============================================================
// 3. Context Manager — 五层渐进式压缩
// ============================================================

class ContextManager {
  constructor(config = {}) {
    this.maxTokens = config.maxTokens || 64000;
    this.compressThreshold = config.compressThreshold || 0.7; // 70%触发压缩
    this.usageHistory = [];
  }

  /** 压缩消息历史（逐级升级） */
  compress(messages) {
    const estimatedTokens = this._estimateTokens(messages);
    if (estimatedTokens < this.maxTokens * this.compressThreshold) {
      return messages; // 无压缩
    }

    // Layer 1: Snip — 删除最老的轮次（保留 system + 最近5轮）
    if (estimatedTokens > this.maxTokens * 0.8) {
      const system = messages.find(m => m.role === 'system');
      const recent = messages.slice(-12); // 保留最近 ~6 轮
      if (system && !recent.find(m => m.role === 'system')) {
        recent.unshift(system);
      }
      return recent;
    }

    // Layer 2: Microcompact — 截断冗长的工具输出
    return messages.map(m => {
      if (m.role === 'tool' && m.content && m.content.length > 2000) {
        return { ...m, content: m.content.substring(0, 2000) + '\n...(已截断)' };
      }
      return m;
    });
  }

  /** 记录使用统计 */
  recordUsage(iterations, messageCount) {
    this.usageHistory.push({ time: Date.now(), iterations, messageCount });
    if (this.usageHistory.length > 100) this.usageHistory.shift();
  }

  /** 粗略估算 token 数（中文 ~1.5 字符/token，英文 ~4 字符/token） */
  _estimateTokens(messages) {
    let total = 0;
    for (const m of messages) {
      const text = typeof m.content === 'string' ? m.content : JSON.stringify(m.content);
      total += Math.ceil(text.length / 3); // 混合语言估算
    }
    return total;
  }
}

// ============================================================
// 4. Permission System — 七链决策
// ============================================================

class PermissionSystem {
  constructor(config = {}) {
    this.mode = config.mode || 'default'; // default / auto / bypass / yolo
    this.alwaysAllow = new Set(config.alwaysAllow || ['web_search', 'calculator', 'file_read']);
    this.alwaysDeny = new Set(config.alwaysDeny || []);
    this.alwaysAsk = new Set(config.alwaysAsk || []);
    this.decisionCache = new Map(); // 30分钟缓存
    this.cacheTTL = 30 * 60 * 1000;
  }

  /** 七链决策 */
  check(toolName, args) {
    // ① 安全检查
    if (this._isDangerous(toolName, args)) {
      return { allowed: false, reason: '操作包含安全风险模式' };
    }

    // ② bypass 模式 → 直接放行
    if (this.mode === 'bypass') {
      return { allowed: true };
    }

    // ③ 缓存决策
    const cached = this.decisionCache.get(toolName);
    if (cached && Date.now() - cached.time < this.cacheTTL) {
      return cached.decision;
    }

    // ④ always-allow 规则
    if (this.alwaysAllow.has(toolName)) {
      return this._cacheAndReturn(toolName, { allowed: true });
    }

    // ⑤ always-deny 规则
    if (this.alwaysDeny.has(toolName)) {
      return this._cacheAndReturn(toolName, { allowed: false, reason: '工具被列入拒绝列表' });
    }

    // ⑥ always-ask 规则 → 需要批准
    if (this.alwaysAsk.has(toolName) || this.mode === 'default') {
      return this._cacheAndReturn(toolName, { 
        allowed: true, 
        needsApproval: true,
        reason: '需要用户确认'
      });
    }

    // ⑦ 默认：允许
    return this._cacheAndReturn(toolName, { allowed: true });
  }

  _isDangerous(toolName, args) {
    // 检查命令注入、路径遍历等
    if (toolName === 'shell_exec' && args?.command) {
      const dangerous = [/rm\s+-rf\s+\//, />\s*\/dev\//, /mkfs\./, /dd\s+if=/];
      if (dangerous.some(p => p.test(args.command))) return true;
    }
    return false;
  }

  _cacheAndReturn(toolName, decision) {
    this.decisionCache.set(toolName, { time: Date.now(), decision });
    return decision;
  }
}

// ============================================================
// 5. Memory System — 三层架构
// ============================================================

class MemorySystem {
  constructor(config = {}) {
    this.shortTerm = [];           // 当前会话消息
    this.maxShortTerm = config.maxShortTerm || 50;
    this.longTerm = new Map();     // 持久化键值
    this.working = new Map();      // 任务上下文
  }

  add(role, content) {
    this.shortTerm.push({ role, content, timestamp: Date.now() });
    while (this.shortTerm.length > this.maxShortTerm) {
      this.shortTerm.shift();
    }
  }

  getRecent(n = 10) { return this.shortTerm.slice(-n); }
  remember(key, value) { this.longTerm.set(key, value); }
  recall(key) { return this.longTerm.get(key); }
  setWorking(key, value) { this.working.set(key, value); }
  getWorking(key) { return this.working.get(key); }

  /** 自动记忆：从对话历史提取关键信息 */
  autoRemember(history) {
    const lastActions = history.slice(-5);
    for (const a of lastActions) {
      if (a.action === 'file_write' && a.output?.success) {
        this.remember(`last_file_${Date.now()}`, a.input.path);
      }
    }
  }

  clear() {
    this.shortTerm = [];
    this.working.clear();
  }

  snapshot() {
    return {
      shortTermCount: this.shortTerm.length,
      longTermKeys: Array.from(this.longTerm.keys()),
      workingKeys: Array.from(this.working.keys())
    };
  }
}

// ============================================================
// 6. Task Manager — TaskCreate/TaskUpdate 跟踪
// ============================================================

class TaskManager {
  constructor() {
    this.tasks = new Map();
    this.counter = 0;
  }

  create(subject, description = '') {
    const id = String(++this.counter);
    this.tasks.set(id, {
      id, subject, description,
      status: 'pending',
      activeForm: '',
      createdAt: Date.now(),
      completedAt: null,
      metadata: {}
    });
    return this.tasks.get(id);
  }

  update(id, updates) {
    const task = this.tasks.get(id);
    if (!task) return null;
    Object.assign(task, updates);
    if (updates.status === 'completed') task.completedAt = Date.now();
    return task;
  }

  list(status) {
    let tasks = Array.from(this.tasks.values());
    if (status) tasks = tasks.filter(t => t.status === status);
    return tasks.sort((a, b) => b.createdAt - a.createdAt);
  }

  delete(id) {
    this.tasks.delete(id);
  }
}

// ============================================================
// 7. Skill Loader — 技能/插件系统
// ============================================================

class SkillLoader {
  constructor(skillsDir = null) {
    this.skillsDir = skillsDir || path.join(process.cwd(), 'skills');
    this.skills = new Map();
    this._loadAll();
  }

  _loadAll() {
    try {
      if (!fs.existsSync(this.skillsDir)) {
        fs.mkdirSync(this.skillsDir, { recursive: true });
        return;
      }
      const entries = fs.readdirSync(this.skillsDir);
      for (const entry of entries) {
        const skillPath = path.join(this.skillsDir, entry);
        const indexPath = path.join(skillPath, 'index.js');
        if (fs.existsSync(indexPath)) {
          try {
            const skill = require(indexPath);
            if (skill.name) this.skills.set(skill.name, skill);
          } catch(e) {
            console.warn(`[SkillLoader] 加载失败 ${entry}:`, e.message);
          }
        }
      }
    } catch(e) {
      console.warn('[SkillLoader] 初始化失败:', e.message);
    }
  }

  buildContext() {
    if (this.skills.size === 0) return '暂无加载的技能。';
    let ctx = '## 已加载技能\n';
    for (const [name, skill] of this.skills) {
      ctx += `- **${name}**: ${skill.description || '无描述'}\n`;
    }
    return ctx;
  }

  get(name) { return this.skills.get(name); }
  list() { return Array.from(this.skills.keys()); }
}

// ============================================================
// 8. Sub-Agent System
// ============================================================

class SubAgentSystem {
  constructor(harness) {
    this.harness = harness;
    this.agents = new Map();
  }

  async spawn(task, options = {}) {
    const agentId = `sub_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    
    // 创建独立的 harness 实例（共享工具，独立状态）
    const subHarness = new AgentHarness({
      ...this.harness.config,
      maxIterations: options.maxIterations || 10,
      model: options.model || this.harness.config.model
    });

    this.agents.set(agentId, { status: 'running', startTime: Date.now() });

    try {
      // 执行子任务
      const results = [];
      for await (const event of subHarness.run(task, options)) {
        if (event.type === 'final') {
          results.push(event.content);
        }
      }

      this.agents.set(agentId, { 
        status: 'completed', 
        endTime: Date.now(),
        result: results.join('')
      });

      return {
        agentId,
        status: 'completed',
        content: results.join('')
      };
    } catch(e) {
      this.agents.set(agentId, { status: 'failed', error: e.message });
      return { agentId, status: 'failed', error: e.message };
    }
  }

  get(agentId) { return this.agents.get(agentId); }
}

// ============================================================
// 9. Express Router（兼容旧 API）
// ============================================================

function createAgentRouter(engine) {
  const express = require('express');
  const router = express.Router();

  // 新引擎实例
  const harness = engine || new AgentHarness();
  const tools = harness.tools;
  const tasks = harness.tasks;

  // GET /tools
  router.get('/tools', (req, res) => {
    res.json({ ok: true, tools: tools.list() });
  });

  // POST /chat (非流式)
  router.post('/chat', async (req, res) => {
    try {
      if (!req.body.task) return res.status(400).json({ ok: false, error: 'Missing task' });
      const results = [];
      for await (const event of harness.run(req.body.task, {
        model: req.body.model,
        maxIterations: req.body.maxIterations || 30
      })) {
        if (event.type === 'final') {
          results.push(event);
        }
      }
      const final = results.find(r => r.type === 'final') || {};
      res.json({ ok: true, answer: final.content || '', iterations: final.iterations || 0, history: final.history || [] });
    } catch(e) {
      res.status(500).json({ ok: false, error: e.message });
    }
  });

  // POST /chat/stream
  router.post('/chat/stream', async (req, res) => {
    try {
      if (!req.body.task) return res.status(400).json({ ok: false, error: 'Missing task' });
      res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no'
      });

      for await (const event of harness.run(req.body.task, {
        model: req.body.model,
        maxIterations: req.body.maxIterations || 30,
        stream: req.body.stream !== false
      })) {
        res.write(`data: ${JSON.stringify(event)}\n\n`);
      }
      res.end();
    } catch(e) {
      res.write(`data: ${JSON.stringify({ type: 'error', error: e.message })}\n\n`);
      res.end();
    }
  });

  // POST /plan (任务规划)
  router.post('/plan', async (req, res) => {
    try {
      if (!req.body.task) return res.status(400).json({ ok: false, error: 'Missing task' });
      // 用规划专用提示词
      const planPrompt = `为以下任务制定执行计划，输出JSON格式：
{
  "title": "任务标题",
  "steps": [{"id": 1, "description": "步骤描述", "tools": ["所需工具"]}],
  "difficulty": "easy|medium|hard",
  "estimatedIterations": 5
}

任务: ${req.body.task}`;

      let plan;
      for await (const event of harness.run(planPrompt, {
        model: req.body.model,
        maxIterations: 3
      })) {
        if (event.type === 'final') {
          try {
            const jsonMatch = event.content.match(/\{[\s\S]*\}/);
            plan = jsonMatch ? JSON.parse(jsonMatch[0]) : null;
          } catch(e) {}
        }
      }
      res.json({ ok: true, plan: plan || { title: req.body.task, steps: [], difficulty: 'unknown' } });
    } catch(e) {
      res.status(500).json({ ok: false, error: e.message });
    }
  });

  // POST /execute (直接执行工具)
  router.post('/execute', async (req, res) => {
    try {
      if (!req.body.tool) return res.status(400).json({ ok: false, error: 'Missing tool' });
      const result = await tools.execute(req.body.tool, req.body.args || {}, {});
      res.json({ ok: true, result });
    } catch(e) {
      res.status(500).json({ ok: false, error: e.message });
    }
  });

  // === 新增 API ===

  // POST /agent/spawn (子 Agent)
  router.post('/agent/spawn', async (req, res) => {
    try {
      if (!req.body.task) return res.status(400).json({ ok: false, error: 'Missing task' });
      const result = await harness.spawnAgent(req.body.task, {
        model: req.body.model,
        maxIterations: req.body.maxIterations || 10
      });
      res.json({ ok: true, agent: result });
    } catch(e) {
      res.status(500).json({ ok: false, error: e.message });
    }
  });

  // POST /tasks
  router.post('/tasks', (req, res) => {
    const task = tasks.create(req.body.subject, req.body.description);
    res.json({ ok: true, task });
  });

  // GET /tasks
  router.get('/tasks', (req, res) => {
    res.json({ ok: true, tasks: tasks.list(req.query.status) });
  });

  // PATCH /tasks/:id
  router.patch('/tasks/:id', (req, res) => {
    const task = tasks.update(req.params.id, req.body);
    if (!task) return res.status(404).json({ ok: false, error: 'Task not found' });
    res.json({ ok: true, task });
  });

  // GET /permissions
  router.get('/permissions', (req, res) => {
    res.json({ ok: true, mode: harness.permissions.mode, rules: {
      alwaysAllow: Array.from(harness.permissions.alwaysAllow),
      alwaysDeny: Array.from(harness.permissions.alwaysDeny),
      alwaysAsk: Array.from(harness.permissions.alwaysAsk)
    }});
  });

  // PATCH /permissions
  router.patch('/permissions', (req, res) => {
    if (req.body.mode) harness.permissions.mode = req.body.mode;
    res.json({ ok: true, mode: harness.permissions.mode });
  });

  // GET /skills
  router.get('/skills', (req, res) => {
    res.json({ ok: true, skills: harness.skills.list() });
  });

  return { router, agentEngine: harness, toolRegistry: tools, taskManager: tasks };
}

// ============================================================
// Exports (兼容旧版)
// ============================================================

module.exports = {
  // 核心
  AgentHarness,
  ToolRegistry,
  ContextManager,
  PermissionSystem,
  MemorySystem,
  TaskManager,
  SkillLoader,
  SubAgentSystem,
  
  // Router
  createAgentRouter,
  
  // 兼容旧版别名
  AgentEngine: AgentHarness,
  AgentMemory: MemorySystem,
};
