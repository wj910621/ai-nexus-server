// Y·NEX IDE 前端逻辑 v2
// Monaco Editor + 多文件 Agent 编辑 + MCP + Y·NEX自动化工作流

let workspacePath = null;
const openFiles = new Map();
let activeFile = null;
let terminalId = null;
let terminalUnsub = null;
let monacoReady = false;
const editors = new Map();
let diffEditor = null;
const mcpServers = new Map();
const automationHistory = [];

const ynexClient = new YnexClient('http://localhost:7777', localStorage.getItem('ynex_api_key') || '');

// ============================================================
// 初始化
// ============================================================

document.addEventListener('DOMContentLoaded', async () => {
  initMonaco();

  const saved = localStorage.getItem('ynex_workspace');
  if (saved) {
    workspacePath = saved;
    document.getElementById('workspace-path').textContent = workspacePath;
    await refreshFileTree();
  }

  await initTerminal();
  checkLocalAiStatus();
  loadMcpServers();

  // M3: F12 跳转定义
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault();
      saveCurrentFile();
    }
    if (e.key === 'F12') {
      e.preventDefault();
      lspGoToDefinition();
    }
    if (e.key === 'F8') {
      e.preventDefault();
      lspGetDiagnostics();
    }
  });
});

function initMonaco() {
  if (typeof require === 'undefined') {
    console.warn('Monaco loader 未就绪，回退到 textarea');
    return;
  }
  require.config({ paths: { 'vs': './vs' } });
  require(['vs/editor/editor.main'], () => {
    monacoReady = true;
    console.log('[Y·NEX IDE] Monaco Editor 已加载');
    // 重新渲染当前打开的文件
    if (activeFile) switchToTab(activeFile);
  }, (err) => {
    console.error('[Y·NEX IDE] Monaco 加载失败:', err);
  });
}

async function checkLocalAiStatus() {
  try {
    const status = await window.ynex.ynex.status();
    const el = document.getElementById('status-local-ai');
    if (status.online) {
      el.textContent = '本地AI: 在线';
      el.style.color = 'var(--success)';
    } else {
      el.textContent = '本地AI: 离线';
      el.style.color = 'var(--danger)';
    }
  } catch (e) {
    document.getElementById('status-local-ai').textContent = '本地AI: 未知';
  }
}

// ============================================================
// 工作区
// ============================================================

async function openWorkspace() {
  try {
    const result = await window.ynex.workspace.open();
    if (result.ok) {
      workspacePath = result.path;
      localStorage.setItem('ynex_workspace', workspacePath);
      document.getElementById('workspace-path').textContent = workspacePath;
      openFiles.clear();
      document.getElementById('tabs').innerHTML = '';
      document.getElementById('editor-container').innerHTML = '<div class="editor-placeholder">选择左侧文件开始编辑</div>';
      activeFile = null;
      await refreshFileTree();
      appendTerminalOutput(`工作区已打开: ${workspacePath}\r\n`);
    }
  } catch (e) {
    alert('打开工作区失败: ' + e.message);
  }
}

// ============================================================
// 文件树
// ============================================================

async function refreshFileTree() {
  if (!workspacePath) return;
  const treeEl = document.getElementById('file-tree');
  treeEl.innerHTML = '<div class="tree-empty">加载中...</div>';

  try {
    const result = await window.ynex.fs.readDir(workspacePath);
    if (!result.ok) {
      treeEl.innerHTML = `<div class="tree-empty">加载失败: ${escapeHtml(result.error)}</div>`;
      return;
    }
    treeEl.innerHTML = '';
    renderTreeItems(treeEl, result.entries, workspacePath, 0);
  } catch (e) {
    treeEl.innerHTML = `<div class="tree-empty">错误: ${escapeHtml(e.message)}</div>`;
  }
}

function renderTreeItems(container, entries, parentPath, depth) {
  const sorted = entries.slice().sort((a, b) => {
    if (a.isDirectory && !b.isDirectory) return -1;
    if (!a.isDirectory && b.isDirectory) return 1;
    return a.name.localeCompare(b.name);
  });

  sorted.forEach(entry => {
    const item = document.createElement('div');
    item.className = 'tree-item';
    item.style.paddingLeft = (12 + depth * 14) + 'px';
    item.dataset.path = entry.path;
    item.dataset.directory = entry.isDirectory;

    const icon = entry.isDirectory ? '📁' : getFileIcon(entry.name);
    item.innerHTML = `<span class="icon">${icon}</span><span class="name">${escapeHtml(entry.name)}</span>`;

    item.addEventListener('click', (e) => {
      e.stopPropagation();
      document.querySelectorAll('.tree-item').forEach(i => i.classList.remove('active'));
      item.classList.add('active');
      if (entry.isDirectory) {
        toggleDirectory(item, entry.path);
      } else {
        openFile(entry.path);
      }
    });

    item.addEventListener('contextmenu', (e) => showContextMenu(e, entry));
    container.appendChild(item);

    if (entry.isDirectory) {
      const childrenContainer = document.createElement('div');
      childrenContainer.className = 'tree-children';
      childrenContainer.style.display = 'none';
      childrenContainer.id = 'tree-children-' + pathId(entry.path);
      container.appendChild(childrenContainer);
    }
  });
}

async function toggleDirectory(item, dirPath) {
  const childrenId = 'tree-children-' + pathId(dirPath);
  const childrenContainer = document.getElementById(childrenId);
  if (!childrenContainer) return;

  if (childrenContainer.style.display === 'none') {
    if (childrenContainer.children.length === 0) {
      const result = await window.ynex.fs.readDir(dirPath);
      if (result.ok) {
        renderTreeItems(childrenContainer, result.entries, dirPath, 1);
      }
    }
    childrenContainer.style.display = 'block';
    item.querySelector('.icon').textContent = '📂';
  } else {
    childrenContainer.style.display = 'none';
    item.querySelector('.icon').textContent = '📁';
  }
}

function pathId(p) {
  return btoa(unescape(encodeURIComponent(p))).replace(/[^a-zA-Z0-9]/g, '');
}

function getFileIcon(filename) {
  const ext = filename.split('.').pop().toLowerCase();
  const map = {
    js: '📜', ts: '📘', jsx: '⚛️', tsx: '⚛️',
    py: '🐍', java: '☕', cpp: '🔧', c: '🔧',
    html: '🌐', css: '🎨', json: '📋', md: '📝',
    yml: '⚙️', yaml: '⚙️', xml: '📄', txt: '📃'
  };
  return map[ext] || '📄';
}

function showContextMenu(e, entry) {
  e.preventDefault();
  const menu = document.getElementById('context-menu');
  menu.innerHTML = '';
  const items = [
    { label: '打开', action: () => { if (!entry.isDirectory) openFile(entry.path); } },
    { label: '在终端中打开', action: async () => {
      const result = await window.ynex.workspace.set(entry.isDirectory ? entry.path : entry.path.replace(/\\[^\\]+$/, ''));
      if (result.ok) appendTerminalOutput(`工作目录: ${result.path}\r\n`);
    }},
    { label: '重命名', action: async () => {
      const newName = prompt('新名称:', entry.name);
      if (!newName) return;
      const newPath = entry.path.replace(/\\[^\\]+$/, '\\' + newName);
      const r = await window.ynex.fs.rename(entry.path, newPath);
      if (r.ok) refreshFileTree(); else alert(r.error);
    }},
    { label: '删除', action: async () => {
      if (!confirm('确定删除 ' + entry.name + '?')) return;
      const r = await window.ynex.fs.delete(entry.path);
      if (r.ok) refreshFileTree(); else alert(r.error);
    }}
  ];
  items.forEach(it => {
    const div = document.createElement('div');
    div.className = 'menu-item';
    div.textContent = it.label;
    div.onclick = () => { menu.style.display = 'none'; it.action(); };
    menu.appendChild(div);
  });
  menu.style.display = 'block';
  menu.style.left = e.pageX + 'px';
  menu.style.top = e.pageY + 'px';
}

document.addEventListener('click', () => {
  document.getElementById('context-menu').style.display = 'none';
});

async function createNewFile() {
  if (!workspacePath) return alert('请先打开工作区');
  const name = prompt('输入文件名:');
  if (!name) return;
  const filePath = workspacePath + '\\' + name;
  try {
    const result = await window.ynex.fs.writeFile(filePath, '');
    if (result.ok) {
      await refreshFileTree();
      openFile(filePath);
    } else {
      alert('创建失败: ' + result.error);
    }
  } catch (e) {
    alert('错误: ' + e.message);
  }
}

async function createNewFolder() {
  if (!workspacePath) return alert('请先打开工作区');
  const name = prompt('输入文件夹名:');
  if (!name) return;
  const dirPath = workspacePath + '\\' + name;
  try {
    const result = await window.ynex.fs.createDirectory(dirPath);
    if (result.ok) {
      await refreshFileTree();
    } else {
      alert('创建失败: ' + result.error);
    }
  } catch (e) {
    alert('错误: ' + e.message);
  }
}

// ============================================================
// Monaco 编辑器
// ============================================================

function getLanguage(filePath) {
  const ext = filePath.split('.').pop().toLowerCase();
  const map = {
    js: 'javascript', jsx: 'javascript', ts: 'typescript', tsx: 'typescript',
    py: 'python', java: 'java', cpp: 'cpp', c: 'c', h: 'cpp',
    html: 'html', htm: 'html', css: 'css', scss: 'scss', less: 'less',
    json: 'json', md: 'markdown', yaml: 'yaml', yml: 'yaml',
    xml: 'xml', sql: 'sql', sh: 'shell', ps1: 'powershell',
    go: 'go', rs: 'rust', rb: 'ruby', php: 'php'
  };
  return map[ext] || 'plaintext';
}

async function openFile(filePath) {
  if (openFiles.has(filePath)) {
    switchToTab(filePath);
    return;
  }

  try {
    const result = await window.ynex.fs.readFile(filePath);
    if (!result.ok) {
      appendTerminalOutput(`打开文件失败: ${result.error}\r\n`);
      return;
    }

    openFiles.set(filePath, {
      content: result.content,
      modified: false
    });

    createTab(filePath);
    createEditorPane(filePath, result.content);
    switchToTab(filePath);
  } catch (e) {
    appendTerminalOutput(`打开文件错误: ${e.message}\r\n`);
  }
}

function createTab(filePath) {
  const tabsEl = document.getElementById('tabs');
  const tab = document.createElement('div');
  tab.className = 'tab active';
  tab.dataset.path = filePath;
  const filename = filePath.split('\\').pop().split('/').pop();
  tab.innerHTML = `
    <span>${escapeHtml(filename)}</span>
    <span class="close" onclick="closeTab(event, '${escapeJsString(filePath)}')">✕</span>
  `;
  tab.addEventListener('click', (e) => {
    if (!e.target.classList.contains('close')) {
      switchToTab(filePath);
    }
  });
  tabsEl.appendChild(tab);
}

function createEditorPane(filePath, content) {
  const container = document.getElementById('editor-container');
  const placeholder = container.querySelector('.editor-placeholder');
  if (placeholder) placeholder.remove();

  const pane = document.createElement('div');
  pane.className = 'editor-pane';
  pane.dataset.path = filePath;
  pane.innerHTML = `
    <div class="editor-info">
      <span class="editor-path">${escapeHtml(filePath)}</span>
      <span class="editor-status">已保存</span>
    </div>
    <div class="monaco-host"></div>
    <textarea class="editor-textarea" spellcheck="false">${escapeHtml(content)}</textarea>
  `;

  container.appendChild(pane);

  if (monacoReady) {
    initMonacoEditor(filePath, content, pane);
  }
}

function initMonacoEditor(filePath, content, pane) {
  const host = pane.querySelector('.monaco-host');
  if (!host || host.children.length > 0) return;

  const model = monaco.editor.createModel(content, getLanguage(filePath), monaco.Uri.file(filePath));
  const editor = monaco.editor.create(host, {
    model,
    theme: 'vs-dark',
    automaticLayout: true,
    minimap: { enabled: true },
    fontSize: 13,
    fontFamily: 'Cascadia Code, Fira Code, Consolas, monospace',
    lineNumbers: 'on',
    scrollBeyondLastLine: false,
    wordWrap: 'on',
    quickSuggestions: true,
    suggestOnTriggerCharacters: true,
    formatOnPaste: true,
    formatOnType: true
  });

  editor.onDidChangeModelContent(() => {
    const file = openFiles.get(filePath);
    if (file) {
      file.modified = true;
      file.content = editor.getValue();
      updateTabModified(filePath, true);
      updateStatus(filePath);
    }
  });

  editor.onDidChangeCursorPosition((e) => {
    if (activeFile === filePath) {
      document.getElementById('status-position').textContent = `Ln ${e.position.lineNumber}, Col ${e.position.column}`;
    }
  });

  editors.set(filePath, { editor, model });
}

