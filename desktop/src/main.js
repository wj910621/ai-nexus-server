/**
 * Y·NEX Desktop — Electron Main Process
 * 
 * 基于 Claude Code 架构的桌面 AI Agent 平台
 * 集成 agent-engine-v2.js 提供完整 Agent 能力
 */

const { app, BrowserWindow, Tray, Menu, ipcMain, dialog, shell, Notification, globalShortcut } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, execSync } = require('child_process');
const Store = require('electron-store');
const { LspManager } = require('./lsp-manager');
const { McpManager } = require('./mcp-manager');
const { SandboxManager } = require('./sandbox-manager');
const { GitManager } = require('./git-manager');
const { GitHubManager } = require('./github-manager');
const { DebugManager } = require('./debug-manager');
const { SSHManager } = require('./ssh-manager');
const { CompletionManager } = require('./completion-manager');
const { CodeReviewManager } = require('./code-review-manager');
const { RefactorManager } = require('./refactor-manager');
const { ContextManager } = require('./context-manager');
const { MacroManager } = require('./macro-manager');
const { DockerManager } = require('./docker-manager');
const { JupyterManager } = require('./jupyter-manager');
const { CicdManager } = require('./cicd-manager');
const { MermaidManager } = require('./mermaid-manager');
const { PluginSDK } = require('./plugin-sdk');
const { PerfOptimizer } = require('./perf-optimizer');
const { StreamOptimizer } = require('./stream-optimizer');
const { PersistentCache } = require('./persistent-cache');
const { toolRegistry } = require('./unified-tool-registry');
const { WorkflowEngine } = require('./workflow-engine');
const { MultiAgentOrchestrator } = require('./multi-agent');
const { TriggerEngine } = require('./trigger-engine');
const { CreditsSystem } = require('./credits-system');
const { MarketManager } = require('./market-manager');
const { CodeIndex } = require('./code-index');
const { ConnectionPool } = require('./connection-pool');
const { IncrementalParser } = require('./incremental-parser');
const { PerfMonitor } = require('./perf-monitor');
const { V8SnapshotOptimizer } = require('./v8-snapshot');
const { SharedBufferIPC, RenderWorker } = require('./shared-buffer');
const { NativeFileWatcher } = require('./file-watcher');
const { WasmAccelerator } = require('./wasm-accelerator');
const { ArenaAllocator, WeakRefCache } = require('./arena-allocator');
const { ContentAddressableStorage, LazyModuleRegistry } = require('./cas-storage');
const { WebSocketMultiplexer } = require('./ws-multiplex');
const { BrowserUseEnhanced } = require('./browser-use-enhanced');
const { CrewAITools } = require('./crewai-tools');

// Agent Engine（延迟加载，等窗口创建后再初始化）
let agentHarness = null;
let taskManager = null;
let workflowEngine = null;
let multiAgentOrchestrator = null;
let triggerEngine = null;
let creditsSystem = null;
let marketManager = null;

// 性能优化器（全局单例）
let perfOptimizer = null;
let streamOptimizer = null;
let persistentCache = null;
let codeIndex = null;
let connectionPool = null;
let incrementalParser = null;
let perfMonitor = null;
let v8Snapshot = null;
let sharedBuffer = null;
let renderWorker = null;
let fileWatcher = null;
let wasmAccelerator = null;
let arenaAllocator = null;
let weakRefCache = null;
let casStorage = null;
let lazyRegistry = null;
let wsMultiplex = null;
let browserUseEnhanced = null;

// M3: 管理器
let lspManager = null;
let mcpManager = null;
let sandboxManager = null;
let gitManager = null;
let githubManager = null;
let debugManager = null;
let sshManager = null;
let completionManager = null;
let codeReviewManager = null;
let refactorManager = null;
let contextManager = null;
let macroManager = null;
let dockerManager = null;
let jupyterManager = null;
let cicdManager = null;
let mermaidManager = null;
let pluginSDK = null;

// Y·NEX 本地AI服务进程
let ynexProcess = null;
let ynexOnline = false;
const YNEX_PORT = 7777;
const YNEX_PATH = app.isPackaged
  ? path.join(process.resourcesPath, 'ynex')
  : path.join(__dirname, '..', '..');  // 开发模式：Y·NEX Desktop/src/ → 项目根目录
// 自动发现可用的 Python 解释器（打包后优先使用随包虚拟环境）
function findPythonExe() {
  const candidates = [];
  if (app.isPackaged) {
    candidates.push(path.join(YNEX_PATH, '.venv', 'Scripts', 'python.exe'));
    candidates.push(path.join(YNEX_PATH, '.venv', 'bin', 'python'));
  }
  // 开发环境：尝试项目内虚拟环境
  candidates.push(path.join(YNEX_PATH, '.venv', 'Scripts', 'python.exe'));
  // 环境变量指定的 Python
  if (process.env.YNEX_PYTHON) candidates.push(process.env.YNEX_PYTHON);
  // 常见 Windows 安装路径
  const progLocal = path.join(os.homedir(), 'AppData', 'Local', 'Programs', 'Python');
  if (fs.existsSync(progLocal)) {
    const dirs = fs.readdirSync(progLocal).filter(d => /^Python\d+$/i.test(d)).sort();
    for (const d of dirs) candidates.push(path.join(progLocal, d, 'python.exe'));
  }

  // 验证绝对路径候选是否真实可用
  for (const py of candidates) {
    if (py && py.includes(path.sep) && fs.existsSync(py)) {
      try {
        execSync(`"${py}" --version`, { stdio: 'ignore', timeout: 3000 });
        return py;
      } catch (_) {}
    }
  }

  // 在 PATH 中查找，跳过 WindowsApps 商店别名（它在未安装时无法执行）
  for (const name of ['python3', 'python', 'py']) {
    try {
      const output = execSync(`where ${name}`, {
        encoding: 'utf8',
        stdio: ['ignore', 'pipe', 'ignore'],
        timeout: 3000
      });
      const lines = output.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
      for (const line of lines) {
        if (/WindowsApps/i.test(line)) continue;
        try {
          execSync(`"${line}" --version`, { stdio: 'ignore', timeout: 3000 });
          return line;
        } catch (_) {}
      }
    } catch (_) {}
  }

  return null;
}

// 窗口和托盘
let mainWindow = null;
let tray = null;
let isQuitting = false;

// 开发模式与生产模式隔离 userData，避免开发/测试时的登录态泄漏到安装包用户
const isDevMode = process.argv.includes('--dev');
if (isDevMode) {
  const devUserData = path.join(app.getPath('userData'), 'ynex-dev');
  if (!fs.existsSync(devUserData)) fs.mkdirSync(devUserData, { recursive: true });
  app.setPath('userData', devUserData);
  console.log('[Y·NEX Desktop] 开发模式 userData:', devUserData);
}

// 本地持久化存储（用户数据目录，不会打包进安装包）
let store = null;

try {
  store = new Store({ name: 'ynex-desktop-config' });
} catch (e) {
  console.warn('[Y·NEX Desktop] electron-store 初始化失败:', e.message);
}

// IDE 工作区与终端
let currentWorkspace = null;
const terminals = new Map();

// 单例锁（必须在其他 app 事件之前申请）
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  console.log('[Y·NEX Desktop] 已有实例在运行，退出');
  app.quit();
  process.exit(0);
}

app.on('second-instance', () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
  }
});

// ============================================================
// M6: Chromium GPU 加速 + 性能标志
// ============================================================
app.commandLine.appendSwitch('enable-gpu-rasterization');
app.commandLine.appendSwitch('enable-zero-copy');
app.commandLine.appendSwitch('enable-accelerated-2d-canvas');
app.commandLine.appendSwitch('enable-accelerated-video-decode');
app.commandLine.appendSwitch('enable-features', 'Vulkan,DefaultANGLEVulkan,SharedArrayBuffer');
app.commandLine.appendSwitch('disable-features', 'CalculateNativeWinOcclusion');
app.commandLine.appendSwitch('js-flags', '--max-old-space-size=4096 --optimize-for-size');
app.commandLine.appendSwitch('high-dpi-support', '1');
app.commandLine.appendSwitch('ignore-gpu-blocklist');
app.commandLine.appendSwitch('disable-software-rasterizer');

// ============================================================
// 初始化
// ============================================================

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1680,
    height: 1050,
    minWidth: 1280,
    minHeight: 800,
    title: 'Y·NEX Desktop',
    icon: path.join(__dirname, '..', 'assets', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      backgroundThrottling: false,
      enablePreferredSizeMode: true,
      spellcheck: false,
      allowRunningInsecureContent: false,
      defaultFontSize: 17,
      defaultEncoding: 'UTF-8',
    },
    frame: true,
    titleBarStyle: 'default',
    backgroundColor: '#f5f5f7',
    show: false
  });

  // 加载前端
  const isDev = process.argv.includes('--dev');
  mainWindow.loadFile(path.join(__dirname, '..', 'renderer', 'index.html'));
  if (isDev) {
    mainWindow.webContents.openDevTools();
  }

  // 安全：拦截新窗口打开行为，所有 window.open 或 target=_blank
  // 一律在系统默认浏览器打开，避免渲染进程通过弹出窗口加载任意远程页面。
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    // 仅允许 http/https 协议在系统浏览器打开
    try {
      const parsed = new URL(url);
      if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
        shell.openExternal(url);
      } else {
        console.warn('[Y·NEX Desktop] 拦截非 HTTP(S) 新窗口:', url);
      }
    } catch (e) {
      console.warn('[Y·NEX Desktop] 拦截无效 URL 新窗口:', url);
    }
    return { action: 'deny' };
  });

  // 安全：拦截页面内导航，仅允许加载本地文件（file: 协议），
  // 防止渲染进程通过 location.href 或链接跳转到远程恶意页面。
  mainWindow.webContents.on('will-navigate', (event, navigationUrl) => {
    try {
      const parsed = new URL(navigationUrl);
      if (parsed.protocol !== 'file:') {
        console.warn('[Y·NEX Desktop] 拦截远程导航:', navigationUrl);
        event.preventDefault();
      }
    } catch (e) {
      console.warn('[Y·NEX Desktop] 拦截无效导航:', navigationUrl);
      event.preventDefault();
    }
  });

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function createTray() {
  tray = new Tray(path.join(__dirname, '..', 'assets', 'tray-icon.png'));
  
  const contextMenu = Menu.buildFromTemplate([
    { label: '显示 Y·NEX Desktop', click: () => mainWindow.show() },
    { type: 'separator' },
    { label: 'Agent 状态', enabled: false },
    { 
      label: '新建对话', 
      click: () => {
        mainWindow.show();
        mainWindow.webContents.send('agent:new-chat');
      }
    },
    { type: 'separator' },
    { label: '退出', click: () => { isQuitting = true; app.quit(); } }
  ]);

  tray.setToolTip('Y·NEX Desktop');
  tray.setContextMenu(contextMenu);

  tray.on('double-click', () => {
    mainWindow.show();
    mainWindow.focus();
  });
}


// ============================================================
// Y·NEX 本地AI服务管理
// ============================================================


async function checkYnexOnline() {
  return new Promise((resolve) => {
    const http = require('http');
    const req = http.get(`http://127.0.0.1:${YNEX_PORT}/api/health`, (res) => {
      resolve(res.statusCode === 200);
    });
    req.on('error', () => resolve(false));
    req.setTimeout(2000, () => { req.destroy(); resolve(false); });
  });
}

function startYnexServer() {
  if (ynexProcess) return;
  const pythonExe = findPythonExe();
  if (!pythonExe) {
    console.warn('[Y·NEX] 未找到可用的 Python 解释器，本地 AI 服务不会启动');
    ynexOnline = false;
    mainWindow?.webContents.send('ynex:status', { online: false, port: YNEX_PORT, error: '未找到可用的 Python 解释器' });
    return;
  }
  console.log(`[Y·NEX] 启动本地服务: ${pythonExe} ynex_server.py --port ${YNEX_PORT}`);

  ynexProcess = spawn(pythonExe, ['ynex_server.py', '--port', String(YNEX_PORT)], {
    cwd: YNEX_PATH,
    detached: false,
    windowsHide: true,
  });

  ynexProcess.on('error', (err) => {
    console.error('[Y·NEX] 启动本地服务失败:', err.message);
    ynexOnline = false;
    mainWindow?.webContents.send('ynex:status', { online: false, port: YNEX_PORT, error: err.message });
    ynexProcess = null;
  });

  ynexProcess.stdout.on('data', (data) => {
    console.log(`[Y·NEX] ${data.toString().trim()}`);
  });

  ynexProcess.stderr.on('data', (data) => {
    console.error(`[Y·NEX错误] ${data.toString().trim()}`);
  });

  ynexProcess.on('close', (code) => {
    console.log(`[Y·NEX] 服务退出，退出码: ${code}`);
    ynexProcess = null;
    ynexOnline = false;
  });

  // 等待服务就绪
  setTimeout(async () => {
    ynexOnline = await checkYnexOnline();
    console.log(`[Y·NEX] 服务状态: ${ynexOnline ? '在线' : '离线'}`);
    mainWindow?.webContents.send('ynex:status', { online: ynexOnline, port: YNEX_PORT });
  }, 4000);
}

function stopYnexServer() {
  if (ynexProcess) {
    ynexProcess.kill();
    ynexProcess = null;
    ynexOnline = false;
  }
}

// ============================================================
// Agent Engine 初始化
// ============================================================

function initAgentEngine() {
  try {
    const builtInAgent = path.join(YNEX_PATH, 'agent-engine-v2.js');
    if (fs.existsSync(builtInAgent)) {
      const { AgentHarness, TaskManager } = require(builtInAgent);
      agentHarness = new AgentHarness({
        model: 'deepseekv3',
        maxIterations: 50,
        workspace: app.getPath('userData')
      });
      taskManager = new TaskManager();
      console.log('[Y·NEX Desktop] Agent v2 引擎已加载');
      return true;
    }
  } catch(e) {
    console.warn('[Y·NEX Desktop] Agent v2 加载失败:', e.message);
  }

  try {
    const { ReActAgent } = require('./react-agent');
    agentHarness = new ReActAgent({
      model: 'deepseekv3',
      maxIterations: 10,
      workspace: app.getPath('userData')
    });
    taskManager = { tasks: new Map(), create(s,d) { return {id:'1',s} }, list() { return []; } };
    console.log('[Y·NEX Desktop] ReAct Agent 引擎已加载');
    return true;
  } catch(e) {
    console.warn('[Y·NEX Desktop] ReAct Agent 加载失败:', e.message);
  }

  try {
    const { ToolRegistry } = require('./agent-minimal');
    agentHarness = new ToolRegistry();
    taskManager = { tasks: new Map(), create(s,d) { return {id:'1',s} }, list() { return []; } };
    console.log('[Y·NEX Desktop] 内置 Agent 已加载');
    return true;
  } catch(e) {
    console.error('[Y·NEX Desktop] Agent 加载完全失败:', e.message);
    return false;
  }
}

// ============================================================
// 安全命令执行辅助函数
// ============================================================

