/* ========================================
   Plugin Runtime v2 - Enhanced Plugin System
   Skills 注册为运行时插件，支持 Hook 机制
   支持数据管线、异步插件、依赖管理
   ======================================== */
var NexusPlugins = (function() {
  'use strict';

  var _registry = {};
  var _hooks = {};
  var _hookMetadata = {};

  /** 注册插件 */
  function register(plugin) {
    if (!plugin || !plugin.id) return false;
    if (_registry[plugin.id]) {
      console.warn('[Plugin] Overwriting existing plugin:', plugin.id);
    }

    _registry[plugin.id] = plugin;

    // 注册 hooks
    if (plugin.hooks) {
      for (var h in plugin.hooks) {
        if (typeof plugin.hooks[h] === 'function') {
          if (!_hooks[h]) _hooks[h] = [];
          var wrapped = plugin.hooks[h];
          wrapped._pluginId = plugin.id;
          wrapped._priority = plugin.priority || 0;
          _hooks[h].push(wrapped);
          // 按优先级排序
          _hooks[h].sort(function(a, b) { return (b._priority || 0) - (a._priority || 0); });
        }
      }
    }

    // 调 lifecycle.init
    if (typeof plugin.onInit === 'function') {
      try { plugin.onInit(); } catch(e) { console.error('[Plugin] init error:', plugin.id, e); }
    }

    try {
      if (typeof NexusUI !== 'undefined' && NexusUI.toast) {
        NexusUI.toast('Plugin: ' + (plugin.name || plugin.id), 'info');
      }
    } catch(e) {}
    return true;
  }

  /** 注销插件 */
  function unregister(id) {
    var plugin = _registry[id];

    // 调 lifecycle.destroy
    if (plugin && typeof plugin.onDestroy === 'function') {
      try { plugin.onDestroy(); } catch(e) { console.error('[Plugin] destroy error:', id, e); }
    }

    delete _registry[id];
    for (var h in _hooks) {
      _hooks[h] = _hooks[h].filter(function(fn) { return fn._pluginId !== id; });
    }
  }

  /** 同步派发 Hook（数据管线） */
  function dispatch(hook, data) {
    if (!_hooks[hook]) return data;
    var result = data;
    for (var i = 0; i < _hooks[hook].length; i++) {
      try {
        var r = _hooks[hook][i](result);
        if (r !== undefined) result = r;
      } catch(e) {
        console.error('[Plugin] hook error [' + hook + ']:', e);
      }
    }
    return result;
  }

  /** 异步派发 Hook（适用于 onAfterSend 等需要 Promise 的场景） */
  function dispatchAsync(hook, data) {
    if (!_hooks[hook]) return Promise.resolve(data);
    var chain = Promise.resolve(data);
    for (var i = 0; i < _hooks[hook].length; i++) {
      chain = chain.then(function(fn, prev) {
        return function(current) {
          try {
            var r = fn(current);
            return (r && typeof r.then === 'function') ? r : (r !== undefined ? r : current);
          } catch(e) {
            console.error('[Plugin] async hook error:', e);
            return current;
          }
        };
      }(_hooks[hook][i]));
    }
    return chain;
  }

  /** 获取注册了某 hook 的插件列表 */
  function getHookPlugins(hook) {
    if (!_hooks[hook]) return [];
    return _hooks[hook].map(function(fn) { return _registry[fn._pluginId]; }).filter(Boolean);
  }

  /** 获取已注册插件列表 */
  function list() {
    return Object.keys(_registry).map(function(id) {
      var p = _registry[id];
      return {
        id: id,
        name: p.name || id,
        version: p.version || '1.0',
        hooks: p.hooks ? Object.keys(p.hooks) : []
      };
    });
  }

  /** 获取插件详情 */
  function get(id) {
    return _registry[id] || null;
  }

  /** 清理所有插件 */
  function clear() {
    Object.keys(_registry).forEach(function(id) { unregister(id); });
    _hooks = {};
  }

  return {
    register: register,
    unregister: unregister,
    dispatch: dispatch,
    dispatchAsync: dispatchAsync,
    getHookPlugins: getHookPlugins,
    list: list,
    get: get,
    clear: clear
  };
})();
