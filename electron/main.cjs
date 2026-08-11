const { app, BrowserWindow, ipcMain, shell, utilityProcess } = require('electron');
const path = require('path');
const { autoUpdater } = require('electron-updater');

// Handle uncaught exceptions gracefully without throwing fatal UI dialogs
process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception in Main Process:', error);
});

process.on('unhandledRejection', (reason) => {
  console.error('Unhandled Rejection in Main Process:', reason);
});

let mainWindow;
let backendProcess = null;

// Configure autoUpdater logs
autoUpdater.logger = console;
autoUpdater.autoDownload = true;

function loadURLWithRetry(win, url, attempts = 0) {
  win.loadURL(url).catch((err) => {
    console.log(`Waiting for backend server at ${url} (attempt ${attempts + 1})...`);
    if (attempts > 40 && !win.isDestroyed()) {
      const fs = require('fs');
      const localIndexPath = path.join(__dirname, '../dist/index.html');
      if (fs.existsSync(localIndexPath)) {
        console.log(`Fallback loading static file: ${localIndexPath}`);
        win.loadFile(localIndexPath);
        return;
      }
    }
    setTimeout(() => {
      if (!win.isDestroyed()) {
        loadURLWithRetry(win, url, attempts + 1);
      }
    }, 250);
  });
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1366,
    height: 850,
    minWidth: 1024,
    minHeight: 700,
    title: 'EmpMonitor Desktop Dashboard Runner',
    backgroundColor: '#020617',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: false,
    },
  });

  loadURLWithRetry(mainWindow, 'http://127.0.0.1:3000');

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function startBackendServer() {
  const fs = require('fs');
  const { fork, spawn } = require('child_process');
  const serverScript = path.join(__dirname, '../dist/server.cjs');
  const serverTs = path.join(__dirname, '../server.ts');
  
  if (fs.existsSync(serverScript)) {
    try {
      console.log(`Initializing backend server from ${serverScript}...`);
      process.env.PORT = '3000';
      process.env.NODE_ENV = 'production';
      
      // Load bundled standalone Express server directly in Electron main process
      require(serverScript);
      console.log('Backend Express server initialized successfully in main process.');
    } catch (err) {
      console.error('Failed to require backend server script in main process:', err);
      try {
        backendProcess = fork(serverScript, [], {
          cwd: path.join(__dirname, '..'),
          env: { ...process.env, PORT: '3000', NODE_ENV: 'production' },
          stdio: 'ignore'
        });
      } catch (forkErr) {
        console.error('Failed to fork backend process:', forkErr);
      }
    }
  } else if (fs.existsSync(serverTs)) {
    try {
      console.log('dist/server.cjs not found. Starting server using tsx server.ts...');
      const npxCmd = process.platform === 'win32' ? 'npx.cmd' : 'npx';
      backendProcess = spawn(npxCmd, ['tsx', 'server.ts'], {
        cwd: path.join(__dirname, '..'),
        env: { ...process.env, PORT: '3000', NODE_ENV: 'development' },
        shell: true,
        stdio: 'pipe'
      });

      if (backendProcess.stdout) {
        backendProcess.stdout.on('data', (data) => console.log(`Backend: ${data.toString()}`));
      }
      if (backendProcess.stderr) {
        backendProcess.stderr.on('data', (data) => console.error(`Backend ERR: ${data.toString()}`));
      }
    } catch (err) {
      console.error('Failed to start server via tsx:', err);
    }
  }
}

app.whenReady().then(() => {
  startBackendServer();
  createWindow();

  // Check for updates automatically on startup
  if (app.isPackaged) {
    autoUpdater.checkForUpdatesAndNotify().catch((err) => {
      console.log('Startup auto-update check error (non-fatal):', err?.message || err);
    });
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (backendProcess) {
    try {
      backendProcess.kill();
    } catch (e) {
      console.error('Error stopping backend process:', e);
    }
  }
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
  try {
    return await autoUpdater.checkForUpdates();
  } catch (err) {
    console.error('Update check error:', err?.message || err);
    return { status: 'error', error: err?.toString(), message: 'No published versions found on GitHub yet.' };
  }
});

ipcMain.handle('restart-and-install', () => {
  autoUpdater.quitAndInstall();
});

ipcMain.handle('get-app-version', () => {
  return app.getVersion();
});
