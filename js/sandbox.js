/**
 * Y·NEX 沙箱执行系统 v2.0
 * 基于 Codex Bubblewrap 设计理念
 * 提供安全的命令执行环境
 */
'use strict';

// ============================================================
// 一、沙箱配置
// ============================================================
const SandboxConfig = {
  // 允许的操作白名单
  ALLOWED_OPERATIONS: [
    'ls', 'pwd', 'cd', 'echo', 'cat', 'head', 'tail', 'grep', 'find',
    'wc', 'sort', 'uniq', 'cut', 'tr', 'sed', 'awk', 'tar', 'zip', 'unzip',
    'git', 'npm', 'node', 'python', 'python3', 'pip', 'curl', 'wget'
  ],

  // 禁止的模式（危险命令）
  FORBIDDEN_PATTERNS: [
    /rm\s+(-[rf]+\s+)*\//,                          // 删除根目录
    /dd\s+/,                                          // 磁盘操作
    /mkfs/,                                           // 格式化
    /:(){ :|:& };:/,                                 // Fork 炸弹
    /\|\s*sh\s*$/,                                   // 管道到 shell
    /eval\s*\(/,                                     // 动态代码执行
    /\$\(.*\)/,                                      // 命令替换
    /`.*`/,                                          // 反引号执行
    />\s*\/dev\/sd/,                                 // 直接写入设备
    /mv\s+.*\s+\/dev\/null/,                         // 移动到 null
    /chmod\s+777/,                                    // 777 权限
    /curl.*\|.*sh/,                                  // 管道下载执行
    /wget.*\|.*sh/,                                  // Wget 下载执行
  ],

  // 限制配置
  LIMITS: {
    maxOutputSize: 1024 * 1024,     // 1MB 输出限制
    maxExecutionTime: 60000,        // 60秒超时
    maxFileSize: 10 * 1024 * 1024,  // 10MB 文件大小限制
    maxConcurrent: 3                // 最大并发数
  },

  // 权限级别
  PERMISSION_LEVELS: {
    NONE: 0,       // 完全禁止执行
    READ: 1,       // 只读
    WRITE: 2,      // 读写文件
    EXEC: 3,       // 可执行命令
    NETWORK: 4,    // 可访问网络
    SYSTEM: 5      // 系统级操作
  }
};

// ============================================================
// 二、执行策略
// ============================================================
const ExecutionPolicy = {
  // 当前权限级别
  currentLevel: SandboxConfig.PERMISSION_LEVELS.READ,

  // 信任的命令列表（已确认安全）
  trustedCommands: new Set(),

  // 策略规则
  rules: {
    // 需要审批的操作
    requiresApproval: [
      { pattern: /rm\s+-rf|rm\s+--recursive\s+--force/i, reason: '递归强制删除' },
      { pattern: /git\s+push\s+(-f|--force)/i, reason: '强制推送到远程' },
      { pattern: /git\s+reset\s+--hard/i, reason: '强制重置 Git' },
      { pattern: /drop\s+(table|database)/i, reason: '删除数据库' },
      { pattern: /chmod\s+777/i, reason: '设置 777 权限' },
      { pattern: /shutdown|reboot|halt/i, reason: '系统关机/重启' },
      { pattern: /\|\s*bash|\|\s*sh$|&\s*$/i, reason: '管道到 shell' }
    ],

    // 完全禁止的操作
    alwaysBlocked: [
      { pattern: /rm\s+(-[rf]+\s+)*\//, reason: '删除根目录' },
      { pattern: /dd\s+/, reason: '磁盘操作' },
      { pattern: /:\(\){ :|:& };:/, reason: 'Fork 炸弹' },
      { pattern: /mkfs/, reason: '格式化文件系统' }
    ]
  },

  /**
   * 检查命令是否安全
   * @param {string} command - 要检查的命令
   * @returns {object} { safe: boolean, reason: string, level: number }
   */
  check(command) {
    // 检查完全禁止的操作
    for (const rule of this.rules.alwaysBlocked) {
      if (rule.pattern.test(command)) {
        return { safe: false, reason: rule.reason, level: -1, action: 'BLOCK' };
      }
    }

    // 检查是否需要审批
    for (const rule of this.rules.requiresApproval) {
      if (rule.pattern.test(command)) {
        // 如果已信任，直接通过
        if (this.trustedCommands.has(command.trim())) {
          return { safe: true, reason: '已信任', level: this.currentLevel, action: 'TRUSTED' };
        }
        return { safe: true, reason: rule.reason, level: this.currentLevel, action: 'APPROVAL_REQUIRED' };
      }
    }

    // 检查基础权限
    const baseCmd = command.trim().split(/\s+/)[0];
    if (!SandboxConfig.ALLOWED_OPERATIONS.includes(baseCmd) &&
        !this.trustedCommands.has(baseCmd)) {
      return { safe: false, reason: `命令 "${baseCmd}" 不在白名单中`, level: -1, action: 'BLOCK' };
    }

    return { safe: true, reason: '允许执行', level: this.currentLevel, action: 'ALLOW' };
  },

  /**
   * 信任一个命令
   */
  trustCommand(command) {
    this.trustedCommands.add(command.trim());
    // 持久化到 localStorage
    localStorage.setItem('trigen_trusted_commands', JSON.stringify([...this.trustedCommands]));
  },

  /**
   * 取消信任
   */
  untrustCommand(command) {
    this.trustedCommands.delete(command.trim());
    localStorage.setItem('trigen_trusted_commands', JSON.stringify([...this.trustedCommands]));
  },

  /**
   * 加载已信任的命令
   */
  loadTrusted() {
    try {
      const trusted = JSON.parse(localStorage.getItem('trigen_trusted_commands') || '[]');
      this.trustedCommands = new Set(trusted);
    } catch (e) {
      this.trustedCommands = new Set();
    }
  },

  /**
   * 设置权限级别
   */
  setLevel(level) {
    this.currentLevel = Math.min(Math.max(level, 0), SandboxConfig.PERMISSION_LEVELS.SYSTEM);
  }
};

// ============================================================
// 三、沙箱执行器
// ============================================================
const Sandbox = {
  // 当前执行的任务
  runningTasks: new Map(),
  taskCounter: 0,

  /**
   * 在沙箱中执行命令
   * @param {string} command - 要执行的命令
   * @param {object} options - 选项
   * @returns {Promise<object>} 执行结果
   */
  async execute(command, options = {}) {
    const taskId = ++this.taskCounter;
    const startTime = Date.now();

    // 1. 安全检查
    const policyCheck = ExecutionPolicy.check(command);
    if (!policyCheck.safe) {
      return {
        taskId,
        success: false,
        error: policyCheck.reason,
        blocked: true,
        action: policyCheck.action
      };
    }

    // 2. 如果需要审批，弹出确认框
    if (policyCheck.action === 'APPROVAL_REQUIRED') {
      const approved = await this.requestApproval(command, policyCheck.reason);
      if (!approved) {
        return { taskId, success: false, error: '用户取消', cancelled: true };
      }
      ExecutionPolicy.trustCommand(command);
    }

    // 3. 检查并发限制
    if (this.runningTasks.size >= SandboxConfig.LIMITS.maxConcurrent) {
      return {
        taskId,
        success: false,
        error: '并发任务数超限，请稍后再试'
      };
    }

    // 4. 创建执行任务
    const task = {
      id: taskId,
      command,
      startTime,
      status: 'running',
      output: '',
      onProgress: options.onProgress || null,
      abortController: null
    };

    this.runningTasks.set(taskId, task);

    try {
      // 5. 执行命令（通过 API）
      const result = await this.executeInSandbox(task, options);
      return result;
    } finally {
      this.runningTasks.delete(taskId);
    }
  },

  /**
   * 在沙箱中执行（实际调用后端）
   */
  async executeInSandbox(task, options) {
    const timeout = options.timeout || SandboxConfig.LIMITS.maxExecutionTime;

    try {
      const response = await fetch(API_BASE + '/api/sandbox/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          command: task.command,
          cwd: options.cwd || process.cwd(),
          timeout,
          env: options.env || {}
        })
      });

      const result = await response.json();

      return {
        taskId: task.id,
        success: result.success,
        output: result.stdout || '',
        error: result.stderr || '',
        exitCode: result.exitCode,
        duration: Date.now() - task.startTime,
        killed: result.killed
      };
    } catch (e) {
      // 如果后端不可用，模拟执行（仅用于开发）
      if (options.mock) {
        return this.mockExecute(task);
      }
      return {
        taskId: task.id,
        success: false,
        error: e.message,
        offline: true
      };
    }
  },

  /**
   * 模拟执行（开发模式）
   */
  mockExecute(task) {
    const cmd = task.command.toLowerCase();

    if (cmd.startsWith('ls')) {
      return {
        taskId: task.id,
        success: true,
        output: 'file1.txt\nfile2.js\nREADME.md',
        exitCode: 0,
        duration: 100
      };
    }

    if (cmd.startsWith('pwd')) {
      return {
        taskId: task.id,
        success: true,
        output: '/workspace',
        exitCode: 0,
        duration: 50
      };
    }

    return {
      taskId: task.id,
      success: false,
      error: '命令执行失败（模拟模式）',
      exitCode: 1,
      duration: 100
    };
  },

  /**
   * 请求用户审批
   */
  requestApproval(command, reason) {
    return new Promise((resolve) => {
      const overlay = document.createElement('div');
      overlay.id = 'sandbox-approval-overlay';
      overlay.style.cssText = `
        position:fixed;top:0;left:0;right:0;bottom:0;
        background:rgba(0,0,0,0.7);display:flex;align-items:center;
        justify-content:center;z-index:10001;backdrop-filter:blur(4px);
      `;

      overlay.innerHTML = `
        <div style="
          background:var(--bg-card,#1a1035);border:1px solid var(--border,rgba(155,89,247,0.15));
          border-radius:12px;padding:24px;max-width:520px;width:90%;
          box-shadow:0 20px 60px rgba(0,0,0,0.5);
        ">
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
            <span style="font-size:2rem">⚠️</span>
            <h3 style="margin:0;color:var(--text)">需要权限审批</h3>
          </div>
          <p style="color:var(--text-secondary);margin-bottom:12px">
            以下命令可能具有风险：
          </p>
          <pre style="
            background:rgba(0,0,0,0.3);padding:12px;border-radius:8px;
            overflow-x:auto;font-size:0.85rem;color:#f59e0b;
          ">${this.escapeHtml(command)}</pre>
          <p style="color:var(--text-secondary);margin-bottom:20px;font-size:0.9rem">
            原因：${reason}
          </p>
          <div style="display:flex;gap:12px;justify-content:flex-end;flex-wrap:wrap">
            <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:0.85rem;color:var(--text-secondary);margin-right:auto">
              <input type="checkbox" id="trust-cmd"> 信任此类命令
            </label>
            <button id="btn-cancel" style="
              padding:8px 20px;border-radius:6px;border:1px solid var(--border);
              background:transparent;color:var(--text);cursor:pointer;
            ">取消</button>
            <button id="btn-approve" style="
              padding:8px 20px;border-radius:6px;border:none;
              background:#ef4444;color:white;cursor:pointer;font-weight:600;
            ">确认执行</button>
          </div>
        </div>
      `;

      document.body.appendChild(overlay);

      const cancelBtn = overlay.querySelector('#btn-cancel');
      const approveBtn = overlay.querySelector('#btn-approve');
      const trustCheckbox = overlay.querySelector('#trust-cmd');

      const cleanup = (result) => {
        document.body.removeChild(overlay);
        resolve(result);
      };

      cancelBtn.onclick = () => cleanup(false);
      approveBtn.onclick = () => cleanup(trustCheckbox.checked);
      overlay.onclick = (e) => { if (e.target === overlay) cleanup(false); };
    });
  },

  /**
   * 转义 HTML
   */
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  },

  /**
   * 终止任务
   */
  abort(taskId) {
    const task = this.runningTasks.get(taskId);
    if (task && task.abortController) {
      task.abortController.abort();
      return true;
    }
    return false;
  },

  /**
   * 获取运行中的任务
   */
  getRunningTasks() {
    return Array.from(this.runningTasks.values()).map(t => ({
      id: t.id,
      command: t.command,
      duration: Date.now() - t.startTime,
      status: t.status
    }));
  }
};

