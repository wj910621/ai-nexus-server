/* ========================================
   UI 交互模块 - Toast、面板切换、快捷键
   ======================================== */
var NexusUI = (function() {
  'use strict';
  var init, showToast, switchPanel, renderChatMessages, renderHistoryList, setupAPIProviders;
  // 所有关键函数提前声明，防止 IIFE 中途报错时 return 访问到未定义变量

  // ===== Toast 通知 =====
  function showToast(message, type, duration) {
    type = type || 'info';
    duration = duration || 3000;
    var container = document.getElementById('toastContainer');
    if (!container) return;

    var toast = document.createElement('div');
    toast.className = 'toast ' + type;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(function() {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 0.3s ease';
      setTimeout(function() {
        if (toast.parentElement) toast.parentElement.removeChild(toast);
      }, 300);
    }, duration);
  }

  // ===== 面板切换 =====
  var currentPanel = 'chat';

  function switchPanel(panelName) {
    // 隐藏所有面�?
    var panels = document.querySelectorAll('.panel');
    for (var i = 0; i < panels.length; i++) {
      panels[i].classList.remove('active');
    }

    // 取消所有导航选中
    var navItems = document.querySelectorAll('.nav-item');
    for (var j = 0; j < navItems.length; j++) {
      navItems[j].classList.remove('active');
    }

    // 显示目标面板
    var targetPanel = document.getElementById(panelName + 'Panel');
    if (targetPanel) {
      targetPanel.classList.add('active');
      currentPanel = panelName;
    }

    // 高亮导航
    var navItem = document.querySelector('.nav-item[data-panel="' + panelName + '"]');
    if (navItem) navItem.classList.add('active');

    if (typeof NexusPlugins !== 'undefined' && NexusPlugins.dispatch) {
      NexusPlugins.dispatch('onPanelSwitch', panelName);
    }

    // 面板特定初始�?
    if (panelName === 'code' && typeof NexusCode.init === 'function') {
      setTimeout(function() { NexusCode.init(); }, 50);
    }
    if (panelName === 'agent' && typeof NexusAgent.init === 'function') {
      setTimeout(function() { NexusAgent.init(); }, 50);
    }
    if (panelName === 'skills' && typeof NexusSkills.init === 'function') {
      setTimeout(function() { NexusSkills.init(); }, 50);
    }
    if (panelName === 'knowledge' && typeof NexusKnowledge.init === 'function') {
      setTimeout(function() { NexusKnowledge.init(); }, 50);
    }
  }

  // ===== 模型下拉菜单 =====
  var modelDropdownOpen = false;

  function toggleModelDropdown() {
    var dropdown = document.getElementById('modelDropdown');
    if (!dropdown) return;
    modelDropdownOpen = !modelDropdownOpen;
    if (modelDropdownOpen) {
      dropdown.classList.remove('hidden');
      renderModelList('');
      setTimeout(function() {
        document.getElementById('modelSearchInput')?.focus();
      }, 50);
    } else {
      dropdown.classList.add('hidden');
    }
  }

  function renderModelList(query) {
    var container = document.getElementById('modelGroups');
    if (!container) return;
    var groups = query ? NexusModels.searchModels(query) : NexusModels.getGroups();
    var currentModel = NexusModels.getCurrentModel();

    var html = '';
    for (var g = 0; g < groups.length; g++) {
      var group = groups[g];
      html += '<div class="model-group">';
      html += '<div class="model-group-title">' + escapeHtml(group.name) + '</div>';
      for (var m = 0; m < group.models.length; m++) {
        var model = group.models[m];
        var selected = model.id === currentModel ? ' selected' : '';
        html += '<div class="model-option' + selected + '" data-model="' + escapeHtml(model.id) + '">';
        html += '<span class="model-name">' + escapeHtml(model.name) + '</span>';
        if (model.free) html += '<span class="model-free">免费</span>';
        html += '<span class="model-provider">' + escapeHtml(model.provider || group.provider) + '</span>';
        html += '</div>';
      }
      html += '</div>';
    }
    container.innerHTML = html;
    addCopyCodeButtons(container);

    // 绑定点击事件
    var options = container.querySelectorAll('.model-option');
    for (var i = 0; i < options.length; i++) {
      (function(opt) {
        opt.addEventListener('click', function() {
          var modelId = this.getAttribute('data-model');
          NexusModels.setCurrentModel(modelId);
          document.getElementById('currentModelName').textContent = modelId;
          document.getElementById('modelIndicator').textContent = '模型: ' + modelId;
          closeModelDropdown();
          showToast('已切换至 ' + modelId, 'info');
        });
      })(options[i]);
    }
  }

  function closeModelDropdown() {
    modelDropdownOpen = false;
    var dropdown = document.getElementById('modelDropdown');
    if (dropdown) dropdown.classList.add('hidden');
  }

  function escapeHtml(text) {
    if (!text) return '';
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
  }

  // ===== 历史面板 =====
  var historyOpen = false;

  function toggleHistory() {
    // Wire up search input
    var searchInput = document.getElementById("historySearchInput");
    if (searchInput) {
      searchInput.addEventListener("input", function() {
        renderHistoryList();
      });

    }
    var panel = document.getElementById('historyPanel');
    if (!panel) return;
    historyOpen = !historyOpen;
    panel.classList.toggle('open', historyOpen);
    if (historyOpen) renderHistoryList();
  }

  function renderHistoryList() {
  var _pinnedIds = JSON.parse(localStorage.getItem('nx_pinned_convs') || '[]');
  function _isPinned(id) { return _pinnedIds.indexOf(id) >= 0; }
  function _togglePin(id) {
    var idx = _pinnedIds.indexOf(id);
    if (idx >= 0) _pinnedIds.splice(idx, 1); else _pinnedIds.unshift(id);
    localStorage.setItem('nx_pinned_convs', JSON.stringify(_pinnedIds));
    renderHistoryList();
  }
    var container = document.getElementById('historyList');
    if (!container) return;
    var list = NexusChat.getHistoryList();
    var searchInput = document.getElementById('historySearchInput');
    var query = searchInput ? searchInput.value.trim().toLowerCase() : '';

    if (list.length === 0 && !query) {
      container.innerHTML = '<div class="text-muted text-center p-12">暂无对话历史</div>';
      return;
    }

    // 搜索过滤
    var filtered = query ? [] : list;
    if (query) {
      for (var i = 0; i < list.length; i++) {
        var matchTitle = (list[i].title || '').toLowerCase().indexOf(query) >= 0;
        var matchContent = false;
        var snippet = '';
        if (list[i].messages) {
          for (var m = 0; m < list[i].messages.length; m++) {
            var content = (list[i].messages[m].content || '').toLowerCase();
            if (content.indexOf(query) >= 0) {
              matchContent = true;
              var idx = content.indexOf(query);
              var start = Math.max(0, idx - 20);
              var end = Math.min(content.length, idx + query.length + 30);
              snippet = (start > 0 ? '...' : '') + escapeHtml(list[i].messages[m].content.slice(start, end));
              break;
            }
          }
        }
        if (matchTitle || matchContent) {
          filtered.push({ conversation: list[i], snippet: snippet });
        }
      }
    } else {
      for (var k = 0; k < list.length; k++) {
        filtered.push({ conversation: list[k], snippet: '' });
      }
    }

    if (filtered.length === 0) {
      container.innerHTML = '<div class="text-muted text-center p-12">No results for "' + escapeHtml(query) + '"</div>';
      return;
    }

    // Show search count if searching
    var html = '';
    if (query) {
      html += '<div class="history-search-count">' + filtered.length + ' of ' + list.length + ' matched</div>';
    }

    filtered.sort(function(a,b) { var pa=_isPinned(a.conversation.id)?1:0; var pb=_isPinned(b.conversation.id)?1:0; return pb-pa; });
    for (var n = 0; n < filtered.length; n++) {
      var conv = filtered[n].conversation;
      var snip = filtered[n].snippet;
      html += '<div class="history-item" data-id="' + conv.id + '">';
      html += '<div class="history-item-content">';
      html += '<span class="history-title">' + escapeHtml(conv.title || 'New Chat') + '</span>';
      if (snip) {
        html += '<span class="history-snippet">' + snip + '</span>';
      }
      html += '</div>';
      html += '<button class="history-del" data-id="' + conv.id + '" title="Delete">�?/button>';
      html += '</div>';
    }
    container.innerHTML = html;
    addCopyCodeButtons(container);

    // Bind events
    var items = container.querySelectorAll('.history-item');
    for (var j = 0; j < items.length; j++) {
      (function(item) {
        item.addEventListener('click', function(e) {
          if (e.target.classList.contains('history-del')) return;
          var id = this.getAttribute('data-id');
          NexusChat.loadChat(id);
          renderChatMessages();
          toggleHistory();
          showToast('Switched conversation', 'info');
        });

        var delBtn = item.querySelector('.history-del');
        if (delBtn) {
          delBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            var id = this.getAttribute('data-id');
            NexusChat.deleteHistory(id);
            renderHistoryList();
            renderChatMessages();
            showToast('Deleted', 'info');
          });
        }
      })(items[j]);
    var pinBtns = container.querySelectorAll('.history-pin');
    for (var p = 0; p < pinBtns.length; p++) {
      (function(btn) {
        btn.addEventListener('click', function(e) {
          e.stopPropagation();
          _togglePin(this.getAttribute('data-id'));
        });
      })(pinBtns[p]);
    }
  }

  // ===== 对话消息渲染 =====
  function renderChatMessages() {
    var container = document.getElementById('chatMessages');
    if (!container) return;
    var messages = NexusChat.getMessages();

    if (messages.length === 0) {
      container.innerHTML = '<div class="welcome-message">' +
        '<div class="welcome-icon"><svg width="48" height="48" viewBox="0 0 48 48" fill="none"><circle cx="24" cy="24" r="22" stroke="#00d4ff" stroke-width="1.5" opacity="0.3"/><path d="M14 24 L20 18 L28 26 L36 18" stroke="#7b2ff7" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.7"/></svg></div>' +
        '<h2>欢迎使用 TriGenClaw</h2>' +
        '<p>选择模型，开始智能对话。支�?300+ 模型，代码助手，Agent 编排�?/p></div>';
      return;
    }

    var html = '';
    var showAll = document.body.getAttribute('data-show-all-msgs') === 'true';
    var maxV = 50;
    var startFrom = (!showAll && messages.length > maxV) ? messages.length - maxV : 0;
    if (startFrom > 0) {
      var _sm = document.createElement('div'); _sm.className = 'chat-show-more';
      var _sb = document.createElement('button'); _sb.className = 'btn btn-sm btn-ghost'; _sb.id = 'showMoreBtn';
      _sb.textContent = 'Show ' + startFrom + ' earlier messages';
      _sm.appendChild(_sb);
      html = _sm.outerHTML + '\\n' + html;
    }
    for (var i = startFrom; i < messages.length; i++) {
      var msg = messages[i];
      var role = msg.role === 'user' ? 'user' : 'assistant';
      var avatar = role === 'user' ? 'U' : 'AI';
      var content = renderMessageContent(msg.content);
      html += '<div class="message ' + role + '">';
      html += '<div class="message-avatar">' + avatar + '</div>';
      html += '<div class="message-body">';
      html += '<div class="message-header"><span>' + (role === 'user' ? 'You' : 'TriGen AI') + '</span><span class="message-time">' + formatTime(msg.timestamp) + '</span></div>';
      html += '<div class="message-content">' + content + '</div>';
      html += '<div class="message-actions">';
      html += '<button class="copy-btn" data-content="' + escapeHtml(msg.content || '') + '">复制</button>';

      if (role === 'user') {
        html += '<button class="edit-btn" data-index="' + i + '" title="Edit">编辑</button>';
      }
      html += '<button class="delete-btn" data-index="' + i + '" title="Delete">删除</button>';
      if (role === 'assistant' && msg.content) {
        html += '<button class="branch-btn" data-idx=' + i + '>Branch</button>';
        html += '<button class="regenerate-btn">重新生成</button>';
      }
      html += '</div>';
      html += '</div></div>';
    }
    container.innerHTML = html;
    addCopyCodeButtons(container);

    // 绑定复制和重新生�?
    var copyBtns = container.querySelectorAll('.copy-btn');
    for (var c = 0; c < copyBtns.length; c++) {
      (function(btn) {
        btn.addEventListener('click', function() {
          var content = this.getAttribute('data-content');
          navigator.clipboard.writeText(content).then(function() {
            showToast('已复�?, 'success');
          }).catch(function() {
            showToast('复制失败', 'error');
          });

        });
      })(copyBtns[c]);
    var branchBtns = container.querySelectorAll('.branch-btn');
    for (var br = 0; br < branchBtns.length; br++) {
      (function(btn) {
        btn.addEventListener('click', function() {
          var idx = parseInt(this.getAttribute('data-idx'));
          if (typeof NexusChat.branch === 'function') NexusChat.branch(idx);
        });
      })(branchBtns[br]);
    }
    var deleteBtns = container.querySelectorAll('.delete-btn');
    for (var d = 0; d < deleteBtns.length; d++) {
      (function(btn) {
        btn.addEventListener('click', function() {
          var idx = parseInt(this.getAttribute('data-index'));
          NexusChat.deleteMessage(idx);
        });
      })(deleteBtns[d]);
    }

    var editBtns = container.querySelectorAll('.edit-btn');
    for (var e = 0; e < editBtns.length; e++) {
      (function(btn, idx) {
        btn.addEventListener('click', function() {
          var msgEl = this.closest('.message');
          var contentEl = msgEl.querySelector('.message-content');
          if (!contentEl) return;
          var text = contentEl.textContent;
          contentEl.innerHTML = '<textarea class="edit-textarea" rows="3">' + escapeHtml(text) + '</textarea>';
          var textarea = contentEl.querySelector('textarea');
          textarea.focus();
          textarea.setSelectionRange(textarea.value.length, textarea.value.length);
          function saveEdit() {
            var newText = textarea.value;
            if (newText !== text) {
              NexusChat.updateMessage(idx, newText);
            }
            contentEl.textContent = newText;
          }
          textarea.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              saveEdit();
            } else if (e.key === 'Escape') {
              contentEl.textContent = text;
            }
          });

          textarea.addEventListener('blur', saveEdit);
        });
      })(editBtns[e], parseInt(editBtns[e].getAttribute('data-index')));
    }
    var regenBtns = container.querySelectorAll('.regenerate-btn');
    for (var r = 0; r < regenBtns.length; r++) {
      (function(btn) {
        btn.addEventListener('click', function() {
          // 找到上一条用户消�?
          var msgs = NexusChat.getMessages();
          var lastUserMsg = '';
          for (var i = msgs.length - 1; i >= 0; i--) {
            if (msgs[i].role === 'user') {
              lastUserMsg = msgs[i].content;
              break;
            }
          }
          if (lastUserMsg) {
            // 删除最后一条助手消�?
            NexusChat.cancelStream();
            NexusChat.sendMessage(lastUserMsg);
          }
        });
      })(regenBtns[r]);
    }

    // 滚动到底�?
    var _nearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 80;
      if (_nearBottom) container.scrollTop = container.scrollHeight;
      // Chat search filtering
      if (_chatSearchQuery) {
        var _q = _chatSearchQuery.toLowerCase();
        container.querySelectorAll('.message').forEach(function(_m) {
          var _txt = _m.querySelector('.message-content');
          if (_txt) {
            if (_txt.textContent.toLowerCase().indexOf(_q) === -1) {
              _m.classList.add('dimmed');
            }
          }
        });
  }

  /** 渲染消息内容（Markdown -> HTML�?*/
  function formatTime(ts) {
    if (!ts) return '';
    var d = new Date(ts);
    var h = String(d.getHours()).padStart(2, '0');
    var m = String(d.getMinutes()).padStart(2, '0');
    return h + ':' + m;
  }

  function renderMessageContent(content) {
    if (!content) return '<div class="thinking-indicator"><span></span><span></span><span></span></div>';
    var html = escapeHtml(content);

    // 代码�?
    html = html.replace(/`(\w*)\n([\s\S]*?)`/g, function(m, lang, code) {
      return '<pre><code class="language-' + lang + '">' + escapeHtml(code) + '</code></pre>';
    });

    // 行内代码
    html = html.replace(/([^\n]+?)/g, '<code></code>');

    // 图片
    html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="" alt="" style="max-width:100%;border-radius:8px;margin:8px 0;">');

    // 链接
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="" target="_blank"></a>');

    // 标题
    html = html.replace(/^### (.+)$/gm, '<h4></h4>');
    html = html.replace(/^## (.+)$/gm, '<h3></h3>');
    html = html.replace(/^# (.+)$/gm, '<h2></h2>');

    // 加粗
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong></strong>');

    // 斜体
    html = html.replace(/\*(.+?)\*/g, '<em></em>');

    // 删除�?
    html = html.replace(/~~(.+?)~~/g, '<del></del>');

    // 引用
    html = html.replace(/^> (.+)$/gm, '<blockquote></blockquote>');

    // 无序列表
    html = html.replace(/^[-*] (.+)$/gm, '<li></li>');
    html = html.replace(/(<li>.*<\/li>\n?)+/g, function(m) {
      return '<ul>' + m.replace(/\n$/, '') + '</ul>';
    });

    // 有序列表
    html = html.replace(/^\d+\. (.+)$/gm, '<li></li>');

    // 表格
    html = html.replace(/^(\|.+\|)$/gm, function(m) {
      var cells = m.split('|').filter(function(c) { return c.trim(); });
      var rowHtml = '<tr>';
      for (var i = 0; i < cells.length; i++) {
        rowHtml += '<td>' + cells[i].trim() + '</td>';
      }
      rowHtml += '</tr>';
      return rowHtml;
    });

    html = html.replace(/(<tr>.*<\/tr>\n?)+/g, '<table>$&</table>');

    // 段落
    html = html.replace(/\n\n/g, '</p><p>');
    html = '<p>' + html + '</p>';

    // 修复嵌套
    html = html.replace(/<p><\/p>/g, '');
    html = html.replace(/<p><li>/g, '<li>');
    html = html.replace(/<\/li><\/p>/g, '</li>');

    return html;
  }

  // ===== 初始�?UI 事件 =====
  init = function init() {
    // 导航切换
    var navItems = document.querySelectorAll('.nav-item');
    for (var i = 0; i < navItems.length; i++) {
      (function(item) {
        item.addEventListener('click', function() {
          var panel = this.getAttribute('data-panel');
          if (panel) switchPanel(panel);
        });
      })(navItems[i]);
    }

    // 模型选择�?
    var modelSelectBtn = document.getElementById('modelSelectBtn');
    if (modelSelectBtn) {
      modelSelectBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        toggleModelDropdown();
      });

    }

    // 搜索模型
    var searchInput = document.getElementById('modelSearchInput');
    if (searchInput) {
      searchInput.addEventListener('input', function() {
        renderModelList(this.value);
      });

    }

    // 点击外部关闭下拉
    document.addEventListener('click', function(e) {
      if (modelDropdownOpen) {
        var selector = document.getElementById('modelSelector');
        if (selector && !selector.contains(e.target)) {
          closeModelDropdown();
        }
      }
    });

    }

    // 发送消�?
    var sendBtn = document.getElementById('sendBtn');
    var chatInput = document.getElementById('chatInput');

    function doSend() {
      if (!chatInput) return;
      var text = chatInput.value.trim();
      if (!text) return;
      chatInput.value = '';
      NexusChat.sendMessage(text);
    }

    if (sendBtn) sendBtn.addEventListener('click', doSend);

    if (chatInput) {
      chatInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          doSend();
        }
      });

    }

    // 新对�?
    var newChatBtn = document.getElementById('newChatBtn');
    if (newChatBtn) {
      newChatBtn.addEventListener('click', function() {
        NexusChat.newChat();
        renderChatMessages();
      });

    }

    // 历史记录
    var toggleHistoryBtn = document.getElementById('toggleHistory');
    var closeHistoryBtn = document.getElementById('closeHistory');
    if (toggleHistoryBtn) toggleHistoryBtn.addEventListener('click', toggleHistory);
    if (closeHistoryBtn) closeHistoryBtn.addEventListener('click', toggleHistory);

    // 设置
    var themeSelect = document.getElementById('themeSelect');
    if (themeSelect) {
      themeSelect.value = localStorage.getItem('nx_theme') || 'dark';
      themeSelect.addEventListener('change', function() {
        document.documentElement.setAttribute('data-theme', this.value);
        localStorage.setItem('nx_theme', this.value);
      });

    }
      // 应用初始主题
      document.documentElement.setAttribute('data-theme', themeSelect.value);
    }

    var fontSizeRange = document.getElementById('fontSizeRange');
    if (fontSizeRange) {
      var savedSize = localStorage.getItem('nx_font_size') || '14';
      fontSizeRange.value = savedSize;
      document.getElementById('fontSizeLabel').textContent = savedSize + 'px';
      document.documentElement.style.setProperty('--font-size', savedSize + 'px');
      fontSizeRange.addEventListener('input', function() {
        var size = this.value + 'px';
        document.getElementById('fontSizeLabel').textContent = size;
        document.documentElement.style.setProperty('--font-size', size);
        localStorage.setItem('nx_font_size', this.value);
      });

    }

    // 清除数据
    var clearDataBtn = document.getElementById('clearDataBtn');
    if (clearDataBtn) {
      clearDataBtn.addEventListener('click', function() {
        if (confirm('确定清除所有数据？此操作不可恢复�?)) {
          localStorage.clear();
          location.reload();
        }
      });

    }

    // 消息变更回调
    NexusChat.onMessagesChange(function() {
      renderChatMessages();
    });

    // 聊天搜索
    var searchBtn = document.getElementById('chatSearchBtn');
    if (searchBtn) searchBtn.addEventListener('click', toggleChatSearch);

    // Token 计数
    var chatInput = document.getElementById('chatInput');
    if (chatInput) {
      chatInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 200) + 'px';
        updateTokenCount(this.value);
      });

    // Drag & drop file upload
    var dropZone = chatInput.closest('.chat-input-wrapper');
    if (dropZone) {
      dropZone.addEventListener('dragover', function(e) {
        e.preventDefault();
        this.classList.add('drag-over');
      });
      dropZone.addEventListener('dragleave', function() {
        this.classList.remove('drag-over');
      });
      dropZone.addEventListener('drop', function(e) {
        e.preventDefault();
        this.classList.remove('drag-over');
        var file = e.dataTransfer.files[0];
        if (file) {
          var reader = new FileReader();
          reader.onload = function(ev) {
            chatInput.value = ev.target.result;
            chatInput.dispatchEvent(new Event('input'));
            NexusUI.toast('Loaded: ' + file.name, 'info');
          };
          reader.readAsText(file);
        }
      });
    }

    // 更新历史计数
    updateHistoryCount();

        // 聊天导出
    var chatExportBtn = document.getElementById('chatExportBtn');
    if (chatExportBtn) {
      chatExportBtn.addEventListener('click', function() {
        var msgs = NexusChat.getMessages();
        if (msgs.length === 0) { showToast('No messages to export', 'warning'); return; }
        var markdown = formatChatAsMarkdown(msgs);
        var blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = 'nexus-chat-' + new Date().toISOString().slice(0, 10) + '.md';
        a.click();
        URL.revokeObjectURL(url);
        showToast('Chat exported', 'success');
      });

    }

  function formatChatAsMarkdown(messages) {
    var md = '# TriGenClaw Chat\n\n';
    md += 'Exported: ' + new Date().toLocaleString() + '\n\n';
    md += '---\n\n';
    for (var i = 0; i < messages.length; i++) {
      var msg = messages[i];
      md += '### ' + (msg.role === 'user' ? '👤 User' : '🤖 TriGen AI') + '\n\n';
      md += msg.content.trim() + '\n\n';
      md += '---\n\n';
    }
    md += '_Exported from TriGenClaw_\n';
    return md;
  }

  // ===== Global Search =====
  function performGlobalSearch(query) {
    var existing = document.getElementById('gsResults'); if (existing) existing.remove();
    if (!query || query.length < 2) return; var q = query.toLowerCase();
    var div = document.createElement('div'); div.id = 'gsResults'; div.className = 'gs-results';
    var chats = []; var docs = [];
    try { var convs = NexusChat.getHistoryList();
      for (var i = 0; i < convs.length && chats.length < 5; i++) {
        var found = (convs[i].title || '').toLowerCase().indexOf(q) >= 0;
        if (!found && convs[i].messages) {
          for (var j = 0; j < convs[i].messages.length; j++) {
            if ((convs[i].messages[j].content || '').toLowerCase().indexOf(q) >= 0) { found = true; break; }
          }
        }
        if (found) chats.push({ id: convs[i].id, title: convs[i].title || 'Chat' });
      }
    } catch(e) {}
    try { var kbs = NexusKnowledge.getAllDocuments();
      for (var k = 0; k < kbs.length && docs.length < 5; k++) {
        if ((kbs[k].title || '').toLowerCase().indexOf(q) >= 0 || (kbs[k].content || '').toLowerCase().indexOf(q) >= 0) {
          docs.push({ id: kbs[k].id, title: kbs[k].title || 'Doc' });
        }
      }
    } catch(e) {}
    if (chats.length + docs.length === 0) return;
    if (chats.length > 0) {
      var tg = document.createElement('div'); tg.className = 'gs-grp';
      var tt = document.createElement('div'); tt.className = 'gs-title'; tt.textContent = 'Chats'; tg.appendChild(tt);
      for (var a = 0; a < chats.length; a++) {
        var ti = document.createElement('div'); ti.className = 'gs-itm'; ti.textContent = chats[a].title;
        ti.setAttribute('data-t', 'chat'); ti.setAttribute('data-d', chats[a].id);
        ti.addEventListener('click', function() {
          NexusChat.loadChat(this.getAttribute('data-d')); switchPanel('chat'); renderChatMessages();
          div.remove(); document.getElementById('globalSearchInput').value = '';
        });
        tg.appendChild(ti);
      }
      div.appendChild(tg);
    }
    if (docs.length > 0) {
      var dg = document.createElement('div'); dg.className = 'gs-grp';
      var dt = document.createElement('div'); dt.className = 'gs-title'; dt.textContent = 'Knowledge'; dg.appendChild(dt);
      for (var b = 0; b < docs.length; b++) {
        var di = document.createElement('div'); di.className = 'gs-itm'; di.textContent = docs[b].title;
        di.setAttribute('data-t', 'kb'); di.setAttribute('data-d', docs[b].id);
        di.addEventListener('click', function() {
          if (typeof NexusKnowledge.openDocumentById === 'function') { switchPanel('knowledge'); NexusKnowledge.openDocumentById(this.getAttribute('data-d')); }
          div.remove(); document.getElementById('globalSearchInput').value = '';
        });
        dg.appendChild(di);
      }
      div.appendChild(dg);
    }
    document.body.appendChild(div);
    var inp = document.getElementById('globalSearchInput');
    if (inp) { var r = inp.getBoundingClientRect();
      div.style.cssText = 'position:fixed;top:' + (r.bottom + 2) + 'px;left:' + r.left + 'px;width:' + r.width + 'px;z-index:9999';
    }
  }
  // ===== 快捷键参考弹�?=====
  function showShortcutModal() {
    var existing = document.querySelector('.shortcut-modal-overlay');
    if (existing) { existing.remove(); return; }

    var overlay = document.createElement('div');
    overlay.className = 'shortcut-modal-overlay';
    overlay.innerHTML = [
      '<div class="shortcut-modal">',
      '<div class="shortcut-modal-header">',
      '<span>Keyboard Shortcuts</span>',
      '<button class="modal-close" id="shortcutCloseBtn">×</button>',
      '</div>',
      '<div class="shortcut-modal-body">',

      '<div class="shortcut-group"><h4>General</h4>',
      '<div class="shortcut-row"><span class="shortcut-key">Esc</span><span class="shortcut-desc">Close dropdowns / panels</span></div>',
      '<div class="shortcut-row"><span class="shortcut-key">?</span><span class="shortcut-desc">Show this help</span></div>',
      '</div>',

      '<div class="shortcut-group"><h4>Chat</h4>',
      '<div class="shortcut-row"><span class="shortcut-key">Enter</span><span class="shortcut-desc">Send message</span></div>',
      '<div class="shortcut-row"><span class="shortcut-key">Shift+Enter</span><span class="shortcut-desc">New line</span></div>',
      '<div class="shortcut-row"><span class="shortcut-key">Ctrl+K</span><span class="shortcut-desc">Focus chat input</span></div>',
      '</div>',

      '<div class="shortcut-group"><h4>Code Editor</h4>',
      '<div class="shortcut-row"><span class="shortcut-key">Ctrl+S</span><span class="shortcut-desc">Save + Auto review</span></div>',
      '<div class="shortcut-row"><span class="shortcut-key">Tab</span><span class="shortcut-desc">Indent (4 spaces)</span></div>',
      '<div class="shortcut-row"><span class="shortcut-key">�?/ �?/span><span class="shortcut-desc">Terminal command history</span></div>',
      '</div>',

      '<div class="shortcut-group"><h4>Knowledge Base</h4>',
      '<div class="shortcut-row"><span class="shortcut-key">Ctrl+S</span><span class="shortcut-desc">Save document</span></div>',
      '<div class="shortcut-row"><span class="shortcut-key">Tab</span><span class="shortcut-desc">Indent content</span></div>',
      '</div>',

      '<div class="shortcut-group"><h4>Electron (Desktop)</h4>',
      '<div class="shortcut-row"><span class="shortcut-key">Alt+Space</span><span class="shortcut-desc">Show / hide window</span></div>',
      '<div class="shortcut-row"><span class="shortcut-key">F12</span><span class="shortcut-desc">Developer Tools</span></div>',
      '<div class="shortcut-row"><span class="shortcut-key">F11</span><span class="shortcut-desc">Toggle fullscreen</span></div>',
      '<div class="shortcut-row"><span class="shortcut-key">Ctrl+Q</span><span class="shortcut-desc">Quit app</span></div>',
      '</div>',

      '</div>',
      '</div>'
    ].join('\n');

    document.body.appendChild(overlay);

    overlay.querySelector('#shortcutCloseBtn').onclick = function() { overlay.remove(); };
    overlay.addEventListener('click', function(e) {
      if (e.target === overlay) overlay.remove();
    });

    }
  }
