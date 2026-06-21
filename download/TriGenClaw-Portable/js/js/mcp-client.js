/* ========================================
   TriGen MCP Client v2 - Enhanced
   连接 MCP 服务器，发现和调用工具
   支持多服务器、重连、工具注册到 Agent 引擎
   ======================================== */
var NexusMCP = (function() {
  'use strict';

  var DEFAULT_SERVER = 'https://j3trisheng.com/mcp/';
  var _serverUrls = [DEFAULT_SERVER];
  var _toolsCache = [];
  var _connected = false;
  var _serverInfos = {};

  /**
   * 连接 MCP 服务器，获取工具列表
   * 支持连接多台 MCP 服务器并聚合所有工具
   */
  function connect(serverUrls) {
    if (serverUrls) {
      _serverUrls = Array.isArray(serverUrls) ? serverUrls : [serverUrls];
    }
    var promises = _serverUrls.map(function(url) { return connectSingle(url); });
    return Promise.all(promises).then(function() {
      console.log('[MCP] Connected to', Object.keys(_serverInfos).length, 'server(s),', _toolsCache.length, 'tools total');
      return _toolsCache;
    });
  }

  function connectSingle(url) {
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: '2024-11-05' } })
    }).then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.result && data.result.serverInfo) {
        _connected = true;
        _serverInfos[url] = data.result.serverInfo;
        return listToolsFrom(url);
      }
      throw new Error('MCP init failed for ' + url);
    }).catch(function(e) {
      console.warn('[MCP] Failed to connect', url, e.message);
      return [];
    });
  }

  /**
   * 列出所有 MCP 工具
   */
  function listTools(serverUrl) {
    if (serverUrl) return listToolsFrom(serverUrl);
    var promises = _serverUrls.map(function(url) { return listToolsFrom(url); });
    return Promise.all(promises).then(function() { return _toolsCache; });
  }

  function listToolsFrom(url) {
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jsonrpc: '2.0', id: 2, method: 'tools/list', params: {} })
    }).then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.result && data.result.tools) {
        // 去重合并
        data.result.tools.forEach(function(t) {
          if (!_toolsCache.find(function(et) { return et.name === t.name; })) {
            _toolsCache.push(t);
          }
        });
        return _toolsCache;
      }
      return [];
    });
  }

  /**
   * 调用一个 MCP 工具（自动发现正确的服务器）
   */
  function callTool(toolName, args) {
    // 遍历所有服务器尝试调用
    function tryServer(idx) {
      if (idx >= _serverUrls.length) {
        return Promise.resolve({ success: false, text: 'Tool not found on any MCP server: ' + toolName });
      }
      var url = _serverUrls[idx];
      return fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          jsonrpc: '2.0',
          id: Date.now() + idx,
          method: 'tools/call',
          params: { name: toolName, arguments: args || {} }
        })
      }).then(function(r) { return r.json(); })
      .then(function(data) {
        if (data.result) {
          var content = data.result.content || [];
          var text = content.filter(function(c) { return c.type === 'text'; }).map(function(c) { return c.text; }).join('\n');
          return { success: !data.result.isError, text: text.trim(), raw: data.result };
        }
        return tryServer(idx + 1);
      }).catch(function() { return tryServer(idx + 1); });
    }
    return tryServer(0);
  }

  function getTools() { return _toolsCache; }
  function isConnected() { return _connected; }
  function getServerInfos() { return _serverInfos; }

  /**
   * 将 MCP 工具转换为 Agent 引擎兼容格式
   */
  function toAgentTools() {
    return _toolsCache.map(function(t) {
      return {
        name: t.name,
        description: t.description,
        parameters: t.inputSchema || { type: 'object', properties: {} },
        handler: function(args) {
          return callTool(t.name, args).then(function(r) {
            return { success: r.success, data: r.text, raw: r.raw };
          });
        }
      };
    });
  }

  /**
   * 注册所有 MCP 工具到全局 ToolRegistry
   * 让 Agent 引擎可以调用 MCP 工具
   */
  function registerToAgent(agentEngine) {
    var tools = toAgentTools();
    tools.forEach(function(t) {
      if (typeof agentEngine !== 'undefined' && agentEngine && agentEngine.registerTool) {
        agentEngine.registerTool(t.name, t.description, t.parameters, t.handler);
      }
    });
    return tools;
  }

  // 自动连接
  setTimeout(function() {
    connect().catch(function(e) { console.warn('[MCP] Auto-connect failed:', e.message); });
  }, 1000);

  return {
    connect: connect,
    listTools: listTools,
    callTool: callTool,
    getTools: getTools,
    isConnected: isConnected,
    getServerInfos: getServerInfos,
    toAgentTools: toAgentTools,
    registerToAgent: registerToAgent
  };
})();
