const http = require('http');

const YNEX_API_BASE = 'http://127.0.0.1:7777';

const YNEX_BUILTIN_SKILLS = [
  { name: 'get_weather', description: '查询城市天气', category: 'weather', icon: '🌤️' },
  { name: 'get_time', description: '获取当前时间', category: 'system', icon: '⏰' },
  { name: 'get_system_info', description: '获取系统信息', category: 'system', icon: '💻' },
  { name: 'search_file', description: '搜索本地文件', category: 'file', icon: '🔍' },
  { name: 'set_reminder', description: '设置提醒事项', category: 'reminder', icon: '⏰' },
  { name: 'list_reminders', description: '查看提醒列表', category: 'reminder', icon: '📋' },
  { name: 'cancel_reminder', description: '取消提醒', category: 'reminder', icon: '❌' },
  { name: 'open_application', description: '打开应用程序', category: 'system', icon: '📱' },
  { name: 'write_note', description: '写笔记', category: 'note', icon: '📝' },
  { name: 'read_notes', description: '读取笔记', category: 'note', icon: '📖' },
  { name: 'tell_joke', description: '讲笑话', category: 'entertainment', icon: '😄' },
  { name: 'list_ha_entities', description: '列出HA设备', category: 'home_assistant', icon: '🏠' },
  { name: 'control_ha_device', description: '控制HA设备', category: 'home_assistant', icon: '🎛️' },
  { name: 'get_ha_entity_state', description: '获取HA设备状态', category: 'home_assistant', icon: '📊' },
  { name: 'list_ha_scenes', description: '列出HA场景', category: 'home_assistant', icon: '🎬' },
  { name: 'activate_ha_scene', description: '激活HA场景', category: 'home_assistant', icon: '✨' },
  { name: 'list_ha_areas', description: '列出HA区域', category: 'home_assistant', icon: '🗺️' },
  { name: 'get_ha_sensor', description: '获取HA传感器数据', category: 'home_assistant', icon: '🌡️' },
  { name: 'read_emails', description: '读取邮件', category: 'email', icon: '📧' },
  { name: 'send_email', description: '发送邮件', category: 'email', icon: '✉️' },
  { name: 'add_event', description: '添加日历事件', category: 'calendar', icon: '📅' },
  { name: 'list_events', description: '查看日历事件', category: 'calendar', icon: '📆' },
  { name: 'read_webpage', description: '读取网页内容', category: 'browser', icon: '🌐' },
  { name: 'search_web', description: '搜索网络信息', category: 'browser', icon: '🔍' },
  { name: 'run_browser_task', description: '执行浏览器任务', category: 'browser', icon: '🤖' },
  { name: 'safe_eval', description: '安全计算表达式', category: 'code', icon: '🧮' },
  { name: 'execute_shell', description: '执行Shell命令', category: 'code', icon: '💻' },
  { name: 'execute_python', description: '执行Python代码', category: 'code', icon: '🐍' },
  { name: 'run_multi_agent_task', description: '多Agent协作任务', category: 'agent', icon: '🤖' },
  { name: 'control_pc', description: '控制电脑（窗口/键鼠/音量）', category: 'device', icon: '🖥️' },
  { name: 'device_command', description: '设备控制命令', category: 'device', icon: '📱' },
  { name: 'list_device_domains', description: '列出设备分类', category: 'device', icon: '📂' },
  { name: 'mqtt_publish', description: '发送MQTT消息', category: 'iot', icon: '📡' },
  { name: 'add_automation_rule', description: '添加自动化规则', category: 'automation', icon: '⚙️' },
  { name: 'list_automation_rules', description: '列出自动化规则', category: 'automation', icon: '📋' },
  { name: 'vision_check', description: '视觉检测', category: 'multimedia', icon: '👁️' },
  { name: 'vision_snapshot', description: '视觉快照', category: 'multimedia', icon: '📷' },
  { name: 'search_docs', description: '搜索文档', category: 'knowledge', icon: '📚' },
  { name: 'upload_doc', description: '上传文档', category: 'knowledge', icon: '📤' },
  { name: 'search_photos', description: '搜索照片', category: 'multimedia', icon: '🖼️' },
  { name: 'memory_lane', description: '回忆记忆', category: 'memory', icon: '🧠' },
  { name: 'upload_photo', description: '上传照片', category: 'multimedia', icon: '📸' },
  { name: 'list_workflows', description: '列出工作流', category: 'automation', icon: '🔄' },
  { name: 'trigger_workflow', description: '触发工作流', category: 'automation', icon: '▶️' },
  { name: 'selfhost_status', description: '自托管服务状态', category: 'system', icon: '🖥️' },
  { name: 'super_agent_task', description: '超级Agent任务', category: 'agent', icon: '🦸' },
  { name: 'agent_chat', description: 'Agent对话', category: 'agent', icon: '💬' },
  { name: 'write_code', description: '写代码项目', category: 'code', icon: '💻' },
  { name: 'local_llm_status', description: '本地LLM状态', category: 'system', icon: '🧠' },
];