// 键盘快捷�?
    document.addEventListener('keydown', function(e) {
    // Global search
    var gs = document.getElementById('globalSearchInput');
    if (gs) {
      gs.addEventListener('input', function() { performGlobalSearch(this.value); });
      gs.addEventListener('blur', function() { setTimeout(function() { var e = document.getElementById('gsResults'); if (e) e.remove(); }, 300); });
      gs.addEventListener('keydown', function(e) { if (e.key === 'Escape') { this.value = ''; var e2 = document.getElementById('gsResults'); if (e2) e2.remove(); } });
    }
      // ? 显示快捷键帮�?
      // Ctrl+P / Cmd+P 命令面板
      if ((e.ctrlKey || e.metaKey) && e.key === 'p') {
        e.preventDefault();
        showCommandPalette();
      }
      if (e.key === '?' && !e.ctrlKey && !e.metaKey && !e.shiftKey) {
        e.preventDefault();
        showShortcutModal();
      }
      // Ctrl+K 聚焦输入
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        switchPanel('chat');
        var input = document.getElementById('chatInput');
        if (input) input.focus();
      }
      // Esc 关闭面板
      if (e.key === 'Escape') {
        closeModelDropdown();
        if (historyOpen) toggleHistory();
      }
    });

    // 初始渲染
    renderChatMessages();

    // 右键 tab 切换
    var codeRightTabs = document.querySelectorAll('.code-right-tab');
    for (var t = 0; t < codeRightTabs.length; t++) {
      (function(tab) {
        tab.addEventListener('click', function() {
          var target = this.getAttribute('data-panel');
          codeRightTabs.forEach(function(t) { t.classList.remove('active'); });
          this.classList.add('active');
          document.querySelectorAll('.code-right-content > div').forEach(function(p) {
            p.classList.remove('active');
          });

          var panel = document.getElementById(target);
          if (panel) panel.classList.add('active');
        });
      })(codeRightTabs[t]);
    }
  }

  // 检�?Electron 环境
  if (document.body.getAttribute('data-electron') === 'true') {
    var appEl = document.getElementById('app');
    if (appEl) appEl.setAttribute('data-electron', 'true');
    // 在侧边栏底部添加 Electron 指示
    var verEl = document.createElement('div');
    verEl.className = 'electron-badge';
    verEl.textContent = 'Desktop';
    verEl.title = 'Running as Electron desktop app';
    var sidebar = document.getElementById('sidebar');
    if (sidebar) sidebar.appendChild(verEl);
  }

  // ===== 骨架�?=====
  /** 聊天面板骨架�?*/
  
    // 自定义主题色
    var ACCENTS = {
      cyan: { primary: '#00d4ff', primaryDim: 'rgba(0,212,255,0.15)', secondary: '#7b2ff7', secondaryDim: 'rgba(123,47,247,0.15)' },
      purple: { primary: '#a855f7', primaryDim: 'rgba(168,85,247,0.15)', secondary: '#6366f1', secondaryDim: 'rgba(99,102,241,0.15)' },
      green: { primary: '#22c55e', primaryDim: 'rgba(34,197,94,0.15)', secondary: '#06b6d4', secondaryDim: 'rgba(6,182,212,0.15)' },
      orange: { primary: '#f97316', primaryDim: 'rgba(249,115,22,0.15)', secondary: '#eab308', secondaryDim: 'rgba(234,179,8,0.15)' },
      pink: { primary: '#ec4899', primaryDim: 'rgba(236,72,153,0.15)', secondary: '#f472b6', secondaryDim: 'rgba(244,114,182,0.15)' },
      red: { primary: '#ef4444', primaryDim: 'rgba(239,68,68,0.15)', secondary: '#f87171', secondaryDim: 'rgba(248,113,113,0.15)' }
    };

    function setAccent(name) {
      var a = ACCENTS[name];
      if (!a) return;
      var root = document.documentElement;
      root.style.setProperty('--primary', a.primary);
      root.style.setProperty('--primary-dim', a.primaryDim);
      root.style.setProperty('--secondary', a.secondary);
      root.style.setProperty('--secondary-dim', a.secondaryDim);
      localStorage.setItem('nx_accent', name);
    }
    // 语言切换
    var langSelect = document.getElementById('langSelect');
    if (langSelect) {
      langSelect.value = _lang;
      langSelect.addEventListener('change', function() {
        setLanguage(this.value);
        NexusUI.toast(this.value === 'zh' ? '语言: 中文' : 'Language: English', 'info');
      });

    }
      setLanguage(_lang);
    }

    // 数据备份
    setupDataBackup();
    setupAPIProviders();
  
    // Quick prompts
    var prompts = [
      { name: 'Explain', text: 'Explain the following code:' },
      { name: 'Review', text: 'Review for bugs and performance:' },
      { name: 'Optimize', text: 'Optimize for better performance:' },
      { name: 'Tests', text: 'Write comprehensive unit tests:' },
      { name: 'Refactor', text: 'Refactor for better quality:' },
      { name: 'Document', text: 'Add documentation and comments:' }
    ];
    try { var sp = JSON.parse(localStorage.getItem('nx_qp')); if (sp) prompts = sp; } catch(e) {}
    var pb = document.createElement('button'); pb.className = 'btn-icon prompts-btn'; pb.title = 'Prompts'; pb.textContent = '#';
    var pd = null;
    pb.addEventListener('click', function() {
      if (pd) { pd.remove(); pd = null; return; }
      pd = document.createElement('div'); pd.className = 'prompts-dropdown';
      for (var p = 0; p < prompts.length; p++) {
        (function(pd) {
          var it = document.createElement('div'); it.className = 'prompts-item'; it.textContent = pd.name;
          it.addEventListener('click', function() {
            var ta = document.getElementById('chatInput');
            if (ta) { ta.value = pd.text + '\n\n' + ta.value; ta.focus(); ta.dispatchEvent(new Event('input')); }
            pd.remove(); pd = null;
          }); pd.appendChild(it);
        })(prompts[p]);
      }
      var sv = document.createElement('div'); sv.className = 'prompts-item prompts-save'; sv.textContent = '+ Save';
      sv.addEventListener('click', function() {
        var ta = document.getElementById('chatInput'); var txt = ta ? ta.value.trim() : '';
        if (!txt) { NexusUI.toast('Empty input', 'warning'); pd.remove(); pd = null; return; }
        var n = prompt('Name:', 'Custom ' + (prompts.length + 1));
        if (n) { prompts.push({ name: n, text: txt }); localStorage.setItem('nx_qp', JSON.stringify(prompts)); NexusUI.toast('Saved', 'success'); }
        pd.remove(); pd = null;
      });
      pd.appendChild(sv);
      document.body.appendChild(pd);
      var r = pb.getBoundingClientRect();
      pd.style.cssText = 'position:fixed;bottom:' + (window.innerHeight - r.top + 4) + 'px;left:' + Math.max(8, r.left - 100) + 'px;z-index:9999';
    });
    var info = document.querySelector('#chatPanel .chat-input-info');
    if (info) info.insertBefore(pb, info.children[1]);
  function showChatSkeleton() {
    var container = document.getElementById('chatMessages');
    if (!container || container.querySelector('.message')) return false;
    var html = '';
    for (var i = 0; i < 3; i++) {
      html += '<div class="skeleton-message">' +
        '<div class="skeleton skeleton-avatar"></div>' +
        '<div class="skeleton-message-body">' +
        '<div class="skeleton skeleton-line tiny"></div>' +
        '<div class="skeleton skeleton-line"></div>' +
        '<div class="skeleton skeleton-line short"></div>' +
        '</div></div>';
    }
    container.innerHTML = html;
    addCopyCodeButtons(container);
    return true;
  }

  /** 代码面板骨架�?*/
  function showCodeSkeleton() {
    var container = document.getElementById('codePanel');
    if (!container) return;
    var existing = container.querySelector('.skeleton-panel');
    if (existing) return;
    var skel = document.createElement('div');
    skel.className = 'skeleton-panel';
    var html = '<div class="skeleton-editor">';
    for (var i = 0; i < 12; i++) {
      var w = 40 + Math.random() * 60;
      html += '<div class="skeleton skeleton-line" style="width:' + Math.round(w) + '%"></div>';
    }
    html += '</div>';
    skel.innerHTML = html;
    container.appendChild(skel);
  }

  /** 隐藏代码面板骨架�?*/
  function hideCodeSkeleton() {
    var panel = document.getElementById('codePanel');
    if (!panel) return;
    var skel = panel.querySelector('.skeleton-panel');
    if (skel) {
      skel.classList.add('fade-out');
      setTimeout(function() { skel.remove(); }, 400);
    }
  }

  /** Agent 面板骨架�?*/
  function showAgentSkeleton() {
    var grid = document.getElementById('agentCardGrid');
    if (!grid || grid.children.length > 0) return;
    var html = '';
    for (var i = 0; i < 8; i++) {
      html += '<div class="skeleton skeleton-card"></div>';
    }
    grid.innerHTML = html;
  }

  // ===== i18n 中英文切�?=====
  var I18N = {
    en: {
      'panel.chat': 'AI Chat', 'panel.code': 'Code Assistant', 'panel.agent': 'Agent Workbench',
      'panel.skills': 'Skill Store', 'panel.knowledge': 'Knowledge Base', 'panel.settings': 'Settings',
      'settings.theme': 'Theme', 'settings.lang': 'Language', 'settings.font': 'UI Font',
      'settings.editor': 'Editor', 'settings.editorFont': 'Font', 'settings.tab': 'Tab',
      'settings.data': 'Data', 'settings.history': 'History', 'settings.backup': 'Backup',
      'settings.api': 'API', 'settings.apiKey': 'Proxy Key', 'settings.apiUrl': 'Proxy URL', 'settings.providers': 'Provider Keys',
      'btn.export': 'Export', 'btn.import': 'Import', 'btn.clear': 'Clear All',
      'btn.save': 'Save', 'btn.cancel': 'Cancel', 'btn.create': 'Create',
      'chat.input': 'Type a message...', 'chat.model': 'Model',
      'code.review': 'Review', 'code.explain': 'Explain', 'code.optimize': 'Optimize',
      'kb.new': '+ New Note', 'kb.search': 'Search knowledge...',
      'skill.create': '+ Create Skill', 'skill.search': 'Search skills...',
      'agent.run': 'Run Workflow', 'agent.clear': 'Clear Canvas',
      'welcome.title': 'Welcome to TriGenClaw',
      'welcome.desc': 'Choose a model and start chatting. 300+ models, Code Assistant, Agent orchestration.',
      'nav.chat': 'Chat', 'nav.code': 'Code', 'nav.agent': 'Agent',
      'nav.skills': 'Skills', 'nav.knowledge': 'Knowledge', 'nav.settings': 'Settings',
      'lang.en': 'English', 'lang.zh': '中文',
      'installed': 'Installed',
      'export.success': 'Data exported successfully',
      'import.success': 'Data imported. Reloading...',
      'import.error': 'Invalid backup file'
    },
    zh: {
      'panel.chat': 'AI 对话', 'panel.code': '代码助手', 'panel.agent': 'Agent 工作�?,
      'panel.skills': '技能商�?, 'panel.knowledge': '知识�?, 'panel.settings': '设置',
      'settings.theme': '主题', 'settings.lang': '语言', 'settings.font': '界面字体',
      'settings.editor': '编辑�?, 'settings.editorFont': '字体大小', 'settings.tab': 'Tab 大小',
      'settings.data': '数据', 'settings.history': '对话历史', 'settings.backup': '备份恢复',
      'settings.api': 'API 配置', 'settings.apiKey': '代理 Key', 'settings.apiUrl': '代理地址', 'settings.providers': '厂商密钥',
      'btn.export': '导出', 'btn.import': '导入', 'btn.clear': '清除所有数�?,
      'btn.save': '保存', 'btn.cancel': '取消', 'btn.create': '创建',
      'chat.input': '输入消息...', 'chat.model': '模型',
      'code.review': '审查', 'code.explain': '解释', 'code.optimize': '优化',
      'kb.new': '+ 新建笔记', 'kb.search': '搜索知识...',
      'skill.create': '+ 创建技�?, 'skill.search': '搜索技�?..',
      'agent.run': '执行工作�?, 'agent.clear': '清空画布',
      'welcome.title': '欢迎使用 TriGenClaw',
      'welcome.desc': '选择模型，开始智能对话。支�?300+ 模型，代码助手，Agent 编排�?,
      'nav.chat': '对话', 'nav.code': '代码', 'nav.agent': 'Agent',
      'nav.skills': '技�?, 'nav.knowledge': '知识', 'nav.settings': '设置',
      'lang.en': 'English', 'lang.zh': '中文',
      'installed': '已安�?,
      'export.success': '数据导出成功',
      'import.success': '数据已导入，重新加载�?..',
      'import.error': '无效的备份文�?
    }
  };
  var _lang = localStorage.getItem('nx_lang') || 'en';

  function __(key) {
    return (I18N[_lang] && I18N[_lang][key]) || key;
  }

  function setLanguage(lang) {
    _lang = lang;
    localStorage.setItem('nx_lang', lang);
    document.documentElement.lang = lang === 'zh' ? 'zh-CN' : 'en';
    applyUILanguage(lang);
  }

  function applyUILanguage(lang) {
    // Update nav labels
    var navMap = { chat: 'nav.chat', code: 'nav.code', agent: 'nav.agent', skills: 'nav.skills', knowledge: 'nav.knowledge', settings: 'nav.settings' };
    document.querySelectorAll('.nav-item').forEach(function(item) {
      var panel = item.getAttribute('data-panel');
      var label = item.querySelector('.nav-label');
      if (panel && label && navMap[panel]) label.textContent = __(navMap[panel]);
    });

    // Update welcome message
    var welcomeTitle = document.querySelector('.welcome-message h2');
    var welcomeDesc = document.querySelector('.welcome-message p');
    if (welcomeTitle) welcomeTitle.textContent = __('welcome.title');
    if (welcomeDesc) welcomeDesc.textContent = __('welcome.desc');
    // Update chat input placeholder
    var chatInput = document.getElementById('chatInput');
    if (chatInput) chatInput.placeholder = __('chat.input');
    // Update settings labels
    var settingsLabels = {
      'themeSelect': __('settings.theme'),
      'langSelect': __('settings.lang'),
      'fontSizeRange': __('settings.font'),
      'editorFontSizeRange': __('settings.editorFont'),
      'tabSizeSelect': __('settings.tab')
    };
    // Update on next view switch
  }

  // ===== 数据备份/恢复 =====
  function setupDataBackup() {
    var exportBtn = document.getElementById('exportDataBtn');
    var importBtn = document.getElementById('importDataBtn');
    
    // 创建隐藏文件输入
    var fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.json';
    fileInput.style.display = 'none';
    fileInput.id = 'importFileInput';
    document.body.appendChild(fileInput);

    if (exportBtn) {
      exportBtn.addEventListener('click', function() {
        var keys = [];
        for (var i = 0; i < localStorage.length; i++) {
          var key = localStorage.key(i);
          if (key && key.indexOf('nx_') === 0) keys.push(key);
        }
        var data = {};
        for (var j = 0; j < keys.length; j++) {
          try { data[keys[j]] = JSON.parse(localStorage.getItem(keys[j])); }
          catch(e) { data[keys[j]] = localStorage.getItem(keys[j]); }
        }
        var blob = new Blob([JSON.stringify({ app: 'trigenclaw', version: 1, exportedAt: new Date().toISOString(), data: data }, null, 2)], { type: 'application/json' });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = 'trigenclaw-backup-' + new Date().toISOString().slice(0, 10) + '.json';
        a.click();
        URL.revokeObjectURL(url);
        showToast(__('export.success'), 'success');
      });

    }

    if (importBtn) {
      importBtn.addEventListener('click', function() {
        fileInput.click();
      });

    }

    fileInput.addEventListener('change', function(e) {
      var file = e.target.files[0];
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function(ev) {
        try {
          var backup = JSON.parse(ev.target.result);
          if (!backup.data || backup.app !== 'trigenclaw') {
            showToast(__('import.error'), 'error');
            return;
          }
          var keys = Object.keys(backup.data);
          for (var k = 0; k < keys.length; k++) {
            var val = backup.data[keys[k]];
            localStorage.setItem(keys[k], typeof val === 'string' ? val : JSON.stringify(val));
          }
          showToast(__('import.success'), 'success');
          setTimeout(function() { location.reload(); }, 1500);
        } catch(err) {
          showToast(__('import.error'), 'error');
        }
      };
      reader.readAsText(file);
      fileInput.value = '';
    });

  }

  // 自定义主题色
    var ACCENTS = {
      cyan: { primary: '#00d4ff', primaryDim: 'rgba(0,212,255,0.15)', secondary: '#7b2ff7', secondaryDim: 'rgba(123,47,247,0.15)' },
      purple: { primary: '#a855f7', primaryDim: 'rgba(168,85,247,0.15)', secondary: '#6366f1', secondaryDim: 'rgba(99,102,241,0.15)' },
      green: { primary: '#22c55e', primaryDim: 'rgba(34,197,94,0.15)', secondary: '#06b6d4', secondaryDim: 'rgba(6,182,212,0.15)' },
      orange: { primary: '#f97316', primaryDim: 'rgba(249,115,22,0.15)', secondary: '#eab308', secondaryDim: 'rgba(234,179,8,0.15)' },
      pink: { primary: '#ec4899', primaryDim: 'rgba(236,72,153,0.15)', secondary: '#f472b6', secondaryDim: 'rgba(244,114,182,0.15)' },
      red: { primary: '#ef4444', primaryDim: 'rgba(239,68,68,0.15)', secondary: '#f87171', secondaryDim: 'rgba(248,113,113,0.15)' }
    };

    function setAccent(name) {
      var a = ACCENTS[name];
      if (!a) return;
      var root = document.documentElement;
      root.style.setProperty('--primary', a.primary);
      root.style.setProperty('--primary-dim', a.primaryDim);
      root.style.setProperty('--secondary', a.secondary);
      root.style.setProperty('--secondary-dim', a.secondaryDim);
      localStorage.setItem('nx_accent', name);
    }
    // 语言切换
    var langSelect = document.getElementById('langSelect');
    if (langSelect) {
      langSelect.value = _lang;
      langSelect.addEventListener('change', function() {
        setLanguage(this.value);
        NexusUI.toast(this.value === 'zh' ? '语言: 中文' : 'Language: English', 'info');
      });

    }

    // 数据备份
    setupDataBackup();
    setupAPIProviders();

  // ===== 命令面板 (Ctrl+P) =====
  var COMMANDS = [
    // 面板导航
    { id: 'goto-chat', label: 'Go to Chat', icon: '💬', keywords: 'chat,对话', panel: 'chat' },
    { id: 'goto-code', label: 'Go to Code', icon: '💻', keywords: 'code,代码', panel: 'code' },
    { id: 'goto-agent', label: 'Go to Agent', icon: '🤖', keywords: 'agent,工作�?, panel: 'agent' },
    { id: 'goto-skills', label: 'Go to Skills', icon: '🔧', keywords: 'skills,技�?, panel: 'skills' },
    { id: 'goto-knowledge', label: 'Go to Knowledge', icon: '📚', keywords: 'knowledge,知识', panel: 'knowledge' },
    { id: 'goto-settings', label: 'Go to Settings', icon: '⚙️', keywords: 'settings,设置', panel: 'settings' },
    // 操作
    { id: 'new-chat', label: 'New Chat', icon: '�?, keywords: 'new,新建,对话', fn: 'newChat' },
    { id: 'export-chat', label: 'Export Chat', icon: '📤', keywords: 'export,导出', fn: 'exportChat' },
    { id: 'new-note', label: 'New Knowledge Note', icon: '📝', keywords: 'new note,新建,笔记', fn: 'newNote' },
    { id: 'run-workflow', label: 'Run Agent Workflow', icon: '▶️', keywords: 'run,执行,workflow', fn: 'runWorkflow' },
    { id: 'save-file', label: 'Save Current File', icon: '💾', keywords: 'save,保存', fn: 'saveFile' },
    { id: 'toggle-theme', label: 'Toggle Theme', icon: '🎨', keywords: 'theme,主题', fn: 'toggleTheme' }
  ];

  function showCommandPalette() {
    var existing = document.querySelector('.cmd-palette-overlay');
    if (existing) { existing.remove(); return; }

    var overlay = document.createElement('div');
    overlay.className = 'cmd-palette-overlay';
    overlay.innerHTML = '<div class="cmd-palette">' +
      '<div class="cmd-palette-input-wrap">' +
      '<span class="cmd-palette-prefix">></span>' +
      '<input type="text" class="cmd-palette-input" id="cmdPaletteInput" placeholder="Type to search..." autocomplete="off" spellcheck="false">' +
      '</div>' +
      '<div class="cmd-palette-results" id="cmdPaletteResults"></div>' +
      '</div>';

    document.body.appendChild(overlay);

    var input = overlay.querySelector('#cmdPaletteInput');
    var results = overlay.querySelector('#cmdPaletteResults');
    var selectedIndex = 0;
    var filteredCommands = COMMANDS.slice();

    function renderResults() {
      var q = input.value.toLowerCase();
      filteredCommands = q ? COMMANDS.filter(function(c) {
        return c.label.toLowerCase().indexOf(q) >= 0 || (c.keywords || '').indexOf(q) >= 0;
      }) : COMMANDS;

      if (filteredCommands.length === 0) {
        results.innerHTML = '<div class="cmd-palette-empty">No matching commands</div>';
        return;
      }

      var html = '';
      for (var i = 0; i < filteredCommands.length; i++) {
        var selected = i === selectedIndex ? ' selected' : '';
        html += '<div class="cmd-palette-item' + selected + '" data-index="' + i + '">' +
          '<span class="cmd-palette-icon">' + filteredCommands[i].icon + '</span>' +
          '<span class="cmd-palette-label">' + filteredCommands[i].label + '</span>' +
          '</div>';
      }
      results.innerHTML = html;
      if (selectedIndex >= filteredCommands.length) selectedIndex = 0;

      // Bind clicks
      var items = results.querySelectorAll('.cmd-palette-item');
      for (var j = 0; j < items.length; j++) {
        (function(idx) {
          items[j].addEventListener('click', function() {
            executeCommand(filteredCommands[idx]);
            overlay.remove();
          });

          items[j].addEventListener('mouseenter', function() {
            results.querySelector('.selected')?.classList.remove('selected');
            this.classList.add('selected');
            selectedIndex = idx;
          });
        })(j);
      }
    }

    renderResults();

    input.addEventListener('input', function() {
      selectedIndex = 0;
      renderResults();
    });

    input.addEventListener('keydown', function(e) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        selectedIndex = Math.min(selectedIndex + 1, filteredCommands.length - 1);
        renderResults();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        selectedIndex = Math.max(selectedIndex - 1, 0);
        renderResults();
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (filteredCommands.length > 0 && filteredCommands[selectedIndex]) {
          executeCommand(filteredCommands[selectedIndex]);
          overlay.remove();
        }
      } else if (e.key === 'Escape') {
        overlay.remove();
      }
    });

    overlay.addEventListener('click', function(e) {
      if (e.target === overlay) overlay.remove();
    });

    setTimeout(function() { input.focus(); }, 50);
  }

  function executeCommand(cmd) {
    if (cmd.panel) {
      switchPanel(cmd.panel);
    } else if (cmd.fn === 'newChat') {
      var btn = document.getElementById('newChatBtn');
      if (btn) btn.click();
    } else if (cmd.fn === 'exportChat') {
      var btn = document.getElementById('chatExportBtn');
      if (btn) btn.click();
    } else if (cmd.fn === 'newNote') {
      switchPanel('knowledge');
      setTimeout(function() {
        if (typeof NexusKnowledge !== 'undefined' && NexusKnowledge.newDocument) {
          NexusKnowledge.newDocument();
        }
      }, 200);
    } else if (cmd.fn === 'runWorkflow') {
      switchPanel('agent');
      setTimeout(function() {
        var btn = document.getElementById('agentRunBtn');
        if (btn) btn.click();
      }, 200);
    } else if (cmd.fn === 'saveFile') {
      var btn = document.getElementById('codeSaveBtn');
      if (btn) btn.click();
    } else if (cmd.fn === 'toggleTheme') {
      var select = document.getElementById('themeSelect');
      if (select) {
        select.value = select.value === 'dark' ? 'light' : 'dark';
        select.dispatchEvent(new Event('change'));
      }
    }
  }    // 聊天高级设置（System Prompt, Temp, Max Tokens�?
    var chatAdvContainer = document.createElement('div');
    chatAdvContainer.className = 'chat-advanced';
    chatAdvContainer.innerHTML = ''
      + '<div class="chat-advanced-toggle" id="chatAdvancedToggle">�?Advanced</div>'
      + '<div class="chat-advanced-content hidden" id="chatAdvancedContent">'
      + '<div class="adv-row"><label>System Prompt</label>'
      + '<textarea id="chatSystemPrompt" class="adv-textarea" rows="2" placeholder="Optional system prompt for this conversation..."></textarea></div>'
      + '<div class="adv-row"><label>Temperature: <span id="chatTempLabel">0.7</span></label>'
      + '<input type="range" id="chatTemperature" class="adv-range" min="0" max="2" step="0.1" value="0.7"></div>'
      + '<div class="adv-row"><label>Max Tokens</label>'
      + '<input type="number" id="chatMaxTokens" class="adv-number" value="4096" min="256" max="32768"></div>'
      + '</div>';

    // Insert between chat-messages and chat-input-area
    var chatPanel = document.getElementById('chatPanel');
    var chatInputArea = chatPanel.querySelector('.chat-input-area');
    if (chatInputArea) {
      chatPanel.insertBefore(chatAdvContainer, chatInputArea);
    }

    // Wire up toggles
    var advToggle = document.getElementById('chatAdvancedToggle');
    var advContent = document.getElementById('chatAdvancedContent');
    var sysPromptEl = document.getElementById('chatSystemPrompt');
    var tempEl = document.getElementById('chatTemperature');
    var tempLabelEl = document.getElementById('chatTempLabel');
    var maxTokensEl = document.getElementById('chatMaxTokens');

    if (advToggle && advContent) {
      advToggle.addEventListener('click', function() {
        var isOpen = advContent.classList.toggle('hidden');
        this.classList.toggle('expanded', !isOpen);
      });
    }

    // Load current values
    if (sysPromptEl && typeof NexusChat.getSystemPrompt === 'function') {
      sysPromptEl.value = NexusChat.getSystemPrompt();
      sysPromptEl.addEventListener('input', function() {
        NexusChat.setSystemPrompt(this.value);
      });
    }

    if (tempEl && tempLabelEl) {
      tempEl.addEventListener('input', function() {
        tempLabelEl.textContent = this.value;
        if (typeof NexusChat.setTemperature === 'function') {
          NexusChat.setTemperature(parseFloat(this.value));
        }
      });
    }

    if (maxTokensEl) {
      maxTokensEl.addEventListener('input', function() {
        if (typeof NexusChat.setMaxTokens === 'function') {
          NexusChat.setMaxTokens(parseInt(this.value) || 4096);
        }
      });
    }

  function addCopyCodeButtons(container) {
    container.querySelectorAll('pre').forEach(function(pre) {
      var btn = document.createElement('button');
      btn.className = 'copy-code-btn';
      btn.textContent = 'Copy';
      btn.addEventListener('click', function() {
        var txt = pre.textContent;
        navigator.clipboard.writeText(txt).then(function() {
          btn.textContent = 'Copied!';
          setTimeout(function() { btn.textContent = 'Copy'; }, 2000);
        }).catch(function() { btn.textContent = 'Failed'; });
      });
      pre.parentNode.appendChild(btn);
    });
  }

  function updateHistoryCount() {
    var countEl = document.getElementById('historyCount');
    if (countEl) {
      var count = NexusChat.getHistoryList().length;
      countEl.textContent = count + ' 条记�?;
    }
  }

  
  // ===== 聊天消息搜索 =====
  var _chatSearchQuery = '';
  var _chatSearchVisible = false;

  function toggleChatSearch() {
    var existing = document.querySelector('.chat-search-bar');
    if (existing) {
      existing.remove();
      _chatSearchQuery = '';
      _chatSearchVisible = false;
      renderChatMessages();
      return;
    }
    _chatSearchVisible = true;
    var messagesEl = document.getElementById('chatMessages');
    if (!messagesEl) return;
    var bar = document.createElement('div');
    bar.className = 'chat-search-bar';
    bar.innerHTML = '<input type="text" id="chatSearchInput" placeholder="Search messages..." autocomplete="off"><span class="chat-search-count" id="chatSearchCount"></span><button class="chat-search-close">×</button>';
    messagesEl.parentNode.insertBefore(bar, messagesEl);
    var input = bar.querySelector('#chatSearchInput');
    input.focus();
    input.addEventListener('input', function() {
      _chatSearchQuery = this.value.trim();
      renderChatMessages();
      updateSearchCount();
    });

    input.addEventListener('keydown', function(e) {
      if (e.key === 'Escape') { toggleChatSearch(); }
    });

    bar.querySelector('.chat-search-close').addEventListener('click', toggleChatSearch);
  }

  function updateSearchCount() {
    var countEl = document.getElementById('chatSearchCount');
    if (!countEl) return;
    if (!_chatSearchQuery) { countEl.textContent = ''; return; }
    var msgs = document.querySelectorAll('.chat-messages .message');
    var visible = 0;
    msgs.forEach(function(m) { if (m.style.display !== 'none') visible++; });
    countEl.textContent = visible + '/' + msgs.length + ' matched';
  }

  // ===== Token 计数 =====
  function updateTokenCount(text) {
    var el = document.getElementById('tokenCounter');
    if (!el) return;
    if (!text) { el.textContent = ''; return; }
    var charCount = text.length;
    // Rough token estimate: ~4 chars per token for Chinese, ~1 token per 4 chars for English
    var asciiChars = (text.match(/[\x00-\x7F]/g) || []).length;
    var unicodeChars = charCount - asciiChars;
    var estimatedTokens = Math.round(asciiChars / 4 + unicodeChars);
    el.textContent = estimatedTokens + ' tokens';
  }
  function setupAPIProviders() {
    var container = document.getElementById('providerList');
    if (!container) return;
    var providers, modelMap;
    if (typeof NexusAPI !== 'undefined' && NexusAPI.getProviders) {
      providers = NexusAPI.getProviders();
      modelMap = NexusAPI.getModelProviderMap();
    }
    if (!providers) return;

    var allConfigs = (typeof NexusAPI !== 'undefined' && NexusAPI.getAllProviderConfigs) ? NexusAPI.getAllProviderConfigs() : {};
    var html = '';
    var count = 0;
    for (var key in providers) {
      var p = providers[key];
      var cfg = allConfigs[key] || {};
      var hasKey = cfg.apiKey && cfg.apiKey.length > 0;
      var statusText = hasKey ? '已配�? : (p.noKey ? '无需 Key' : '未配�?);
      var statusClass = hasKey ? 'provider-ok' : (p.noKey ? 'provider-na' : 'provider-missing');
      var expanded = hasKey ? '' : 'hidden';
      var checked = cfg.enabled !== false ? 'checked' : '';
      var modelNames = [];
      for (var mk in modelMap) {
        if (modelMap[mk] === key) modelNames.push(mk + '*');
      }
      count++;
      html += '<div class="provider-item">';
      html += '<div class="provider-header" data-provider="' + key + '">';
      html += '<span class="provider-name">' + p.name + '</span>';
      html += '<span class="provider-status ' + statusClass + '">' + statusText + '</span>';
      html += '<button class="btn btn-sm btn-ghost provider-toggle">编辑</button>';
      html += '</div>';
      html += '<div class="provider-body ' + expanded + '">';
      html += '<div class="settings-item"><label>API Key</label><input type="password" class="provider-key settings-input" value="' + (cfg.apiKey || '') + '" placeholder="' + (p.noKey ? '无需 Key' : 'sk-...') + '"></div>';
      html += '<div class="settings-item"><label>API URL</label><input type="text" class="provider-url settings-input" value="' + (cfg.baseUrl || p.baseUrl) + '"></div>';
      html += '<div class="settings-item"><label class="config-checkbox"><input type="checkbox" class="provider-enabled" ' + checked + '> 启用路由</label></div>';
      if (modelNames.length > 0) {
        html += '<div class="provider-models text-muted">匹配模型: ' + modelNames.join(', ') + '</div>';
      }
      html += '<div class="settings-item"><button class="btn btn-sm btn-primary provider-save">保存</button><span class="provider-msg text-muted" style="margin-left:8px"></span></div>';
      html += '</div>';
      html += '</div>';
    }

    container.innerHTML = html;

    // Bind toggle
    var toggles = container.querySelectorAll('.provider-toggle');
    for (var t = 0; t < toggles.length; t++) {
      (function(btn) {
        btn.addEventListener('click', function() {
          var body = this.parentElement.nextElementSibling;
          if (body) {
            body.classList.toggle('hidden');
            this.textContent = body.classList.contains('hidden') ? '编辑' : '收起';
          }
        });
      })(toggles[t]);
    }

    // Bind save
    var saves = container.querySelectorAll('.provider-save');
    for (var s = 0; s < saves.length; s++) {
      (function(btn) {
        btn.addEventListener('click', function() {
          var item = this.closest('.provider-item');
          var header = item.querySelector('.provider-header');
          var provider = header.getAttribute('data-provider');
          var keyInput = item.querySelector('.provider-key');
          var urlInput = item.querySelector('.provider-url');
          var enabledInput = item.querySelector('.provider-enabled');
          var msgEl = item.querySelector('.provider-msg');

          var config = {
            apiKey: keyInput ? keyInput.value : '',
            baseUrl: urlInput ? urlInput.value : '',
            enabled: enabledInput ? enabledInput.checked : true
          };

          if (msgEl) msgEl.textContent = '保存�?..';

          try {
            NexusAPI.setProviderConfig(provider, config);
            if (msgEl) msgEl.textContent = '已保�?;
            // Update status
            var statusEl = header.querySelector('.provider-status');
            if (config.apiKey && config.apiKey.length > 0) {
              statusEl.textContent = '已配�?;
              statusEl.className = 'provider-status provider-ok';
            } else {
              statusEl.textContent = '未配�?;
              statusEl.className = 'provider-status provider-missing';
            }
            setTimeout(function() { if (msgEl) msgEl.textContent = ''; }, 2000);
          } catch(e) {
            if (msgEl) msgEl.textContent = '保存失败: ' + e.message;
          }
        });
      })(saves[s]);
    }

    // Init default fields
    var apiUrlInput = document.getElementById('apiUrlInput');
    var apiKeyInput = document.getElementById('apiKeyInput');
    if (apiUrlInput) {
      var savedUrl = localStorage.getItem('nx_api_url');
      if (savedUrl) apiUrlInput.value = savedUrl;
      apiUrlInput.addEventListener('change', function() {
        localStorage.setItem('nx_api_url', this.value);
      });
    }
    if (apiKeyInput) {
      var savedKey = localStorage.getItem('nx_api_key');
      if (savedKey) apiKeyInput.value = savedKey;
      apiKeyInput.addEventListener('change', function() {
        localStorage.setItem('nx_api_key', this.value);
        if (typeof NexusAPI !== 'undefined' && NexusAPI.setAuth) {
          NexusAPI.setAuth('', this.value);
        }
      });
    }
  }
  // 安全网：确保 return 前所有关键函数都有定�?
  if (typeof init !== 'function') init = function() { console.warn('[NexusUI] init fallback'); };
  if (typeof showToast !== 'function') showToast = function(){};
  if (typeof switchPanel !== 'function') switchPanel = function(){};
  if (typeof renderChatMessages !== 'function') renderChatMessages = function(){};
  if (typeof renderHistoryList !== 'function') renderHistoryList = function(){};
  if (typeof setupAPIProviders !== 'function') setupAPIProviders = function(){};
  return {
    init: init,
    toast: showToast,
    switchPanel: switchPanel,
    renderChatMessages: renderChatMessages,
    renderHistoryList: renderHistoryList,
    setupAPIProviders: setupAPIProviders
  };
})();
if (!NexusUI || typeof NexusUI.init !== 'function') {
  console.error('[NexusUI] Init failed, using fallback');
  NexusUI = { init: function(){}, toast: function(){}, switchPanel: function(){}, renderChatMessages: function(){}, renderHistoryList: function(){}, setupAPIProviders: function(){} };
}

