/**
 * Y·NEX 安全确认系统 v2.0
 * 基于 Claude Code 设计理念
 * 不可逆操作的确认机制
 */
'use strict';

// ============================================================
// 一、危险操作定义
// ============================================================
const DANGEROUS_OPERATIONS = {
  // 文件操作
  FILE_DELETE: {
    id: 'file_delete',
    name: '删除文件',
    pattern: /rm\s+(-[rf]?\s+)*|delete\s+file|remove\s+file|unlink/i,
    requiresConfirm: true,
    confirmMessage: '即将删除文件，此操作不可恢复。确认继续？'
  },
  FILE_OVERWRITE: {
    id: 'file_overwrite',
    name: '覆盖文件',
    pattern: />\s*[\w.-]+|write\s+file|overwrite/i,
    requiresConfirm: false, // 编辑器覆盖通常是有意的
    checkContent: true
  },
  FILE_CREATE: {
    id: 'file_create',
    name: '创建文件',
    pattern: /touch\s+|create\s+file|new\s+file|\|\s*tee/i,
    requiresConfirm: false
  },

  // 目录操作
  DIR_DELETE: {
    id: 'dir_delete',
    name: '删除目录',
    pattern: /rm\s+(-r?\s+)*.*\/$|rmdir|remove\s+directory/i,
    requiresConfirm: true,
    confirmMessage: '即将删除目录及其所有内容，此操作不可恢复。确认继续？'
  },

  // Git 操作
  GIT_PUSH: {
    id: 'git_push',
    name: '推送到远程',
    pattern: /git\s+push|git\s+push\s+(-f\s+)?origin/i,
    requiresConfirm: true,
    confirmMessage: '即将推送到远程仓库，可能覆盖远程代码。确认继续？'
  },
  GIT_FORCE_PUSH: {
    id: 'git_force_push',
    name: '强制推送',
    pattern: /git\s+push\s+(-f|--force)/i,
    requiresConfirm: true,
    confirmMessage: '⚠️ 强制推送会覆盖远程历史，此操作危险且不可恢复！确认继续？',
    highRisk: true
  },
  GIT_RESET_HARD: {
    id: 'git_reset_hard',
    name: '强制重置',
    pattern: /git\s+reset\s+(--hard|--mixed)/i,
    requiresConfirm: true,
    confirmMessage: '⚠️ Git 重置会丢失未提交的更改！确认继续？',
    highRisk: true
  },
  GIT_DESTRUCTIVE: {
    id: 'git_destructive',
    name: '破坏性 Git 操作',
    pattern: /git\s+rebase\s+-i|git\s+filter-branch|git\s+push\s+origin\s+:|git\s+branch\s+-D/i,
    requiresConfirm: true,
    confirmMessage: '此操作可能永久丢失代码历史。确认继续？',
    highRisk: true
  },

  // 系统命令
  SYSTEM_KILL: {
    id: 'system_kill',
    name: '终止进程',
    pattern: /kill\s+(-9\s+)?\d+|pkill|killall/i,
    requiresConfirm: true,
    confirmMessage: '即将终止进程，可能导致数据丢失。确认继续？'
  },
  SYSTEM_REBOOT: {
    id: 'system_reboot',
    name: '系统重启',
    pattern: /reboot|shutdown|init\s+6/i,
    requiresConfirm: true,
    confirmMessage: '⚠️ 即将重启系统，所有未保存工作将丢失！确认继续？',
    highRisk: true
  },

  // 网络操作
  NETWORK_SEND: {
    id: 'network_send',
    name: '发送网络数据',
    pattern: /curl\s+(-X\s+POST|-d|--data)/i,
    requiresConfirm: false,
    checkTarget: true
  },
  NETWORK_SSH: {
    id: 'network_ssh',
    name: 'SSH 连接',
    pattern: /ssh\s+(-i\s+)?[^\s@]+@[^\s]+/i,
    requiresConfirm: false,
    checkTarget: true
  },

  // 数据库操作
  DB_DROP: {
    id: 'db_drop',
    name: '删除数据库',
    pattern: /drop\s+(table|database)|delete\s+from\s+\w+\s*;?\s*where/i,
    requiresConfirm: true,
    confirmMessage: '⚠️ 此操作会永久删除数据！确认继续？',
    highRisk: true
  },
  DB_TRUNCATE: {
    id: 'db_truncate',
    name: '清空数据表',
    pattern: /truncate\s+\w+|delete\s+from\s+\w+\s*;?\s*$/im,
    requiresConfirm: true,
    confirmMessage: '即将清空数据表内容，此操作不可恢复。确认继续？'
  },

  // 环境变更
  ENV_SECRET: {
    id: 'env_secret',
    name: '处理敏感信息',
    pattern: /password|secret|api[_-]?key|token|credential/i,
    requiresConfirm: false,
    warnMessage: '注意：即将处理敏感信息，请确保不将其暴露在日志或输出中'
  },

  // 外部命令执行
  EXEC_EXTERNAL: {
    id: 'exec_external',
    name: '执行外部命令',
    pattern: /\$\(.*\)|`.*`|eval\s+|exec\s+/i,
    requiresConfirm: true,
    confirmMessage: '即将执行动态生成的命令，可能存在安全风险。确认继续？',
    highRisk: true
  },

  // 批量操作
  BATCH_DELETE: {
    id: 'batch_delete',
    name: '批量删除',
    pattern: /\*\s*\|\s*xargs\s+rm|find\s+.*-delete|batch\s+delete/i,
    requiresConfirm: true,
    confirmMessage: '⚠️ 批量删除操作影响范围广！确认继续？',
    highRisk: true
  }
};

