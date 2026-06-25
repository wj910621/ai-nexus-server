/**
 * TriGen Trace & Replay 系统
 * 基于 he-wiki-rag Tracer 模块设计
 * 支持执行记录、追踪、回放、审计
 */
'use strict';

// ============================================================
// 一、Trace 配置
// ============================================================
const TRACE_CONFIG = {
    // 存储配置
    storage: {
        type: 'indexeddb',     // indexeddb / localstorage / memory
        dbName: 'trigen_traces',
        storeName: 'traces',
        maxTraces: 1000,       // 最大保存 trace 数
        maxSizeMB: 100,        // 最大存储大小
    },
    
    // 捕获配置
    capture: {
        llm: true,            // 捕获 LLM 输入输出
        tools: true,          // 捕获工具调用
        state: true,          // 捕获状态变更
        errors: true,         // 捕获错误
        performance: true,    // 捕获性能数据
    },
    
    // 保留策略
    retention: {
        keepErrors: true,     // 始终保留错误 trace
        keepSuccess: 7,       // 成功 trace 保留天数
        maxAge: 30,          // 最大保留天数
    },
};

// ============================================================
// 二、Trace 记录器
// ============================================================
class Tracer {
    constructor(options = {}) {
        this.config = { ...TRACE_CONFIG, ...options };
        this.traces = new Map();         // 内存中的 trace
        this.currentTrace = null;        // 当前 trace
        this.storage = null;            // 存储实例
        
        // 性能追踪
        this.performanceMarks = new Map();
        
        // 初始化存储
        this.initStorage();
    }

    // ------------------------------------------------
    // 2.1 存储初始化
    // ------------------------------------------------
    
    async initStorage() {
        if (this.config.storage.type === 'indexeddb') {
            this.storage = new IndexedDBStorage(this.config.storage);
            await this.storage.init();
        }
    }

    // ------------------------------------------------
    // 2.2 Trace 管理
    // ------------------------------------------------
    
    /**
     * 开始记录 Trace
     */
    recordStart(sessionId, metadata = {}) {
        this.currentTrace = {
            id: sessionId,
            metadata,
            startTime: Date.now(),
            endTime: null,
            duration: null,
            status: 'running',
            
            // 事件记录
            events: [],
            
            // LLM 记录
            llmCalls: [],
            
            // 工具调用记录
            toolCalls: [],
            
            // 状态变更记录
            stateChanges: [],
            
            // 错误记录
            errors: [],
            
            // 性能记录
            performance: {
                marks: [],
                measures: [],
            },
            
            // 统计
            stats: {
                totalLLMCalls: 0,
                totalToolCalls: 0,
                totalTokens: 0,
                inputTokens: 0,
                outputTokens: 0,
            },
        };
        
        // 性能标记
        this.performanceMarks.set(sessionId, Date.now());
        
        this.traces.set(sessionId, this.currentTrace);
        
        this.addEvent('trace_start', { sessionId });
        
        return this.currentTrace;
    }

    /**
     * 结束记录 Trace
     */
    recordEnd(sessionId, result = {}) {
        const trace = this.traces.get(sessionId);
        if (!trace) return null;
        
        trace.endTime = Date.now();
        trace.duration = trace.endTime - trace.startTime;
        trace.status = 'completed';
        trace.result = result;
        
        // 计算性能
        trace.performance.totalDuration = trace.duration;
        trace.performance.avgLLMLatency = trace.stats.totalLLMCalls > 0
            ? trace.llmCalls.reduce((sum, c) => sum + c.duration, 0) / trace.stats.totalLLMCalls
            : 0;
        trace.performance.avgToolLatency = trace.stats.totalToolCalls > 0
            ? trace.toolCalls.reduce((sum, c) => sum + c.duration, 0) / trace.stats.totalToolCalls
            : 0;
        
        // 添加事件
        this.addEvent('trace_end', {
            duration: trace.duration,
            status: trace.status,
        });
        
        // 持久化
        this.persistTrace(trace);
        
        // 清理当前 trace
        if (this.currentTrace?.id === sessionId) {
            this.currentTrace = null;
        }
        
        return trace;
    }

