/**
 * TriGenClaw 桌面端安全确认系统 v2.0
 * 基于 Claude Code 设计理念
 * 不可逆操作的确认机制
 */
'use strict';

var DesktopSafetyConfirm = {
  // 危险操作定义
  DANGEROUS_OPERATIONS: {
    // 文件操作
    FILE_DELETE: {
      id: 'file_delete',
      name: '删除文件',
      patterns: [/rm\s+(-[rf]?\s+)*/i, /delete\s+file/i, /remove\s+file/i, /unlink/i],
      highRisk: true,
      message: '即将删除文件，此操作不可恢复。确认继续？'
    },
    DIR_DELETE: {
      id: 'dir_delete',
      name: '删除目录',
      patterns: [/rm\s+(-r?\s+)*.*\/$/i, /rmdir/i, /remove\s+directory/i],
      highRisk: true,
      message: '即将删除目录及其所有内容，此操作不可恢复。确认继续？'
    },

    // Git 操作
    GIT_FORCE_PUSH: {
      id: 'git_force_push',
      name: '强制推送',
      patterns: [/git\s+push\s+(-f|--force)/i],
      highRisk: true,
      message: '强制推送会覆盖远程历史，此操作危险且不可恢复！确认继续？'
    },
    GIT_RESET_HARD: {
      id: 'git_reset_hard',
      name: '强制重置',
      patterns: [/git\s+reset\s+(--hard|--mixed)/i],
      highRisk: true,
      message: 'Git 重置会丢失未提交的更改！确认继续？'
    },
    GIT_PUSH: {
      id: 'git_push',
      name: '推送到远程',
      patterns: [/git\s+push/i],
      risk: 'medium',
      message: '即将推送到远程仓库。确认继续？'
    },

    // 系统命令
    SYSTEM_KILL: {
      id: 'system_kill',
      name: '终止进程',
      patterns: [/kill\s+(-9\s+)?\d+/i, /pkill/i, /killall/i],
      highRisk: true,
      message: '即将终止进程，可能导致数据丢失。确认继续？'
    },
    SYSTEM_REBOOT: {
      id: 'system_reboot',
      name: '系统重启',
      patterns: [/reboot/i, /shutdown/i, /init\s+6/i],
      highRisk: true,
      message: '即将重启系统，所有未保存工作将丢失！确认继续？'
    },

    // 数据库操作
    DB_DROP: {
      id: 'db_drop',
      name: '删除数据库',
      patterns: [/drop\s+(table|database)/i],
      highRisk: true,
      message: '此操作会永久删除数据！确认继续？'
    },
    DB_TRUNCATE: {
      id: 'db_truncate',
      name: '清空数据表',
      patterns: [/truncate\s+\w+/i],
      risk: 'medium',
      message: '即将清空数据表内容，此操作不可恢复。确认继续？'
    },

    // 网络操作
    NETWORK_SEND: {
      id: 'network_send',
      name: '发送敏感数据',
      patterns: [/curl\s+(-X\s+POST|-d|--data)/i, /wget/i],
      risk: 'medium',
      message: '即将发送数据到外部服务。确认继续？'
    },

    // 外部命令执行
    EXEC_EXTERNAL: {
      id: 'exec_external',
      name: '执行动态命令',
      patterns: [/\$\(.*\)/i, /`.*`/i, /eval\s+/i],
      highRisk: true,
      message: '即将执行动态生成的命令，可能存在安全风险。确认继续？'
    },

    // 批量操作
    BATCH_DELETE: {
      id: 'batch_delete',
      name: '批量删除',
      patterns: [/\*\s*\|\s*xargs\s+rm/i, /find\s+.*-delete/i],
      highRisk: true,
      message: '批量删除操作影响范围广！确认继续？'
    }
  },

  // 信任状态
  trusted: {},

  // 分析命令
  analyze: function(command) {
    var matches = [];
    var ops = this.DANGEROUS_OPERATIONS;

    for (var key in ops) {
      if (!ops.hasOwnProperty(key)) continue;
      var op = ops[key];
      for (var i = 0; i < op.patterns.length; i++) {
        if (op.patterns[i].test(command)) {
          matches.push(op);
          break;
        }
      }
    }

    return matches;
  },

  // 检查是否已信任
  isTrusted: function(operationId) {
    return this.trusted[operationId] === true;
  },

  // 添加信任
  trust: function(operationId) {
    this.trusted[operationId] = true;
  },

  // 移除信任
  untrust: function(operationId) {
    delete this.trusted[operationId];
  },

  // 清空信任
  clearTrust: function() {
    this.trusted = {};
  },

  // 请求确认
  requestConfirm: function(operation, onConfirm, onCancel) {
    var self = this;

    // 如果已信任，直接执行
    if (this.isTrusted(operation.id)) {
      if (typeof onConfirm === 'function') onConfirm();
      return;
    }

    // 显示确认对话框
    this.showDialog(operation, function(trusted) {
      if (trusted) {
        self.trust(operation.id);
      }
      if (typeof (trusted ? onConfirm : onCancel) === 'function') {
        (trusted ? onConfirm : onCancel)();
      }
    });
  },

  // 显示确认对话框
  showDialog: function(operation, callback) {
    var overlay = document.createElement('div');
    overlay.style.cssText = [
      'position:fixed',
      'top:0', 'left:0', 'right:0', 'bottom:0',
      'background:rgba(0,0,0,0.7)',
      'display:flex',
      'align-items:center',
      'justify-content:center',
      'z-index:10000'
    ].join(';');

    var dialog = document.createElement('div');
    dialog.style.cssText = [
      'background:#1a1035',
      'border:1px solid rgba(155,89,247,0.15)',
      'border-radius:12px',
      'padding:24px',
      'max-width:480px',
      'width:90%',
      'box-shadow:0 20px 60px rgba(0,0,0,0.5)'
    ].join(';');

    var icon = operation.highRisk ? '⚠️' : '⚡';
    var btnColor = operation.highRisk ? '#ef4444' : '#9b59f7';

    dialog.innerHTML = [
      '<div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">',
      '<span style="font-size:2rem">' + icon + '</span>',
      '<h3 style="margin:0;font-size:1.2rem;color:#e8e0f0">' + operation.name + '</h3>',
      '</div>',
      '<p style="color:#9d92b5;margin-bottom:20px;font-size:0.95rem;line-height:1.6">',
      operation.message || '此操作可能具有风险。确认继续？',
      '</p>',
      '<div style="display:flex;gap:12px;justify-content:flex-end">',
      '<label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-size:0.85rem;color:#9d92b5;margin-right:auto">',
      '<input type="checkbox" id="trust-op">',
      '信任此类操作',
      '</label>',
      '<button id="btn-cancel" style="padding:8px 20px;border-radius:6px;border:1px solid rgba(155,89,247,0.15);background:transparent;color:#e8e0f0;cursor:pointer;font-size:0.9rem">取消</button>',
      '<button id="btn-confirm" style="padding:8px 20px;border-radius:6px;border:none;background:' + btnColor + ';color:white;cursor:pointer;font-size:0.9rem;font-weight:600">确认执行</button>',
      '</div>'
    ].join('');

    overlay.appendChild(dialog);
    document.body.appendChild(overlay);

    // 事件绑定
    var cancelBtn = dialog.querySelector('#btn-cancel');
    var confirmBtn = dialog.querySelector('#btn-confirm');
    var trustCheckbox = dialog.querySelector('#trust-op');

    var close = function(result) {
      document.body.removeChild(overlay);
      callback(result);
    };

    cancelBtn.onclick = function() { close(false); };
    confirmBtn.onclick = function() { close(trustCheckbox.checked); };
    overlay.onclick = function(e) {
      if (e.target === overlay) close(false);
    };
  },

  // 执行前检查
  checkBeforeExecute: function(command) {
    var dangerous = this.analyze(command);
    if (dangerous.length === 0) return Promise.resolve(true);

    var self = this;
    return new Promise(function(resolve) {
      self.requestConfirm(
        dangerous[0],
        function() { resolve(true); },
        function() { resolve(false); }
      );
    });
  }
};

