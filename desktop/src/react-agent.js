const { toolRegistry } = require('./unified-tool-registry');

const SYSTEM_PROMPT = `你是 Y·NEX Desktop 的 AI 助手，是一个强大的全能创作 Agent。

## 你的能力
你可以调用各种工具来帮助用户完成任务，包括：
- 系统工具（天气、时间、文件操作等）
- 智能家居控制
- 邮件、日历、浏览器
- 代码执行（Python/Shell）
- 设备控制、自动化
- 知识库、记忆系统

## 工作方式（ReAct 模式）
当用户提出需求时，你需要：
1. **思考**：分析用户需求，判断是否需要调用工具
2. **行动**：如果需要工具，调用合适的工具
3. **观察**：获取工具执行结果
4. **回答**：基于工具结果给出最终回答

## 工具调用格式
当你需要调用工具时，严格使用以下格式：

\`\`\`
Action: tool_name
Input: {"arg1": "value1", "arg2": "value2"}
\`\`\`

## 回答格式
当你有了最终答案，直接用自然语言回答用户，不要包含 Action 格式。

## 重要规则
- 如果用户需求可以直接回答，不需要调用工具
- 如果需要信息才能回答，调用工具获取
- 一次只调用一个工具
- 调用工具时确保参数正确
- 危险操作（删除文件、执行命令等）需要先确认用户意图
`;

const MAX_ITERATIONS = 10;

class ReActAgent {
  constructor(options = {}) {
    this.model = options.model || 'deepseekv3';
    this.maxIterations = options.maxIterations || MAX_ITERATIONS;
    this.workspace = options.workspace || process.cwd();
    this.history = [];
    this.streamCallback = null;
  }

  async *run(userMessage, options = {}) {
    const model = options.model || this.model;
    const maxIterations = options.maxIterations || this.maxIterations;
    
    this.history = [
      { role: 'system', content: SYSTEM_PROMPT },
      { role: 'user', content: userMessage },
    ];

    yield { type: 'start', content: userMessage };

    for (let i = 0; i < maxIterations; i++) {
      yield { type: 'thinking', iteration: i + 1, max: maxIterations };

      try {
        const response = await this._callLLM(this.history, model);
        
        const parsed = this._parseAction(response);
        
        if (parsed.action) {
          yield {
            type: 'tool_call',
            tool: parsed.action,
            args: parsed.input,
            iteration: i + 1,
          };

          const toolResult = await this._callTool(parsed.action, parsed.input);
          
          yield {
            type: 'tool_result',
            tool: parsed.action,
            result: toolResult.ok ? toolResult.result : toolResult.error,
            ok: toolResult.ok,
            iteration: i + 1,
          };

          this.history.push({ role: 'assistant', content: response });
          this.history.push({
            role: 'user',
            content: toolResult.ok
              ? `工具执行结果：\n${JSON.stringify(toolResult.result)}`
              : `工具执行失败：\n${toolResult.error}`,
          });
        } else {
          yield {
            type: 'final',
            content: response,
            iterations: i + 1,
            history: this.history,
          };
          return;
        }
      } catch (e) {
        yield {
          type: 'error',
          error: e.message,
          iteration: i + 1,
        };
        return;
      }
    }

    yield {
      type: 'final',
      content: '抱歉，达到最大迭代次数，未能完成任务。请尝试简化需求。',
      iterations: maxIterations,
      history: this.history,
    };
  }

  async _callLLM(messages, model) {
    try {
      const fetch = globalThis.fetch || require('node-fetch');
      
      const tools = toolRegistry.list({ dangerous: false });
      const toolDescriptions = tools
        .slice(0, 30)
        .map(t => `- ${t.name.replace('yntex_', '')}: ${t.description}`)
        .join('\n');

      const systemMsg = messages.find(m => m.role === 'system');
      if (systemMsg) {
        systemMsg.content = SYSTEM_PROMPT + `\n\n## 当前可用工具\n${toolDescriptions}\n\n(注意：工具名请使用原始名称，不需要加yntex_前缀)`;
      }

      const resp = await fetch('http://127.0.0.1:7777/v1/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: model,
          messages: messages.map(m => ({ role: m.role, content: m.content })),
          stream: false,
          temperature: 0.7,
        }),
      });

      const data = await resp.json();
      if (data.choices && data.choices[0]) {
        return data.choices[0].message.content;
      }
      throw new Error(data.error?.message || 'LLM 调用失败');
    } catch (e) {
      console.error('[ReActAgent] LLM调用失败:', e.message);
      throw new Error(`AI 服务暂不可用: ${e.message}`);
    }
  }

  _parseAction(text) {
    const actionMatch = text.match(/Action:\s*([^\n]+)/i);
    const inputMatch = text.match(/Input:\s*(\{[\s\S]*?\})/i);
    
    if (actionMatch) {
      let actionName = actionMatch[1].trim();
      actionName = actionName.replace(/^yntex_/, '');
      
      let input = {};
      if (inputMatch) {
        try {
          input = JSON.parse(inputMatch[1].trim());
        } catch (e) {
          input = { input: inputMatch[1].trim() };
        }
      }
      
      return { action: actionName, input };
    }
    
    return { action: null, input: null };
  }

  async _callTool(name, args) {
    const toolNames = toolRegistry.list().map(t => t.displayName);
    let actualName = name;
    
    if (!toolNames.includes(name)) {
      const matched = toolNames.find(t => 
        t.toLowerCase().includes(name.toLowerCase()) ||
        name.toLowerCase().includes(t.toLowerCase())
      );
      if (matched) actualName = matched;
    }

    const toolKey = toolRegistry.list().find(t => t.displayName === actualName)?.name;
    
    if (!toolKey) {
      return { ok: false, error: `工具不存在: ${name}` };
    }

    return toolRegistry.callTool(toolKey, args, { workspace: this.workspace });
  }
}

module.exports = { ReActAgent };
