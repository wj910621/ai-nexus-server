/**
 * Y·NEX Agent Harness - Agent 执行回路核心
 * 基于 he-wiki-rag Harness 模块设计
 * 完整的 Agent + Tool 工程化样板
 */
'use strict';

// ============================================================
// 一、Harness 配置
// ============================================================
const HARNESS_CONFIG = {
    // Agent 配置
    agent: {
        maxIterations: 50,         // 最大迭代次数
        timeoutSeconds: 300,       // 超时时间
        maxToolCalls: 100,         // 最大工具调用次数
    },
    
    // 上下文配置
    context: {
        maxTokens: 8000,           // 最大 token 数
        compressionThreshold: 6000, // 压缩阈值
        preserveSystem: true,      // 保留系统提示
    },
    
    // 工具配置
    tools: {
        allowedTools: [],          // 允许的工具（空=全部）
        deniedTools: [],           // 禁止的工具
        maxConcurrent: 3,          // 最大并发工具数
    },
    
    // 状态配置
    state: {
        autoSave: true,
        saveInterval: 5000,        // 保存间隔
        maxHistory: 100,           // 最大历史记录
    },
    
    // Trace 配置
    trace: {
        enabled: true,
        captureLLM: true,
        captureTools: true,
        captureState: true,
    }
};

// ============================================================
// 二、Agent Harness 核心
// ============================================================
class AgentHarness {
    constructor(options = {}) {
        this.config = { ...HARNESS_CONFIG, ...options };
        
        // 核心组件
        this.agentLoop = null;
        this.toolRegistry = new Map();
        this.stateStore = null;
        this.tracer = null;
        this.contextCompressor = null;
        
        // 当前会话
        this.currentSession = null;
        
        // 初始化内置工具
        this.registerBuiltinTools();
    }

    // ------------------------------------------------
    // 2.1 初始化
    // ------------------------------------------------
    
    /**
     * 初始化 Harness
     */
    async initialize(options = {}) {
        if (options.contextCompressor) {
            this.contextCompressor = options.contextCompressor;
        }
        
        if (options.stateStore) {
            this.stateStore = options.stateStore;
        }
        
        if (options.tracer) {
            this.tracer = options.tracer;
        }
        
        // 初始化 Agent Loop
        this.agentLoop = new AgentLoop(this.config.agent);
        
        return this;
    }

    /**
     * 注册内置工具
     */
    registerBuiltinTools() {
        // 知识检索工具
        this.registerTool({
            name: 'knowledge_search',
            description: '搜索知识库相关内容',
            parameters: {
                query: { type: 'string', required: true },
                topK: { type: 'number', default: 5 },
            },
            handler: async (params) => {
                if (typeof ragEngine !== 'undefined') {
                    const results = await ragEngine.search(params.query, { topK: params.topK });
                    return results;
                }
                return { error: 'RAG engine not available' };
            }
        });

        // 章节导航工具
        this.registerTool({
            name: 'chapter_index',
            description: '获取文档章节结构',
            parameters: {
                docId: { type: 'string', required: true },
            },
            handler: async (params) => {
                if (typeof wikiKnowledgeBase !== 'undefined') {
                    const doc = wikiKnowledgeBase.getDocument(params.docId);
                    return doc?.sections || [];
                }
                return { error: 'Wiki knowledge base not available' };
            }
        });

        // 状态检查点工具
        this.registerTool({
            name: 'state_checkpoint',
            description: '保存当前状态快照',
            parameters: {
                label: { type: 'string', required: false },
            },
            handler: async (params) => {
                if (this.stateStore) {
                    const checkpoint = await this.stateStore.createCheckpoint(params.label);
                    return checkpoint;
                }
                return { error: 'State store not available' };
            }
        });

        // Trace 回放工具
        this.registerTool({
            name: 'trace_replay',
            description: '回放之前的执行记录',
            parameters: {
                traceId: { type: 'string', required: true },
            },
            handler: async (params) => {
                if (this.tracer) {
                    return await this.tracer.replay(params.traceId, this);
                }
                return { error: 'Tracer not available' };
            }
        });
    }

    /**
     * 注册工具
     */
    registerTool(tool) {
        this.toolRegistry.set(tool.name, tool);
    }

    /**
     * 移除工具
     */
    unregisterTool(name) {
        this.toolRegistry.delete(name);
    }

    // ------------------------------------------------
    // 2.2 执行任务
    // ------------------------------------------------
    
