/* ========================================
   Electron 主进程
   窗口管理、系统托盘、快捷键、菜单、IPC、自动更新
   ======================================== */
const { app, BrowserWindow, Tray, Menu, globalShortcut, ipcMain, dialog, shell, nativeImage, clipboard } = require('electron');
const path = require('path');
const fs = require('fs');

// ===== 常量 =====
const isDev = process.argv.includes('--dev') || !app.isPackaged;
const APP_NAME = 'TriGenClaw';
const WINDOW_WIDTH = 1280;
const WINDOW_HEIGHT = 800;
const MIN_WIDTH = 800;
const MIN_HEIGHT = 600;

let mainWindow = null;
let tray = null;
let isQuitting = false;
let currentProjectPath = null;

// ===== 主窗口 =====
function createWindow() {
  mainWindow = new BrowserWindow({
    width: WINDOW_WIDTH,
    height: WINDOW_HEIGHT,
    minWidth: MIN_WIDTH,
    minHeight: MIN_HEIGHT,
    title: APP_NAME,
    backgroundColor: '#0f0f23',
    show: false,
    icon: path.join(__dirname, 'build', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false
    }
  });

  mainWindow.loadFile('index.html');

  // 窗口就绪后显示（避免白屏）
  mainWindow.once('ready-to-show', function() {
    mainWindow.show();
    if (isDev) mainWindow.webContents.openDevTools();
  });

  // 最小化时隐藏到托盘
  mainWindow.on('minimize', function(e) {
    e.preventDefault();
    mainWindow.hide();
  });

  mainWindow.on('close', function(e) {
    if (!isQuitting) {
      e.preventDefault();
      mainWindow.hide();
    }
  });

  mainWindow.on('closed', function() {
    mainWindow = null;
  });
}

// ===== 系统托盘 =====
function createTray() {
  const iconPath = path.join(__dirname, 'build', 'tray-icon.png');
  let trayIcon;
  try {
    trayIcon = nativeImage.createFromPath(iconPath);
    if (trayIcon.isEmpty()) {
      // 创建纯色图标
      const size = 16;
      const buf = Buffer.alloc(size * size * 4);
      for (let i = 0; i < size * size; i++) {
        const x = i % size;
        const y = Math.floor(i / size);
        const cx = size / 2, cy = size / 2;
        const dist = Math.sqrt((x - cx) ** 2 + (y - cy) ** 2);
        if (dist < size / 2) {
          buf[i * 4] = 0;     // R
          buf[i * 4 + 1] = 212; // G
          buf[i * 4 + 2] = 255; // B
          buf[i * 4 + 3] = 200; // A
        } else {
          buf[i * 4 + 3] = 0; // transparent
        }
      }
      trayIcon = nativeImage.createFromBuffer(buf, { width: size, height: size });
    }
  } catch (e) {
    trayIcon = nativeImage.createEmpty();
  }

  tray = new Tray(trayIcon);
  tray.setToolTip(APP_NAME);

  const contextMenu = Menu.buildFromTemplate([
    { label: '显示 ' + APP_NAME, click: showWindow },
    { type: 'separator' },
    { label: '新对话', click: function() { sendToRenderer('action', 'new-chat'); showWindow(); } },
    { label: '打开代码', click: function() { sendToRenderer('action', 'open-code'); showWindow(); } },
    { label: 'Agent 工作台', click: function() { sendToRenderer('action', 'open-agent'); showWindow(); } },
    { type: 'separator' },
    { label: '退出', click: function() { isQuitting = true; app.quit(); } }
  ]);

  tray.setContextMenu(contextMenu);
  tray.on('double-click', showWindow);
}

function showWindow() {
  if (mainWindow) {
    mainWindow.show();
    mainWindow.focus();
  }
}

