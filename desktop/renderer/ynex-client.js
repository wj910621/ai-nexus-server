/**
 * Y·NEX 本地AI核心服务 - JavaScript SDK
 * 供 Y·NEX Desktop / Web / 手机端调用本地Y·NEX 服务
 *
 * 使用方式：
 *   const ynex = new YnexClient('http://localhost:7777');
 *   const reply = await ynex.chat('你好');
 *   console.log(reply);
 */

class YnexClient {
  constructor(baseUrl = 'http://localhost:7777', apiKey = '') {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.apiKey = apiKey;
    this.messageHistory = [];

    // M3: 本地 LLM 调度与缓存策略
    this.requestQueue = [];
    this.running = 0;
    this.maxConcurrency = 2;            // 本地 LLM 并发限制，避免压垮 8GB VRAM
    this.responseCache = new Map();     // 基于提示词哈希的响应缓存
    this.cacheMaxSize = 100;            // 最多缓存 100 条响应
    this.cacheEnabled = true;
    this.schedulerStats = {
      queued: 0,
      running: 0,
      completed: 0,
      cacheHits: 0,
      cacheMisses: 0,
      errors: 0,
    };
  }

  // 简单哈希，用于缓存键
  hashString(str) {
    let h = 0;
    for (let i = 0; i < str.length; i++) {
      h = (h << 5) - h + str.charCodeAt(i);
      h |= 0;
    }
    return String(h);
  }

  getCacheKey(path, body) {
    return this.hashString(path + ':' + JSON.stringify(body || {}));
  }

  getSchedulerStats() {
    return { ...this.schedulerStats, queued: this.requestQueue.length, running: this.running };
  }

  setCacheEnabled(enabled) {
    this.cacheEnabled = enabled;
  }

  clearCache() {
    this.responseCache.clear();
  }

  async request(path, options = {}) {
    const method = (options.method || 'GET').toUpperCase();
    const body = options.body || null;

    // GET/POST 静态请求可缓存
    const cacheKey = this.getCacheKey(path, body);
    if (this.cacheEnabled && method === 'GET' && this.responseCache.has(cacheKey)) {
      this.schedulerStats.cacheHits++;
      return this.responseCache.get(cacheKey);
    }

    // 调度器：限制并发，避免本地 LLM 过载
    return new Promise((resolve, reject) => {
      this.requestQueue.push(async () => {
        this.running++;
        try {
          const data = await this._doRequest(path, options, method, body);
          if (this.cacheEnabled && method === 'GET' && this.responseCache.size < this.cacheMaxSize) {
            this.responseCache.set(cacheKey, data);
          }
          this.schedulerStats.completed++;
          resolve(data);
        } catch (e) {
          this.schedulerStats.errors++;
          reject(e);
        } finally {
          this.running--;
          this.processQueue();
        }
      });
      this.processQueue();
    });
  }

  processQueue() {
    while (this.running < this.maxConcurrency && this.requestQueue.length > 0) {
      const task = this.requestQueue.shift();
      task();
    }
  }

