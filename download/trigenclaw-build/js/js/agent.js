/* ========================================
   Agent 工作台核心模块 - P2
   20 个预设角色、工作流画布、配置、执行
   ======================================== */
var NexusAgent = (function() {
  'use strict';

  // ===== 20 个预设 Agent 角色 =====
  var AGENT_ROLES = [
    { id: 'fullstack', name: '全栈开发者', icon: '🌐', color: '#00d4ff',
      desc: '前后端全栈开发，可从零搭建完整 Web 应用',
      prompt: '你是一个全栈开发专家，精通前端和后端技术。',
      defaultModel: 'deepseek-chat' },
    { id: 'frontend', name: '前端工程师', icon: '🎨', color: '#e44d26',
      desc: '精通 HTML/CSS/JS，擅长 UI 实现和交互优化',
      prompt: '你是一个前端开发专家，精通 HTML、CSS、JavaScript。',
      defaultModel: 'deepseek-chat' },
    { id: 'backend', name: '后端工程师', icon: '⚙️', color: '#2ed573',
      desc: 'API 设计、数据库、服务器架构',
      prompt: '你是一个后端开发专家，精通 API 设计、数据库和服务器架构。',
      defaultModel: 'deepseek-chat' },
    { id: 'tester', name: '测试工程师', icon: '🔍', color: '#ffa502',
      desc: '单元测试、集成测试、E2E 测试',
      prompt: '你是一个测试专家，擅长编写全面的测试用例。',
      defaultModel: 'deepseek-chat' },
    { id: 'product', name: '产品经理', icon: '📋', color: '#7b2ff7',
      desc: '需求分析、PRD 撰写、功能规划',
      prompt: '你是一个资深产品经理，擅长需求分析和产品规划。',
      defaultModel: 'gpt-4o' },
    { id: 'designer', name: 'UI/UX 设计师', icon: '✨', color: '#ff6b6b',
      desc: '界面设计、用户体验、设计系统',
      prompt: '你是一个 UI/UX 设计专家，擅长界面设计和用户体验优化。',
      defaultModel: 'gpt-4o' },
    { id: 'devops', name: '运维工程师', icon: '🚀', color: '#1dd1a1',
      desc: 'CI/CD、容器化、云服务部署',
      prompt: '你是一个 DevOps 专家，精通 CI/CD、Docker、K8s。',
      defaultModel: 'deepseek-chat' },
    { id: 'data', name: '数据科学家', icon: '📊', color: '#54a0ff',
      desc: '数据分析、机器学习模型训练',
      prompt: '你是一个数据科学家，精通数据分析和机器学习。',
      defaultModel: 'deepseek-chat' },
    { id: 'security', name: '安全工程师', icon: '🔒', color: '#ff6348',
      desc: '安全审计、渗透测试、代码安全审查',
      prompt: '你是一个安全专家，精通代码安全审查和安全测试。',
      defaultModel: 'deepseek-chat' },
    { id: 'mobile', name: '移动端工程师', icon: '📱', color: '#2e86de',
      desc: 'iOS/Android/跨平台移动开发',
      prompt: '你是一个移动端开发专家，精通 iOS、Android 和跨平台开发。',
      defaultModel: 'deepseek-chat' },
    { id: 'ml', name: 'AI/ML 工程师', icon: '🧠', color: '#a29bfe',
      desc: '模型训练、推理优化、AI 应用开发',
      prompt: '你是一个 AI/ML 工程师，精通模型训练和 AI 应用开发。',
      defaultModel: 'deepseek-chat' },
    { id: 'qa', name: '质量保障', icon: '✅', color: '#00b894',
      desc: '质量流程、自动化测试框架',
      prompt: '你是一个 QA 专家，擅长质量流程管理和自动化测试。',
      defaultModel: 'deepseek-chat' },
    { id: 'docs', name: '技术文档工程师', icon: '📝', color: '#636e72',
      desc: 'API 文档、技术博客、用户手册',
      prompt: '你是一个技术文档专家，擅长撰写清晰的技术文档。',
      defaultModel: 'gpt-4o-mini' },
    { id: 'architect', name: '架构师', icon: '🏗️', color: '#fdcb6e',
      desc: '系统架构设计、技术选型、架构评审',
      prompt: '你是一个系统架构师，精通分布式系统架构设计。',
      defaultModel: 'gpt-4o' },
    { id: 'db', name: '数据库管理员', icon: '🗄️', color: '#74b9ff',
      desc: '数据库设计、优化、迁移',
      prompt: '你是一个数据库专家，精通 SQL、NoSQL 和数据库优化。',
      defaultModel: 'deepseek-chat' },
    { id: 'network', name: '网络工程师', icon: '🌐', color: '#55efc4',
      desc: '网络协议、负载均衡、CDN',
      prompt: '你是一个网络专家，精通网络协议和架构。',
      defaultModel: 'deepseek-chat' },
    { id: 'sysadmin', name: '系统管理员', icon: '💻', color: '#dfe6e9',
      desc: '服务器管理、监控、自动化运维',
      prompt: '你是一个系统管理员，精通服务器管理和运维。',
      defaultModel: 'deepseek-chat' },
    { id: 'automation', name: '自动化工程师', icon: '🤖', color: '#e17055',
      desc: '流程自动化、脚本开发、RPA',
      prompt: '你是一个自动化专家，擅长流程自动化和脚本开发。',
      defaultModel: 'deepseek-chat' },
    { id: 'gamedev', name: '游戏开发者', icon: '🎮', color: '#6c5ce7',
      desc: '游戏逻辑、图形渲染、物理引擎',
      prompt: '你是一个游戏开发专家，精通游戏引擎和图形编程。',
      defaultModel: 'deepseek-chat' },
    { id: 'blockchain', name: '区块链工程师', icon: '⛓️', color: '#f9ca24',
      desc: '智能合约、DApp 开发、Web3',
      prompt: '你是一个区块链开发专家，精通智能合约和 DApp。',
      defaultModel: 'deepseek-chat' }
  ];

  // ===== 工作流模板 =====
  var WORKFLOW_TEMPLATES = [
    { name: 'Code Review Pipeline', icon: '👁️', color: '#00d4ff',
      desc: 'Fullstack > Tester > Architect: comprehensive code review',
      agents: [{ roleId: 'fullstack' }, { roleId: 'tester' }, { roleId: 'architect' }],
      connections: [{ from: 0, to: 1 }, { from: 1, to: 2 }] },
    { name: 'Bug Report Analyzer', icon: '🐛', color: '#ff6348',
      desc: 'PM > Tester > Fullstack: triage and fix bugs',
      agents: [{ roleId: 'product' }, { roleId: 'tester' }, { roleId: 'fullstack' }],
      connections: [{ from: 0, to: 1 }, { from: 1, to: 2 }] },
    { name: 'API Development Flow', icon: '🔗', color: '#2ed573',
      desc: 'Architect > Backend > Tester > Docs: full API lifecycle',
      agents: [{ roleId: 'architect' }, { roleId: 'backend' }, { roleId: 'tester' }, { roleId: 'docs' }],
      connections: [{ from: 0, to: 1 }, { from: 1, to: 2 }, { from: 2, to: 3 }] },
    { name: 'Full App Generator', icon: '🌐', color: '#7b2ff7',
      desc: 'Product > Designer > Fullstack > DevOps: launch an app',
      agents: [{ roleId: 'product' }, { roleId: 'designer' }, { roleId: 'fullstack' }, { roleId: 'devops' }],
      connections: [{ from: 0, to: 1 }, { from: 1, to: 2 }, { from: 2, to: 3 }] },
    { name: 'Data Analysis Pipeline', icon: '📊', color: '#54a0ff',
      desc: 'Data Scientist > ML Engineer > Backend: data to API',
      agents: [{ roleId: 'data' }, { roleId: 'ml' }, { roleId: 'backend' }],
      connections: [{ from: 0, to: 1 }, { from: 1, to: 2 }] }
  ];  // ===== 状态 =====
  var canvasAgents = [];
  var connections = [];
  var selectedAgentId = null;
  var agentIdCounter = 0;
  var isDragging = false;
  var dragTarget = null;
  var dragOffsetX = 0;
  var dragOffsetY = 0;
  var connectingSource = null;
  var connectingLine = null;
  var canvasScale = 1;

  // DOM 引用
  var cardGrid, canvasDropzone, canvasSvg, canvasWrapper;
  var configForm, configPlaceholder;
  var resultsPlaceholder, resultsContent, resultsLog, resultsStatus;

  // ===== 初始化 =====
  function init() {
    cardGrid = document.getElementById('agentCardGrid');
    canvasDropzone = document.getElementById('canvasDropzone');
    canvasSvg = document.getElementById('canvasSvg');
    canvasWrapper = document.getElementById('canvasWrapper');
    configForm = document.getElementById('configForm');
    configPlaceholder = document.getElementById('configPlaceholder');
    resultsPlaceholder = document.getElementById('resultsPlaceholder');
    resultsContent = document.getElementById('resultsContent');
    resultsLog = document.getElementById('resultsLog');
    resultsStatus = document.getElementById('resultsStatus');

    if (!cardGrid) return;

    renderGallery();
    setupGallerySearch();
    setupCanvas();
    setupConfigForm();
    setupResults();
    setupAgentTabs();
    setupWorkflowActions();
  }

  // ===== Agent 库渲染 =====
  function renderGallery(filter) {
    if (!cardGrid) return;
    cardGrid.innerHTML = '';
    var roles = filter ? AGENT_ROLES.filter(function(a) {
      var q = filter.toLowerCase();
      return a.name.indexOf(q) >= 0 || a.id.indexOf(q) >= 0 || a.desc.indexOf(q) >= 0;
    }) : AGENT_ROLES;

    for (var i = 0; i < roles.length; i++) {
      var role = roles[i];
      var card = document.createElement('div');
      card.className = 'agent-card';
      card.setAttribute('data-role', role.id);
      card.style.setProperty('--agent-color', role.color);
      card.innerHTML =
        '<div class="agent-card-icon">' + role.icon + '</div>' +
        '<div class="agent-card-info">' +
        '<div class="agent-card-name">' + role.name + '</div>' +
        '<div class="agent-card-desc">' + role.desc + '</div>' +
        '</div>' +
        '<button class="agent-card-add" title="添加到画布">+</button>';
      cardGrid.appendChild(card);
    }
  }

  // After all agent cards, render templates
  renderTemplates();

  function setupCardDrag() {
    var cards = document.querySelectorAll('.agent-card[draggable="true"]');
    for (var i = 0; i < cards.length; i++) {
      (function(card) {
      // 添加到画布
      card.querySelector('.agent-card-add').addEventListener('click', function(e) {
        e.stopPropagation();
        var roleId = this.closest('.agent-card').getAttribute('data-role');
        addAgentToCanvas(roleId);
      });

      // 拖拽开始
      card.addEventListener('mousedown', function(e) {
        if (e.target.classList.contains('agent-card-add')) return;
        var roleId = this.getAttribute('data-role');
        startCanvasDrag(e, roleId);
      });

      card.addEventListener('touchstart', function(e) {
        if (e.target.classList.contains('agent-card-add')) return;
        var roleId = this.getAttribute('data-role');
        startCanvasDrag(e, roleId);
      }, { passive: true });
    })(cards[i]);
    }

  }
  function renderTemplates() {
    var container = document.getElementById('agentCardGrid');
    if (!container) return;
    // Add template section header
    var header = document.createElement('div');
    header.className = 'gallery-section-header';
    header.innerHTML = '<span>Workflow Templates</span>';
    container.appendChild(header);

    for (var i = 0; i < WORKFLOW_TEMPLATES.length; i++) {
      var tmpl = WORKFLOW_TEMPLATES[i];
      var card = document.createElement('div');
      card.className = 'agent-card template-card';
      card.style.setProperty('--agent-color', tmpl.color);
      card.innerHTML =
        '<div class="agent-card-icon" style="border-color:' + tmpl.color + '">' + tmpl.icon + '</div>' +
        '<div class="agent-card-info">' +
        '<div class="agent-card-name">' + tmpl.name + '</div>' +
        '<div class="agent-card-desc">' + tmpl.desc + '</div>' +
        '</div>' +
        '<button class="agent-card-add" title="Load template">+</button>';

      card.querySelector('.agent-card-add').addEventListener('click', function(e) {
        e.stopPropagation();
        loadTemplate(this.closest('.template-card').getAttribute('data-index'));
      });

      card.setAttribute('data-index', i);
      container.appendChild(card);
    }
  }

  /** 加载工作流模板 */
  function loadTemplate(index) {
    if (index < 0 || index >= WORKFLOW_TEMPLATES.length) return;
    var tmpl = WORKFLOW_TEMPLATES[index];

    if (canvasAgents.length > 0) {
      if (!confirm('Clear current canvas and load template?')) return;
    }

    // 清空画布
    canvasAgents = [];
    connections = [];
    selectedAgentId = null;
    configForm.classList.add('hidden');
    configPlaceholder.classList.remove('hidden');

    // 添加 Agent
    var idMap = {};
    var startX = 60;
    var startY = 60;
    for (var i = 0; i < tmpl.agents.length; i++) {
      var roleId = tmpl.agents[i].roleId;
      var agentId = addAgentToCanvas(roleId, startX + i * 220, startY);
      idMap[i] = agentId;
    }

    // 建立连接
    for (var j = 0; j < tmpl.connections.length; j++) {
      var c = tmpl.connections[j];
      if (idMap[c.from] && idMap[c.to]) {
        connections.push({ from: idMap[c.from], to: idMap[c.to] });
      }
    }

    renderCanvas();
    showCanvas();

    // 切换到画布视图
    var canvasTab = document.querySelector('.agent-tab[data-tab="workflow"]');
    if (canvasTab) canvasTab.click();

    NexusUI.toast('Loaded: ' + tmpl.name, 'success');
  }
function setupGallerySearch() {
    var input = document.getElementById('agentSearchInput');
    if (!input) return;
    input.addEventListener('input', function() {
      renderGallery(this.value);
    });
  }

  // ===== 画布拖拽 =====
  function startCanvasDrag(e, roleId) {
    NexusUI.toast('拖拽到画布上放置', 'info');
    // Set drag data
    window._agentDragRole = roleId;
  }

  function addAgentToCanvas(roleId, optX, optY) {
    // 找到角色信息
    var role = null;
    for (var i = 0; i < AGENT_ROLES.length; i++) {
      if (AGENT_ROLES[i].id === roleId) { role = AGENT_ROLES[i]; break; }
    }
    if (!role) return;

    agentIdCounter++;
    var agentId = 'agent_' + agentIdCounter;
    var canvasRect = canvasDropzone.getBoundingClientRect();
    if (optX !== undefined) offset = 0;

    var agent = {
      id: agentId,
      roleId: role.id,
      name: role.name,
      icon: role.icon,
      color: role.color,
      prompt: role.prompt,
      model: role.defaultModel,
      tools: { code: true, terminal: true, file: true, web: false, image: false },
      temperature: 0.7,
      maxTokens: 4096,
      x: optX !== undefined ? optX : (60 + offset % 300),
      y: optY !== undefined ? optY : (40 + Math.floor(offset / 300) * 120)
    };

    canvasAgents.push(agent);
    renderCanvas();
    showCanvas();

    NexusUI.toast('已添加: ' + role.name, 'success');
    return agentId;
  }

  function showCanvas() {
    var placeholder = canvasDropzone.querySelector('.canvas-placeholder');
    if (placeholder) placeholder.style.display = 'none';
  }

  // ===== 画布渲染 =====
  function renderCanvas() {
    // 清空并重新渲染所有节点
    var existingNodes = canvasDropzone.querySelectorAll('.canvas-node');
    for (var i = 0; i < existingNodes.length; i++) {
      existingNodes[i].remove();
    }

    for (var i = 0; i < canvasAgents.length; i++) {
      var agent = canvasAgents[i];
      var node = document.createElement('div');
      node.className = 'canvas-node' + (selectedAgentId === agent.id ? ' selected' : '');
      node.setAttribute('data-agent-id', agent.id);
      node.style.left = agent.x + 'px';
      node.style.top = agent.y + 'px';
      node.style.setProperty('--node-color', agent.color);
      node.innerHTML =
        '<div class="node-header">' +
        '<span class="node-icon">' + agent.icon + '</span>' +
        '<span class="node-name">' + agent.name + '</span>' +
        '</div>' +
        '<div class="node-ports">' +
        '<div class="node-port node-port-input" title="输入"></div>' +
        '<div class="node-port node-port-output" title="输出"></div>' +
        '</div>' +
        '<button class="node-remove" title="移除">×</button>';

      // 拖拽
      node.addEventListener('mousedown', function(e) {
        if (e.target.classList.contains('node-remove') ||
            e.target.classList.contains('node-port')) return;
        startNodeDrag(e, this);
      });

      // 选择
      node.addEventListener('click', function(e) {
        if (e.target.classList.contains('node-remove')) return;
        selectAgent(this.getAttribute('data-agent-id'));
      });

      // 移除
      node.querySelector('.node-remove').addEventListener('click', function(e) {
        e.stopPropagation();
        var id = this.closest('.canvas-node').getAttribute('data-agent-id');
        removeAgent(id);
      });

      // 端口连接
      node.querySelector('.node-port-output').addEventListener('mousedown', function(e) {
        e.stopPropagation();
        e.preventDefault();
        var id = this.closest('.canvas-node').getAttribute('data-agent-id');
        startConnection(e, id, 'output');
      });

      node.querySelector('.node-port-input').addEventListener('mousedown', function(e) {
        e.stopPropagation();
        if (connectingSource) {
          var id = this.closest('.canvas-node').getAttribute('data-agent-id');
          completeConnection(id);
        }
      });

      canvasDropzone.appendChild(node);
    }

    renderConnections();
    updateCanvasSize();
  }

  function updateCanvasSize() {
    if (canvasAgents.length === 0) {
      var placeholder = canvasDropzone.querySelector('.canvas-placeholder');
      if (placeholder) placeholder.style.display = 'flex';
      return;
    }
    // 计算需要的画布大小
    var maxX = 200;
    var maxY = 200;
    for (var i = 0; i < canvasAgents.length; i++) {
      if (canvasAgents[i].x + 180 > maxX) maxX = canvasAgents[i].x + 180;
      if (canvasAgents[i].y + 120 > maxY) maxY = canvasAgents[i].y + 120;
    }
    canvasDropzone.style.minWidth = Math.max(600, maxX + 100) + 'px';
    canvasDropzone.style.minHeight = Math.max(400, maxY + 100) + 'px';
  }

  // ===== 画布拖拽节点 =====
  function startNodeDrag(e, nodeEl) {
    isDragging = true;
    dragTarget = nodeEl;
    var rect = nodeEl.getBoundingClientRect();
    var canvasRect = canvasDropzone.getBoundingClientRect();
    dragOffsetX = (e.clientX || e.touches[0].clientX) - rect.left;
    dragOffsetY = (e.clientY || e.touches[0].clientY) - rect.top;
    nodeEl.classList.add('dragging');
  }

  document.addEventListener('mousemove', function(e) {
    if (!isDragging || !dragTarget) return;
    var canvasRect = canvasDropzone.getBoundingClientRect();
    var x = e.clientX - canvasRect.left - dragOffsetX;
    var y = e.clientY - canvasRect.top - dragOffsetY;
    var snap = document.getElementById('canvasSnapToggle')?.checked;
    if (snap) { x = Math.round(x / 20) * 20; y = Math.round(y / 20) * 20; }
    x = Math.max(0, x); y = Math.max(0, y);
    dragTarget.style.left = x + 'px';
    dragTarget.style.top = y + 'px';

    var agentId = dragTarget.getAttribute('data-agent-id');
    for (var i = 0; i < canvasAgents.length; i++) {
      if (canvasAgents[i].id === agentId) {
        canvasAgents[i].x = x;
        canvasAgents[i].y = y;
        break;
      }
    }
    renderConnections();
  });

  document.addEventListener('mouseup', function() {
    if (isDragging && dragTarget) {
      dragTarget.classList.remove('dragging');
    }
    isDragging = false;
    dragTarget = null;
    if (connectingSource) {
      connectingSource = null;
      if (connectingLine) connectingLine.remove();
      connectingLine = null;
    }
  });

  // ===== 连接线 =====
  function startConnection(e, agentId, portType) {
    connectingSource = { agentId: agentId, portType: portType };
    connectingLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    connectingLine.setAttribute('stroke', '#00d4ff');
    connectingLine.setAttribute('stroke-width', '2');
    connectingLine.setAttribute('stroke-dasharray', '5,3');
    canvasSvg.appendChild(connectingLine);

    var portEl = canvasDropzone.querySelector('[data-agent-id="' + agentId + '"] .node-port-output');
    if (portEl) {
      var portRect = portEl.getBoundingClientRect();
      var canvasRect = canvasDropzone.getBoundingClientRect();
      connectingLine.setAttribute('x1', portRect.left - canvasRect.left + 8);
      connectingLine.setAttribute('y1', portRect.top - canvasRect.top + 8);
      connectingLine.setAttribute('x2', portRect.left - canvasRect.left + 8);
      connectingLine.setAttribute('y2', portRect.top - canvasRect.top + 8);
    }

    document.addEventListener('mousemove', onConnectionMove);
  }

  function onConnectionMove(e) {
    if (!connectingSource || !connectingLine) return;
    var canvasRect = canvasDropzone.getBoundingClientRect();
    var portEl = canvasDropzone.querySelector('[data-agent-id="' + connectingSource.agentId + '"] .node-port-output');
    if (portEl) {
      var portRect = portEl.getBoundingClientRect();
      connectingLine.setAttribute('x1', portRect.left - canvasRect.left + 8);
      connectingLine.setAttribute('y1', portRect.top - canvasRect.top + 8);
    }
    var x2 = e.clientX - canvasRect.left;
    var y2 = e.clientY - canvasRect.top;
    connectingLine.setAttribute('x2', x2);
    connectingLine.setAttribute('y2', y2);
  }

  function completeConnection(targetAgentId) {
    if (!connectingSource) return;
    if (connectingSource.agentId === targetAgentId) {
      connectingSource = null;
      if (connectingLine) { connectingLine.remove(); connectingLine = null; }
      document.removeEventListener('mousemove', onConnectionMove);
      NexusUI.toast('不能连接到自身', 'error');
      return;
    }

    // 检查是否已存在相同连接
    for (var i = 0; i < connections.length; i++) {
      if (connections[i].from === connectingSource.agentId && connections[i].to === targetAgentId) {
        connectingSource = null;
        if (connectingLine) { connectingLine.remove(); connectingLine = null; }
        document.removeEventListener('mousemove', onConnectionMove);
        NexusUI.toast('连接已存在', 'info');
        return;
      }
    }

    connections.push({ from: connectingSource.agentId, to: targetAgentId });
    connectingSource = null;
    if (connectingLine) { connectingLine.remove(); connectingLine = null; }
    document.removeEventListener('mousemove', onConnectionMove);
    renderConnections();
    NexusUI.toast('已连接', 'success');
  }

  function renderConnections() {
    // 清除旧连线
    canvasSvg.innerHTML = '';

    if (connections.length === 0 || canvasAgents.length === 0) return;

    for (var i = 0; i < connections.length; i++) {
      var conn = connections[i];
      var fromAgent = null, toAgent = null;
      for (var j = 0; j < canvasAgents.length; j++) {
        if (canvasAgents[j].id === conn.from) fromAgent = canvasAgents[j];
        if (canvasAgents[j].id === conn.to) toAgent = canvasAgents[j];
      }
      if (!fromAgent || !toAgent) continue;

      var fromNode = canvasDropzone.querySelector('[data-agent-id="' + conn.from + '"] .node-port-output');
      var toNode = canvasDropzone.querySelector('[data-agent-id="' + conn.to + '"] .node-port-input');
      if (!fromNode || !toNode) continue;

      var canvasRect = canvasDropzone.getBoundingClientRect();
      var fromRect = fromNode.getBoundingClientRect();
      var toRect = toNode.getBoundingClientRect();

      var x1 = fromRect.left - canvasRect.left + 8;
      var y1 = fromRect.top - canvasRect.top + 8;
      var x2 = toRect.left - canvasRect.left + 8;
      var y2 = toRect.top - canvasRect.top + 8;

      // 贝塞尔曲线
      var cx1 = x1 + Math.abs(x2 - x1) * 0.5;
      var cy1 = y1;
      var cx2 = x2 - Math.abs(x2 - x1) * 0.5;
      var cy2 = y2;

      var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('d', 'M ' + x1 + ' ' + y1 + ' C ' + cx1 + ' ' + cy1 + ', ' + cx2 + ' ' + cy2 + ', ' + x2 + ' ' + y2);
      path.setAttribute('stroke', '#00d4ff');
      path.setAttribute('stroke-width', '2');
      path.setAttribute('fill', 'none');
      path.setAttribute('class', 'connection-line');

      // 删除按钮
      path.addEventListener('dblclick', function() {
        var idx = -1;
        for (var k = 0; k < connections.length; k++) {
          if (connections[k].from === conn.from && connections[k].to === conn.to) {
            idx = k; break;
          }
        }
        if (idx >= 0) {
          connections.splice(idx, 1);
          renderConnections();
          NexusUI.toast('连接已删除', 'info');
        }
      });

      canvasSvg.appendChild(path);
    }
  }

  // ===== Agent 选择 =====
  function selectAgent(agentId) {
    selectedAgentId = agentId;
    // 更新节点高亮
    var nodes = canvasDropzone.querySelectorAll('.canvas-node');
    for (var i = 0; i < nodes.length; i++) {
      nodes[i].classList.toggle('selected', nodes[i].getAttribute('data-agent-id') === agentId);
    }

    // 更新配置表单
    var agent = null;
    for (var j = 0; j < canvasAgents.length; j++) {
      if (canvasAgents[j].id === agentId) { agent = canvasAgents[j]; break; }
    }
    if (!agent) return;

    showConfig(agent);
  }

  function removeAgent(agentId) {
    canvasAgents = canvasAgents.filter(function(a) { return a.id !== agentId; });
    connections = connections.filter(function(c) { return c.from !== agentId && c.to !== agentId; });
    if (selectedAgentId === agentId) {
      selectedAgentId = null;
      configForm.classList.add('hidden');
      configPlaceholder.classList.remove('hidden');
    }
    renderCanvas();
    NexusUI.toast('已移除', 'info');
  }

  // ===== 配置表单 =====
  function showConfig(agent) {
    configPlaceholder.classList.add('hidden');
    configForm.classList.remove('hidden');

    document.getElementById('configAgentName').textContent = agent.name;
    document.getElementById('configAgentRole').textContent = getRoleName(agent.roleId);

    var modelSelect = document.getElementById('configModelSelect');
    modelSelect.innerHTML = '';
    var groups = NexusModels.getGroups();
    for (var g = 0; g < groups.length; g++) {
      for (var m = 0; m < groups[g].models.length; m++) {
        var opt = document.createElement('option');
        opt.value = groups[g].models[m].id;
        opt.textContent = groups[g].models[m].name;
        if (groups[g].models[m].id === agent.model) opt.selected = true;
        modelSelect.appendChild(opt);
      }
    }

    document.getElementById('configTemperature').value = agent.temperature;
    document.getElementById('configTempLabel').textContent = agent.temperature;
    document.getElementById('configMaxTokens').value = agent.maxTokens;
    document.getElementById('toolCode').checked = agent.tools.code;
    document.getElementById('toolTerminal').checked = agent.tools.terminal;
    document.getElementById('toolFile').checked = agent.tools.file;
    document.getElementById('toolWeb').checked = agent.tools.web;
    document.getElementById('toolImage').checked = agent.tools.image;
    document.getElementById('configSystemPrompt').value = agent.prompt;

    configForm.setAttribute('data-agent-id', agentId);

    // 设置触发器
    document.getElementById('configTemperature').oninput = function() {
      document.getElementById('configTempLabel').textContent = this.value;
    };
  }

  function setupConfigForm() {
    var saveBtn = document.getElementById('configSaveBtn');
    if (!saveBtn) return;
    saveBtn.addEventListener('click', function() {
      var agentId = configForm.getAttribute('data-agent-id');
      if (!agentId) return;
      for (var i = 0; i < canvasAgents.length; i++) {
        if (canvasAgents[i].id === agentId) {
          canvasAgents[i].model = document.getElementById('configModelSelect').value;
          canvasAgents[i].temperature = parseFloat(document.getElementById('configTemperature').value);
          canvasAgents[i].maxTokens = parseInt(document.getElementById('configMaxTokens').value);
          canvasAgents[i].tools = {
            code: document.getElementById('toolCode').checked,
            terminal: document.getElementById('toolTerminal').checked,
            file: document.getElementById('toolFile').checked,
            web: document.getElementById('toolWeb').checked,
            image: document.getElementById('toolImage').checked
          };
          canvasAgents[i].prompt = document.getElementById('configSystemPrompt').value;
          NexusUI.toast('配置已保存: ' + canvasAgents[i].name, 'success');
          break;
        }
      }
    });
  }

  function getRoleName(roleId) {
    for (var i = 0; i < AGENT_ROLES.length; i++) {
      if (AGENT_ROLES[i].id === roleId) return AGENT_ROLES[i].name;
    }
    return '';
  }

  // ===== Agent Tab 切换 =====
  function setupAgentTabs() {
    var tabs = document.querySelectorAll('.agent-tab');
    for (var i = 0; i < tabs.length; i++) {
      (function(tab) {
        tab.addEventListener('click', function() {
          var target = this.getAttribute('data-tab');
          tabs.forEach(function(t) { t.classList.remove('active'); });
          this.classList.add('active');

          var views = ['agentGallery', 'agentWorkflow', 'agentConfig', 'agentResults'];
          for (var v = 0; v < views.length; v++) {
            var el = document.getElementById(views[v]);
            if (el) el.classList.remove('active');
          }

          var idMap = { gallery: 'agentGallery', workflow: 'agentWorkflow', config: 'agentConfig', results: 'agentResults' };
          var targetEl = document.getElementById(idMap[target]);
          if (targetEl) targetEl.classList.add('active');
        });
      })(tabs[i]);
    }
  }

  // ===== 工作流操作 =====
  function setupWorkflowActions() {
    var runBtn = document.getElementById('agentRunBtn');
    var clearBtn = document.getElementById('agentClearBtn');
    var saveBtn = document.getElementById('agentSaveBtn');

    if (runBtn) runBtn.addEventListener('click', executeWorkflow);
    if (clearBtn) clearBtn.addEventListener('click', clearCanvas);
    if (saveBtn) saveBtn.addEventListener('click', saveWorkflow);
  }

  function clearCanvas() {
    if (canvasAgents.length === 0) return;
    if (!confirm('确定清空画布？')) return;
    canvasAgents = [];
    connections = [];
    selectedAgentId = null;
    configForm.classList.add('hidden');
    configPlaceholder.classList.remove('hidden');
    renderCanvas();
    NexusUI.toast('画布已清空', 'info');
  }

  function saveWorkflow() {
    var data = JSON.stringify({ agents: canvasAgents, connections: connections });
    try {
      localStorage.setItem('nx_agent_workflow', data);
      NexusUI.toast('工作流已保存', 'success');
    } catch (e) {
      NexusUI.toast('保存失败', 'error');
    }
  }

  function loadWorkflow() {
    try {
      var data = localStorage.getItem('nx_agent_workflow');
      if (data) {
        var parsed = JSON.parse(data);
        canvasAgents = parsed.agents || [];
        connections = parsed.connections || [];
        renderCanvas();
        if (canvasAgents.length > 0) showCanvas();
      }
    } catch (e) {}
  }

  // ===== 执行工作流 =====
  function executeWorkflow() {
  function executeWorkflow() {
    if (canvasAgents.length === 0) {
      if (typeof NexusUI !== 'undefined' && NexusUI.toast) NexusUI.toast('画布上没有 Agent', 'error');
      return;
    }

    // 切换结果视图
    var resultsTab = document.querySelector('.agent-tab[data-tab="results"]');
    if (resultsTab) resultsTab.click();

    resultsPlaceholder.classList.add('hidden');
    resultsContent.classList.remove('hidden');
    resultsLog.innerHTML = '';

    // 找到起始 Agent（没有输入连接的 Agent）
    var hasInput = {};
    for (var i = 0; i < connections.length; i++) {
      hasInput[connections[i].to] = true;
    }
    var startAgents = [];
    for (var j = 0; j < canvasAgents.length; j++) {
      if (!hasInput[canvasAgents[j].id]) startAgents.push(canvasAgents[j]);
    }
    if (startAgents.length === 0 && canvasAgents.length > 0) {
      startAgents = [canvasAgents[0]];
    }

    resultsStatus.textContent = '运行中...';
    resultsStatus.style.color = '#ffa502';
    addLog('system', '开始执行工作流 (' + canvasAgents.length + ' 个 Agent)');

    // 存储每个 Agent 的输出，供下游使用
    var agentOutputs = {};
    var processed = {};
    var pendingQueue = [];

    // 初始化队列
    for (var s = 0; s < startAgents.length; s++) {
      pendingQueue.push({ agent: startAgents[s], input: '请开始你的任务。' });
    }

    function processNext() {
      if (pendingQueue.length === 0) {
        var allDone = true;
        for (var a = 0; a < canvasAgents.length; a++) {
          if (!processed[canvasAgents[a].id]) { allDone = false; break; }
        }
        if (allDone) {
          resultsStatus.textContent = '完成';
          resultsStatus.style.color = '#2ed573';
          addLog('system', '工作流执行完成');
        }
        return;
      }

      var task = pendingQueue.shift();
      var agent = task.agent;
      var inputText = task.input;

      if (processed[agent.id]) {
        processNext();
        return;
      }
      processed[agent.id] = true;

      addLog(agent.id, agent.name + ' 启动...', 'start');
      resultsStatus.textContent = agent.name + ' 运行中...';

      // 构建系统提示词
      var systemPrompt = agent.config && agent.config.systemPrompt ? agent.config.systemPrompt :
        '你是一个 ' + agent.name + ' Agent。根据你的角色和任务，给出专业、有用的回应。';

      // 添加工具描述
      var toolsDesc = '';
      if (agent.config && agent.config.tools) {
        var toolNames = [];
        if (agent.config.tools.code) toolNames.push('代码编写');
        if (agent.config.tools.terminal) toolNames.push('终端执行');
        if (agent.config.tools.file) toolNames.push('文件操作');
        if (agent.config.tools.web) toolNames.push('网络搜索');
        if (agent.config.tools.image) toolNames.push('图像生成');
        if (toolNames.length > 0) {
          toolsDesc = '\n\n你可以使用以下工具: ' + toolNames.join(', ');
        }
      }

      // 添加上游输入
      var upstreamOutputs = [];
      for (var c = 0; c < connections.length; c++) {
        if (connections[c].to === agent.id) {
          var fromAgent = null;
          for (var a = 0; a < canvasAgents.length; a++) {
            if (canvasAgents[a].id === connections[c].from) {
              fromAgent = canvasAgents[a];
              break;
            }
          }
          if (fromAgent && agentOutputs[fromAgent.id]) {
            upstreamOutputs.push(fromAgent.name + ' 的输出:\n' + agentOutputs[fromAgent.id]);
          }
        }
      }

      var fullPrompt = systemPrompt + toolsDesc;
      if (upstreamOutputs.length > 0) {
        fullPrompt += '\n\n来自上游 Agent 的信息:\n' + upstreamOutputs.join('\n---\n');
      }

      var messages = [
        { role: 'system', content: fullPrompt },
        { role: 'user', content: inputText }
      ];

      var model = (agent.config && agent.config.model) ? agent.config.model :
        (typeof NexusModels !== 'undefined' ? NexusModels.getCurrentModel() : 'deepseek-chat');
      var temperature = (agent.config && agent.config.temperature) || 0.7;
      var maxTokens = (agent.config && agent.config.maxTokens) || 4096;

      addLog(agent.id, agent.name + ' 正在处理中 (' + model + ')...', 'info');

      // 检查是否有工具需要 → 使用 Agent 引擎（ReAct 循环）
      var hasTools = agent.config && agent.config.tools && (
        agent.config.tools.code || agent.config.tools.terminal || 
        agent.config.tools.file || agent.config.tools.web
      );

      if (hasTools && typeof NexusAPI !== 'undefined' && NexusAPI.agentExecuteStream) {
        // 使用 Agent 引擎（SSE 流式）
        addLog(agent.id, agent.name + ' 使用 Agent 引擎（工具模式·流式）', 'info');
        var taskText = fullPrompt + '\n\n用户请求: ' + inputText;
        var _agentStepLog = '';
        
        NexusAPI.agentExecuteStream(taskText, function(evt) {
          if (evt.type === 'thought') {
            _agentStepLog += '🤔 ' + (evt.action || '分析中...') + '\n';
            addLog(agent.id, '思考 → ' + (evt.action || '分析'), 'info');
          } else if (evt.type === 'observation') {
            var r = JSON.stringify(evt.result || {}).substring(0, 80);
            _agentStepLog += '  ✅ ' + (evt.action || '') + ' → ' + r + '\n';
          } else if (evt.type === 'final' && evt.content) {
            addLog(agent.id, '收到最终回答...', 'info');
          }
        }, function() {
          // onDone - 已完成所有 SSE 事件，需要获取最终结果（回退到非流式获取最终 answer）
          // 由于 SSE 流已经结束，且最后一个done事件包含了answer，但这里可能拿不到答案
          // 所以用 agentExecute 回退获取最终结果
          NexusAPI.agentExecute(taskText, model, 10).then(function(data) {
            var output = '';
            
            if (_agentStepLog) {
              output += '--- 工具调用 ---\n' + _agentStepLog + '---\n\n';
            }
            
            output += data.answer || '暂无回答';
            
            if (data.iterations) {
              output += '\n\n(⚡ ' + data.iterations + ' 步)';
            }
            
            agentOutputs[agent.id] = output;
            addLog(agent.id, agent.name + ' 完成（Agent 引擎）', 'success');
            
            // 找下游 & 入队
            for (var c2 = 0; c2 < connections.length; c2++) {
              if (connections[c2].from === agent.id) {
                for (var a3 = 0; a3 < canvasAgents.length; a3++) {
                  if (canvasAgents[a3].id === connections[c2].to && !processed[canvasAgents[a3].id]) {
                    pendingQueue.push({ agent: canvasAgents[a3], input: output.substring(0, 500) });
                  }
                }
              }
            }
            processNext();
          }).catch(function(err) {
            addLog(agent.id, agent.name + ' Agent 引擎错误: ' + err.message, 'error');
            processNext();
          });
        }, function(err) {
          addLog(agent.id, agent.name + ' 流式错误: ' + err, 'error');
          processNext();
        }, { model: model, maxIterations: 10 });
      } else if (hasTools && typeof NexusAPI !== 'undefined' && NexusAPI.agentExecute) {
        // 使用 Agent 引擎
        addLog(agent.id, agent.name + ' 使用 Agent 引擎（工具模式）', 'info');
        var taskText = fullPrompt + '\n\n用户请求: ' + inputText;
        
        NexusAPI.agentExecute(taskText, model, 10).then(function(data) {
          var output = '';
          
          // 显示工具调用历史
          if (data.history && data.history.length > 0) {
            output += '--- 工具调用 ---\n';
            data.history.forEach(function(h) {
              var r = JSON.stringify(h.result).substring(0, 100);
              output += '🔧 ' + h.action + ' → ' + r + '\n';
            });
            output += '---\n\n';
          }
          
          // 最终答案
          output += data.answer || '暂无回答';
          
          if (data.iterations) {
            output += '\n\n(⚡ ' + data.iterations + ' 步)';
          }
          
          agentOutputs[agent.id] = output;
          addLog(agent.id, agent.name + ' 完成（Agent 引擎）', 'success');
          
          // 找下游 & 入队
          for (var c2 = 0; c2 < connections.length; c2++) {
            if (connections[c2].from === agent.id) {
              for (var a3 = 0; a3 < canvasAgents.length; a3++) {
                if (canvasAgents[a3].id === connections[c2].to && !processed[canvasAgents[a3].id]) {
                  pendingQueue.push({ agent: canvasAgents[a3], input: output.substring(0, 500) });
                }
              }
            }
          }
          processNext();
        }).catch(function(err) {
          addLog(agent.id, agent.name + ' Agent 引擎错误: ' + err.message, 'error');
          processNext();
        });
        return;
      }

      // 无工具 → 使用普通聊天
      var fullResponse = '';

      if (typeof NexusAPI !== 'undefined' && NexusAPI.chatStream) {
        var controller = NexusAPI.chatStream(
          model,
          messages,
          function(chunk) {
            fullResponse += chunk;
            // 每收到一个块，更新最后一行日志
            var lastLog = resultsLog.lastElementChild;
            if (lastLog && lastLog.classList.contains('streaming')) {
              var msgEl = lastLog.querySelector('.log-msg');
              if (msgEl) msgEl.textContent = agent.name + ': ' + fullResponse.substring(0, 200) + (fullResponse.length > 200 ? '...' : '');
            } else {
              addLog(agent.id, agent.name + ': ' + fullResponse.substring(0, 100) + (fullResponse.length > 100 ? '...' : ''), 'streaming');
            }
          },
          function() {
            // Done
            agentOutputs[agent.id] = fullResponse;
            addLog(agent.id, agent.name + ' 完成', 'success');

            // 找下游 & 入队
            for (var c2 = 0; c2 < connections.length; c2++) {
              if (connections[c2].from === agent.id) {
                for (var a3 = 0; a3 < canvasAgents.length; a3++) {
                  if (canvasAgents[a3].id === connections[c2].to && !processed[canvasAgents[a3].id]) {
                    pendingQueue.push({ agent: canvasAgents[a3], input: fullResponse.substring(0, 500) });
                  }
                }
              }
            }
            // 处理下一个
            processNext();
          },
          function(err) {
            addLog(agent.id, agent.name + ' 出错: ' + err, 'error');
            agentOutputs[agent.id] = '(错误: ' + err + ')';
            processNext();
          },
          { temperature: temperature, max_tokens: maxTokens }
        );
      } else {
        // Fallback: 模拟响应
        addLog(agent.id, agent.name + ' 正在处理: ' + inputText.substring(0, 100), 'info');
        setTimeout(function() {
          agentOutputs[agent.id] = agent.name + ' 处理完成: 分析完毕。';
          addLog(agent.id, agent.name + ' 完成 (模拟)', 'success');
          processNext();
        }, 300);
      }
    }

    processNext();
  }

  function addLog(source, message, type) {
    if (!resultsLog) return;
    type = type || 'info';
    var line = document.createElement('div');
    line.className = 'results-log-line ' + type;
    line.innerHTML = '<span class="log-time">' + new Date().toLocaleTimeString() + '</span> ' +
      '<span class="log-source">[' + source + ']</span> ' +
      '<span class="log-msg">' + message + '</span>';
    resultsLog.appendChild(line);
    resultsLog.scrollTop = resultsLog.scrollHeight;
  }

  function setupResults() {
    var clearBtn = document.getElementById('resultsClearBtn');
    if (clearBtn) {
      clearBtn.addEventListener('click', function() {
        resultsLog.innerHTML = '';
        resultsContent.classList.add('hidden');
        resultsPlaceholder.classList.remove('hidden');
        resultsStatus.textContent = 'Ready';
        resultsStatus.style.color = '';
      });
    }
  }

  // ===== 画布放置 =====
  function setupCanvas() {
    if (!canvasDropzone) return;

    canvasDropzone.addEventListener('dragover', function(e) {
      e.preventDefault();
    });

    canvasDropzone.addEventListener('drop', function(e) {
      e.preventDefault();
      if (window._agentDragRole) {
        addAgentToCanvas(window._agentDragRole);
        window._agentDragRole = null;
      }
    });

    // 加载保存的工作流
    loadWorkflow();
  }

  // ===== 公共 API =====
  return {
    init: init,
    addAgent: addAgentToCanvas,
  }
    executeWorkflow: executeWorkflow
  };
})();