    /**
     * 运行任务
     */
    async run(task, context = {}) {
        const sessionId = this.generateSessionId();
        
        // 创建会话
        this.currentSession = {
            id: sessionId,
            task,
            context,
            startTime: Date.now(),
            messages: [],
            toolCalls: [],
            state: {},
            checkpoints: [],
        };
        
        // 开始 Trace
        if (this.config.trace.enabled && this.tracer) {
            this.tracer.recordStart(sessionId, {
                task,
                context,
                config: this.config,
            });
        }
        
        try {
            // 初始化 Agent Loop
            await this.agentLoop.initialize({
                task,
                context,
                tools: this.getAvailableTools(),
                harness: this,
            });
            
            // 主循环
            let iteration = 0;
            let lastResult = null;
            
            while (iteration < this.config.agent.maxIterations) {
                // 检查超时
                if (this.checkTimeout()) {
                    throw new Error('Task timeout exceeded');
                }
                
                // Agent Loop 单步执行
                const stepResult = await this.agentLoop.step();
                
                if (stepResult.done) {
                    lastResult = stepResult.result;
                    break;
                }
                
                // 如果有工具调用
                if (stepResult.toolCalls?.length > 0) {
                    for (const toolCall of stepResult.toolCalls) {
                        await this.executeToolCall(toolCall);
                    }
                }
                
                iteration++;
            }
            
            // 结束 Trace
            if (this.config.trace.enabled && this.tracer) {
                this.tracer.recordEnd(sessionId, {
                    result: lastResult,
                    iterations: iteration,
                    toolCalls: this.currentSession.toolCalls.length,
                });
            }
            
            return {
                success: true,
                result: lastResult,
                sessionId,
                stats: {
                    iterations: iteration,
                    toolCalls: this.currentSession.toolCalls.length,
                    duration: Date.now() - this.currentSession.startTime,
                }
            };
            
        } catch (error) {
            // 记录错误
            if (this.config.trace.enabled && this.tracer) {
                this.tracer.recordError(sessionId, error);
            }
            
            return {
                success: false,
                error: error.message,
                sessionId,
                stats: {
                    iterations: iteration,
                    toolCalls: this.currentSession.toolCalls.length,
                    duration: Date.now() - this.currentSession.startTime,
                }
            };
        }
    }

    /**
     * 执行工具调用
     */
    async executeToolCall(toolCall) {
        const { id, name, arguments: args } = toolCall;
        
        // 检查工具是否允许
        if (!this.isToolAllowed(name)) {
            return {
                id,
                error: `Tool '${name}' is not allowed`,
            };
        }
        
        // 获取工具
        const tool = this.toolRegistry.get(name);
        if (!tool) {
            return {
                id,
                error: `Tool '${name}' not found`,
            };
        }
        
        // 记录工具调用
        this.currentSession.toolCalls.push({
            id,
            name,
            args,
            startTime: Date.now(),
        });
        
        // Trace 工具调用
        if (this.config.trace.enabled && this.tracer) {
            this.tracer.recordToolCall(this.currentSession.id, {
                id,
                name,
                args,
            });
        }
        
        try {
            // 执行工具
            const result = await tool.handler(args, this);
            
            // 记录结果
            const toolResult = {
                id,
                success: true,
                result,
                duration: Date.now() - this.currentSession.toolCalls.slice(-1)[0].startTime,
            };
            
            // 添加到消息
            this.currentSession.messages.push({
                role: 'tool',
                toolCallId: id,
                content: JSON.stringify(result),
            });
            
            // 返回结果给 Agent Loop
            this.agentLoop.addToolResult(id, result);
            
            return toolResult;
            
        } catch (error) {
            return {
                id,
                success: false,
                error: error.message,
            };
        }
    }

    // ------------------------------------------------
    // 2.3 工具管理
    // ------------------------------------------------
    
    /**
     * 获取可用工具列表
     */
    getAvailableTools() {
        const tools = [];
        
        for (const [name, tool] of this.toolRegistry) {
            if (this.isToolAllowed(name)) {
                tools.push({
                    name,
                    description: tool.description,
                    parameters: tool.parameters,
                });
            }
        }
        
        return tools;
    }

    /**
     * 检查工具是否允许执行
     */
    isToolAllowed(name) {
        // 检查禁止列表
        if (this.config.tools.deniedTools.includes(name)) {
            return false;
        }
        
        // 检查允许列表（如果配置了）
        if (this.config.tools.allowedTools.length > 0) {
            return this.config.tools.allowedTools.includes(name);
        }
        
        return true;
    }

    // ------------------------------------------------
    // 2.4 上下文管理
    // ------------------------------------------------
    
    /**
     * 压缩上下文
     */
    compressContext(messages) {
        if (!this.contextCompressor) {
            return messages;
        }
        
        const totalTokens = this.estimateTokens(messages);
        
        if (totalTokens > this.config.context.compressionThreshold) {
            return this.contextCompressor.compress(messages, {
                maxTokens: this.config.context.maxTokens,
                preserveSystem: this.config.context.preserveSystem,
            });
        }
        
        return messages;
    }