  async _doRequest(path, options, method, body) {
    // 在 Electron 桌面端，优先通过主进程 IPC 转发，避免 file:// 协议的 CORS 限制
    if (typeof window !== 'undefined' && window.ynex && window.ynex.ynex && window.ynex.ynex.api) {
      const result = await window.ynex.ynex.api(method, path, body);
      if (!result.ok) {
        throw new Error(`Y·NEX 服务错误 ${result.status || ''}: ${JSON.stringify(result.data || result.error || result)}`);
      }
      return result.data;
    }

    const url = `${this.baseUrl}${path}`;
    const headers = {
      'Content-Type': 'application/json',
    };
    if (this.apiKey) {
      headers['X-API-Key'] = this.apiKey;
    }

    const config = {
      method,
      headers: {
        ...headers,
        ...(options.headers || {}),
      },
    };

    if (body && typeof body === 'object') {
      config.body = JSON.stringify(body);
    }

    const response = await fetch(url, config);
    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Y·NEX 服务错误 ${response.status}: ${error}`);
    }
    return response.json();
  }

  /**
   * 检查Y·NEX 服务是否在线
   */
  async isOnline() {
    try {
      const resp = await fetch(`${this.baseUrl}/api/health`, { method: 'GET' });
      return resp.ok;
    } catch (e) {
      return false;
    }
  }

  /**
   * 获取服务健康状态和硬件信息
   */
  async health() {
    return this.request('/api/health');
  }

  /**
   * 普通文本对话
   * @param {string} message 用户消息
   * @param {Object} options 选项 { useLocal: false, useMock: false, saveHistory: true }
   */
  async chat(message, options = {}) {
    const { useLocal = false, useMock = false, saveHistory = true } = options;

    const data = await this.request('/api/chat', {
      method: 'POST',
      body: {
        message,
        history: saveHistory ? this.messageHistory : [],
        use_local: useLocal,
        use_mock: useMock,
      },
    });

    if (saveHistory) {
      this.messageHistory.push({ role: 'user', content: message });
      this.messageHistory.push({ role: 'assistant', content: data.reply });
      // 只保留最近20轮
      if (this.messageHistory.length > 40) {
        this.messageHistory = this.messageHistory.slice(-40);
      }
    }

    return data.reply;
  }

  /**
   * 流式对话
   * @param {string} message 用户消息
   * @param {Function} onChunk 每个字符的回调 (text, source) => void
   * @param {Object} options 选项
   */
  async chatStream(message, onChunk, options = {}) {
    const { useLocal = false, useMock = false } = options;

    // Electron 桌面端：通过 IPC 非流式调用，再逐字模拟流式效果
    if (typeof window !== 'undefined' && window.ynex && window.ynex.ynex && window.ynex.ynex.api) {
      const data = await this.request('/api/chat', {
        method: 'POST',
        body: { message, use_local: useLocal, use_mock: useMock },
      });
      const fullText = data.reply || '';
      for (let i = 0; i < fullText.length; i++) {
        const chunk = fullText[i];
        if (onChunk) onChunk(chunk, data.source || 'local');
        if (i % 5 === 0) await new Promise(r => setTimeout(r, 8));
      }
      this.messageHistory.push({ role: 'user', content: message });
      this.messageHistory.push({ role: 'assistant', content: fullText });
      return fullText;
    }

    const response = await fetch(`${this.baseUrl}/api/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, use_local: useLocal, use_mock: useMock }),
    });

    if (!response.ok) {
      throw new Error(`流式对话失败: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let fullText = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const text = decoder.decode(value);
      const lines = text.split('\n');
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          if (data === '[DONE]') continue;
          try {
            const obj = JSON.parse(data);
            if (obj.content) {
              fullText += obj.content;
              if (onChunk) onChunk(obj.content, obj.source || 'api');
            }
          } catch (e) {
            // 忽略解析错误
          }
        }
      }
    }

    this.messageHistory.push({ role: 'user', content: message });
    this.messageHistory.push({ role: 'assistant', content: fullText });
    return fullText;
  }

  /**
   * 列出所有可用技能
   */
  async listSkills() {
    return this.request('/api/skills');
  }

  /**
   * 调用技能
   * @param {string} skillName 技能名
   * @param {Object} params 技能参数
   */
  async callSkill(skillName, params = {}) {
    return this.request(`/api/skills/${skillName}`, {
      method: 'POST',
      body: params,
    });
  }

  /**
   * 执行复杂任务（超级Agent）
   * @param {string} task 任务描述
   */
  async runTask(task) {
    return this.request('/api/agent/task', {
      method: 'POST',
      body: { task },
    });
  }

  /**
   * 带工具调用的Agent对话
   * @param {string} message 用户消息
   */
  async agentChat(message) {
    const data = await this.request('/api/agent/chat', {
      method: 'POST',
      body: { message },
    });
    return data.reply;
  }

  /**
   * 列出调度任务
   * @param {string} status 状态筛选
   * @param {number} limit 条数
   */
  async listTasks(status = '', limit = 50) {
    const qs = new URLSearchParams();
    if (status) qs.append('status', status);
    qs.append('limit', String(limit));
    return this.request(`/api/tasks?${qs.toString()}`);
  }

  /**
   * 创建异步任务
   * @param {string} request 任务请求
   * @param {number} maxRetries 最大重试次数
   */
  async createTask(request, maxRetries = 2) {
    return this.request('/api/tasks', {
      method: 'POST',
      body: { request, max_retries: maxRetries },
    });
  }

  /**
   * 获取任务详情
   * @param {string} taskId 任务ID
   */
  async getTask(taskId) {
    return this.request(`/api/tasks/${taskId}`);
  }

  /**
   * 取消任务
   * @param {string} taskId 任务ID
   */
  async cancelTask(taskId) {
    return this.request(`/api/tasks/${taskId}/cancel`, {
      method: 'POST',
    });
  }

  /**
   * 删除任务
   * @param {string} taskId 任务ID
   */
  async deleteTask(taskId) {
    return this.request(`/api/tasks/${taskId}`, {
      method: 'DELETE',
    });
  }

  /**
   * 获取本地LLM状态
   */
  async localLlmStatus() {
    return this.request('/api/local_llm/status');
  }

  /**
   * 获取本地LLM推荐模型
   */
  async localLlmModels() {
    return this.request('/api/local_llm/models');
  }

  /**
   * 语音输入识别
   * @param {number} duration 录音时长（秒）
   */
  async voiceListen(duration = 5) {
    return this.request('/api/voice/listen', {
      method: 'POST',
      body: { duration },
    });
  }

  /**
   * 语音播报
   * @param {string} text 要播报的文本
   * @param {object} options 可选：voice 音色 / async 是否后台播放
   */
  async voiceSpeak(text, options = {}) {
    return this.request('/api/voice/speak', {
      method: 'POST',
      body: {
        text,
        voice: options.voice || '',
        async: options.async !== false,  // 默认后台异步播放
      },
    });
  }

  /**
   * 获取语音引擎状态
   */
  async voiceEngineStatus() {
    return this.request('/api/voice/engine/status');
  }

  /**
   * 启动语音引擎
   * @param {Array<string>} wake_words 唤醒词列表
   * @param {number} sensitivity 灵敏度 0-1
   */
  async startVoiceEngine(wake_words = ['hey_jarvis'], sensitivity = 0.5) {
    return this.request('/api/voice/engine/start', {
      method: 'POST',
      body: { wake_words, sensitivity },
    });
  }

  /**
   * 停止语音引擎
   */
  async stopVoiceEngine() {
    return this.request('/api/voice/engine/stop', {
      method: 'POST',
    });
  }

  /**
   * 启动实时语音对话循环
   */
  async startVoiceConversation() {
    return this.request('/api/voice/conversation/start', {
      method: 'POST',
    });
  }

  /**
   * 停止实时语音对话循环
   */
  async stopVoiceConversation() {
    return this.request('/api/voice/conversation/stop', {
      method: 'POST',
    });
  }

  /**
   * 获取实时语音对话状态
   */
  async voiceConversationStatus() {
    return this.request('/api/voice/conversation/status');
  }

  /**
   * 获取系统信息
   */
  async systemInfo() {
    return this.request('/api/system/info');
  }

  /**
   * 列出目录
   * @param {string} path 目录路径
   */
  async listFiles(path = '.') {
    return this.request(`/api/files/list?path=${encodeURIComponent(path)}`);
  }

  /**
   * 读取文件
   * @param {string} path 文件路径
   */
  async readFile(path) {
    return this.request(`/api/files/read?path=${encodeURIComponent(path)}`);
  }

  /**
   * 写入文件
   * @param {string} path 文件路径
   * @param {string} content 内容
   */
  async writeFile(path, content) {
    return this.request('/api/files/write', {
      method: 'POST',
      body: { path, content },
    });
  }

  /**
   * 获取对话历史
   */
  async getConversations(limit = 20) {
    return this.request(`/api/memory/conversations?limit=${limit}`);
  }

  /**
   * 获取 PC 当前状态（活跃窗口、CPU、内存、音量）
   */
  async pcState() {
    return this.request('/api/pc/state');
  }

  /**
   * 获取剪贴板历史
   * @param {number} limit 条数
   */
  async pcClipboardHistory(limit = 10) {
    return this.request(`/api/pc/clipboard?limit=${limit}`);
  }

  /**
   * 注册全局热键
   * @param {string} combo 热键组合，如 '<ctrl>+<shift>+m'
   * @param {string} action PC 控制动作，如 'mute'
   */
  async registerHotkey(combo, action) {
    return this.request('/api/pc/hotkeys', {
      method: 'POST',
      body: { combo, action },
    });
  }

  /**
   * 注销全局热键
   * @param {string} combo 热键组合
   */
  async unregisterHotkey(combo) {
    return this.request('/api/pc/hotkeys', {
      method: 'DELETE',
      body: { combo },
    });
  }

  /**
   * 获取 PC 自动化状态
   */
  async pcAutomationStatus() {
    return this.request('/api/pc/automation/status');
  }

  /**
   * 浏览器：打开网页
   * @param {string} url
   */
  async browserGoto(url) {
    return this.request('/api/browser/goto', {
      method: 'POST',
      body: { url },
    });
  }

  /**
   * 浏览器：获取页面文本
   * @param {number} maxChars
   */
  async browserText(maxChars = 3000) {
    return this.request(`/api/browser/text?max_chars=${maxChars}`);
  }

  /**
   * 浏览器：截图
   * @param {boolean} fullPage
   */
  async browserScreenshot(fullPage = false) {
    return this.request('/api/browser/screenshot', {
      method: 'POST',
      body: { full_page: fullPage },
    });
  }

  /**
   * 浏览器：点击
   * @param {string} text 要点击的文本
   */
  async browserClick(text) {
    return this.request('/api/browser/click', {
      method: 'POST',
      body: { text },
    });
  }

  /**
   * 浏览器：滚动
   */
  async browserScroll(direction = 'down', amount = 500) {
    return this.request('/api/browser/scroll', {
      method: 'POST',
      body: { direction, amount },
    });
  }

  /**
   * 浏览器：标签页列表
   */
  async browserTabs() {
    return this.request('/api/browser/tabs');
  }

  /**
   * 浏览器：新建标签页
   */
  async browserNewTab(url) {
    return this.request('/api/browser/tabs/new', {
      method: 'POST',
      body: { url },
    });
  }

  /**
   * 浏览器：切换标签页
   */
  async browserSwitchTab(index) {
    return this.request('/api/browser/tabs/switch', {
      method: 'POST',
      body: { index },
    });
  }

  /**
   * 浏览器：执行自然语言任务
   * @param {string} task
   */
  async browserTask(task) {
    return this.request('/api/browser/task', {
      method: 'POST',
      body: { task },
    });
  }

  /**
   * 浏览器：状态
   */
  async browserStatus() {
    return this.request('/api/browser/status');
  }

  /**
   * 浏览器：关闭
   */
  async browserClose() {
    return this.request('/api/browser/close', { method: 'POST' });
  }

  /**
   * 获取系统信息
   */
  async systemInfo() {
    return this.request('/api/system/info');
  }

  // ========== 移动端设备管理 ==========

  /**
   * 列出所有注册的移动设备
   */
  async listMobileDevices(platform) {
    const path = platform ? `/api/mobile/devices?platform=${platform}` : '/api/mobile/devices';
    return this.request(path);
  }

  /**
   * 注册移动设备
   */
  async registerMobileDevice(deviceInfo) {
    return this.request('/api/mobile/register', {
      method: 'POST',
      body: deviceInfo,
    });
  }

  /**
   * 设备心跳保活
   */
  async mobileHeartbeat(deviceId, extra = {}) {
    return this.request('/api/mobile/heartbeat', {
      method: 'POST',
      body: { device_id: deviceId, ...extra },
    });
  }

  /**
   * 注销设备
   */
  async unregisterMobileDevice(deviceId) {
    return this.request(`/api/mobile/devices/${deviceId}`, {
      method: 'DELETE',
    });
  }

  // ========== 推送通知 ==========

  /**
   * 推送通知（多通道）
   */
  async pushNotification(title, body, options = {}) {
    return this.request('/api/mobile/push', {
      method: 'POST',
      body: { title, body, ...options },
    });
  }

  /**
   * 转发PC通知到手机
   */
  async forwardNotification(title, body, priority = 'normal') {
    return this.request('/api/mobile/notify', {
      method: 'POST',
      body: { title, body, priority },
    });
  }

  /**
   * 获取通知历史
   */
  async notificationHistory(limit = 20) {
    return this.request(`/api/mobile/notifications?limit=${limit}`);
  }

  // ========== 手机远程控制 PC ==========

  /**
   * 远程控制PC
   * action: lock / shutdown / restart / sleep / screenshot /
   *         volume_up / volume_down / volume_mute / open_app / type_text
   */
  async remotePcAction(action, params = {}) {
    return this.request('/api/mobile/pc/action', {
      method: 'POST',
      body: { action, params },
    });
  }

  // ========== 位置服务 ==========

  /**
   * 上报设备位置
   */
  async updateLocation(deviceId, lat, lon, accuracy) {
    return this.request('/api/mobile/location', {
      method: 'POST',
      body: { device_id: deviceId, lat, lon, accuracy },
    });
  }

  /**
   * 获取地理围栏列表
   */
  async listGeofences() {
    return this.request('/api/mobile/geofences');
  }

  /**
   * 添加地理围栏
   */
  async addGeofence(name, lat, lon, radius = 100, options = {}) {
    return this.request('/api/mobile/geofences', {
      method: 'POST',
      body: { name, lat, lon, radius, ...options },
    });
  }

  // ========== 文件传输 ==========

  /**
   * 列出传输目录文件
   */
  async listTransferFiles() {
    return this.request('/api/mobile/files');
  }

  /**
   * 上传文件到PC（base64方式）
   */
  async uploadFile(filename, content, encoding = 'base64') {
    return this.request('/api/mobile/upload', {
      method: 'POST',
      body: { filename, content, encoding },
    });
  }

  /**
   * 获取下载文件URL
   */
  getDownloadUrl(filename) {
    return `${this.baseUrl}/api/mobile/download/${encodeURIComponent(filename)}`;
  }

  // ========== 知识库 RAG ==========

  /**
   * 检索知识库
   * @param {string} query 查询文本
   * @param {number} topK 返回数量
   * @param {string} mode 检索模式：vector/keyword/hybrid
   * @param {boolean} rerank 是否重排序
   * @param {boolean} expand 是否查询扩展
   * @param {boolean} aggregate 是否聚合相邻片段
   */
  async knowledgeSearch(query, topK = 3, mode = 'hybrid', rerank = true, expand = true, aggregate = true) {
    const qs = new URLSearchParams();
    qs.append('query', query);
    qs.append('top_k', String(topK));
    qs.append('mode', mode);
    qs.append('rerank', String(rerank));
    qs.append('expand', String(expand));
    qs.append('aggregate', String(aggregate));
    return this.request(`/api/knowledge/search?${qs.toString()}`);
  }

  /**
   * 导入文档到知识库
   */
  async knowledgeIngest(path) {
    return this.request('/api/knowledge/ingest', {
      method: 'POST',
      body: { path },
    });
  }

  /**
   * 抓取网页入库
   */
  async knowledgeAddWebpage(url) {
    return this.request('/api/knowledge/webpage', {
      method: 'POST',
      body: { url },
    });
  }

  /**
   * 列出知识库来源
   */
  async knowledgeSources() {
    return this.request('/api/knowledge/sources');
  }

  /**
   * 知识库状态
   */
  async knowledgeStatus() {
    return this.request('/api/knowledge/status');
  }

  /**
   * 文本摘要
   */
  async knowledgeSummarize(text, maxSentences = 5) {
    return this.request('/api/knowledge/summarize', {
      method: 'POST',
      body: { text, max_sentences: maxSentences },
    });
  }

  // ========== 插件系统 ==========

  /**
   * 列出所有已安装插件
   */
  async listPlugins() {
    return this.request('/api/plugins');
  }

  /**
   * 列出所有插件技能
   */
  async listPluginSkills() {
    return this.request('/api/plugins/skills');
  }

  /**
   * 从URL安装插件
   */
  async installPlugin(url) {
    return this.request('/api/plugins/install', {
      method: 'POST',
      body: { url },
    });
  }

  /**
   * 启用插件
   */
  async enablePlugin(pluginId) {
    return this.request(`/api/plugins/${pluginId}/enable`, {
      method: 'POST',
    });
  }

  /**
   * 禁用插件
   */
  async disablePlugin(pluginId) {
    return this.request(`/api/plugins/${pluginId}/disable`, {
      method: 'POST',
    });
  }

  /**
   * 热重载插件
   */
  async reloadPlugin(pluginId) {
    return this.request(`/api/plugins/${pluginId}/reload`, {
      method: 'POST',
    });
  }

  /**
   * 卸载插件
   */
  async uninstallPlugin(pluginId) {
    return this.request(`/api/plugins/${pluginId}`, {
      method: 'DELETE',
    });
  }

  /**
   * 获取插件配置
   */
  async getPluginConfig(pluginId, key = null) {
    const path = key
      ? `/api/plugins/${pluginId}/config?key=${encodeURIComponent(key)}`
      : `/api/plugins/${pluginId}/config`;
    return this.request(path);
  }

  /**
   * 设置插件配置
   */
  async setPluginConfig(pluginId, key, value) {
    return this.request(`/api/plugins/${pluginId}/config`, {
      method: 'POST',
      body: { key, value },
    });
  }

  /**
   * 调用插件技能
   */
  async callPluginSkill(skillName, params = {}) {
    return this.request(`/api/plugins/call/${skillName}`, {
      method: 'POST',
      body: params,
    });
  }

  // ========== 认证管理 ==========

  /**
   * 验证当前身份
   */
  async verifyAuth() {
    return this.request('/api/auth/verify');
  }

  /**
   * 列出 API Key（需要 owner 权限）
   */
  async listApiKeys() {
    return this.request('/api/auth/keys');
  }

  /**
   * 创建 API Key（需要 owner 权限）
   */
  async createApiKey(name, role = 'family') {
    return this.request('/api/auth/keys', {
      method: 'POST',
      body: { name, role },
    });
  }

  /**
   * 撤销 API Key（需要 owner 权限）
   */
  async revokeApiKey(keyId) {
    return this.request(`/api/auth/keys/${keyId}`, {
      method: 'DELETE',
    });
  }

  // ========== 性能监控 ==========

  /**
   * 获取性能统计
   */
  async performanceStats() {
    return this.request('/api/performance/stats');
  }

  /**
   * 重置性能统计
   */
  async resetPerformanceStats() {
    return this.request('/api/performance/stats', {
      method: 'DELETE',
    });
  }

  /**
   * 手动触发 GC
   */
  async triggerGC() {
    return this.request('/api/performance/gc', {
      method: 'POST',
    });
  }

  // ========== 多模态/视觉 ==========

  /**
   * 获取可用视觉模型列表
   */
  async visionModels() {
    return this.request('/api/vision/models');
  }

  /**
   * 分析图片内容
   */
  async analyzeImage(imagePath, prompt = '请详细描述这张图片的内容', model) {
    const body = { image_path: imagePath, prompt };
    if (model) body.model = model;
    return this.request('/api/vision/analyze', {
      method: 'POST',
      body,
    });
  }

  /**
   * OCR 文字识别
   */
  async ocrImage(imagePath) {
    return this.request('/api/vision/ocr', {
      method: 'POST',
      body: { image_path: imagePath },
    });
  }

  /**
   * 截屏并分析
   */
  async analyzeScreen(prompt = '描述一下当前屏幕显示的内容') {
    return this.request('/api/vision/screenshot', {
      method: 'POST',
      body: { prompt },
    });
  }

  /**
   * 摄像头拍照并分析
   */
  async analyzeCamera(prompt = '描述一下摄像头拍到的内容', cameraIndex = 0) {
    return this.request('/api/vision/camera', {
      method: 'POST',
      body: { prompt, camera_index: cameraIndex },
    });
  }

  /**
   * 文本生成图片
   * @param {string} prompt 图片描述
   * @param {object} options 可选：width/height/seed/style
   */
  async generateImage(prompt, options = {}) {
    return this.request('/api/vision/generate-image', {
      method: 'POST',
      body: {
        prompt,
        width: options.width || 1024,
        height: options.height || 1024,
        seed: options.seed,
        style: options.style || '',
      },
    });
  }

  /**
   * 清空本地对话历史
   */
  clearHistory() {
    this.messageHistory = [];
  }
}

// 兼容多种模块导出方式
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { YnexClient };
}
if (typeof window !== 'undefined') {
  window.YnexClient = YnexClient;
}
