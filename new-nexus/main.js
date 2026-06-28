const { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage } = require('electron');
const path = require('path');
const fs = require('fs');

let mainWindow;
let tray;

// Current app version — used for update checking
const APP_VERSION = '1.0.0';
const UPDATE_URL = 'https://raw.githubusercontent.com/trigen/desktop/main/VERSION';

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    frame: false,
    titleBarStyle: 'hidden',
    backgroundColor: '#f5f5f7',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    icon: path.join(__dirname, 'icons', 'icon.png'),
    show: false,
  });

  mainWindow.loadFile('index.html');

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    mainWindow.center();
  });

  // Minimize to tray instead of closing
  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
      return false;
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// System Tray
function createTray() {
  const iconPath = path.join(__dirname, 'icons', 'icon.png');
  let trayIcon;
  try {
    trayIcon = nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 });
  } catch(e) {
    // Fallback: create a simple 16x16 image
    trayIcon = nativeImage.createEmpty();
  }

  tray = new Tray(trayIcon);
  tray.setToolTip('Y·NEX Desktop');

  const contextMenu = Menu.buildFromTemplate([
    {
      label: '打开 Y·NEX Desktop',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
        }
      }
    },
    { type: 'separator' },
    {
      label: '检查更新',
      click: () => {
        checkForUpdates(true);
      }
    },
    { type: 'separator' },
    {
      label: '退出',
      click: () => {
        app.isQuitting = true;
        app.quit();
      }
    }
  ]);

  tray.setContextMenu(contextMenu);

  // Double-click on tray icon opens the window
  tray.on('double-click', () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

// Check for updates
function checkForUpdates(notifyUpToDate) {
  const https = require('https');
  const req = https.get(UPDATE_URL, { timeout: 5000 }, (res) => {
    let data = '';
    res.on('data', (chunk) => data += chunk);
    res.on('end', () => {
      const latestVersion = data.trim();
      if (latestVersion && latestVersion !== APP_VERSION) {
        // New version available
        const result = require('electron').dialog.showMessageBoxSync(mainWindow, {
          type: 'info',
          title: '发现新版本',
          message: `新版本 ${latestVersion} 可用！`,
          detail: `当前版本: ${APP_VERSION}\n最新版本: ${latestVersion}\n\n请访问官网下载最新版本。`,
          buttons: ['下载更新', '稍后提醒'],
          defaultId: 0,
        });
        if (result === 0) {
          require('electron').shell.openExternal('https://trigen.ai/download');
        }
      } else if (notifyUpToDate) {
        require('electron').dialog.showMessageBox(mainWindow, {
          type: 'info',
          title: '已是最新',
          message: `Y·NEX Desktop ${APP_VERSION} 已是最新版本。`,
        });
      }
    });
  });
  req.on('error', () => {
    if (notifyUpToDate) {
      require('electron').dialog.showMessageBox(mainWindow, {
        type: 'error',
        title: '检查更新失败',
        message: '无法连接到更新服务器，请检查网络连接。',
      });
    }
  });
  req.end();
}

// IPC handlers
ipcMain.on('window-minimize', () => {
  if (mainWindow) mainWindow.minimize();
});

ipcMain.on('window-maximize', () => {
  if (mainWindow) {
    mainWindow.isMaximized() ? mainWindow.unmaximize() : mainWindow.maximize();
  }
});

ipcMain.on('window-close', () => {
  if (mainWindow) mainWindow.close();
});

ipcMain.handle('window-isMaximized', () => {
  return mainWindow ? mainWindow.isMaximized() : false;
});

// Expose app info to renderer
ipcMain.handle('app-getVersion', () => APP_VERSION);
ipcMain.handle('app-checkUpdate', async () => {
  return new Promise((resolve) => {
    const https = require('https');
    const req = https.get(UPDATE_URL, { timeout: 5000 }, (res) => {
      let data = '';
      res.on('data', (chunk) => data += chunk);
      res.on('end', () => {
        const latest = data.trim();
        resolve({ current: APP_VERSION, latest: latest || APP_VERSION, hasUpdate: latest !== APP_VERSION && !!latest });
      });
    });
    req.on('error', () => resolve({ current: APP_VERSION, latest: APP_VERSION, hasUpdate: false }));
    req.end();
  });
});

app.whenReady().then(() => {
  createWindow();
  createTray();

  // Check for updates silently on startup
  setTimeout(() => checkForUpdates(false), 3000);

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
    else if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  app.isQuitting = true;
});
