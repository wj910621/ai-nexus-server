/* ========================================
   代码助手核心模块
   文件树、编辑器、语法高亮、终端、AI分析
   ======================================== */
var NexusCode = (function() {
  'use strict';

  // ===== 文件树数�?=====
  var FILE_TREE = [
    {
      name: 'trigenclaw',
      type: 'directory',
      expanded: true,
      children: [
        { name: 'index.html', type: 'file' },
        {
          name: 'css', type: 'directory', expanded: true,
          children: [
            { name: 'style.css', type: 'file' }
          ]
        },
        {
          name: 'js', type: 'directory', expanded: true,
          children: [
            { name: 'api.js', type: 'file' },
            { name: 'models.js', type: 'file' },
            { name: 'chat.js', type: 'file' },
            { name: 'code.js', type: 'file', highlight: true },
            { name: 'ui.js', type: 'file' },
            { name: 'app.js', type: 'file' }
          ]
        },
        { name: 'manifest.json', type: 'file' },
        { name: 'sw.js', type: 'file' }
      ]
    }
  ];

  // ===== 内置文件内容 =====
  var FILE_CONTENTS = {
    'index.html': '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n  <meta charset="UTF-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n  <title>TriGenClaw</title>\n  <link rel="stylesheet" href="css/style.css">\n</head>\n<body>\n  <div id="app" class="app-container">\n    <!-- 主容�?-->\n  </div>\n  <script src="js/app.js"></script>\n</body>\n</html>',
    'style.css': ':root {\n  --primary: #00d4ff;\n  --secondary: #7b2ff7;\n  --bg-deep: #0f0f23;\n  --bg-card: #1a1a2e;\n  --text-primary: #e0e0e0;\n  --text-secondary: #8888aa;\n}\n\n* { margin: 0; padding: 0; box-sizing: border-box; }\n\nbody {\n  font-family: "Microsoft YaHei", sans-serif;\n  background: var(--bg-deep);\n  color: var(--text-primary);\n}',
    'api.js': 'var NexusAPI = (function() {\n  "use strict";\n  var API_BASE = "https://j3trisheng.com";\n  \n  function chatStream(model, messages, onChunk, onDone, onError) {\n    // SSE streaming implementation\n  }\n  \n  return { chatStream: chatStream };\n})();',
    'models.js': 'var NexusModels = (function() {\n  "use strict";\n  var currentModel = "deepseek-chat";\n  \n  function getCurrentModel() { return currentModel; }\n  function setCurrentModel(id) { currentModel = id; }\n  \n  return { getCurrentModel: getCurrentModel, setCurrentModel: setCurrentModel };\n})();',
    'chat.js': 'var NexusChat = (function() {\n  "use strict";\n  var messages = [];\n  \n  function addMessage(role, content) {\n    messages.push({ role: role, content: content });\n  }\n  \n  return { addMessage: addMessage, getMessages: function() { return messages; } };\n})();',
    'code.js': 'var NexusCode = (function() {\n  "use strict";\n  // Code editor, file tree, terminal\n  return {};\n})();',
    'ui.js': 'var NexusUI = (function() {\n  "use strict";\n  // UI utilities: Toast, panel switching, keyboard shortcuts\n  return {};\n})();',
    'app.js': 'var appReady = true;\nconsole.log("TriGenClaw initialized.");',
    'manifest.json': '{\n  "name": "TriGenClaw",\n  "short_name": "TriGen AI",\n  "start_url": ".",\n  "display": "standalone"\n}',
    'sw.js': 'self.addEventListener("install", function(e) {\n  console.log("Service Worker installed");\n});'
  };

  // ===== 代码片段模板 =====
  var CODE_SNIPPETS = [
    { name: 'HTML5 Boilerplate', lang: 'html', code: '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n  <meta charset="UTF-8">\n  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n  <title>Document</title>\n  <link rel="stylesheet" href="style.css">\n</head>\n<body>\n  <div id="app"></div>\n  <script src="app.js"><\/script>\n</body>\n</html>' },
    { name: 'CSS Reset', lang: 'css', code: '*, *::before, *::after {\n  margin: 0;\n  padding: 0;\n  box-sizing: border-box;\n}\n\nhtml, body {\n  height: 100%;\n  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;\n  font-size: 16px;\n  line-height: 1.5;\n  color: #333;\n}\n\na { text-decoration: none; color: inherit; }\nul, ol { list-style: none; }\nimg { max-width: 100%; display: block; }' },
    { name: 'Express Server', lang: 'js', code: 'const express = require("express");\nconst app = express();\nconst PORT = process.env.PORT || 3000;\n\napp.use(express.json());\napp.use(express.static("public"));\n\napp.get("/api/health", (req, res) => {\n  res.json({ status: "ok", timestamp: new Date().toISOString() });\n});\n\napp.listen(PORT, () => {\n  console.log(`Server running on http://localhost:${PORT}`);\n});' },
    { name: 'React Component', lang: 'jsx', code: 'import React, { useState, useEffect } from "react";\nimport "./styles.css";\n\nfunction App() {\n  const [data, setData] = useState(null);\n  const [loading, setLoading] = useState(true);\n\n  useEffect(() => {\n    fetch("/api/data")\n      .then(res => res.json())\n      .then(data => { setData(data); setLoading(false); })\n      .catch(err => console.error("Error:", err));\n  }, []);\n\n  if (loading) return <div className="loading">Loading...</div>;\n\n  return (\n    <div className="app">\n      <h1>Hello React</h1>\n      <pre>{JSON.stringify(data, null, 2)}</pre>\n    </div>\n  );\n}\n\nexport default App;' },
    { name: 'JS Module Pattern', lang: 'js', code: 'var MyModule = (function() {\n  "use strict";\n\n  var privateVar = 0;\n\n  function privateMethod() {\n    return privateVar;\n  }\n\n  function publicMethod(value) {\n    privateVar = value;\n    return privateMethod();\n  }\n\n  return {\n    get: privateMethod,\n    set: publicMethod,\n    reset: function() { privateVar = 0; }\n  };\n})();\n\n// Usage:\n// MyModule.set(42);\n// console.log(MyModule.get()); // 42' },
    { name: 'Python Flask API', lang: 'python', code: 'from flask import Flask, request, jsonify\nfrom flask_cors import CORS\n\napp = Flask(__name__)\nCORS(app)\n\n@app.route("/api/hello", methods=["GET"])\ndef hello():\n    name = request.args.get("name", "World")\n    return jsonify({"message": f"Hello, {name}!"})\n\n@app.route("/api/data", methods=["POST"])\ndef handle_data():\n    data = request.get_json()\n    if not data:\n        return jsonify({"error": "No data provided"}), 400\n    return jsonify({"received": data, "status": "ok"})\n\nif __name__ == "__main__":\n    app.run(debug=True, port=5000)' }
  ];

  
  
  function setupAuto() {
    var btn = document.getElementById('codeAutoBtn');
    if (!btn) return;
    btn.addEventListener('click', function() {
      var request = prompt('What feature do you want to implement?');
      if (request && request.trim()) {
        document.querySelector('[data-panel=aiPanel]')?.click();
        showAILoading();
        NexusAuto.start(request.trim());
      }
    });
  }
    function setupRun() {
    var btn = document.getElementById('codeRunBtn');
    if (!btn) return;
    btn.addEventListener('click', runCode);
  }

  function runCode() {
    var code = editorEl.value;
    if (!code || !code.trim()) { NexusUI.toast('No code to run', 'warning'); return; }
    document.querySelector('[data-panel="terminalPanel"]')?.click();
    addTerminalLine('<span class="terminal-prompt">TriGen:~$</span> node ' + (currentFileName || 'code.js'));
    addTerminalLine('Running in sandbox...');
    
    var safeCode = code.replace(/<\/script>/gi, '<\\/script>');
    var html = '<!DOCTYPE html><html><body><script>';
    html += 'window.onerror=function(m){parent.postMessage({type:"sb",data:"[ERROR] "+m},"*");};';
    html += 'var _o=[];';
    html += 'console.log=function(){_o.push(Array.prototype.join.call(arguments," "));};';
    html += 'console.error=function(){_o.push("[ERROR] "+Array.prototype.join.call(arguments," "));};';
    html += 'try{(function(){\n' + safeCode + '\n})();}catch(e){_o.push("[EXCEPTION] "+e.message);}';
    html += 'parent.postMessage({type:"sb",data:_o.join("\\n")},"*");';
    html += '<\\/script></body></html>';
    
    var sb = document.createElement('iframe');
    sb.style.display = 'none';
    sb.setAttribute('sandbox', 'allow-scripts');
    sb.src = URL.createObjectURL(new Blob([html], { type: 'text/html' }));
    document.body.appendChild(sb);
    setTimeout(function() { sb.remove(); URL.revokeObjectURL(sb.src); }, 3000);
  }

  window.addEventListener('message', function(e) {
    if (e.data && e.data.type === 'sb') {
      var lines = e.data.data.split('\n');
      for (var i = 0; i < lines.length; i++) {
        addTerminalLine('<span class="terminal-output">' + escapeHtml(lines[i]) + '</span>');
      }
      if (terminalContentEl) terminalContentEl.scrollTop = terminalContentEl.scrollHeight;
    }
  });
  function setupEvolve() {
    var btn = document.getElementById('codeEvolveBtn'); if (!btn) return; btn.addEventListener('click', evolveCurrentFile);
  }
  function evolveCurrentFile() {
    var code = editorEl.value;
    if (!code || !code.trim()) { NexusUI.toast('No code to evolve', 'warning'); return; }
    var aiTab = document.querySelector('[data-panel=aiPanel]');
    if (aiTab) aiTab.click();
    showAILoading();
    var promptText = 'Analyze and improve this code. Focus on quality, performance, security, and modern syntax.';
    promptText = promptText + ' Provide the complete improved code between CODE_START and CODE_END markers.';
    promptText = promptText + '\\n\\nCODE_START\\n' + code + '\\nCODE_END';
    NexusAPI.chat(NexusModels.getCurrentModel(), [
      { role: 'system', content: 'You are a senior code architect.' },
      { role: 'user', content: promptText }
    ], { temperature: 0.3, max_tokens: 8192 }).then(function(content) {
      showAIResult(content);
      addEvolveApplyBtn(content);
      NexusUI.toast('Evolution suggestions ready', 'success');
    }).catch(function(err) {
      var fb = '## Code Evolution (Demo)\\n\\n### Suggested Improvements\\n1. Add try-catch error handling\\n2. Use const/let instead of var\\n3. Add JSDoc comments\\n4. Extract repeated logic\\n\\nCODE_START\\n' + code.replace(/var /g, 'const ') + '\\nCODE_END';
      showAIResult(fb);
      addEvolveApplyBtn(fb);
    });
  }
  function addEvolveApplyBtn(response) {
    var cs = response.indexOf('CODE_START');
    var ce = response.indexOf('CODE_END');
    if (cs < 0 || ce <= cs) return;
    var improved = response.substring(cs + 10, ce).trim();
    var container = document.getElementById('aiPanelContent');
    if (!container || container.querySelector('.evolve-bar')) return;
    var bar = document.createElement('div'); bar.className = 'evolve-bar';
    var btn = document.createElement('button'); btn.className = 'btn btn-sm btn-primary evolve-apply'; btn.textContent = 'Apply Changes';
    btn.addEventListener('click', function() {
      editorEl.value = improved;
      syncLineNumbers(); syncHighlight();
      NexusUI.toast('Code evolved! Save with Ctrl+S', 'success');
      bar.remove();
    });
    bar.appendChild(btn);
    container.appendChild(bar);
  }
  function setupSnippets() {
    var btn = document.getElementById('codeSnippetsBtn');
    if (!btn) return;
    btn.addEventListener('click', function() {
      showSnippetsMenu();
    });
  }

  function showSnippetsMenu() {
    // 创建下拉菜单
    var existing = document.querySelector('.snippets-dropdown');
    if (existing) { existing.remove(); return; }

    var dropdown = document.createElement('div');
    dropdown.className = 'snippets-dropdown';
    dropdown.innerHTML = '<div class="snippets-header">Code Snippets</div>';

    var list = document.createElement('div');
    list.className = 'snippets-list';
    for (var i = 0; i < CODE_SNIPPETS.length; i++) {
      var item = document.createElement('div');
      item.className = 'snippets-item';
      item.innerHTML = '<span class="snippets-lang">' + CODE_SNIPPETS[i].lang + '</span> ' +
        '<span class="snippets-name">' + CODE_SNIPPETS[i].name + '</span>';
      (function(idx) {
        item.addEventListener('click', function() {
          insertSnippet(idx);
          dropdown.remove();
        });
      })(i);
      list.appendChild(item);
    }
    dropdown.appendChild(list);
    document.body.appendChild(dropdown);

    // 定位在按钮下�?    var btn = document.getElementById('codeSnippetsBtn');
    if (btn) {
      var rect = btn.getBoundingClientRect();
      dropdown.style.top = (rect.bottom + 4) + 'px';
      dropdown.style.left = rect.left + 'px';
    }

    // 点击外部关闭
    setTimeout(function() {
      document.addEventListener('click', function closeMenu(e) {
        if (!dropdown.contains(e.target) && e.target !== btn) {
          dropdown.remove();
          document.removeEventListener('click', closeMenu);
        }
      });
    }, 0);
  }

  function insertSnippet(index) {
    if (!editorEl || index < 0 || index >= CODE_SNIPPETS.length) return;
    var snippet = CODE_SNIPPETS[index].code;
    var start = editorEl.selectionStart;
    var end = editorEl.selectionEnd;
    editorEl.value = editorEl.value.substring(0, start) + snippet + editorEl.value.substring(end);
    editorEl.selectionStart = editorEl.selectionEnd = start + snippet.length;
    syncLineNumbers();
    syncHighlight();
    NexusUI.toast('Inserted: ' + CODE_SNIPPETS[index].name, 'success');
  }  // ===== 状�?=====
  var currentFile = null;
  var editorEl = null;
  var lineNumbersEl = null;
  var highlightLayerEl = null;
  var fileTreeEl = null;
  var fileTreeContentEl = null;
  var editorTabsEl = null;
  var aiPanelContentEl = null;
  var terminalContentEl = null;
  var terminalInputEl = null;
  var terminalHistory = [];
  var terminalHistoryIndex = -1;
  var terminalCommands = {};

  var currentFileName = '';

  // ===== 语法高亮 =====
  var KEYWORDS_JS = ['var', 'let', 'const', 'function', 'return', 'if', 'else', 'for', 'while', 'do', 'switch', 'case', 'break', 'continue', 'new', 'this', 'typeof', 'instanceof', 'in', 'of', 'try', 'catch', 'finally', 'throw', 'async', 'await', 'class', 'extends', 'import', 'export', 'default', 'from', 'true', 'false', 'null', 'undefined', 'NaN'];
  var KEYWORDS_HTML = ['html', 'head', 'body', 'div', 'span', 'p', 'a', 'img', 'ul', 'ol', 'li', 'table', 'tr', 'td', 'th', 'form', 'input', 'button', 'textarea', 'select', 'option', 'header', 'footer', 'main', 'section', 'nav', 'aside', 'h1', 'h2', 'h3', 'h4', 'h5'];
  var KEYWORDS_CSS = ['margin', 'padding', 'border', 'background', 'color', 'font', 'display', 'flex', 'grid', 'position', 'top', 'left', 'right', 'bottom', 'width', 'height', 'overflow', 'text', 'align', 'justify', 'transition', 'animation', 'transform', 'opacity', 'z-index'];

  function getKeywordsForFile(fileName) {
    if (/\.html?$/.test(fileName)) return { html: true, css: true, js: true };
    if (/\.css$/.test(fileName)) return { css: true };
    if (/\.js$/.test(fileName)) return { js: true };
    if (/\.json$/.test(fileName)) return { json: true };
    return {};
  }

  /**
   * 语法高亮 �?将纯文本转换为带 span 标签�?HTML
   */
  function highlightCode(code, fileName) {
    if (!code) return '';
    var lang = getKeywordsForFile(fileName || '');
    var escaped = escapeHtml(code);

    if (lang.json) {
      // JSON 简单高亮：键名、字符串、数字、布尔�?      escaped = escaped
        .replace(/("(?:[^"\\]|\\.)*")\s*:/g, '<span class="hl-key"></span>:')
        .replace(/:(\s*)("(?:[^"\\]|\\.)*")/g, ':<span class="hl-string"></span>')
        .replace(/:(\s*)(true|false|null)/g, ':<span class="hl-literal"></span>')
        .replace(/:(\s*)(-?\d+\.?\d*)/g, ':<span class="hl-number"></span>');
    } else {
      // 注释
      if (lang.js || lang.html) {
        escaped = escaped
          .replace(/\/\/.*$/gm, '<span class="hl-comment">$&</span>')
          .replace(/\/\*[\s\S]*?\*\//g, '<span class="hl-comment">$&</span>');
      }

      // HTML 标签（如果文件中可能�?HTML�?      if (lang.html || lang.js) {
        escaped = escaped
          .replace(/(&lt;\/?)(\w+)([^&]*?)(\/?&gt;)/g, function(m, open, tag, attrs, close) {
            var result = open + '<span class="hl-tag">' + tag + '</span>';
            // 属�?            result += attrs.replace(/(\s+)(\w[-.\w]*)(\s*=\s*)(&(?:quot|#39);[^&]*&(?:quot|#39);|"[^"]*"|'[^']*')/g, function(m2, space, attrName, eq, attrVal) {
              return space + '<span class="hl-attr">' + attrName + '</span>' + eq + '<span class="hl-string">' + attrVal + '</span>';
            });
            result += close;
            return result;
          });
      }

      // CSS 属�?      if (lang.css || lang.html) {
        escaped = escaped.replace(/([-\w]+)\s*:/g, function(m, prop) {
          if (KEYWORDS_CSS.indexOf(prop) !== -1 || /^--/.test(prop)) {
            return '<span class="hl-attr">' + prop + '</span>:';
          }
          if (prop === 'var') {
            return '<span class="hl-builtin">' + prop + '</span>:';
          }
          return m;
        });
        // CSS 选择器类名和 ID
        escaped = escaped.replace(/(\.[\w-]+)/g, '<span class="hl-class"></span>');
        escaped = escaped.replace(/(#[\w-]+)/g, '<span class="hl-id"></span>');
        // CSS �?        escaped = escaped.replace(/(#[0-9a-fA-F]{3,8})\b/g, '<span class="hl-number"></span>');
        escaped = escaped.replace(/\b(\d+)(px|em|rem|%|vh|vw|s|ms)?\b/g, function(m, num, unit) {
          return '<span class="hl-number">' + num + '</span>' + (unit || '');
        });
      }

      // JS 关键�?      if (lang.js || lang.html) {
        var kwSet = {};
        for (var k = 0; k < KEYWORDS_JS.length; k++) kwSet[KEYWORDS_JS[k]] = true;
        escaped = escaped.replace(/\b([a-zA-Z_$][\w$]*)\b/g, function(m, word) {
          if (kwSet[word]) return '<span class="hl-keyword">' + word + '</span>';
          return m;
        });

        // 字符串（单引号、双引号、模板字符串�?        escaped = escaped.replace(/("(?:[^"\\]|\\.)*")/g, '<span class="hl-string"></span>');
        escaped = escaped.replace(/('(?:[^'\\]|\\.)*')/g, '<span class="hl-string"></span>');
        // 数字
        escaped = escaped.replace(/\b(\d+\.?\d*)\b/g, '<span class="hl-number"></span>');
      }
    }

    // 将换行转�?<br>
    return escaped;
  }

  function escapeHtml(text) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
  }

  // ===== 初始�?=====
  function init() {
    editorEl = document.getElementById('codeEditor');
    lineNumbersEl = document.getElementById('lineNumbers');
    highlightLayerEl = document.getElementById('highlightLayer');
    fileTreeContentEl = document.getElementById('fileTreeContent');
    editorTabsEl = document.getElementById('editorTabs');
    aiPanelContentEl = document.getElementById('aiPanelContent');
    terminalContentEl = document.getElementById('terminalContent');
    terminalInputEl = document.getElementById('terminalInput');

    if (!editorEl) return;

    renderFileTree();
    setupEditor();
    setupTerminal();
    setupCodeActions();
    setupSnippets();
    setupEvolve();
    setupRun();
    setupAuto();

    // 默认打开 welcome
    showWelcome();
    setupFullscreenButton();
    setupElectronFS();
    patchOpenFile();
    patchSaveFile();

    // Ctrl+S 保存
    document.addEventListener('keydown', function(e) {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        saveFile();
      }
    });
  }

  // ===== 欢迎页面 =====
  function showWelcome() {
    var welcomeCode = '/*\n * TriGenClaw - Code Assistant\n * =================================\n * \n * Welcome! This is your code editing workspace.\n * \n * Features:\n * - Syntax highlighting for JS, HTML, CSS, JSON\n * - Real-time line number sync\n * - File tree with project navigation\n * - AI-powered code review, explanation, and optimization\n * - Built-in terminal simulator\n * - Ctrl+S to save and trigger AI review\n * \n * Getting Started:\n * 1. Click a file in the file tree to open it\n * 2. Edit code in the editor\n * 3. Click "Review", "Explain", or "Optimize" for AI analysis\n * 4. Use the terminal at the bottom-right panel\n */\n\nfunction greet(name) {\n  console.log("Hello, " + name + "!");\n  return "Welcome to TriGenClaw";\n}\n\n// Try editing this code and click "Review"!\ngreet("Developer");\n\n// Example: async function\nasync function fetchData(url) {\n  try {\n    const response = await fetch(url);\n    const data = await response.json();\n    return data;\n  } catch (error) {\n    console.error("Failed:", error);\n    return null;\n  }\n}';
    setEditorContent('welcome.js', welcomeCode);
    currentFileName = 'welcome.js';
  }

  // ===== 文件树渲�?=====
  function renderFileTree() {
    if (!fileTreeContentEl) return;
    fileTreeContentEl.innerHTML = '';
    renderTreeNodes(FILE_TREE, 0);
  }

  function renderTreeNodes(nodes, depth) {
    for (var i = 0; i < nodes.length; i++) {
      var node = nodes[i];
      var item = document.createElement('div');
      item.className = 'file-tree-item' + (node.type === 'directory' ? ' directory' : '') + (node.highlight ? ' active' : '');
      item.style.paddingLeft = (12 + depth * 16) + 'px';
      item.setAttribute('data-path', node.name);

      if (node.type === 'directory') {
        // 展开箭头
        var arrow = document.createElement('span');
        arrow.className = 'tree-arrow' + (node.expanded ? ' expanded' : '');
        arrow.innerHTML = '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>';
        arrow.addEventListener('click', function(e) {
          e.stopPropagation();
          toggleDir(this);
        });
        item.appendChild(arrow);

        var icon = document.createElement('span');
        icon.className = 'tree-icon';
        icon.innerHTML = node.expanded
          ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ffa502" stroke-width="1.5"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>'
          : '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ffa502" stroke-width="1.5"><path d="M3 7v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-6l-2-2H5a2 2 0 0 0-2 2z"/></svg>';
        item.appendChild(icon);
      } else {
        // 文件图标
        var icon = document.createElement('span');
        icon.className = 'tree-icon';
        var ext = node.name.split('.').pop();
        var iconColor = '#555577';
        if (ext === 'html' || ext === 'htm') iconColor = '#e44d26';
        else if (ext === 'css') iconColor = '#264de4';
        else if (ext === 'js') iconColor = '#f7df1e';
        else if (ext === 'json') iconColor = '#00d4ff';
        icon.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="' + iconColor + '" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>';
        item.appendChild(icon);
      }

      var nameSpan = document.createElement('span');
      nameSpan.className = 'tree-name';
      nameSpan.textContent = node.name;
      item.appendChild(nameSpan);

      item.addEventListener('click', function(e) {
        if (this.classList.contains('directory')) return;
        var path = getNodePath(this);
        openFile(path);
      });

      fileTreeContentEl.appendChild(item);

      // 递归渲染子节�?      if (node.type === 'directory' && node.expanded && node.children) {
        renderTreeNodes(node.children, depth + 1);
      }
    }
  }

  function getNodePath(el) {
    var parts = [];
    var current = el;
    while (current && current.classList.contains('file-tree-item')) {
      parts.unshift(current.getAttribute('data-path'));
      current = current.parentElement ? current.parentElement.previousElementSibling : null;
      if (!current || !current.classList.contains('file-tree-item')) {
        // 尝试找到父级目录�?        var parent = el.parentElement;
        while (parent && !parent.classList.contains('file-tree-content')) {
          if (parent.classList.contains('file-tree-item') && parent.classList.contains('directory')) {
            parts.unshift(parent.getAttribute('data-path'));
            break;
          }
          parent = parent.parentElement;
        }
        break;
      }
    }
    return parts.join('/');
  }

  function toggleDir(arrowEl) {
    var item = arrowEl.closest('.file-tree-item');
    if (!item) return;
    var expanded = arrowEl.classList.toggle('expanded');
    // 找到对应目录节点
    var path = item.getAttribute('data-path');
    toggleNode(FILE_TREE, path, expanded);
    // 重新渲染
    renderFileTree();
  }

  function toggleNode(nodes, name, expanded) {
    for (var i = 0; i < nodes.length; i++) {
      if (nodes[i].name === name && nodes[i].type === 'directory') {
        nodes[i].expanded = expanded;
        return true;
      }
      if (nodes[i].children && toggleNode(nodes[i].children, name, expanded)) return true;
    }
    return false;
  }

  // ===== 编辑�?=====
  function setupEditor() {
    if (!editorEl) return;

    // 输入事件 - 同步行号和高�?    editorEl.addEventListener('input', function() {
      syncLineNumbers();
      syncHighlight();
    });

    editorEl.addEventListener('scroll', function() {
      syncScroll();
    });

    // Tab 键插入空�?    editorEl.addEventListener('keydown', function(e) {
      if (e.key === 'Tab') {
        e.preventDefault();
        var tabSize = parseInt(document.getElementById('tabSizeSelect')?.value || '4');
        var spaces = ' '.repeat(tabSize);
        var start = this.selectionStart;
        var end = this.selectionEnd;
        this.value = this.value.substring(0, start) + spaces + this.value.substring(end);
        this.selectionStart = this.selectionEnd = start + tabSize;
        syncLineNumbers();
        syncHighlight();
      }
    });

    // 初始同步
    syncLineNumbers();
    syncHighlight();

    // 监听编辑器字体大小变�?    var fontSizeRange = document.getElementById('editorFontSizeRange');
    if (fontSizeRange) {
      fontSizeRange.addEventListener('input', function() {
        var size = this.value + 'px';
        document.getElementById('editorFontSizeLabel').textContent = size;
        editorEl.style.fontSize = size;
        lineNumbersEl.style.fontSize = size;
        syncLineNumbers();
      });
    }

    // 监听 Tab 大小变化
    var tabSizeSelect = document.getElementById('tabSizeSelect');
    if (tabSizeSelect) {
      tabSizeSelect.addEventListener('change', function() {
        editorEl.style.tabSize = this.value;
        editorEl.style.MozTabSize = this.value;
      });
    }
  }

  /** 同步行号 */
  function syncLineNumbers() {
    if (!editorEl || !lineNumbersEl) return;
    var lines = editorEl.value.split('\n');
    var html = '';
    for (var i = 0; i < lines.length; i++) {
      html += '<div class="line-number">' + (i + 1) + '</div>';
    }
    lineNumbersEl.innerHTML = html;
  }

  /** 同步滚动 */
  function syncScroll() {
    if (lineNumbersEl && editorEl) {
      lineNumbersEl.scrollTop = editorEl.scrollTop;
    }
    if (highlightLayerEl && editorEl) {
      highlightLayerEl.scrollTop = editorEl.scrollTop;
    }
  }

  /** 同步语法高亮 */
  function syncHighlight() {
    if (!highlightLayerEl || !editorEl) return;
    var code = editorEl.value;
    var highlighted = highlightCode(code, currentFileName);
    highlightLayerEl.innerHTML = highlighted;
  }

  /** 设置编辑器内�?*/
  function setEditorContent(content, fileName) {
    if (!editorEl) return;
    editorEl.value = content;
    currentFileName = fileName || '';
    syncLineNumbers();
    syncHighlight();
    updateActiveTab(fileName);
  }

  /** 更新活跃标签 */
  function updateActiveTab(fileName) {
    if (!editorTabsEl) return;
    var tabs = editorTabsEl.querySelectorAll('.tab');
    for (var i = 0; i < tabs.length; i++) {
      tabs[i].classList.remove('active');
    }
    // 更新或添加标�?    var existingTab = editorTabsEl.querySelector('.tab[data-file="' + fileName + '"]');
    if (existingTab) {
      existingTab.classList.add('active');
    } else {
      // 如果已经�?welcome 标签，替换它
      var welcomeTab = editorTabsEl.querySelector('.tab[data-file="welcome"]');
      if (welcomeTab) {
        welcomeTab.setAttribute('data-file', fileName);
        welcomeTab.querySelector('span').textContent = fileName;
        welcomeTab.classList.add('active');
      } else {
        var tab = document.createElement('div');
        tab.className = 'tab active';
        tab.setAttribute('data-file', fileName);
        tab.innerHTML = '<span>' + fileName + '</span>';
        editorTabsEl.appendChild(tab);
      }
    }

    // 更新文件树高�?    var items = fileTreeContentEl?.querySelectorAll('.file-tree-item');
    if (items) {
      for (var j = 0; j < items.length; j++) {
        items[j].classList.remove('active');
        if (items[j].getAttribute('data-path') === fileName) {
          items[j].classList.add('active');
        }
      }
    }
  }

  /** 打开文件 */
  function openFile(path) {
    var fileName = path.split('/').pop();
    if (FILE_CONTENTS[fileName] !== undefined) {
      setEditorContent(FILE_CONTENTS[fileName], fileName);
    } else if (fileName === 'welcome.js') {
      showWelcome();
    setupFullscreenButton();
    setupElectronFS();
    patchOpenFile();
    patchSaveFile();
    } else {
      setEditorContent('// ' + fileName + '\n// File not loaded. Click a file from the tree.', fileName);
    }
    currentFileName = fileName;

    // 显示 Toast
    NexusUI.toast('已打开: ' + fileName, 'info');
  }

  // ===== 保存文件 =====
  function saveFile() {
    if (!editorEl || !currentFileName) return;
    var code = editorEl.value;
    FILE_CONTENTS[currentFileName] = code;
    NexusUI.toast('已保�? ' + currentFileName, 'success');

    // 触发 AI 审查
    triggerReview(code);

    // 保存�?localStorage
    try {
      var savedFiles = JSON.parse(localStorage.getItem('nx_saved_files') || '{}');
      savedFiles[currentFileName] = code;
      localStorage.setItem('nx_saved_files', JSON.stringify(savedFiles));
    } catch (e) {}
  }

  // ===== 代码操作 =====
  function setupCodeActions() {
    var reviewBtn = document.getElementById('codeReviewBtn');
    var explainBtn = document.getElementById('codeExplainBtn');
    var optimizeBtn = document.getElementById('codeOptimizeBtn');
    var saveBtn = document.getElementById('codeSaveBtn');

    if (reviewBtn) reviewBtn.addEventListener('click', function() { analyzeCode('review'); });
    if (explainBtn) explainBtn.addEventListener('click', function() { analyzeCode('explain'); });
    if (optimizeBtn) optimizeBtn.addEventListener('click', function() { analyzeCode('optimize'); });
    if (saveBtn) saveBtn.addEventListener('click', saveFile);

    var refreshBtn = document.getElementById('fileTreeRefresh');
    if (refreshBtn) refreshBtn.addEventListener('click', function() {
      renderFileTree();
      NexusUI.toast('文件树已刷新', 'info');
    });
  }

  /** 触发审查（保存时自动调用�?*/
  function triggerReview(code) {
    if (!code || code.trim().length < 10) return;
    // 使用非流�?API 审查
    showAILoading();
    NexusChat.analyzeCode(code, 'review', function(err, content) {
      if (err) {
        showAIResult('保存时自动审查失�? ' + err);
      } else {
        showAIResult('【保存时自动审查】\n\n' + content);
        NexusUI.toast('代码审查完成', 'info');
      }
    });
  }

  /** 分析代码 */
  function analyzeCode(action) {
    if (!editorEl) return;
    var code = editorEl.value;
    if (!code || !code.trim()) {
      NexusUI.toast('编辑器中没有代码', 'error');
      return;
    }

    showAILoading();
    NexusChat.analyzeCode(code, action, function(err, content) {
      if (err) {
        showAIResult('API 请求失败: ' + err + '\n\n（这是模拟结果，请检�?API 配置�?);
        // 提供模拟结果
        showSimulatedResult(action, code);
      } else {
        showAIResult(content);
      }
      NexusUI.toast('分析完成', 'success');
    });
  }

  /** 显示模拟结果（API 不可用时回退�?*/
  function showSimulatedResult(action, code) {
    var lines = code.split('\n').length;
    var results = {
      review: '## 代码审查报告\n\n**文件概况**\n- 代码行数: ' + lines + '\n- 复杂�? 低\n\n' +
        '### 发现的问题\n\n' +
        '1. **代码格式** �?建议统一缩进风格，确保一致性\n' +
        '2. **错误处理** �?建议增加 try-catch 处理潜在异常\n' +
        '3. **注释** �?建议为关键逻辑添加中文注释\n\n' +
        '### 改进建议\n\n' +
        '- 使用 const 替代 var 以提高代码可预测性\n' +
        '- 考虑提取重复逻辑为独立函数\n' +
        '- 添加输入验证和边界检查\n\n' +
        '_提示：配�?API Key 后可获得真实 AI 审查结果_',
      explain: '## 代码解释\n\n**代码概述**\n' +
        '这段代码�?' + lines + ' 行，主要实现以下功能：\n\n' +
        '### 核心逻辑\n' +
        '1. 定义了变量和函数\n' +
        '2. 包含了基本的控制流（循环/条件）\n' +
        '3. 使用了标�?JavaScript 语法\n\n' +
        '### 关键部分\n\n' +
        '主要逻辑位于函数定义和调用部分，' +
        '代码结构清晰，适合进一步扩展。\n\n' +
        '_提示：配�?API Key 后可获得真实 AI 解释_',
      optimize: '## 代码优化建议\n\n**当前代码评价**\n' +
        '- 代码行数: ' + lines + '\n' +
        '- 可读�? 良好\n' +
        '- 性能: 无显著瓶颈\n\n' +
        '### 优化方案\n\n' +
        '1. �?var 替换�?const/let，提升作用域安全性\n' +
        '2. 使用现代语法简化代码（箭头函数、解构等）\n' +
        '3. 添加 JSDoc 注释提高可维护性\n\n' +
        '### 优化后代码\n\n' +
        '`javascript\n' +
        '// 优化版代码将在此显示\n' +
        '// 配置 API Key 后可获得真实优化建议\n' +
        '`\n\n' +
        '_提示：配�?API Key 后可获得真实 AI 优化_'
    };
    showAIResult(results[action] || results.review);
  }

  /** 显示 AI 加载�?*/
  function showAILoading() {
    var placeholder = document.querySelector('.ai-panel-placeholder');
    var content = aiPanelContentEl;
    if (placeholder) placeholder.classList.add('hidden');
    if (content) {
      content.classList.remove('hidden');
      content.innerHTML = '<div class="thinking-indicator"><span></span><span></span><span></span></div>';
    }
  }

  /** 显示 AI 结果 */
  function showAIResult(text) {
    var placeholder = document.querySelector('.ai-panel-placeholder');
    var content = aiPanelContentEl;
    if (placeholder) placeholder.classList.add('hidden');
    if (content) {
      content.classList.remove('hidden');
      // 简�?Markdown 渲染
      var html = renderMarkdown(text);
      content.innerHTML = '<div class="ai-analysis-message"><div class="analysis-text">' + html + '</div></div>';
    }
  }

  /** 简�?Markdown 渲染 */
  function renderMarkdown(text) {
    if (!text) return '';
    var html = escapeHtml(text);
    // 代码�?    html = html.replace(/`(\w*)\n([\s\S]*?)`/g, '<pre><code></code></pre>');
    // 行内代码
    html = html.replace(/([^]+)/g, '<code></code>');
    // 标题
    html = html.replace(/^### (.+)$/gm, '<h4></h4>');
    html = html.replace(/^## (.+)$/gm, '<h3></h3>');
    // 加粗
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong></strong>');
    // 列表
    html = html.replace(/^- (.+)$/gm, '<li></li>');
    html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');
    // 换行
    html = html.replace(/\n/g, '<br>');
    return html;
  }

  // ===== 终端 =====
  function setupTerminal() {
    if (!terminalInputEl) return;

    terminalInputEl.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        var cmd = this.value.trim();
        this.value = '';
        executeCommand(cmd);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (terminalHistory.length > 0) {
          terminalHistoryIndex = Math.max(0, terminalHistoryIndex - 1);
          this.value = terminalHistory[terminalHistoryIndex];
        }
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (terminalHistoryIndex < terminalHistory.length - 1) {
          terminalHistoryIndex++;
          this.value = terminalHistory[terminalHistoryIndex];
        } else {
          terminalHistoryIndex = terminalHistory.length;
          this.value = '';
        }
      }
    });

    // 注册内置命令
    registerCommand('help', function(args) {
      return '可用命令:\n' +
        '  help          - 显示帮助信息\n' +
        '  clear         - 清屏\n' +
        '  ls            - 列出文件\n' +
        '  cat <file>    - 查看文件内容\n' +
        '  pwd           - 显示当前目录\n' +
        '  echo <text>   - 输出文本\n' +
        '  node <code>   - 运行 JavaScript\n' +
        '  npm <args>    - npm 命令（模拟）\n' +
        '  date          - 显示当前时间\n' +
        '  whoami        - 显示当前用户';
    });

    registerCommand('clear', function() { return '__CLEAR__'; });
    registerCommand('ls', function() { return 'trigenclaw/\n  index.html\n  css/\n    style.css\n  js/\n    api.js\n    models.js\n    chat.js\n    code.js\n    ui.js\n    app.js\n  manifest.json\n  sw.js'; });
    registerCommand('pwd', function() { return '/home/TriGen/trigenclaw'; });
    registerCommand('whoami', function() { return 'nexus'; });
    registerCommand('date', function() { return new Date().toLocaleString('zh-CN'); });
    registerCommand('echo', function(args) { return args.join(' '); });

    registerCommand('cat', function(args) {
      var fileName = args[0];
      if (fileName && FILE_CONTENTS[fileName]) {
        return FILE_CONTENTS[fileName];
      }
      return 'cat: ' + (fileName || '') + ': No such file';
    });

    registerCommand('node', function(args) {
      if (args.length === 0) return 'node: missing argument';
      var code = args.join(' ');
      try {
        var result = eval(code);
        return String(result);
      } catch (e) {
        return 'Error: ' + e.message;
      }
    });

    registerCommand('npm', function(args) {
      if (args[0] === 'start') return '> trigenclaw@1.0.0 start\n> Starting dev server...\n\n  Local: http://localhost:3000';
      if (args[0] === 'install') return 'npm install\n+ nexus-deps@1.0.0\nadded 1 package in 2s';
      if (args[0] === 'run' && args[1] === 'build') return '> Building...\n�?Build complete (2.3s)';
      return 'npm: ' + (args.join(' ') || '') + ' (simulated)';
    });

    var clearBtn = document.getElementById('terminalClearBtn');
    if (clearBtn) clearBtn.addEventListener('click', function() {
      if (terminalContentEl) terminalContentEl.innerHTML = '';
    });
  }

  function registerCommand(name, handler) {
    terminalCommands[name] = handler;
  }

  function executeCommand(cmd) {
    if (!cmd) return;
    // 添加到历�?    terminalHistory.push(cmd);
    terminalHistoryIndex = terminalHistory.length;

    // 回显命令
    addTerminalLine('<span class="terminal-prompt">TriGen@studio:~$</span>' + escapeHtml(cmd));

    var parts = cmd.match(/(?:[^\s"']+|"[^"]*"|'[^']*')+/g) || [];
    var commandName = parts[0] || '';
    var args = parts.slice(1).map(function(a) {
      return a.replace(/^["']|["']$/g, '');
    });

    var handler = terminalCommands[commandName];
    if (handler) {
      var result = handler(args);
      if (result === '__CLEAR__') {
        if (terminalContentEl) terminalContentEl.innerHTML = '';
        return;
      }
      var lines = result.split('\n');
      for (var i = 0; i < lines.length; i++) {
        addTerminalLine('<span class="terminal-output">' + escapeHtml(lines[i]) + '</span>');
      }
    } else if (commandName) {
      addTerminalLine('<span class="terminal-output error">' + commandName + ': command not found</span>');
    }

    // 滚动到底�?    if (terminalContentEl) {
      terminalContentEl.scrollTop = terminalContentEl.scrollHeight;
    }
  }

  function addTerminalLine(html) {
    if (!terminalContentEl) return;
    var line = document.createElement('div');
    line.className = 'terminal-line';
    line.innerHTML = html;
    terminalContentEl.appendChild(line);
    terminalContentEl.scrollTop = terminalContentEl.scrollHeight;
  }

  /** 检测是否运行在 Electron 环境 */
  function isElectron() {
    return typeof window !== 'undefined' && window.electronAPI && window.electronAPI.readFile;
  }

  /** 初始�?Electron 原生文件系统 */
  function setupElectronFS() {
    if (!isElectron()) return;
    // 监听 Electron 项目打开事件
    window.electronAPI.onMessage('project:open', function(data) {
      currentProjectPath = data.path;
      NexusUI.toast('Opened project: ' + data.path, 'success');
    });

    window.electronAPI.onMessage('project:tree', function(tree) {
      // 替换文件树为真实项目目录
      if (tree && tree.items) {
        buildFileTreeFromNative(tree.path, tree.items);
      }
    });

    window.electronAPI.onMessage('action', function(action) {
      if (action === 'new-chat') {
        document.querySelector('.nav-item[data-panel="chat"]')?.click();
      } else if (action === 'open-code') {
        document.querySelector('.nav-item[data-panel="code"]')?.click();
      } else if (action === 'open-agent') {
        document.querySelector('.nav-item[data-panel="agent"]')?.click();
      } else if (action === 'save-file') {
        saveFile();
      } else if (action === 'new-file') {
        handleNewFile();
      }
    });

    // 打开文件�?    var folderBtn = document.getElementById('fileTreePanel')?.querySelector('.code-sidebar-header');
    if (folderBtn) {
      var openBtn = document.createElement('button');
      openBtn.className = 'btn-icon';
      openBtn.title = 'Open Folder';
      openBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>';
      openBtn.addEventListener('click', function() {
        window.electronAPI.selectFolder();
      });
      folderBtn.appendChild(openBtn);
    }
  }

  function handleNewFile() {
    var name = prompt('Enter file name:', 'new-file.js');
    if (name) {
      if (!FILE_CONTENTS[name]) {
        FILE_CONTENTS[name] = '';
        // 更新文件�?        var jsDir = findDirNode(FILE_TREE, 'js');
        if (jsDir && jsDir.children) {
          jsDir.children.push({ name: name, type: 'file' });
        }
        renderFileTree();
        openFile(name);
        NexusUI.toast('Created: ' + name, 'success');
      } else {
        NexusUI.toast('File already exists', 'warning');
      }
    }
  }

  function findDirNode(nodes, name) {
    for (var i = 0; i < nodes.length; i++) {
      if (nodes[i].type === 'directory') {
        if (nodes[i].name === name) return nodes[i];
        if (nodes[i].children) {
          var found = findDirNode(nodes[i].children, name);
          if (found) return found;
        }
      }
    }
    return null;
  }

  /** �?Electron 原生目录树构建文件树 */
  function buildFileTreeFromNative(rootPath, items) {
    // 替换内置 FILE_TREE 为原生目录树
    var tree = buildTreeFromItems(rootPath, items);
    if (tree) {
      // 保存原生�?      nativeFileTree = { name: getDirName(rootPath), type: 'directory', expanded: true, children: tree, path: rootPath };
      FILE_TREE = [nativeFileTree];
      renderFileTree();
    }
  }

  function buildTreeFromItems(basePath, items) {
    if (!items) return [];
    var result = [];
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var node = {
        name: item.name,
        type: item.type,
        path: item.path
      };
      if (item.type === 'directory') {
        node.expanded = false;
        node.children = [];
        node.path = item.path;
      }
      result.push(node);
    }
    return result;
  }

  function getDirName(filePath) {
    var parts = filePath.replace(/\\/g, '/').split('/');
    return parts[parts.length - 1] || 'project';
  }

  // 修改 openFile 以支持原�?FS
  var originalOpenFile = null;

  function patchOpenFile() {
    if (!isElectron() || originalOpenFile) return;
    originalOpenFile = openFile;
    openFile = function(path) {
      var fileName = path.split('/').pop();
      // 检查是否是原生路径
      var node = findNodeByPath(FILE_TREE, path);
      if (node && node.path) {
        // 从原�?FS 读取
        window.electronAPI.readFile(node.path).then(function(result) {
          if (result.success) {
            setEditorContent(result.content, fileName);
            currentFileName = fileName;
            currentNativePath = node.path;
          } else {
            setEditorContent('// Error reading file: ' + (result.error || 'unknown'), fileName);
          }
        });
      } else if (FILE_CONTENTS[fileName] !== undefined) {
        setEditorContent(FILE_CONTENTS[fileName], fileName);
        currentNativePath = null;
      } else if (fileName === 'welcome.js') {
        showWelcome();
    setupFullscreenButton();
    setupElectronFS();
    patchOpenFile();
    patchSaveFile();
      } else {
        setEditorContent('// ' + fileName + '\n// File not loaded.', fileName);
        currentNativePath = null;
      }
      currentFileName = fileName;
      NexusUI.toast('Opened: ' + fileName, 'info');
    };
  }

  var nativeFileTree = null;
  var currentNativePath = null;

  function findNodeByPath(nodes, relativePath) {
    var parts = relativePath.split('/');
    function search(list, depth) {
      for (var i = 0; i < list.length; i++) {
        if (list[i].name === parts[depth]) {
          if (depth === parts.length - 1) return list[i];
          if (list[i].children) return search(list[i].children, depth + 1);
        }
      }
      return null;
    }
    return search(nodes, 0);
  }

  // 修改 saveFile 以支持原�?FS
  var originalSaveFile = null;

  function patchSaveFile() {
    if (!isElectron() || originalSaveFile) return;
    originalSaveFile = saveFile;
    saveFile = function() {
      if (!editorEl || !currentFileName) return;

      if (typeof NexusPlugins !== 'undefined' && NexusPlugins.dispatch) {
      NexusPlugins.dispatch('onFileSave', { filename: currentFileName });
    }

    if (currentNativePath) {
        // 写入原生 FS
        window.electronAPI.writeFile(currentNativePath, editorEl.value).then(function(result) {
          if (result.success) {
            NexusUI.toast('Saved: ' + currentFileName + ' (native)', 'success');
          } else {
            NexusUI.toast('Save failed: ' + (result.error || 'unknown'), 'error');
          }
        });
      } else {
        // 回退到内置存�?        FILE_CONTENTS[currentFileName] = editorEl.value;
        NexusUI.toast('Saved: ' + currentFileName, 'success');
        try {
          var savedFiles = JSON.parse(localStorage.getItem('nx_saved_files') || '{}');
          savedFiles[currentFileName] = editorEl.value;
          localStorage.setItem('nx_saved_files', JSON.stringify(savedFiles));
        } catch (e) {}
      }
    };
  }

  function setupFullscreenButton() {
    var b = document.createElement('button');
    b.className = 'btn-icon editor-fs-btn';
    b.title = 'Fullscreen';
    b.textContent = '\u26F6';
    b.addEventListener('click', function() { document.querySelector('.code-panel-body').classList.toggle('fullscreen'); });
    var t = document.getElementById('editorTabs');
    if (t) t.appendChild(b);
  }

  // ===== 公共 API =====
  return {
    init: init,
    openFile: openFile,
    saveFile: saveFile,
    renderFileTree: renderFileTree
  };
})();


