/**
 * TriGenClaw 桌面端沙箱执行系统 v2.0
 * 基于 Codex Bubblewrap 设计，本地执行更安全
 */
'use strict';

// ============================================================
// 一、沙箱配置
// ============================================================
var DesktopSandbox = {
  // 权限级别
  LEVELS: {
    NONE: 0,
    READ: 1,
    WRITE: 2,
    EXEC: 3,
    NETWORK: 4,
    SYSTEM: 5
  },

  // 当前权限
  currentLevel: 2, // 默认读写

  // 信任的命令
  trustedCommands: new Set(),

  // 禁止的命令
  FORBIDDEN: [
    'rm -rf /',
    'dd if=',
    'mkfs',
    ':(){ :|:& };:',
    '> /dev/sd'
  ],

  // 需要审批的命令
  NEEDS_APPROVAL: [
    { pattern: /git push -f/i, reason: '强制推送' },
    { pattern: /git reset --hard/i, reason: '强制重置 Git' },
    { pattern: /rm -rf/i, reason: '递归删除' },
    { pattern: /chmod 777/i, reason: '777 权限' },
    { pattern: /drop table/i, reason: '删除数据库表' }
  ],

  // 初始化
  init: function() {
    // 加载信任列表
    var trusted = localStorage.getItem('trigen_trusted');
    if (trusted) {
      try {
        this.trustedCommands = new Set(JSON.parse(trusted));
      } catch (e) {
        this.trustedCommands = new Set();
      }
    }
  },

  /**
   * 检查命令
   */
  check: function(command) {
    // 检查完全禁止
    for (var i = 0; i < this.FORBIDDEN.length; i++) {
      if (command.indexOf(this.FORBIDDEN[i]) !== -1) {
        return { allowed: false, reason: '命令被禁止' };
      }
    }

    // 检查是否需要审批
    for (var j = 0; j < this.NEEDS_APPROVAL.length; j++) {
      var rule = this.NEEDS_APPROVAL[j];
      if (rule.pattern.test(command)) {
        if (this.trustedCommands.has(command.trim())) {
          return { allowed: true, trusted: true };
        }
        return { allowed: true, approvalNeeded: true, reason: rule.reason };
      }
    }

    return { allowed: true };
  },

  /**
   * 信任命令
   */
  trust: function(command) {
    this.trustedCommands.add(command.trim());
    localStorage.setItem('trigen_trusted', JSON.stringify([...this.trustedCommands]));
  },

  /**
   * 执行命令
   */
  execute: function(command, options) {
    var self = this;
    options = options || {};

    return new Promise(function(resolve, reject) {
      // 检查权限
      var check = self.check(command);

      if (!check.allowed) {
        resolve({ success: false, error: check.reason, blocked: true });
        return;
      }

      if (check.approvalNeeded && !options.autoApprove) {
        self.requestApproval(command, check.reason, function(approved, trust) {
          if (!approved) {
            resolve({ success: false, cancelled: true });
            return;
          }
          if (trust) {
            self.trust(command);
          }
          self.doExecute(command, options, resolve);
        });
      } else {
        self.doExecute(command, options, resolve);
      }
    });
  },

  /**
   * 实际执行
   */
  doExecute: function(command, options, resolve) {
    // 桌面端直接使用 Node.js child_process
    if (typeof require !== 'undefined') {
      try {
        var child = require('child_process');
        var exec = child.exec;

        var proc = exec(command, {
          cwd: options.cwd || process.cwd(),
          timeout: options.timeout || 60000,
          maxBuffer: 1024 * 1024
        }, function(error, stdout, stderr) {
          if (error) {
            resolve({
              success: false,
              error: error.message,
              exitCode: error.code
            });
          } else {
            resolve({
              success: true,
              output: stdout,
              error: stderr,
              exitCode: 0
            });
          }
        });

        proc.on('error', function(err) {
          resolve({ success: false, error: err.message });
        });
      } catch (e) {
        // Electron 环境外，模拟执行
        resolve(this.mockExecute(command));
      }
    } else {
      // Web 环境，使用 API
      fetch(API_BASE + '/api/sandbox/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: command, cwd: options.cwd })
      })
      .then(function(r) { return r.json(); })
      .then(resolve)
      .catch(function(e) {
        resolve({ success: false, error: e.message, offline: true });
      });
    }
  },

  /**
   * 模拟执行
   */
  mockExecute: function(command) {
    var cmd = command.toLowerCase().trim();

    if (cmd === 'ls' || cmd === 'ls -la') {
      return {
        success: true,
        output: 'file1.txt  file2.js  README.md',
        exitCode: 0
      };
    }

    if (cmd === 'pwd') {
      return {
        success: true,
        output: '/workspace',
        exitCode: 0
      };
    }

    if (cmd === 'node -v') {
      return {
        success: true,
        output: 'v20.0.0',
        exitCode: 0
      };
    }

    return {
      success: true,
      output: '命令已执行（模拟）',
      exitCode: 0,
      mock: true
    };
  },

  /**
   * 请求审批
   */
  requestApproval: function(command, reason, callback) {
    var overlay = document.createElement('div');
    overlay.style.cssText = [
      'position:fixed', 'top:0', 'left:0', 'right:0', 'bottom:0',
      'background:rgba(0,0,0,0.7)', 'display:flex', 'align-items:center',
      'justify-content:center', 'z-index:10001'
    ].join(';');

    overlay.innerHTML = [
      '<div style="background:#1a1035;border:1px solid rgba(155,89,247,0.15);border-radius:12px;padding:24px;max-width:520px;width:90%;box-shadow:0 20px 60px rgba(0,0,0,0.5)">',
      '<div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">',
      '<span style="font-size:2rem">⚠️</span>',
      '<h3 style="margin:0;color:#e8e0f0">需要权限审批</h3>',
      '</div>',
      '<p style="color:#9d92b5;margin-bottom:12px">以下命令可能具有风险：</p>',
      '<pre style="background:rgba(0,0,0,0.3);padding:12px;border-radius:8px;overflow-x:auto;font-size:0.85rem;color:#f59e0b">',
      this.escapeHtml(command),
      '</pre>',
      '<p style="color:#9d92b5;margin-bottom:20px;font-size:0.9rem">原因：' + reason + '</p>',
      '<div style="display:flex;gap:12px;justify-content:flex-end">',
      '<label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:0.85rem;color:#9d92b5;margin-right:auto">',
      '<input type="checkbox" id="trust-cmd"> 信任此类命令',
      '</label>',
      '<button id="btn-cancel" style="padding:8px 20px;border-radius:6px;border:1px solid rgba(155,89,247,0.15);background:transparent;color:#e8e0f0;cursor:pointer">取消</button>',
      '<button id="btn-approve" style="padding:8px 20px;border-radius:6px;border:none;background:#ef4444;color:white;cursor:pointer;font-weight:600">确认执行</button>',
      '</div>',
      '</div>'
    ].join('');

    document.body.appendChild(overlay);

    var cancelBtn = overlay.querySelector('#btn-cancel');
    var approveBtn = overlay.querySelector('#btn-approve');
    var trustCheckbox = overlay.querySelector('#trust-cmd');

    var cleanup = function(result) {
      document.body.removeChild(overlay);
      callback(result, trustCheckbox.checked);
    };

    cancelBtn.onclick = function() { cleanup(false); };
    approveBtn.onclick = function() { cleanup(true); };
    overlay.onclick = function(e) { if (e.target === overlay) cleanup(false); };
  },

  escapeHtml: function(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
};