function getEditorContent(filePath) {
  const ed = editors.get(filePath);
  if (ed) return ed.editor.getValue();
  const pane = document.querySelector(`.editor-pane[data-path="${escapeSelector(filePath)}"]`);
  if (pane) return pane.querySelector('.editor-textarea').value;
  const file = openFiles.get(filePath);
  return file ? file.content : '';
}

function switchToTab(filePath) {
  activeFile = filePath;

  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.editor-pane').forEach(p => p.classList.remove('active'));

  const tab = document.querySelector(`.tab[data-path="${escapeSelector(filePath)}"]`);
  const pane = document.querySelector(`.editor-pane[data-path="${escapeSelector(filePath)}"]`);
  if (tab) tab.classList.add('active');
  if (pane) {
    pane.classList.add('active');
    if (monacoReady && !editors.has(filePath)) {
      const file = openFiles.get(filePath);
      if (file) initMonacoEditor(filePath, file.content, pane);
    }
  }

  updateStatus(filePath);
}

function closeTab(event, filePath) {
  event.stopPropagation();
  const file = openFiles.get(filePath);
  if (file && file.modified) {
    if (confirm('文件已修改，是否保存?')) saveFile(filePath);
  }

  openFiles.delete(filePath);
  const ed = editors.get(filePath);
  if (ed) { ed.editor.dispose(); ed.model.dispose(); editors.delete(filePath); }
  const tab = document.querySelector(`.tab[data-path="${escapeSelector(filePath)}"]`);
  const pane = document.querySelector(`.editor-pane[data-path="${escapeSelector(filePath)}"]`);
  if (tab) tab.remove();
  if (pane) pane.remove();

  if (activeFile === filePath) {
    const remaining = document.querySelectorAll('.tab');
    if (remaining.length > 0) {
      switchToTab(remaining[remaining.length - 1].dataset.path);
    } else {
      activeFile = null;
      document.getElementById('editor-container').innerHTML = '<div class="editor-placeholder">选择左侧文件开始编辑</div>';
      document.getElementById('status-file').textContent = '未选择文件';
    }
  }
}

async function saveCurrentFile() {
  if (!activeFile) return;
  await saveFile(activeFile);
}

async function saveFile(filePath) {
  const file = openFiles.get(filePath);
  if (!file) return;

  try {
    const content = getEditorContent(filePath);
    const result = await window.ynex.fs.writeFile(filePath, content);
    if (result.ok) {
      file.content = content;
      file.modified = false;
      updateTabModified(filePath, false);
      updateStatus(filePath);
      appendTerminalOutput(`已保存: ${filePath}\r\n`);
    } else {
      appendTerminalOutput(`保存失败: ${result.error}\r\n`);
    }
  } catch (e) {
    appendTerminalOutput(`保存错误: ${e.message}\r\n`);
  }
}

function updateTabModified(filePath, modified) {
  const tab = document.querySelector(`.tab[data-path="${escapeSelector(filePath)}"] span`);
  if (!tab) return;
  const filename = filePath.split('\\').pop().split('/').pop();
  tab.textContent = modified ? filename + ' ●' : filename;
}

function updateStatus(filePath) {
  const file = openFiles.get(filePath);
  const pane = document.querySelector(`.editor-pane[data-path="${escapeSelector(filePath)}"]`);
  if (pane) {
    const statusEl = pane.querySelector('.editor-status');
    if (statusEl) statusEl.textContent = file && file.modified ? '已修改' : '已保存';
  }
  document.getElementById('status-file').textContent = filePath.split('\\').pop().split('/').pop();
}

// ============================================================
// Diff 面板
// ============================================================

function showDiffPanel() {
  document.getElementById('diff-panel').classList.add('active');
}

function closeOverlay(id) {
  document.getElementById(id).classList.remove('active');
}

async function diffCurrentFileWithSaved() {
  if (!activeFile) return alert('请先打开一个文件');
  const original = openFiles.get(activeFile)?.content || '';
  const modified = getEditorContent(activeFile);
  showDiff(original, modified, activeFile);
}

async function diffWorkspaceGitStatus() {
  if (!workspacePath) return alert('请先打开工作区');
  const result = await window.ynex.system.execute({
    program: 'git',
    args: ['diff', '--stat'],
    cwd: workspacePath
  });
  if (!result.ok || !result.result.stdout) {
    alert('无法获取 Git 状态，请确认是 Git 仓库');
    return;
  }
  appendTerminalOutput(`Git 状态:\r\n${result.result.stdout}\r\n`);
}

function showDiff(original, modified, title) {
  showDiffPanel();
  const host = document.getElementById('diff-editor');
  host.innerHTML = '';
  if (!monacoReady) {
    host.textContent = 'Monaco 未就绪';
    return;
  }
  if (diffEditor) diffEditor.dispose();
  diffEditor = monaco.editor.createDiffEditor(host, {
    theme: 'vs-dark',
    automaticLayout: true,
    renderSideBySide: true,
    readOnly: true
  });
  diffEditor.setModel({
    original: monaco.editor.createModel(original, getLanguage(title)),
    modified: monaco.editor.createModel(modified, getLanguage(title))
  });
}

// ============================================================
// 终端
// ============================================================

async function initTerminal() {
  terminalId = 'main-terminal';
  try {
    const result = await window.ynex.terminal.create(terminalId, workspacePath || undefined);
    if (result.ok) {
      terminalUnsub = window.ynex.terminal.onData(terminalId, (output) => {
        appendTerminalOutput(output);
      });
      appendTerminalOutput('终端已启动\r\n');
    } else {
      appendTerminalOutput(`终端启动失败: ${result.error}\r\n`);
    }
  } catch (e) {
    appendTerminalOutput(`终端错误: ${e.message}\r\n`);
  }
}

function appendTerminalOutput(text) {
  const outputEl = document.getElementById('terminal-output');
  outputEl.textContent += text;
  outputEl.scrollTop = outputEl.scrollHeight;
}

function clearTerminal() {
  document.getElementById('terminal-output').textContent = '';
}

async function handleTerminalKey(event) {
  if (event.key !== 'Enter') return;
  const input = document.getElementById('terminal-input');
  const command = input.value;
  if (!command.trim()) return;

  appendTerminalOutput(`PS > ${command}\r\n`);
  input.value = '';

  try {
    await window.ynex.terminal.write(terminalId, command + '\r\n');
  } catch (e) {
    appendTerminalOutput(`发送命令失败: ${e.message}\r\n`);
  }
}

