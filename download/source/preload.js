/* ========================================
   Electron preload - 安全桥接层
   通过 contextBridge 暴露 API 给渲染进程
   ======================================== */
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // ===== 文件系统 =====
  /** 列出目录内容 */
  listDirectory: function(dirPath) {
    return ipcRenderer.invoke('file:list', dirPath);
  },
  /** 读取文件内容 */
  readFile: function(filePath) {
    return ipcRenderer.invoke('file:read', filePath);
  },
  /** 写入文件 */
  writeFile: function(filePath, content) {
    return ipcRenderer.invoke('file:write', filePath, content);
  },
  /** 删除文件 */
  deleteFile: function(filePath) {
    return ipcRenderer.invoke('file:delete', filePath);
  },
  /** 创建文件 */
  createFile: function(filePath) {
    return ipcRenderer.invoke('file:create', filePath);
  },

  // ===== 对话框 =====
  /** 选择文件夹 */
  selectFolder: function() {
    return ipcRenderer.invoke('dialog:select-folder');
  },
  /** 打开文件选择 */
  openFile: function(opts) {
    return ipcRenderer.invoke('dialog:open-file', opts || null);
  },

  // ===== 应用信息 =====
  /** 获取版本号 */
  getVersion: function() {
    return ipcRenderer.invoke('app:version');
  },
  /** 获取平台信息 */
  getPlatform: function() {
    return ipcRenderer.invoke('app:platform');
  },

  // ===== Shell =====
  /** 打开外部链接 */
  openExternal: function(url) {
    return ipcRenderer.invoke('shell:open-external', url);
  },

  // ===== 窗口 =====
  /** 设置窗口大小 */
  setWindowSize: function(width, height) {
    return ipcRenderer.invoke('window:set-size', width, height);
  },

  // ===== 贾维斯设备控制 =====
  /** 搜索文件 */
  searchFile: function(query) {
    return ipcRenderer.invoke('device:search-file', query);
  },
  /** 打开文件/文件夹 */
  openPath: function(filePath) {
    return ipcRenderer.invoke('shell:open-path', filePath);
  },

  // ===== 事件监听 =====
  /** 监听主进程消息 */
  onMessage: function(channel, callback) {
    ipcRenderer.on(channel, function(event, data) {
      callback(data);
    });
  },
  /** 移除监听 */
  removeListener: function(channel, callback) {
    ipcRenderer.removeListener(channel, callback);
  },

  // ===== 剪贴板 =====
  copyToClipboard: function(text) {
    ipcRenderer.invoke('clipboard:write', text);
  },

  // ===== 更新 =====
  onUpdateProgress: function(callback) {
    ipcRenderer.on('update:progress', function(event, data) {
      callback(data);
    });
  }
});

// 通知渲染进程 Electron 环境已就绪
window.addEventListener('DOMContentLoaded', function() {
  document.body.setAttribute('data-electron', 'true');
});
