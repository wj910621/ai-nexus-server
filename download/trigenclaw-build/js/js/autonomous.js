/* ========================================
   Autonomous Coding Agent - 自主编程智能体
   理解代码库 → 规划实现 → 逐文件编码 → 用户审批
   Enhanced with streaming, file save, git integration
   ======================================== */
var NexusAuto = (function() {
  'use strict';

  var _plan = [];
  var _taskHistory = [];

  /**
   * 开始实现特性
   */
  function start(request) {
    _plan = [];
    var editor = document.getElementById('codeEditor');
    var fileName = '';
    var activeTab = document.querySelector('.tab.active');
    if (activeTab) fileName = activeTab.getAttribute('data-file') || '';
    var currentCode = editor ? editor.value : '';
    var context = 'Project: TriGenClaw\n\n';
    context += 'File tree:\n' + getFileTreeSummary() + '\n\n';
    context += 'Current file: ' + fileName + '\n';
    context += 'Content:\n' + currentCode.substring(0, 3000) + '\n';

    var prompt = 'You are an AI developer. Implement this feature request.\n';
    prompt += 'Codebase:\n' + context + '\n';
    prompt += 'Feature: ' + request + '\n\n';
    prompt += 'Output format (CRITICAL - use EXACTLY this format):\n';
    prompt += 'For each file that needs to change:\nFILE: relative/path\n`\n[complete new file content]\n`\n';
    prompt += 'Start with a short plan, then show each file change.';

    var container = document.getElementById('aiPanelContent');
    if (container) {
      container.classList.remove('hidden');
      container.innerHTML = '<div class="thinking-indicator"><span></span><span></span><span></span></div>';
    }

    _taskHistory.push({ request: request, time: new Date().toISOString() });

    // 先切换到 AI 面板
    var aiPanelBtn = document.querySelector('[data-panel="aiPanel"]');
    if (aiPanelBtn) aiPanelBtn.click();

    // 使用流式调用获取规划
    var model = (typeof NexusModels !== 'undefined') ? NexusModels.getCurrentModel() : 'deepseek-chat';
    var accumulated = '';

    if (typeof NexusAPI !== 'undefined' && NexusAPI.chatStream) {
      NexusAPI.chatStream(model, [
        { role: 'system', content: 'You implement features by reading codebases and generating file changes. Always output in FILE:/``` format.' },
        { role: 'user', content: prompt }
      ], function(chunk) {
        accumulated += chunk;
        if (container && container.querySelector('.thinking-indicator')) {
          container.querySelector('.thinking-indicator').outerHTML = '<div style="font-size:0.78rem;color:var(--text-secondary);padding:8px">Generating plan...</div>';
        }
      }, function() {
        // onDone
        processResponse(accumulated);
        if (typeof NexusUI !== 'undefined' && NexusUI.toast) {
          NexusUI.toast('Implementation plan ready', 'success');
        }
      }, function(err) {
        if (container) container.innerHTML = '<div class="ai-analysis-error">Error: ' + (err.message || err) + '</div>';
      }, { temperature: 0.3, max_tokens: 16384 });
    } else {
      // Fallback: 非流式
      NexusAPI.chat(model, [
        { role: 'system', content: 'You implement features by reading codebases and generating file changes.' },
        { role: 'user', content: prompt }
      ], { temperature: 0.3, max_tokens: 16384 }).then(function(resp) {
        processResponse(resp);
        if (typeof NexusUI !== 'undefined' && NexusUI.toast) {
          NexusUI.toast('Implementation plan ready', 'success');
        }
      }).catch(function(err) {
        if (container) container.innerHTML = '<div class="ai-analysis-error">Error: ' + err + '</div>';
      });
    }
  }

  function getFileTreeSummary() {
    var files = [
      'index.html', 'manifest.json', 'sw.js',
      'css/style.css',
      'js/api.js', 'js/models.js', 'js/chat.js', 'js/code.js',
      'js/agent.js', 'js/skills.js', 'js/knowledge.js', 'js/plugin.js',
      'js/mcp-client.js', 'js/music.js', 'js/model3d.js',
      'js/autonomous.js', 'js/ui.js', 'js/app.js',
      'main.js', 'preload.js', 'package.json'
    ];
    var tree = 'trigenclaw/\n';
    tree += '  index.html (SPA entry)\n';
    tree += '  css/\n    style.css\n';
    tree += '  js/\n';
    for (var i = 0; i < files.length; i++) {
      if (files[i].indexOf('/') < 0 && files[i].indexOf('.') > 0 && files[i] !== 'index.html') {
        tree += '    ' + files[i] + '\n';
      }
    }
    tree += '  manifest.json\n  sw.js\n  package.json\n';
    return tree;
  }

  function processResponse(response) {
    _plan = [];
    var lines = response.split('\n');
    var currentFile = '';
    var currentCode = '';
    var inBlock = false;
    var summary = [];
    var inSummary = true;

    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      var fileMatch = line.match(/^FILE:\s*(.+)/i);
      var codeMatch = line.match(/^```/);

      if (fileMatch) {
        if (currentFile && currentCode) {
          _plan.push({ file: currentFile, code: currentCode });
        }
        currentFile = fileMatch[1].trim();
        currentCode = '';
        inBlock = false;
        inSummary = false;
      } else if (codeMatch && !inBlock) {
        inBlock = true;
      } else if (codeMatch && inBlock) {
        inBlock = false;
        if (currentFile) {
          _plan.push({ file: currentFile, code: currentCode });
          currentFile = '';
          currentCode = '';
        }
      } else if (inBlock) {
        currentCode += (currentCode ? '\n' : '') + line;
      } else if (inSummary && !fileMatch) {
        summary.push(line);
      }
    }
    if (currentFile && currentCode) {
      _plan.push({ file: currentFile, code: currentCode });
    }

    showPlan(response, summary, _plan);
  }

  function showPlan(response, summary, plan) {
    var container = document.getElementById('aiPanelContent');
    if (!container) return;

    var html = '<div class="auto-plan">';
    html += '<h3 style="color:var(--primary);margin-bottom:8px">Implementation Plan</h3>';
    html += '<p style="color:var(--text-secondary);font-size:13px;margin-bottom:12px">';
    html += (summary.length ? summary.join('\n').substring(0, 500).replace(/\n/g, '<br>') : '') + '</p>';

    if (plan.length === 0) {
      html += '<p style="color:var(--text-muted)">No file changes detected. Raw response below:</p>';
      html += '<hr style="border-color:var(--border);margin:8px 0">';
      html += '<div style="font-size:13px;color:var(--text-secondary);line-height:1.6">';
      html += escapeHtml(response).replace(/\n/g, '<br>');
      html += '</div></div>';
      container.innerHTML = html;
      return;
    }

    html += '<div class="auto-files">';
    for (var i = 0; i < plan.length; i++) {
      var lineCount = plan[i].code.split('\n').length;
      html += '<div class="auto-file-item">';
      html += '<div class="auto-file-header">';
      html += '<span class="auto-file-name">' + plan[i].file + '</span>';
      html += '<span class="auto-file-lines">' + lineCount + ' lines</span>';
      html += '<button class="btn btn-sm btn-primary auto-apply" data-idx="' + i + '">Apply</button>';
      html += '</div>';
      html += '<pre class="auto-preview"><code>' + escapeHtml(plan[i].code.substring(0, 300)) + '</code></pre>';
      html += '</div>';
    }
    html += '</div>';

    if (plan.length > 1) {
      html += '<div class="auto-actions">';
      html += '<button class="btn btn-sm btn-primary" id="autoApplyAll">Apply All</button>';
      html += '<button class="btn btn-sm btn-ghost" id="autoRejectAll">Reject All</button>';
      html += '</div>';
    }

    html += '</div>';
    container.innerHTML = html;

    container.querySelectorAll('.auto-apply').forEach(function(btn) {
      btn.addEventListener('click', function() {
        var idx = parseInt(this.getAttribute('data-idx'));
        applyChange(idx);
      });
    });
    var applyAllBtn = document.getElementById('autoApplyAll');
    if (applyAllBtn) {
      applyAllBtn.addEventListener('click', function() {
        for (var j = 0; j < _plan.length; j++) applyChange(j);
        if (typeof NexusUI !== 'undefined' && NexusUI.toast) {
          NexusUI.toast('All ' + _plan.length + ' changes applied', 'success');
        }
      });
    }
    var rejectAllBtn = document.getElementById('autoRejectAll');
    if (rejectAllBtn) {
      rejectAllBtn.addEventListener('click', function() {
        _plan = [];
        container.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:40px">All changes rejected.</p>';
        if (typeof NexusUI !== 'undefined' && NexusUI.toast) {
          NexusUI.toast('Changes rejected', 'info');
        }
      });
    }
  }

  function applyChange(index) {
    if (index < 0 || index >= _plan.length) return;
    var change = _plan[index];
    var fileName = change.file.split('/').pop();

    // Try to open via NexusCode
    if (typeof NexusCode !== 'undefined' && NexusCode.openFile) {
      NexusCode.openFile(fileName);
    }

    // Set content in editor
    var editor = document.getElementById('codeEditor');
    if (editor) {
      editor.value = change.code;
      editor.dispatchEvent(new Event('input'));
    }

    if (typeof NexusUI !== 'undefined' && NexusUI.toast) {
      NexusUI.toast('Applied: ' + fileName, 'success');
    }
  }

  function escapeHtml(t) {
    if (!t) return '';
    var d = document.createElement('div');
    d.appendChild(document.createTextNode(t));
    return d.innerHTML;
  }

  return {
    start: start,
    applyChange: applyChange
  };
})();