function showBottomTab(tab) {
  document.querySelectorAll('#bottom-panel .tab-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
}

// ============================================================
// AI 助手
// ============================================================

function toggleAiPanel() {
  const panel = document.getElementById('ai-panel');
  panel.style.display = panel.style.display === 'none' ? 'flex' : 'none';
}

function addAiMessage(role, content) {
  const container = document.getElementById('ai-messages');
  const div = document.createElement('div');
  div.className = `ai-message ${role}`;
  div.innerHTML = content;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  return div;
}

function getCurrentCode() {
  if (!activeFile) return null;
  return {
    path: activeFile,
    code: getEditorContent(activeFile)
  };
}

async function sendAiMessage() {
  const input = document.getElementById('ai-input');
  const text = input.value.trim();
  if (!text) return;

  input.value = '';
  addAiMessage('user', escapeHtml(text));
  const replyEl = addAiMessage('assistant', '思考中...');

  try {
    const status = await window.ynex.ynex.status();
    const useLocal = status.online;
    const useMock = false;

    let reply = '';
    await ynexClient.chatStream(text, (chunk) => {
      reply += chunk;
      replyEl.innerHTML = formatAiReply(reply);
    }, { useLocal, useMock });
  } catch (e) {
    replyEl.textContent = '错误: ' + e.message;
  }
}

async function aiExplainCode() {
  const current = getCurrentCode();
  if (!current) {
    addAiMessage('assistant', '请先打开一个文件并选择要解释的代码。');
    return;
  }
  const prompt = `请解释以下代码的作用和工作原理，用中文回答。文件路径: ${current.path}\n\n${current.code}`;
  document.getElementById('ai-input').value = prompt;
  await sendAiMessage();
}

async function aiRefactorCode() {
  const current = getCurrentCode();
  if (!current) {
    addAiMessage('assistant', '请先打开一个文件。');
    return;
  }
  const prompt = `请重构以下代码，使其更简洁、高效、易读。保持原有功能不变，用中文说明主要改动。文件路径: ${current.path}\n\n${current.code}`;
  document.getElementById('ai-input').value = prompt;
  await sendAiMessage();
}

async function aiCompleteCode() {
  const current = getCurrentCode();
  if (!current) {
    addAiMessage('assistant', '请先打开一个文件并将光标放在需要补全的位置。');
    return;
  }
  const prompt = `请根据当前文件内容和光标位置，补全后续代码。只输出需要补充的代码片段，不要重复已有内容。文件路径: ${current.path}\n\n${current.code}`;
  document.getElementById('ai-input').value = prompt;
  await sendAiMessage();
}

function formatAiReply(text) {
  return escapeHtml(text).replace(/```([\s\S]*?)```/g, '<div class="code-block">$1</div>');
}

// ============================================================
// 多文件 Agent 编辑 / 项目级重构
// ============================================================

async function runProjectAgent() {
  if (!workspacePath) return alert('请先打开工作区');
  const task = prompt('描述要对整个项目执行的任务:', '重构代码风格并统一错误处理');
  if (!task) return;

  addAiMessage('user', `[项目级任务] ${task}`);
  const replyEl = addAiMessage('assistant', '正在扫描项目并制定计划...');

  try {
    const files = await collectProjectFiles();
    const status = await window.ynex.ynex.status();
    const useLocal = status.online;

    let plan = '';
    await ynexClient.chatStream(
      `你是项目级重构 Agent。工作区: ${workspacePath}\n共有 ${files.length} 个代码文件。\n任务: ${task}\n请制定详细计划：要修改哪些文件、每处如何改。只输出计划，不要执行。文件列表前 50 个:\n${files.slice(0, 50).join('\n')}`,
      (chunk) => { plan += chunk; replyEl.innerHTML = formatAiReply(plan); },
      { useLocal }
    );

    if (confirm('是否让 Agent 自动应用修改？')) {
      replyEl.innerHTML += '<br><br>正在执行修改...';
      await executeAgentPlan(task, files, replyEl);
    }
  } catch (e) {
    replyEl.textContent = '错误: ' + e.message;
  }
}

async function collectProjectFiles() {
  const isWin = navigator.platform.toLowerCase().includes('win');
  let result;
  if (isWin) {
    result = await window.ynex.system.execute({
      program: 'powershell',
      args: ['-Command', 'Get-ChildItem -Recurse -File -Include *.js,*.ts,*.jsx,*.tsx,*.py,*.java,*.html,*.css,*.json | Select-Object -ExpandProperty FullName'],
      cwd: workspacePath
    });
  } else {
    result = await window.ynex.system.execute({
      program: 'find',
      args: ['.', '-type', 'f', '(', '-name', '*.js', '-o', '-name', '*.ts', '-o', '-name', '*.jsx', '-o', '-name', '*.tsx', '-o', '-name', '*.py', '-o', '-name', '*.java', '-o', '-name', '*.html', '-o', '-name', '*.css', '-o', '-name', '*.json', ')'],
      cwd: workspacePath
    });
  }
  if (!result.ok || !result.result.stdout) return [];
  return result.result.stdout.split('\n').map(x => x.trim()).filter(Boolean);
}

async function executeAgentPlan(task, files, replyEl) {
  // M3: 沙箱模式 — 先快照，再修改，语法检查，diff 审查，可回滚
  replyEl.innerHTML += '<br><br>📸 正在创建文件快照...';
  await window.ynex.sandbox.snapshotAll(files.slice(0, 20));

  let modifiedCount = 0;
  const diffs = [];

  for (const filePath of files.slice(0, 20)) {
    try {
      const readResult = await window.ynex.fs.readFile(filePath);
      if (!readResult.ok) continue;

      let newContent = '';
      await ynexClient.chatStream(
        `对文件执行以下任务，直接输出修改后的完整文件内容，不要加解释。任务: ${task}\n文件: ${filePath}\n\n${readResult.content}`,
        (chunk) => { newContent += chunk; },
        { useLocal: true }
      );

      newContent = newContent.replace(/^```[\w]*\n?/, '').replace(/\n?```$/, '');
      if (newContent && newContent !== readResult.content) {
        // M3: 沙箱安全写入（语法检查 + 自动回滚）
        const writeResult = await window.ynex.sandbox.safeWrite(filePath, newContent);
        if (writeResult.ok) {
          modifiedCount++;
          diffs.push({ filePath, status: 'ok' });
        } else {
          diffs.push({ filePath, status: 'failed', error: writeResult.error });
        }
      }
    } catch (e) {
      diffs.push({ filePath, status: 'error', error: e.message });
    }
  }

  let summary = `<br><br>✅ 已完成，修改了 ${modifiedCount} 个文件。`;
  const failed = diffs.filter(d => d.status !== 'ok');
  if (failed.length > 0) {
    summary += `<br>⚠️ ${failed.length} 个文件修改失败（已自动回滚）:<br>`;
    failed.forEach(d => { summary += `- ${d.filePath}: ${d.error}<br>`; });
  }
  summary += `<br><button onclick="rollbackAgentChanges()" style="margin-top:8px;padding:4px 10px;background:var(--danger);color:#fff;border:none;border-radius:4px;cursor:pointer">↩ 回滚所有修改</button>`;
  replyEl.innerHTML += summary;
  await refreshFileTree();
}

async function rollbackAgentChanges() {
  if (!confirm('确定要回滚所有 Agent 修改吗？这将恢复到修改前的状态。')) return;
  const result = await window.ynex.sandbox.rollbackAll();
  addAiMessage('assistant', '已回滚所有修改。');
  await refreshFileTree();
}

// ============================================================
// M3: LSP 语言服务器（跳转定义、诊断、悬停）
// ============================================================

async function lspGoToDefinition() {
  if (!activeFile) return;
  const ed = editors.get(activeFile);
  if (!ed) return;
  const pos = ed.editor.getPosition();
  try {
    const result = await window.ynex.lsp.goToDefinition(activeFile, pos.lineNumber, pos.column, workspacePath);
    if (result.ok && result.locations?.length > 0) {
      const loc = result.locations[0];
      openFile(loc.path);
      // 跳转到指定行
      const targetEd = editors.get(loc.path);
      if (targetEd) {
        targetEd.editor.revealLineInCenter(loc.line);
        targetEd.editor.setPosition({ lineNumber: loc.line, column: loc.col });
      }
      appendTerminalOutput(`[LSP] 跳转到: ${loc.path}:${loc.line}:${loc.col}\r\n`);
    } else {
      appendTerminalOutput(`[LSP] ${result.error || '未找到定义'}\r\n`);
    }
  } catch (e) {
    appendTerminalOutput(`[LSP] 错误: ${e.message}\r\n`);
  }
}

async function lspGetDiagnostics() {
  if (!activeFile) return;
  try {
    const result = await window.ynex.lsp.getDiagnostics(activeFile, workspacePath);
    if (result.ok && result.diagnostics?.length > 0) {
      // 设置 Monaco 标记
      const ed = editors.get(activeFile);
      if (ed && monacoReady) {
        const markers = result.diagnostics.map(d => ({
          severity: d.severity === 1 ? monaco.MarkerSeverity.Error : monaco.MarkerSeverity.Warning,
          message: d.message,
          startLineNumber: (d.range?.start?.line ?? 0) + 1,
          startColumn: (d.range?.start?.character ?? 0) + 1,
          endLineNumber: (d.range?.end?.line ?? 0) + 1,
          endColumn: (d.range?.end?.character ?? 0) + 1,
        }));
        monaco.editor.setModelMarkers(ed.model, 'lsp', markers);
      }
      const errors = result.diagnostics.filter(d => d.severity === 1).length;
      const warnings = result.diagnostics.filter(d => d.severity === 2).length;
      appendTerminalOutput(`[LSP] 诊断: ${errors} 错误, ${warnings} 警告\r\n`);
    } else {
      // 清除标记
      const ed = editors.get(activeFile);
      if (ed && monacoReady) monaco.editor.setModelMarkers(ed.model, 'lsp', []);
      appendTerminalOutput('[LSP] 无诊断问题\r\n');
    }
  } catch (e) {
    appendTerminalOutput(`[LSP] 诊断失败: ${e.message}\r\n`);
  }
}

async function lspHover() {
  if (!activeFile) return;
  const ed = editors.get(activeFile);
  if (!ed) return;
  const pos = ed.editor.getPosition();
  try {
    const result = await window.ynex.lsp.hover(activeFile, pos.lineNumber, pos.column, workspacePath);
    if (result.ok) {
      addAiMessage('assistant', '<b>悬停信息:</b><br>' + escapeHtml(result.content));
    }
  } catch (e) {}
}

// ============================================================
// M3: 自动运行测试
// ============================================================

async function runProjectTests() {
  if (!workspacePath) return alert('请先打开工作区');
  appendTerminalOutput('[测试] 正在运行项目测试...\r\n');
  const result = await window.ynex.sandbox.runTests(workspacePath);
  if (result.ok && result.results?.length > 0) {
    result.results.forEach(r => {
      appendTerminalOutput(`[测试] ${r.command || ''}\r\n${r.stdout || ''}\r\n${r.error ? '错误: ' + r.error : '通过'}\r\n`);
    });
  } else {
    appendTerminalOutput('[测试] 未检测到可运行的测试命令\r\n');
  }
}

// ============================================================
// MCP 协议接入
// ============================================================

function openMcpPanel() {
  document.getElementById('mcp-panel').classList.add('active');
  renderMcpServers();
}

function loadMcpServers() {
  try {
    const saved = JSON.parse(localStorage.getItem('ynex_mcp_servers') || '[]');
    saved.forEach(s => mcpServers.set(s.name, s));
  } catch (e) {}
}

function saveMcpServers() {
  localStorage.setItem('ynex_mcp_servers', JSON.stringify(Array.from(mcpServers.values())));
}

function addMcpServer() {
  const name = document.getElementById('mcp-server-name').value.trim();
  const command = document.getElementById('mcp-server-command').value.trim();
  if (!name || !command) return alert('请输入名称和命令');
  mcpServers.set(name, { name, command, tools: [] });
  saveMcpServers();
  document.getElementById('mcp-server-name').value = '';
  document.getElementById('mcp-server-command').value = '';
  renderMcpServers();
}

function removeMcpServer(name) {
  mcpServers.delete(name);
  saveMcpServers();
  renderMcpServers();
}

async function discoverMcpTools(name) {
  const server = mcpServers.get(name);
  if (!server) return;
  addAiMessage('assistant', `正在连接 MCP 服务器: ${name}...`);
  appendTerminalOutput(`[MCP] 连接 ${name}...\r\n`);

  const result = await window.ynex.mcp.addServer(name, server.command, workspacePath);
  if (result.ok) {
    server.tools = result.tools || [];
    addAiMessage('assistant', `MCP ${name} 已连接，发现 ${server.tools.length} 个工具`);
    renderMcpServers();
  } else {
    addAiMessage('assistant', `MCP ${name} 连接失败: ${result.error}`);
  }
}

function renderMcpServers() {
  const listEl = document.getElementById('mcp-server-list');
  const toolEl = document.getElementById('mcp-tool-list');
  listEl.innerHTML = '';
  toolEl.innerHTML = '';

  if (mcpServers.size === 0) {
    listEl.innerHTML = '<div class="list-item"><span>暂无 MCP 服务器</span></div>';
    toolEl.innerHTML = '<div class="list-item"><span>连接后显示工具列表</span></div>';
    return;
  }

  mcpServers.forEach((server, name) => {
    const item = document.createElement('div');
    item.className = 'list-item';
    item.innerHTML = `<span>${escapeHtml(name)}: ${escapeHtml(server.command)}</span>
      <div>
        <button class="secondary" onclick="discoverMcpTools('${escapeJsString(name)}')">发现工具</button>
        <button class="secondary" onclick="removeMcpServer('${escapeJsString(name)}')">删除</button>
      </div>`;
    listEl.appendChild(item);

    (server.tools || []).forEach(tool => {
      const t = document.createElement('div');
      t.className = 'list-item';
      t.innerHTML = `<span>${escapeHtml(tool.name)}</span><button class="secondary">调用</button>`;
      toolEl.appendChild(t);
    });
  });
}

// ============================================================
// Y·NEX自动化工作流
// ============================================================

function openAutomationPanel() {
  document.getElementById('automation-panel').classList.add('active');
  renderAutomationLog();
}

async function runAutomationTask() {
  const input = document.getElementById('automation-input');
  const task = input.value.trim();
  if (!task) return;
  input.value = '';

  const record = { id: Date.now(), task, status: 'running', result: '' };
  automationHistory.unshift(record);
  renderAutomationLog();

  try {
    const status = await window.ynex.ynex.status();
    const useLocal = status.online;

    let plan = '';
    await ynexClient.chatStream(
      `你是Y·NEX自动化 Agent，可以直接调用系统工具和文件系统。用户任务: ${task}\n工作区: ${workspacePath || '未打开'}\n请把任务拆成步骤并输出可执行计划。`,
      (chunk) => { plan += chunk; record.result += chunk; renderAutomationLog(); },
      { useLocal }
    );

    // 简单执行：如果任务包含运行测试，则在终端执行
    if (task.includes('测试') || task.includes('test')) {
      await window.ynex.terminal.write(terminalId, 'npm test\r\n');
    }

    record.status = 'completed';
  } catch (e) {
    record.status = 'failed';
    record.result += '\n错误: ' + e.message;
  }
  renderAutomationLog();
}

function renderAutomationLog() {
  const el = document.getElementById('automation-log');
  el.innerHTML = '';
  if (automationHistory.length === 0) {
    el.innerHTML = '<div class="list-item"><span>暂无工作流记录</span></div>';
    return;
  }
  automationHistory.forEach(r => {
    const item = document.createElement('div');
    item.className = 'list-item';
    item.innerHTML = `<span>[${r.status}] ${escapeHtml(r.task)}</span>`;
    el.appendChild(item);
    if (r.result) {
      const pre = document.createElement('pre');
      pre.style.cssText = 'white-space:pre-wrap;word-break:break-word;background:var(--bg);padding:8px;border-radius:4px;margin-top:6px;font-size:11px';
      pre.textContent = r.result;
      item.appendChild(pre);
    }
  });
}

// ============================================================
// Y·NEX 系统控制
// ============================================================

async function ynexControl(action, params = {}) {
  try {
    const result = await window.ynex.system.controlDesktop(action, params);
    if (result.ok) {
      appendTerminalOutput(`[Y·NEX] 执行成功: ${action}\r\n`);
    } else {
      appendTerminalOutput(`[Y·NEX] 执行失败: ${result.error}\r\n`);
    }
    return result;
  } catch (e) {
    appendTerminalOutput(`[Y·NEX] 错误: ${e.message}\r\n`);
    return { ok: false, error: e.message };
  }
}

async function ynexExecute(command) {
  try {
    appendTerminalOutput(`[Y·NEX] 执行命令: ${command}\r\n`);
    const result = await window.ynex.system.execute(command);
    if (result.ok) {
      appendTerminalOutput(result.result.stdout || result.result.stderr || '(无输出)\r\n');
    } else {
      appendTerminalOutput(`命令失败: ${result.error}\r\n`);
    }
    return result;
  } catch (e) {
    appendTerminalOutput(`命令错误: ${e.message}\r\n`);
    return { ok: false, error: e.message };
  }
}

// ============================================================
// 工具函数
// ============================================================

// ============================================================
// M3: 命令面板 (Ctrl+Shift+P / Ctrl+P)
// ============================================================

const COMMANDS = [
  // 核心
  { id: 'open', label: '打开工作区', kbd: 'Ctrl+O', action: openWorkspace },
  { id: 'save', label: '保存文件', kbd: 'Ctrl+S', action: saveCurrentFile },
  { id: 'closeFile', label: '关闭文件', kbd: 'Ctrl+W', action: () => { if (currentFile) closeTab({stopPropagation:()=>{}}, currentFile); } },
  // 导航
  { id: 'goToDef', label: '跳转到定义', kbd: 'F12', action: lspGoToDefinition },
  { id: 'diagnostics', label: '查看诊断', kbd: 'F8', action: lspGetDiagnostics },
  { id: 'search', label: '在项目中搜索', kbd: 'Ctrl+Shift+F', action: toggleSearchPanel },
  { id: 'searchSemantic', label: '语义代码搜索', kbd: '', action: () => semanticSearch(prompt('搜索关键词:')) },
  // 编辑器
  { id: 'split', label: '分屏编辑', kbd: 'Ctrl+\\', action: toggleSplitEditor },
  { id: 'newFile', label: '新建文件', kbd: 'Ctrl+N', action: createNewFile },
  { id: 'newFolder', label: '新建文件夹', kbd: '', action: createNewFolder },
  // AI
  { id: 'ai', label: 'AI 助手', kbd: 'Ctrl+I', action: toggleAiPanel },
  { id: 'aiExplain', label: 'AI 解释代码', kbd: '', action: aiExplainCode },
  { id: 'aiRefactor', label: 'AI 重构', kbd: '', action: aiRefactorCode },
  { id: 'aiComplete', label: 'AI 内联补全', kbd: '', action: aiCompleteCode },
  // Git
  { id: 'git', label: 'Git 面板', kbd: 'Ctrl+Shift+G', action: toggleGitPanel },
  { id: 'gitCommit', label: 'Git 提交', kbd: '', action: gitCommit },
  { id: 'gitDiff', label: 'Git Diff', kbd: '', action: showDiffPanel },
  // 调试 & 测试
  { id: 'debug', label: '调试器', kbd: 'Ctrl+Shift+D', action: openDebugPanel },
  { id: 'runTests', label: '运行测试', kbd: '', action: runProjectTests },
  // 工具
  { id: 'terminal', label: '终端', kbd: 'Ctrl+`', action: toggleTerminal },
  { id: 'mcp', label: 'MCP 工具生态', kbd: '', action: openMcpPanel },
  { id: 'automation', label: 'Y·NEX自动化', kbd: '', action: openAutomationPanel },
  { id: 'tasks', label: '任务运行器', kbd: '', action: openTasksPanel },
  { id: 'ssh', label: 'SSH 远程开发', kbd: '', action: openSshPanel },
  { id: 'db', label: '数据库浏览器', kbd: '', action: openDbPanel },
  { id: 'api', label: 'API 测试客户端', kbd: '', action: openApiTestPanel },
  // 高级工具
  { id: 'review', label: 'AI 代码审查', kbd: '', action: openCodeReviewPanel },
  { id: 'refactor', label: 'AI 重构面板', kbd: '', action: openRefactorPanel },
  { id: 'docker', label: 'Docker 容器管理', kbd: '', action: openDockerPanel },
  { id: 'jupyter', label: 'Jupyter 笔记本', kbd: '', action: openJupyterPanel },
  { id: 'cicd', label: 'CI/CD 流水线', kbd: '', action: openCicdPanel },
  { id: 'mermaid', label: 'Mermaid 图表', kbd: '', action: openMermaidPanel },
  { id: 'preview', label: 'Live Preview', kbd: '', action: openLivePreviewPanel },
  { id: 'macro', label: '键盘宏录制', kbd: '', action: openMacroPanel },
  { id: 'voice', label: '语音转代码', kbd: '', action: voiceToCode },
  { id: 'extensions', label: '扩展市场', kbd: '', action: openExtensionsPanel },
  { id: 'plugin', label: '插件 SDK', kbd: '', action: openPluginSdkPanel },
  // 设置
  { id: 'settings', label: '设置', kbd: 'Ctrl+,', action: openSettingsPanel },
  { id: 'theme', label: '切换主题', kbd: 'Ctrl+K Ctrl+T', action: () => {
    const themes = ['vs-dark', 'vs', 'hc-black', 'jetbrains'];
    const idx = themes.indexOf(localStorage.getItem('ynex_theme') || 'vs-dark');
    switchTheme(themes[(idx + 1) % themes.length]);
  }},
  { id: 'autoSave', label: '切换自动保存', kbd: '', action: toggleAutoSave },
  // Y·NEX
  { id: 'agent', label: '项目级 Agent 重构', kbd: '', action: runProjectAgent },
  { id: 'ynex', label: 'Y·NEX 系统控制', kbd: '', action: () => window.location.href='index.html' },
];

// ============================================================
// 全局快捷键系统
// ============================================================

const KEYBOARD_SHORTCUTS = {
  'Ctrl+O': () => openWorkspace(),
  'Ctrl+S': (e) => { e.preventDefault(); saveCurrentFile(); },
  'Ctrl+W': (e) => { e.preventDefault(); if (currentFile) closeTab({stopPropagation:()=>{}}, currentFile); },
  'Ctrl+N': (e) => { e.preventDefault(); createNewFile(); },
  'Ctrl+Shift+F': (e) => { e.preventDefault(); toggleSearchPanel(); },
  'Ctrl+Shift+G': (e) => { e.preventDefault(); toggleGitPanel(); },
  'Ctrl+Shift+P': (e) => { e.preventDefault(); toggleCommandPalette(); },
  'Ctrl+Shift+D': (e) => { e.preventDefault(); openDebugPanel(); },
  'Ctrl+I': (e) => { e.preventDefault(); toggleAiPanel(); },
  'Ctrl+,': (e) => { e.preventDefault(); openSettingsPanel(); },
  'Ctrl+\\': (e) => { e.preventDefault(); toggleSplitEditor(); },
  'Ctrl+K Ctrl+T': (e) => {
    e.preventDefault();
    const themes = ['vs-dark', 'vs', 'hc-black', 'jetbrains'];
    const idx = themes.indexOf(localStorage.getItem('ynex_theme') || 'vs-dark');
    switchTheme(themes[(idx + 1) % themes.length]);
  },
  'Ctrl+B': (e) => { e.preventDefault(); toggleFileExplorer(); },
  'F12': (e) => { e.preventDefault(); lspGoToDefinition(); },
  'F8': (e) => { e.preventDefault(); lspGetDiagnostics(); },
  'Escape': () => { closeCommandPalette(); closeAllOverlays(); },
};

document.addEventListener('keydown', (e) => {
  // 不在输入框内才触发快捷键
  const tag = document.activeElement.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') {
    // 例外：Ctrl+Shift+P 在编辑器内仍可用
    if (!(e.ctrlKey && e.shiftKey && e.key === 'P')) return;
  }

  const key = [
    e.ctrlKey ? 'Ctrl' : '',
    e.shiftKey ? 'Shift' : '',
    e.altKey ? 'Alt' : '',
    e.metaKey ? 'Meta' : '',
    e.key === 'Control' || e.key === 'Shift' || e.key === 'Alt' || e.key === 'Meta' ? '' : e.key,
  ].filter(Boolean).join('+');

  const handler = KEYBOARD_SHORTCUTS[key];
  if (handler) {
    handler(e);
    return;
  }

  // Ctrl+` 特殊处理
  if (e.ctrlKey && e.key === '`') {
    e.preventDefault();
    toggleTerminal();
  }
});