class UnifiedToolRegistry {
  constructor() {
    this.tools = new Map();
    this.sources = new Map();
    this._mcpManager = null;
    this._ynexReady = false;
    this._ynexPingTimer = null;
  }

  setMcpManager(mcpManager) {
    this._mcpManager = mcpManager;
  }

  async init() {
    await this._loadYnexSkills();
    await this._loadMcpTools();
    this._startYnnexHealthCheck();
    console.log(`[ToolRegistry] 初始化完成，共 ${this.tools.size} 个工具`);
    return { ok: true, total: this.tools.size };
  }

  async _loadYnexSkills() {
    try {
      const alive = await this._ynnexPing();
      if (!alive) {
        console.warn('[ToolRegistry] YNEX服务未启动，使用内置技能列表');
        this._ynexReady = false;
      } else {
        this._ynexReady = true;
      }
      
      for (const s of YNEX_BUILTIN_SKILLS) {
        const toolKey = `yntex_${s.name}`;
        this.tools.set(toolKey, {
          name: toolKey,
          displayName: s.name,
          description: s.description || s.name,
          category: s.category || 'yntex',
          source: 'yntex',
          inputSchema: this._defaultSchema(),
          dangerous: this._isDangerous(s.name),
          icon: s.icon || this._getIcon(s.category),
        });
      }
      
      this.sources.set('yntex', { name: 'YNEX技能', count: YNEX_BUILTIN_SKILLS.length });
      console.log(`[ToolRegistry] YNEX技能加载: ${YNEX_BUILTIN_SKILLS.length} 个 (服务状态: ${this._ynexReady ? '在线' : '离线'})`);
    } catch (e) {
      console.warn(`[ToolRegistry] YNEX技能加载失败: ${e.message}`);
      this._ynexReady = false;
    }
  }

  async _loadMcpTools() {
    if (!this._mcpManager) return;
    try {
      let mcpTotal = 0;
      for (const [name, server] of this._mcpManager.servers.entries()) {
        if (server.tools && server.tools.length > 0) {
          for (const t of server.tools) {
            const toolKey = `mcp_${name}_${t.name}`;
            this.tools.set(toolKey, {
              name: toolKey,
              displayName: t.name,
              description: t.description || t.name,
              category: 'mcp_' + name,
              source: 'mcp',
              mcpServer: name,
              inputSchema: t.inputSchema || this._defaultSchema(),
              dangerous: this._isDangerous(t.name),
              icon: '🔌',
            });
          }
          mcpTotal += server.tools.length;
        }
      }
      if (mcpTotal > 0) {
        this.sources.set('mcp', { name: 'MCP工具', count: mcpTotal });
        console.log(`[ToolRegistry] MCP工具加载: ${mcpTotal} 个`);
      }
    } catch (e) {
      console.warn(`[ToolRegistry] MCP工具加载失败: ${e.message}`);
    }
  }

  list(options = {}) {
    const { category, source, search, dangerous: showDangerous } = options;
    let result = Array.from(this.tools.values());
    
    if (category) {
      result = result.filter(t => t.category === category);
    }
    if (source) {
      result = result.filter(t => t.source === source);
    }
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(t => 
        t.name.toLowerCase().includes(q) || 
        (t.description || '').toLowerCase().includes(q)
      );
    }
    if (showDangerous === false) {
      result = result.filter(t => !t.dangerous);
    }
    
