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
  const { session } = require('electron');
  if (session && session.defaultSession) {
    session.defaultSession.setProxy({ proxyBypassRules: '<local>,127.0.0.1,localhost' }).catch(() => {});
  }

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
function logToFile(level, category, message, details) {
  try {
    const fs = require('fs');
    const rootLog = path.join(__dirname, '../log.txt');
    const timestamp = new Date().toISOString();
    let line = `[${timestamp}] [${level}] [${category}] ${message}`;
    if (details) {
      line += ` | Details: ${typeof details === 'object' ? JSON.stringify(details) : details}`;
    }
    line += '\n';

    [rootLog].forEach((p) => {
      try {
        fs.appendFileSync(p, line, 'utf-8');
      } catch (e) {}
    });
  } catch (e) {}
}

autoUpdater.on('checking-for-update', () => {
  console.log('Auto-updater: checking for update...');
  logToFile('INFO', 'AUTO_UPDATER', 'Checking for updates via GitHub Releases feed...');
  mainWindow?.webContents.send('updater-status', {
    status: 'checking',
    working: true,
    message: 'Connecting to GitHub Releases feed... Checking for updates.'
  });
});

autoUpdater.on('update-available', (info) => {
  console.log('Auto-updater: update available', info?.version);
  logToFile('SUCCESS', 'AUTO_UPDATER', `Update available: v${info?.version}`, info);
  mainWindow?.webContents.send('updater-status', {
    status: 'available',
    working: true,
    info,
    message: `YES - Auto-Updater is Working! New release v${info.version} found on GitHub. Downloading...`
  });
});

autoUpdater.on('update-not-available', (info) => {
  console.log('Auto-updater: up to date', info?.version);
  logToFile('SUCCESS', 'AUTO_UPDATER', `Application up to date (v${info?.version || '0.1.0'})`);
  mainWindow?.webContents.send('updater-status', {
    status: 'not-available',
    working: true,
    info,
    message: `YES - Auto-Updater is Working! You are on the latest version (v${info?.version || '0.1.0'}).`
  });
});

autoUpdater.on('error', (err) => {
  const errMsg = err?.message || err?.toString() || 'Unknown updater error';
  console.error('Auto-updater error:', errMsg);
  logToFile('ERROR', 'AUTO_UPDATER', `Auto-update error: ${errMsg}`);
  mainWindow?.webContents.send('updater-status', {
    status: 'error',
    working: false,
    error: errMsg,
    message: `Auto-Update Error: ${errMsg.includes('404') ? 'No published releases found on GitHub repo yet (404).' : errMsg}`
  });
});

autoUpdater.on('download-progress', (progressObj) => {
  logToFile('INFO', 'AUTO_UPDATER', `Download progress: ${Math.round(progressObj.percent)}%`);
  mainWindow?.webContents.send('updater-status', {
    status: 'downloading',
    working: true,
    progress: progressObj.percent,
    bytesPerSecond: progressObj.bytesPerSecond,
    message: `Downloading update from GitHub: ${Math.round(progressObj.percent)}%`
  });
});

autoUpdater.on('update-downloaded', (info) => {
  logToFile('SUCCESS', 'AUTO_UPDATER', `Update downloaded successfully: v${info?.version}`);
  mainWindow?.webContents.send('updater-status', {
    status: 'downloaded',
    working: true,
    info,
    message: `YES - Update v${info.version} downloaded successfully! Ready to restart and install.`
  });
});

// IPC handlers
ipcMain.handle('check-for-updates', async () => {
  logToFile('INFO', 'AUTO_UPDATER', 'User manually clicked Check For Updates');
  if (!app.isPackaged) {
    const devInfo = {
      status: 'dev',
      working: true,
      message: 'Running in development mode (app.isPackaged = false). Auto-updater triggers automatically in built .exe.'
    };
    mainWindow?.webContents.send('updater-status', devInfo);
    return devInfo;
  }
  try {
    const result = await autoUpdater.checkForUpdates();
    return { status: 'checking', working: true, message: 'Check initiated with GitHub Releases.', result };
  } catch (err) {
    const errMsg = err?.message || err?.toString() || 'Error checking updates';
    console.error('Update check exception:', errMsg);
    logToFile('ERROR', 'AUTO_UPDATER', `Check exception: ${errMsg}`);
    const errPayload = {
      status: 'error',
      working: false,
      error: errMsg,
      message: `Auto-Update Error: ${errMsg.includes('404') ? 'No published releases found on GitHub repo yet (404).' : errMsg}`
    };
    mainWindow?.webContents.send('updater-status', errPayload);
    return errPayload;
  }
});

ipcMain.handle('restart-and-install', () => {
  logToFile('INFO', 'AUTO_UPDATER', 'Triggered quitAndInstall');
  autoUpdater.quitAndInstall();
});

ipcMain.handle('get-app-version', () => {
  return app.getVersion();
});

ipcMain.handle('get-logs', () => {
  try {
    const fs = require('fs');
    const rootLog = path.join(__dirname, '../log.txt');
    let content = '';
    if (fs.existsSync(rootLog)) {
      content = fs.readFileSync(rootLog, 'utf-8');
    } else {
      content = `[EmpMonitor Log Initializing] ${new Date().toISOString()}\n`;
    }
    return { success: true, content };
  } catch (err) {
    return { success: false, error: err?.message || String(err) };
  }
});

ipcMain.handle('download-logs', async () => {
  const { dialog } = require('electron');
  const fs = require('fs');
  try {
    const rootLog = path.join(__dirname, '../log.txt');

    const { filePath } = await dialog.showSaveDialog(mainWindow, {
      title: 'Save Application Log Report',
      defaultPath: 'log.txt',
      filters: [{ name: 'Text Documents (*.txt)', extensions: ['txt'] }]
    });

    if (filePath) {
      if (fs.existsSync(rootLog)) {
        fs.copyFileSync(rootLog, filePath);
      } else {
        fs.writeFileSync(filePath, `[EmpMonitor System Log]\nCreated: ${new Date().toISOString()}\nNo events recorded yet.\n`, 'utf-8');
      }
      logToFile('INFO', 'SYSTEM', `Exported log.txt file to user location: ${filePath}`);
      return { success: true, filePath };
    }
    return { success: false, cancelled: true };
  } catch (err) {
    return { success: false, error: err?.message || String(err) };
  }
});