// ============================================================
// 敏感信息过滤器
// ============================================================
var DesktopOutputFilter = {
  patterns: [
    { pattern: /api[_-]?key['":\s=]+['"]?([a-zA-Z0-9_-]{20,})/gi, replace: 'api_key: "***"' },
    { pattern: /sk-[a-zA-Z0-9]{20,}/g, replace: 'sk-***' },
    { pattern: /sk-ant-[a-zA-Z0-9]{20,}/g, replace: 'sk-ant-***' },
    { pattern: /password['":\s=]+['"]?([^\s'"]{8,})/gi, replace: 'password: "***"' },
    { pattern: /token['":\s=]+['"]?([a-zA-Z0-9_-]{20,})/gi, replace: 'token: "***"' },
    { pattern: /bearer\s+[a-zA-Z0-9_-]{20,}/gi, replace: 'bearer ***' },
    { pattern: /-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----/g, replace: '-----BEGIN PRIVATE KEY-----' },
    { pattern: /(mongodb|postgres|mysql):\/\/[^@]+@[^\s'"]+/gi, replace: '***://***@host' }
  ],

  filter: function(output) {
    var filtered = output;
    for (var i = 0; i < this.patterns.length; i++) {
      filtered = filtered.replace(this.patterns[i].pattern, this.patterns[i].replace);
    }
    return filtered;
  }
};

// ============================================================
// 导出
// ============================================================
window.DesktopSafety = {
  Confirm: DesktopSafetyConfirm,
  Filter: DesktopOutputFilter
};
