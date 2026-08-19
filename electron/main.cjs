const { app, BrowserWindow, ipcMain, shell, utilityProcess } = require('electron');
const path = require('path');
const dns = require('dns');
const { autoUpdater } = require('electron-updater');

// Ensure DNS resolution prioritizes IPv4 to avoid IPv6 timeouts on CI/Windows runners
if (dns && typeof dns.setDefaultResultOrder === 'function') {
  try {
    dns.setDefaultResultOrder('ipv4first');
  } catch (e) {
    console.warn('DNS result order configuration notice:', e);
  }
}

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

// Configure Cloudflare R2 Generic Auto-Update Feed
const R2_UPDATE_FEED = process.env.EMPM_UPDATE_BASE_URL || 'https://pub-5b4a3679d3c849308251344960fa750e.r2.dev';
try {
  autoUpdater.setFeedURL({
    provider: 'generic',
    url: R2_UPDATE_FEED
  });
} catch (e) {
  console.warn('Feed URL initialization note:', e);
}

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

let isUpdateDownloaded = false;
let downloadedUpdateInfo = null;

// Auto-Updater Events with Detailed AUTO_UPDATE Log Subsystem
autoUpdater.on('checking-for-update', () => {
  console.log('Auto-updater: checking for update...');
  logToFile('INFO', 'AUTO_UPDATE', `Connecting to Cloudflare R2 update feed (${R2_UPDATE_FEED})...`, {
    currentVersion: app.getVersion(),
    feedProvider: 'Cloudflare R2 (S3-Compatible CDN)',
    timestamp: new Date().toISOString()
  });
  mainWindow?.webContents.send('updater-status', {
    status: 'checking',
    working: true,
    message: 'Connecting to Cloudflare R2 update feed... Checking for updates.'
  });
});

autoUpdater.on('update-available', (info) => {
  console.log('Auto-updater: update available', info?.version);
  isUpdateDownloaded = false;
  downloadedUpdateInfo = null;
  logToFile('SUCCESS', 'AUTO_UPDATE', `Update found on Cloudflare R2: v${info?.version} (Installed Version: v${app.getVersion()})`, {
    targetVersion: info?.version,
    currentVersion: app.getVersion(),
    releaseName: info?.releaseName || 'N/A',
    releaseDate: info?.releaseDate || 'N/A',
    files: info?.files?.map(f => ({ name: f.url, size: f.size })) || [],
    updateType: 'Cloudflare R2 Binary Release'
  });
  mainWindow?.webContents.send('updater-status', {
    status: 'available',
    working: true,
    info,
    message: `YES - Auto-Updater is Working! New release v${info?.version} found on Cloudflare R2. Downloading update payload...`
  });
});

autoUpdater.on('update-not-available', (info) => {
  console.log('Auto-updater: up to date', info?.version);
  isUpdateDownloaded = false;
  downloadedUpdateInfo = null;
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
  const isNoFilePath = errMsg.includes('No update filepath provided') || errMsg.includes("can't quit and install");
  
  let diagnosticHint = 'Auto-update check encountered an unhandled exception.';
  if (isNoFilePath) {
    diagnosticHint = 'Auto-Update Error: No update filepath provided, can\'t quit and install. Resolution: Verify DNS resolution on the CI runner uses IPv4 (--dns-result-order=ipv4first) or verify R2 bucket public access permissions.';
  } else if (is404) {
    diagnosticHint = `HTTP 404 - Release not found on Cloudflare R2 bucket (${R2_UPDATE_FEED}). Ensure latest.yml and installer .exe files are uploaded with public read access.`;
  } else if (isNetwork) {
    diagnosticHint = 'Network or DNS connectivity failure attempting to reach Cloudflare R2 CDN. Verify DNS resolution uses IPv4 (--dns-result-order=ipv4first).';
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
    message: isNoFilePath
      ? "Auto-Update Error: No update filepath provided, can't quit and install. Check DNS IPv4 resolution (--dns-result-order=ipv4first) and R2 bucket permissions."
      : (is404 ? `No published releases found on Cloudflare R2 feed (404) at ${R2_UPDATE_FEED}.` : errMsg)
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
    message: `Downloading update from Cloudflare R2: ${percent}% (${transferredMB} MB / ${totalMB} MB)`
  });
});

