const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  checkForUpdates: () => ipcRenderer.invoke('check-for-updates'),
  restartAndInstall: () => ipcRenderer.invoke('restart-and-install'),
  markUpdateDownloaded: () => ipcRenderer.invoke('mark-update-downloaded'),
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),
  getLogs: () => ipcRenderer.invoke('get-logs'),
  downloadLogs: () => ipcRenderer.invoke('download-logs'),
  appendLog: (logData) => ipcRenderer.invoke('append-log', logData),
  listEvidenceFiles: () => ipcRenderer.invoke('list-evidence-files'),
  readEvidenceFile: (filename) => ipcRenderer.invoke('read-evidence-file', filename),
  onUpdaterStatus: (callback) => {
    const listener = (_event, value) => callback(value);
    ipcRenderer.on('updater-status', listener);
    return () => ipcRenderer.removeListener('updater-status', listener);
  }
});
