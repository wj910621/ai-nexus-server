/**
 * Y·NEX Agent Engine v1.0
 * 
 * 内置 Agent 引擎：ReAct 循环 + 工具系统 + 任务分解 + 记忆
 * 支持 MCP 风格�?tools 注册和调�? * 
 * 加载方式: server.js �?require('./agent-engine')
 */

// ============================================================
// 工具注册系统
// ============================================================

class ToolRegistry {
  constructor() {
    this.tools = new Map();
    this._registerBuiltins();
  }

  register(name, description, parameters, handler) {
    this.tools.set(name, {
      name,
      description,
      parameters,
      handler
    });
    return this;
  }

  get(name) {
    return this.tools.get(name);
  }

  list() {
    return Array.from(this.tools.values()).map(t => ({
      name: t.name,
      description: t.description,
      parameters: t.parameters
    }));
  }

  async execute(name, args, context = {}) {
    const tool = this.tools.get(name);
    if (!tool) throw new Error(`Tool '${name}' not found`);
    console.log(`[Agent Tool] ${name}(${JSON.stringify(args)})`);
    const result = await tool.handler(args, context);
    console.log(`[Agent Tool] ${name} �?${JSON.stringify(result).substring(0, 200)}`);
    return result;
  }

  _registerBuiltins() {
    // 1. Web Search
    this.register(
      'web_search',
      'Search the web for information. Returns search results with titles, snippets, and URLs.',
      {
        type: 'object',
        properties: {
          query: { type: 'string', description: 'The search query' },
          count: { type: 'number', description: 'Number of results (1-10)', default: 5 }
        },
        required: ['query']
      },
      async (args) => {
        const { query, count = 5 } = args;
        try {
          const url = `https://api.duckduckgo.com/?q=${encodeURIComponent(query)}&format=json&no_html=1`;
          const res = await fetch(url);
          const data = await res.json();
          const results = (data.RelatedTopics || []).slice(0, count).map(r => ({
            title: r.Text?.substring(0, 80) || r.FirstURL || 'Result',
            snippet: r.Text || '',
            url: r.FirstURL || ''
          }));
          return { success: true, results };
        } catch (e) {
          return { success: false, error: e.message };
        }
      }
    );

    // 2. Web Fetch
    this.register(
      'web_fetch',
      'Fetch and read the content of a web page. Returns the page text content.',
      {
        type: 'object',
        properties: {
          url: { type: 'string', description: 'The URL to fetch' }
        },
        required: ['url']
      },
      async (args) => {
        const { url } = args;
        try {
          const res = await fetch(url, { signal: AbortSignal.timeout(15000) });
          const text = await res.text();
          const stripped = text.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
          return { success: true, content: stripped.substring(0, 8000) };
        } catch (e) {
          return { success: false, error: e.message };
        }
      }
    );

    // 3. File Read (sandboxed)
    this.register(
      'file_read',
      'Read a file from the workspace. Path is relative to the workspace root.',
      {
        type: 'object',
        properties: {
          path: { type: 'string', description: 'File path relative to workspace' }
        },
        required: ['path']
      },
      async (args, context) => {
        const { path: filePath } = args;
        const workspace = context.workspace || process.cwd();
        const safePath = path.resolve(workspace, filePath);
        if (!safePath.startsWith(workspace)) {
          return { success: false, error: 'Path traversal denied' };
        }
        try {
          const content = fs.readFileSync(safePath, 'utf-8');
          return { success: true, content, size: content.length };
        } catch (e) {
          return { success: false, error: e.message };
        }
      }
    );

    // 4. File Write (sandboxed)
    this.register(
      'file_write',
      'Write content to a file in the workspace. Creates directories if needed.',
      {
        type: 'object',
        properties: {
          path: { type: 'string', description: 'File path relative to workspace' },
          content: { type: 'string', description: 'Content to write' }
        },
        required: ['path', 'content']
      },
      async (args, context) => {
        const { path: filePath, content } = args;
        const workspace = context.workspace || process.cwd();
        const safePath = path.resolve(workspace, filePath);
        if (!safePath.startsWith(workspace)) {
          return { success: false, error: 'Path traversal denied' };
        }
        try {
          fs.mkdirSync(path.dirname(safePath), { recursive: true });
          fs.writeFileSync(safePath, content, 'utf-8');
          return { success: true, path: filePath, size: content.length };
        } catch (e) {
          return { success: false, error: e.message };
        }
      }
    );

    // 5. Shell Execute (sandboxed, timeout 30s)
    this.register(
      'shell_exec',
      'Execute a shell command in the workspace. Returns stdout and stderr.',
      {
        type: 'object',
        properties: {
          command: { type: 'string', description: 'Shell command to execute' },
          timeout: { type: 'number', description: 'Timeout in seconds (max 30)', default: 10 }
        },
        required: ['command']
      },
      async (args, context) => {
        const { command, timeout = 10 } = args;
        const maxTimeout = Math.min(timeout, 30);
        const workspace = context.workspace || process.cwd();
        try {
          const { execFileSync } = require('child_process');
          const isWin = process.platform === 'win32';
          const shell = isWin ? 'cmd.exe' : '/bin/bash';
          const shellFlag = isWin ? '/c' : '-c';
          const result = execFileSync(shell, [shellFlag, command], {
            cwd: workspace,
            timeout: maxTimeout * 1000,
            maxBuffer: 1024 * 1024,
            encoding: 'utf-8'
          });
          return { success: true, stdout: result.substring(0, 10000), stderr: '' };
        } catch (e) {
          const stdout = e.stdout || '';
          const stderr = e.stderr || e.message;
          return { success: false, stdout: stdout.substring(0, 5000), stderr: stderr.substring(0, 5000) };
        }
      }
    );

    // 6. Calculator (math evaluation)
    this.register(
      'calculator',
      'Evaluate a mathematical expression. Supports +, -, *, /, **, sqrt, sin, cos, log.',
      {
        type: 'object',
        properties: {
          expression: { type: 'string', description: 'Math expression to evaluate' }
        },
        required: ['expression']
      },
      async (args) => {
        try {
          const safeEval = (expr) => {
            // Only allow safe math operations
            const allowed = /^[\d\s\+\-\*\/\(\)\.\,\^\%\s]+$/;
            if (!allowed.test(expr)) {
              // Try with math functions
              const mathAllowed = /^[\d\s\+\-\*\/\(\)\.\,\^\%\s]|Math\.|PI|E|sin|cos|tan|sqrt|log|abs|round|floor|ceil|pow/g;
              const cleaned = expr.replace(mathAllowed, '');
              if (cleaned.trim()) throw new Error('Unsafe expression');
            }
            const fn = new Function('return (' + expr + ')');
            return fn();
          };
          const result = safeEval(args.expression);
          return { success: true, result: Number(result) };
        } catch (e) {
          return { success: false, error: e.message };
        }
      }
    );
  }
}