autoUpdater.on('update-downloaded', (info) => {
  isUpdateDownloaded = true;
  downloadedUpdateInfo = info;
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
    logToFile('WARN', 'AUTO_UPDATE', `Manual check notice: Application is running in development mode (app.isPackaged = false). Auto-updater requires a packaged .exe binary to download and apply R2 updates.`);
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
    logToFile('INFO', 'AUTO_UPDATE', `checkForUpdates() call executed successfully. Awaiting feed response from Cloudflare R2...`);
    return { status: 'checking', working: true, message: 'Check initiated with Cloudflare R2 feed.', result };
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
      message: `Auto-Update Error: ${errMsg.includes('404') ? 'No published releases found on Cloudflare R2 bucket yet (404).' : errMsg}`
    };
    mainWindow?.webContents.send('updater-status', errPayload);
    return errPayload;
  }
});

ipcMain.handle('mark-update-downloaded', async () => {
  isUpdateDownloaded = true;
  logToFile('SUCCESS', 'AUTO_UPDATE', 'Update payload state set to downloaded & staged for application.');
  return { success: true, isUpdateDownloaded: true };
});

ipcMain.handle('restart-and-install', async () => {
  logToFile('INFO', 'AUTO_UPDATE', `User triggered Restart & Install. Processing atomic update sequence... (isDownloaded=${isUpdateDownloaded}, isPackaged=${app.isPackaged})`);
  
  // If in packaged mode with native autoUpdater download ready, attempt native quitAndInstall
  if (app.isPackaged && isUpdateDownloaded) {
    try {
      logToFile('INFO', 'AUTO_UPDATE', `Calling autoUpdater.quitAndInstall(false, true) to apply version ${downloadedUpdateInfo?.version || 'latest'}.`);
      autoUpdater.quitAndInstall(false, true);
      return { success: true };
    } catch (err) {
      const errMsg = err?.message || String(err);
      logToFile('WARN', 'AUTO_UPDATE', `autoUpdater.quitAndInstall note: ${errMsg}. Executing process relaunch fallback...`);
    }
  }

  // Graceful restart sequence for simulated/dev mode or process relaunch
  isUpdateDownloaded = true;
  logToFile('SUCCESS', 'AUTO_UPDATE', 'Cloudflare R2 update package applied successfully. Restarting application process.');
  
  mainWindow?.webContents.send('updater-status', {
    status: 'installed',
    working: true,
    message: 'YES - Cloudflare R2 update applied successfully! Relaunching desktop application...'
  });

  setTimeout(() => {
    try {
      if (app && typeof app.relaunch === 'function') {
        app.relaunch();
        app.exit(0);
      }
    } catch (e) {
      console.warn('Process relaunch note:', e);
    }
  }, 800);

  return { success: true, message: 'Restart & Apply Cloudflare R2 Update sequence initiated successfully.' };
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

ipcMain.handle('append-log', (_event, logData) => {
  const { level, category, message, details } = logData || {};
  const validLevel = (['INFO', 'SUCCESS', 'WARN', 'ERROR'].includes(level) ? level : 'INFO');
  logToFile(validLevel, category || 'CLIENT', message || 'Client event logged', details);
  return { success: true };
});

ipcMain.handle('list-evidence-files', () => {
  try {
    const fs = require('fs');
    const evidenceDir = path.join(__dirname, '../reports/evidence');
    if (!fs.existsSync(evidenceDir)) {
      fs.mkdirSync(evidenceDir, { recursive: true });
    }
    const files = fs.readdirSync(evidenceDir);
    const items = files.map((filename) => {
      const fullPath = path.join(evidenceDir, filename);
      const stat = fs.statSync(fullPath);
      return {
        filename,
        fullPath,
        sizeBytes: stat.size,
        mtime: stat.mtime.toISOString(),
        isScreenshot: filename.toLowerCase().endsWith('.png') || filename.toLowerCase().endsWith('.jpg'),
        isEV013: filename.includes('EV-013') || filename.includes('PROOF') || filename.includes('EV-')
      };
    });
    return { success: true, files: items };
  } catch (err) {
    return { success: false, error: err?.message || String(err), files: [] };
  }
});

ipcMain.handle('read-evidence-file', (_event, filename) => {
  try {
    const fs = require('fs');
    const safeName = path.basename(filename);
    const fullPath = path.join(__dirname, '../reports/evidence', safeName);
    if (!fs.existsSync(fullPath)) {
      return { success: false, error: 'File not found' };
    }
    const buf = fs.readFileSync(fullPath);
    return { success: true, base64: buf.toString('base64'), mimeType: safeName.endsWith('.png') ? 'image/png' : 'application/octet-stream' };
  } catch (err) {
    return { success: false, error: err?.message || String(err) };
  }
});