    /**
     * 记录错误
     */
    recordError(sessionId, error) {
        const trace = this.traces.get(sessionId);
        if (!trace) return null;
        
        const errorRecord = {
            id: 'err_' + Date.now().toString(36),
            timestamp: Date.now(),
            message: error.message || String(error),
            stack: error.stack,
            type: error.name || 'Error',
        };
        
        trace.errors.push(errorRecord);
        trace.status = 'failed';
        
        this.addEvent('error', errorRecord);
        
        // 始终保留错误 trace
        this.persistTrace(trace);
        
        return errorRecord;
    }

    /**
     * 添加事件
     */
    addEvent(type, data = {}) {
        if (!this.currentTrace) return;
        
        this.currentTrace.events.push({
            id: 'evt_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 5),
            type,
            timestamp: Date.now(),
            data,
        });
    }

    // ------------------------------------------------
    // 2.3 LLM 调用记录
    // ------------------------------------------------
    
    /**
     * 记录 LLM 调用
     */
    recordLLMCall(sessionId, callData) {
        const trace = this.traces.get(sessionId);
        if (!trace || !this.config.capture.llm) return;
        
        const startTime = Date.now();
        
        const llmCall = {
            id: 'llm_' + Date.now().toString(36),
            timestamp: startTime,
            model: callData.model || 'unknown',
            
            // 输入
            input: {
                messages: callData.messages,
                temperature: callData.temperature,
                maxTokens: callData.maxTokens,
            },
            
            // 输出
            output: callData.output || null,
            
            // Token 统计
            tokens: {
                prompt: callData.promptTokens || 0,
                completion: callData.completionTokens || 0,
                total: (callData.promptTokens || 0) + (callData.completionTokens || 0),
            },
            
            // 性能
            duration: 0,
            status: 'pending',
        };
        
        trace.llmCalls.push(llmCall);
        trace.stats.totalLLMCalls++;
        trace.stats.inputTokens += llmCall.tokens.prompt;
        trace.stats.outputTokens += llmCall.tokens.completion;
        trace.stats.totalTokens += llmCall.tokens.total;
        
        return llmCall;
    }

    /**
     * 完成 LLM 调用
     */
    completeLLMCall(sessionId, llmCallId, output) {
        const trace = this.traces.get(sessionId);
        if (!trace) return;
        
        const llmCall = trace.llmCalls.find(c => c.id === llmCallId);
        if (llmCall) {
            llmCall.output = output;
            llmCall.duration = Date.now() - llmCall.timestamp;
            llmCall.status = 'completed';
        }
    }

    /**
     * 失败 LLM 调用
     */
    failLLMCall(sessionId, llmCallId, error) {
        const trace = this.traces.get(sessionId);
        if (!trace) return;
        
        const llmCall = trace.llmCalls.find(c => c.id === llmCallId);
        if (llmCall) {
            llmCall.duration = Date.now() - llmCall.timestamp;
            llmCall.status = 'failed';
            llmCall.error = error.message || String(error);
        }
    }

    // ------------------------------------------------
    // 2.4 工具调用记录
    // ------------------------------------------------
    
    /**
     * 记录工具调用
     */
    recordToolCall(sessionId, callData) {
        const trace = this.traces.get(sessionId);
        if (!trace || !this.config.capture.tools) return;
        
        const startTime = Date.now();
        
        const toolCall = {
            id: callData.id,
            name: callData.name,
            arguments: callData.args,
            timestamp: startTime,
            status: 'running',
            result: null,
            error: null,
            duration: 0,
        };
        
        trace.toolCalls.push(toolCall);
        trace.stats.totalToolCalls++;
        
        this.addEvent('tool_call_start', {
            toolId: callData.id,
            toolName: callData.name,
        });
        
        return toolCall;
    }

