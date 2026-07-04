/**
 * Y·NEX Desktop — Trigger Engine
 * 触发器引擎，支持定时触发、Webhook触发和事件触发
 */

const EventEmitter = require('events');
const http = require('http');

// ============================================================
// 触发器类型
// ============================================================

const TRIGGER_TYPES = {
  SCHEDULE: 'schedule',     // 定时触发（cron表达式）
  INTERVAL: 'interval',     // 间隔触发
  WEBHOOK: 'webhook',       // Webhook 触发
  EVENT: 'event',           // 事件触发
  DATE: 'date',             // 单次日期触发
};

// ============================================================
// 触发器
// ============================================================

class Trigger {
  constructor(config) {
    this.id = config.id || `trigger_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    this.name = config.name || '触发器';
    this.description = config.description || '';
    this.type = config.type || TRIGGER_TYPES.SCHEDULE;
    this.enabled = config.enabled !== undefined ? config.enabled : true;
    this.target = config.target || { type: 'workflow', id: null }; // workflow | agent | chat
    this.config = config.config || {};
    this.createdAt = Date.now();
    this.lastRunAt = null;
    this.runCount = 0;
    this.status = 'idle';
  }

  toJSON() {
    return {
      id: this.id,
      name: this.name,
      description: this.description,
      type: this.type,
      enabled: this.enabled,
      target: this.target,
      config: this.config,
      createdAt: this.createdAt,
      lastRunAt: this.lastRunAt,
      runCount: this.runCount,
      status: this.status,
    };
  }

  static fromJSON(data) {
    const trigger = new Trigger(data);
    trigger.createdAt = data.createdAt;
    trigger.lastRunAt = data.lastRunAt;
    trigger.runCount = data.runCount || 0;
    trigger.status = data.status || 'idle';
    return trigger;
  }
}

// ============================================================
// Cron 表达式解析器（简化版）
// ============================================================

function parseCron(expr) {
  const parts = expr.trim().split(/\s+/);
  if (parts.length < 5) {
    throw new Error('Cron 表达式至少需要 5 个部分');
  }

  return {
    minute: parseField(parts[0], 0, 59),
    hour: parseField(parts[1], 0, 23),
    dayOfMonth: parseField(parts[2], 1, 31),
    month: parseField(parts[3], 1, 12),
    dayOfWeek: parseField(parts[4], 0, 6),
  };
}

function parseField(field, min, max) {
  if (field === '*') return { type: 'all', min, max };
  
  if (field.startsWith('*/')) {
    return { type: 'step', step: parseInt(field.slice(2)), min, max };
  }
  
  if (field.includes(',')) {
    return { type: 'list', values: field.split(',').map(v => parseInt(v)) };
  }
  
  if (field.includes('-')) {
    const [start, end] = field.split('-').map(v => parseInt(v));
    return { type: 'range', start, end };
  }
  
  return { type: 'value', value: parseInt(field) };
}

function checkCron(schedule, date) {
  const minute = date.getMinutes();
  const hour = date.getHours();
  const dayOfMonth = date.getDate();
  const month = date.getMonth() + 1;
  const dayOfWeek = date.getDay();

  return (
    matchField(schedule.minute, minute) &&
    matchField(schedule.hour, hour) &&
    matchField(schedule.dayOfMonth, dayOfMonth) &&
    matchField(schedule.month, month) &&
    matchField(schedule.dayOfWeek, dayOfWeek)
  );
}

function matchField(field, value) {
  switch (field.type) {
    case 'all': return true;
    case 'value': return field.value === value;
    case 'list': return field.values.includes(value);
    case 'range': return value >= field.start && value <= field.end;
    case 'step': return (value - field.min) % field.step === 0 && value >= field.min && value <= field.max;
    default: return false;
  }
}

// ============================================================
// 触发器引擎
// ============================================================

class TriggerEngine extends EventEmitter {
  constructor(workflowEngine, multiAgentOrchestrator) {
    super();
    this.triggers = new Map(); // id -> Trigger
    this.timers = new Map();   // id -> timer
    this.workflowEngine = workflowEngine;
    this.multiAgentOrchestrator = multiAgentOrchestrator;
    this.webhookServer = null;
    this.webhookPort = 8765;
    this.checkInterval = null;
    this._isRunning = false;
  }

  // ============================================================
  // 触发器管理
  // ============================================================

  createTrigger(config) {
    const trigger = new Trigger(config);
    this.triggers.set(trigger.id, trigger);
    
    if (trigger.enabled) {
      this._activateTrigger(trigger);
    }
    
    this.emit('trigger:created', trigger);
    return trigger;
  }

  getTrigger(id) {
    return this.triggers.get(id);
  }

  listTriggers() {
    return Array.from(this.triggers.values()).map(t => t.toJSON());
  }

  deleteTrigger(id) {
    const trigger = this.triggers.get(id);
    if (!trigger) return false;
    
    this._deactivateTrigger(trigger);
    this.triggers.delete(id);
    this.emit('trigger:deleted', id);
    return true;
  }

  enableTrigger(id) {
    const trigger = this.triggers.get(id);
    if (!trigger) return false;
    
    trigger.enabled = true;
    this._activateTrigger(trigger);
    this.emit('trigger:enabled', id);
    return true;
  }

  disableTrigger(id) {
    const trigger = this.triggers.get(id);
    if (!trigger) return false;
    
    trigger.enabled = false;
    this._deactivateTrigger(trigger);
    this.emit('trigger:disabled', id);
    return true;
  }

  // ============================================================
  // 引擎控制
  // ============================================================

  start() {
    if (this._isRunning) return;
    
    this._isRunning = true;
    this._startCronChecker();
    this._startWebhookServer();
    
    // 激活所有已启用的触发器
    for (const trigger of this.triggers.values()) {
      if (trigger.enabled) {
        this._activateTrigger(trigger);
      }
    }
    
    console.log('[TriggerEngine] 触发器引擎已启动');
  }

  stop() {
    if (!this._isRunning) return;
    
    this._isRunning = false;
    
    if (this.checkInterval) {
      clearInterval(this.checkInterval);
      this.checkInterval = null;
    }
    
    if (this.webhookServer) {
      this.webhookServer.close();
      this.webhookServer = null;
    }
    
    // 停用所有触发器
    for (const trigger of this.triggers.values()) {
      this._deactivateTrigger(trigger);
    }
    
    console.log('[TriggerEngine] 触发器引擎已停止');
  }

  // ============================================================
  // 内部方法
  // ============================================================

  _activateTrigger(trigger) {
    switch (trigger.type) {
      case TRIGGER_TYPES.INTERVAL:
        this._activateIntervalTrigger(trigger);
        break;
      case TRIGGER_TYPES.DATE:
        this._activateDateTrigger(trigger);
        break;
      case TRIGGER_TYPES.SCHEDULE:
        // cron 触发器由全局检查器处理
        break;
      case TRIGGER_TYPES.WEBHOOK:
        // webhook 触发器由 webhook 服务器处理
        break;
      case TRIGGER_TYPES.EVENT:
        // 事件触发器由事件系统处理
        break;
    }
  }

  _deactivateTrigger(trigger) {
    const timer = this.timers.get(trigger.id);
    if (timer) {
      clearTimeout(timer);
      clearInterval(timer);
      this.timers.delete(trigger.id);
    }
  }

  _activateIntervalTrigger(trigger) {
    const interval = trigger.config.interval || 60000; // 默认60秒
    const timer = setInterval(() => {
      this._runTrigger(trigger);
    }, interval);
    this.timers.set(trigger.id, timer);
  }

  _activateDateTrigger(trigger) {
    const targetDate = new Date(trigger.config.date);
    const now = Date.now();
    const delay = targetDate.getTime() - now;
    
    if (delay > 0) {
      const timer = setTimeout(() => {
        this._runTrigger(trigger);
        // 单次触发后禁用
        this.disableTrigger(trigger.id);
      }, delay);
      this.timers.set(trigger.id, timer);
    }
  }

  _startCronChecker() {
    this.checkInterval = setInterval(() => {
      const now = new Date();
      
      for (const trigger of this.triggers.values()) {
        if (!trigger.enabled || trigger.type !== TRIGGER_TYPES.SCHEDULE) continue;
        
        try {
          const schedule = parseCron(trigger.config.cron || '* * * * *');
          if (checkCron(schedule, now)) {
            // 避免重复触发（检查上一次运行时间）
            if (!trigger.lastRunAt || (now.getTime() - trigger.lastRunAt > 55000)) {
              this._runTrigger(trigger);
            }
          }
        } catch (e) {
          console.warn(`[TriggerEngine] Cron解析失败 [${trigger.name}]:`, e.message);
        }
      }
    }, 30000); // 每30秒检查一次
  }

  _startWebhookServer() {
    this.webhookServer = http.createServer((req, res) => {
      if (req.method === 'POST' && req.url.startsWith('/webhook/')) {
        const triggerId = req.url.slice(9); // 去掉 "/webhook/"
        const trigger = this.triggers.get(triggerId);
        
        if (trigger && trigger.enabled && trigger.type === TRIGGER_TYPES.WEBHOOK) {
          let body = '';
          req.on('data', chunk => body += chunk);
          req.on('end', () => {
            try {
              const data = JSON.parse(body);
              this._runTrigger(trigger, { webhookData: data });
              res.writeHead(200, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ ok: true, message: 'Webhook 已接收' }));
            } catch (e) {
              this._runTrigger(trigger, { webhookRaw: body });
              res.writeHead(200, { 'Content-Type': 'application/json' });
              res.end(JSON.stringify({ ok: true, message: 'Webhook 已接收' }));
            }
          });
        } else {
          res.writeHead(404);
          res.end('Trigger not found');
        }
      } else {
        res.writeHead(404);
        res.end('Not found');
      }
    });

    try {
      this.webhookServer.listen(this.webhookPort, () => {
        console.log(`[TriggerEngine] Webhook 服务器已启动在端口 ${this.webhookPort}`);
      });
    } catch (e) {
      console.warn('[TriggerEngine] Webhook 服务器启动失败:', e.message);
    }
  }

  async _runTrigger(trigger, context = {}) {
    trigger.status = 'running';
    trigger.lastRunAt = Date.now();
    trigger.runCount++;
    
    this.emit('trigger:fired', { triggerId: trigger.id, context });
    
    try {
      let result;
      
      switch (trigger.target.type) {
        case 'workflow':
          if (this.workflowEngine && trigger.target.id) {
            result = await this.workflowEngine.runWorkflow(trigger.target.id, context);
          }
          break;
        case 'agent':
          if (this.multiAgentOrchestrator && trigger.target.id) {
            result = await this.multiAgentOrchestrator.runTask(
              trigger.target.id,
              trigger.config.task || context.task || '执行自动化任务'
            );
          }
          break;
        case 'chat':
          // 聊天触发，发送到主窗口
          this.emit('trigger:chat', {
            triggerId: trigger.id,
            message: trigger.config.message || context.message,
            context,
          });
          break;
      }
      
      trigger.status = 'success';
      this.emit('trigger:completed', { triggerId: trigger.id, result });
      
      return { ok: true, result };
    } catch (e) {
      trigger.status = 'error';
      this.emit('trigger:error', { triggerId: trigger.id, error: e.message });
      
      return { ok: false, error: e.message };
    }
  }

  // ============================================================
  // 预设触发器模板
  // ============================================================

  createPresetTrigger(type) {
    const presets = {
      'daily_morning': {
        name: '每日早报',
        description: '每天早上 8 点生成每日早报',
        type: TRIGGER_TYPES.SCHEDULE,
        target: { type: 'workflow', id: null },
        config: { cron: '0 8 * * *' }
      },
      'hourly_check': {
        name: '每小时检查',
        description: '每小时执行一次检查任务',
        type: TRIGGER_TYPES.INTERVAL,
        target: { type: 'workflow', id: null },
        config: { interval: 3600000 }
      },
      'webhook_github': {
        name: 'GitHub Webhook',
        description: '接收 GitHub Webhook 触发工作流',
        type: TRIGGER_TYPES.WEBHOOK,
        target: { type: 'workflow', id: null },
        config: {}
      },
      'once_after_5min': {
        name: '5分钟后执行',
        description: '5分钟后执行一次任务',
        type: TRIGGER_TYPES.DATE,
        target: { type: 'workflow', id: null },
        config: { date: new Date(Date.now() + 5 * 60 * 1000).toISOString() }
      },
      'on_startup': {
        name: '应用启动时',
        description: '应用启动时自动执行',
        type: TRIGGER_TYPES.EVENT,
        target: { type: 'workflow', id: null },
        config: { event: 'app:started' }
      }
    };

    const preset = presets[type];
    if (!preset) return null;

    return this.createTrigger(preset);
  }
}

module.exports = {
  TriggerEngine,
  Trigger,
  TRIGGER_TYPES,
  parseCron,
  checkCron,
};