let paletteIndex = 0;
let paletteResults = [];

function openCommandPalette() {
  const el = document.getElementById('command-palette');
  el.classList.add('active');
  const input = document.getElementById('palette-input');
  input.value = '';
  input.focus();
  paletteIndex = 0;
  filterPalette('');
}

function closeCommandPalette() {
  document.getElementById('command-palette').classList.remove('active');
}

function filterPalette(query) {
  const q = query.toLowerCase();
  // 搜索命令 + 已打开文件
  paletteResults = [];
  if (q) {
    paletteResults = COMMANDS.filter(c => c.label.toLowerCase().includes(q) || c.id.toLowerCase().includes(q));
    // 添加已打开文件
    for (const [fp] of openFiles) {
      const name = fp.split('\\').pop().split('/').pop();
      if (name.toLowerCase().includes(q) || fp.toLowerCase().includes(q)) {
        paletteResults.push({ id: 'file:' + fp, label: '📄 ' + name, filePath: fp, action: () => openFile(fp) });
      }
    }
  } else {
    paletteResults = COMMANDS.slice();
  }
  paletteIndex = Math.min(paletteIndex, paletteResults.length - 1);
  renderPalette();
}

function renderPalette() {
  const el = document.getElementById('palette-results');
  el.innerHTML = paletteResults.map((c, i) => {
    const cls = i === paletteIndex ? 'palette-item selected' : 'palette-item';
    return `<div class="${cls}" data-idx="${i}" onmousedown="executePalette(${i})">${escapeHtml(c.label)}${c.kbd ? '<span class="kbd">'+c.kbd+'</span>' : ''}</div>`;
  }).join('');
}

function executePalette(idx) {
  const cmd = paletteResults[idx];
  closeCommandPalette();
  if (cmd && cmd.action) cmd.action();
}

function handlePaletteKey(event) {
  if (event.key === 'Escape') { closeCommandPalette(); return; }
  if (event.key === 'ArrowDown') { paletteIndex = Math.min(paletteIndex + 1, paletteResults.length - 1); renderPalette(); event.preventDefault(); return; }
  if (event.key === 'ArrowUp') { paletteIndex = Math.max(paletteIndex - 1, 0); renderPalette(); event.preventDefault(); return; }
  if (event.key === 'Enter') { executePalette(paletteIndex); return; }
  filterPalette(event.target.value);
}

// 绑定 Ctrl+Shift+P 和 Ctrl+P
document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'P') {
    e.preventDefault();
    openCommandPalette();
  }
  if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key === 'p') {
    e.preventDefault();
    openCommandPalette();
  }
  if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key === 'w') {
    e.preventDefault();
    if (activeFile) closeTab({ stopPropagation: () => {} }, activeFile);
  }
});

// 绑定命令面板输入事件
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => {
    const paletteInput = document.getElementById('palette-input');
    if (paletteInput) {
      paletteInput.addEventListener('keydown', handlePaletteKey);
      paletteInput.addEventListener('input', (e) => filterPalette(e.target.value));
    }
    document.getElementById('command-palette').addEventListener('click', (e) => {
      if (e.target.id === 'command-palette') closeCommandPalette();
    });
  }, 100);
});

// ============================================================
// M3: 全项目代码搜索 (ripgrep)
// ============================================================

function toggleSearchPanel() {
  const panel = document.getElementById('search-panel');
  panel.classList.toggle('active');
  if (panel.classList.contains('active')) document.getElementById('search-input').focus();
}

function closeSearchPanel() {
  document.getElementById('search-panel').classList.remove('active');
}

async function searchInProject() {
  if (!workspacePath) return alert('请先打开工作区');
  const query = document.getElementById('search-input').value.trim();
  if (!query) return;

  const resultsEl = document.getElementById('search-results');
  resultsEl.innerHTML = '<div class="tree-empty">搜索中...</div>';

  try {
    const isWin = navigator.platform.toLowerCase().includes('win');
    let result;
    if (isWin) {
      result = await window.ynex.system.execute({
        program: 'powershell',
        args: ['-Command', `Get-ChildItem -Recurse -File -Exclude node_modules,.git,__pycache__,*.exe,*.dll,*.zip | Select-String -Pattern '${query.replace(/'/g, "''")}' -SimpleMatch | Select-Object -First 50 Filename,LineNumber,Line`],
        cwd: workspacePath
      });
    } else {
      result = await window.ynex.system.execute({
        program: 'grep',
        args: ['-R', '-n', '-I', '--exclude-dir=node_modules', '--exclude-dir=.git', '--exclude-dir=__pycache__', '-m', '50', query, '.'],
        cwd: workspacePath
      });
    }
    if (!result.ok || !result.result.stdout) {
      resultsEl.innerHTML = '<div class="tree-empty">无结果</div>';
      return;
    }
    const lines = result.result.stdout.trim().split('\n').filter(Boolean);
    resultsEl.innerHTML = lines.map(line => {
      const match = line.match(/^(.+?):(\d+):(.+)$/);
      if (!match) return '';
      const file = match[1];
      const lnum = match[2];
      const content = match[3];
      const highlighted = escapeHtml(content).replace(new RegExp(escapeRegex(query), 'gi'), '<b>$&</b>');
      return `<div class="search-result" onclick="openFileAt('${escapeJsString(workspacePath + '\\\\' + file)}', ${lnum})">
        <div class="file">${escapeHtml(file)}:${lnum}</div>
        <div class="match">${highlighted}</div>
      </div>`;
    }).join('');
  } catch (e) {
    resultsEl.innerHTML = `<div class="tree-empty">搜索失败: ${escapeHtml(e.message)}</div>`;
  }
}

async function openFileAt(filePath, line) {
  await openFile(filePath);
  if (activeFile === filePath) {
    const ed = editors.get(filePath);
    if (ed) {
      ed.editor.revealLineInCenter(line);
      ed.editor.setPosition({ lineNumber: line, column: 1 });
    }
  }
}

function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// ============================================================
// M3: 分屏编辑器
// ============================================================

let splitMode = false;
let splitFile = null;
let splitEditor = null;

function toggleSplitEditor() {
  if (!activeFile) return alert('请先打开文件');
  if (!splitMode) {
    splitMode = true;
    splitFile = activeFile;
    renderSplitEditor();
  } else {
    splitMode = false;
    splitFile = null;
    if (splitEditor) { splitEditor.dispose(); splitEditor = null; }
    renderSplitEditor();
  }
}