    /**
     * 完成工具调用
     */
    completeToolCall(sessionId, toolCallId, result) {
        const trace = this.traces.get(sessionId);
        if (!trace) return;
        
        const toolCall = trace.toolCalls.find(c => c.id === toolCallId);
        if (toolCall) {
            toolCall.result = result;
            toolCall.duration = Date.now() - toolCall.timestamp;
            toolCall.status = 'completed';
            
            this.addEvent('tool_call_end', {
                toolId: toolCallId,
                toolName: toolCall.name,
                duration: toolCall.duration,
            });
        }
    }

    /**
     * 失败工具调用
     */
    failToolCall(sessionId, toolCallId, error) {
        const trace = this.traces.get(sessionId);
        if (!trace) return;
        
        const toolCall = trace.toolCalls.find(c => c.id === toolCallId);
        if (toolCall) {
            toolCall.error = error.message || String(error);
            toolCall.duration = Date.now() - toolCall.timestamp;
            toolCall.status = 'failed';
            
            this.addEvent('tool_call_error', {
                toolId: toolCallId,
                toolName: toolCall.name,
                error: toolCall.error,
            });
        }
    }

    // ------------------------------------------------
    // 2.5 状态变更记录
    // ------------------------------------------------
    
    /**
     * 记录状态变更
     */
    recordStateChange(sessionId, changeData) {
        const trace = this.traces.get(sessionId);
        if (!trace || !this.config.capture.state) return;
        
        const stateChange = {
            id: 'state_' + Date.now().toString(36),
            timestamp: Date.now(),
            key: changeData.key,
            oldValue: changeData.oldValue,
            newValue: changeData.newValue,
            reason: changeData.reason,
        };
        
        trace.stateChanges.push(stateChange);
        
        this.addEvent('state_change', stateChange);
        
        return stateChange;
    }

    // ------------------------------------------------
    // 2.6 性能追踪
    // ------------------------------------------------
    
    /**
     * 性能标记
     */
    mark(name) {
        this.performanceMarks.set(name, Date.now());
    }

    /**
     * 性能测量
     */
    measure(name, startMark, endMark) {
        const startTime = this.performanceMarks.get(startMark) || Date.now();
        const endTime = this.performanceMarks.get(endMark) || Date.now();
        
        const measure = {
            name,
            startTime,
            endTime,
            duration: endTime - startTime,
        };
        
        if (this.currentTrace) {
            this.currentTrace.performance.measures.push(measure);
        }
        
        return measure;
    }

    // ------------------------------------------------
    // 2.7 查询与回放
    // ------------------------------------------------
    
    /**
     * 获取 Trace
     */
    getTrace(sessionId) {
        return this.traces.get(sessionId) || null;
    }

    /**
     * 查询 Trace
     */
    async queryTraces(filter = {}) {
        const results = [];
        
        for (const [id, trace] of this.traces) {
            // 状态过滤
            if (filter.status && trace.status !== filter.status) continue;
            
            // 时间范围过滤
            if (filter.startTime && trace.startTime < filter.startTime) continue;
            if (filter.endTime && trace.startTime > filter.endTime) continue;
            
            // 错误过滤
            if (filter.hasErrors && trace.errors.length === 0) continue;
            
            results.push(trace);
        }
        
        // 按时间排序
        results.sort((a, b) => b.startTime - a.startTime);
        
        // 分页
        if (filter.limit) {
            return results.slice(0, filter.limit);
        }
        
        return results;
    }

    /**
     * 回放 Trace
     */
    async replay(traceId, harness) {
        const trace = await this.getTrace(traceId);
        if (!trace) {
            return { error: 'Trace not found' };
        }
        
        const replayResult = {
            traceId,
            originalDuration: trace.duration,
            replayDuration: 0,
            steps: [],
            matches: [],
        };
        
        const startTime = Date.now();
        
        // 回放 LLM 调用
        for (const llmCall of trace.llmCalls) {
            // 实际调用 LLM
            const result = await harness.callLLM(llmCall.input.messages);
            
            replayResult.steps.push({
                type: 'llm_call',
                original: llmCall,
                replayed: result,
                match: result === llmCall.output,
            });
        }
        
        // 回放工具调用
        for (const toolCall of trace.toolCalls) {
            const result = await harness.executeToolCall({
                id: toolCall.id,
                name: toolCall.name,
                arguments: toolCall.arguments,
            });
            
            replayResult.steps.push({
                type: 'tool_call',
                original: toolCall,
                replayed: result,
                match: JSON.stringify(result) === JSON.stringify(toolCall.result),
            });
        }
        
        replayResult.replayDuration = Date.now() - startTime;
        
        // 计算匹配率
        const matches = replayResult.steps.filter(s => s.match);
        replayResult.matchRate = replayResult.steps.length > 0
            ? matches.length / replayResult.steps.length
            : 0;
        
        return replayResult;
    }