// 允许执行的程序白名单（仅匹配文件名，不区分大小写和 .exe 后缀）
// 安全：排除 shell 解释器（bash/sh/zsh/powershell/pwsh/cmd），避免通过解释器绕过元字符检查
const ALLOWED_PROGRAMS = new Set([
  'python', 'python3', 'py',
  'node', 'npm', 'npx', 'yarn', 'pnpm',
  'git',
  'code', 'cursor',
  'tasklist', 'taskkill',
  'ps', 'kill',
  'ls', 'dir', 'cat', 'type', 'find', 'grep', 'echo',
]);

// 危险 shell 元字符：禁止在命令字符串中出现
const DANGEROUS_SHELL_METACHARS = /[;&|`$(){}[\]<>\\]/;

// 检查命令中是否存在未在引号内的危险 shell 元字符
function hasUnquotedShellMetacharacters(command) {
  let inQuote = false;
  let quoteChar = null;
  for (let i = 0; i < command.length; i++) {
    const ch = command[i];
    if (!inQuote && (ch === '"' || ch === "'")) {
      inQuote = true;
      quoteChar = ch;
    } else if (inQuote && ch === quoteChar) {
      inQuote = false;
      quoteChar = null;
    } else if (!inQuote && DANGEROUS_SHELL_METACHARS.test(ch)) {
      return true;
    }
  }
  return false;
}

// 验证程序是否在白名单中
function validateProgram(program) {
  if (!program || typeof program !== 'string') {
    throw new Error('程序名必须是非空字符串');
  }
  const basename = path.basename(program).replace(/\.exe$/i, '').toLowerCase();
  if (!ALLOWED_PROGRAMS.has(basename)) {
    throw new Error(`程序不在白名单中: ${basename}`);
  }
  return program;
}

// 安全地构造 spawn 参数
function sanitizeArgs(args) {
  if (args === undefined || args === null) return [];
  if (!Array.isArray(args)) {
    throw new Error('命令参数必须是数组');
  }
  return args.map(a => String(a));
}

// 简单命令解析：program arg1 "arg2" ...
function parseSimpleCommand(command) {
  const tokens = [];
  let current = '';
  let inQuote = false;
  let quoteChar = null;
  for (let i = 0; i < command.length; i++) {
    const ch = command[i];
    if (!inQuote && (ch === '"' || ch === "'")) {
      inQuote = true;
      quoteChar = ch;
    } else if (inQuote && ch === quoteChar) {
      inQuote = false;
      quoteChar = null;
    } else if (!inQuote && /\s/.test(ch)) {
      if (current.length > 0) {
        tokens.push(current);
        current = '';
      }
    } else {
      current += ch;
    }
  }
  if (current.length > 0) tokens.push(current);
  if (inQuote) throw new Error('命令引号不匹配');
  if (tokens.length === 0) throw new Error('命令为空');
  return { program: tokens[0], args: tokens.slice(1) };
}

// 将命令字符串安全解析为 { program, args, cwd }
// 仅支持两种形式：
//   1. 单个程序 + 参数（无 shell 元字符）
//   2. cd "path" && program args... （用于兼容历史代码）
function parseSafeCommand(command) {
  if (typeof command !== 'string' || !command.trim()) {
    throw new Error('命令必须是有效字符串');
  }
  command = command.trim();

  // 兼容 "cd \"path\" && program args"
  const cdMatch = command.match(/^cd\s+["']([^"']+)["']\s*&&\s*(.+)$/i);
  if (cdMatch) {
    const cwd = cdMatch[1];
    const rest = cdMatch[2].trim();
    const parsed = parseSimpleCommand(rest);
    return { ...parsed, cwd };
  }

  // 禁止未在引号内的 shell 元字符，防止命令链/管道/重定向注入
  if (hasUnquotedShellMetacharacters(command)) {
    throw new Error('命令包含不安全的 shell 元字符，请使用 { program, args, cwd } 对象形式');
  }

  return { ...parseSimpleCommand(command), cwd: undefined };
}

// 安全执行外部程序（禁用 shell）
function safeSpawn(program, args, options = {}) {
  validateProgram(program);
  const safeArgs = sanitizeArgs(args);
  const cwd = options.cwd;
  if (cwd && typeof cwd === 'string') {
    const resolved = path.resolve(cwd);
    if (!fs.existsSync(resolved)) {
      throw new Error('工作目录不存在: ' + cwd);
    }
  }
  return spawn(program, safeArgs, {
    ...options,
    shell: false,
    windowsHide: true,
    detached: false
  });
}

// 运行安全命令并返回结果 Promise
function runSafeCommand(program, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = safeSpawn(program, args, options);
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (data) => { stdout += data.toString(); });
    child.stderr.on('data', (data) => { stderr += data.toString(); });
    child.on('close', (code) => resolve({ code, stdout, stderr }));
    child.on('error', (err) => reject(err));
  });
}

// ============================================================
// 流式输出批量合并器（减少高频 IPC 发送，降低渲染进程重绘开销）
// ============================================================
class StreamBatcher {
  constructor(sendFn, interval) {
    this.sendFn = sendFn;
    this.interval = interval || 16;
    this.buffer = '';
    this.timer = null;
  }
  push(data) {
    this.buffer += data;
    if (!this.timer) {
      this.timer = setTimeout(() => this.flush(), this.interval);
    }
  }
  flush() {
    if (this.buffer) {
      this.sendFn(this.buffer);
      this.buffer = '';
    }
    this.timer = null;
  }
}

// ============================================================
// IPC 处理器
// ============================================================

function isPathAllowed(targetPath) {
  if (!targetPath || typeof targetPath !== 'string') return false;
  const resolved = path.resolve(targetPath);
  const workspace = currentWorkspace || process.cwd();
  const tempDir = os.tmpdir();
  // 安全：仅允许工作区本身及其子目录、系统临时目录。
  // 不再开放父目录（path.dirname(workspace)），避免访问兄弟项目；
  // 父目录访问需通过明确的"切换工作区"流程并经用户确认。
  const allowedRoots = [workspace, tempDir];
  for (const root of allowedRoots) {
    // 确保是目录前缀匹配（root + 路径分隔符），避免 /foo 匹配 /foobar
    const rootNorm = path.resolve(root);
    if (resolved.toLowerCase() === rootNorm.toLowerCase()) return true;
    if (resolved.toLowerCase().startsWith(rootNorm.toLowerCase() + path.sep)) return true;
  }
  return false;
}

function setupIPC() {
  // Agent 对话
  ipcMain.handle('agent:chat', async (event, { task, model, maxIterations }) => {
    if (!agentHarness) return { ok: false, error: 'Agent 引擎未初始化' };
    try {
      const results = [];
      let final = null;
      for await (const event of agentHarness.run(task, { model, maxIterations })) {
        if (results.length < 500) results.push(event);
        if (event.type === 'final') final = event;
        // 实时推送到渲染进程
        mainWindow?.webContents.send('agent:stream', event);
      }
      return { 
        ok: true, 
        answer: final?.content || '',
        iterations: final?.iterations || 0,
        history: final?.history || []
      };
    } catch(e) {
      return { ok: false, error: e.message };
    }
  });

  // 子 Agent 派发
  ipcMain.handle('agent:spawn', async (event, { task, model, maxIterations }) => {
    if (!agentHarness?.spawnAgent) return { ok: false, error: '子 Agent 不支持' };
    try {
      const result = await agentHarness.spawnAgent(task, { model, maxIterations });
      return { ok: true, agent: result };
    } catch(e) {
      return { ok: false, error: e.message };
    }
  });

  // 任务管理
  ipcMain.handle('tasks:create', (event, { subject, description }) => {
    if (!taskManager) return { ok: false, error: '任务管理器未初始化' };
    const task = taskManager.create(subject, description);
    return { ok: true, task };
  });

  ipcMain.handle('tasks:list', (event, status) => {
    if (!taskManager) return { ok: true, tasks: [] };
    return { ok: true, tasks: taskManager.list(status) };
  });

  ipcMain.handle('tasks:update', (event, { id, updates }) => {
    if (!taskManager) return { ok: false, error: '任务管理器未初始化' };
    const task = taskManager.update(id, updates);
    return { ok: true, task };
  });

  // 文件对话框
  ipcMain.handle('dialog:open', async (event, options) => {
    return dialog.showOpenDialog(mainWindow, options);
  });

  ipcMain.handle('dialog:save', async (event, options) => {
    return dialog.showSaveDialog(mainWindow, options);
  });

  // 通知
  ipcMain.handle('notify:send', (event, { title, body }) => {
    if (Notification.isSupported()) {
      new Notification({ title, body }).show();
    }
    return { ok: true };
  });

  // 窗口控制
  ipcMain.handle('window:minimize', () => mainWindow?.minimize());
  ipcMain.handle('window:maximize', () => {
    if (mainWindow?.isMaximized()) mainWindow.unmaximize();
    else mainWindow?.maximize();
  });
  ipcMain.handle('window:close', () => mainWindow?.close());

  // 外部链接（仅允许 http/https 协议，防止 file:/// 或恶意协议执行）
  ipcMain.handle('shell:open', (event, url) => {
    if (typeof url !== 'string') return;
    try {
      const parsed = new URL(url);
      if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
        return shell.openExternal(url);
      }
      console.warn('[Y·NEX Desktop] 拒绝打开非 HTTP(S) 链接:', url);
    } catch (e) {
      console.warn('[Y·NEX Desktop] 无效 URL:', url);
    }
  });

  // Agent 状态
  ipcMain.handle('agent:status', () => {
    return {
      ok: true,
      engine: !!agentHarness,
      model: agentHarness?.config?.model || 'unknown',
      tools: agentHarness?.tools?.list()?.length || 0
    };
  });

  // Y·NEX 本地AI状态
  ipcMain.handle('ynex:status', async () => {
    ynexOnline = await checkYnexOnline();
    return { online: ynexOnline, port: YNEX_PORT };
  });

  // Y·NEX 服务控制
  ipcMain.handle('ynex:start', () => {
    const pythonExe = findPythonExe();
    if (!pythonExe) {
      return { ok: false, started: false, error: '未找到可用的 Python 解释器，请安装 Python 并添加到 PATH' };
    }
    startYnexServer();
    return { ok: true, started: true };
  });

  ipcMain.handle('ynex:stop', () => {
    stopYnexServer();
    return { ok: true, stopped: true };
  });

  // Y·NEX 通用 API 转发（避免 renderer 直接跨域访问本地服务）
  ipcMain.handle('ynex:api', async (event, { method, endpoint, body }) => {
    try {
      const http = require('http');
      const data = body ? JSON.stringify(body) : null;
      return await new Promise((resolve, reject) => {
        const options = {
          hostname: '127.0.0.1',
          port: YNEX_PORT,
          path: endpoint,
          method: method || 'GET',
          headers: {
            'Content-Type': 'application/json',
            ...(data ? { 'Content-Length': Buffer.byteLength(data) } : {}),
          },
          timeout: 60000,
        };
        const req = http.request(options, (res) => {
          let responseData = '';
          res.on('data', (chunk) => responseData += chunk);
          res.on('end', () => {
            try { resolve({ ok: res.statusCode < 300, status: res.statusCode, data: JSON.parse(responseData) }); }
            catch { resolve({ ok: res.statusCode < 300, status: res.statusCode, data: responseData }); }
          });
        });
        req.on('error', (err) => reject(err));
        req.on('timeout', () => { req.destroy(); reject(new Error('请求超时')); });
        if (data) req.write(data);
        req.end();
      });
    } catch (e) {
      console.error('[Y·NEX API转发] 失败:', e.message);
      return { ok: false, error: e.message };
    }
  });

  // ============================================================
  // IDE 工作区
  // ============================================================

  ipcMain.handle('workspace:open', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openDirectory'],
      title: '选择工作区文件夹'
    });
    if (!result.canceled && result.filePaths.length > 0) {
      currentWorkspace = result.filePaths[0];
      return { ok: true, path: currentWorkspace };
    }
    return { ok: false };
  });

  ipcMain.handle('workspace:get', () => {
    return { ok: true, path: currentWorkspace };
  });

  ipcMain.handle('workspace:set', (event, wsPath) => {
    // 安全策略：工作区路径必须是绝对路径、真实存在的目录，
    // 且必须在用户家目录子树内，防止设置 currentWorkspace = "C:\\" 绕过 isPathAllowed。
    if (typeof wsPath !== 'string' || !wsPath.trim()) {
      return { ok: false, error: '工作区路径不能为空' };
    }
    const resolved = path.resolve(wsPath);
    if (!path.isAbsolute(resolved)) {
      return { ok: false, error: '工作区路径必须是绝对路径' };
    }
    if (resolved.includes('..')) {
      return { ok: false, error: '工作区路径不能包含 ..' };
    }
    // 限制工作区必须在用户家目录子树内，防止设置根目录（如 C:\、/）绕过 isPathAllowed
    const homeDir = os.homedir();
    const normalizedHome = path.resolve(homeDir);
    const normalizedResolved = path.resolve(resolved);
    if (normalizedResolved !== normalizedHome && !normalizedResolved.startsWith(normalizedHome + path.sep)) {
      return { ok: false, error: `安全限制：工作区必须在用户家目录内 (${normalizedHome})` };
    }
    try {
      const stat = fs.statSync(resolved);
      if (!stat.isDirectory()) {
        return { ok: false, error: '工作区路径必须是目录' };
      }
    } catch (e) {
      return { ok: false, error: '工作区路径不存在或无法访问' };
    }
    currentWorkspace = resolved;
    return { ok: true, path: currentWorkspace };
  });

  // ============================================================
  // IDE 文件系统
  // ============================================================

  ipcMain.handle('fs:readDir', async (event, dirPath) => {
    if (!isPathAllowed(dirPath)) return { ok: false, error: '安全限制：无法访问该路径' };
    try {
      const entries = await fs.promises.readdir(dirPath, { withFileTypes: true });
      return {
        ok: true,
        entries: entries.map(e => ({
          name: e.name,
          path: path.join(dirPath, e.name),
          isDirectory: e.isDirectory(),
          isFile: e.isFile()
        }))
      };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('fs:readFile', async (event, filePath) => {
    if (!isPathAllowed(filePath)) return { ok: false, error: '安全限制：无法访问该路径' };
    try {
      const content = await fs.promises.readFile(filePath, 'utf-8');
      return { ok: true, content };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('fs:writeFile', async (event, { path, content }) => {
    if (!isPathAllowed(path)) return { ok: false, error: '安全限制：无法访问该路径' };
    try {
      await fs.promises.writeFile(path, content, 'utf-8');
      return { ok: true };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('fs:stat', async (event, filePath) => {
    if (!isPathAllowed(filePath)) return { ok: false, error: '安全限制：无法访问该路径' };
    try {
      const stat = await fs.promises.stat(filePath);
      return {
        ok: true,
        stat: {
          isFile: stat.isFile(),
          isDirectory: stat.isDirectory(),
          size: stat.size,
          mtime: stat.mtime
        }
      };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('fs:createDirectory', async (event, dirPath) => {
    if (!isPathAllowed(dirPath)) return { ok: false, error: '安全限制：无法访问该路径' };
    try {
      await fs.promises.mkdir(dirPath, { recursive: true });
      return { ok: true };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('fs:delete', async (event, targetPath) => {
    if (!isPathAllowed(targetPath)) return { ok: false, error: '安全限制：无法访问该路径' };
    try {
      const stat = await fs.promises.stat(targetPath);
      if (stat.isDirectory()) {
        await fs.promises.rm(targetPath, { recursive: true, force: true });
      } else {
        await fs.promises.unlink(targetPath);
      }
      return { ok: true };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('fs:rename', async (event, { oldPath, newPath }) => {
    if (!isPathAllowed(oldPath) || !isPathAllowed(newPath)) return { ok: false, error: '安全限制：无法访问该路径' };
    try {
      await fs.promises.rename(oldPath, newPath);
      return { ok: true };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  // ============================================================
  // IDE 终端
  // ============================================================

  ipcMain.handle('terminal:create', async (event, { id, cwd }) => {
    try {
      const targetCwd = cwd || currentWorkspace || process.cwd();
      const resolvedCwd = path.resolve(targetCwd);
      const userHome = process.env.USERPROFILE || process.env.HOME || os.homedir();
      if (!resolvedCwd.toLowerCase().startsWith(userHome.toLowerCase()) &&
          !resolvedCwd.toLowerCase().startsWith(path.resolve(currentWorkspace || process.cwd()).toLowerCase())) {
        return { ok: false, error: '安全限制：终端工作目录不在允许范围内' };
      }
      const shell = process.platform === 'win32' ? 'powershell.exe' : 'bash';
      const term = spawn(shell, [], {
        cwd: targetCwd,
        env: process.env,
        windowsHide: true
      });

      const batcher = new StreamBatcher((output) => {
        mainWindow?.webContents.send(`terminal:data:${id}`, { id, output });
      });
      term.stdout.on('data', (data) => batcher.push(data.toString()));
      term.stderr.on('data', (data) => batcher.push(data.toString()));
      term.on('close', (code) => {
        batcher.push(`\r\n[终端退出，退出码: ${code}]\r\n`);
        batcher.flush();
        terminals.delete(id);
      });

      terminals.set(id, term);
      return { ok: true, id };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('terminal:write', async (event, { id, data }) => {
    const term = terminals.get(id);
    if (!term) return { ok: false, error: '终端不存在' };
    try {
      term.stdin.write(data);
      return { ok: true };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('terminal:resize', async (event, { id, cols, rows }) => {
    // 无 node-pty 时仅记录，不影响功能
    return { ok: true };
  });

  ipcMain.handle('terminal:kill', async (event, id) => {
    const term = terminals.get(id);
    if (!term) return { ok: false, error: '终端不存在' };
    try {
      term.kill();
      terminals.delete(id);
      return { ok: true };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  // ============================================================
  // 系统控制（Y·NEX 完全控制桌面端和用户电脑）
  // ============================================================

  ipcMain.handle('system:execute', async (event, command) => {
    try {
      let program, args, cwd;
      if (command && typeof command === 'object') {
        ({ program, args, cwd } = command);
        if (!program) throw new Error('缺少 program 字段');
        const SAFE_PROGRAMS = ['tasklist', 'ps', 'ls', 'dir', 'echo', 'whoami', 'hostname', 'ipconfig', 'ifconfig', 'systeminfo'];
        const baseProg = path.basename(program).replace(/\.(exe|cmd|bat)$/i, '');
        if (!SAFE_PROGRAMS.includes(baseProg.toLowerCase())) {
          const { response } = await dialog.showMessageBox(mainWindow, {
            type: 'warning',
            buttons: ['取消', '允许执行'],
            defaultId: 0, cancelId: 0,
            title: 'Y·NEX Desktop',
            message: '即将执行外部程序',
            detail: `${program} ${(args || []).join(' ')}`,
            noLink: true
          });
          if (response !== 1) return { ok: false, error: '用户取消了命令执行' };
        }
      } else {
        // 字符串命令通常来自 AI/终端输入，弹窗让用户确认以防止自动执行恶意命令
        const { response } = await dialog.showMessageBox(mainWindow, {
          type: 'warning',
          buttons: ['取消', '允许执行'],
          defaultId: 0,
          cancelId: 0,
          title: 'Y·NEX Desktop',
          message: '即将执行外部命令',
          detail: String(command),
          noLink: true
        });
        if (response !== 1) {
          return { ok: false, error: '用户取消了命令执行' };
        }
        const parsed = parseSafeCommand(command);
        program = parsed.program;
        args = parsed.args;
        cwd = parsed.cwd;
      }
      const result = await runSafeCommand(program, args, { cwd });
      return { ok: true, result };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('system:listProcesses', async () => {
    try {
      const isWin = process.platform === 'win32';
      const program = isWin ? 'tasklist' : 'ps';
      const args = isWin ? ['/FO', 'CSV', '/NH'] : ['aux'];
      const result = await runSafeCommand(program, args);
      return { ok: true, processes: result.stdout };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('system:killProcess', async (event, pid) => {
    try {
      const pidNum = Number(pid);
      if (!Number.isInteger(pidNum) || pidNum <= 0) {
        throw new Error('PID 必须是正整数');
      }
      const isWin = process.platform === 'win32';
      const program = isWin ? 'taskkill' : 'kill';
      const args = isWin ? ['/F', '/PID', String(pidNum)] : ['-9', String(pidNum)];
      const result = await runSafeCommand(program, args);
      return { ok: true, stdout: result.stdout, stderr: result.stderr };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('system:screenshot', async () => {
    try {
      const screenshot = require('screenshot-desktop');
      const img = await screenshot();
      return { ok: true, image: img.toString('base64') };
    } catch (e) {
      return { ok: false, error: '截屏功能需要 screenshot-desktop 依赖: ' + e.message };
    }
  });

  ipcMain.handle('system:controlDesktop', async (event, { action, params }) => {
    try {
      switch (action) {
        case 'openApp': {
          if (!params.command || typeof params.command !== 'string') {
            throw new Error('缺少 command 参数');
          }
          // 安全：所有 openApp 操作必须经用户确认，防止渲染进程被 XSS 后
          // 通过 python -c / node -e 等解释器参数执行任意代码。
          const argsStr = Array.isArray(params.args) ? params.args.join(' ') : '';
          const { response } = await dialog.showMessageBox(mainWindow, {
            type: 'warning',
            buttons: ['取消', '允许启动'],
            defaultId: 0, cancelId: 0,
            title: 'Y·NEX Desktop',
            message: '即将启动外部程序',
            detail: `${params.command} ${argsStr}`,
            noLink: true
          });
          if (response !== 1) return { ok: false, error: '用户取消了程序启动' };
          const child = safeSpawn(params.command, params.args, { detached: true });
          child.on('error', (err) => console.error('[system:controlDesktop openApp] 启动失败:', err.message));
          return { ok: true };
        }
        case 'openUrl': {
          const url = params.url;
          if (typeof url !== 'string' || !/^https?:\/\//i.test(url)) {
            throw new Error('URL 必须是 http/https 链接');
          }
          await shell.openExternal(url);
          return { ok: true };
        }
        case 'showWindow':
          mainWindow?.show();
          return { ok: true };
        case 'hideWindow':
          mainWindow?.hide();
          return { ok: true };
        case 'minimizeWindow':
          mainWindow?.minimize();
          return { ok: true };
        case 'maximizeWindow':
          mainWindow?.maximize();
          return { ok: true };
        case 'closeWindow':
          mainWindow?.close();
          return { ok: true };
        case 'notify':
          if (Notification.isSupported()) {
            new Notification({ title: params.title, body: params.body }).show();
          }
          return { ok: true };
        default:
          return { ok: false, error: '未知控制动作: ' + action };
      }
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  // ============================================================
  // M3: LSP 语言服务器
  // ============================================================

  ipcMain.handle('lsp:autoDetect', () => {
    lspManager.autoDetect();
    return { ok: true };
  });

  ipcMain.handle('lsp:goToDefinition', async (event, { filePath, line, col, rootPath }) => {
    return lspManager.goToDefinition(filePath, line, col, rootPath || currentWorkspace);
  });

  ipcMain.handle('lsp:getDiagnostics', async (event, { filePath, rootPath }) => {
    return lspManager.getDiagnostics(filePath, rootPath || currentWorkspace);
  });

  ipcMain.handle('lsp:hover', async (event, { filePath, line, col, rootPath }) => {
    return lspManager.hover(filePath, line, col, rootPath || currentWorkspace);
  });

  ipcMain.handle('lsp:documentSymbols', async (event, { filePath, rootPath }) => {
    return lspManager.documentSymbols(filePath, rootPath || currentWorkspace);
  });

  // ============================================================
  // M3: MCP 服务器管理
  // ============================================================

  ipcMain.handle('mcp:addServer', async (event, { name, command, rootPath }) => {
    if (!mcpManager) return { ok: false, error: 'MCP 管理器未初始化' };
    // 安全：MCP server 命令可启动任意解释器进程，必须经用户确认。
    // 同时禁止 -c/-e/--eval 等即时执行参数，防止通过 python -c "..." 实现 RCE。
    if (typeof command !== 'string' || !command.trim()) {
      return { ok: false, error: '命令不能为空' };
    }
    const lowerCmd = command.toLowerCase();
    const dangerousFlags = ['-c ', ' -c', '-e ', ' -e', '--eval', '--exec', 'eval(', 'exec('];
    for (const flag of dangerousFlags) {
      if (lowerCmd.includes(flag)) {
        return { ok: false, error: `安全限制：MCP 命令禁止包含即时执行参数 (${flag.trim()})` };
      }
    }
    const { response } = await dialog.showMessageBox(mainWindow, {
      type: 'warning',
      buttons: ['取消', '允许添加'],
      defaultId: 0, cancelId: 0,
      title: 'Y·NEX Desktop',
      message: '即将添加 MCP 服务器',
      detail: `名称: ${name}\n命令: ${command}\n工作目录: ${rootPath || currentWorkspace}`,
      noLink: true
    });
    if (response !== 1) return { ok: false, error: '用户取消了 MCP 服务器添加' };
    return mcpManager.addServer(name, command, rootPath || currentWorkspace);
  });

  ipcMain.handle('mcp:removeServer', async (event, { name }) => {
    if (!mcpManager) return { ok: false, error: 'MCP 管理器未初始化' };
    return mcpManager.removeServer(name);
  });

  ipcMain.handle('mcp:list', () => {
    if (!mcpManager) return { ok: true, servers: [] };
    return { ok: true, servers: mcpManager.listAll() };
  });

  ipcMain.handle('mcp:callTool', async (event, { serverName, toolName, args }) => {
    if (!mcpManager) return { ok: false, error: 'MCP 管理器未初始化' };
    return mcpManager.callTool(serverName, toolName, args);
  });

  ipcMain.handle('mcp:listResources', async (event, { serverName }) => {
    if (!mcpManager) return { ok: false, error: 'MCP 管理器未初始化' };
    return mcpManager.listResources(serverName);
  });

  ipcMain.handle('mcp:readResource', async (event, { serverName, uri }) => {
    if (!mcpManager) return { ok: false, error: 'MCP 管理器未初始化' };
    return mcpManager.readResource(serverName, uri);
  });

  // ============================================================
  // M3.5: 统一工具注册中心
  // ============================================================

  ipcMain.handle('tools:init', async () => {
    toolRegistry.setMcpManager(mcpManager);
    return toolRegistry.init();
  });

  ipcMain.handle('tools:list', async (event, options) => {
    return { ok: true, tools: toolRegistry.list(options || {}) };
  });

  ipcMain.handle('tools:categories', async () => {
    return { ok: true, categories: toolRegistry.categories() };
  });

  ipcMain.handle('tools:call', async (event, { name, args, ctx }) => {
    return toolRegistry.callTool(name, args, ctx || {});
  });

  ipcMain.handle('tools:get', async (event, { name }) => {
    const t = toolRegistry.getTool(name);
    return { ok: !!t, tool: t };
  });

  // ============================================================
  // Workflow Engine 工作流引擎
  // ============================================================

  ipcMain.handle('workflow:create', async (event, config) => {
    if (!workflowEngine) return { ok: false, error: 'Workflow Engine 未初始化' };
    const wf = workflowEngine.createWorkflow(config);
    return { ok: true, workflow: wf.toJSON() };
  });

  ipcMain.handle('workflow:get', async (event, { id }) => {
    if (!workflowEngine) return { ok: false, error: 'Workflow Engine 未初始化' };
    const wf = workflowEngine.getWorkflow(id);
    return { ok: !!wf, workflow: wf ? wf.toJSON() : null };
  });

  ipcMain.handle('workflow:list', async () => {
    if (!workflowEngine) return { ok: false, error: 'Workflow Engine 未初始化' };
    const list = workflowEngine.listWorkflows();
    return { ok: true, workflows: list };
  });

  ipcMain.handle('workflow:delete', async (event, { id }) => {
    if (!workflowEngine) return { ok: false, error: 'Workflow Engine 未初始化' };
    const result = workflowEngine.deleteWorkflow(id);
    return { ok: result };
  });

  ipcMain.handle('workflow:save', async (event, { id }) => {
    if (!workflowEngine) return { ok: false, error: 'Workflow Engine 未初始化' };
    const data = workflowEngine.saveWorkflow(id);
    return { ok: !!data, data };
  });

  ipcMain.handle('workflow:load', async (event, data) => {
    if (!workflowEngine) return { ok: false, error: 'Workflow Engine 未初始化' };
    const wf = workflowEngine.loadWorkflow(data);
    return { ok: true, workflow: wf.toJSON() };
  });

  ipcMain.handle('workflow:run', async (event, { id, input }) => {
    if (!workflowEngine) return { ok: false, error: 'Workflow Engine 未初始化' };
    const result = await workflowEngine.runWorkflow(id, input || {});
    return result;
  });

  ipcMain.handle('workflow:pause', async (event, { id }) => {
    if (!workflowEngine) return { ok: false, error: 'Workflow Engine 未初始化' };
    const result = workflowEngine.pauseWorkflow(id);
    return { ok: result };
  });

  ipcMain.handle('workflow:resume', async (event, { id }) => {
    if (!workflowEngine) return { ok: false, error: 'Workflow Engine 未初始化' };
    const result = workflowEngine.resumeWorkflow(id);
    return { ok: result };
  });

  ipcMain.handle('workflow:stop', async (event, { id }) => {
    if (!workflowEngine) return { ok: false, error: 'Workflow Engine 未初始化' };
    const result = workflowEngine.stopWorkflow(id);
    return { ok: result };
  });

  ipcMain.handle('workflow:addNode', async (event, { workflowId, nodeConfig }) => {
    if (!workflowEngine) return { ok: false, error: 'Workflow Engine 未初始化' };
    const wf = workflowEngine.getWorkflow(workflowId);
    if (!wf) return { ok: false, error: '工作流不存在' };
    const node = wf.addNode(nodeConfig);
    return { ok: true, node: node.toJSON() };
  });

  ipcMain.handle('workflow:removeNode', async (event, { workflowId, nodeId }) => {
    if (!workflowEngine) return { ok: false, error: 'Workflow Engine 未初始化' };
    const wf = workflowEngine.getWorkflow(workflowId);
    if (!wf) return { ok: false, error: '工作流不存在' };
    const result = wf.removeNode(nodeId);
    return { ok: result };
  });

  ipcMain.handle('workflow:addConnection', async (event, { workflowId, connConfig }) => {
    if (!workflowEngine) return { ok: false, error: 'Workflow Engine 未初始化' };
    const wf = workflowEngine.getWorkflow(workflowId);
    if (!wf) return { ok: false, error: '工作流不存在' };
    const conn = wf.addConnection(connConfig);
    return { ok: true, connection: conn.toJSON() };
  });

  ipcMain.handle('workflow:removeConnection', async (event, { workflowId, connId }) => {
    if (!workflowEngine) return { ok: false, error: 'Workflow Engine 未初始化' };
    const wf = workflowEngine.getWorkflow(workflowId);
    if (!wf) return { ok: false, error: '工作流不存在' };
    const result = wf.removeConnection(connId);
    return { ok: result };
  });

  // ============================================================
  // Multi-Agent Orchestrator 多 Agent 协作系统
  // ============================================================

  ipcMain.handle('agent:createTeam', async (event, config) => {
    if (!multiAgentOrchestrator) return { ok: false, error: 'Multi-Agent Orchestrator 未初始化' };
    const team = multiAgentOrchestrator.createTeam(config);
    return { ok: true, team: team.toJSON() };
  });

  ipcMain.handle('agent:getTeam', async (event, { id }) => {
    if (!multiAgentOrchestrator) return { ok: false, error: 'Multi-Agent Orchestrator 未初始化' };
    const team = multiAgentOrchestrator.getTeam(id);
    return { ok: !!team, team: team ? team.toJSON() : null };
  });

  ipcMain.handle('agent:listTeams', async () => {
    if (!multiAgentOrchestrator) return { ok: false, error: 'Multi-Agent Orchestrator 未初始化' };
    const list = multiAgentOrchestrator.listTeams();
    return { ok: true, teams: list };
  });

  ipcMain.handle('agent:deleteTeam', async (event, { id }) => {
    if (!multiAgentOrchestrator) return { ok: false, error: 'Multi-Agent Orchestrator 未初始化' };
    const result = multiAgentOrchestrator.deleteTeam(id);
    return { ok: result };
  });

  ipcMain.handle('agent:createPresetTeam', async (event, { type }) => {
    if (!multiAgentOrchestrator) return { ok: false, error: 'Multi-Agent Orchestrator 未初始化' };
    const team = multiAgentOrchestrator.createPresetTeam(type);
    return { ok: !!team, team: team ? team.toJSON() : null };
  });

  ipcMain.handle('agent:addMember', async (event, { teamId, memberConfig }) => {
    if (!multiAgentOrchestrator) return { ok: false, error: 'Multi-Agent Orchestrator 未初始化' };
    const team = multiAgentOrchestrator.getTeam(teamId);
    if (!team) return { ok: false, error: '团队不存在' };
    const member = team.addMember(memberConfig);
    return { ok: true, member: member.toJSON() };
  });

  ipcMain.handle('agent:removeMember', async (event, { teamId, memberId }) => {
    if (!multiAgentOrchestrator) return { ok: false, error: 'Multi-Agent Orchestrator 未初始化' };
    const team = multiAgentOrchestrator.getTeam(teamId);
    if (!team) return { ok: false, error: '团队不存在' };
    const result = team.removeMember(memberId);
    return { ok: result };
  });

  ipcMain.handle('agent:runTask', async (event, { teamId, task }) => {
    if (!multiAgentOrchestrator) return { ok: false, error: 'Multi-Agent Orchestrator 未初始化' };
    const result = await multiAgentOrchestrator.runTask(teamId, task);
    return result;
  });

  // ============================================================
  // Trigger Engine 触发器引擎
  // ============================================================

  ipcMain.handle('trigger:create', async (event, config) => {
    if (!triggerEngine) return { ok: false, error: 'Trigger Engine 未初始化' };
    const trigger = triggerEngine.createTrigger(config);
    return { ok: true, trigger: trigger.toJSON() };
  });

  ipcMain.handle('trigger:get', async (event, { id }) => {
    if (!triggerEngine) return { ok: false, error: 'Trigger Engine 未初始化' };
    const trigger = triggerEngine.getTrigger(id);
    return { ok: !!trigger, trigger: trigger ? trigger.toJSON() : null };
  });

  ipcMain.handle('trigger:list', async () => {
    if (!triggerEngine) return { ok: false, error: 'Trigger Engine 未初始化' };
    const list = triggerEngine.listTriggers();
    return { ok: true, triggers: list };
  });

  ipcMain.handle('trigger:delete', async (event, { id }) => {
    if (!triggerEngine) return { ok: false, error: 'Trigger Engine 未初始化' };
    const result = triggerEngine.deleteTrigger(id);
    return { ok: result };
  });

  ipcMain.handle('trigger:enable', async (event, { id }) => {
    if (!triggerEngine) return { ok: false, error: 'Trigger Engine 未初始化' };
    const result = triggerEngine.enableTrigger(id);
    return { ok: result };
  });

  ipcMain.handle('trigger:disable', async (event, { id }) => {
    if (!triggerEngine) return { ok: false, error: 'Trigger Engine 未初始化' };
    const result = triggerEngine.disableTrigger(id);
    return { ok: result };
  });

  ipcMain.handle('trigger:createPreset', async (event, { type }) => {
    if (!triggerEngine) return { ok: false, error: 'Trigger Engine 未初始化' };
    const trigger = triggerEngine.createPresetTrigger(type);
    return { ok: !!trigger, trigger: trigger ? trigger.toJSON() : null };
  });

  ipcMain.handle('trigger:runNow', async (event, { id }) => {
    if (!triggerEngine) return { ok: false, error: 'Trigger Engine 未初始化' };
    const trigger = triggerEngine.getTrigger(id);
    if (!trigger) return { ok: false, error: '触发器不存在' };
    const result = await triggerEngine._runTrigger(trigger, { manual: true });
    return result;
  });

  // ============================================================
  // 积分与会员系统
  // ============================================================
  ipcMain.handle('credits:getUser', async (event, { userId }) => {
    if (!creditsSystem) return { ok: false, error: '积分系统未初始化' };
    const uid = userId || 'local_user';
    return { ok: true, user: creditsSystem.getUser(uid) };
  });

  ipcMain.handle('credits:getAvailable', async (event, { userId }) => {
    if (!creditsSystem) return { ok: false, error: '积分系统未初始化' };
    const uid = userId || 'local_user';
    return { ok: true, credits: creditsSystem.getAvailableCredits(uid) };
  });

  ipcMain.handle('credits:getPlans', async () => {
    if (!creditsSystem) return { ok: false, error: '积分系统未初始化' };
    return { ok: true, plans: creditsSystem.getAllPlans() };
  });

  ipcMain.handle('credits:getPackages', async () => {
    if (!creditsSystem) return { ok: false, error: '积分系统未初始化' };
    return { ok: true, packages: creditsSystem.getCreditPackages() };
  });

  ipcMain.handle('credits:subscribe', async (event, { userId, planId }) => {
    if (!creditsSystem) return { ok: false, error: '积分系统未初始化' };
    const uid = userId || 'local_user';
    const result = creditsSystem.subscribePlan(uid, planId);
    return result;
  });

  ipcMain.handle('credits:recharge', async (event, { userId, packageId, operator }) => {
    if (!creditsSystem) return { ok: false, error: '积分系统未初始化' };
    if (operator !== 'admin') {
      const auth = loadAuth();
      if (!auth || !auth.user || auth.user.role !== 'admin') {
        return { ok: false, error: '需要管理员权限' };
      }
    }
    const uid = userId || 'local_user';
    const pkg = creditsSystem.getCreditPackages().find(p => p.id === packageId);
    if (!pkg) return { ok: false, error: '套餐不存在' };
    const totalCredits = pkg.credits + pkg.bonus;
    creditsSystem.addCredits(uid, totalCredits, `购买${pkg.name}`);
    return { ok: true, credits: totalCredits, user: creditsSystem.getUser(uid) };
  });

  ipcMain.handle('credits:transactions', async (event, { userId, limit, offset }) => {
    if (!creditsSystem) return { ok: false, error: '积分系统未初始化' };
    const uid = userId || 'local_user';
    return { ok: true, transactions: creditsSystem.getTransactions(uid, limit || 50, offset || 0) };
  });

  ipcMain.handle('credits:usageStats', async (event, { userId, days }) => {
    if (!creditsSystem) return { ok: false, error: '积分系统未初始化' };
    const uid = userId || 'local_user';
    return { ok: true, stats: creditsSystem.getUsageStats(uid, days || 30) };
  });

  ipcMain.handle('credits:syncFromCloud', async (event, { username, cloudData }) => {
    if (!creditsSystem) return { ok: false, error: '积分系统未初始化' };
    return { ok: creditsSystem.syncFromCloud(username, cloudData) };
  });

  ipcMain.handle('credits:summary', async (event, { userId }) => {
    if (!creditsSystem) return { ok: false, error: '积分系统未初始化' };
    return { ok: true, summary: creditsSystem.getUserSummary(userId) };
  });

  // ============================================================
  // 市场与模板系统
  // ============================================================
  ipcMain.handle('market:listSkills', async (event, { keyword, category }) => {
    if (!marketManager) return { ok: false, error: '市场系统未初始化' };
    return { ok: true, skills: marketManager.listSkills(keyword, category) };
  });

  ipcMain.handle('market:getSkill', async (event, { id }) => {
    if (!marketManager) return { ok: false, error: '市场系统未初始化' };
    return { ok: true, skill: marketManager.getSkill(id) };
  });

  ipcMain.handle('market:installSkill', async (event, { skillData }) => {
    if (!marketManager) return { ok: false, error: '市场系统未初始化' };
    const skill = marketManager.installSkill(skillData);
    return { ok: !!skill, skill };
  });

  ipcMain.handle('market:uninstallSkill', async (event, { id }) => {
    if (!marketManager) return { ok: false, error: '市场系统未初始化' };
    return { ok: marketManager.uninstallSkill(id) };
  });

  ipcMain.handle('market:exportSkill', async (event, { id }) => {
    if (!marketManager) return { ok: false, error: '市场系统未初始化' };
    return { ok: true, data: marketManager.exportSkill(id) };
  });

  ipcMain.handle('market:skillCategories', async () => {
    if (!marketManager) return { ok: false, error: '市场系统未初始化' };
    return { ok: true, categories: marketManager.getSkillCategories() };
  });

  ipcMain.handle('market:listAgents', async (event, { keyword }) => {
    if (!marketManager) return { ok: false, error: '市场系统未初始化' };
    return { ok: true, agents: marketManager.listAgents(keyword) };
  });

  ipcMain.handle('market:getAgent', async (event, { id }) => {
    if (!marketManager) return { ok: false, error: '市场系统未初始化' };
    return { ok: true, agent: marketManager.getAgent(id) };
  });

  ipcMain.handle('market:installAgent', async (event, { agentData }) => {
    if (!marketManager) return { ok: false, error: '市场系统未初始化' };
    const agent = marketManager.installAgent(agentData);
    return { ok: !!agent, agent };
  });

  ipcMain.handle('market:uninstallAgent', async (event, { id }) => {
    if (!marketManager) return { ok: false, error: '市场系统未初始化' };
    return { ok: marketManager.uninstallAgent(id) };
  });

  ipcMain.handle('market:exportAgent', async (event, { id }) => {
    if (!marketManager) return { ok: false, error: '市场系统未初始化' };
    return { ok: true, data: marketManager.exportAgent(id) };
  });

  ipcMain.handle('market:listWorkflowTemplates', async (event, { keyword }) => {
    if (!marketManager) return { ok: false, error: '市场系统未初始化' };
    return { ok: true, templates: marketManager.listWorkflowTemplates(keyword) };
  });

  ipcMain.handle('market:getWorkflowTemplate', async (event, { id }) => {
    if (!marketManager) return { ok: false, error: '市场系统未初始化' };
    return { ok: true, template: marketManager.getWorkflowTemplate(id) };
  });

  ipcMain.handle('market:installWorkflowTemplate', async (event, { templateData }) => {
    if (!marketManager) return { ok: false, error: '市场系统未初始化' };
    const t = marketManager.installWorkflowTemplate(templateData);
    return { ok: !!t, template: t };
  });

  ipcMain.handle('market:uninstallWorkflowTemplate', async (event, { id }) => {
    if (!marketManager) return { ok: false, error: '市场系统未初始化' };
    return { ok: marketManager.uninstallWorkflowTemplate(id) };
  });

  ipcMain.handle('market:exportWorkflowTemplate', async (event, { id }) => {
    if (!marketManager) return { ok: false, error: '市场系统未初始化' };
    return { ok: true, data: marketManager.exportWorkflowTemplate(id) };
  });

  // ============================================================
  // M3: 代码沙箱与自动测试
  // 安全：所有 sandbox IPC handler 必须校验 filePath 在允许范围内，
  // 防止渲染进程被 XSS 后通过 sandbox 接口任意读写系统文件。
  // ============================================================

  ipcMain.handle('sandbox:snapshot', async (event, { filePath }) => {
    if (!filePath || !isPathAllowed(filePath)) return { ok: false, error: '安全限制：路径不在允许范围内' };
    const snap = sandboxManager.snapshot(filePath);
    return { ok: !!snap, snapshot: snap };
  });

  ipcMain.handle('sandbox:snapshotAll', async (event, { filePaths }) => {
    if (!Array.isArray(filePaths)) return { ok: false, error: '参数错误' };
    for (const fp of filePaths) {
      if (!isPathAllowed(fp)) return { ok: false, error: `安全限制：路径 ${fp} 不在允许范围内` };
    }
    const snaps = sandboxManager.snapshotAll(filePaths);
    return { ok: true, count: snaps.length };
  });

  ipcMain.handle('sandbox:rollback', async (event, { filePath }) => {
    if (!filePath || !isPathAllowed(filePath)) return { ok: false, error: '安全限制：路径不在允许范围内' };
    return sandboxManager.rollback(filePath);
  });

  ipcMain.handle('sandbox:rollbackAll', () => {
    return { ok: true, results: sandboxManager.rollbackAll() };
  });

  ipcMain.handle('sandbox:getDiff', async (event, { filePath }) => {
    if (!filePath || !isPathAllowed(filePath)) return { ok: false, error: '安全限制：路径不在允许范围内' };
    return sandboxManager.getDiff(filePath);
  });

  ipcMain.handle('sandbox:syntaxCheck', async (event, { filePath }) => {
    if (!filePath || !isPathAllowed(filePath)) return { ok: false, error: '安全限制：路径不在允许范围内' };
    return sandboxManager.syntaxCheck(filePath);
  });

  ipcMain.handle('sandbox:safeWrite', async (event, { filePath, content }) => {
    if (!filePath || !isPathAllowed(filePath)) return { ok: false, error: '安全限制：路径不在允许范围内' };
    return sandboxManager.safeWrite(filePath, content);
  });

  ipcMain.handle('sandbox:safeWriteBatch', async (event, { edits }) => {
    if (!Array.isArray(edits)) return { ok: false, error: '参数错误' };
    for (const edit of edits) {
      if (!edit.filePath || !isPathAllowed(edit.filePath)) return { ok: false, error: `安全限制：路径 ${edit.filePath} 不在允许范围内` };
    }
    return sandboxManager.safeWriteBatch(edits);
  });

  ipcMain.handle('sandbox:runTests', async (event, { workspacePath }) => {
    const ws = workspacePath || currentWorkspace;
    if (!ws || !isPathAllowed(ws)) return { ok: false, error: '安全限制：路径不在允许范围内' };
    return sandboxManager.runProjectTests(ws);
  });

  // ============================================================
  // M3: Git 集成
  // ============================================================

  if (!gitManager) gitManager = new GitManager();

  // 安全：校验 git 操作的工作区路径，防止在任意目录执行 git 命令。
  function _guardGitWs(wsPath) {
    const target = wsPath || currentWorkspace;
    if (!isPathAllowed(target)) return null;
    return target;
  }
  const _wsBlocked = { ok: false, error: '安全限制：工作区路径不在允许范围内' };

  ipcMain.handle('git:status', async (event, { workspacePath }) => {
    const ws = _guardGitWs(workspacePath); if (!ws) return _wsBlocked;
    const r = await gitManager.status(ws);
    return { ok: r.ok, output: r.stdout, error: r.stderr };
  });

  ipcMain.handle('git:stage', async (event, { workspacePath, files }) => {
    const ws = _guardGitWs(workspacePath); if (!ws) return _wsBlocked;
    const r = await gitManager.stage(ws, files);
    return { ok: r.ok, output: r.stdout, error: r.stderr };
  });

  ipcMain.handle('git:unstage', async (event, { workspacePath, files }) => {
    const ws = _guardGitWs(workspacePath); if (!ws) return _wsBlocked;
    const r = await gitManager.unstage(ws, files);
    return { ok: r.ok, output: r.stdout, error: r.stderr };
  });

  ipcMain.handle('git:commit', async (event, { workspacePath, message }) => {
    const ws = _guardGitWs(workspacePath); if (!ws) return _wsBlocked;
    const r = await gitManager.commit(ws, message);
    return { ok: r.ok, output: r.stdout, error: r.stderr };
  });

  ipcMain.handle('git:push', async (event, { workspacePath, remote, branch }) => {
    const ws = _guardGitWs(workspacePath); if (!ws) return _wsBlocked;
    const r = await gitManager.push(ws, remote, branch);
    return { ok: r.ok, output: r.stdout, error: r.stderr };
  });

  ipcMain.handle('git:pull', async (event, { workspacePath, remote, branch }) => {
    const ws = _guardGitWs(workspacePath); if (!ws) return _wsBlocked;
    const r = await gitManager.pull(ws, remote, branch);
    return { ok: r.ok, output: r.stdout, error: r.stderr };
  });

  ipcMain.handle('git:branches', async (event, { workspacePath }) => {
    const ws = _guardGitWs(workspacePath); if (!ws) return _wsBlocked;
    const branches = await gitManager.branches(ws);
    const current = await gitManager.currentBranch(ws);
    return { ok: true, branches, current };
  });

  ipcMain.handle('git:checkout', async (event, { workspacePath, branch }) => {
    const ws = _guardGitWs(workspacePath); if (!ws) return _wsBlocked;
    const r = await gitManager.checkout(ws, branch);
    return { ok: r.ok, output: r.stdout, error: r.stderr };
  });

  ipcMain.handle('git:createBranch', async (event, { workspacePath, branch }) => {
    const ws = _guardGitWs(workspacePath); if (!ws) return _wsBlocked;
    const r = await gitManager.createBranch(ws, branch);
    return { ok: r.ok, output: r.stdout, error: r.stderr };
  });

  ipcMain.handle('git:log', async (event, { workspacePath, count }) => {
    const ws = _guardGitWs(workspacePath); if (!ws) return _wsBlocked;
    const logs = await gitManager.log(ws, count);
    return { ok: true, logs };
  });

  ipcMain.handle('git:blame', async (event, { workspacePath, filePath }) => {
    const ws = _guardGitWs(workspacePath); if (!ws) return _wsBlocked;
    // 同时校验 filePath 在工作区内
    if (filePath) {
      const fullFp = path.resolve(ws, filePath);
      if (!isPathAllowed(fullFp)) return _wsBlocked;
    }
    const lines = await gitManager.blame(ws, filePath);
    return { ok: true, lines };
  });

  ipcMain.handle('git:diff', async (event, { workspacePath, staged }) => {
    const ws = _guardGitWs(workspacePath); if (!ws) return _wsBlocked;
    const r = await gitManager.diff(ws, staged);
    return { ok: r.ok, output: r.stdout, error: r.stderr };
  });

  ipcMain.handle('git:diffFile', async (event, { workspacePath, filePath, staged }) => {
    const ws = _guardGitWs(workspacePath); if (!ws) return _wsBlocked;
    if (filePath) {
      const fullFp = path.resolve(ws, filePath);
      if (!isPathAllowed(fullFp)) return _wsBlocked;
    }
    const r = await gitManager.diffFile(ws, filePath, staged);
    return { ok: r.ok, output: r.stdout, error: r.stderr };
  });

  ipcMain.handle('git:stash', async (event, { workspacePath }) => {
    const ws = _guardGitWs(workspacePath); if (!ws) return _wsBlocked;
    const r = await gitManager.stash(ws);
    return { ok: r.ok, output: r.stdout, error: r.stderr };
  });

  ipcMain.handle('git:stashPop', async (event, { workspacePath }) => {
    const ws = _guardGitWs(workspacePath); if (!ws) return _wsBlocked;
    const r = await gitManager.stashPop(ws);
    return { ok: r.ok, output: r.stdout, error: r.stderr };
  });

  ipcMain.handle('git:stashList', async (event, { workspacePath }) => {
    const ws = _guardGitWs(workspacePath); if (!ws) return _wsBlocked;
    const list = await gitManager.stashList(ws);
    return { ok: true, list };
  });

  ipcMain.handle('git:isRepo', async (event, { workspacePath }) => {
    const ws = _guardGitWs(workspacePath); if (!ws) return _wsBlocked;
    return { ok: true, isRepo: gitManager.isRepo(ws) };
  });

  // ============================================================
  // GitHub API 集成
  // ============================================================
  function getGithubManager(token) {
    if (!token) {
      // 尝试从存储中读取token
      const stored = store?.get?.('githubToken') || '';
      if (!stored) return null;
      token = stored;
    }
    if (!githubManager || githubManager.token !== token) {
      githubManager = new GitHubManager({ token });
      githubManager.token = token;
    }
    return githubManager;
  }

  ipcMain.handle('github:setToken', async (event, { token }) => {
    try {
      if (store) store.set('githubToken', token);
      githubManager = new GitHubManager({ token });
      githubManager.token = token;
      const user = await githubManager.getAuthenticatedUser();
      return { ok: true, user };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('github:checkToken', async () => {
    const token = store?.get?.('githubToken') || '';
    if (!token) return { ok: false, authenticated: false };
    try {
      const mgr = getGithubManager(token);
      if (!mgr) return { ok: false, authenticated: false };
      const user = await mgr.getAuthenticatedUser();
      return { ok: true, authenticated: true, user };
    } catch (e) {
      return { ok: false, authenticated: false, error: e.message };
    }
  });

  ipcMain.handle('github:logout', async () => {
    if (store) store.delete('githubToken');
    githubManager = null;
    return { ok: true };
  });

  ipcMain.handle('github:repos', async (event, { page, perPage, type, sort, direction } = {}) => {
    try {
      const mgr = getGithubManager();
      if (!mgr) return { ok: false, error: '未设置GitHub Token' };
      const repos = await mgr.listRepositories({ page, perPage, type, sort, direction });
      return { ok: true, repos };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('github:repo', async (event, { owner, repo } = {}) => {
    try {
      const mgr = getGithubManager();
      if (!mgr) return { ok: false, error: '未设置GitHub Token' };
      const data = await mgr.getRepository(owner, repo);
      return { ok: true, repo: data };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('github:createRepo', async (event, { name, description, private, autoInit } = {}) => {
    try {
      const mgr = getGithubManager();
      if (!mgr) return { ok: false, error: '未设置GitHub Token' };
      const repo = await mgr.createRepository({ name, description, private, autoInit });
      return { ok: true, repo };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('github:issues', async (event, { owner, repo, state, page, perPage } = {}) => {
    try {
      const mgr = getGithubManager();
      if (!mgr) return { ok: false, error: '未设置GitHub Token' };
      const issues = await mgr.listIssues(owner, repo, { state, page, perPage });
      return { ok: true, issues };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('github:createIssue', async (event, { owner, repo, title, body, labels } = {}) => {
    try {
      const mgr = getGithubManager();
      if (!mgr) return { ok: false, error: '未设置GitHub Token' };
      const issue = await mgr.createIssue(owner, repo, { title, body, labels });
      return { ok: true, issue };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('github:pulls', async (event, { owner, repo, state, page, perPage } = {}) => {
    try {
      const mgr = getGithubManager();
      if (!mgr) return { ok: false, error: '未设置GitHub Token' };
      const prs = await mgr.listPullRequests(owner, repo, { state, page, perPage });
      return { ok: true, pulls: prs };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('github:createPull', async (event, { owner, repo, title, head, base, body } = {}) => {
    try {
      const mgr = getGithubManager();
      if (!mgr) return { ok: false, error: '未设置GitHub Token' };
      const pr = await mgr.createPullRequest(owner, repo, { title, head, base, body });
      return { ok: true, pull: pr };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('github:mergePull', async (event, { owner, repo, number, commitTitle, commitMessage, mergeMethod } = {}) => {
    try {
      const mgr = getGithubManager();
      if (!mgr) return { ok: false, error: '未设置GitHub Token' };
      const result = await mgr.mergePullRequest(owner, repo, number, { commitTitle, commitMessage, mergeMethod });
      return { ok: true, result };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('github:branches', async (event, { owner, repo, page, perPage } = {}) => {
    try {
      const mgr = getGithubManager();
      if (!mgr) return { ok: false, error: '未设置GitHub Token' };
      const branches = await mgr.listBranches(owner, repo, { page, perPage });
      return { ok: true, branches };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('github:workflows', async (event, { owner, repo, page, perPage } = {}) => {
    try {
      const mgr = getGithubManager();
      if (!mgr) return { ok: false, error: '未设置GitHub Token' };
      const runs = await mgr.listWorkflowRuns(owner, repo, { page, perPage });
      return { ok: true, runs };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('github:searchCode', async (event, { q, page, perPage } = {}) => {
    try {
      const mgr = getGithubManager();
      if (!mgr) return { ok: false, error: '未设置GitHub Token' };
      const results = await mgr.searchCode(q, { page, perPage });
      return { ok: true, results };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('github:searchRepos', async (event, { q, page, perPage, sort, order } = {}) => {
    try {
      const mgr = getGithubManager();
      if (!mgr) return { ok: false, error: '未设置GitHub Token' };
      const results = await mgr.searchRepositories(q, { page, perPage, sort, order });
      return { ok: true, results };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('github:user', async (event, { username } = {}) => {
    try {
      const mgr = getGithubManager();
      if (!mgr) return { ok: false, error: '未设置GitHub Token' };
      const user = username ? await mgr.getUser(username) : await mgr.getAuthenticatedUser();
      return { ok: true, user };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  // ============================================================
  // 增强浏览器自动化（BrowserUseEnhanced）
  // 灵感来源：Browser Use 开源项目
  // 通过 child_process 调用已安装的 Playwright/Puppeteer
  // 未安装时自动降级为 fetch 模式
  // ============================================================
  function getBrowserUseEnhanced() {
    if (!browserUseEnhanced) {
      browserUseEnhanced = new BrowserUseEnhanced();
    }
    return browserUseEnhanced;
  }

  ipcMain.handle('browser:navigate', async (event, { url } = {}) => {
    try {
      if (!url) return { ok: false, error: 'url 不能为空' };
      const bue = getBrowserUseEnhanced();
      const result = await bue.navigate(url);
      return { ok: true, result };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('browser:screenshot', async (event, { fullPage } = {}) => {
    try {
      const bue = getBrowserUseEnhanced();
      const result = await bue.screenshot({ fullPage: !!fullPage });
      return { ok: true, result };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('browser:extract', async (event, { selector } = {}) => {
    try {
      const bue = getBrowserUseEnhanced();
      const result = await bue.extract(selector);
      return { ok: true, result };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('browser:click', async (event, { selector } = {}) => {
    try {
      if (!selector) return { ok: false, error: 'selector 不能为空' };
      const bue = getBrowserUseEnhanced();
      const result = await bue.click(selector);
      return { ok: true, result };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('browser:type', async (event, { selector, text } = {}) => {
    try {
      if (!selector) return { ok: false, error: 'selector 不能为空' };
      const bue = getBrowserUseEnhanced();
      const result = await bue.type(selector, text);
      return { ok: true, result };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('browser:smart_action', async (event, { instruction } = {}) => {
    try {
      if (!instruction) return { ok: false, error: 'instruction 不能为空' };
      const bue = getBrowserUseEnhanced();
      const result = await bue.smart_action(instruction);
      return { ok: true, result };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('browser:start_recording', async () => {
    try {
      const bue = getBrowserUseEnhanced();
      const result = bue.start_recording();
      return { ok: true, result };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('browser:stop_recording', async () => {
    try {
      const bue = getBrowserUseEnhanced();
      const result = bue.stop_recording();
      return { ok: true, result };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('browser:replay', async (event, { recording } = {}) => {
    try {
      const bue = getBrowserUseEnhanced();
      const result = await bue.replay(recording);
      return { ok: true, result };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  // ============================================================
  // M3: DAP 调试器
  // ============================================================

  if (!debugManager) debugManager = new DebugManager();

  ipcMain.handle('debug:startPython', async (event, { scriptPath, workspacePath, breakpoints }) => {
    // 安全：校验脚本路径和工作区路径，防止调试任意系统脚本。
    const ws = workspacePath || currentWorkspace;
    if (!isPathAllowed(ws)) return { ok: false, error: '安全限制：工作区路径不在允许范围内' };
    if (scriptPath && !isPathAllowed(scriptPath)) {
      return { ok: false, error: '安全限制：脚本路径不在允许范围内' };
    }
    const id = await debugManager.startPython(scriptPath, ws, breakpoints);
    return { ok: true, id };
  });

  ipcMain.handle('debug:startNode', async (event, { scriptPath, workspacePath, breakpoints }) => {
    // 安全：校验脚本路径和工作区路径，防止调试任意系统脚本。
    const ws = workspacePath || currentWorkspace;
    if (!isPathAllowed(ws)) return { ok: false, error: '安全限制：工作区路径不在允许范围内' };
    if (scriptPath && !isPathAllowed(scriptPath)) {
      return { ok: false, error: '安全限制：脚本路径不在允许范围内' };
    }
    const id = await debugManager.startNode(scriptPath, ws, breakpoints);
    return { ok: true, id };
  });

  ipcMain.handle('debug:getOutput', async (event, { id }) => {
    return debugManager.getOutput(id);
  });

  ipcMain.handle('debug:stop', async (event, { id }) => {
    return debugManager.stop(id);
  });

  ipcMain.handle('debug:list', () => {
    return { ok: true, sessions: debugManager.list() };
  });

  // ============================================================
  // M3: SSH 远程开发
  // ============================================================

  if (!sshManager) sshManager = new SSHManager();

  ipcMain.handle('ssh:connect', async (event, { host, port, username }) => {
    return sshManager.connect({ host, port, username });
  });

  ipcMain.handle('ssh:disconnect', async (event, { id }) => {
    return sshManager.disconnect(id);
  });

  ipcMain.handle('ssh:listDir', async (event, { id, remotePath }) => {
    return sshManager.listDir(id, remotePath);
  });

  ipcMain.handle('ssh:readFile', async (event, { id, remotePath }) => {
    return sshManager.readFile(id, remotePath);
  });

  ipcMain.handle('ssh:writeFile', async (event, { id, remotePath, content }) => {
    return sshManager.writeFile(id, remotePath, content);
  });

  ipcMain.handle('ssh:deleteFile', async (event, { id, remotePath }) => {
    return sshManager.deleteFile(id, remotePath);
  });

  ipcMain.handle('ssh:exec', async (event, { id, command }) => {
    // 安全：记录远程命令执行日志，便于审计。
    if (!command || typeof command !== 'string') {
      return { ok: false, error: '命令不能为空' };
    }
    try { console.log(`[ssh:exec] connection=${id} cmd=${command.slice(0, 200)}`); } catch (_) {}
    return sshManager.exec(id, command);
  });

  ipcMain.handle('ssh:list', () => {
    return { ok: true, connections: sshManager.list() };
  });

  // ============================================================
  // M5: AI 内联代码补全
  // ============================================================

  if (!completionManager) completionManager = new CompletionManager();

  ipcMain.handle('completion:get', async (event, { code, suffix, language, filePath }) => {
    const result = await completionManager.getCompletion({ code, suffix, language, filePath });
    return { ok: true, completion: result };
  });

  ipcMain.handle('completion:clearCache', () => {
    completionManager.clearCache();
    return { ok: true };
  });

  // ============================================================
  // M5: AI 代码审查
  // ============================================================

  if (!codeReviewManager) codeReviewManager = new CodeReviewManager();

  ipcMain.handle('review:file', async (event, { code, filePath, language }) => {
    const result = await codeReviewManager.reviewFile({ code, filePath, language });
    return { ok: true, review: result };
  });

  ipcMain.handle('review:project', async (event, { files, workspacePath }) => {
    const result = await codeReviewManager.reviewProject({ files, workspacePath });
    return { ok: true, ...result };
  });

  ipcMain.handle('review:list', () => {
    return { ok: true, reviews: codeReviewManager.listReviews() };
  });

  // ============================================================
  // M5: AI 重构
  // ============================================================

  if (!refactorManager) refactorManager = new RefactorManager();

  ipcMain.handle('refactor:execute', async (event, { code, filePath, language, operation, selection }) => {
    const result = await refactorManager.refactor({ code, filePath, language, operation, selection });
    return { ok: !result.error, ...result };
  });

  ipcMain.handle('refactor:operations', () => {
    return { ok: true, operations: refactorManager.getOperations() };
  });

  // ============================================================
  // M5: 智能上下文管理
  // ============================================================

  if (!contextManager) contextManager = new ContextManager();

  ipcMain.handle('context:collect', async (event, { task, workspacePath, openFiles, currentFile }) => {
    const context = await contextManager.collectContext({ task, workspacePath, openFiles, currentFile });
    return { ok: true, context };
  });

  ipcMain.handle('context:buildPrompt', (event, { context }) => {
    const prompt = contextManager.buildContextPrompt(context);
    return { ok: true, prompt };
  });

  // ============================================================
  // M5: 键盘宏录制
  // ============================================================

  if (!macroManager) macroManager = new MacroManager();

  ipcMain.handle('macro:start', (event, { name }) => {
    return macroManager.startRecording(name);
  });

  ipcMain.handle('macro:stop', () => {
    return macroManager.stopRecording();
  });

  ipcMain.handle('macro:record', (event, { event: keyEvent }) => {
    macroManager.recordEvent(keyEvent);
    return { ok: true };
  });

  ipcMain.handle('macro:play', (event, { name }) => {
    return macroManager.getPlayback(name);
  });

  ipcMain.handle('macro:list', () => {
    return { ok: true, macros: macroManager.list() };
  });

  ipcMain.handle('macro:delete', (event, { name }) => {
    return macroManager.delete(name);
  });

  ipcMain.handle('macro:isRecording', () => {
    return { ok: true, recording: macroManager.isRecording() };
  });

  // ============================================================
  // M5: Docker 容器集成
  // ============================================================

  if (!dockerManager) dockerManager = new DockerManager();

  ipcMain.handle('docker:check', async () => {
    return dockerManager.checkAvailability();
  });

  ipcMain.handle('docker:listContainers', async () => {
    return dockerManager.listContainers();
  });

  ipcMain.handle('docker:listImages', async () => {
    return dockerManager.listImages();
  });

  ipcMain.handle('docker:start', async (event, { nameOrId }) => {
    return dockerManager.startContainer(nameOrId);
  });

  ipcMain.handle('docker:stop', async (event, { nameOrId }) => {
    return dockerManager.stopContainer(nameOrId);
  });

  ipcMain.handle('docker:restart', async (event, { nameOrId }) => {
    return dockerManager.restartContainer(nameOrId);
  });

  ipcMain.handle('docker:remove', async (event, { nameOrId }) => {
    return dockerManager.removeContainer(nameOrId);
  });

  ipcMain.handle('docker:logs', async (event, { nameOrId, tail }) => {
    return dockerManager.containerLogs(nameOrId, tail);
  });

  ipcMain.handle('docker:exec', async (event, { nameOrId, command }) => {
    return dockerManager.execInContainer(nameOrId, command);
  });

  ipcMain.handle('docker:pull', async (event, { image }) => {
    return dockerManager.pullImage(image);
  });

  ipcMain.handle('docker:composeUp', async (event, { composeFile, cwd }) => {
    return dockerManager.composeUp(composeFile, cwd);
  });

  ipcMain.handle('docker:composeDown', async (event, { composeFile, cwd }) => {
    return dockerManager.composeDown(composeFile, cwd);
  });

  // ============================================================
  // M5: Jupyter 笔记本
  // ============================================================

  if (!jupyterManager) jupyterManager = new JupyterManager();

  ipcMain.handle('jupyter:start', async (event, { workspacePath }) => {
    return jupyterManager.startServer(workspacePath);
  });

  ipcMain.handle('jupyter:stop', () => {
    return jupyterManager.stopServer();
  });

  ipcMain.handle('jupyter:createNotebook', (event, { filePath }) => {
    return jupyterManager.createNotebook(filePath);
  });

  ipcMain.handle('jupyter:readNotebook', (event, { filePath }) => {
    return jupyterManager.readNotebookCode(filePath);
  });

  ipcMain.handle('jupyter:status', () => {
    return { ok: true, ...jupyterManager.getStatus() };
  });

  // ============================================================
  // M5: CI/CD 面板
  // ============================================================

  if (!cicdManager) cicdManager = new CicdManager();

  ipcMain.handle('cicd:detect', (event, { workspacePath }) => {
    return cicdManager.detectConfig(workspacePath);
  });

  ipcMain.handle('cicd:runNpm', async (event, { workspacePath, script }) => {
    return cicdManager.runNpmScript(workspacePath, script);
  });

  ipcMain.handle('cicd:runMake', async (event, { workspacePath, target }) => {
    return cicdManager.runMake(workspacePath, target);
  });

  ipcMain.handle('cicd:runCommand', async (event, { workspacePath, command }) => {
    return cicdManager.runCommand(workspacePath, command);
  });

  ipcMain.handle('cicd:runDocker', async (event, { workspacePath, dockerfile, tag }) => {
    return cicdManager.runDockerBuild(workspacePath, dockerfile, tag);
  });

  // ============================================================
  // M5: Mermaid 图表
  // ============================================================

  if (!mermaidManager) mermaidManager = new MermaidManager();

  ipcMain.handle('mermaid:render', async (event, { diagram, format, theme }) => {
    return mermaidManager.render(diagram, { format, theme });
  });

  ipcMain.handle('mermaid:flowchart', async (event, { code, language }) => {
    return mermaidManager.generateFlowchart(code, language);
  });

  ipcMain.handle('mermaid:classDiagram', async (event, { code, language }) => {
    return mermaidManager.generateClassDiagram(code, language);
  });

  // ============================================================
  // M5: 插件 SDK
  // ============================================================

  if (!pluginSDK) pluginSDK = new PluginSDK();

  ipcMain.handle('plugin:init', (event, { pluginDir }) => {
    pluginSDK.init(pluginDir);
    return { ok: true };
  });

  ipcMain.handle('plugin:create', (event, { name, options }) => {
    return pluginSDK.createPlugin(name, options);
  });

  ipcMain.handle('plugin:remove', (event, { name }) => {
    return pluginSDK.removePlugin(name);
  });

  ipcMain.handle('plugin:toggle', (event, { name }) => {
    return pluginSDK.togglePlugin(name);
  });

  ipcMain.handle('plugin:list', () => {
    return { ok: true, plugins: pluginSDK.listPlugins() };
  });

  ipcMain.handle('plugin:getContext', () => {
    return { ok: true, context: pluginSDK.getPluginContext() };
  });

  // ============================================================
  // 性能优化器 IPC
  // ============================================================

  if (!perfOptimizer) perfOptimizer = new PerfOptimizer();
  if (!streamOptimizer) streamOptimizer = new StreamOptimizer();

  ipcMain.handle('perf:stats', () => {
    return { ok: true, stats: perfOptimizer.getMemoryStats() };
  });

  ipcMain.handle('perf:cacheInvalidate', (event, { pattern }) => {
    perfOptimizer.cacheInvalidate(pattern);
    return { ok: true };
  });

  ipcMain.handle('perf:gc', () => {
    perfOptimizer.gc();
    return { ok: true };
  });

  ipcMain.handle('stream:chat', async (event, { messages, options }) => {
    const abortController = streamOptimizer.createAbortController();
    const result = await streamOptimizer.streamChat(messages, {
      ...options,
      signal: abortController.signal,
    });
    return { ok: true, result };
  });

  ipcMain.handle('stream:parallelTools', async (event, { toolCalls }) => {
    const results = await streamOptimizer.parallelTools(toolCalls);
    return { ok: true, results };
  });

  ipcMain.handle('stream:adaptiveTemp', (event, { taskType }) => {
    return { ok: true, temperature: streamOptimizer.adaptiveTemperature(taskType) };
  });

  // ============================================================
  // M6: 持久化缓存 IPC
  // ============================================================

  if (!persistentCache) persistentCache = new PersistentCache();

  ipcMain.handle('cache:get', (event, { key }) => {
    return { ok: true, value: persistentCache.get(key) };
  });

  ipcMain.handle('cache:set', (event, { key, value, ttl }) => {
    persistentCache.set(key, value, ttl || 300);
    return { ok: true };
  });

  ipcMain.handle('cache:delete', (event, { key }) => {
    persistentCache.delete(key);
    return { ok: true };
  });

  ipcMain.handle('cache:clear', () => {
    persistentCache.clear();
    return { ok: true };
  });

  ipcMain.handle('cache:stats', () => {
    return { ok: true, stats: persistentCache.stats() };
  });

  // ============================================================
  // M6: 代码索引 IPC
  // ============================================================

  if (!codeIndex) codeIndex = new CodeIndex();

  ipcMain.handle('index:build', (event, { workspacePath }) => {
    return { ok: true, ...codeIndex.indexWorkspace(workspacePath) };
  });

  ipcMain.handle('index:prefixSearch', (event, { query }) => {
    return { ok: true, ...codeIndex.prefixSearch(query) };
  });

  ipcMain.handle('index:fuzzySearch', (event, { query }) => {
    return { ok: true, ...codeIndex.fuzzySearch(query) };
  });

  ipcMain.handle('index:contentSearch', (event, { query }) => {
    return { ok: true, ...codeIndex.contentSearch(query) };
  });

  ipcMain.handle('index:onFileChange', (event, { event: fileEvent, filePath }) => {
    codeIndex.onFileChange(fileEvent, filePath);
    return { ok: true };
  });

  ipcMain.handle('index:stats', () => {
    return { ok: true, stats: codeIndex.stats() };
  });

  // ============================================================
  // M6: 连接池 IPC
  // ============================================================

  if (!connectionPool) connectionPool = new ConnectionPool();

  // 安全：SSRF 防护 — 拒绝非 HTTP(S) 协议和云元数据地址。
  function _isSsrfSafe(urlStr) {
    if (!urlStr || typeof urlStr !== 'string') return false;
    let parsed;
    try { parsed = new URL(urlStr); } catch (_) { return false; }
    // 仅允许 http/https 协议
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return false;
    // 拒绝云元数据地址（AWS/Azure/GCP），防止凭据泄露
    const hostname = parsed.hostname.toLowerCase();
    if (hostname === '169.254.169.254' || hostname === 'metadata.google.internal') return false;
    return true;
  }

  ipcMain.handle('pool:request', async (event, { options, body }) => {
    // SSRF 校验
    const reqUrl = (options && (options.url || options.href)) || options;
    if (!_isSsrfSafe(typeof reqUrl === 'string' ? reqUrl : (options && options.url))) {
      return { ok: false, error: '安全限制：请求协议或目标地址不被允许（SSRF 防护）' };
    }
    const result = await connectionPool.request(options, body);
    return { ok: true, result };
  });

  ipcMain.handle('pool:parallel', async (event, { requests }) => {
    if (Array.isArray(requests)) {
      for (const req of requests) {
        const reqUrl = (req && req.options && (req.options.url || req.options.href)) || (req && req.options);
        if (!_isSsrfSafe(typeof reqUrl === 'string' ? reqUrl : (req && req.options && req.options.url))) {
          return { ok: false, error: '安全限制：批量请求中包含不允许的地址（SSRF 防护）' };
        }
      }
    }
    const results = await connectionPool.parallelRequests(requests);
    return { ok: true, results };
  });

  ipcMain.handle('pool:stats', () => {
    return { ok: true, stats: connectionPool.stats() };
  });

  // ============================================================
  // M6: 增量解析 IPC
  // ============================================================

  if (!incrementalParser) incrementalParser = new IncrementalParser();

  ipcMain.handle('parser:parse', (event, { filePath, content }) => {
    return { ok: true, ...incrementalParser.parse(filePath, content) };
  });

  ipcMain.handle('parser:parseDiff', (event, { filePath, oldContent, newContent, changes }) => {
    return { ok: true, ...incrementalParser.parseDiff(filePath, oldContent, newContent, changes) };
  });

  ipcMain.handle('parser:monacoLang', (event, { filePath }) => {
    return { ok: true, ...incrementalParser.getMonacoLanguages(filePath) };
  });

  ipcMain.handle('parser:dependencyGraph', (event, { filePath }) => {
    return { ok: true, ...incrementalParser.getDependencyGraph(filePath) };
  });

  ipcMain.handle('parser:stats', () => {
    return { ok: true, stats: incrementalParser.stats() };
  });

  // ============================================================
  // M6: 性能监控 IPC
  // ============================================================

  if (!perfMonitor) perfMonitor = new PerfMonitor();

  ipcMain.handle('monitor:start', () => {
    perfMonitor.start();
    return { ok: true };
  });

  ipcMain.handle('monitor:stop', () => {
    perfMonitor.stop();
    return { ok: true };
  });

  ipcMain.handle('monitor:snapshot', () => {
    return { ok: true, snapshot: perfMonitor.getSnapshot() };
  });

  ipcMain.handle('monitor:bottlenecks', () => {
    return { ok: true, ...perfMonitor.detectBottlenecks() };
  });

  ipcMain.handle('monitor:report', () => {
    return { ok: true, report: perfMonitor.getReport() };
  });

  // ============================================================
  // M7: V8 快照 IPC
  // ============================================================

  if (!v8Snapshot) v8Snapshot = new V8SnapshotOptimizer();

  ipcMain.handle('v8:warmup', async (event, { modules }) => {
    const result = await v8Snapshot.warmup(modules || [
      path.join(__dirname, 'main.js'),
      path.join(__dirname, 'preload.js'),
    ]);
    return { ok: true, ...result };
  });

  ipcMain.handle('v8:stats', () => {
    return { ok: true, stats: v8Snapshot.stats() };
  });

  ipcMain.handle('v8:clear', () => {
    v8Snapshot.clear();
    return { ok: true };
  });

  // ============================================================
  // M7: SharedArrayBuffer IPC
  // ============================================================

  if (!sharedBuffer) sharedBuffer = new SharedBufferIPC();
  if (!renderWorker) renderWorker = new RenderWorker();

  ipcMain.handle('sab:allocate', (event, { id, size }) => {
    sharedBuffer.allocate(id, size);
    return { ok: true };
  });

  ipcMain.handle('sab:write', (event, { id, data, offset }) => {
    return { ok: sharedBuffer.write(id, data, offset) };
  });

  ipcMain.handle('sab:read', (event, { id, offset, length }) => {
    const view = sharedBuffer.read(id, offset, length);
    return { ok: true, data: view ? Buffer.from(view).toString('base64') : null };
  });

  ipcMain.handle('sab:release', (event, { id }) => {
    sharedBuffer.release(id);
    return { ok: true };
  });

  ipcMain.handle('sab:stats', () => {
    return { ok: true, stats: sharedBuffer.stats() };
  });

  // ============================================================
  // M7: 原生文件监听 IPC
  // ============================================================

  if (!fileWatcher) fileWatcher = new NativeFileWatcher();

  ipcMain.handle('watch:start', (event, { workspacePath }) => {
    return fileWatcher.watch(workspacePath);
  });

  ipcMain.handle('watch:stop', () => {
    fileWatcher.unwatch();
    return { ok: true };
  });

  ipcMain.handle('watch:stats', () => {
    return { ok: true, stats: fileWatcher.stats() };
  });

  // 文件变化事件转发
  fileWatcher.on('add', (files) => {
    if (mainWindow) mainWindow.webContents.send('files:added', files);
  });
  fileWatcher.on('change', (files) => {
    if (mainWindow) mainWindow.webContents.send('files:changed', files);
  });
  fileWatcher.on('delete', (files) => {
    if (mainWindow) mainWindow.webContents.send('files:deleted', files);
  });

  // ============================================================
  // M7: WASM 加速器 IPC
  // ============================================================

  if (!wasmAccelerator) wasmAccelerator = new WasmAccelerator();

  ipcMain.handle('wasm:regexSearch', (event, { text, pattern, flags }) => {
    const results = wasmAccelerator.fastRegexSearch(text, pattern, flags);
    return { ok: true, results };
  });

  ipcMain.handle('wasm:diff', (event, { oldText, newText }) => {
    const changes = wasmAccelerator.fastDiff(oldText, newText);
    return { ok: true, changes };
  });

  ipcMain.handle('wasm:fullTextSearch', async (event, { texts, query, maxResults }) => {
    const results = await wasmAccelerator.fastFullTextSearch(texts, query, maxResults);
    return { ok: true, results };
  });

  // ============================================================
  // M7: Arena 分配器 + 弱引用缓存 IPC
  // ============================================================

  if (!arenaAllocator) arenaAllocator = new ArenaAllocator();
  if (!weakRefCache) weakRefCache = new WeakRefCache();

  ipcMain.handle('arena:stats', () => {
    return { ok: true, stats: arenaAllocator.stats() };
  });

  ipcMain.handle('wrc:get', (event, { key }) => {
    return { ok: true, value: weakRefCache.get(key) };
  });

  ipcMain.handle('wrc:set', (event, { key, value }) => {
    weakRefCache.set(key, value);
    return { ok: true };
  });

  ipcMain.handle('wrc:stats', () => {
    return { ok: true, stats: weakRefCache.stats() };
  });

  // ============================================================
  // M7: 内容寻址存储 + 懒加载 IPC
  // ============================================================

  if (!casStorage) casStorage = new ContentAddressableStorage();
  if (!lazyRegistry) lazyRegistry = new LazyModuleRegistry();

  ipcMain.handle('cas:put', (event, { filePath, content }) => {
    return { ok: true, ...casStorage.put(filePath, content) };
  });

  ipcMain.handle('cas:get', (event, { filePath }) => {
    return { ok: true, content: casStorage.get(filePath) };
  });

  ipcMain.handle('cas:remove', (event, { filePath }) => {
    return { ok: casStorage.remove(filePath) };
  });

  ipcMain.handle('cas:stats', () => {
    return { ok: true, stats: casStorage.stats() };
  });

  ipcMain.handle('lazy:register', (event, { name, priority }) => {
    lazyRegistry.register(name, () => {
      try { return require(name); } catch { return null; }
    }, priority || 100);
    return { ok: true };
  });

  ipcMain.handle('lazy:loadAll', async () => {
    const results = await lazyRegistry.loadAll();
    return { ok: true, results };
  });

  ipcMain.handle('lazy:loadIdle', () => {
    lazyRegistry.loadIdle();
    return { ok: true };
  });

  ipcMain.handle('lazy:stats', () => {
    return { ok: true, stats: lazyRegistry.stats() };
  });

  // ============================================================
  // M7: WebSocket 多路复用 IPC
  // ============================================================

  if (!wsMultiplex) wsMultiplex = new WebSocketMultiplexer();

  ipcMain.handle('ws:connect', async () => {
    const result = await wsMultiplex.connect();
    return { ok: result };
  });

  ipcMain.handle('ws:request', async (event, { method, path, body }) => {
    const result = await wsMultiplex.request(method, path, body);
    return { ok: true, result };
  });

  ipcMain.handle('ws:multiplex', async (event, { requests }) => {
    const results = await wsMultiplex.multiplex(requests);
    return { ok: true, results };
  });

  ipcMain.handle('ws:stats', () => {
    return { ok: true, stats: wsMultiplex.stats() };
  });

  // ============================================================
  // 主站互通：用户认证 + 云端对话（扣减积分）
  // ============================================================
  // 云端基址：优先从环境变量 YNEX_CLOUD_BASE 读取，
  // 默认 ynexai.cn（备案完成后启用），便于切换而不修改代码。
  const CLOUD_BASE = process.env.YNEX_CLOUD_BASE || 'https://ynexai.cn';
  const authFile = path.join(app.getPath('userData'), 'auth.json');

  function loadAuth() {
    try {
      const data = fs.readFileSync(authFile, 'utf-8');
      return JSON.parse(data);
    } catch (e) { return null; }
  }
  function saveAuth(data) {
    try {
      fs.writeFileSync(authFile, JSON.stringify(data, null, 2), 'utf-8');
    } catch (e) {
      console.warn('[Y·NEX Desktop] 保存登录信息失败:', e.message);
    }
  }
  function clearAuth() {
    try { fs.unlinkSync(authFile); } catch (e) {}
  }
  function emitAuthChange(payload) {
    mainWindow?.webContents.send('auth:change', payload);
  }

  // 通用 HTTPS 请求到主站
  function cloudRequest(method, endpoint, body, token) {
    const https = require('https');
    const data = body ? JSON.stringify(body) : null;
    return new Promise((resolve) => {
      const url = new URL(CLOUD_BASE + endpoint);
      const options = {
        hostname: url.hostname,
        path: url.pathname + url.search,
        method,
        headers: {
          'Content-Type': 'application/json',
          'User-Agent': 'YNEX-Desktop/2.0',
          ...(data ? { 'Content-Length': Buffer.byteLength(data) } : {}),
          ...(token ? { 'Authorization': 'Bearer ' + token } : {}),
        },
        timeout: 60000,
        rejectUnauthorized: true,
      };
      const req = https.request(options, (res) => {
        let responseData = '';
        res.on('data', (chunk) => responseData += chunk);
        res.on('end', () => {
          let parsed;
          try { parsed = JSON.parse(responseData); }
          catch (e) { parsed = responseData; }
          resolve({ ok: res.statusCode < 300, status: res.statusCode, data: parsed });
        });
      });
      req.on('error', (e) => resolve({ ok: false, status: 0, error: e.message }));
      req.on('timeout', () => { req.destroy(); resolve({ ok: false, status: 0, error: '请求超时' }); });
      if (data) req.write(data);
      req.end();
    });
  }

  // 登录
  ipcMain.handle('auth:login', async (event, { username, password }) => {
    const r = await cloudRequest('POST', '/api/auth/login', { username, password });
    if (r.ok && r.data && r.data.ok && r.data.token) {
      const user = r.data.user || { username };
      saveAuth({ token: r.data.token, user });
      emitAuthChange({ logged: true, user });
      return { ok: true, user };
    }
    return { ok: false, error: (r.data && r.data.error) || '登录失败，请检查用户名和密码' };
  });

  // 注册
  ipcMain.handle('auth:register', async (event, data) => {
    const r = await cloudRequest('POST', '/api/auth/register', data);
    if (r.ok && r.data && r.data.ok) {
      if (r.data.token) {
        const user = r.data.user || { username: data.username };
        saveAuth({ token: r.data.token, user });
        emitAuthChange({ logged: true, user });
        return { ok: true, user: r.data.user, token: r.data.token };
      }
      return { ok: true, msg: r.data.msg || '注册成功，请登录' };
    }
    return { ok: false, error: (r.data && r.data.error) || '注册失败' };
  });

  // 登出
  ipcMain.handle('auth:logout', async () => {
    clearAuth();
    emitAuthChange({ logged: false });
    return { ok: true };
  });

  // 检查本地 token + 自动登录
  ipcMain.handle('auth:check', async () => {
    const auth = loadAuth();
    if (!auth || !auth.token) return { ok: false, logged: false };
    const r = await cloudRequest('GET', '/api/user/data', null, auth.token);
    if (r.ok && r.data && r.data.ok) {
      const d = r.data.data || r.data;
      const user = { ...(auth.user || {}), credits: d.credits !== undefined ? d.credits : auth.user?.credits };
      saveAuth({ token: auth.token, user });
      emitAuthChange({ logged: true, user });
      return { ok: true, logged: true, user };
    }
    // token 失效
    if (r.status === 401) clearAuth();
    return { ok: false, logged: false, error: '登录已过期，请重新登录' };
  });

  // 获取用户资料 + 积分
  ipcMain.handle('auth:profile', async () => {
    const auth = loadAuth();
    if (!auth || !auth.token) return { ok: false, error: '未登录' };
    const r = await cloudRequest('GET', '/api/user/data', null, auth.token);
    if (r.ok && r.data && r.data.ok) {
      const d = r.data.data || r.data;
      const user = { ...(auth.user || {}), credits: d.credits !== undefined ? d.credits : auth.user?.credits };
      saveAuth({ token: auth.token, user });
      return { ok: true, user };
    }
    return { ok: false, error: (r.data && r.data.error) || '获取资料失败' };
  });

  // 云端对话（走主站 /api/chat，扣减积分）
  ipcMain.handle('cloud:chat', async (event, { model, messages, rawModel }) => {
    const auth = loadAuth();
    if (!auth || !auth.token) return { ok: false, error: '未登录，请先登录', needLogin: true };
    const body = { model, messages };
    if (rawModel) body.rawModel = rawModel;
    const r = await cloudRequest('POST', '/api/chat', body, auth.token);
    if (r.ok) {
      // 更新本地积分
      const d = r.data && r.data.data ? r.data.data : r.data;
      if (d && d.credits !== undefined) {
        const user = { ...(auth.user || {}), credits: d.credits };
        saveAuth({ token: auth.token, user });
        emitAuthChange({ logged: true, user, creditsChanged: true });
      } else {
        // 主动拉取最新积分
        const pr = await cloudRequest('GET', '/api/user/data', null, auth.token);
        if (pr.ok && pr.data && pr.data.ok) {
          const pd = pr.data.data || pr.data;
          if (pd.credits !== undefined) {
            const user = { ...(auth.user || {}), credits: pd.credits };
            saveAuth({ token: auth.token, user });
            emitAuthChange({ logged: true, user, creditsChanged: true });
          }
        }
      }
      // 本地积分系统扣费（与云端积分独立核算）
      if (creditsSystem) {
        const d = r.data && r.data.data ? r.data.data : r.data;
        let answer = '';
        if (d && d.answer) answer = d.answer;
        else if (d && d.content) answer = d.content;
        else if (d && d.reply) answer = d.reply;
        if (answer) {
          const modelId = rawModel || model || 'default';
          const userId = (auth.user && (auth.user.username || auth.user.userId)) || 'local_user';
          const modelCost = creditsSystem.calculateCreditCost
            ? creditsSystem.calculateCreditCost(modelId, 0, 0)
            : 0;
          if (modelCost > 0) {
            const result = creditsSystem.deductCredits(userId, modelId, 0, 0, '模型调用: ' + modelId);
            if (!result.ok) {
              return { ok: false, error: '积分不足，请充值或升级会员套餐' };
            }
          }
        }
      }
      return { ok: true, data: r.data };
    }
    if (r.status === 401) {
      clearAuth();
      emitAuthChange({ logged: false, reason: '登录已过期' });
      return { ok: false, error: '登录已过期，请重新登录', needLogin: true };
    }
    const errMsg = (r.data && r.data.error && (r.data.error.message || r.data.error)) || ('请求失败 (' + r.status + ')');
    return { ok: false, error: errMsg, status: r.status };
  });

  // 获取可用模型列表
  ipcMain.handle('cloud:models', async () => {
    const r = await cloudRequest('GET', '/api/models', null);
    if (r.ok && r.data) return { ok: true, models: r.data.models || r.data };
    return { ok: false, error: r.error || '获取模型失败' };
  });

  // ============================================================
  // Y·NEX 粒子界面对话：优先本地 Agent，回退云端
  // ============================================================
  ipcMain.handle('chat:send', async (event, { text }) => {
    if (!text) return { ok: false, error: '消息为空' };
    // 1) 本地 Agent
    if (agentHarness) {
      try {
        let final = null;
        for await (const ev of agentHarness.run(text, {})) {
          if (ev.type === 'final') final = ev;
          if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send('agent:stream', ev);
        }
        const answer = (final && final.content) || '';
        if (answer) return { ok: true, answer, source: 'agent' };
      } catch (e) {
        // 落到云端兜底
      }
    }
    // 2) 云端对话
    const auth = loadAuth();
    if (auth && auth.token) {
      try {
        const r = await cloudRequest('POST', '/api/chat', { messages: [{ role: 'user', content: text }] }, auth.token);
        if (r.ok) {
          const d = r.data && r.data.data ? r.data.data : r.data;
          let answer = '';
          if (d && d.answer) answer = d.answer;
          else if (d && d.content) answer = d.content;
          else if (d && d.reply) answer = d.reply;
          else if (d && d.choices && d.choices[0] && d.choices[0].message) answer = d.choices[0].message.content || '';
          return { ok: true, answer, source: 'cloud' };
        }
        return { ok: false, error: r.error || ('云端请求失败 (' + r.status + ')') };
      } catch (e) {
        return { ok: false, error: e.message };
      }
    }
    return { ok: false, error: 'AI 引擎未就绪，请初始化 Agent 或登录账号' };
  });

  // ============================================================
  // 语音 IPC handlers（语音输入/输出）
  // 主进程通过 executeJavaScript 在主窗口渲染进程中执行
  // speechSynthesis，便于系统级触发（通知、托盘等）。
  // 语音识别（SpeechRecognition）需在渲染进程执行。
  // ============================================================
  ipcMain.handle('voice:speak', async (event, { text, options }) => {
    if (!mainWindow || mainWindow.isDestroyed()) return { ok: false, error: '窗口未就绪' };
    const o = options || {};
    const js = `(function(){
      return new Promise((resolve) => {
        if (!('speechSynthesis' in window)) { resolve({ ok:false, error:'no speechSynthesis' }); return; }
        try {
          window.speechSynthesis.cancel();
          const u = new SpeechSynthesisUtterance(${JSON.stringify(text || '')});
          u.lang = ${JSON.stringify(o.lang || 'zh-CN')};
          u.rate = ${Number(o.rate) || 1};
          u.pitch = ${Number(o.pitch) || 1};
          u.volume = ${Number(o.volume) || 1};
          u.onend = () => resolve({ ok:true });
          u.onerror = (e) => resolve({ ok:false, error: e.error || 'speak error' });
          window.speechSynthesis.speak(u);
        } catch(e) { resolve({ ok:false, error: e.message }); }
      });
    })()`;
    try {
      const r = await mainWindow.webContents.executeJavaScript(js, true);
      return r || { ok: false, error: 'no result' };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  });

  ipcMain.handle('voice:stopSpeak', async () => {
    if (!mainWindow || mainWindow.isDestroyed()) return { ok: false, error: '窗口未就绪' };
    try {
      await mainWindow.webContents.executeJavaScript("if ('speechSynthesis' in window) window.speechSynthesis.cancel();", true);
      return { ok: true };
    } catch (e) { return { ok: false, error: e.message }; }
  });

  ipcMain.handle('voice:recognize', async () => {
    // 语音识别需在渲染进程执行（Web Speech API），主进程仅返回提示
    return { ok: false, error: '请在渲染进程中使用 window.ynex.voice.recognize 或 Web Speech API', rendererOnly: true };
  });

  ipcMain.handle('voice:status', async () => {
    return { ok: true, speechSynthesis: true, speechRecognition: true, note: 'renderer-side Web Speech API' };
  });
}

// ============================================================
// 快捷键
// ============================================================

function setupShortcuts() {
  // Ctrl+Shift+Space 唤起窗口（确保 app 已 ready 并加保护）
  try {
    if (!app.isReady()) {
      console.warn('[Y·NEX Desktop] globalShortcut 在 app ready 前被调用，已跳过');
      return;
    }
    const ok = globalShortcut.register('CommandOrControl+Shift+Space', () => {
      if (mainWindow) {
        if (mainWindow.isVisible()) {
          mainWindow.hide();
        } else {
          mainWindow.show();
          mainWindow.focus();
        }
      }
    });
    if (!ok) console.warn('[Y·NEX Desktop] 全局快捷键注册失败');
  } catch (e) {
    console.warn('[Y·NEX Desktop] 全局快捷键注册异常:', e.message);
  }
}

// ============================================================
// 中文应用菜单
// ============================================================

function createAppMenu() {
  const template = [
    {
      label: 'Y·NEX',
      submenu: [
        { label: '关于 Y·NEX Desktop', role: 'about' },
        { type: 'separator' },
        { label: '隐藏', role: 'hide' },
        { label: '隐藏其他', role: 'hideOthers' },
        { label: '显示全部', role: 'unhide' },
        { type: 'separator' },
        { label: '退出', role: 'quit' }
      ]
    },
    {
      label: '编辑',
      submenu: [
        { label: '撤销', role: 'undo' },
        { label: '重做', role: 'redo' },
        { type: 'separator' },
        { label: '剪切', role: 'cut' },
        { label: '复制', role: 'copy' },
        { label: '粘贴', role: 'paste' },
        { label: '全选', role: 'selectAll' }
      ]
    },
    {
      label: '视图',
      submenu: [
        ...(isDevMode ? [
          { label: '重新加载', role: 'reload' },
          { label: '强制重新加载', role: 'forceReload' },
          { label: '开发者工具', role: 'toggleDevTools' },
          { type: 'separator' },
        ] : []),
        { label: '放大', role: 'zoomIn' },
        { label: '缩小', role: 'zoomOut' },
        { label: '重置缩放', role: 'resetZoom' },
        { type: 'separator' },
        { label: '全屏', role: 'togglefullscreen' }
      ]
    },
    {
      label: '窗口',
      submenu: [
        { label: '最小化', role: 'minimize' },
        { label: '关闭', role: 'close' }
      ]
    },
    {
      label: '帮助',
      submenu: [
        {
          label: '打开官网',
          click: () => shell.openExternal('https://ynexai.cn')
        },
        {
          label: '文档',
          click: () => shell.openExternal('https://ynexai.cn/docs')
        }
      ]
    }
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

// ============================================================
// App 生命周期
// ============================================================

app.whenReady().then(async () => {
  // 设置关于面板（显示 slogan）
  app.setAboutPanelOptions({
    applicationName: 'Y·NEX Desktop',
    applicationVersion: app.getVersion(),
    copyright: `© ${new Date().getFullYear()} Y·NEX · 亿界网络科技工作室`,
    credits: '亿界互联·无界未来',
    authors: ['Y·NEX Team'],
    website: 'https://ynexai.cn',
    iconPath: path.join(__dirname, '..', 'assets', 'icon.png'),
  });

  // 首次运行 / 版本升级安全检查：清除可能随测试环境残留的登录凭证
  // 避免开发/测试时的登录态泄漏到安装包用户，或在版本更新后残留旧 token
  const firstRunMarker = path.join(app.getPath('userData'), '.ynex-first-run');
  let shouldClearAuth = false;
  try {
    if (!fs.existsSync(firstRunMarker)) {
      shouldClearAuth = true;
    } else {
      const lastVersion = fs.readFileSync(firstRunMarker, 'utf-8').trim();
      if (lastVersion !== app.getVersion()) {
        shouldClearAuth = true;
        console.log(`[Y·NEX Desktop] 版本变化 ${lastVersion} -> ${app.getVersion()}，将清理旧登录态`);
      }
    }
  } catch (e) { shouldClearAuth = true; }

  if (shouldClearAuth) {
    const candidates = ['auth.json', 'config.json', 'session.json'];
    for (const name of candidates) {
      try {
        const f = path.join(app.getPath('userData'), name);
        if (fs.existsSync(f)) {
          fs.unlinkSync(f);
          console.log(`[Y·NEX Desktop] 已清除残留凭证文件: ${name}`);
        }
      } catch (e) {
        console.warn(`[Y·NEX Desktop] 清理 ${name} 失败:`, e.message);
      }
    }
    try { fs.writeFileSync(firstRunMarker, app.getVersion(), 'utf-8'); } catch (e) {}
  }

  createAppMenu();
  await createWindow();

  // 尽早注册 IPC 通道，避免渲染进程在管理器初始化前调用时提示“无 handler”
  try { setupIPC(); } catch (e) { console.error('IPC 注册错误:', e); }

  // 窗口显示后异步初始化
  setTimeout(async () => {
    try {
      initAgentEngine();

      // 初始化 MCP 管理器
      try {
        const mcpDataDir = path.join(app.getPath('userData'), 'mcp');
        if (!fs.existsSync(mcpDataDir)) fs.mkdirSync(mcpDataDir, { recursive: true });
        mcpManager = new McpManager(mcpDataDir);
        console.log('[Y·NEX Desktop] MCP 管理器已加载');
      } catch(e) {
        console.warn('[Y·NEX Desktop] MCP 管理器加载失败:', e.message);
      }

      initWorkflowEngine();
      initMultiAgentOrchestrator();
      initTriggerEngine();
      initCreditsSystem();
      initMarketManager();

      // 注册 CrewAI 工具到统一工具注册表
      try {
        const crewaiTools = new CrewAITools();
        if (typeof toolRegistry !== 'undefined' && toolRegistry) {
          crewaiTools.registerAll(toolRegistry);
          console.log('[Y·NEX Desktop] CrewAI 工具已注册:', crewaiTools.count(), '个');
        } else {
          // 延迟注册，等工具注册表初始化完成
          setTimeout(() => {
            try {
              if (typeof toolRegistry !== 'undefined' && toolRegistry) {
                crewaiTools.registerAll(toolRegistry);
                console.log('[Y·NEX Desktop] CrewAI 工具已注册(延迟):', crewaiTools.count(), '个');
              }
            } catch(e) {
              console.warn('[Y·NEX Desktop] CrewAI 工具注册失败(延迟):', e.message);
            }
          }, 3000);
        }
      } catch(e) {
        console.warn('[Y·NEX Desktop] CrewAI 工具加载失败:', e.message);
      }
    } catch (e) { console.error('后台初始化错误:', e); }
  }, 100);

  setTimeout(async () => {
    try {
      setupShortcuts();
      startYnexServer();
      createTray();
      lspManager = new LspManager();
      lspManager.autoDetect();
    } catch (e) { console.error('延迟初始化错误:', e); }
  }, 500);
});

function initWorkflowEngine() {
  try {
    workflowEngine = new WorkflowEngine(toolRegistry, agentHarness);
    console.log('[Y·NEX Desktop] Workflow Engine 已加载');
  } catch(e) {
    console.warn('[Y·NEX Desktop] Workflow Engine 加载失败:', e.message);
  }
}

function initMultiAgentOrchestrator() {
  try {
    multiAgentOrchestrator = new MultiAgentOrchestrator(toolRegistry, null);
    console.log('[Y·NEX Desktop] Multi-Agent Orchestrator 已加载');
  } catch(e) {
    console.warn('[Y·NEX Desktop] Multi-Agent Orchestrator 加载失败:', e.message);
  }
}

function initTriggerEngine() {
  try {
    triggerEngine = new TriggerEngine(workflowEngine, multiAgentOrchestrator);
    triggerEngine.start();
    console.log('[Y·NEX Desktop] Trigger Engine 已启动');
  } catch(e) {
    console.warn('[Y·NEX Desktop] Trigger Engine 启动失败:', e.message);
  }
}

function initCreditsSystem() {
  try {
    const dataDir = path.join(app.getPath('userData'), 'credits');
    creditsSystem = new CreditsSystem(dataDir);
    console.log('[Y·NEX Desktop] 积分系统 已启动');
  } catch(e) {
    console.warn('[Y·NEX Desktop] 积分系统 启动失败:', e.message);
  }
}

function initMarketManager() {
  try {
    const dataDir = path.join(app.getPath('userData'), 'market');
    marketManager = new MarketManager(dataDir);
    console.log('[Y·NEX Desktop] 市场与模板系统 已启动');
  } catch(e) {
    console.warn('[Y·NEX Desktop] 市场与模板系统 启动失败:', e.message);
  }
}

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
  else mainWindow?.show();
});

app.on('before-quit', () => {
  isQuitting = true;
  globalShortcut.unregisterAll();
  stopYnexServer();
  // 清理所有终端
  for (const [, term] of terminals.entries()) {
    try { term.kill(); } catch(e) {}
  }
  terminals.clear();
  // 清理 LSP 服务器
  if (lspManager) { try { lspManager.shutdown(); } catch(e) {} }
  // 清理 MCP 服务器
  if (mcpManager) { try { mcpManager.shutdown(); } catch(e) {} }
  // 清理沙箱快照
  if (sandboxManager) { try { sandboxManager.clear(); } catch(e) {} }
  // 清理调试器
  if (debugManager) { try { debugManager.shutdown(); } catch(e) {} }
  // 清理 SSH 连接
  if (sshManager) { try { sshManager.shutdown(); } catch(e) {} }
  // 清理 M5 管理器
  if (completionManager) { try { completionManager.clearCache(); } catch(e) {} }
  if (jupyterManager) { try { jupyterManager.stopServer(); } catch(e) {} }
  if (pluginSDK) { try { pluginSDK.removeAllListeners(); } catch(e) {} }
  if (perfOptimizer) { try { perfOptimizer.shutdown(); } catch(e) {} }
  if (persistentCache) { try { persistentCache.shutdown(); } catch(e) {} }
  if (connectionPool) { try { connectionPool.shutdown(); } catch(e) {} }
  if (perfMonitor) { try { perfMonitor.stop(); } catch(e) {} }
  if (sharedBuffer) { try { sharedBuffer.shutdown(); } catch(e) {} }
  if (fileWatcher) { try { fileWatcher.unwatch(); } catch(e) {} }
  if (wsMultiplex) { try { wsMultiplex.shutdown(); } catch(e) {} }
  if (casStorage) { try { casStorage.shutdown(); } catch(e) {} }
});

// 单例锁已在文件顶部处理