function renderSplitEditor() {
  const container = document.getElementById('editor-container');
  if (splitMode) {
    container.innerHTML = `
      <div class="editor-split" id="editor-split">
        <div class="split-pane" id="split-pane-left"></div>
        <div class="split-divider" id="split-divider"></div>
        <div class="split-pane" id="split-pane-right"></div>
      </div>`;
    // 渲染左侧
    if (activeFile) {
      const ed = editors.get(activeFile);
      if (ed) {
        const leftHost = document.getElementById('split-pane-left');
        const newEd = monaco.editor.create(leftHost, {
          model: ed.model,
          theme: 'vs-dark',
          automaticLayout: true,
          minimap: { enabled: false },
          fontSize: 13,
          fontFamily: 'Cascadia Code, Fira Code, Consolas, monospace',
          readOnly: false,
        });
        ed.editor = newEd;
        editors.set(activeFile, { ...ed, editor: newEd });
      }
    }
    // 渲染右侧
    if (splitFile && openFiles.has(splitFile)) {
      const file = openFiles.get(splitFile);
      const rightHost = document.getElementById('split-pane-right');
      const model = monaco.editor.createModel(file.content, getLanguage(splitFile), monaco.Uri.file(splitFile));
      splitEditor = monaco.editor.create(rightHost, {
        model,
        theme: 'vs-dark',
        automaticLayout: true,
        minimap: { enabled: false },
        fontSize: 13,
        fontFamily: 'Cascadia Code, Fira Code, Consolas, monospace',
        readOnly: false,
      });
      splitEditor.onDidChangeModelContent(() => {
        const f = openFiles.get(splitFile);
        if (f) { f.content = splitEditor.getValue(); f.modified = true; }
      });
    }
  } else {
    // 恢复单屏模式 — 重新渲染所有编辑器
    container.innerHTML = '';
    for (const [fp, file] of openFiles) {
      createEditorPane(fp, file.content);
    }
    if (activeFile) switchToTab(activeFile);
  }
}

// ============================================================
// M3: Git 集成
// ============================================================

async function openGitPanel() {
  document.getElementById('git-panel').classList.add('active');
  await gitRefresh();
}

async function gitRefresh() {
  if (!workspacePath) return;
  try {
    const isRepo = await window.ynex.git.isRepo(workspacePath);
    if (!isRepo.ok || !isRepo.isRepo) {
      document.getElementById('git-changes').innerHTML = '<div class="list-item">不是 Git 仓库</div>';
      return;
    }
    const status = await window.ynex.git.status(workspacePath);
    const log = await window.ynex.git.log(workspacePath, 20);

    // 渲染变更
    const changesEl = document.getElementById('git-changes');
    const lines = status.output.trim().split('\n').filter(Boolean);
    if (lines.length === 0) {
      changesEl.innerHTML = '<div class="list-item"><span>无变更</span></div>';
    } else {
      changesEl.innerHTML = lines.map(l => {
        const code = l.substring(0, 2).trim();
        const file = l.substring(2).trim();
        return `<div class="git-file-item" onclick="gitStageFile('${escapeJsString(file)}')" ondblclick="openFileAt('${escapeJsString(workspacePath + '\\\\' + file)}',1)">
          <span class="git-status ${escapeHtml(code)}"></span>
          <span>${escapeHtml(file)}</span>
          <span style="margin-left:auto;color:var(--text2)">${escapeHtml(code)}</span>
        </div>`;
      }).join('');
    }

    // 渲染日志
    const logEl = document.getElementById('git-log');
    logEl.innerHTML = log.logs.map(l => `<div class="list-item" style="font-size:11px;font-family:var(--mono)">${escapeHtml(l)}</div>`).join('');
  } catch (e) {
    document.getElementById('git-changes').innerHTML = `<div class="list-item">错误: ${escapeHtml(e.message)}</div>`;
  }
}

async function gitStageAll() {
  const r = await window.ynex.git.stage(workspacePath);
  appendTerminalOutput(`[Git] ${r.ok ? 'Stage 完成' : '错误: ' + r.error}\r\n`);
  await gitRefresh();
}

async function gitStageFile(file) {
  const r = await window.ynex.git.stage(workspacePath, [file]);
  appendTerminalOutput(`[Git] Stage ${file}: ${r.ok ? 'ok' : r.error}\r\n`);
  await gitRefresh();
}

async function gitCommit() {
  const message = prompt('输入提交信息:');
  if (!message) return;
  const r = await window.ynex.git.commit(workspacePath, message);
  appendTerminalOutput(`[Git] Commit: ${r.ok ? '完成' : '错误: ' + r.error}\r\n${r.output}\r\n`);
  await gitRefresh();
}

async function gitPush() {
  const r = await window.ynex.git.push(workspacePath);
  appendTerminalOutput(`[Git] Push: ${r.ok ? '完成' : '错误: ' + r.error}\r\n${r.output}\r\n`);
}

async function gitPull() {
  const r = await window.ynex.git.pull(workspacePath);
  appendTerminalOutput(`[Git] Pull: ${r.ok ? '完成' : '错误: ' + r.error}\r\n${r.output}\r\n`);
}

async function gitStash() {
  const r = await window.ynex.git.stash(workspacePath);
  appendTerminalOutput(`[Git] Stash: ${r.ok ? '完成' : '错误: ' + r.error}\r\n`);
  await gitRefresh();
}

async function gitBranches() {
  const r = await window.ynex.git.branches(workspacePath);
  if (r.ok) {
    const msg = ['当前分支: ' + r.current, '所有分支:', ...r.branches.map(b => b === r.current ? `* ${b}` : `  ${b}`)].join('\r\n');
    addAiMessage('assistant', '<pre>' + escapeHtml(msg) + '</pre>');
  }
}

// ============================================================
// M3: 调试器
// ============================================================

let debugSessionId = null;

function openDebugPanel() {
  document.getElementById('debug-panel').classList.add('active');
}

async function debugStartPython() {
  if (!activeFile) return alert('请先打开 Python 文件');
  const scriptPath = activeFile;
  const breakpoints = [{ file: scriptPath, line: 1 }];
  try {
    const r = await window.ynex.debug.startPython(scriptPath, workspacePath, breakpoints);
    if (r.ok) {
      debugSessionId = r.id;
      document.getElementById('debug-output').textContent = `调试会话已启动: ${r.id}\n`;
      pollDebugOutput();
    }
  } catch (e) {
    document.getElementById('debug-output').textContent = '启动失败: ' + e.message;
  }
}

async function debugStartNode() {
  if (!activeFile) return alert('请先打开 JS 文件');
  const r = await window.ynex.debug.startNode(activeFile, workspacePath, [{ file: activeFile, line: 1 }]);
  if (r.ok) {
    debugSessionId = r.id;
    document.getElementById('debug-output').textContent = `调试会话已启动: ${r.id}\n`;
    pollDebugOutput();
  }
}

function pollDebugOutput() {
  if (!debugSessionId) return;
  const interval = setInterval(async () => {
    const r = await window.ynex.debug.getOutput(debugSessionId);
    if (r.ok) {
      document.getElementById('debug-output').textContent = r.output;
      if (r.state === 'stopped') { clearInterval(interval); debugSessionId = null; }
    }
  }, 500);
}

async function debugStop() {
  if (!debugSessionId) return;
  await window.ynex.debug.stop(debugSessionId);
  debugSessionId = null;
  document.getElementById('debug-output').textContent += '\n调试已停止';
}

// ============================================================
// M3: 多模型切换
// ============================================================

function switchModel(model) {
  localStorage.setItem('ynex_model', model);
  ynexClient.model = model;
  addAiMessage('assistant', '已切换到: ' + model);
  if (model === 'local') {
    window.ynex.ynex.start();
  }
}

// 初始化模型
(function() {
  const saved = localStorage.getItem('ynex_model') || 'auto';
  ynexClient.model = saved;
  const sel = document.getElementById('model-switcher');
  if (sel) sel.value = saved;
})();

// ============================================================
// M3: 自动上下文 + 检查点
// ============================================================

const checkpoints = [];

async function createCheckpoint(label) {
  if (!workspacePath) return;
  const stamp = Date.now();
  const files = [];
  for (const [fp] of openFiles) {
    const content = getEditorContent(fp);
    files.push({ path: fp, content });
  }
  checkpoints.push({ id: stamp, label: label || `检查点 ${checkpoints.length + 1}`, files, timestamp: new Date().toISOString() });
  appendTerminalOutput(`[检查点] 已创建: ${label || stamp}\r\n`);
  return stamp;
}

async function restoreCheckpoint(id) {
  const cp = checkpoints.find(c => c.id === id);
  if (!cp) return;
  for (const file of cp.files) {
    await window.ynex.fs.writeFile(file.path, file.content);
    const existing = openFiles.get(file.path);
    if (existing) { existing.content = file.content; existing.modified = false; }
  }
  // 刷新编辑器
  if (activeFile) switchToTab(activeFile);
  appendTerminalOutput(`[检查点] 已恢复: ${cp.label}\r\n`);
}

function listCheckpoints() {
  if (checkpoints.length === 0) {
    addAiMessage('assistant', '暂无检查点');
    return;
  }
  const html = checkpoints.map(cp => 
    `<div class="list-item">
      <span>${escapeHtml(cp.label)} - ${cp.timestamp}</span>
      <button class="secondary" onclick="restoreCheckpoint(${cp.id})">恢复</button>
    </div>`
  ).join('');
  addAiMessage('assistant', `<b>检查点列表:</b><br>${html}`);
}

// 自动上下文：在 AI 对话中自动包含相关文件
async function getAutoContext(task) {
  if (!workspacePath) return '';
  const contextFiles = [];
  // 收集当前打开的文件
  for (const [fp] of openFiles) {
    const content = getEditorContent(fp).substring(0, 2000);
    contextFiles.push(`\n文件: ${fp}\n\`\`\`\n${content}\n\`\`\``);
  }
  return contextFiles.join('\n');
}

// 覆写 sendAiMessage 以支持自动上下文
const originalSendAiMessage = sendAiMessage;
sendAiMessage = async function() {
  const input = document.getElementById('ai-input');
  const text = input.value.trim();
  if (!text) return;

  input.value = '';
  addAiMessage('user', escapeHtml(text));
  const replyEl = addAiMessage('assistant', '思考中...');

  try {
    // 自动收集上下文
    const ctx = await getAutoContext(text);
    const fullPrompt = ctx ? `上下文:\n${ctx}\n\n用户问题: ${text}` : text;

    const status = await window.ynex.ynex.status();
    const useLocal = ynexClient.model === 'local' || (status.online && ynexClient.model === 'auto');

    let reply = '';
    await ynexClient.chatStream(fullPrompt, (chunk) => {
      reply += chunk;
      replyEl.innerHTML = formatAiReply(reply);
    }, { useLocal, useMock: false });
  } catch (e) {
    replyEl.textContent = '错误: ' + e.message;
  }
};

// ============================================================
// M3: 任务运行器
// ============================================================

function openTasksPanel() {
  document.getElementById('tasks-panel').classList.add('active');
  loadTasks();
}

async function loadTasks() {
  if (!workspacePath) return;
  const tasksEl = document.getElementById('tasks-list');
  tasksEl.innerHTML = '<div class="list-item">检测中...</div>';

  const tasks = [];
  // 检测 npm scripts
  try {
    const pkgPath = workspacePath + '\\package.json';
    const r = await window.ynex.fs.readFile(pkgPath);
    if (r.ok) {
      const pkg = JSON.parse(r.content);
      if (pkg.scripts) {
        for (const [name] of Object.entries(pkg.scripts)) {
          tasks.push({ name: 'npm ' + name, cmd: 'npm run ' + name });
        }
      }
    }
  } catch (e) {}

  // 检测 common tasks
  tasks.push({ name: 'Python 测试', cmd: 'python -m pytest --tb=short' });
  tasks.push({ name: 'Python Lint', cmd: 'python -m flake8 .' });
  tasks.push({ name: 'TypeScript 编译', cmd: 'npx tsc --noEmit' });

  tasksEl.innerHTML = tasks.map(t =>
    `<div class="list-item">
      <span>${escapeHtml(t.name)}</span>
      <button class="secondary" onclick="runTask('${escapeJsString(t.cmd)}')">运行</button>
    </div>`
  ).join('');
}

async function runTask(cmd) {
  const outputEl = document.getElementById('tasks-output');
  outputEl.textContent = '运行中...\n';
  await window.ynex.terminal.write(terminalId, cmd + '\r\n');
}

// ============================================================
// M3: 代码片段
// ============================================================

const SNIPPETS = {
  'py:main': 'def main():\n    pass\n\nif __name__ == "__main__":\n    main()',
  'py:class': 'class ${1:ClassName}:\n    def __init__(self):\n        ${0:pass}',
  'js:func': 'function ${1:name}(${2:params}) {\n    ${0:// body}\n}',
  'js:arrow': 'const ${1:name} = (${2:params}) => {\n    ${0:// body}\n};',
  'html:base': '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n    <meta charset="UTF-8">\n    <title>${1:Title}</title>\n</head>\n<body>\n    ${0}\n</body>\n</html>',
};

function getSnippet(filePath) {
  const ext = filePath.split('.').pop().toLowerCase();
  const name = filePath.split('\\').pop().split('/').pop();
  if (name === 'main.py') return SNIPPETS['py:main'];
  return null;
}

