const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),
  isMaximized: () => ipcRenderer.invoke('window-isMaximized'),
  getVersion: () => ipcRenderer.invoke('app-getVersion'),
  checkUpdate: () => ipcRenderer.invoke('app-checkUpdate'),
});