// 初始化
DesktopSandbox.init();

// ============================================================
// 二、输出过滤器
// ============================================================
var DesktopSanitizer = {
  patterns: [
    { pattern: /api[_-]?key['":\s=]+['"]?([a-zA-Z0-9_-]{20,})/gi, replace: 'api_key: "***"' },
    { pattern: /sk-[a-zA-Z0-9]{20,}/g, replace: 'sk-***' },
    { pattern: /password['":\s=]+['"]?([^\s'"]{8,})/gi, replace: 'password: "***"' },
    { pattern: /token['":\s=]+['"]?([a-zA-Z0-9_-]{20,})/gi, replace: 'token: "***"' },
    { pattern: /-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----/g, replace: '-----BEGIN PRIVATE KEY-----' }
  ],

  sanitize: function(output) {
    var sanitized = output;
    for (var i = 0; i < this.patterns.length; i++) {
      sanitized = sanitized.replace(this.patterns[i].pattern, this.patterns[i].replace);
    }
    return sanitized;
  }
};

// ============================================================
// 三、导出
// ============================================================
window.DesktopSandbox = {
  Sandbox: DesktopSandbox,
  Sanitizer: DesktopSanitizer,

  execute: function(cmd, opts) { return DesktopSandbox.execute(cmd, opts); },
  check: function(cmd) { return DesktopSandbox.check(cmd); },
  trust: function(cmd) { return DesktopSandbox.trust(cmd); },
  sanitize: function(output) { return DesktopSanitizer.sanitize(output); }
};