/**
 * Phase 4 增强工具工厂函数
 * 注册知识库检索等工具�?ToolRegistry 实例
 */
function class AgentMemory {
  constructor(maxShortTerm = 20) {
    this.shortTerm = [];      // 最近对话历�?    this.maxShortTerm = maxShortTerm;
    this.longTerm = {};       // 持久化的关键信息
    this.workingMemory = {};  // 当前任务的工作状�?  }

  add(role, content) {
    this.shortTerm.push({ role, content, timestamp: Date.now() });
    if (this.shortTerm.length > this.maxShortTerm) {
      this.shortTerm.shift();
    }
  }

  getRecent(n = 10) {
    return this.shortTerm.slice(-n);
  }

  getAll() {
    return this.shortTerm;
  }

  remember(key, value) {
    this.longTerm[key] = value;
  }

  recall(key) {
    return this.longTerm[key];
  }

  setWorking(key, value) {
    this.workingMemory[key] = value;
  }

  getWorking(key) {
    return this.workingMemory[key];
  }

  clear() {
    this.shortTerm = [];
    this.workingMemory = {};
  }

  summarize() {
    return {
      shortTermCount: this.shortTerm.length,
      longTermKeys: Object.keys(this.longTerm),
      workingKeys: Object.keys(this.workingMemory)
    };
  }
}

// ============================================================
// LLM 调用包装
// ============================================================

const http = require('http');
const https = require('https');

function fetchSSE(url, options, onData) {
  return new Promise((resolve, reject) => {
    const urlObj = new URL(url);
    const mod = urlObj.protocol === 'https:' ? https : http;
    const req = mod.request(url, {
      method: options.method || 'POST',
      headers: options.headers || { 'Content-Type': 'application/json' },
      timeout: 120000
    }, (res) => {
      let buffer = '';
      res.on('data', (chunk) => {
        buffer += chunk.toString();
        // Process SSE
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim();
            if (data === '[DONE]') continue;
            try {
              const parsed = JSON.parse(data);
              if (onData) onData(parsed);
            } catch (e) {}
          }
        }
      });
      res.on('end', () => resolve());
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('Timeout')); });
    req.write(JSON.stringify(options.body || {}));
    req.end();
  });
}