// ===== 原生菜单 =====
function createMenu() {
  const template = [
    {
      label: '文件',
      submenu: [
        { label: '新建文件', accelerator: 'CmdOrCtrl+N', click: function() { sendToRenderer('action', 'new-file'); } },
        { label: '打开文件夹...', accelerator: 'CmdOrCtrl+O', click: openFolderDialog },
        { type: 'separator' },
        { label: '保存', accelerator: 'CmdOrCtrl+S', click: function() { sendToRenderer('action', 'save-file'); } },
        { label: '另存为...', accelerator: 'CmdOrCtrl+Shift+S', click: saveFileDialog },
        { type: 'separator' },
        { label: '退出', accelerator: 'CmdOrCtrl+Q', click: function() { isQuitting = true; app.quit(); } }
      ]
    },
    {
      label: '编辑',
      submenu: [
        { role: 'undo', label: '撤销' },
        { role: 'redo', label: '重做' },
        { type: 'separator' },
        { role: 'cut', label: '剪切' },
        { role: 'copy', label: '复制' },
        { role: 'paste', label: '粘贴' },
        { role: 'selectAll', label: '全选' }
      ]
    },
    {
      label: '视图',
      submenu: [
        { label: '开发者工具', accelerator: 'F12', click: function() { mainWindow?.webContents.toggleDevTools(); } },
        { type: 'separator' },
        { label: '放大', accelerator: 'CmdOrCtrl+=', role: 'zoomIn' },
        { label: '缩小', accelerator: 'CmdOrCtrl+-', role: 'zoomOut' },
        { label: '重置缩放', accelerator: 'CmdOrCtrl+0', role: 'resetZoom' },
        { type: 'separator' },
        { label: '切换全屏', accelerator: 'F11', role: 'togglefullscreen' }
      ]
    },
    {
      label: '帮助',
      submenu: [
        { label: '关于 ' + APP_NAME, click: showAboutDialog },
        { type: 'separator' },
        { label: '检查更新', click: checkForUpdates }
      ]
    }
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

// ===== 对话框 =====
async function openFolderDialog() {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
    title: '选择项目文件夹'
  });
  if (!result.canceled && result.filePaths.length > 0) {
    currentProjectPath = result.filePaths[0];
    sendToRenderer('project:open', { path: currentProjectPath });
    // 读取目录结构
    const tree = readDirectoryTree(currentProjectPath);
    sendToRenderer('project:tree', tree);
  }
}

async function saveFileDialog() {
  const result = await dialog.showSaveDialog(mainWindow, {
    filters: [
      { name: '所有文件', extensions: ['*'] },
      { name: 'JavaScript', extensions: ['js', 'jsx', 'ts', 'tsx'] },
      { name: 'HTML', extensions: ['html', 'htm'] },
      { name: 'CSS', extensions: ['css', 'scss', 'less'] },
      { name: 'JSON', extensions: ['json'] },
      { name: 'Markdown', extensions: ['md', 'markdown'] }
    ]
  });
  if (!result.canceled && result.filePath) {
    sendToRenderer('project:save-as', { path: result.filePath });
  }
}

function showAboutDialog() {
  dialog.showMessageBox(mainWindow, {
    type: 'info',
    title: '关于 ' + APP_NAME,
    message: APP_NAME,
    detail: '版本 ' + app.getVersion() + '\n\n' +
      '下一代 AI 桌面工作台\n' +
      '集成 300+ 模型、代码助手、Agent 编排、技能生态\n\n' +
      'Electron: ' + process.versions.electron + '\n' +
      'Node: ' + process.versions.node + '\n' +
      'Chromium: ' + process.versions.chrome,
    buttons: ['确定']
  });
}

// ===== 自动更新 =====
let updateChecking = false;

function checkForUpdates() {
  if (updateChecking) return;
  updateChecking = true;

  try {
    const { autoUpdater } = require('electron-updater');
    autoUpdater.autoDownload = false;
    autoUpdater.setFeedURL({
      provider: 'generic',
      url: 'https://releases.trigenclaw.com'
    });

    autoUpdater.on('update-available', function(info) {
      updateChecking = false;
      dialog.showMessageBox(mainWindow, {
        type: 'info',
        title: '发现更新',
        message: '新版本 ' + info.version + ' 可用',
        detail: '当前版本: ' + app.getVersion() + '\n新版本: ' + info.version,
        buttons: ['下载更新', '稍后']
      }).then(function(result) {
        if (result.response === 0) {
          autoUpdater.downloadUpdate();
        }
      });
    });

    autoUpdater.on('update-not-available', function() {
      updateChecking = false;
      dialog.showMessageBox(mainWindow, {
        type: 'info',
        title: '已是最新',
        message: APP_NAME + ' 已是最新版本',
        detail: '当前版本: ' + app.getVersion()
      });
    });

    autoUpdater.on('download-progress', function(progress) {
      sendToRenderer('update:progress', progress);
    });

    autoUpdater.on('update-downloaded', function(info) {
      dialog.showMessageBox(mainWindow, {
        type: 'question',
        title: '更新已就绪',
        message: '更新已下载完成，是否立即安装？',
        buttons: ['立即安装', '稍后重启']
      }).then(function(result) {
        if (result.response === 0) {
          autoUpdater.quitAndInstall();
        }
      });
    });

    autoUpdater.on('error', function(err) {
      updateChecking = false;
      if (isDev) {
        dialog.showMessageBox(mainWindow, {
          type: 'info',
          title: '更新检查',
          message: '开发模式下跳过更新检查',
          detail: err ? err.message : ''
        });
      }
    });

    autoUpdater.checkForUpdates();

  } catch (e) {
    updateChecking = false;
  }
}

