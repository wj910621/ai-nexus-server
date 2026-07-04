/**
 * Y·NEX Desktop — 插件 SDK
 * 提供插件开发接口：注册命令、添加面板、扩展编辑器
 */

const fs = require('fs');
const path = require('path');
const { EventEmitter } = require('events');

class PluginSDK extends EventEmitter {
  constructor() {
    super();
    this.plugins = new Map();
    this.hooks = new Map();
    this.pluginDir = null;
  }

  /**
   * 初始化插件系统
   */
  init(pluginDir) {
    this.pluginDir = pluginDir;
    if (!fs.existsSync(pluginDir)) {
      fs.mkdirSync(pluginDir, { recursive: true });
    }
    this._loadAllPlugins();
  }

  /**
   * 加载所有插件
   */
  _loadAllPlugins() {
    if (!this.pluginDir) return;
    try {
      const dirs = fs.readdirSync(this.pluginDir, { withFileTypes: true });
      for (const entry of dirs) {
        if (entry.isDirectory()) {
          const manifestPath = path.join(this.pluginDir, entry.name, 'plugin.json');
          if (fs.existsSync(manifestPath)) {
            try {
              const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
              this._registerPlugin(entry.name, manifest);
            } catch (e) {
              console.warn(`[PluginSDK] 加载 ${entry.name} 失败:`, e.message);
            }
          }
        }
      }
    } catch (e) {}
  }

  _registerPlugin(name, manifest) {
    this.plugins.set(name, {
      ...manifest,
      name,
      enabled: manifest.enabled !== false,
      installedAt: new Date().toISOString()
    });
    this.emit('plugin:registered', name);
    console.log(`[PluginSDK] 插件注册: ${name}`);
  }

  /**
   * 创建新插件模板
   */
  createPlugin(name, options = {}) {
    if (!this.pluginDir) return { error: '插件目录未初始化' };
    const pluginPath = path.join(this.pluginDir, name);
    if (fs.existsSync(pluginPath)) return { error: '插件已存在' };

    const manifest = {
      name,
      version: options.version || '1.0.0',
      description: options.description || '',
      author: options.author || '',
      main: 'index.js',
      contributes: {
        commands: options.commands || [],
        views: options.views || [],
        snippets: options.snippets || [],
        themes: options.themes || []
      },
      activationEvents: options.activationEvents || ['*'],
      enabled: true
    };

    fs.mkdirSync(pluginPath, { recursive: true });
    fs.writeFileSync(path.join(pluginPath, 'plugin.json'), JSON.stringify(manifest, null, 2), 'utf-8');

    // 创建主入口文件模板
    const mainContent = `/**
 * ${name} Plugin for Y·NEX Desktop
 */
module.exports = {
  activate(context) {
    console.log('[${name}] 插件已激活');
    
    // 注册命令
    context.commands.register('${name}.hello', () => {
      return 'Hello from ${name}!';
    });
    
    // 注册视图
    context.views.register('${name}Panel', {
      title: '${name}',
      render: () => '<div>${name} Panel</div>'
    });
  },
  
  deactivate() {
    console.log('[${name}] 插件已停用');
  }
};
`;

    fs.writeFileSync(path.join(pluginPath, 'index.js'), mainContent, 'utf-8');
    this._registerPlugin(name, manifest);

    return { ok: true, path: pluginPath, manifest };
  }

  /**
   * 删除插件
   */
  removePlugin(name) {
    if (!this.pluginDir) return { error: '插件目录未初始化' };
    const pluginPath = path.join(this.pluginDir, name);
    if (fs.existsSync(pluginPath)) {
      fs.rmSync(pluginPath, { recursive: true, force: true });
    }
    this.plugins.delete(name);
    this.emit('plugin:removed', name);
    return { ok: true };
  }

  /**
   * 启用/禁用插件
   */
  togglePlugin(name) {
    const plugin = this.plugins.get(name);
    if (!plugin) return { error: '插件不存在' };
    plugin.enabled = !plugin.enabled;
    if (plugin.enabled) {
      this.emit('plugin:enabled', name);
    } else {
      this.emit('plugin:disabled', name);
    }
    return { ok: true, enabled: plugin.enabled };
  }

  /**
   * 列出所有插件
   */
  listPlugins() {
    return Array.from(this.plugins.entries()).map(([name, p]) => ({
      name,
      version: p.version,
      description: p.description,
      author: p.author,
      enabled: p.enabled,
      contributes: p.contributes
    }));
  }

  /**
   * 注册钩子
   */
  registerHook(name, handler) {
    if (!this.hooks.has(name)) {
      this.hooks.set(name, []);
    }
    this.hooks.get(name).push(handler);
  }

  /**
   * 触发钩子
   */
  triggerHook(name, ...args) {
    const handlers = this.hooks.get(name) || [];
    const results = [];
    for (const handler of handlers) {
      try {
        results.push(handler(...args));
      } catch (e) {
        console.warn(`[PluginSDK] Hook ${name} 错误:`, e.message);
      }
    }
    return results;
  }

  /**
   * 获取插件 API（供插件调用）
   */
  getPluginContext() {
    return {
      commands: {
        register: (name, handler) => this.registerHook(`command:${name}`, handler),
        execute: (name, ...args) => this.triggerHook(`command:${name}`, ...args)
      },
      views: {
        register: (name, view) => this.registerHook(`view:${name}`, view),
        render: (name) => this.triggerHook(`view:${name}`)
      },
      editor: {
        onDidChange: (handler) => this.registerHook('editor:change', handler),
        onDidSave: (handler) => this.registerHook('editor:save', handler)
      },
      workspace: {
        onDidChange: (handler) => this.registerHook('workspace:change', handler)
      }
    };
  }
}

module.exports = { PluginSDK };