# TriGenClaw

> Next-generation AI Desktop Workbench ¡ª 300+ Models, Code Assistant, Agent Orchestration, Skill Ecosystem

TriGenClaw is a unified AI development environment that integrates model chat, code assistance, agent workflow orchestration, and a skill ecosystem into a single desktop application. Built with pure HTML/CSS/JS (no framework), with an optional Electron desktop wrapper.

---

## Features

### P0 ¡ª Foundation ?
- **PWA Desktop App** ¡ª Installable via manifest.json + Service Worker
- **Sidebar Navigation** ¡ª Chat, Code, Agent, Skills, Knowledge, Settings
- **AI Chat** ¡ª SSE streaming responses from 300+ models
- **Model Selector** ¡ª Grouped model list with search and free tags
- **Chat History** ¡ª localStorage persistence, history panel with switch/delete
- **Settings** ¡ª Theme (dark/light), font size, tab size, data management, API config
- **Responsive** ¡ª Desktop and mobile layouts
- **Keyboard Shortcuts** ¡ª Enter to send, Ctrl+K focus, Esc close
- **Markdown Rendering** ¡ª Code blocks, tables, lists, images, links
- **PWA Install** ¡ª Android auto-prompt, iOS guide, desktop install

### P1 ¡ª Code Assistant ?
- **Code Editor** ¡ª Textarea with line numbers, scroll sync, Tab indentation
- **Syntax Highlighting** ¡ª JS/HTML/CSS/JSON keywords, strings, comments, numbers
- **File Tree** ¡ª Recursive directory rendering with expand/collapse
- **Built-in Terminal** ¡ª Commands: help, clear, ls, cat, pwd, echo, node, npm, date, whoami
- **AI Analysis** ¡ª Review, Explain, Optimize via real API calls (with simulated fallback)
- **Ctrl+S Save** ¡ª Auto-save + trigger AI review

### P2 ¡ª Agent Workshop ?
- **20 Preset Agents** ¡ª Full-stack, Frontend, Backend, Tester, PM, Designer, DevOps, Data Scientist, Security, Mobile, AI/ML, QA, Docs, Architect, DBA, Network, SysAdmin, Automation, Game Dev, Blockchain
- **Visual Canvas** ¡ª Drag & drop agent nodes, SVG bezier curve connections
- **Port Connections** ¡ª Output (cyan) ¡ú Input (green) ports, double-click to delete
- **Agent Config** ¡ª Model selection, temperature, max tokens, 5 tool permissions, system prompt
- **Workflow Execution** ¡ª Topological sort, simulated serial execution with real-time logging
- **Persistence** ¡ª localStorage save/load workflow configurations

### P3 ¡ª Skill Store ?
- **30+ Preset Skills** ¡ª Across 10 categories: Development, Testing, Optimization, Data, DevOps, Security, Mobile, Design, AI/ML
- **Category Filter** ¡ª Tag-based filtering with search
- **Install/Uninstall** ¡ª One-click install into localStorage, immediate effect
- **Custom Skills** ¡ª Modal form: name, description, icon, prompt, triggers, tools, tokens
- **Triple View** ¡ª Browse all / Installed / My Skills tabs

### P4 ¡ª Electron Desktop ?
- **Native Window** ¡ª 1280x800 with dark theme background
- **System Tray** ¡ª Background resident, right-click menu (Show/New Chat/Open Code/Agent/Quit)
- **Global Shortcut** ¡ª `Alt+Space` to show/hide
- **Native Menu** ¡ª File (New/Open/Save), Edit (Undo/Redo/Cut/Copy/Paste), View (DevTools/Zoom), Help (About/Update)
- **IPC File System** ¡ª Full CRUD via `file:list/read/write/delete/create`, dialog-based folder selection
- **Context Isolation** ¡ª Secure preload bridge with `contextBridge.exposeInMainWorld`
- **Auto Updater** ¡ª `electron-updater` with progress notifications and install prompts
- **Code.js Integration** ¡ª Native file tree replaces built-in when Electron is detected

