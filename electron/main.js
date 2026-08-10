const { app, BrowserWindow, ipcMain, shell } = require('electron');
const path = require('path');
const { autoUpdater } = require('electron-updater');
const { spawn } = require('child_process');

let mainWindow;
let pyProcess = null;

// Configure autoUpdater logs
autoUpdater.logger = console;
autoUpdater.autoDownload = true;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1366,
    height: 850,
    minWidth: 1024,
    minHeight: 700,
    title: 'EmpMonitor Desktop Dashboard Runner',
    backgroundColor: '#020617',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: false,
    },
  });

  const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;

  if (isDev) {
    mainWindow.loadURL('http://localhost:3000');
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function startBackendServer() {
  // Start server if packaged or needed
  if (app.isPackaged) {
    const serverScript = path.join(__dirname, '../dist/server.cjs');
    pyProcess = spawn('node', [serverScript], {
      cwd: path.join(__dirname, '..'),
      env: { ...process.env, PORT: '3000', NODE_ENV: 'production' }
    });

    pyProcess.stdout?.on('data', (data) => console.log(`Backend: ${data}`));
    pyProcess.stderr?.on('data', (data) => console.error(`Backend ERR: ${data}`));
  }
}

app.whenReady().then(() => {
  startBackendServer();
  createWindow();

  // Check for updates automatically on startup
  if (app.isPackaged) {
    autoUpdater.checkForUpdatesAndNotify();
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (pyProcess) pyProcess.kill();
  if (process.platform !== 'darwin') app.quit();
});

// Auto-Updater Events
autoUpdater.on('checking-for-update', () => {
  mainWindow?.webContents.send('updater-status', { status: 'checking', message: 'Checking for updates...' });
});

autoUpdater.on('update-available', (info) => {
  mainWindow?.webContents.send('updater-status', { status: 'available', info, message: `Update v${info.version} available. Downloading...` });
});

autoUpdater.on('update-not-available', (info) => {
  mainWindow?.webContents.send('updater-status', { status: 'not-available', info, message: 'App is up to date.' });
});

autoUpdater.on('error', (err) => {
  mainWindow?.webContents.send('updater-status', { status: 'error', error: err.toString(), message: 'Error checking updates.' });
});

autoUpdater.on('download-progress', (progressObj) => {
  mainWindow?.webContents.send('updater-status', {
    status: 'downloading',
    progress: progressObj.percent,
    bytesPerSecond: progressObj.bytesPerSecond,
    message: `Downloading update: ${Math.round(progressObj.percent)}%`
  });
});

autoUpdater.on('update-downloaded', (info) => {
  mainWindow?.webContents.send('updater-status', { status: 'downloaded', info, message: 'Update downloaded. Ready to install.' });
});

// IPC handlers
ipcMain.handle('check-for-updates', async () => {
  if (!app.isPackaged) {
    return { status: 'dev', message: 'Running in development mode.' };
  }
  return autoUpdater.checkForUpdates();
});

ipcMain.handle('restart-and-install', () => {
  autoUpdater.quitAndInstall();
});

ipcMain.handle('get-app-version', () => {
  return app.getVersion();
});