// ============================================================
// 二、确认状态管理
// ============================================================
const SafetyConfirm = {
  // 待确认队列
  queue: [],

  // 已确认的信任列表（本次会话）
  trustedPatterns: new Set(),

  // 用户配置：是否自动确认（默认需要确认）
  autoConfirm: false,

  // 信任期限（毫秒），0 表示永久直到页面关闭
  trustDuration: 0,
  trustTimestamp: {},

  /**
   * 分析命令是否包含危险操作
   * @param {string} command - 要分析的命令
   * @returns {Array} 匹配到的危险操作列表
   */
  analyze(command) {
    const matches = [];

    for (const [key, op] of Object.entries(DANGEROUS_OPERATIONS)) {
      if (op.pattern.test(command)) {
        matches.push({
          ...op,
          key
        });
      }
    }

    return matches;
  },

  /**
   * 检查是否已信任该操作模式
   * @param {string} operationId - 操作 ID
   * @returns {boolean}
   */
  isTrusted(operationId) {
    if (!this.trustedPatterns.has(operationId)) return false;

    const timestamp = this.trustTimestamp[operationId];
    if (!timestamp) return false;

    if (this.trustDuration > 0 && Date.now() - timestamp > this.trustDuration) {
      this.trustedPatterns.delete(operationId);
      delete this.trustTimestamp[operationId];
      return false;
    }

    return true;
  },

  /**
   * 添加信任
   * @param {string} operationId - 操作 ID
   * @param {number} duration - 信任持续时间（毫秒）
   */
  trust(operationId, duration = 0) {
    this.trustedPatterns.add(operationId);
    this.trustTimestamp[operationId] = Date.now();
    if (duration > 0) {
      this.trustDuration = duration;
    }
  },

  /**
   * 移除信任
   * @param {string} operationId - 操作 ID
   */
  untrust(operationId) {
    this.trustedPatterns.delete(operationId);
    delete this.trustTimestamp[operationId];
  },

  /**
   * 清空所有信任
   */
  clearTrust() {
    this.trustedPatterns.clear();
    this.trustTimestamp = {};
  },

  /**
   * 请求确认
   * @param {object} operation - 危险操作信息
   * @param {Function} onConfirm - 确认回调
   * @param {Function} onCancel - 取消回调
   */
  requestConfirm(operation, onConfirm, onCancel) {
    // 如果已信任，直接执行
    if (this.isTrusted(operation.id)) {
      onConfirm();
      return;
    }

    // 显示确认对话框
    this.showConfirmDialog(operation, onConfirm, onCancel);
  },

  /**
   * 显示确认对话框
   */
  showConfirmDialog(operation, onConfirm, onCancel) {
    // 创建确认对话框
    const overlay = document.createElement('div');
    overlay.id = 'safety-confirm-overlay';
    overlay.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0,0,0,0.7);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 10000;
      backdrop-filter: blur(4px);
    `;

    const dialog = document.createElement('div');
    dialog.style.cssText = `
      background: var(--bg-card, #1a1035);
      border: 1px solid var(--border, rgba(155,89,247,0.15));
      border-radius: 12px;
      padding: 24px;
      max-width: 480px;
      width: 90%;
      box-shadow: 0 20px 60px rgba(0,0,0,0.5);
    `;

    const icon = operation.highRisk ? '⚠️' : '⚡';
    const titleColor = operation.highRisk ? 'color: #ef4444;' : 'color: #f59e0b;';

    dialog.innerHTML = `
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
        <span style="font-size:2rem">${icon}</span>
        <h3 style="margin:0;font-size:1.2rem;color:var(--text)">${operation.name}</h3>
      </div>
      <p style="color:var(--text-secondary);margin-bottom:20px;font-size:0.95rem;line-height:1.6">
        ${operation.confirmMessage || '此操作可能具有风险。确认继续？'}
      </p>
      <div style="display:flex;gap:12px;justify-content:flex-end">
        <label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:0.85rem;color:var(--text-secondary);margin-right:auto">
          <input type="checkbox" id="trust-this">
          本次会话信任此类操作
        </label>
        <button id="confirm-cancel" style="
          padding:8px 20px;border-radius:6px;border:1px solid var(--border);
          background:transparent;color:var(--text);cursor:pointer;font-size:0.9rem
        ">取消</button>
        <button id="confirm-proceed" style="
          padding:8px 20px;border-radius:6px;border:none;
          background:${operation.highRisk ? '#ef4444' : 'var(--accent)'};
          color:white;cursor:pointer;font-size:0.9rem;font-weight:600
        ">确认执行</button>
      </div>
    `;

    overlay.appendChild(dialog);
    document.body.appendChild(overlay);

    // 事件绑定
    const cancelBtn = dialog.querySelector('#confirm-cancel');
    const proceedBtn = dialog.querySelector('#confirm-proceed');
    const trustCheckbox = dialog.querySelector('#trust-this');

    const closeDialog = (result) => {
      if (trustCheckbox.checked) {
        this.trust(operation.id, this.trustDuration);
      }
      document.body.removeChild(overlay);
      if (result) {
        onConfirm && onConfirm();
      } else {
        onCancel && onCancel();
      }
    };

    cancelBtn.onclick = () => closeDialog(false);
    proceedBtn.onclick = () => closeDialog(true);
    overlay.onclick = (e) => {
      if (e.target === overlay) closeDialog(false);
    };

    // ESC 键取消
    const escHandler = (e) => {
      if (e.key === 'Escape') {
        closeDialog(false);
        document.removeEventListener('keydown', escHandler);
      }
    };
    document.addEventListener('keydown', escHandler);
  },

  /**
   * 在执行前检查命令安全性
   * @param {string} command - 要执行的命令
   * @returns {Promise<boolean>} 是否可以执行
   */
  async checkBeforeExecute(command) {
    const dangerous = this.analyze(command);

    if (dangerous.length === 0) return true;

    for (const op of dangerous) {
      if (!this.isTrusted(op.id)) {
        return new Promise((resolve) => {
          this.requestConfirm(
            op,
            () => resolve(true),
            () => resolve(false)
          );
        });
      }
    }

    return true;
  }
};

// ============================================================
// 三、输出过滤器
// ============================================================
const OutputFilter = {
  // 敏感信息模式
  patterns: [
    // API Keys
    { pattern: /api[_-]?key['":\s=]+['"]?([a-zA-Z0-9_-]{20,})/gi, replacement: 'api_key: "***"' },
    { pattern: /sk-[a-zA-Z0-9]{20,}/g, replacement: 'sk-***' },
    { pattern: /sk-ant-[a-zA-Z0-9]{20,}/g, replacement: 'sk-ant-***' },

    // Passwords
    { pattern: /password['":\s=]+['"]?([^\s'"]{8,})/gi, replacement: 'password: "***"' },
    { pattern: /passwd['":\s=]+['"]?([^\s'"]{8,})/gi, replacement: 'passwd: "***"' },

    // Tokens
    { pattern: /token['":\s=]+['"]?([a-zA-Z0-9_-]{20,})/gi, replacement: 'token: "***"' },
    { pattern: /bearer\s+[a-zA-Z0-9_-]{20,}/gi, replacement: 'bearer ***' },

    // Private keys
    { pattern: /-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----/g, replacement: '-----BEGIN PRIVATE KEY-----' },
    { pattern: /-----END\s+(RSA\s+)?PRIVATE\s+KEY-----/g, replacement: '-----END PRIVATE KEY-----' },

    // Database connection strings
    { pattern: /(mongodb|postgres|mysql):\/\/[^@]+@[^\s'"]+/gi, replacement: '***://***@host' },

    // IP addresses in certain contexts
    { pattern: /(\d{1,3}\.){3}\d{1,3}(:\d+)?/g, replacement: '***.***.***' }
  ],

  /**
   * 过滤输出中的敏感信息
   * @param {string} output - 原始输出
   * @returns {string} 过滤后的输出
   */
  filter(output) {
    let filtered = output;

    for (const { pattern, replacement } of this.patterns) {
      filtered = filtered.replace(pattern, replacement);
    }

    return filtered;
  },

  /**
   * 检查输出是否包含敏感信息
   * @param {string} output - 待检查的输出
   * @returns {boolean}
   */
  containsSensitive(output) {
    for (const { pattern } of this.patterns) {
      if (pattern.test(output)) return true;
    }
    return false;
  }
};

// ============================================================
// 四、导出
// ============================================================
window.SafetySystem = {
  DANGEROUS_OPERATIONS,
  SafetyConfirm,
  OutputFilter
};