// ============================================================
// Agent 循环引擎 (ReAct)
// ============================================================

class AgentEngine {
  constructor(options = {}) {
    this.tools = options.tools || new ToolRegistry();
    this.maxIterations = options.maxIterations || 15;
    this.model = options.model || 'deepseekv3';
    this.systemPrompt = options.systemPrompt || this._defaultSystemPrompt();
  }

  _defaultSystemPrompt() {
    return `你是 Y·NEX AI Agent，一个能够自主执行任务的智能助手�?
你可以使用以下工具来完成任务。每次需要工具时，请严格按照以下格式输出�?
思考：<分析当前状态，决定下一步行�?
行动�?工具名称>
输入�?JSON格式的工具参�?
观察�?工具返回的结�?
...（可以重复多次思考→行动→观察循环）
思考：<基于所有观察，总结答案>
最终回答：<你的最终答�?

如果你不需要使用工具，直接给出回答即可�?
可用工具列表将在每次请求时动态提供。始终使用中文与用户交流。`;
  }

  /**
   * 构建工具描述�?JSON 格式
   */
  _buildToolDescriptions() {
    return this.tools.list().map(t => ({
      type: 'function',
      function: {
        name: t.name,
        description: t.description,
        parameters: t.parameters
      }
    }));
  }

  /**
   * �?LLM 回复中提取工具调�?   * 支持两种格式�?   * 1. 结构化格式：行动：xxx + 输入：{...}
   * 2. JSON 格式：{"action": "xxx", "input": {...}}
   */
  _parseAction(response) {
    // Format 1: 行动：xxx\n输入：{...}
    const actionMatch = response.match(/行动[�?]\s*(\w+)/);
    const inputMatch = response.match(/输入[�?]\s*(\{[\s\S]*?\})/);
    if (actionMatch) {
      try {
        const input = inputMatch ? JSON.parse(inputMatch[1]) : {};
        return { action: actionMatch[1], input };
      } catch (e) {
        // 尝试非严�?JSON
        if (inputMatch) {
          try {
            const input = JSON.parse(inputMatch[1].replace(/'/g, '"').replace(/(\w+):/g, '"$1":'));
            return { action: actionMatch[1], input };
          } catch (e2) {}
        }
        return { action: actionMatch[1], input: {} };
      }
    }

    // Format 2: JSON block
    const jsonMatch = response.match(/\{[\s\S]*"action"[\s\S]*"input"[\s\S]*\}/);
    if (jsonMatch) {
      try {
        const parsed = JSON.parse(jsonMatch[0]);
        if (parsed.action && parsed.input !== undefined) {
          return { action: parsed.action, input: parsed.input };
        }
      } catch (e) {}
    }

    return null;
  }

  /**
   * 检查回复是否包含最终答�?   */
  _hasFinalAnswer(response) {
    return /最终回答[�?]/.test(response) || /Final Answer[�?]/.test(response);
  }

  /**
   * 提取最终答�?   */
  _extractFinalAnswer(response) {
    const match = response.match(/(?:最终回答|Final Answer)[�?]\s*([\s\S]*)/);
    if (match) return match[1].trim();
    return response;
  }

  /**
   * 调用 LLM
   */
  async _callLLM(messages, model) {
    const useModel = model || this.model;
    const apiKey = this._getApiKeyForModel(useModel);
    
    if (!apiKey) {
      return { content: '�?模型 API Key 未配�?, role: 'assistant' };
    }

    try {
      const response = await fetch('https://www.dmxapi.cn/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ' + apiKey
        },
        body: JSON.stringify({
          model: useModel,
          messages: messages,
          temperature: 0.7,
          max_tokens: 4096,
          stream: false
        }),
        signal: AbortSignal.timeout(60000)
      });

      if (!response.ok) {
        const errText = await response.text();
        return { content: `�?API Error (${response.status}): ${errText}`, role: 'assistant' };
      }

      const data = await response.json();
      return {
        content: data.choices?.[0]?.message?.content || 'No response',
        role: 'assistant'
      };
    } catch (e) {
      return { content: `�?调用失败: ${e.message}`, role: 'assistant' };
    }
  }

  _getApiKeyForModel(modelId) {
    // Reuse server.js logic - lookup env vars
    if (modelId.startsWith('dmx_')) return process.env.DMXAPI_API_KEY;
    if (modelId.startsWith('deepseek')) return process.env.DEEPSEEK_API_KEY;
    if (modelId.startsWith('sf_')) return process.env.SILICONFLOW_API_KEY;
    if (modelId.startsWith('nx_')) return process.env.NEXUS_API_KEY;
    return process.env.DMXAPI_API_KEY || process.env.OPENAI_API_KEY;
  }

  /**
   * 运行 Agent：ReAct 循环
   */
  async run(task, options = {}) {
    const {
      model = this.model,
      maxIterations = this.maxIterations,
      tools = this.tools,
      memory = new AgentMemory(),
      workspace = process.cwd(),
      streamCallback = null
    } = options;

    const toolDescriptions = this._buildToolDescriptions();
    const toolNames = tools.list().map(t => t.name).join(', ');
    const toolDocs = toolDescriptions.map(t =>
      `- ${t.function.name}: ${t.function.description}\n  参数: ${JSON.stringify(t.function.parameters)}`
    ).join('\n');

    const systemMessage = {
      role: 'system',
      content: `${this.systemPrompt}

【可用工具�?${toolDocs}

【使用规则�?1. 需要信息时，使用工具获�?2. 每次只能调用一个工�?3. 调用格式�?行动：工具名�?输入：{ "参数�?: "参数�? }
4. 完成任务后，输出�?最终回答：你的答案

【工具列表�?{toolNames}`
    };

    const messages = [systemMessage, { role: 'user', content: task }];
    const history = [];
    let finalAnswer = '';
    let iterationCount = 0;

    while (iterationCount < maxIterations) {
      iterationCount++;

      const response = await this._callLLM(messages, model);
      const content = response.content;

      if (response.content.startsWith('�?)) {
        finalAnswer = response.content;
        break;
      }

      // 检查是否有最终答�?      if (this._hasFinalAnswer(content)) {
        finalAnswer = this._extractFinalAnswer(content);
        if (streamCallback) streamCallback({ type: 'final', content: finalAnswer });
        break;
      }

      // 解析工具调用
      const parsedAction = this._parseAction(content);
      if (parsedAction) {
        const { action, input } = parsedAction;

        if (streamCallback) streamCallback({ type: 'thought', content, action, input });

        // 执行工具
        try {
          const toolResult = await tools.execute(action, input, { workspace });
          const observation = JSON.stringify(toolResult);
          const obsTruncated = observation.substring(0, 2000);

          // 添加到消息历�?          messages.push({ role: 'assistant', content });
          messages.push({ role: 'user', content: `观察�?{obsTruncated}\n\n请根据观察继续，或如果任务完成则输出"最终回答："。` });
          history.push({ action, input, result: toolResult });

          if (streamCallback) streamCallback({ type: 'observation', action, result: toolResult });
        } catch (e) {
          messages.push({ role: 'assistant', content });
          messages.push({ role: 'user', content: `工具执行错误�?{e.message}\n\n请尝试其他工具或方法。` });
        }
      } else {
        // 没有工具调用 �?这是纯文本回�?        finalAnswer = content;
        if (streamCallback) streamCallback({ type: 'final', content });
        break;
      }

      // 防止无限循环
      if (iterationCount >= maxIterations) {
        finalAnswer = '已达到最大迭代次数，任务可能未完全完成。\n\n' + content;
        if (streamCallback) streamCallback({ type: 'final', content: finalAnswer });
      }
    }

    return {
      answer: finalAnswer,
      iterations: iterationCount,
      history,
      memory: memory.summarize()
    };
  }

  /**
   * 任务分解�?   */
  async plan(task, options = {}) {
    const { model = this.model } = options;
    const planPrompt = `你是一个任务规划专家。请将以下任务分解为可执行的步骤�?
任务�?{task}

请输出一个结构化的计划，格式�?JSON�?{
  "title": "任务标题",
  "steps": [
    { "id": 1, "description": "步骤描述", "estimatedTools": ["可能用到的工具名"] }
  ],
  "estimatedDifficulty": "简�?中等/困难",
  "dependencies": [[1], [2], [3, 4], [5]]
}

注意：dependencies 数组的每个子数组表示一个阶段，同一阶段的任务可以并行执行。`;

    const response = await this._callLLM([
      { role: 'system', content: 'You are a task planning expert. Always respond in Chinese.' },
      { role: 'user', content: planPrompt }
    ], model);

    try {
      const jsonMatch = response.content.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        return JSON.parse(jsonMatch[0]);
      }
    } catch (e) {}

    return {
      title: task.substring(0, 50),
      steps: [{ id: 1, description: response.content, estimatedTools: [] }],
      estimatedDifficulty: '未知',
      dependencies: [[1]]
    };
  }
}