### P5 ¡ª Polish ?
- **Splash Screen** ¡ª Animated loading screen with pulsing logo and progress bar
- **Skeleton Screens** ¡ª Shimmer loading placeholders for chat, code editor, and agent panels
- **Error Boundary** ¡ª Global `window.onerror` + `onunhandledrejection` handler with friendly error UI
- **Panel Animations** ¡ª Fade-in transitions for all panels
- **Loading States** ¡ª Overlay spinners and backdrop blur for async operations
- **Lazy Loading** ¡ª Native `loading="lazy"` for images with fade-in
- **Empty States** ¡ª Graceful placeholders for all empty views
- **Comprehensive Docs** ¡ª This README

---

## Architecture

```
trigenclaw/
©À©¤©¤ index.html          # SPA entry ¡ª sidebar, chat, code, agent, skills, settings
©À©¤©¤ manifest.json        # PWA manifest
©À©¤©¤ sw.js                # Service Worker (offline cache)
©À©¤©¤ main.js              # Electron main process
©À©¤©¤ preload.js           # Electron preload bridge
©À©¤©¤ package.json         # Electron + build config
©À©¤©¤ build/               # Build resources
©À©¤©¤ css/
©¦   ©¸©¤©¤ style.css        # All styles (~45KB)
©¸©¤©¤ js/
    ©À©¤©¤ api.js           # Backend API: SSE streaming, auth, model list
    ©À©¤©¤ models.js        # Model management: groups, search, selection
    ©À©¤©¤ chat.js          # Chat: streaming, history, code analysis API
    ©À©¤©¤ code.js          # Code assistant: editor, syntax highlighting, terminal, file tree
    ©À©¤©¤ agent.js         # Agent workshop: 20 roles, canvas, connections, execution
    ©À©¤©¤ skills.js        # Skill store: 30+ skills, install, custom creation
    ©À©¤©¤ ui.js            # UI: panel switching, toasts, keyboard shortcuts, skeletons
    ©¸©¤©¤ app.js           # Entry: init, SW, PWA, error boundary, splash
```

### Design Principles

- **Zero Framework** ¡ª Pure HTML5 + CSS3 + Vanilla JS (ES6+). No React, no Vue, no build step.
- **SPA Architecture** ¡ª Single page, view switching via CSS `display: none/block`, no page reloads.
- **Dark First** ¡ª Dark theme by default with light theme option. CSS variables for theming.
- **Responsive** ¡ª Desktop (`>=768px`) and mobile (`<768px`) layouts with media queries.
- **IIFE Modules** ¡ª Each JS module wrapped in an IIFE, exposed via global namespace (`NexusChat`, `NexusCode`, etc.).
- **localStorage Persistence** ¡ª Chat history, settings, installed skills, saved workflows.
- **Progressive Enhancement** ¡ª Works in browser (PWA), enhanced in Electron (native FS, tray, shortcuts).

### Color System

| Token | Dark | Light |
|-------|------|-------|
| Primary | `#00d4ff` | `#00d4ff` |
| Secondary | `#7b2ff7` | `#7b2ff7` |
| Background | `#0f0f23` | `#f5f5fa` |
| Card | `#1a1a2e` | `#ffffff` |
| Text | `#e0e0e0` | `#1a1a2e` |

---

## Getting Started

### In Browser (PWA)
Open `index.html` in any modern browser. No build step required.

```bash
# Serve locally (recommended to avoid CORS issues with Service Worker)
npx serve trigenclaw/
# Or just open the file directly
open trigenclaw/index.html
```

### Electron Desktop App

```bash
cd trigenclaw
npm install
npm start              # Development mode (DevTools auto-open)
npm run dev            # Same as above
```

### Build for Distribution

```bash
# Windows (NSIS installer + portable)
npm run build:win

# macOS (DMG + ZIP)
npm run build:mac

# Linux (AppImage + deb)
npm run build:linux

# All platforms
npm run build
```

