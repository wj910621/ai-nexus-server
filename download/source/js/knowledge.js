/* ========================================
   知识库核心模块 - 文档管理、分类、搜索
   ======================================== */
var NexusKnowledge = (function() {
  "use strict";

  var STORAGE_KEY = "nx_knowledge_docs";
  var documents = [];
  var currentDocId = null;
  var currentCategory = "all";
  var currentSearch = "";

  var docListEl, welcomeEl, editorEl, previewEl;
  var docTitleEl, docContentEl, docCategoryEl;
  var searchInputEl, categoryBtns;
  var saveBtn, deleteBtn, copyBtn;
  var kbAddBtn;

  // ===== 初始化 =====
  function init() {
    docListEl = document.getElementById("kbDocList");
    welcomeEl = document.getElementById("kbWelcome");
    editorEl = document.getElementById("kbEditor");
    previewEl = document.getElementById("kbPreview");
    docTitleEl = document.getElementById("kbDocTitle");
    docContentEl = document.getElementById("kbDocContent");
    docCategoryEl = document.getElementById("kbDocCategory");
    searchInputEl = document.getElementById("kbSearchInput");
    saveBtn = document.getElementById("kbSaveBtn");
    deleteBtn = document.getElementById("kbDeleteBtn");
    copyBtn = document.getElementById("kbCopyBtn");
    kbAddBtn = document.getElementById("kbAddBtn");

    if (!docListEl) return;

    loadDocuments();
    renderDocList();

    setupCategories();
    setupSearch();
    setupEditor();
    setupActions();

    // Show welcome if no documents
    if (documents.length === 0) showWelcome();
  }

  // ===== 数据 =====
  function loadDocuments() {
    try {
      var data = localStorage.getItem(STORAGE_KEY);
      documents = data ? JSON.parse(data) : [];
    } catch(e) { documents = []; }
  }

  function saveDocuments() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(documents)); } catch(e) {}
  }

  function generateId() {
    return "kb_" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  }

  function getTimestamp() {
    return new Date().toISOString().replace("T", " ").slice(0, 16);
  }

  // ===== 文档列表 =====
  function renderDocList() {
    if (!docListEl) return;
    var filtered = getFilteredDocs();

    if (filtered.length === 0) {
      docListEl.innerHTML = '<div class="kb-empty">' +
        (currentSearch ? "No results found." : "No documents yet. Click + New Note to begin.") +
        "</div>";
      return;
    }

    var html = "";
    for (var i = 0; i < filtered.length; i++) {
      var doc = filtered[i];
      var active = doc.id === currentDocId ? " active" : "";
      var icon = getCategoryIcon(doc.category);
      var preview = (doc.content || "").replace(/\n/g, " ").slice(0, 80);
      html += '<div class="kb-doc-item' + active + '" data-id="' + doc.id + '">' +
        '<div class="kb-doc-icon">' + icon + '</div>' +
        '<div class="kb-doc-info">' +
        '<div class="kb-doc-title">' + escHtml(doc.title || "Untitled") + '</div>' +
        '<div class="kb-doc-meta">' + escHtml(preview) + (doc.content && doc.content.length > 80 ? "..." : "") + "</div>" +
        "</div>" +
        '<div class="kb-doc-date">' + (doc.updatedAt || doc.createdAt || "").slice(5, 10) + "</div>" +
        "</div>";
    }
    docListEl.innerHTML = html;

    // Bind click
    var items = docListEl.querySelectorAll(".kb-doc-item");
    for (var j = 0; j < items.length; j++) {
      (function(item) {
        item.addEventListener("click", function() {
          var id = this.getAttribute("data-id");
          openDocument(id);
        });
      })(items[j]);
    }
  }

  function getFilteredDocs() {
    var result = documents.slice();
    if (currentCategory !== "all") {
      result = result.filter(function(d) { return d.category === currentCategory; });
    }
    if (currentSearch) {
      var q = currentSearch.toLowerCase();
      result = result.filter(function(d) {
        return (d.title || "").toLowerCase().indexOf(q) >= 0 ||
               (d.content || "").toLowerCase().indexOf(q) >= 0;
      });
    }
    // Most recent first
    result.sort(function(a, b) {
      return (b.updatedAt || b.createdAt || "").localeCompare(a.updatedAt || a.createdAt || "");
    });
    return result;
  }

  function getCategoryIcon(cat) {
    var icons = { code: "💻", api: "🔗", concept: "🧠", guide: "📖", reference: "📌", other: "📦" };
    return icons[cat] || "📄";
  }

  function escHtml(text) {
    if (!text) return "";
    var div = document.createElement("div");
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
  }

  // ===== 打开文档 =====
  function openDocument(id) {
    for (var i = 0; i < documents.length; i++) {
      if (documents[i].id === id) {
        currentDocId = id;
        var doc = documents[i];
        docTitleEl.value = doc.title || "";
        docContentEl.value = doc.content || "";
        docCategoryEl.value = doc.category || "other";
        showEditor();
        renderDocList();
        return;
      }
    }
  }

  // ===== 新建文档 =====
  function newDocument() {
    currentDocId = null;
    docTitleEl.value = "";
    docContentEl.value = "";
    docCategoryEl.value = currentCategory !== "all" ? currentCategory : "code";
    showEditor();
    docTitleEl.focus();
  }

  // ===== 保存文档 =====
  function saveDocument() {
    var title = (docTitleEl.value || "").trim();
    var content = (docContentEl.value || "").trim();
    if (!title && !content) {
      NexusUI.toast("Please add a title or content.", "error");
      return;
    }
    if (!title) title = "Untitled";

    var now = getTimestamp();

    if (currentDocId) {
      // Update existing
      for (var i = 0; i < documents.length; i++) {
        if (documents[i].id === currentDocId) {
          documents[i].title = title;
          documents[i].content = content;
          documents[i].category = docCategoryEl.value;
          documents[i].updatedAt = now;
          break;
        }
      }
    } else {
      // Create new
      var doc = {
        id: generateId(),
        title: title,
        content: content,
        category: docCategoryEl.value,
        createdAt: now,
        updatedAt: now
      };
      documents.push(doc);
      currentDocId = doc.id;
    }

    saveDocuments();
    renderDocList();
    NexusUI.toast("Saved: " + title, "success");
  }

  // ===== 删除文档 =====
  function deleteDocument() {
    if (!currentDocId) return;
    if (!confirm("Delete this document?")) return;
    documents = documents.filter(function(d) { return d.id !== currentDocId; });
    currentDocId = null;
    saveDocuments();
    renderDocList();
    showWelcome();
    NexusUI.toast("Document deleted.", "info");
  }

  // ===== 复制内容 =====
  function copyContent() {
    var content = docContentEl.value;
    if (!content) { NexusUI.toast("No content to copy.", "info"); return; }
    navigator.clipboard.writeText(content).then(function() {
      NexusUI.toast("Content copied!", "success");
    }).catch(function() {
      NexusUI.toast("Copy failed.", "error");
    });
  }

  // ===== 视图切换 =====
  function showEditor() {
    if (welcomeEl) welcomeEl.classList.add("hidden");
    if (editorEl) editorEl.classList.remove("hidden");
  }

  function showWelcome() {
    if (welcomeEl) welcomeEl.classList.remove("hidden");
    if (editorEl) editorEl.classList.add("hidden");
  }

  // ===== 分类 & 搜索 =====
  function setupCategories() {
    categoryBtns = document.querySelectorAll(".kb-cat");
    for (var i = 0; i < categoryBtns.length; i++) {
      (function(btn) {
        btn.addEventListener("click", function() {
          currentCategory = this.getAttribute("data-cat");
          categoryBtns.forEach(function(b) { b.classList.remove("active"); });
          this.classList.add("active");
          renderDocList();
        });
      })(categoryBtns[i]);
    }
  }

  function setupSearch() {
    if (!searchInputEl) return;
    searchInputEl.addEventListener("input", function() {
      currentSearch = this.value;
      renderDocList();
    });
  }

  // ===== 编辑器 =====
  function setupEditor() {
    if (!docContentEl) return;

    // Tab support
    docContentEl.addEventListener("keydown", function(e) {
      if (e.key === "Tab") {
        e.preventDefault();
        var start = this.selectionStart;
        var end = this.selectionEnd;
        this.value = this.value.substring(0, start) + "  " + this.value.substring(end);
        this.selectionStart = this.selectionEnd = start + 2;
      }
    });

    // Ctrl+S to save
    docContentEl.addEventListener("keydown", function(e) {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        saveDocument();
      }
    });

    docTitleEl.addEventListener("keydown", function(e) {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        saveDocument();
      }
    });
  }

  // ===== 按钮 =====
  function setupActions() {
    if (saveBtn) saveBtn.addEventListener("click", saveDocument);
    if (deleteBtn) deleteBtn.addEventListener("click", deleteDocument);
    var previewBtn = document.getElementById('kbPreviewBtn');
      // Preview toggle
    if (previewBtn) {
      previewBtn.addEventListener("click", function() {
        var isPreview = this.classList.toggle("active");
        if (isPreview) {
          // Show preview
          var content = docContentEl.value || "";
          var html = renderMarkdown(content);
          previewEl.innerHTML = html;
          previewEl.classList.remove("hidden");
          docContentEl.style.display = "none";
          this.textContent = "Edit";
        } else {
          // Show editor
          previewEl.classList.add("hidden");
          docContentEl.style.display = "";
          this.textContent = "Preview";
        }
      });
    }
  if (copyBtn) copyBtn.addEventListener("click", copyContent);
      // File upload
    var uploadBtn = document.getElementById('kbUploadBtn');
    var fileInput = document.getElementById('kbFileInput');
    if (uploadBtn && fileInput) {
      uploadBtn.addEventListener('click', function() {
        fileInput.click();
      });
      fileInput.addEventListener('change', function() {
        if (this.files && this.files[0]) {
          NexusKnowledge.uploadFile(this.files[0], function(err, doc) {
            if (err) {
              if (typeof NexusUI !== 'undefined' && NexusUI.toast) NexusUI.toast('Upload failed: ' + (err.message || ''), 'error');
            } else {
              if (typeof NexusUI !== 'undefined' && NexusUI.toast) NexusUI.toast('Uploaded: ' + (doc.title || ''), 'success');
            }
          });
          this.value = '';
        }
      });
    }
  if (kbAddBtn) kbAddBtn.addEventListener("click", newDocument);
  }

  // ===== 公开 API =====
    /** 简单 Markdown 渲染 */
  function renderMarkdown(text) {
    if (!text) return '<p class="text-muted">No content</p>';
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    var html = div.innerHTML;

    // Code blocks
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
    // Inline code
    html = html.replace(/`([^`\n]+?)`/g, '<code>$1</code>');
    // Headers
    html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>');
    html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^# (.+)$/gm, '<h2>$1</h2>');
    // Bold/Italic
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
    // Links
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
    // Lists
    html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');
    // Line breaks
    html = html.replace(/\n/g, '<br>');
    return '<div class="kb-preview-content">' + html + '</div>';
  }

  return {
    init: init,
    newDocument: newDocument,
    openDocumentById: function(id) { openDocument(id); },
    getAllDocuments: function() { return documents.slice(); },
    searchDocuments: function(query) {
      if (!query) return documents.slice();
      var q = query.toLowerCase();
      return documents.filter(function(d) {
        return (d.title || "").toLowerCase().indexOf(q) >= 0 ||
               (d.content || "").toLowerCase().indexOf(q) >= 0;
      });
    }
  };
})();



