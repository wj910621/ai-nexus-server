/**
 * dashboard.html 中的「Y·NEX 本地AI」面板逻辑
 * 通过 CORS 直连用户本机 localhost:7777
 */
(function() {
  const YNEX_BASE = 'http://127.0.0.1:7777';
  let ynexOnline = false;
  let currentAbort = null;

  // 工具函数
  function $(id) { return document.getElementById(id); }
  function htmlEscape(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  async function YNEXFetch(path, options = {}) {
    const url = `${YNEX_BASE}${path}`;
    const res = await fetch(url, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  async function nexusFetch(path, options = {}) {
    const token = localStorage.getItem('nexus_token');
    const res = await fetch(path, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token ? `Bearer ${token}` : '',
        ...(options.headers || {}),
      },
    });
    return res.json();
  }

  // 状态检测
  async function checkYNEXStatus() {
    const dot = $('YNEXStatusDot');
    const text = $('YNEXStatusText');
    const panel = $('YNEXChatPanel');
    try {
      const data = await YNEXFetch('/api/health', { method: 'GET' });
      ynexOnline = true;
      if (dot) dot.className = 'conn-dot online';
      if (text) text.textContent = `本机Y·NEX在线 — ${data.hardware?.gpu_name || 'CPU'} · ${data.hardware?.vram_gb || 0}GB VRAM`;
      if (panel) panel.style.display = 'flex';
      renderHardware(data.hardware);
    } catch (e) {
      ynexOnline = false;
      if (dot) dot.className = 'conn-dot offline';
      if (text) text.textContent = '本机Y·NEX未启动，请打开 TriGenClaw 桌面端';
      if (panel) panel.style.display = 'none';
    }
  }

  function renderHardware(hw) {
    const el = $('YNEXHardwareInfo');
    if (!el || !hw) return;
    el.innerHTML = `
      <div class="info-grid">
        <div class="info-item"><span>GPU</span><b>${hw.gpu_name || '无'}</b></div>
        <div class="info-item"><span>显存</span><b>${hw.vram_gb || 0} GB</b></div>
        <div class="info-item"><span>内存</span><b>${hw.ram_gb || 0} GB</b></div>
        <div class="info-item"><span>CPU</span><b>${hw.cpu_cores || 0} 核</b></div>
      </div>
    `;
  }

  // 聊天
  function addYNEXMessage(role, content, isHtml) {
    const container = $('YNEXMessages');
    if (!container) return;
    const div = document.createElement('div');
    div.className = `YNEX-msg ${role}`;
    div.innerHTML = `
      <div class="YNEX-avatar">${role === 'user' ? '👤' : '🌐'}</div>
      <div class="YNEX-bubble">${isHtml ? content : htmlEscape(content)}</div>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div.querySelector('.YNEX-bubble');
  }

  async function sendYNEXMessage() {
    const input = $('YNEXInput');
    const text = input.value.trim();
    if (!text || !ynexOnline) return;
    input.value = '';
    addYNEXMessage('user', text);
    const bubble = addYNEXMessage('assistant', '思考中...');

    const useLocal = $('YNEXUseLocal')?.checked || false;
    const useMock = $('YNEXUseMock')?.checked || false;

    try {
      const res = await YNEXFetch('/api/chat', {
        method: 'POST',
        body: JSON.stringify({ message: text, use_local: useLocal, use_mock: useMock }),
      });
      bubble.textContent = res.reply || '（无回复）';
      reportUsage(1, 0);
    } catch (e) {
      bubble.textContent = '请求失败：' + e.message;
    }
  }

  // 流式对话
  async function sendYNEXStream() {
    const input = $('YNEXInput');
    const text = input.value.trim();
    if (!text || !ynexOnline) return;
    input.value = '';
    addYNEXMessage('user', text);
    const bubble = addYNEXMessage('assistant', '');

    const useLocal = $('YNEXUseLocal')?.checked || false;
    const useMock = $('YNEXUseMock')?.checked || false;

    try {
      const res = await fetch(`${YNEX_BASE}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, use_local: useLocal, use_mock: useMock }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let full = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6);
          if (data === '[DONE]') continue;
          try {
            const obj = JSON.parse(data);
            if (obj.content) {
              full += obj.content;
              bubble.innerHTML = htmlEscape(full).replace(/\n/g, '<br>');
            }
          } catch (e) {}
        }
      }
      reportUsage(1, 0);
    } catch (e) {
      bubble.textContent = '请求失败：' + e.message;
    }
  }

  // 调用Y·NEX技能
  async function callYNEXSkill(name, params = {}) {
    if (!ynexOnline) return alert('本机Y·NEX未启动');
    const bubble = addYNEXMessage('assistant', `正在执行技能：${name}...`);
    try {
      const res = await YNEXFetch('/api/skills/' + name, {
        method: 'POST',
        body: JSON.stringify(params),
      });
      bubble.innerHTML = `<pre>${htmlEscape(JSON.stringify(res, null, 2))}</pre>`;
    } catch (e) {
      bubble.textContent = '技能调用失败：' + e.message;
    }
  }

  // 上报用量到云端
  async function reportUsage(requests, tokens) {
    try {
      await nexusFetch('/api/YNEX/usage', {
        method: 'POST',
        body: JSON.stringify({ requests, tokens }),
      });
    } catch (e) {}
  }

  // 加载云端会员/用量信息
  async function loadCloudInfo() {
    const el = $('YNEXCloudInfo');
    if (!el) return;
    try {
      const mem = await nexusFetch('/api/YNEX/membership');
      const usage = await nexusFetch('/api/YNEX/usage');
      const total = (usage.usage || []).reduce((a, b) => a + (b.requests || 0), 0);
      el.innerHTML = `
        <div class="info-grid">
          <div class="info-item"><span>会员</span><b>${mem.tier?.name || '免费版'}</b></div>
          <div class="info-item"><span>积分</span><b>${mem.credits || 0}</b></div>
          <div class="info-item"><span>到期</span><b>${mem.expires ? mem.expires.split('T')[0] : '-'}</b></div>
          <div class="info-item"><span>累计调用</span><b>${total} 次</b></div>
        </div>
        <div style="margin-top:10px;font-size:12px;color:var(--text-secondary)">
          ${mem.tier?.cloud_sync ? '✅ 已开通云端同步与远程指令' : '💡 升级会员可解锁云端同步、远程指令、多设备'}
        </div>
      `;
    } catch (e) {
      el.innerHTML = '<div style="color:var(--text-secondary)">云端信息加载失败，请重新登录</div>';
    }
  }

  // 远程指令
  async function sendRemoteCommand() {
    const input = $('YNEXRemoteInput');
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    try {
      await nexusFetch('/api/YNEX/commands', {
        method: 'POST',
        body: JSON.stringify({ command: 'chat', params: { message: text } }),
      });
      addYNEXMessage('assistant', '✅ 指令已发送到云端队列，本地设备上线后执行。', true);
    } catch (e) {
      alert('发送失败：' + e.message);
    }
  }

  // 绑定事件
  function bindEvents() {
    const input = $('YNEXInput');
    if (input) {
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          sendYNEXStream();
        }
      });
    }
    const btn = $('YNEXSendBtn');
    if (btn) btn.addEventListener('click', sendYNEXStream);

    const remoteBtn = $('YNEXRemoteSendBtn');
    if (remoteBtn) remoteBtn.addEventListener('click', sendRemoteCommand);

    const checkBtn = $('YNEXCheckBtn');
    if (checkBtn) checkBtn.addEventListener('click', () => { checkYNEXStatus(); loadCloudInfo(); });

    // 技能按钮
    ['get_weather', 'get_system_info', 'list_reminders'].forEach(skill => {
      const el = $('YNEXSkill_' + skill);
      if (el) el.addEventListener('click', () => callYNEXSkill(skill, skill === 'get_weather' ? { city: '北京' } : {}));
    });
  }

  // 页面激活时初始化
  window.initYNEXPanel = function() {
    bindEvents();
    checkYNEXStatus();
    loadCloudInfo();
    setInterval(checkYNEXStatus, 10000);
  };
})();