// ===== 全局快捷键 =====
function registerShortcuts() {
  // Alt+Space 唤起/隐藏
  globalShortcut.register('Alt+Space', function() {
    if (mainWindow) {
      if (mainWindow.isVisible()) {
        mainWindow.hide();
      } else {
        showWindow();
      }
    }
  });
}

// ===== 文件系统 IPC =====
function setupIPC() {
  // 读取目录树
  ipcMain.handle('file:list', async function(event, dirPath) {
    try {
      return readDirectoryTree(dirPath || currentProjectPath || __dirname);
    } catch (e) {
      return { error: e.message, path: dirPath, items: [] };
    }
  });

  // 读取文件
  ipcMain.handle('file:read', async function(event, filePath) {
    try {
      const content = fs.readFileSync(filePath, 'utf-8');
      return { success: true, content: content };
    } catch (e) {
      return { success: false, error: e.message };
    }
  });

  // 写入文件
  ipcMain.handle('file:write', async function(event, filePath, content) {
    try {
      const dir = path.dirname(filePath);
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(filePath, content, 'utf-8');
      return { success: true };
    } catch (e) {
      return { success: false, error: e.message };
    }
  });

  // 删除文件
  ipcMain.handle('file:delete', async function(event, filePath) {
    try {
      fs.unlinkSync(filePath);
      return { success: true };
    } catch (e) {
      return { success: false, error: e.message };
    }
  });

  // 创建文件
  ipcMain.handle('file:create', async function(event, filePath) {
    try {
      const dir = path.dirname(filePath);
      if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(filePath, '', 'utf-8');
      return { success: true };
    } catch (e) {
      return { success: false, error: e.message };
    }
  });

  // 选择文件夹对话框
  ipcMain.handle('dialog:select-folder', async function() {
    const result = await dialog.showOpenDialog(mainWindow, { properties: ['openDirectory'] });
    if (!result.canceled && result.filePaths.length > 0) {
      currentProjectPath = result.filePaths[0];
      return { success: true, path: currentProjectPath };
    }
    return { success: false };
  });

  // 获取应用版本
  ipcMain.handle('app:version', function() {
    return app.getVersion();
  });

  // 获取平台信息
  ipcMain.handle('app:platform', function() {
    return {
      platform: process.platform,
      electronVersion: process.versions.electron,
      nodeVersion: process.versions.node,
      chromeVersion: process.versions.chrome
    };
  });

  // 打开文件选择对话框
  ipcMain.handle('dialog:open-file', async function(event, opts) {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openFile'],
      filters: opts?.filters || [{ name: '所有文件', extensions: ['*'] }]
    });
    if (!result.canceled && result.filePaths.length > 0) {
      return { success: true, path: result.filePaths[0] };
    }
    return { success: false };
  });

  // 打开外部链接
  ipcMain.handle('shell:open-external', async function(event, url) {
    shell.openExternal(url);
  });

  // 设置窗口大小
  ipcMain.handle('window:set-size', function(event, width, height) {
    if (mainWindow) mainWindow.setSize(width, height);
  });
}

function readDirectoryTree(dirPath) {
  const items = [];
  try {
    const entries = fs.readdirSync(dirPath, { withFileTypes: true });
    for (const entry of entries) {
      // 跳过隐藏文件和 node_modules
      if (entry.name.startsWith('.') || entry.name === 'node_modules') continue;
      items.push({
        name: entry.name,
        type: entry.isDirectory() ? 'directory' : 'file',
        path: path.join(dirPath, entry.name)
      });
    }
    // 目录优先，然后按名称排序
    items.sort(function(a, b) {
      if (a.type !== b.type) return a.type === 'directory' ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
  } catch (e) {}
  return items;
}

// ===== 发送消息到渲染进程 =====
function sendToRenderer(channel, data) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send(channel, data);
  }
}

// ===== 应用生命周期 =====
app.whenReady().then(function() {
  createWindow();
  createMenu();
  setupIPC();
  registerShortcuts();

  // 延迟创建托盘（需要等窗口显示后）
  setTimeout(createTray, 1000);

  // 自动检查更新（非开发模式）
  if (!isDev) {
    setTimeout(checkForUpdates, 5000);
  }
});

app.on('window-all-closed', function() {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', function() {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  } else {
    showWindow();
  }
});

app.on('before-quit', function() {
  isQuitting = true;
});

app.on('will-quit', function() {
  globalShortcut.unregisterAll();
});
