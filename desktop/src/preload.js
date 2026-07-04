/**
 * Y·NEX Desktop — Preload Script
 * 安全地向渲染进程暴露 IPC 接口
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('ynex', {
  // Agent 通信
  // chat 既是函数（调用 agent:chat），也提供 .send(text) 用于 Y·NEX 粒子界面
  chat: Object.assign(
    (options) => ipcRenderer.invoke('agent:chat', options),
    {
      send: (text) => ipcRenderer.invoke('chat:send', { text }),
    }
  ),
  spawn: (options) => ipcRenderer.invoke('agent:spawn', options),
  status: () => ipcRenderer.invoke('agent:status'),

  // 语音输入 / 输出（基于渲染进程 Web Speech API）
  voice: {
    // 语音识别：callback 收到 { text } / { error } / { done }
    recognize: (callback) => {
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SR) { callback({ error: '当前环境不支持语音识别' }); return () => {}; }
      try {
        const rec = new SR();
        rec.lang = 'zh-CN';
        rec.continuous = false;
        rec.interimResults = false;
        rec.onresult = (e) => { try { callback({ text: e.results[0][0].transcript }); } catch (_) {} };
        rec.onerror = (e) => { try { callback({ error: e.error || '识别错误' }); } catch (_) {} };
        rec.onend = () => { try { callback({ done: true }); } catch (_) {} };
        rec.start();
        return () => { try { rec.stop(); } catch (_) {} };
      } catch (e) {
        callback({ error: e.message });
        return () => {};
      }
    },
    // 语音合成：返回 Promise<{ ok, error? }>
    speak: (text, options) => {
      return new Promise((resolve) => {
        if (!('speechSynthesis' in window)) { resolve({ ok: false, error: 'no speechSynthesis' }); return; }
        try {
          window.speechSynthesis.cancel();
          const u = new SpeechSynthesisUtterance(text || '');
          const o = options || {};
          u.lang = o.lang || 'zh-CN';
          u.rate = o.rate || 1;
          u.pitch = o.pitch || 1;
          u.volume = o.volume || 1;
          u.onend = () => resolve({ ok: true });
          u.onerror = (e) => resolve({ ok: false, error: e.error || 'speak error' });
          window.speechSynthesis.speak(u);
        } catch (e) { resolve({ ok: false, error: e.message }); }
      });
    },
    // 停止语音合成
    stopSpeak: () => {
      if ('speechSynthesis' in window) { try { window.speechSynthesis.cancel(); } catch (_) {} }
      return { ok: true };
    },
  },

  // 任务管理
  tasks: {
    create: (subject, description) => ipcRenderer.invoke('tasks:create', { subject, description }),
    list: (status) => ipcRenderer.invoke('tasks:list', status),
    update: (id, updates) => ipcRenderer.invoke('tasks:update', { id, updates }),
  },

  // 文件对话框
  dialog: {
    open: (options) => ipcRenderer.invoke('dialog:open', options),
    save: (options) => ipcRenderer.invoke('dialog:save', options),
  },

  // 工作区
  workspace: {
    open: () => ipcRenderer.invoke('workspace:open'),
    get: () => ipcRenderer.invoke('workspace:get'),
    set: (path) => ipcRenderer.invoke('workspace:set', path),
  },

  // 文件系统
  fs: {
    readDir: (path) => ipcRenderer.invoke('fs:readDir', path),
    readFile: (path) => ipcRenderer.invoke('fs:readFile', path),
    writeFile: (path, content) => ipcRenderer.invoke('fs:writeFile', { path, content }),
    stat: (path) => ipcRenderer.invoke('fs:stat', path),
    createDirectory: (path) => ipcRenderer.invoke('fs:createDirectory', path),
    delete: (path) => ipcRenderer.invoke('fs:delete', path),
    rename: (oldPath, newPath) => ipcRenderer.invoke('fs:rename', { oldPath, newPath }),
  },

  // 终端
  terminal: {
    create: (id, cwd) => ipcRenderer.invoke('terminal:create', { id, cwd }),
    write: (id, data) => ipcRenderer.invoke('terminal:write', { id, data }),
    resize: (id, cols, rows) => ipcRenderer.invoke('terminal:resize', { id, cols, rows }),
    kill: (id) => ipcRenderer.invoke('terminal:kill', id),
    onData: (id, callback) => {
      const handler = (event, data) => {
        if (data.id === id) callback(data.output);
      };
      ipcRenderer.on(`terminal:data:${id}`, handler);
      return () => ipcRenderer.removeListener(`terminal:data:${id}`, handler);
    },
  },

  // 系统控制
  system: {
    execute: (command) => ipcRenderer.invoke('system:execute', command),
    listProcesses: () => ipcRenderer.invoke('system:listProcesses'),
    killProcess: (pid) => ipcRenderer.invoke('system:killProcess', pid),
    screenshot: () => ipcRenderer.invoke('system:screenshot'),
    controlDesktop: (action, params) => ipcRenderer.invoke('system:controlDesktop', { action, params }),
  },

  // 通知
  notify: (title, body) => ipcRenderer.invoke('notify:send', { title, body }),

  // 窗口
  window: {
    minimize: () => ipcRenderer.invoke('window:minimize'),
    maximize: () => ipcRenderer.invoke('window:maximize'),
    close: () => ipcRenderer.invoke('window:close'),
  },

  // 外部链接
  openExternal: (url) => ipcRenderer.invoke('shell:open', url),

  // 流式事件监听
  onStream: (callback) => {
    const handler = (event, data) => callback(data);
    ipcRenderer.on('agent:stream', handler);
    return () => ipcRenderer.removeListener('agent:stream', handler);
  },

  onNewChat: (callback) => {
    ipcRenderer.on('agent:new-chat', callback);
    return () => ipcRenderer.removeAllListeners('agent:new-chat');
  },

  // Y·NEX 本地AI
  ynex: {
    status: () => ipcRenderer.invoke('ynex:status'),
    start: () => ipcRenderer.invoke('ynex:start'),
    stop: () => ipcRenderer.invoke('ynex:stop'),
    api: (method, endpoint, body) => ipcRenderer.invoke('ynex:api', { method, endpoint, body }),
  },

  onYnexStatus: (callback) => {
    const handler = (event, data) => callback(data);
    ipcRenderer.on('ynex:status', handler);
    return () => ipcRenderer.removeListener('ynex:status', handler);
  },

  // M3: LSP 语言服务器
  lsp: {
    autoDetect: () => ipcRenderer.invoke('lsp:autoDetect'),
    goToDefinition: (filePath, line, col, rootPath) => ipcRenderer.invoke('lsp:goToDefinition', { filePath, line, col, rootPath }),
    getDiagnostics: (filePath, rootPath) => ipcRenderer.invoke('lsp:getDiagnostics', { filePath, rootPath }),
    hover: (filePath, line, col, rootPath) => ipcRenderer.invoke('lsp:hover', { filePath, line, col, rootPath }),
    documentSymbols: (filePath, rootPath) => ipcRenderer.invoke('lsp:documentSymbols', { filePath, rootPath }),
  },

  // M3: MCP 服务器管理
  mcp: {
    addServer: (name, command, rootPath) => ipcRenderer.invoke('mcp:addServer', { name, command, rootPath }),
    removeServer: (name) => ipcRenderer.invoke('mcp:removeServer', { name }),
    list: () => ipcRenderer.invoke('mcp:list'),
    callTool: (serverName, toolName, args) => ipcRenderer.invoke('mcp:callTool', { serverName, toolName, args }),
    listResources: (serverName) => ipcRenderer.invoke('mcp:listResources', { serverName }),
    readResource: (serverName, uri) => ipcRenderer.invoke('mcp:readResource', { serverName, uri }),
  },

  // M3.5: 统一工具注册中心
  tools: {
    init: () => ipcRenderer.invoke('tools:init'),
    list: (options) => ipcRenderer.invoke('tools:list', options || {}),
    categories: () => ipcRenderer.invoke('tools:categories'),
    call: (name, args, ctx) => ipcRenderer.invoke('tools:call', { name, args, ctx }),
    get: (name) => ipcRenderer.invoke('tools:get', { name }),
  },

  // M3.5: Workflow Engine 工作流引擎
  workflow: {
    create: (config) => ipcRenderer.invoke('workflow:create', config),
    get: (id) => ipcRenderer.invoke('workflow:get', { id }),
    list: () => ipcRenderer.invoke('workflow:list'),
    delete: (id) => ipcRenderer.invoke('workflow:delete', { id }),
    save: (id) => ipcRenderer.invoke('workflow:save', { id }),
    load: (data) => ipcRenderer.invoke('workflow:load', data),
    run: (id, input) => ipcRenderer.invoke('workflow:run', { id, input }),
    pause: (id) => ipcRenderer.invoke('workflow:pause', { id }),
    resume: (id) => ipcRenderer.invoke('workflow:resume', { id }),
    stop: (id) => ipcRenderer.invoke('workflow:stop', { id }),
    addNode: (workflowId, nodeConfig) => ipcRenderer.invoke('workflow:addNode', { workflowId, nodeConfig }),
    removeNode: (workflowId, nodeId) => ipcRenderer.invoke('workflow:removeNode', { workflowId, nodeId }),
    addConnection: (workflowId, connConfig) => ipcRenderer.invoke('workflow:addConnection', { workflowId, connConfig }),
    removeConnection: (workflowId, connId) => ipcRenderer.invoke('workflow:removeConnection', { workflowId, connId }),
  },

  // M3.5: Multi-Agent Orchestrator 多Agent协作
  agent: {
    createTeam: (config) => ipcRenderer.invoke('agent:createTeam', config),
    getTeam: (id) => ipcRenderer.invoke('agent:getTeam', { id }),
    listTeams: () => ipcRenderer.invoke('agent:listTeams'),
    deleteTeam: (id) => ipcRenderer.invoke('agent:deleteTeam', { id }),
    createPresetTeam: (type) => ipcRenderer.invoke('agent:createPresetTeam', { type }),
    addMember: (teamId, memberConfig) => ipcRenderer.invoke('agent:addMember', { teamId, memberConfig }),
    removeMember: (teamId, memberId) => ipcRenderer.invoke('agent:removeMember', { teamId, memberId }),
    runTask: (teamId, task) => ipcRenderer.invoke('agent:runTask', { teamId, task }),
  },

  // M3.5: Trigger Engine 触发器引擎
  trigger: {
    create: (config) => ipcRenderer.invoke('trigger:create', config),
    get: (id) => ipcRenderer.invoke('trigger:get', { id }),
    list: () => ipcRenderer.invoke('trigger:list'),
    delete: (id) => ipcRenderer.invoke('trigger:delete', { id }),
    enable: (id) => ipcRenderer.invoke('trigger:enable', { id }),
    disable: (id) => ipcRenderer.invoke('trigger:disable', { id }),
    createPreset: (type) => ipcRenderer.invoke('trigger:createPreset', { type }),
    runNow: (id) => ipcRenderer.invoke('trigger:runNow', { id }),
  },

  // 积分与会员系统
  credits: {
    getUser: (userId) => ipcRenderer.invoke('credits:getUser', { userId }),
    getAvailable: (userId) => ipcRenderer.invoke('credits:getAvailable', { userId }),
    getPlans: () => ipcRenderer.invoke('credits:getPlans'),
    getPackages: () => ipcRenderer.invoke('credits:getPackages'),
    subscribe: (planId, userId) => ipcRenderer.invoke('credits:subscribe', { planId, userId }),
    recharge: (packageId, userId) => ipcRenderer.invoke('credits:recharge', { packageId, userId }),
    transactions: (userId, limit, offset) => ipcRenderer.invoke('credits:transactions', { userId, limit, offset }),
    usageStats: (userId, days) => ipcRenderer.invoke('credits:usageStats', { userId, days }),
  },

  // 市场与模板系统
  market: {
    // 技能
    listSkills: (keyword, category) => ipcRenderer.invoke('market:listSkills', { keyword, category }),
    getSkill: (id) => ipcRenderer.invoke('market:getSkill', { id }),
    installSkill: (skillData) => ipcRenderer.invoke('market:installSkill', { skillData }),
    uninstallSkill: (id) => ipcRenderer.invoke('market:uninstallSkill', { id }),
    exportSkill: (id) => ipcRenderer.invoke('market:exportSkill', { id }),
    skillCategories: () => ipcRenderer.invoke('market:skillCategories'),
    // Agent团队
    listAgents: (keyword) => ipcRenderer.invoke('market:listAgents', { keyword }),
    getAgent: (id) => ipcRenderer.invoke('market:getAgent', { id }),
    installAgent: (agentData) => ipcRenderer.invoke('market:installAgent', { agentData }),
    uninstallAgent: (id) => ipcRenderer.invoke('market:uninstallAgent', { id }),
    exportAgent: (id) => ipcRenderer.invoke('market:exportAgent', { id }),
    // 工作流模板
    listWorkflowTemplates: (keyword) => ipcRenderer.invoke('market:listWorkflowTemplates', { keyword }),
    getWorkflowTemplate: (id) => ipcRenderer.invoke('market:getWorkflowTemplate', { id }),
    installWorkflowTemplate: (templateData) => ipcRenderer.invoke('market:installWorkflowTemplate', { templateData }),
    uninstallWorkflowTemplate: (id) => ipcRenderer.invoke('market:uninstallWorkflowTemplate', { id }),
    exportWorkflowTemplate: (id) => ipcRenderer.invoke('market:exportWorkflowTemplate', { id }),
  },

  // M3: 代码沙箱与自动测试
  sandbox: {
    snapshot: (filePath) => ipcRenderer.invoke('sandbox:snapshot', { filePath }),
    snapshotAll: (filePaths) => ipcRenderer.invoke('sandbox:snapshotAll', { filePaths }),
    rollback: (filePath) => ipcRenderer.invoke('sandbox:rollback', { filePath }),
    rollbackAll: () => ipcRenderer.invoke('sandbox:rollbackAll'),
    getDiff: (filePath) => ipcRenderer.invoke('sandbox:getDiff', { filePath }),
    syntaxCheck: (filePath) => ipcRenderer.invoke('sandbox:syntaxCheck', { filePath }),
    safeWrite: (filePath, content) => ipcRenderer.invoke('sandbox:safeWrite', { filePath, content }),
    safeWriteBatch: (edits) => ipcRenderer.invoke('sandbox:safeWriteBatch', { edits }),
    runTests: (workspacePath) => ipcRenderer.invoke('sandbox:runTests', { workspacePath }),
  },

  // M3: Git 集成
  git: {
    status: (workspacePath) => ipcRenderer.invoke('git:status', { workspacePath }),
    stage: (workspacePath, files) => ipcRenderer.invoke('git:stage', { workspacePath, files }),
    unstage: (workspacePath, files) => ipcRenderer.invoke('git:unstage', { workspacePath, files }),
    commit: (workspacePath, message) => ipcRenderer.invoke('git:commit', { workspacePath, message }),
    push: (workspacePath, remote, branch) => ipcRenderer.invoke('git:push', { workspacePath, remote, branch }),
    pull: (workspacePath, remote, branch) => ipcRenderer.invoke('git:pull', { workspacePath, remote, branch }),
    branches: (workspacePath) => ipcRenderer.invoke('git:branches', { workspacePath }),
    checkout: (workspacePath, branch) => ipcRenderer.invoke('git:checkout', { workspacePath, branch }),
    createBranch: (workspacePath, branch) => ipcRenderer.invoke('git:createBranch', { workspacePath, branch }),
    log: (workspacePath, count) => ipcRenderer.invoke('git:log', { workspacePath, count }),
    blame: (workspacePath, filePath) => ipcRenderer.invoke('git:blame', { workspacePath, filePath }),
    diff: (workspacePath, staged) => ipcRenderer.invoke('git:diff', { workspacePath, staged }),
    diffFile: (workspacePath, filePath, staged) => ipcRenderer.invoke('git:diffFile', { workspacePath, filePath, staged }),
    stash: (workspacePath) => ipcRenderer.invoke('git:stash', { workspacePath }),
    stashPop: (workspacePath) => ipcRenderer.invoke('git:stashPop', { workspacePath }),
    stashList: (workspacePath) => ipcRenderer.invoke('git:stashList', { workspacePath }),
    isRepo: (workspacePath) => ipcRenderer.invoke('git:isRepo', { workspacePath }),
  },

  // GitHub API 集成
  github: {
    setToken: (token) => ipcRenderer.invoke('github:setToken', { token }),
    checkToken: () => ipcRenderer.invoke('github:checkToken'),
    logout: () => ipcRenderer.invoke('github:logout'),
    repos: (page, perPage, type, sort, direction) => ipcRenderer.invoke('github:repos', { page, perPage, type, sort, direction }),
    repo: (owner, repo) => ipcRenderer.invoke('github:repo', { owner, repo }),
    createRepo: (name, description, isPrivate, autoInit) => ipcRenderer.invoke('github:createRepo', { name, description, private: isPrivate, autoInit }),
    issues: (owner, repo, state, page, perPage) => ipcRenderer.invoke('github:issues', { owner, repo, state, page, perPage }),
    createIssue: (owner, repo, title, body, labels) => ipcRenderer.invoke('github:createIssue', { owner, repo, title, body, labels }),
    pulls: (owner, repo, state, page, perPage) => ipcRenderer.invoke('github:pulls', { owner, repo, state, page, perPage }),
    createPull: (owner, repo, title, head, base, body) => ipcRenderer.invoke('github:createPull', { owner, repo, title, head, base, body }),
    mergePull: (owner, repo, number, commitTitle, commitMessage, mergeMethod) => ipcRenderer.invoke('github:mergePull', { owner, repo, number, commitTitle, commitMessage, mergeMethod }),
    branches: (owner, repo, page, perPage) => ipcRenderer.invoke('github:branches', { owner, repo, page, perPage }),
    workflows: (owner, repo, page, perPage) => ipcRenderer.invoke('github:workflows', { owner, repo, page, perPage }),
    searchCode: (q, page, perPage) => ipcRenderer.invoke('github:searchCode', { q, page, perPage }),
    searchRepos: (q, page, perPage, sort, order) => ipcRenderer.invoke('github:searchRepos', { q, page, perPage, sort, order }),
    user: (username) => ipcRenderer.invoke('github:user', { username }),
  },

  // 增强浏览器自动化（Browser Use）
  browser: {
    navigate: (url) => ipcRenderer.invoke('browser:navigate', { url }),
    screenshot: () => ipcRenderer.invoke('browser:screenshot'),
    extract: (selector) => ipcRenderer.invoke('browser:extract', { selector }),
    click: (selector) => ipcRenderer.invoke('browser:click', { selector }),
    type: (selector, text) => ipcRenderer.invoke('browser:type', { selector, text }),
    smartAction: (instruction) => ipcRenderer.invoke('browser:smart_action', { instruction }),
    startRecording: () => ipcRenderer.invoke('browser:start_recording'),
    stopRecording: () => ipcRenderer.invoke('browser:stop_recording'),
    replay: (recording) => ipcRenderer.invoke('browser:replay', { recording }),
  },

  // M3: DAP 调试器
  debug: {
    startPython: (scriptPath, workspacePath, breakpoints) => ipcRenderer.invoke('debug:startPython', { scriptPath, workspacePath, breakpoints }),
    startNode: (scriptPath, workspacePath, breakpoints) => ipcRenderer.invoke('debug:startNode', { scriptPath, workspacePath, breakpoints }),
    getOutput: (id) => ipcRenderer.invoke('debug:getOutput', { id }),
    stop: (id) => ipcRenderer.invoke('debug:stop', { id }),
    list: () => ipcRenderer.invoke('debug:list'),
  },

  // M3: SSH 远程开发
  ssh: {
    connect: (host, port, username) => ipcRenderer.invoke('ssh:connect', { host, port, username }),
    disconnect: (id) => ipcRenderer.invoke('ssh:disconnect', { id }),
    listDir: (id, remotePath) => ipcRenderer.invoke('ssh:listDir', { id, remotePath }),
    readFile: (id, remotePath) => ipcRenderer.invoke('ssh:readFile', { id, remotePath }),
    writeFile: (id, remotePath, content) => ipcRenderer.invoke('ssh:writeFile', { id, remotePath, content }),
    deleteFile: (id, remotePath) => ipcRenderer.invoke('ssh:deleteFile', { id, remotePath }),
    exec: (id, command) => ipcRenderer.invoke('ssh:exec', { id, command }),
    list: () => ipcRenderer.invoke('ssh:list'),
  },

  // M5: AI 内联代码补全
  completion: {
    get: (code, suffix, language, filePath) => ipcRenderer.invoke('completion:get', { code, suffix, language, filePath }),
    clearCache: () => ipcRenderer.invoke('completion:clearCache'),
  },

  // M5: AI 代码审查
  review: {
    file: (code, filePath, language) => ipcRenderer.invoke('review:file', { code, filePath, language }),
    project: (files, workspacePath) => ipcRenderer.invoke('review:project', { files, workspacePath }),
    list: () => ipcRenderer.invoke('review:list'),
  },

  // M5: AI 重构
  refactor: {
    execute: (code, filePath, language, operation, selection) => ipcRenderer.invoke('refactor:execute', { code, filePath, language, operation, selection }),
    operations: () => ipcRenderer.invoke('refactor:operations'),
  },

  // M5: 智能上下文管理
  context: {
    collect: (task, workspacePath, openFiles, currentFile) => ipcRenderer.invoke('context:collect', { task, workspacePath, openFiles, currentFile }),
    buildPrompt: (context) => ipcRenderer.invoke('context:buildPrompt', { context }),
  },

  // M5: 键盘宏录制
  macro: {
    start: (name) => ipcRenderer.invoke('macro:start', { name }),
    stop: () => ipcRenderer.invoke('macro:stop'),
    record: (event) => ipcRenderer.invoke('macro:record', { event }),
    play: (name) => ipcRenderer.invoke('macro:play', { name }),
    list: () => ipcRenderer.invoke('macro:list'),
    delete: (name) => ipcRenderer.invoke('macro:delete', { name }),
    isRecording: () => ipcRenderer.invoke('macro:isRecording'),
  },

  // M5: Docker 容器
  docker: {
    check: () => ipcRenderer.invoke('docker:check'),
    listContainers: () => ipcRenderer.invoke('docker:listContainers'),
    listImages: () => ipcRenderer.invoke('docker:listImages'),
    start: (nameOrId) => ipcRenderer.invoke('docker:start', { nameOrId }),
    stop: (nameOrId) => ipcRenderer.invoke('docker:stop', { nameOrId }),
    restart: (nameOrId) => ipcRenderer.invoke('docker:restart', { nameOrId }),
    remove: (nameOrId) => ipcRenderer.invoke('docker:remove', { nameOrId }),
    logs: (nameOrId, tail) => ipcRenderer.invoke('docker:logs', { nameOrId, tail }),
    exec: (nameOrId, command) => ipcRenderer.invoke('docker:exec', { nameOrId, command }),
    pull: (image) => ipcRenderer.invoke('docker:pull', { image }),
    composeUp: (composeFile, cwd) => ipcRenderer.invoke('docker:composeUp', { composeFile, cwd }),
    composeDown: (composeFile, cwd) => ipcRenderer.invoke('docker:composeDown', { composeFile, cwd }),
  },

  // M5: Jupyter
  jupyter: {
    start: (workspacePath) => ipcRenderer.invoke('jupyter:start', { workspacePath }),
    stop: () => ipcRenderer.invoke('jupyter:stop'),
    createNotebook: (filePath) => ipcRenderer.invoke('jupyter:createNotebook', { filePath }),
    readNotebook: (filePath) => ipcRenderer.invoke('jupyter:readNotebook', { filePath }),
    status: () => ipcRenderer.invoke('jupyter:status'),
  },

  // M5: CI/CD
  cicd: {
    detect: (workspacePath) => ipcRenderer.invoke('cicd:detect', { workspacePath }),
    runNpm: (workspacePath, script) => ipcRenderer.invoke('cicd:runNpm', { workspacePath, script }),
    runMake: (workspacePath, target) => ipcRenderer.invoke('cicd:runMake', { workspacePath, target }),
    runCommand: (workspacePath, command) => ipcRenderer.invoke('cicd:runCommand', { workspacePath, command }),
    runDocker: (workspacePath, dockerfile, tag) => ipcRenderer.invoke('cicd:runDocker', { workspacePath, dockerfile, tag }),
  },

  // M5: Mermaid
  mermaid: {
    render: (diagram, format, theme) => ipcRenderer.invoke('mermaid:render', { diagram, format, theme }),
    flowchart: (code, language) => ipcRenderer.invoke('mermaid:flowchart', { code, language }),
    classDiagram: (code, language) => ipcRenderer.invoke('mermaid:classDiagram', { code, language }),
  },

  // M5: 插件 SDK
  plugin: {
    init: (pluginDir) => ipcRenderer.invoke('plugin:init', { pluginDir }),
    create: (name, options) => ipcRenderer.invoke('plugin:create', { name, options }),
    remove: (name) => ipcRenderer.invoke('plugin:remove', { name }),
    toggle: (name) => ipcRenderer.invoke('plugin:toggle', { name }),
    list: () => ipcRenderer.invoke('plugin:list'),
    getContext: () => ipcRenderer.invoke('plugin:getContext'),
  },

  // 性能优化器
  perf: {
    stats: () => ipcRenderer.invoke('perf:stats'),
    cacheInvalidate: (pattern) => ipcRenderer.invoke('perf:cacheInvalidate', { pattern }),
    gc: () => ipcRenderer.invoke('perf:gc'),
  },

  // M6: 持久化缓存
  cache: {
    get: (key) => ipcRenderer.invoke('cache:get', { key }),
    set: (key, value, ttl) => ipcRenderer.invoke('cache:set', { key, value, ttl }),
    delete: (key) => ipcRenderer.invoke('cache:delete', { key }),
    clear: () => ipcRenderer.invoke('cache:clear'),
    stats: () => ipcRenderer.invoke('cache:stats'),
  },

  // M6: 代码索引
  index: {
    build: (workspacePath) => ipcRenderer.invoke('index:build', { workspacePath }),
    prefixSearch: (query) => ipcRenderer.invoke('index:prefixSearch', { query }),
    fuzzySearch: (query) => ipcRenderer.invoke('index:fuzzySearch', { query }),
    contentSearch: (query) => ipcRenderer.invoke('index:contentSearch', { query }),
    onFileChange: (event, filePath) => ipcRenderer.invoke('index:onFileChange', { event, filePath }),
    stats: () => ipcRenderer.invoke('index:stats'),
  },

  // M6: 连接池
  pool: {
    request: (options, body) => ipcRenderer.invoke('pool:request', { options, body }),
    parallel: (requests) => ipcRenderer.invoke('pool:parallel', { requests }),
    stats: () => ipcRenderer.invoke('pool:stats'),
  },

  // M6: 增量解析
  parser: {
    parse: (filePath, content) => ipcRenderer.invoke('parser:parse', { filePath, content }),
    parseDiff: (filePath, oldContent, newContent, changes) => ipcRenderer.invoke('parser:parseDiff', { filePath, oldContent, newContent, changes }),
    monacoLang: (filePath) => ipcRenderer.invoke('parser:monacoLang', { filePath }),
    dependencyGraph: (filePath) => ipcRenderer.invoke('parser:dependencyGraph', { filePath }),
    stats: () => ipcRenderer.invoke('parser:stats'),
  },

  // M6: 性能监控
  monitor: {
    start: () => ipcRenderer.invoke('monitor:start'),
    stop: () => ipcRenderer.invoke('monitor:stop'),
    snapshot: () => ipcRenderer.invoke('monitor:snapshot'),
    bottlenecks: () => ipcRenderer.invoke('monitor:bottlenecks'),
    report: () => ipcRenderer.invoke('monitor:report'),
  },

  // === M7: V8 快照优化 ===
  v8: {
    warmup: (modules) => ipcRenderer.invoke('v8:warmup', { modules }),
    stats: () => ipcRenderer.invoke('v8:stats'),
    clear: () => ipcRenderer.invoke('v8:clear'),
  },

  // === M7: SharedArrayBuffer 零拷贝 IPC ===
  sab: {
    allocate: (id, size) => ipcRenderer.invoke('sab:allocate', { id, size }),
    write: (id, data, offset) => ipcRenderer.invoke('sab:write', { id, data, offset }),
    read: (id, offset, length) => ipcRenderer.invoke('sab:read', { id, offset, length }),
    release: (id) => ipcRenderer.invoke('sab:release', { id }),
    stats: () => ipcRenderer.invoke('sab:stats'),
  },

  // === M7: 原生文件监听 ===
  watch: {
    start: (workspacePath) => ipcRenderer.invoke('watch:start', { workspacePath }),
    stop: () => ipcRenderer.invoke('watch:stop'),
    stats: () => ipcRenderer.invoke('watch:stats'),
  },
  onFilesAdded: (cb) => {
    const h = (e, f) => cb(f);
    ipcRenderer.on('files:added', h);
    return () => ipcRenderer.removeListener('files:added', h);
  },
  onFilesChanged: (cb) => {
    const h = (e, f) => cb(f);
    ipcRenderer.on('files:changed', h);
    return () => ipcRenderer.removeListener('files:changed', h);
  },
  onFilesDeleted: (cb) => {
    const h = (e, f) => cb(f);
    ipcRenderer.on('files:deleted', h);
    return () => ipcRenderer.removeListener('files:deleted', h);
  },

  // === M7: WASM 加速器 ===
  wasm: {
    regexSearch: (text, pattern, flags) => ipcRenderer.invoke('wasm:regexSearch', { text, pattern, flags }),
    diff: (oldText, newText) => ipcRenderer.invoke('wasm:diff', { oldText, newText }),
    fullTextSearch: (texts, query, maxResults) => ipcRenderer.invoke('wasm:fullTextSearch', { texts, query, maxResults }),
  },

  // === M7: Arena 内存分配器 + 弱引用缓存 ===
  arena: {
    stats: () => ipcRenderer.invoke('arena:stats'),
  },
  wrc: {
    get: (key) => ipcRenderer.invoke('wrc:get', { key }),
    set: (key, value) => ipcRenderer.invoke('wrc:set', { key, value }),
    stats: () => ipcRenderer.invoke('wrc:stats'),
  },

  // === M7: 内容寻址存储 + 懒加载 ===
  cas: {
    put: (filePath, content) => ipcRenderer.invoke('cas:put', { filePath, content }),
    get: (filePath) => ipcRenderer.invoke('cas:get', { filePath }),
    remove: (filePath) => ipcRenderer.invoke('cas:remove', { filePath }),
    stats: () => ipcRenderer.invoke('cas:stats'),
  },
  lazy: {
    register: (name, priority) => ipcRenderer.invoke('lazy:register', { name, priority }),
    loadAll: () => ipcRenderer.invoke('lazy:loadAll'),
    loadIdle: () => ipcRenderer.invoke('lazy:loadIdle'),
    stats: () => ipcRenderer.invoke('lazy:stats'),
  },

  // === M7: WebSocket 多路复用 ===
  ws: {
    connect: () => ipcRenderer.invoke('ws:connect'),
    request: (method, path, body) => ipcRenderer.invoke('ws:request', { method, path, body }),
    multiplex: (requests) => ipcRenderer.invoke('ws:multiplex', { requests }),
    stats: () => ipcRenderer.invoke('ws:stats'),
  },

  // ============================================================
  // 主站互通：用户认证 + 云端对话（扣减积分）
  // ============================================================
  auth: {
    login: (username, password) => ipcRenderer.invoke('auth:login', { username, password }),
    register: (data) => ipcRenderer.invoke('auth:register', data),
    logout: () => ipcRenderer.invoke('auth:logout'),
    check: () => ipcRenderer.invoke('auth:check'),
    profile: () => ipcRenderer.invoke('auth:profile'),
  },
  cloud: {
    chat: (model, messages, rawModel) => ipcRenderer.invoke('cloud:chat', { model, messages, rawModel }),
    models: () => ipcRenderer.invoke('cloud:models'),
  },
  onAuthChange: (callback) => {
    const handler = (event, data) => callback(data);
    ipcRenderer.on('auth:change', handler);
    return () => ipcRenderer.removeListener('auth:change', handler);
  },
});