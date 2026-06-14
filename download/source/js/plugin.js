/* ========================================
   Plugin Runtime - 插件运行时系统
   Skills 注册为运行时插件，支持 Hook 机制
   ======================================== */
var NexusPlugins = (function() {
  'use strict';

  var _registry = {};
  var _hooks = {};

  /** 注册插件 */
  function register(plugin) {
    if (!plugin || !plugin.id) return false;
    _registry[plugin.id] = plugin;
    if (plugin.hooks) {
      for (var h in plugin.hooks) {
        if (typeof plugin.hooks[h] === 'function') {
          if (!_hooks[h]) _hooks[h] = [];
          _hooks[h].push(plugin.hooks[h]);
        }
      }
    }
    try { NexusUI.toast('Plugin: ' + (plugin.name || plugin.id), 'info'); } catch(e) {}
    return true;
  }

  /** 注销插件 */
  function unregister(id) {
    delete _registry[id];
    for (var h in _hooks) {
      _hooks[h] = _hooks[h].filter(function(fn) { return fn._pluginId !== id; });
    }
  }

  /** 派发 Hook 事件，支持数据管线 */
  function dispatch(hook, data) {
    if (!_hooks[hook]) return data;
    var result = data;
    for (var i = 0; i < _hooks[hook].length; i++) {
      try {
        var r = _hooks[hook][i](result);
        if (r !== undefined) result = r;
      } catch(e) {
        console.error('Plugin[' + hook + ']:', e);
      }
    }
    return result;
  }

  /** 获取已注册插件列表 */
  function list() {
    return Object.keys(_registry).map(function(id) {
      return { id: id, name: (_registry[id].name || id) };
    });
  }

  return {
    register: register,
    unregister: unregister,
    dispatch: dispatch,
    list: list
  };
})();
