/* ========================================
   API 模块 - 多 Provider API 封装
   支持用户配置自有 API Key，按 model 自动路由
   默认回退到 j3trisheng.com
   ======================================== */
var NexusAPI = (function() {
  'use strict';

  /* ---------- 内部状态 ---------- */
  var _authToken = localStorage.getItem('nx_auth_token') || '';
  var _defaultBaseUrl = 'https://j3trisheng.com';
  var _worker = null;
  var _callbacks = {};
  var _callId = 0;
  try { _worker = new Worker('js/worker.js'); } catch(e) {}

  /* ---------- Provider 定义 ---------- */
  var PROVIDERS = {
    openai:    { name: 'OpenAI',           baseUrl: 'https://api.openai.com/v1' },
    deepseek:  { name: 'DeepSeek',         baseUrl: 'https://api.deepseek.com' },
    anthropic: { name: 'Anthropic',        baseUrl: 'https://api.anthropic.com/v1' },
    google:    { name: 'Google Gemini',    baseUrl: 'https://generativelanguage.googleapis.com/v1beta' },
    ollama:    { name: 'Ollama',           baseUrl: 'http://localhost:11434/v1', noKey: true },
    qwen:      { name: '贯通千问',          baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
    glm:       { name: '智谱 GLM',          baseUrl: 'https://open.bigmodel.cn/api/paas/v4' },
    yi:        { name: '零一万物 Yi',        baseUrl: 'https://api.lingyiwanwu.com/v1' },
    baichuan:  { name: '百川',             baseUrl: 'https://api.baichuan-ai.com/v1' },
    local:     { name: '本地后端',           baseUrl: 'http://localhost:8000', noKey: true }
  };

  /* model ID 前缀 - provider key 映射 */
  var MODEL_PROVIDER = {
    gpt: 'openai', 'o1': 'openai', 'o3': 'openai',
    deepseek: 'deepseek',
    claude: 'anthropic',
    gemini: 'google',
    llama: 'ollama', mistral: 'ollama', mixtral: 'ollama',
    codellama: 'ollama', phi3: 'ollama', 'phi-3': 'ollama',
    'stable-code': 'ollama', 'stable-diffusion': 'ollama',
    dbrx: 'ollama', 'command-r': 'ollama', solar: 'ollama', reka: 'ollama',
    qwen: 'qwen',
    glm: 'glm',
    yi: 'yi',
    baichuan: 'baichuan'
  };

  /* ---------- 配置读写 ---------- */
  function loadConfig() {
    var cfg = {};
    try { cfg = JSON.parse(localStorage.getItem('nx_api_providers') || '{}'); } catch(e) {}
    return cfg;
  }
  function saveConfig(cfg) {
    localStorage.setItem('nx_api_providers', JSON.stringify(cfg));
  }
  function getProviderKey(provider) {
    var cfg = loadConfig();
    return (cfg[provider] && cfg[provider].apiKey) || '';
  }
  function getProviderBaseUrl(provider) {
    var cfg = loadConfig();
    return (cfg[provider] && cfg[provider].baseUrl) || (PROVIDERS[provider] && PROVIDERS[provider].baseUrl) || '';
  }
  function getProviderEnabled(provider) {
    var cfg = loadConfig();
    return cfg[provider] ? cfg[provider].enabled !== false : true;
  }
  function getAllProviderConfigs() {
    var cfg = loadConfig();
    var result = {};
    for (var key in PROVIDERS) {
      result[key] = {
        name: PROVIDERS[key].name,
        baseUrl: (cfg[key] && cfg[key].baseUrl) || PROVIDERS[key].baseUrl,
        apiKey: (cfg[key] && cfg[key].apiKey) || '',
        enabled: cfg[key] ? cfg[key].enabled !== false : true,
        noKey: PROVIDERS[key].noKey || false
      };
    }
    return result;
  }
  function setProviderConfig(provider, config) {
    var cfg = loadConfig();
    cfg[provider] = cfg[provider] || {};
    if (config.apiKey !== undefined) cfg[provider].apiKey = config.apiKey;
    if (config.baseUrl !== undefined) cfg[provider].baseUrl = config.baseUrl;
    if (config.enabled !== undefined) cfg[provider].enabled = config.enabled;
    saveConfig(cfg);
  }

  /* ---------- 模型路由 ---------- */
  function resolveProvider(modelId) {
    if (!modelId) return null;
    var m = modelId.toLowerCase();
    for (var key in MODEL_PROVIDER) {
      if (m === key || m.indexOf(key) === 0) {
        var p = MODEL_PROVIDER[key];
        if (getProviderEnabled(p)) return p;
        return null;
      }
    }
    return null;
  }

  /* ---------- 统一请求头 ---------- */
  function getHeaders(provider) {
    var headers = { 'Content-Type': 'application/json' };
    if (provider) {
      var key = getProviderKey(provider);
      if (key && provider !== 'google') {
        headers['Authorization'] = 'Bearer ' + key;
      } else if (!key && provider === 'local' && _authToken) {
        headers['Authorization'] = 'Bearer ' + _authToken;
      }
    } else {
      // 后端代理接口认证：支持 API Key 和登录 Token 两种模式
      if (_authToken) {
        headers['Authorization'] = 'Bearer ' + _authToken;
        headers['x-auth-token'] = _authToken;  // 后端通过此头识别登录用户
      }
    }
    return headers;
  }

  /* ---------- 构建 API URL ---------- */
  function getApiUrl(provider) {
    if (!provider) return _defaultBaseUrl + '/api/chat';
    var base = getProviderBaseUrl(provider);
    var key = getProviderKey(provider);
    if (provider === 'google' && key) {
      return base + '/models/gemini-pro:streamGenerateContent?key=' + encodeURIComponent(key);
    }
    return base + '/chat/completions';
  }

  /* ---------- SSE 流式聊天 ---------- */
  function chatStream(model, messages, onChunk, onDone, onError, opts) {
    opts = opts || {};
    var provider = resolveProvider(model);

    /* 无 provider 匹配时走 Worker + 默认代理 */
    if (_worker && typeof Worker !== 'undefined' && !provider) {
      var id = ++_callId;
      _callbacks[id] = { onChunk: onChunk, onDone: onDone, onError: onError };
      _worker.onmessage = function(e) {
        var m = e.data;
        var cb = _callbacks[m.id];
        if (!cb) return;
        if (m.type === 'chunk' && cb.onChunk) cb.onChunk(m.text);
        else if (m.type === 'done' && cb.onDone) { cb.onDone(); delete _callbacks[m.id]; }
        else if (m.type === 'error' && cb.onError) { cb.onError(m.text); delete _callbacks[m.id]; }
      };
      _worker.postMessage({ type: 'chat', model: model, messages: messages, opts: opts, id: id });
      return { abort: function() { _worker.postMessage({ type: 'abort', id: id }); } };
    }

    var controller = new AbortController();
    var url = provider ? getApiUrl(provider) : _defaultBaseUrl + '/api/chat';
    var headers = provider ? getHeaders(provider) : getHeaders();
    var body = JSON.stringify({
      model: model,
      messages: messages,
      temperature: opts.temperature || 0.7,
      max_tokens: opts.max_tokens || 4096,
      stream: true
    });

    fetch(url, {
      method: 'POST',
      headers: headers,
      body: body,
      signal: controller.signal
    }).then(function(response) {
      if (!response.ok) {
        if (provider && !opts._fallback) {
          return chatStreamFallback(model, messages, onChunk, onDone, onError, opts, controller);
        }
        throw new Error('API error: ' + response.status + ' ' + response.statusText);
      }
      parseSSE(response, onChunk, onDone, onError);
    }).catch(function(err) {
      if (err.name === 'AbortError') return;
      if (provider && !opts._fallback) {
        return chatStreamFallback(model, messages, onChunk, onDone, onError, opts, controller);
      }
      if (typeof onError === 'function') onError(err.message || String(err));
    });

    return controller;
  }

  /* 回退到默认代理 */
  function chatStreamFallback(model, messages, onChunk, onDone, onError, opts, controller) {
    if (controller.signal.aborted) return;
    var url = _defaultBaseUrl + '/api/chat';
    var body = JSON.stringify({
      model: model,
      messages: messages,
      temperature: opts.temperature || 0.7,
      max_tokens: opts.max_tokens || 4096,
      stream: true
    });
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body,
      signal: controller.signal
    }).then(function(response) {
      if (!response.ok) throw new Error('Fallback error: ' + response.status);
      parseSSE(response, onChunk, onDone, onError);
    }).catch(function(err) {
      if (err.name === 'AbortError') return;
      if (typeof onError === 'function') onError('Provider unavailable, fallback also failed: ' + err.message);
    });
  }

  /* 解析 SSE 流 */
  function parseSSE(response, onChunk, onDone, onError) {
    var reader = response.body.getReader();
    var decoder = new TextDecoder();
    var buffer = '';

    function read() {
      reader.read().then(function(result) {
        if (result.done) {
          if (typeof onDone === 'function') onDone();
          return;
        }
        buffer += decoder.decode(result.value, { stream: true });
        var lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (var i = 0; i < lines.length; i++) {
          var line = lines[i].trim();
          if (line.indexOf('data: ') === 0) {
            var data = line.slice(6);
            if (data === '[DONE]') {
              if (typeof onDone === 'function') onDone();
              return;
            }
            try {
              var parsed = JSON.parse(data);
              var c = '';
              if (parsed.choices && parsed.choices[0]) {
                if (parsed.choices[0].delta && parsed.choices[0].delta.content) {
                  c = parsed.choices[0].delta.content;
                } else if (parsed.choices[0].text) {
                  c = parsed.choices[0].text;
                }
              }
              if (parsed.message && parsed.message.content) {
                c = parsed.message.content;
                if (parsed.done) { if (typeof onDone === 'function') onDone(); return; }
              }
              if (parsed.candidates && parsed.candidates[0]) {
                var parts = (parsed.candidates[0].content && parsed.candidates[0].content.parts) || [];
                c = parts.map(function(p) { return p.text || ''; }).join('');
              }
              if (c && typeof onChunk === 'function') onChunk(c);
            } catch(e) {}
          }
        }
        read();
      }).catch(function(err) {
        if (err.name === 'AbortError') return;
        if (typeof onError === 'function') onError(err.message || String(err));
      });
    }
    read();
  }

  /* ---------- 非流式（代码分析等） ---------- */
  function chat(model, messages, opts) {
    opts = opts || {};
    var provider = resolveProvider(model);
    var url = provider ? getApiUrl(provider) : _defaultBaseUrl + '/api/chat';
    var headers = provider ? getHeaders(provider) : getHeaders();
    var body = JSON.stringify({
      model: model,
      messages: messages,
      temperature: opts.temperature || 0.3,
      max_tokens: opts.max_tokens || 2048,
      stream: false
    });

    return fetch(url, {
      method: 'POST',
      headers: headers,
      body: body
    }).then(function(response) {
      if (!response.ok) {
        if (provider) {
          return fetch(_defaultBaseUrl + '/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: body
          }).then(function(r2) {
            if (!r2.ok) throw new Error('API error: ' + r2.status);
            return r2.json();
          }).then(function(data) { return extractContent(data); });
        }
        throw new Error('API error: ' + response.status);
      }
      return response.json();
    }).then(function(data) {
      return extractContent(data);
    });
  }

  function extractContent(data) {
    if (data.choices && data.choices[0] && data.choices[0].message && data.choices[0].message.content) {
      return data.choices[0].message.content;
    }
    if (data.message && data.message.content) return data.message.content;
    if (data.candidates && data.candidates[0] && data.candidates[0].content) {
      var parts = data.candidates[0].content.parts || [];
      return parts.map(function(p) { return p.text || ''; }).join('');
    }
    return data.content || data.response || '';
  }

  /* ---------- 模型列表 ---------- */
  function fetchModels() {
    return fetch(_defaultBaseUrl + '/api/models', { headers: getHeaders() })
      .then(function(r) { return r.json(); })
      .then(function(data) { return data.models || []; });
  }

  /* ---------- 鉴权 ---------- */
  function setAuth(token, key) {
    _authToken = token || '';
    if (token) localStorage.setItem('nx_auth_token', token);
    if (key) localStorage.setItem('nx_api_key', key);
    if (key) localStorage.setItem('nx_api_key', key);
  }

  function login(username, password) {
    return fetch(_defaultBaseUrl + '/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username, password: password })
    }).then(function(r) { return r.json(); });
  }

  function register(username, password, email) {
    return fetch(_defaultBaseUrl + '/api/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username, password: password, email: email })
    }).then(function(r) { return r.json(); });
  }

  /* ===== Agent 引擎 API ===== */

  /**
   * Agent 执行：调用服务端 Agent 引擎（ReAct 循环 + 工具）
   */
  function agentExecute(task, model, maxIterations) {
    return fetch(_defaultBaseUrl + '/api/agent/chat', {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({
        task: task,
        model: model || 'deepseekv3',
        maxIterations: maxIterations || 10
      })
    }).then(function(r) { return r.json(); });
  }

  /**
   * Agent 计划：分解任务为子步骤
   */
  function agentPlan(task, model) {
    return fetch(_defaultBaseUrl + '/api/agent/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        task: task,
        model: model || 'deepseekv3'
      })
    }).then(function(r) { return r.json(); });
  }

  /**
   * 直接执行一个工具
   */
  function toolExecute(toolName, args) {
    return fetch(_defaultBaseUrl + '/api/agent/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tool: toolName,
        args: args || {}
      })
    }).then(function(r) { return r.json(); });
  }

  /**
   * 列出所有可用工具
   */
  function listTools() {
    return fetch(_defaultBaseUrl + '/api/agent/tools', {
      headers: { 'Content-Type': 'application/json' }
    }).then(function(r) { return r.json(); });
  }

  /* ---------- Provider 管理 ---------- */
  function getProviders() { return PROVIDERS; }
  function getModelProviderMap() { return MODEL_PROVIDER; }

  /* ---------- 导出 ---------- */
  return {
    setAuth: setAuth,
    chatStream: chatStream,
    chat: chat,
    fetchModels: fetchModels,
    login: login,
    register: register,
    getAllProviderConfigs: getAllProviderConfigs,
    setProviderConfig: setProviderConfig,
    getProviders: getProviders,
    getModelProviderMap: getModelProviderMap,
    resolveProvider: resolveProvider,
    agentExecute: agentExecute,
    agentPlan: agentPlan,
    toolExecute: toolExecute,
    listTools: listTools
  };
})();