function escapeHtml(text) {
  if (text == null) return '';
  return String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
}

function escapeJsString(str) {
  return str.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"');
}

function escapeSelector(str) {
  return str.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
}

// ============================================================
// M3: SSH 远程开发
// ============================================================

let sshConnectionId = null;

function openSshPanel() {
  document.getElementById('ssh-panel').classList.add('active');
}

async function sshConnect() {
  const host = document.getElementById('ssh-host').value.trim();
  const port = parseInt(document.getElementById('ssh-port').value) || 22;
  const username = document.getElementById('ssh-user').value.trim();
  if (!host) return alert('请输入主机地址');

  const el = document.getElementById('ssh-connections');
  el.innerHTML = '<div class="list-item">连接中...</div>';

  try {
    const r = await window.ynex.ssh.connect(host, port, username);
    if (r.ok) {
      sshConnectionId = r.id;
      el.innerHTML = `<div class="list-item"><span>已连接: ${username}@${host}:${port}</span><button class="secondary" onclick="sshDisconnect()">断开</button></div>`;
      sshListDir('/');
    } else {
      el.innerHTML = `<div class="list-item">连接失败: ${r.error}</div>`;
    }
  } catch (e) {
    el.innerHTML = `<div class="list-item">错误: ${e.message}</div>`;
  }
}

async function sshDisconnect() {
  if (!sshConnectionId) return;
  await window.ynex.ssh.disconnect(sshConnectionId);
  sshConnectionId = null;
  document.getElementById('ssh-connections').innerHTML = '<div class="list-item">已断开</div>';
  document.getElementById('ssh-file-tree').innerHTML = '';
}

async function sshListDir(remotePath) {
  if (!sshConnectionId) return;
  const el = document.getElementById('ssh-file-tree');
  el.innerHTML = '<div class="list-item">加载中...</div>';

  const r = await window.ynex.ssh.listDir(sshConnectionId, remotePath);
  if (!r.ok) { el.innerHTML = `<div class="list-item">错误: ${r.error}</div>`; return; }

  const parent = remotePath.split('/').slice(0, -1).join('/') || '/';
  el.innerHTML = `<div class="list-item" onclick="sshListDir('${parent}')">📂 ..</div>` +
    r.entries.map(e => 
      `<div class="list-item" ondblclick="${e.isDirectory ? `sshListDir('${e.path}')` : `sshReadFile('${e.path}')`}" 
        onclick="${e.isDirectory ? `sshListDir('${e.path}')` : `sshReadFile('${e.path}')`}">
        <span>${e.isDirectory ? '📁' : '📄'} ${escapeHtml(e.name)}</span>
        <span style="margin-left:auto;color:var(--text2);font-size:11px">${e.isFile ? formatSize(e.size) : ''}</span>
      </div>`
    ).join('');
}