// ============================================================
// 四、输出过滤器
// ============================================================
const OutputSanitizer = {
  // 敏感信息模式
  patterns: [
    // API Keys
    { pattern: /api[_-]?key['":\s=]+['"]?([a-zA-Z0-9_-]{20,})/gi, replace: 'api_key: "***"' },
    { pattern: /sk-[a-zA-Z0-9]{20,}/g, replace: 'sk-***' },
    { pattern: /sk-ant-[a-zA-Z0-9]{20,}/g, replace: 'sk-ant-***' },

    // Passwords
    { pattern: /password['":\s=]+['"]?([^\s'"]{8,})/gi, replace: 'password: "***"' },
    { pattern: /passwd['":\s=]+['"]?([^\s'"]{8,})/gi, replace: 'passwd: "***"' },

    // Tokens
    { pattern: /token['":\s=]+['"]?([a-zA-Z0-9_-]{20,})/gi, replace: 'token: "***"' },
    { pattern: /bearer\s+[a-zA-Z0-9_-]{20,}/gi, replace: 'bearer ***' },

    // Private keys
    { pattern: /-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----/g, replace: '-----BEGIN PRIVATE KEY-----' },

    // Database connection strings
    { pattern: /(mongodb|postgres|mysql):\/\/[^@]+@[^\s'"]+/gi, replace: '***://***@host' },

    // IP addresses (过滤内部 IP)
    { pattern: /\b(10\.\d{1,3}|172\.(1[6-9]|2\d)|192\.168)\.\d{1,3}(:\d+)?/g, replace: '***.***.***' }
  ],

  /**
   * 过滤敏感信息
   */
  sanitize(output) {
    let sanitized = output;

    for (const { pattern, replace } of this.patterns) {
      sanitized = sanitized.replace(pattern, replace);
    }

    return sanitized;
  },

  /**
   * 截断过长输出
   */
  truncate(output, maxLength = SandboxConfig.LIMITS.maxOutputSize) {
    if (output.length > maxLength) {
      return {
        truncated: true,
        output: output.substring(0, maxLength),
        remaining: output.length - maxLength
      };
    }
    return { truncated: false, output };
  }
};

// ============================================================
// 五、初始化
// ============================================================
ExecutionPolicy.loadTrusted();

// ============================================================
// 六、导出
// ============================================================
window.SandboxSystem = {
  Config: SandboxConfig,
  Policy: ExecutionPolicy,
  Sandbox,
  Sanitizer: OutputSanitizer,

  // 便捷方法
  execute: (cmd, opts) => Sandbox.execute(cmd, opts),
  check: (cmd) => ExecutionPolicy.check(cmd),
  trust: (cmd) => ExecutionPolicy.trustCommand(cmd),
  sanitize: (output) => OutputSanitizer.sanitize(output),
  getTasks: () => Sandbox.getRunningTasks()
};
