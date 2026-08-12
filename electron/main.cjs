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

// Configure autoUpdater logs & dedicated logging channel
function logToFile(level, category, message, details) {
  try {
    const fs = require('fs');
    const os = require('os');
    const rootLog = path.join(__dirname, '../log.txt');
    const userLog = path.join(os.homedir(), '.empmonitor', 'log.txt');
    const timestamp = new Date().toISOString();
    let line = `[${timestamp}] [${level}] [${category}] ${message}`;
    if (details) {
      if (typeof details === 'object') {
        try {
          line += ` | Details: ${JSON.stringify(details)}`;
        } catch (e) {
          line += ` | Details: ${String(details)}`;
        }
      } else {
        line += ` | Details: ${details}`;
      }
    }
    line += '\n';

    [rootLog, userLog].forEach((p) => {
      try {
        const dir = path.dirname(p);
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
        fs.appendFileSync(p, line, 'utf-8');
      } catch (e) {}
    });
  } catch (e) {}
}

const autoUpdateLogger = {
  info: (msg, ...args) => {
    const text = [msg, ...args].map(a => (typeof a === 'object' ? JSON.stringify(a) : String(a))).join(' ');
    console.log('[autoUpdater:info]', text);
    logToFile('INFO', 'AUTO_UPDATE', text);
  },
  warn: (msg, ...args) => {
    const text = [msg, ...args].map(a => (typeof a === 'object' ? JSON.stringify(a) : String(a))).join(' ');
    console.warn('[autoUpdater:warn]', text);
    logToFile('WARN', 'AUTO_UPDATE', text);
  },
  error: (msg, ...args) => {
    const text = [msg, ...args].map(a => (typeof a === 'object' ? JSON.stringify(a) : String(a))).join(' ');
    console.error('[autoUpdater:error]', text);
    logToFile('ERROR', 'AUTO_UPDATE', text);
  },
  debug: (msg, ...args) => {
    const text = [msg, ...args].map(a => (typeof a === 'object' ? JSON.stringify(a) : String(a))).join(' ');
    console.debug('[autoUpdater:debug]', text);
    logToFile('DEBUG', 'AUTO_UPDATE', text);
  }
};