// ============================================================
// Express 路由生成�?// ============================================================

function createAgentRouter(engine) {
  // Lazy require express - let it be resolved from the parent app's context
  const express = require('express');
  const router = express.Router();
  const agentEngine = engine || new AgentEngine();
  const toolRegistry = agentEngine.tools;

  // GET /api/agent/tools �?列出所有工�?  router.get('/tools', (req, res) => {
    res.json({ ok: true, tools: toolRegistry.list() });
  });

  // POST /api/agent/chat �?Agent 对话（非流式�?  router.post('/chat', async (req, res) => {
    try {
      const { task, model, maxIterations, workspace } = req.body;
      if (!task) return res.status(400).json({ ok: false, error: 'Missing task' });

      const result = await agentEngine.run(task, {
        model: model || 'deepseekv3',
        maxIterations: maxIterations || 10,
        workspace: workspace || process.cwd()
      });

      res.json({ ok: true, ...result });
    } catch (e) {
      res.status(500).json({ ok: false, error: e.message });
    }
  });

  // POST /api/agent/chat/stream �?Agent 对话（SSE 流式�?  router.post('/chat/stream', async (req, res) => {
    const { task, model, maxIterations, workspace } = req.body;
    if (!task) return res.status(400).json({ ok: false, error: 'Missing task' });

    res.writeHead(200, {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive'
    });

    const sendSSE = (data) => {
      res.write(`data: ${JSON.stringify(data)}\n\n`);
    };

    sendSSE({ type: 'start', task });

    const result = await agentEngine.run(task, {
      model: model || 'deepseekv3',
      maxIterations: maxIterations || 10,
      workspace: workspace || process.cwd(),
      streamCallback: (event) => {
        sendSSE(event);
      }
    });

    sendSSE({ type: 'done', ...result });
    res.end();
  });

  // POST /api/agent/plan �?任务分解
  router.post('/plan', async (req, res) => {
    try {
      const { task, model } = req.body;
      if (!task) return res.status(400).json({ ok: false, error: 'Missing task' });

      const plan = await agentEngine.plan(task, { model });
      res.json({ ok: true, plan });
    } catch (e) {
      res.status(500).json({ ok: false, error: e.message });
    }
  });

  // POST /api/agent/execute �?一次性工具执�?  router.post('/execute', async (req, res) => {
    try {
      const { tool, args, workspace } = req.body;
      if (!tool) return res.status(400).json({ ok: false, error: 'Missing tool name' });

      const result = await toolRegistry.execute(tool, args || {}, { workspace: workspace || process.cwd() });
      res.json({ ok: true, result });
    } catch (e) {
      res.status(500).json({ ok: false, error: e.message });
    }
  });

  return { router, agentEngine, toolRegistry };
}

// ============================================================
// 导出
// ============================================================

module.exports = {
  ToolRegistry,
  AgentMemory,
  AgentEngine,
  createAgentRouter,
  registerPhase4Tools
};