    /**
     * 导出 Trace
     */
    exportTrace(sessionId, format = 'json') {
        const trace = this.traces.get(sessionId);
        if (!trace) return null;
        
        if (format === 'json') {
            return JSON.stringify(trace, null, 2);
        }
        
        return trace;
    }

    // ------------------------------------------------
    // 2.8 存储管理
    // ------------------------------------------------
    
    /**
     * 持久化 Trace
     */
    async persistTrace(trace) {
        if (this.storage) {
            await this.storage.save(trace.id, trace);
        }
    }

    /**
     * 清理过期 Trace
     */
    async cleanup() {
        const now = Date.now();
        const maxAge = this.config.retention.maxAge * 24 * 60 * 60 * 1000;
        
        for (const [id, trace] of this.traces) {
            // 保留错误 trace
            if (this.config.retention.keepErrors && trace.errors.length > 0) {
                continue;
            }
            
            // 检查年龄
            if (now - trace.startTime > maxAge) {
                this.traces.delete(id);
                if (this.storage) {
                    await this.storage.delete(id);
                }
            }
        }
    }

    // ------------------------------------------------
    // 2.9 统计与报告
    // ------------------------------------------------
    
    /**
     * 获取统计信息
     */
    getStats() {
        const stats = {
            totalTraces: this.traces.size,
            byStatus: {
                running: 0,
                completed: 0,
                failed: 0,
            },
            totalLLMCalls: 0,
            totalToolCalls: 0,
            totalTokens: 0,
            avgDuration: 0,
            errorRate: 0,
        };
        
        let totalDuration = 0;
        let errors = 0;
        
        for (const [, trace] of this.traces) {
            stats.byStatus[trace.status]++;
            stats.totalLLMCalls += trace.stats.totalLLMCalls;
            stats.totalToolCalls += trace.stats.totalToolCalls;
            stats.totalTokens += trace.stats.totalTokens;
            
            if (trace.duration) {
                totalDuration += trace.duration;
            }
            if (trace.errors.length > 0) {
                errors++;
            }
        }
        
        if (this.traces.size > 0) {
            stats.avgDuration = totalDuration / this.traces.size;
            stats.errorRate = errors / this.traces.size;
        }
        
        return stats;
    }
}

// ============================================================
// 三、IndexedDB 存储
// ============================================================
class IndexedDBStorage {
    constructor(config) {
        this.config = config;
        this.db = null;
    }

    async init() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.config.dbName, 1);
            
            request.onerror = () => reject(request.error);
            request.onsuccess = () => {
                this.db = request.result;
                resolve();
            };
            
            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                if (!db.objectStoreNames.contains(this.config.storeName)) {
                    db.createObjectStore(this.config.storeName, { keyPath: 'id' });
                }
            };
        });
    }

    async save(id, data) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([this.config.storeName], 'readwrite');
            const store = transaction.objectStore(this.config.storeName);
            const request = store.put({ id, ...data });
            
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }

    async get(id) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([this.config.storeName], 'readonly');
            const store = transaction.objectStore(this.config.storeName);
            const request = store.get(id);
            
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    async delete(id) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([this.config.storeName], 'readwrite');
            const store = transaction.objectStore(this.config.storeName);
            const request = store.delete(id);
            
            request.onsuccess = () => resolve();
            request.onerror = () => reject(request.error);
        });
    }
}

// ============================================================
// 四、全局实例
// ============================================================
const tracer = new Tracer();

// ============================================================
// 五、导出
// ============================================================
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { Tracer, IndexedDBStorage, tracer, TRACE_CONFIG };
}
