# TriGenClaw ¡ª Deployment Guide

Deploy as a subdirectory of the existing TriGen Hub (j3trisheng.com).

---

## 1. File Manifest

Deploy these files to \/home/admin/nexus-studio/\:

\\\
nexus-studio/
©À©¤©¤ index.html          # Main entry point (PWA, SSE chat, sidebar nav)
©À©¤©¤ manifest.json       # PWA manifest (data URI icons, no external assets)
©À©¤©¤ sw.js               # Service Worker (offline cache)
©À©¤©¤ css/
©¦   ©¸©¤©¤ style.css       # All styles (64 KB)
©À©¤©¤ js/
©¦   ©À©¤©¤ app.js          # Entry: init, error boundary, SW registration
©¦   ©À©¤©¤ api.js          # API layer: 10 providers, model routing, fallback
©¦   ©À©¤©¤ worker.js       # Web Worker for non-blocking SSE
©¦   ©À©¤©¤ chat.js         # Chat core: streaming, history, RAG
©¦   ©À©¤©¤ models.js       # 300+ model definitions, grouped, searchable
©¦   ©À©¤©¤ code.js         # Code editor, syntax highlight, terminal, file tree
©¦   ©À©¤©¤ agent.js        # Agent workshop: visual canvas, real execution
©¦   ©À©¤©¤ autonomous.js   # Autonomous agent mode
©¦   ©À©¤©¤ knowledge.js    # Knowledge base: CRUD, file upload, RAG search
©¦   ©À©¤©¤ skills.js       # Skill store: 30+ preset skills
©¦   ©À©¤©¤ storage.js      # IndexedDB persistent storage layer
©¦   ©À©¤©¤ ui.js           # All UI components (123 KB)
©¦   ©¸©¤©¤ plugin.js       # Plugin event system
©¸©¤©¤ build/              # (optional) Electron build assets
    ©¸©¤©¤ icon.png
\\\

**Total: ~17 files, ~350 KB gzipped.**

---

## 2. Server.js Change

Add **one line** to your Express app:

\\\js
// Add after your existing static/routes
app.use('/studio', express.static('/home/admin/nexus-studio'));
\\\

---

## 3. Deploy Steps

\\\ash
# 1. Copy files to server
scp -r /local/nexus-studio/* root@j3trisheng.com:/home/admin/nexus-studio/

# 2. SSH in
ssh root@j3trisheng.com

# 3. Verify structure
ls -la /home/admin/nexus-studio/

# 4. Edit server.js
nano /home/admin/server.js
# ¡ú Add: app.use('/studio', express.static('/home/admin/nexus-studio'));

# 5. Restart
pm2 restart ai-TriGen

# 6. Verify
curl -s http://localhost:3000/studio/ | head -5
# ¡ú Should return HTML with '<title>TriGenClaw</title>'
\\\

---

## 4. API Integration

The frontend already points to \https://j3trisheng.com\ as the default API proxy. No config needed.

Users can optionally configure their own API keys via Settings ¡ú API.

**Auth flow:** The frontend uses \
x_auth_token\ and \
x_api_key\ from localStorage. If your existing site sets these cookies/headers, the Studio will pick them up.

---

## 5. What Works Immediately

| Feature | Status |
|---------|--------|
| AI Chat (SSE streaming) | ? |
| 300+ model selection | ? |
| Chat history (localStorage) | ? |
| Code editor + syntax highlight | ? |
| Built-in terminal | ? |
| Agent workshop (real API) | ? |
| Skill store (30+ skills) | ? |
| Knowledge base + file upload | ? |
| RAG (auto search knowledge for context) | ? |
| API Key config (10 providers) | ? |
| Multi-provider auto-routing | ? |
| PWA installable | ? |
| Settings (theme/font/data) | ? |
| Keyboard shortcuts | ? |
| Markdown export | ? |
| i18n (EN/ZH) | ? |