    return result;
  }

  getTool(name) {
    return this.tools.get(name);
  }

  categories() {
    const cats = new Map();
    for (const t of this.tools.values()) {
      const c = t.category || 'other';
      if (!cats.has(c)) {
        cats.set(c, { name: c, count: 0, icon: t.icon || '📦' });
      }
      cats.get(c).count++;
    }
    return Array.from(cats.values()).sort((a, b) => b.count - a.count);
  }

  async callTool(name, args, ctx = {}) {
    const tool = this.tools.get(name);
    if (!tool) {
      return { ok: false, error: `工具不存在: ${name}` };
    }

    try {
      if (tool.source === 'yntex') {
        return await this._callYntexTool(tool, args, ctx);
      } else if (tool.source === 'mcp') {
        return await this._callMcpTool(tool, args, ctx);
      } else {
        return { ok: false, error: `未知工具来源: ${tool.source}` };
      }
    } catch (e) {
      console.error(`[ToolRegistry] 调用工具 ${name} 失败:`, e);
      return { ok: false, error: e.message };
    }
  }

  async _callYntexTool(tool, args, ctx) {
    if (!this._ynexReady) {
      return { ok: false, error: 'YNEX服务未启动，无法调用该技能' };
    }
    
    const result = await this._ynnexRequest('POST', '/command', {
      tool: tool.displayName,
      ...args,
    });
    
    if (result && result.result !== undefined) {
      return { ok: true, result: result.result, raw: result };
    } else if (result && result.error) {
      return { ok: false, error: result.error };
    } else {
      return { ok: false, error: '工具执行失败' };
    }
  }

  async _callMcpTool(tool, args, ctx) {
    if (!this._mcpManager) {
      return { ok: false, error: 'MCP Manager 未初始化' };
    }
    try {
      const result = await this._mcpManager.callTool(tool.mcpServer, tool.displayName, args);
      return { ok: true, result: result, raw: result };
    } catch (e) {
      return { ok: false, error: e.message };
    }
  }

  _ynnexRequest(method, path, body) {
    return new Promise((resolve, reject) => {
      const url = YNEX_API_BASE + path;
      const urlObj = new URL(url);
      
      const options = {
        hostname: urlObj.hostname,
        port: urlObj.port || 7777,
        path: urlObj.pathname + urlObj.search,
        method: method,
        headers: {
          'Content-Type': 'application/json',
        },
      };

      const req = http.request(options, (res) => {
        let data = '';
        res.on('data', (chunk) => data += chunk);
        res.on('end', () => {
          try {
            resolve(JSON.parse(data));
          } catch (e) {
            resolve({ ok: false, error: '响应解析失败', raw: data });
          }
        });
      });

      req.on('error', (err) => reject(err));
      
      if (body && method !== 'GET') {
        req.write(JSON.stringify(body));
      }
      
      req.end();
    });
  }

  _startYnnexHealthCheck() {
    this._ynexPingTimer = setInterval(async () => {
      try {
        const alive = await this._ynnexPing();
        if (alive && !this._ynexReady) {
          console.log('[ToolRegistry] YNEX服务已恢复');
          this._ynexReady = true;
        } else if (!alive && this._ynexReady) {
          console.warn('[ToolRegistry] YNEX服务断开');
          this._ynexReady = false;
        }
      } catch (e) {
        if (this._ynexReady) {
          console.warn('[ToolRegistry] YNEX服务断开');
          this._ynexReady = false;
        }
      }
    }, 30000);
  }

  async _ynnexPing() {
    try {
      const result = await this._ynnexRequest('GET', '/status');
      return result && result.status === 'running';
    } catch (e) {
      return false;
    }
  }

  _isDangerous(name) {
    const dangerousKeywords = ['delete', 'remove', 'execute', 'shell', 'command', 'write', 'send', 'control', 'publish'];
    const n = name.toLowerCase();
    return dangerousKeywords.some(kw => n.includes(kw));
  }

  _getIcon(category) {
    const iconMap = {
      'yntex': '⚡',
      'weather': '🌤️',
      'file': '📁',
      'system': '💻',
      'home_assistant': '🏠',
      'email': '📧',
      'calendar': '📅',
      'browser': '🌐',
      'code': '💻',
      'device': '📱',
      'automation': '🤖',
      'knowledge': '📚',
      'memory': '🧠',
      'voice': '🎤',
      'multimedia': '🎨',
      'reminder': '⏰',
      'note': '📝',
    };
    return iconMap[category] || '🔧';
  }

  _defaultSchema() {
    return {
      type: 'object',
      properties: {
        input: { type: 'string', description: '输入参数' }
      },
      required: []
    };
  }

  destroy() {
    if (this._ynexPingTimer) {
      clearInterval(this._ynexPingTimer);
      this._ynexPingTimer = null;
    }
    this.tools.clear();
    this.sources.clear();
  }
}

const toolRegistry = new UnifiedToolRegistry();

module.exports = { UnifiedToolRegistry, toolRegistry };