autoUpdater.logger = autoUpdateLogger;
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
    logToFile('INFO', 'AUTO_UPDATE', `Application startup auto-update check initiated (Version: v${app.getVersion()}, Platform: ${process.platform}-${process.arch}, Feed Provider: GitHub Releases)`);
    autoUpdater.checkForUpdatesAndNotify().catch((err) => {
      const errMsg = err?.message || String(err);
      logToFile('ERROR', 'AUTO_UPDATE', `Startup auto-update check error: ${errMsg}`, {
        version: app.getVersion(),
        isPackaged: app.isPackaged,
        errorStack: err?.stack || null
      });
    });
  } else {
    logToFile('INFO', 'AUTO_UPDATE', `Startup check skipped: Running in unpackaged/development mode (app.isPackaged = false, Current Version: v${app.getVersion()})`);
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

// Auto-Updater Events with Detailed AUTO_UPDATE Log Subsystem
autoUpdater.on('checking-for-update', () => {
  console.log('Auto-updater: checking for update...');
  logToFile('INFO', 'AUTO_UPDATE', 'Connecting to GitHub Releases feed (https://github.com/adsecurto-boop/Emp_Regression_suite/releases)...', {
    currentVersion: app.getVersion(),
    feedProvider: 'GitHub Releases (electron-updater)',
    timestamp: new Date().toISOString()
  });
  mainWindow?.webContents.send('updater-status', {
    status: 'checking',
    working: true,
    message: 'Connecting to GitHub Releases feed... Checking for updates.'
  });
});

autoUpdater.on('update-available', (info) => {
  console.log('Auto-updater: update available', info?.version);
  logToFile('SUCCESS', 'AUTO_UPDATE', `Update found on GitHub Releases: v${info?.version} (Installed Version: v${app.getVersion()})`, {
    targetVersion: info?.version,
    currentVersion: app.getVersion(),
    releaseName: info?.releaseName || 'N/A',
    releaseDate: info?.releaseDate || 'N/A',
    files: info?.files?.map(f => ({ name: f.url, size: f.size })) || [],
    updateType: 'GitHub Binary Release'
  });
  mainWindow?.webContents.send('updater-status', {
    status: 'available',
    working: true,
    info,
    message: `YES - Auto-Updater is Working! New release v${info?.version} found on GitHub. Downloading update payload...`
  });
});

autoUpdater.on('update-not-available', (info) => {
  console.log('Auto-updater: up to date', info?.version);
  logToFile('SUCCESS', 'AUTO_UPDATE', `Application is up-to-date. Version v${app.getVersion()} matches or is newer than feed (v${info?.version || app.getVersion()}).`, {
    installedVersion: app.getVersion(),
    latestFeedVersion: info?.version || app.getVersion(),
    checkedAt: new Date().toISOString()
  });
  mainWindow?.webContents.send('updater-status', {
    status: 'not-available',
    working: true,
    info,
    message: `YES - Auto-Updater is Working! You are on the latest version (v${app.getVersion()}).`
  });
});

autoUpdater.on('error', (err) => {
  const errMsg = err?.message || String(err);
  const errStack = err?.stack || 'No stack trace';
  const is404 = errMsg.includes('404') || errMsg.includes('Cannot find channel');
  const isNetwork = errMsg.includes('ENOTFOUND') || errMsg.includes('ETIMEDOUT') || errMsg.includes('net::ERR');
  
  let diagnosticHint = 'Auto-update check encountered an unhandled exception.';
  if (is404) {
    diagnosticHint = 'No published releases found on GitHub repository (HTTP 404). Ensure a release tag (e.g. v0.1.2) is published on github.com/adsecurto-boop/Emp_Regression_suite containing latest.yml and installer .exe.';
  } else if (isNetwork) {
    diagnosticHint = 'Network or DNS connectivity failure attempting to reach github.com / github-releases API.';
  }

  console.error('Auto-updater error:', errMsg);
  logToFile('ERROR', 'AUTO_UPDATE', `Auto-update error occurred: ${errMsg}`, {
    errorName: err?.name || 'UpdateError',
    errorMessage: errMsg,
    diagnosticHint,
    installedVersion: app.getVersion(),
    isPackaged: app.isPackaged,
    platform: process.platform,
    stackTrace: errStack
  });

  mainWindow?.webContents.send('updater-status', {
    status: 'error',
    working: false,
    error: errMsg,
    diagnosticHint,
    message: `Auto-Update Error: ${is404 ? 'No published releases found on GitHub repo yet (404).' : errMsg}`
  });
});

autoUpdater.on('download-progress', (progressObj) => {
  const percent = Math.round(progressObj.percent || 0);
  const transferredMB = ((progressObj.transferred || 0) / 1024 / 1024).toFixed(2);
  const totalMB = ((progressObj.total || 0) / 1024 / 1024).toFixed(2);
  const speedKBs = ((progressObj.bytesPerSecond || 0) / 1024).toFixed(1);

  if (percent === 0 || percent === 100 || percent % 25 === 0) {
    logToFile('INFO', 'AUTO_UPDATE', `Downloading update payload: ${percent}% (${transferredMB} MB / ${totalMB} MB @ ${speedKBs} KB/s)`, {
      percent,
      transferredBytes: progressObj.transferred,
      totalBytes: progressObj.total,
      bytesPerSecond: progressObj.bytesPerSecond
    });
  }

  mainWindow?.webContents.send('updater-status', {
    status: 'downloading',
    working: true,
    progress: progressObj.percent,
    bytesPerSecond: progressObj.bytesPerSecond,
    message: `Downloading update from GitHub: ${percent}% (${transferredMB} MB / ${totalMB} MB)`
  });
});

autoUpdater.on('update-downloaded', (info) => {
  logToFile('SUCCESS', 'AUTO_UPDATE', `Update package v${info?.version} downloaded successfully and checksum verified! Ready for restart and installation.`, {
    downloadedVersion: info?.version,
    releaseName: info?.releaseName || 'N/A',
    downloadedAt: new Date().toISOString()
  });
  mainWindow?.webContents.send('updater-status', {
    status: 'downloaded',
    working: true,
    info,
    message: `YES - Update v${info?.version} downloaded successfully! Ready to restart and install.`
  });
});

// IPC handlers
ipcMain.handle('check-for-updates', async () => {
  logToFile('INFO', 'AUTO_UPDATE', `Manual update check triggered by user (Current Version: v${app.getVersion()}, IsPackaged: ${app.isPackaged})`);
  
  if (!app.isPackaged) {
    logToFile('WARN', 'AUTO_UPDATE', `Manual check notice: Application is running in development mode (app.isPackaged = false). Auto-updater requires a packaged .exe binary to download and apply GitHub updates.`);
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
    logToFile('INFO', 'AUTO_UPDATE', `checkForUpdates() call executed successfully. Awaiting feed response...`);
    return { status: 'checking', working: true, message: 'Check initiated with GitHub Releases.', result };
  } catch (err) {
    const errMsg = err?.message || String(err);
    logToFile('ERROR', 'AUTO_UPDATE', `Manual checkForUpdates() exception: ${errMsg}`, {
      errorMessage: errMsg,
      stackTrace: err?.stack || null
    });
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
  logToFile('INFO', 'AUTO_UPDATE', `User triggered Restart & Install. Calling autoUpdater.quitAndInstall() to update application.`);
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