async function sshReadFile(remotePath) {
  if (!sshConnectionId) return;
  const r = await window.ynex.ssh.readFile(sshConnectionId, remotePath);
  if (r.ok) {
    // 写入临时文件并打开
    const tmpPath = workspacePath + '\\_remote_' + remotePath.replace(/\//g, '_');
    await window.ynex.fs.writeFile(tmpPath, r.content);
    openFile(tmpPath);
  } else {
    appendTerminalOutput(`[SSH] 读取失败: ${r.error}\r\n`);
  }
}

async function sshExec() {
  if (!sshConnectionId) return alert('请先连接');
  const cmd = document.getElementById('ssh-command').value.trim();
  if (!cmd) return;
  const el = document.getElementById('ssh-output');
  el.textContent = '执行中...\n';
  const r = await window.ynex.ssh.exec(sshConnectionId, cmd);
  el.textContent = (r.stdout || '') + (r.stderr ? '\n[stderr]\n' + r.stderr : '') + `\n退出码: ${r.code}`;
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + 'B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB';
  return (bytes / (1024 * 1024)).toFixed(1) + 'MB';
}

// ============================================================
// M3: 数据库浏览器
// ============================================================

let dbConnection = null;

function openDbPanel() {
  document.getElementById('db-panel').classList.add('active');
}

async function dbConnect() {
  const dbPath = document.getElementById('db-path').value.trim();
  if (!dbPath) return alert('请输入数据库路径');

  try {
    const r = await window.ynex.fs.readFile(dbPath);
    if (!r.ok) { alert('无法读取数据库文件'); return; }
    dbConnection = dbPath;
    document.getElementById('db-tables').innerHTML = '<div class="list-item">已连接</div>';
    await dbLoadTables();
  } catch (e) {
    alert('连接失败: ' + e.message);
  }
}

async function dbLoadTables() {
  if (!dbConnection) return;
  const r = await window.ynex.system.execute({
    program: 'python',
    args: ['-c', "import sys, sqlite3; conn=sqlite3.connect(sys.argv[1]); print('\\n'.join(row[0] for row in conn.execute('SELECT name FROM sqlite_master WHERE type=\\'table\\'').fetchall()))", dbConnection]
  });
  if (r.ok && r.result.stdout) {
    const tables = r.result.stdout.trim().split('\n').filter(Boolean);
    document.getElementById('db-tables').innerHTML = tables.map(t =>
      `<div class="list-item" onclick="dbShowTable('${escapeJsString(t)}')">
        <span>📋 ${escapeHtml(t)}</span>
        <button class="secondary" onclick="event.stopPropagation(); dbQuery('SELECT * FROM ${escapeJsString(t)} LIMIT 100')">查询</button>
      </div>`
    ).join('');
  }
}

async function dbQuery(presetSql) {
  const sql = presetSql || document.getElementById('db-query').value.trim();
  if (!sql || !dbConnection) return;
  const el = document.getElementById('db-results');
  el.textContent = '查询中...';

  const r = await window.ynex.system.execute({
    program: 'python',
    args: ['-c', "import sys, sqlite3, json; conn=sqlite3.connect(sys.argv[1]); cur=conn.execute(sys.argv[2]); rows=cur.fetchall(); cols=[d[0] for d in cur.description] if cur.description else []; print(json.dumps({'cols':cols,'rows':[list(r) for r in rows[:200]]}, ensure_ascii=False, default=str))", dbConnection, sql]
  });
  if (r.ok && r.result.stdout) {
    try {
      const data = JSON.parse(r.result.stdout);
      let html = '<table style="width:100%;border-collapse:collapse;font-size:11px">';
      if (data.cols.length > 0) {
        html += '<tr>' + data.cols.map(c => `<th style="border:1px solid var(--border);padding:4px 8px;background:var(--surface2);text-align:left">${escapeHtml(c)}</th>`).join('') + '</tr>';
        html += data.rows.map(row => '<tr>' + row.map(v => `<td style="border:1px solid var(--border);padding:4px 8px">${escapeHtml(String(v ?? ''))}</td>`).join('') + '</tr>').join('');
      }
      html += '</table>';
      el.innerHTML = html + `<div style="margin-top:8px;color:var(--text2)">${data.rows.length} 行</div>`;
    } catch (e) {
      el.textContent = r.result.stdout;
    }
  } else {
    el.textContent = '查询失败: ' + (r.result?.stderr || r.error || '');
  }
}

function dbShowTable(tableName) {
  document.getElementById('db-query').value = `SELECT * FROM ${tableName} LIMIT 100`;
  dbQuery();
}

// ============================================================
// M3: API 测试客户端
// ============================================================

function openApiTestPanel() {
  document.getElementById('api-panel').classList.add('active');
}

async function apiSend() {
  const method = document.getElementById('api-method').value;
  const url = document.getElementById('api-url').value.trim();
  if (!url) return alert('请输入 URL');

  let headers = {};
  try {
    const h = document.getElementById('api-headers').value.trim();
    if (h) headers = JSON.parse(h);
  } catch (e) { alert('Headers 格式错误'); return; }

  let body = null;
  if (method !== 'GET') {
    const b = document.getElementById('api-body').value.trim();
    if (b) {
      try { body = JSON.parse(b); } catch (e) { body = b; }
    }
  }

  const el = document.getElementById('api-response');
  el.textContent = '请求中...';

  try {
    const fetchOptions = { method, headers };
    if (body) fetchOptions.body = typeof body === 'string' ? body : JSON.stringify(body);
    const start = Date.now();
    const res = await fetch(url, fetchOptions);
    const elapsed = Date.now() - start;
    const resBody = await res.text();
    let formatted = resBody;
    try { formatted = JSON.stringify(JSON.parse(resBody), null, 2); } catch (e) {}
    el.innerHTML = `<b>${res.status} ${res.statusText}</b> · ${elapsed}ms<br><pre style="white-space:pre-wrap;word-break:break-word">${escapeHtml(formatted)}</pre>`;
  } catch (e) {
    el.textContent = '请求失败: ' + e.message;
  }
}

// ============================================================
// M3: 扩展市场
// ============================================================

const EXTENSIONS = [
  { id: 'python', name: 'Python', desc: 'Python 语言支持、调试、Lint', icon: '🐍', installed: false },
  { id: 'node', name: 'Node.js', desc: 'JavaScript/TypeScript 高级支持', icon: '🟢', installed: false },
  { id: 'docker', name: 'Docker', desc: 'Docker 容器管理', icon: '🐳', installed: false },
  { id: 'gitlens', name: 'GitLens', desc: 'Git 增强：blame、历史对比', icon: '🔍', installed: false },
  { id: 'prettier', name: 'Prettier', desc: '代码格式化工具', icon: '✨', installed: false },
  { id: 'eslint', name: 'ESLint', desc: 'JS/TS 代码质量检查', icon: '🔬', installed: false },
  { id: 'markdown', name: 'Markdown Preview', desc: '实时 Markdown 预览', icon: '📝', installed: false },
  { id: 'rest', name: 'REST Client', desc: 'API 测试客户端', icon: '📡', installed: true },
  { id: 'sqlite', name: 'SQLite Browser', desc: 'SQLite 数据库管理', icon: '🗄', installed: true },
  { id: 'ssh', name: 'SSH Remote', desc: '远程服务器开发', icon: '🖥', installed: true },
  { id: 'theme', name: 'Theme Pack', desc: '额外配色主题', icon: '🎨', installed: false },
  { id: 'snippets', name: 'Snippets Pack', desc: '扩展代码片段库', icon: '📋', installed: false },
];

function openExtensionsPanel() {
  document.getElementById('ext-panel').classList.add('active');
  extRefresh();
}

function extRefresh() {
  filterExtensions();
}

function filterExtensions() {
  const q = (document.getElementById('ext-search')?.value || '').toLowerCase();
  const filtered = EXTENSIONS.filter(e => e.name.toLowerCase().includes(q) || e.desc.toLowerCase().includes(q));
  document.getElementById('ext-list').innerHTML = filtered.map(e =>
    `<div class="list-item">
      <span>${e.icon} ${escapeHtml(e.name)}</span>
      <span style="flex:1;margin-left:12px;color:var(--text2);font-size:11px">${escapeHtml(e.desc)}</span>
      <button class="${e.installed ? 'secondary' : 'action'}" onclick="toggleExtension('${e.id}')">${e.installed ? '已安装' : '安装'}</button>
    </div>`
  ).join('');
}

function toggleExtension(id) {
  const ext = EXTENSIONS.find(e => e.id === id);
  if (!ext) return;
  ext.installed = !ext.installed;
  extRefresh();
  appendTerminalOutput(`[扩展] ${ext.name} ${ext.installed ? '已安装' : '已卸载'}\r\n`);
}

// ============================================================
// M3: 主题 + 自动保存
// ============================================================

function switchTheme(theme) {
  localStorage.setItem('ynex_theme', theme);
  const monacoTheme = theme === 'jetbrains' ? 'vs-dark' : theme;
  for (const [, ed] of editors) {
    monaco.editor.setTheme(monacoTheme);
  }
  if (diffEditor) monaco.editor.setTheme(monacoTheme);
}

(function() {
  const saved = localStorage.getItem('ynex_theme') || 'vs-dark';
  const sel = document.getElementById('theme-picker');
  if (sel) sel.value = saved;
})();

let autoSaveEnabled = false;
let autoSaveInterval = null;

function toggleAutoSave() {
  autoSaveEnabled = !autoSaveEnabled;
  if (autoSaveEnabled) {
    autoSaveInterval = setInterval(async () => {
      for (const [fp, file] of openFiles) {
        if (file.modified) {
          await saveFile(fp);
        }
      }
    }, 5000);
    appendTerminalOutput('自动保存已开启 (5秒间隔)\r\n');
  } else {
    if (autoSaveInterval) clearInterval(autoSaveInterval);
    autoSaveInterval = null;
    appendTerminalOutput('自动保存已关闭\r\n');
  }
}

// ============================================================
// M5: 键盘宏录制
// ============================================================

let macroRecording = false;

async function openMacroPanel() {
  toggleOverlay('macro-panel');
  macroRefreshList();
}

async function macroStartRecording() {
  const name = document.getElementById('macro-name').value || `宏_${Date.now()}`;
  const result = await window.ynex.macro.start(name);
  if (result.ok) {
    macroRecording = true;
    document.getElementById('macro-record-btn').style.display = 'none';
    document.getElementById('macro-stop-btn').style.display = '';
    showToast(`开始录制宏: ${name}`);
    document.addEventListener('keydown', macroOnKeyDown);
    document.addEventListener('keyup', macroOnKeyUp);
  }
}

async function macroStopRecording() {
  document.removeEventListener('keydown', macroOnKeyDown);
  document.removeEventListener('keyup', macroOnKeyUp);
  const result = await window.ynex.macro.stop();
  if (result.ok) {
    macroRecording = false;
    document.getElementById('macro-record-btn').style.display = '';
    document.getElementById('macro-stop-btn').style.display = 'none';
    showToast(`录制完成: ${result.macro.eventCount} 个事件`);
    macroRefreshList();
  }
}

function macroOnKeyDown(e) {
  if (!macroRecording) return;
  window.ynex.macro.record({ event: { type: 'keydown', key: e.key, code: e.code, ctrl: e.ctrlKey, shift: e.shiftKey, alt: e.altKey, meta: e.metaKey } });
}

function macroOnKeyUp(e) {
  if (!macroRecording) return;
  window.ynex.macro.record({ event: { type: 'keyup', key: e.key, code: e.code } });
}

async function macroPlay(name) {
  const result = await window.ynex.macro.play(name);
  if (result.ok && result.events) {
    for (const evt of result.events) {
      const event = new KeyboardEvent(evt.type, {
        key: evt.key, code: evt.code, ctrlKey: evt.ctrl, shiftKey: evt.shift, altKey: evt.alt, metaKey: evt.meta
      });
      document.activeElement.dispatchEvent(event);
      await new Promise(r => setTimeout(r, evt.delay || 50));
    }
    showToast(`回放完成: ${name}`);
  }
}

async function macroDelete(name) {
  await window.ynex.macro.delete(name);
  macroRefreshList();
}

async function macroRefreshList() {
  const result = await window.ynex.macro.list();
  const el = document.getElementById('macro-list');
  if (result.ok && result.macros.length > 0) {
    el.innerHTML = result.macros.map(m => 
      `<div class="list-item"><span>${m.name} (${m.eventCount} 事件, ${(m.totalTime/1000).toFixed(1)}s)</span><div><button class="action" onclick="macroPlay('${m.name}')">▶</button><button class="secondary" onclick="macroDelete('${m.name}')">🗑</button></div></div>`
    ).join('');
  } else {
    el.innerHTML = '<div class="list-item"><span>暂无宏</span></div>';
  }
}

// ============================================================
// M5: Docker 容器管理
// ============================================================

async function openDockerPanel() {
  toggleOverlay('docker-panel');
  dockerRefresh();
}

async function dockerRefresh() {
  const check = await window.ynex.docker.check();
  if (!check.available) {
    document.getElementById('docker-containers').innerHTML = '<div class="list-item">Docker 未安装</div>';
    document.getElementById('docker-images').innerHTML = '';
    return;
  }
  const [containers, images] = await Promise.all([
    window.ynex.docker.listContainers(),
    window.ynex.docker.listImages()
  ]);
  const cEl = document.getElementById('docker-containers');
  if (containers.containers && containers.containers.length > 0) {
    cEl.innerHTML = containers.containers.map(c => 
      `<div class="list-item"><span>${c.names} (${c.image})</span><span style="color:${c.status.includes('Up')?'#4caf50':'#888'}">${c.status}</span><div><button class="action" onclick="dockerContainerAction('${c.id}','start')">▶</button><button class="action" onclick="dockerContainerAction('${c.id}','stop')">⏹</button><button class="action" onclick="dockerContainerAction('${c.id}','restart')">↻</button><button class="secondary" onclick="dockerContainerLogs('${c.id}')">📋</button><button class="secondary" onclick="dockerContainerAction('${c.id}','remove')">🗑</button></div></div>`
    ).join('');
  } else {
    cEl.innerHTML = '<div class="list-item">无容器</div>';
  }
  const iEl = document.getElementById('docker-images');
  if (images.images && images.images.length > 0) {
    iEl.innerHTML = images.images.map(i => `<div class="list-item"><span>${i.repo}:${i.tag}</span><span>${i.size}</span></div>`).join('');
  } else {
    iEl.innerHTML = '<div class="list-item">无镜像</div>';
  }
}

async function dockerContainerAction(id, action) {
  let result;
  switch (action) {
    case 'start': result = await window.ynex.docker.start(id); break;
    case 'stop': result = await window.ynex.docker.stop(id); break;
    case 'restart': result = await window.ynex.docker.restart(id); break;
    case 'remove': result = await window.ynex.docker.remove(id); break;
  }
  showToast(`${action} ${result.ok ? '成功' : '失败'}`);
  dockerRefresh();
}

async function dockerContainerLogs(id) {
  const result = await window.ynex.docker.logs(id);
  document.getElementById('docker-logs').textContent = result.logs || result.error || '';
}

async function dockerPullImage() {
  const image = document.getElementById('docker-image-pull').value.trim();
  if (!image) return;
  showToast('拉取中...');
  const result = await window.ynex.docker.pull(image);
  showToast(result.ok ? '拉取成功' : '拉取失败');
  dockerRefresh();
}

// ============================================================
// M5: Jupyter
// ============================================================

async function openJupyterPanel() {
  toggleOverlay('jupyter-panel');
  const status = await window.ynex.jupyter.status();
  jupyterUpdateUI(status.running);
}

async function jupyterStart() {
  showToast('启动 Jupyter 服务器...');
  const result = await window.ynex.jupyter.start(currentWorkspace);
  if (result.ok) {
    jupyterUpdateUI(true);
    document.getElementById('jupyter-status').innerHTML = `<div class="list-item"><span>Jupyter 运行中</span><a href="${result.url}" style="color:var(--accent)" target="_blank">打开</a></div>`;
  } else {
    document.getElementById('jupyter-status').innerHTML = `<div class="list-item">启动失败: ${result.error}</div>`;
  }
}

async function jupyterStop() {
  await window.ynex.jupyter.stop();
  jupyterUpdateUI(false);
  document.getElementById('jupyter-status').innerHTML = '<div class="list-item">已停止</div>';
}

function jupyterUpdateUI(running) {
  document.getElementById('jupyter-start-btn').style.display = running ? 'none' : '';
  document.getElementById('jupyter-stop-btn').style.display = running ? '' : 'none';
}

async function jupyterCreateNotebook() {
  const name = prompt('笔记本文件名:', 'notebook.ipynb');
  if (!name) return;
  const filePath = currentWorkspace ? `${currentWorkspace}/${name}` : name;
  const result = await window.ynex.jupyter.createNotebook(filePath);
  if (result.ok) {
    showToast('笔记本已创建');
    await openFile(filePath);
  }
}

// ============================================================
// M5: CI/CD 面板
// ============================================================

async function openCicdPanel() {
  toggleOverlay('cicd-panel');
  cicdDetect();
}

async function cicdDetect() {
  if (!currentWorkspace) return;
  const result = await window.ynex.cicd.detect(currentWorkspace);
  const el = document.getElementById('cicd-configs');
  if (result.configs && result.configs.length > 0) {
    el.innerHTML = result.configs.map(c => 
      `<div class="list-item"><span>${c.icon} ${c.type}: ${c.name}</span><div><button class="action" onclick="cicdRunConfig('${c.type}','${c.file}','${c.name}')">▶ 运行</button></div></div>`
    ).join('');
  } else {
    el.innerHTML = '<div class="list-item">未检测到 CI/CD 配置</div>';
  }
}

async function cicdRunConfig(type, file, name) {
  document.getElementById('cicd-output').textContent = `运行中: ${type} ${name}...\n`;
  let result;
  switch (type) {
    case 'npm scripts':
      result = await window.ynex.cicd.runNpm(currentWorkspace, name);
      break;
    case 'Make':
      result = await window.ynex.cicd.runMake(currentWorkspace, name);
      break;
    case 'Docker Build':
      result = await window.ynex.cicd.runDocker(currentWorkspace, file);
      break;
    default:
      result = await window.ynex.cicd.runCommand(currentWorkspace, `cat ${file}`);
  }
  document.getElementById('cicd-output').textContent = result.stdout || result.stderr || result.error || '完成';
}

async function cicdRunCustom() {
  const cmd = document.getElementById('cicd-custom-cmd').value.trim();
  if (!cmd) return;
  document.getElementById('cicd-output').textContent = `运行: ${cmd}...\n`;
  const result = await window.ynex.cicd.runCommand(currentWorkspace, cmd);
  document.getElementById('cicd-output').textContent = result.stdout || result.stderr || result.error || '完成';
}

// ============================================================
// M5: Mermaid 图表
// ============================================================

async function openMermaidPanel() {
  toggleOverlay('mermaid-panel');
}

async function mermaidRender() {
  const diagram = document.getElementById('mermaid-diagram').value.trim();
  if (!diagram) return;
  const theme = document.getElementById('mermaid-theme').value;
  const result = await window.ynex.mermaid.render(diagram, 'svg', theme);
  if (result.ok) {
    if (result.svg) {
      document.getElementById('mermaid-output').innerHTML = result.svg;
    } else if (result.html) {
      document.getElementById('mermaid-output').innerHTML = `<iframe src="${result.html}" style="width:100%;min-height:400px;border:none"></iframe>`;
    }
  }
}

async function mermaidGenerateFlowchart() {
  const code = getCurrentCode();
  const lang = getCurrentLanguage();
  if (!code) return showToast('请先打开文件');
  showToast('生成流程图中...');
  const result = await window.ynex.mermaid.flowchart(code, lang);
  if (result.ok) {
    document.getElementById('mermaid-diagram').value = result.diagram;
    mermaidRender();
  }
}

async function mermaidGenerateClassDiagram() {
  const code = getCurrentCode();
  const lang = getCurrentLanguage();
  if (!code) return showToast('请先打开文件');
  showToast('生成类图中...');
  const result = await window.ynex.mermaid.classDiagram(code, lang);
  if (result.ok) {
    document.getElementById('mermaid-diagram').value = result.diagram;
    mermaidRender();
  }
}

// ============================================================
// M5: 插件 SDK
// ============================================================

async function openPluginSdkPanel() {
  toggleOverlay('plugin-sdk-panel');
  pluginRefreshList();
}

async function pluginCreate() {
  const name = document.getElementById('plugin-name').value.trim();
  const desc = document.getElementById('plugin-desc').value.trim();
  if (!name) return;
  const result = await window.ynex.plugin.create(name, { description: desc });
  if (result.ok) {
    showToast(`插件 ${name} 已创建`);
    pluginRefreshList();
  } else {
    showToast(result.error);
  }
}

async function pluginRemove(name) {
  await window.ynex.plugin.remove(name);
  showToast(`插件 ${name} 已删除`);
  pluginRefreshList();
}

async function pluginToggle(name) {
  const result = await window.ynex.plugin.toggle(name);
  showToast(result.enabled ? '已启用' : '已禁用');
  pluginRefreshList();
}

async function pluginRefreshList() {
  const result = await window.ynex.plugin.list();
  const el = document.getElementById('plugin-list');
  if (result.ok && result.plugins.length > 0) {
    el.innerHTML = result.plugins.map(p => 
      `<div class="list-item"><span>${p.name} v${p.version}</span><span style="color:${p.enabled?'#4caf50':'#888'}">${p.enabled ? '启用' : '禁用'}</span><div><button class="action" onclick="pluginToggle('${p.name}')">${p.enabled ? '⏸' : '▶'}</button><button class="secondary" onclick="pluginRemove('${p.name}')">🗑</button></div></div>`
    ).join('');
  } else {
    el.innerHTML = '<div class="list-item">暂无插件</div>';
  }
}

// ============================================================
// M5: AI 代码审查
// ============================================================

async function openCodeReviewPanel() {
  toggleOverlay('code-review-panel');
}

async function codeReviewCurrentFile() {
  const code = getCurrentCode();
  const lang = getCurrentLanguage();
  const filePath = currentFile || 'unknown';
  if (!code) return showToast('请先打开文件');
  document.getElementById('code-review-output').textContent = '审查中...';
  const result = await window.ynex.review.file(code, filePath, lang);
  if (result.ok) {
    document.getElementById('code-review-output').textContent = result.review.result || result.review;
  }
}

async function codeReviewProject() {
  if (!currentWorkspace) return showToast('请先打开工作区');
  const files = Array.from(openFiles.entries()).map(([p, f]) => ({ path: p, content: f.content, language: getLanguageFromPath(p) }));
  document.getElementById('code-review-output').textContent = '项目审查中...';
  const result = await window.ynex.review.project(files, currentWorkspace);
  if (result.ok) {
    const summary = result.summary || '';
    const fileList = (result.files || []).map(r => `\n### ${r.filePath}\n${r.result}`).join('\n');
    document.getElementById('code-review-output').textContent = summary + fileList;
  }
}

// ============================================================
// M5: AI 重构
// ============================================================

let currentRefactorResult = null;

async function openRefactorPanel() {
  toggleOverlay('refactor-panel');
}

async function refactorExecute(operation) {
  const code = getCurrentCode();
  const lang = getCurrentLanguage();
  const filePath = currentFile || 'unknown';
  if (!code) return showToast('请先打开文件');
  document.getElementById('refactor-output').textContent = `重构中 (${operation})...`;
  const result = await window.ynex.refactor.execute(code, filePath, lang, operation, null);
  if (result.ok) {
    currentRefactorResult = result;
    document.getElementById('refactor-output').textContent = result.refactoredCode || result.error;
  }
}

function refactorApply() {
  if (!currentRefactorResult || !currentRefactorResult.refactoredCode) return;
  if (currentEditor) {
    currentEditor.setValue(currentRefactorResult.refactoredCode);
    showToast('重构已应用');
  }
  currentRefactorResult = null;
}

function refactorDiscard() {
  currentRefactorResult = null;
  document.getElementById('refactor-output').textContent = '';
  showToast('已丢弃');
}

// ============================================================
// M5: Live Preview
// ============================================================

async function openLivePreviewPanel() {
  toggleOverlay('live-preview-panel');
}

function livePreviewGo() {
  const url = document.getElementById('preview-url').value.trim();
  if (!url) return;
  const webview = document.getElementById('live-preview-webview');
  if (webview) {
    webview.src = url.startsWith('http') ? url : 'http://' + url;
  }
}

async function livePreviewStartServer() {
  if (!currentWorkspace) return showToast('请先打开工作区');
  showToast('启动开发服务器...');
  document.getElementById('preview-url').value = 'http://localhost:3000';
  livePreviewGo();
}

// ============================================================
// M5: 语义代码搜索 + 辅助函数
// ============================================================

async function semanticSearch(query) {
  if (!query) return;
  showToast('语义搜索中...');
  try {
    const resp = await fetch('http://127.0.0.1:7777/api/code/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, workspacePath: currentWorkspace })
    });
    const data = await resp.json();
    if (data.results && data.results.length > 0) {
      appendTerminalOutput(`[搜索] "${query}" 找到 ${data.results.length} 个结果:\r\n`);
      data.results.forEach(r => {
        appendTerminalOutput(`  ${r.path}:${r.line} - ${r.snippet?.slice(0, 80) || ''}\r\n`);
      });
    } else {
      appendTerminalOutput(`[搜索] "${query}" 未找到结果\r\n`);
    }
  } catch (e) {
    appendTerminalOutput(`[搜索] 请求失败: ${e.message}\r\n`);
  }
}