### API Configuration

By default, the app connects to `https://j3trisheng.com/api/chat`. To use with your own API:

1. Open **Settings** panel (gear icon)
2. Enter your **API Key** (optional for some providers)
3. Update the **API URL** if needed
4. Models will load automatically from `/api/models`

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | SSE streaming chat |
| GET | `/api/models` | List 300+ models |
| POST | `/api/auth/login` | Login |
| POST | `/api/auth/register` | Register |

```json
// Chat request
{ "model": "deepseek-chat", "messages": [{"role":"user","content":"Hello"}], "stream": true }
// Chat response (SSE)
data: {"choices":[{"delta":{"content":"Hello!"}}]}
```

---

## Testing

### In Browser
| Feature | How to Test |
|---------|-------------|
| **Chat** | Type a message and press Enter. Select models from the dropdown. |
| **Code** | Click the Code icon. Explore the file tree, edit code, click Review/Explain/Optimize. |
| **Terminal** | In the Code panel, type `help`, `ls`, `cat index.html`, `npm start`. |
| **Agent** | Click the Agent icon. Browse 20 agent cards, drag to canvas, connect ports. |
| **Skills** | Click the Skills icon. Browse 30+ skills, install one, create a custom skill. |
| **Settings** | Toggle theme, adjust font sizes, clear data, configure API. |
| **Keyboard** | `Enter` send, `Ctrl+K` focus input, `Esc` close panels. |

### In Electron
| Feature | How to Test |
|---------|-------------|
| **Window** | `npm start` ¡ª window opens with splash screen, then app loads. |
| **Tray** | Minimize ¡ª app hides to system tray. Right-click tray icon for menu. |
| **Shortcut** | Press `Alt+Space` anywhere to show/hide the app. |
| **Menu** | File > Open Folder ¡ª opens a folder and loads the file tree natively. |
| **Native FS** | Open a project folder, edit files, save ¡ª writes directly to disk. |
| **DevTools** | F12 or View > Developer Tools. |

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` | Send message |
| `Shift+Enter` | New line in chat |
| `Ctrl+K` | Focus chat input |
| `Esc` | Close dropdowns / panels |
| `Ctrl+S` | Save current file + trigger AI review |
| `Tab` | Insert spaces (in code editor) |
| `ArrowUp/Down` | Terminal command history |
| `Alt+Space` | (Electron) Show/hide window |
| `F12` | (Electron) Toggle DevTools |
| `F11` | (Electron) Toggle fullscreen |
| `Ctrl+Q` | (Electron) Quit app |

---

## Development

### Project Structure

Each JS module follows the IIFE pattern and exposes a global namespace:

```javascript
var NexusChat = (function() {
  'use strict';
  // private state and functions
  return { /* public API */ };
})();
```

### Code Conventions

- **Language**: Chinese comments for core logic, English for variable/function names
- **Formatting**: camelCase for functions and variables, PascalCase for constructors
- **Error handling**: try-catch with user-friendly Toast notifications
- **Mobile**: All panels must be usable on mobile (<768px)
- **SPA**: No page reloads ¡ª view switching via CSS class toggling

### Adding a New Panel

1. Add a nav item in `index.html`: `<button class="nav-item" data-panel="myPanel">`
2. Add a panel section: `<section id="myPanel" class="panel">`
3. Create a JS module: `var NexusMyPanel = (function() { ... })();`
4. Add the script tag in `index.html`
5. Register initialization in `ui.js` `switchPanel()` function
6. Add CSS styles in `style.css`

---

## Roadmap

- [ ] **P3**: Knowledge Base (RAG, document management, team sharing)
- [ ] **P4**: Electron: Notifications, custom titlebar, native file dialogs
- [ ] **P5**: i18n (Chinese/English), performance (virtual scroll), enterprise features

---

## License

MIT ? TriGenClaw
