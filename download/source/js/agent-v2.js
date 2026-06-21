/* ========================================
   Agent v2 前端 — Harness Engineering 前端编排
   基于 Claude Code 架构：
   - SSE 流式 Agent 对话
   - 子 Agent 派发
   - TaskCreate/TaskUpdate 任务追踪
   - 工具调用可视化
   ======================================== */
var AgentV2 = (function() {
  'use strict';

  var _tasks = [];           // 任务列表
  var _currentRun = null;    // 当前运行
  var _subAgents = [];       // 子 Agent 列表
  var _callbacks = {};       // UI 回调

  /* ----- 核心：运行 Agent 任务 ----- */
  function run(task, options, callbacks) {
    options = options || {};
    var model = options.model || 'deepseekv3';
    var maxIter = options.maxIterations || 30;
    _callbacks = callbacks || {};

    // 创建任务
    var taskId = 'task_' + Date.now();
    var taskObj = { id: taskId, subject: task.substring(0, 60), status: 'running', toolCalls: [], messages: [] };
    _tasks.unshift(taskObj);
    _currentRun = taskObj;

    if (_callbacks.onTaskUpdate) _callbacks.onTaskUpdate(taskObj);

    return NexusAPI.agentChatStream(task, model, maxIter,
      // onEvent — 实时处理每个 SSR 事件
      function(event) {
        if (event.type === 'token') {
          if (_callbacks.onToken) _callbacks.onToken(event.content);
          taskObj.messages.push({ type: 'token', content: event.content });
        } else if (event.type === 'observation') {
          taskObj.toolCalls.push({ tool: event.tool, result: event.result });
          if (_callbacks.onToolResult) _callbacks.onToolResult(event.tool, event.result);
        } else if (event.type === 'status') {
          taskObj.status = event.phase;
          if (_callbacks.onStatus) _callbacks.onStatus(event.phase, event.iteration);
        } else if (event.type === 'final') {
          taskObj.status = 'completed';
          taskObj.answer = event.content;
          if (_callbacks.onFinal) _callbacks.onFinal(event.content, event.iterations);
        } else if (event.type === 'error') {
          taskObj.status = 'failed';
          taskObj.error = event.error;
          if (_callbacks.onError) _callbacks.onError(event.error);
        }
      },
      // onDone
      function() {
        if (_callbacks.onDone) _callbacks.onDone();
        _currentRun = null;
      },
      // onError
      function(err) {
        taskObj.status = 'failed';
        taskObj.error = err.message;
        if (_callbacks.onError) _callbacks.onError(err.message);
        _currentRun = null;
      }
    );
  }

  /* ----- 子 Agent 派发 ----- */
  function spawnAgent(task, options) {
    var a = { id: 'sub_' + Date.now(), task: task.substring(0, 60), status: 'pending' };
    _subAgents.unshift(a);
    if (_callbacks.onSubAgentUpdate) _callbacks.onSubAgentUpdate(a);

    return NexusAPI.agentSpawn(task, options.model, options.maxIterations).then(function(r) {
      if (r.ok) {
        a.status = 'completed';
        a.result = r.agent.content;
      } else {
        a.status = 'failed';
        a.error = r.error;
      }
      if (_callbacks.onSubAgentUpdate) _callbacks.onSubAgentUpdate(a);
      return r;
    }).catch(function(e) {
      a.status = 'failed';
      a.error = e.message;
      if (_callbacks.onSubAgentUpdate) _callbacks.onSubAgentUpdate(a);
      return { ok: false, error: e.message };
    });
  }

  /* ----- 任务管理 ----- */
  function getTasks() { return _tasks; }
  function getCurrentRun() { return _currentRun; }
  function getSubAgents() { return _subAgents; }

  function clearTasks() { _tasks = []; _subAgents = []; if (_callbacks.onTaskUpdate) _callbacks.onTaskUpdate(null); }

  /* ----- 导出 ----- */
  return {
    run: run,
    spawnAgent: spawnAgent,
    getTasks: getTasks,
    getCurrentRun: getCurrentRun,
    getSubAgents: getSubAgents,
    clearTasks: clearTasks
  };
})();