    /**
     * 估算 token 数（简化）
     */
    estimateTokens(messages) {
        let total = 0;
        for (const msg of messages) {
            total += (msg.content || '').length / 4;
        }
        return Math.ceil(total);
    }

    // ------------------------------------------------
    // 2.5 状态管理
    // ------------------------------------------------
    
    /**
     * 保存状态
     */
    async saveState() {
        if (this.stateStore && this.currentSession) {
            await this.stateStore.saveSession(
                this.currentSession.id,
                this.currentSession.messages,
                this.currentSession.state
            );
        }
    }

    /**
     * 加载状态
     */
    async loadState(sessionId) {
        if (this.stateStore) {
            const session = await this.stateStore.loadSession(sessionId);
            if (session) {
                this.currentSession = session;
                return session;
            }
        }
        return null;
    }

    // ------------------------------------------------
    // 2.6 超时检查
    // ------------------------------------------------
    
    checkTimeout() {
        if (!this.currentSession) return false;
        
        const elapsed = Date.now() - this.currentSession.startTime;
        return elapsed > this.config.agent.timeoutSeconds * 1000;
    }

    // ------------------------------------------------
    // 2.7 工具函数
    // ------------------------------------------------
    
    generateSessionId() {
        return 'session_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 8);
    }

    /**
     * 获取统计信息
     */
    getStats() {
        return {
            totalSessions: this.currentSession ? 1 : 0,
            registeredTools: this.toolRegistry.size,
            availableTools: this.getAvailableTools().length,
        };
    }

    /**
     * 销毁 Harness
     */
    destroy() {
        this.agentLoop = null;
        this.toolRegistry.clear();
        this.currentSession = null;
    }
}

// ============================================================
// 三、Agent Loop（执行回路）
// ============================================================
class AgentLoop {
    constructor(config = {}) {
        this.config = config;
        this.task = null;
        this.context = null;
        this.tools = [];
        this.messages = [];
        this.pendingToolCalls = [];
        this.iteration = 0;
    }

    async initialize(options) {
        this.task = options.task;
        this.context = options.context;
        this.tools = options.tools || [];
        
        // 添加系统消息
        this.messages.push({
            role: 'system',
            content: this.buildSystemPrompt(),
        });
        
        // 添加任务消息
        this.messages.push({
            role: 'user',
            content: this.task,
        });
    }

    buildSystemPrompt() {
        return `【Agent 执行规范】
- 你是 Agent 执行回路的核心决策单元
- 分析任务，选择工具，生成响应
- 每个迭代最多执行 ${this.config.maxIterations} 次
- 工具调用结果会自动注入到上下文中`;
    }

    /**
     * 单步执行
     */
    async step() {
        this.iteration++;
        
        // 压缩上下文（如果需要）
        if (this.messages.length > 20) {
            this.messages = this.compressMessages(this.messages);
        }
        
        // 调用 LLM
        const llmResponse = await this.callLLM(this.messages);
        
        // 解析响应
        if (llmResponse.toolCalls?.length > 0) {
            // 有工具调用
            this.pendingToolCalls = llmResponse.toolCalls;
            
            // 添加助手消息
            this.messages.push({
                role: 'assistant',
                content: llmResponse.content,
                toolCalls: llmResponse.toolCalls,
            });
            
            return {
                done: false,
                toolCalls: llmResponse.toolCalls,
            };
        } else {
            // 直接响应
            return {
                done: true,
                result: llmResponse.content,
            };
        }
    }

    /**
     * 调用 LLM
     */
    async callLLM(messages) {
        // 这里应该调用实际的 LLM API
        // 简化实现
        return {
            content: 'Task completed',
            toolCalls: [],
        };
    }

    /**
     * 添加工具结果
     */
    addToolResult(toolCallId, result) {
        this.messages.push({
            role: 'tool',
            toolCallId,
            content: JSON.stringify(result),
        });
    }

    /**
     * 压缩消息
     */
    compressMessages(messages) {
        // 保留系统消息和最近的消息
        const systemMsg = messages.find(m => m.role === 'system');
        const recentMsgs = messages.slice(-10);
        
        return [
            ...(systemMsg ? [systemMsg] : []),
            {
                role: 'system',
                content: '[上下文已压缩]',
            },
            ...recentMsgs,
        ];
    }
}

// ============================================================
// 四、全局实例
// ============================================================
const agentHarness = new AgentHarness();

// ============================================================
// 五、导出
// ============================================================
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { AgentHarness, AgentLoop, agentHarness, HARNESS_CONFIG };
}