// ============================================================
// M5: 辅助功能
// ============================================================

function toggleCommandPalette() {
  const el = document.getElementById('command-palette');
  if (el.classList.contains('active')) {
    closeCommandPalette();
  } else {
    openCommandPalette();
  }
}

function toggleTerminal() {
  const panel = document.getElementById('bottom-panel');
  if (panel) {
    panel.style.display = panel.style.display === 'none' ? '' : 'none';
    if (panel.style.display !== 'none') {
      const input = document.getElementById('terminal-input');
      if (input) input.focus();
    }
  }
}

function toggleFileExplorer() {
  const explorer = document.getElementById('file-explorer');
  if (explorer) {
    explorer.style.display = explorer.style.display === 'none' ? '' : 'none';
  }
}

function toggleGitPanel() {
  const panel = document.getElementById('git-panel');
  if (panel) {
    if (panel.classList.contains('active')) {
      panel.classList.remove('active');
    } else {
      panel.classList.add('active');
    }
  }
}

function openDebugPanel() {
  const panel = document.getElementById('debug-panel');
  if (panel) panel.classList.add('active');
}

function closeAllOverlays() {
  document.querySelectorAll('.overlay-panel').forEach(el => el.classList.remove('active'));
  const palette = document.getElementById('command-palette');
  if (palette) palette.classList.remove('active');
}

function openSettingsPanel() {
  // 移除已存在的设置面板
  const existing = document.getElementById('settings-panel');
  if (existing) existing.remove();

  const settings = [
    { id: 'theme-dark', label: '🌙 暗色主题' },
    { id: 'theme-light', label: '☀️ 亮色主题' },
    { id: 'theme-hc', label: '⚫ 高对比主题' },
    { id: 'theme-jb', label: '🧩 JetBrains 主题' },
    { id: 'autosave', label: autoSaveEnabled ? '⏸ 关闭自动保存' : '▶ 开启自动保存' },
    { id: 'perf', label: '📊 性能统计' },
  ];
  const items = settings.map(s => `<div class="settings-item" data-id="${s.id}" style="cursor:pointer;padding:10px 14px;border-bottom:1px solid var(--border);font-size:14px">${s.label}</div>`).join('');
  const html = `<div id="settings-panel" class="overlay-panel active" style="position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);width:340px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);z-index:1000;max-height:420px;overflow:hidden;box-shadow:0 12px 40px rgba(0,0,0,0.5)">
    <div class="overlay-header" style="padding:12px 14px"><h3 style="font-size:15px">⚙ 设置</h3><button id="settings-close" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:4px 10px;border-radius:var(--radius);cursor:pointer;font-size:12px">关闭</button></div>
    <div class="overlay-content" style="padding:0">${items}</div>
  </div>`;
  const div = document.createElement('div');
  div.innerHTML = html;
  const panel = div.firstElementChild;
  document.body.appendChild(panel);

  panel.querySelector('#settings-close').addEventListener('click', () => panel.remove());
  panel.querySelectorAll('.settings-item').forEach(item => {
    item.addEventListener('click', () => {
      const id = item.getAttribute('data-id');
      switch (id) {
        case 'theme-dark': switchTheme('vs-dark'); break;
        case 'theme-light': switchTheme('vs'); break;
        case 'theme-hc': switchTheme('hc-black'); break;
        case 'theme-jb': switchTheme('jetbrains'); break;
        case 'autosave': toggleAutoSave(); break;
        case 'perf': showPerfStats(); break;
      }
      panel.remove();
    });
  });
}

async function showPerfStats() {
  try {
    const resp = await fetch('http://127.0.0.1:7777/api/health');
    const data = await resp.json();
    appendTerminalOutput(`[性能] 堆内存: ${data.heap_mb || '?'}MB | LLM: ${data.local_llm || '?'} | 缓存命中率: ${data.cache_hit_rate || '?'}\r\n`);
  } catch (e) {
    appendTerminalOutput(`[性能] 无法获取统计: ${e.message}\r\n`);
  }
}

// ============================================================
// M6: 性能监控面板
// ============================================================

let perfMonitorActive = false;
let perfMonitorInterval = null;

function showBottomTab(tab) {
  // 更新 tab 按钮
  document.querySelectorAll('#bottom-panel .tab-btn').forEach((btn, i) => {
    btn.classList.toggle('active', false);
  });
  const tabs = document.querySelectorAll('#bottom-panel .tab-btn');
  const tabNames = ['terminal', 'output', 'perf'];
  const idx = tabNames.indexOf(tab);
  if (idx >= 0 && tabs[idx]) tabs[idx].classList.add('active');

  // 切换内容区域
  const terminal = document.getElementById('terminal-container');
  const perf = document.getElementById('perf-container');
  if (terminal) terminal.style.display = tab === 'terminal' ? '' : 'none';
  if (perf) perf.style.display = tab === 'perf' ? '' : 'none';
}

async function perfMonitorStart() {
  await window.ynex.monitor.start();
  perfMonitorActive = true;
  perfMonitorInterval = setInterval(perfMonitorRefresh, 2000);
  perfMonitorRefresh();
  showToast('性能监控已启动');
}

async function perfMonitorStop() {
  await window.ynex.monitor.stop();
  perfMonitorActive = false;
  if (perfMonitorInterval) {
    clearInterval(perfMonitorInterval);
    perfMonitorInterval = null;
  }
  showToast('性能监控已停止');
}

async function perfMonitorRefresh() {
  try {
    const [snapshot, bottlenecks, perfStats, cacheStats, indexStats] = await Promise.all([
      window.ynex.monitor.snapshot(),
      window.ynex.monitor.bottlenecks(),
      window.ynex.perf.stats(),
      window.ynex.cache.stats(),
      window.ynex.index.stats(),
    ]);

    const s = snapshot.snapshot || {};
    const fps = s.fps ? (s.fps.current || s.fps.avg || '--') : '--';
    const mem = s.memory ? `${s.memory.heapUsed || '--'}MB` : '--';
    const cpu = s.cpu ? `${s.cpu.current || '--'}%` : '--';
    const lat = s.latency ? `${s.latency.current || '--'}ms` : '--';

    document.getElementById('perf-fps').textContent = fps;
    document.getElementById('perf-mem').textContent = mem;
    document.getElementById('perf-cpu').textContent = cpu;
    document.getElementById('perf-lat').textContent = lat;
    document.getElementById('perf-cache').textContent = cacheStats.stats ? `${cacheStats.stats.count}条` : '--';
    document.getElementById('perf-idx').textContent = indexStats.stats ? `${indexStats.stats.files}文件` : '--';

    // 瓶颈提示
    const issues = bottlenecks.issues || [];
    const el = document.getElementById('perf-bottlenecks');
    if (issues.length > 0) {
      el.innerHTML = issues.map(i => 
        `<div style="color:${i.severity==='error'?'#f44336':'#ff9800'};padding:2px 0">• ${i.message}</div>`
      ).join('');
    } else {
      el.textContent = '✅ 无性能瓶颈';
    }
  } catch (e) {}
}

function getCurrentCode() {
  if (currentEditor) return currentEditor.getValue();
  return '';
}

function getCurrentLanguage() {
  if (!currentFile) return '';
  return getLanguageFromPath(currentFile);
}

function getLanguageFromPath(filePath) {
  const ext = filePath.split('.').pop().toLowerCase();
  const map = {
    js: 'javascript', jsx: 'javascript', ts: 'typescript', tsx: 'typescript',
    py: 'python', java: 'java', go: 'go', rs: 'rust', cpp: 'cpp', c: 'c',
    h: 'cpp', html: 'html', css: 'css', json: 'json', yaml: 'yaml', yml: 'yaml',
    md: 'markdown', sql: 'sql', sh: 'bash', bat: 'bat', ps1: 'powershell',
    php: 'php', rb: 'ruby', swift: 'swift', kt: 'kotlin'
  };
  return map[ext] || '';
}

// ============================================================
// M5: 语音转代码
// ============================================================

async function voiceToCode() {
  try {
    // 使用浏览器 Web Speech API 进行语音识别
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      showToast('浏览器不支持语音识别');
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = 'zh-CN';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    showToast('正在聆听...说出你的代码需求');

    recognition.onresult = async (event) => {
      const description = event.results[0][0].transcript;
      showToast(`识别: ${description}`);

      // 调用后端生成代码
      const lang = getCurrentLanguage() || 'python';
      const code = getCurrentCode();
      const context = code ? `\n当前文件代码上下文:\n\`\`\`${lang}\n${code.slice(0, 2000)}\n\`\`\`` : '';

      appendTerminalOutput(`🎤 语音输入: ${description}\r\n`);

      try {
        const resp = await fetch('http://127.0.0.1:7777/api/voice/to-code', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ description, language: lang, context })
        });
        const data = await resp.json();
        if (data.code) {
          if (currentEditor) {
            currentEditor.setValue(data.code);
            showToast('代码已生成');
          } else {
            // 创建新文件
            const ext = { javascript: 'js', python: 'py', java: 'java', go: 'go', cpp: 'cpp' }[lang] || 'txt';
            const newPath = `${currentWorkspace || '.'}/voice_${Date.now()}.${ext}`;
            await window.ynex.fs.writeFile(newPath, data.code);
            await openFile(newPath);
            showToast('代码已生成到新文件');
          }
          appendTerminalOutput(`🎤 生成 ${lang} 代码完成\r\n`);
        }
      } catch (e) {
        appendTerminalOutput(`🎤 生成失败: ${e.message}\r\n`);
      }
    };

    recognition.onerror = (event) => {
      showToast(`语音识别错误: ${event.error}`);
    };

    recognition.start();
  } catch (e) {
    showToast(`语音识别启动失败: ${e.message}`);
  }
}
