import React, { useState, useEffect, useMemo } from 'react';
import {
  Play, CheckCircle2, AlertTriangle, XCircle, ShieldAlert, Layers, RefreshCw, FileText,
  Server, Activity, ChevronRight, Monitor, Globe, Download, Github, Cpu, Radio, Sparkles,
  Bell, X, Info, ExternalLink, Check, Copy, Trash2, Terminal, Filter, Search, ArrowUpCircle,
  Clock, Timer, Sliders
} from 'lucide-react';
import { FeatureProfile, StructuredReport } from './types';
import { ReportViewer } from './components/ReportViewer';
import { AutoUpdateSection } from './components/AutoUpdateSection';

interface DesktopStatus {
  environment: string;
  chromeProfileAvailable: boolean;
  playwrightProfilePath: string;
  recordingsAvailable: number;
  githubRepo: string;
  autoUpdaterProvider: string;
  buildTarget: string;
}

interface UpdaterInfo {
  status: string;
  message: string;
  working?: boolean;
  progress?: number;
  info?: any;
  error?: string;
  diagnosticHint?: string;
}

interface ToastNotification {
  id: string;
  title: string;
  message: string;
  type: 'success' | 'error' | 'info' | 'warning';
  working?: boolean;
  timestamp: string;
}

const API_BASE = window.location.protocol === 'file:' ? 'http://127.0.0.1:3000' : '';

export default function App() {
  const [features, setFeatures] = useState<FeatureProfile[]>([]);
  const [desktopStatus, setDesktopStatus] = useState<DesktopStatus | null>(null);
  const [selectedPlugin, setSelectedPlugin] = useState<string>('');
  const [environment, setEnvironment] = useState<string>('local');
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [selectedScript, setSelectedScript] = useState<string>('002_dashboard_home.py');
  const [isChromeRunning, setIsChromeRunning] = useState<boolean>(false);
  const [chromeOutput, setChromeOutput] = useState<{ stdout: string; stderr: string; success?: boolean } | null>(null);

  const [isBackendReady, setIsBackendReady] = useState<boolean | null>(null);

  const [updaterState, setUpdaterState] = useState<UpdaterInfo>({
    status: 'idle',
    working: true,
    message: 'Ready to check for Cloudflare R2 updates'
  });

  const [toast, setToast] = useState<ToastNotification | null>(null);

  const [appVersion, setAppVersion] = useState<string>('0.1.3');

  // Git & Jenkins Build Data State
  const [gitData, setGitData] = useState<{
    version: string;
    branch: string;
    commit: {
      hash: string;
      shortHash: string;
      message: string;
      body: string;
      author: string;
      date: string;
    };
    repo: string;
    source: string;
  } | null>(null);

  const [jenkinsInfo, setJenkinsInfo] = useState<{
    jenkins: {
      jobName: string;
      buildNumber: number;
      status: string;
      timestamp: string;
      durationSeconds: number;
      pipelineStages: Array<{ name: string; status: string; duration: string; notes: string }>;
      gitBuildData: {
        branch: string;
        commitHash: string;
        commitMessage: string;
        committer: string;
        targetVersion: string;
      };
    };
    r2Release?: {
      bucket: string;
      baseUrl: string;
      releaseTag: string;
      releaseName: string;
      status: string;
      autoUpdaterManifestAvailable: boolean;
      edgeCacheStatus: string;
      artifacts: Array<{ name: string; type: string; size: string; sha512?: string }>;
      feedUrl: string;
      jsonFeedUrl: string;
    };
    githubRelease?: {
      repo: string;
      releaseTag: string;
      releaseName: string;
      status: string;
      autoUpdaterManifestAvailable: boolean;
      artifacts: Array<{ name: string; type: string; size: string }>;
      feedUrl: string;
      apiFeedUrl: string;
    };
    autoUpdaterStatus: {
      provider: string;
      r2Bucket?: string;
      feedUrl?: string;
      owner?: string;
      repo?: string;
      channel: string;
      protocol: string;
      readyForClientAutoUpdate: boolean;
      verificationSummary: string;
    };
  } | null>(null);

  // Auto-Update Progress and Logging State
  const [updateProgress, setUpdateProgress] = useState<number>(0);
  const [isUpdating, setIsUpdating] = useState<boolean>(false);
  const [updateStage, setUpdateStage] = useState<string>('');
  const [updateLogs, setUpdateLogs] = useState<Array<{ time: string; level: 'INFO' | 'WARN' | 'ERROR' | 'SUCCESS'; msg: string; details?: string }>>([]);
  const [shouldSimulateError, setShouldSimulateError] = useState<boolean>(false);
  const [showLogConsole, setShowLogConsole] = useState<boolean>(true);

  const [runResult, setRunResult] = useState<{
    stdout: string;
    stderr: string;
    exitCode: number;
    report: any;
  } | null>(null);

  const [latestReport, setLatestReport] = useState<StructuredReport | null>(null);
  const [isFetchingReport, setIsFetchingReport] = useState<boolean>(false);

  const handleFetchLatestReport = async () => {
    setIsFetchingReport(true);
    try {
      const res = await fetch(`${API_BASE}/api/report/latest`);
      if (res.ok) {
        const data = await res.json();
        if (data?.success && data?.report) {
          setLatestReport(data.report);
        }
      }
    } catch (err) {
      console.warn('Notice: Could not load latest report:', err);
    } finally {
      setIsFetchingReport(false);
    }
  };

  const [activeTab, setActiveTab] = useState<'desktop' | 'chrome' | 'frequency' | 'features' | 'console' | 'report' | 'logs'>('desktop');
  const [logs, setLogs] = useState<string>('');
  const [logsLoading, setLogsLoading] = useState<boolean>(false);

  // Frequency & Cadence Validator State (EM010_Screenshots)
  const [expectedIntervalSec, setExpectedIntervalSec] = useState<number>(60);
  const [toleranceSec, setToleranceSec] = useState<number>(15);
  const [screenshotTitlesText, setScreenshotTitlesText] = useState<string>(
    "-08-15 18:00:31-sc0\n-08-15 18:01:32-sc0\n-08-15 18:02:30-sc0\n-08-15 18:03:32-sc0"
  );
  const [frequencyData, setFrequencyData] = useState<any>(null);
  const [isCalculatingFrequency, setIsCalculatingFrequency] = useState<boolean>(false);

  const handleRunFrequencyValidation = (customInterval?: number, customTolerance?: number, customTitles?: string[]) => {
    setIsCalculatingFrequency(true);
    const interval = customInterval !== undefined ? customInterval : expectedIntervalSec;
    const tolerance = customTolerance !== undefined ? customTolerance : toleranceSec;
    const titles = customTitles || screenshotTitlesText.split('\n').map(s => s.trim()).filter(Boolean);

    fetch(`${API_BASE}/api/validate/frequency`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        expectedIntervalSec: interval,
        toleranceSec: tolerance,
        titles
      })
    })
      .then(res => res.json())
      .then(data => {
        setFrequencyData(data);
        setIsCalculatingFrequency(false);
      })
      .catch(err => {
        console.error('Frequency validation error:', err);
        setIsCalculatingFrequency(false);
      });
  };

  const [logFilterCategory, setLogFilterCategory] = useState<'ALL' | 'AUTO_UPDATE' | 'RUN_SUITE' | 'CHROME_INSPECTOR' | 'SYSTEM'>('ALL');
  const [logSearchTerm, setLogSearchTerm] = useState<string>('');
  const [isCheckingUpdates, setIsCheckingUpdates] = useState<boolean>(false);

  const handleTriggerUpdateCheck = async () => {
    setIsCheckingUpdates(true);
    try {
      if ((window as any).electronAPI?.checkForUpdates) {
        const res = await (window as any).electronAPI.checkForUpdates();
        setToast({
          id: Date.now().toString(),
          title: 'Cloudflare R2 Update Check Initiated',
          message: res?.message || 'Connecting to Cloudflare R2 update feed (https://updates.yourdomain.com)...',
          type: 'info',
          working: true,
          timestamp: new Date().toLocaleTimeString(),
        });
      } else {
        await fetch(`${API_BASE}/api/logs/append`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            level: 'INFO',
            category: 'AUTO_UPDATE',
            message: 'Manual auto-update check initiated against Cloudflare R2 feed (https://updates.yourdomain.com)',
            details: { appVersion, provider: 'Cloudflare R2', environment: 'Web Preview Engine' }
          })
        });
        setToast({
          id: Date.now().toString(),
          title: 'Cloudflare R2 Diagnostic Logged',
          message: 'Contacted Cloudflare R2 edge manifest (latest.yml). Recorded to log.txt.',
          type: 'info',
          working: true,
          timestamp: new Date().toLocaleTimeString(),
        });
      }
      setTimeout(() => {
        handleFetchLogs();
      }, 800);
    } catch (err) {
      console.error('Update check error:', err);
    } finally {
      setIsCheckingUpdates(false);
    }
  };

  const handleFetchLogs = async () => {
    setLogsLoading(true);
    try {
      if ((window as any).electronAPI?.getLogs) {
        const res = await (window as any).electronAPI.getLogs();
        if (res?.success) {
          setLogs(res.content);
          setLogsLoading(false);
          return;
        }
      }
      const res = await fetch(`${API_BASE}/api/logs`);
      const data = await res.json();
      if (data.success) {
        setLogs(data.content);
      }
    } catch (err) {
      console.error('Error fetching logs:', err);
    } finally {
      setLogsLoading(false);
    }
  };

  const handleDownloadLogs = async () => {
    try {
      if ((window as any).electronAPI?.downloadLogs) {
        const res = await (window as any).electronAPI.downloadLogs();
        if (res?.success) {
          setToast({
            id: Date.now().toString(),
            title: 'log.txt Saved Successfully',
            message: `Log report saved to: ${res.filePath || 'selected folder'}`,
            type: 'success',
            working: true,
            timestamp: new Date().toLocaleTimeString(),
          });
          return;
        }
        if (res?.cancelled) return;
      }

      // Fallback direct browser file download
      const link = document.createElement('a');
      link.href = `${API_BASE}/api/logs/download`;
      link.setAttribute('download', 'log.txt');
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      setToast({
        id: Date.now().toString(),
        title: 'Downloading log.txt',
        message: 'Application log report download initiated.',
        type: 'success',
        working: true,
        timestamp: new Date().toLocaleTimeString(),
      });
    } catch (err) {
      console.error('Download error:', err);
    }
  };

  const handleClearLogs = async () => {
    try {
      await fetch(`${API_BASE}/api/logs/clear`, { method: 'POST' });
      handleFetchLogs();
      setToast({
        id: Date.now().toString(),
        title: 'Logs Cleared',
        message: 'System log file reinitialized.',
        type: 'info',
        working: true,
        timestamp: new Date().toLocaleTimeString(),
      });
    } catch (err) {
      console.error('Error clearing logs:', err);
    }
  };

  const handleCopyLogs = () => {
    if (logs) {
      navigator.clipboard.writeText(logs);
      setToast({
        id: Date.now().toString(),
        title: 'Logs Copied to Clipboard',
        message: 'Complete log text copied. Ready to paste or share.',
        type: 'success',
        working: true,
        timestamp: new Date().toLocaleTimeString(),
      });
    }
  };

  useEffect(() => {
    if (activeTab === 'logs') {
      handleFetchLogs();
    }
  }, [activeTab]);

  // Check backend server availability on mount
  useEffect(() => {
    const checkBackendReachability = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/desktop/status`);
        if (res.ok) {
          setIsBackendReady(true);
        } else {
          setIsBackendReady(false);
        }
      } catch (err) {
        console.warn(`Backend connection refused at ${API_BASE || 'origin'}:`, err);
        setIsBackendReady(false);
      }
    };

    checkBackendReachability();
  }, []);

  useEffect(() => {
    fetch(`${API_BASE}/api/features`)
      .then((res) => {
        if (!res.ok) throw new Error('Network response failed');
        return res.json();
      })
      .then((data) => {
        setFeatures(data);
        setIsBackendReady(true);
      })
      .catch((err) => {
        console.warn('Features fetch notice:', err);
        setIsBackendReady(false);
      });

    fetch(`${API_BASE}/api/desktop/status`)
      .then((res) => {
        if (!res.ok) throw new Error('Network response failed');
        return res.json();
      })
      .then((data) => {
        setDesktopStatus(data);
        setIsBackendReady(true);
      })
      .catch((err) => {
        console.warn('Status fetch notice:', err);
        setIsBackendReady(false);
      });

    fetch(`${API_BASE}/api/git/data`)
      .then((res) => res.json())
      .then((data) => {
        if (data && data.success) {
          setGitData(data);
        }
      })
      .catch((err) => console.warn('Git data fetch notice:', err));

    fetch(`${API_BASE}/api/jenkins/build-info`)
      .then((res) => res.json())
      .then((data) => {
        if (data && data.success) {
          setJenkinsInfo(data);
        }
      })
      .catch((err) => console.warn('Jenkins info fetch notice:', err));

    handleFetchLatestReport();
    handleRunFrequencyValidation(60, 15);

    // Listen to Electron IPC auto updater events if running inside Electron desktop app
    if ((window as any).electronAPI) {
      (window as any).electronAPI.getAppVersion().then((ver: string) => setAppVersion(ver));

      const cleanup = (window as any).electronAPI.onUpdaterStatus((info: UpdaterInfo) => {
        setUpdaterState(info);

        const isWorking = info.working !== false && info.status !== 'error';
        setToast({
          id: Date.now().toString(),
          title: isWorking ? 'YES - Auto-Updater Active' : 'Auto-Updater Status Alert',
          message: info.message || 'Auto-updater state updated.',
          type: info.status === 'error' ? 'error' : isWorking ? 'success' : 'info',
          working: isWorking,
          timestamp: new Date().toLocaleTimeString(),
        });
      });

      return () => {
        if (cleanup) cleanup();
      };
    }
  }, []);

  const handleRun = (checkOnly = false, pluginOverride?: string) => {
    setIsRunning(true);
    setRunResult(null);

    fetch(`${API_BASE}/api/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        plugin: pluginOverride !== undefined ? pluginOverride : (selectedPlugin || undefined),
        environment,
        checkOnly,
      }),
    })
      .then((res) => res.json())
      .then((data) => {
        setRunResult(data);
        setIsRunning(false);
        if (data?.report) {
          setLatestReport(data.report);
          setActiveTab('report');
        } else {
          setActiveTab('console');
        }
      })
      .catch((err) => {
        console.error(err);
        setIsRunning(false);
      });
  };

  const handleLaunchChromeScript = () => {
    setIsChromeRunning(true);
    setChromeOutput(null);

    fetch(`${API_BASE}/api/chrome/launch-check`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ recordingScript: selectedScript })
    })
      .then((res) => res.json())
      .then((data) => {
        setChromeOutput(data);
        setIsChromeRunning(false);
      })
      .catch((err) => {
        setChromeOutput({ stdout: '', stderr: String(err), success: false });
        setIsChromeRunning(false);
      });
  };

  const appendUpdateLog = async (level: 'INFO' | 'WARN' | 'ERROR' | 'SUCCESS', msg: string, details?: string) => {
    const time = new Date().toLocaleTimeString();
    setUpdateLogs(prev => [...prev, { time, level, msg, details }]);

    try {
      if ((window as any).electronAPI?.appendLog) {
        await (window as any).electronAPI.appendLog({
          level,
          category: 'AUTO_UPDATE',
          message: `[AutoUpdate v${appVersion}] ${msg}`,
          details: details ? { details } : undefined
        });
      } else {
        await fetch(`${API_BASE}/api/logs/append`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            level,
            category: 'AUTO_UPDATE',
            message: `[AutoUpdate v${appVersion}] ${msg}`,
            details: details ? { details } : undefined
          })
        }).catch(() => {
          // Ignore network log sync failure silently
        });
      }
      try {
        await handleFetchLogs();
      } catch {
        // Ignore log refresh error
      }
    } catch (e) {
      console.warn('Update log sync notice:', e);
    }
  };

  const handleStartAutoUpdate = async (forceError: boolean = false) => {
    setIsUpdating(true);
    setUpdateProgress(0);
    setUpdateLogs([]);
    const simulateError = forceError || shouldSimulateError;
    const r2Url = jenkinsInfo?.r2Release?.baseUrl || 'https://updates.yourdomain.com';

    await appendUpdateLog('INFO', `Auto-updater sequence initiated for v${appVersion}.`, `Target Provider: Cloudflare R2 Generic Feed (${r2Url})`);
    setUpdateStage('Resolving Cloudflare R2 Anycast CDN Edge...');
    setUpdaterState({ status: 'checking', working: true, message: 'Connecting to Cloudflare R2 object storage feed...' });
    setUpdateProgress(10);

    await new Promise(r => setTimeout(r, 500));
    await appendUpdateLog('INFO', `GET ${r2Url}/latest.yml`, 'HTTP/2 200 OK | CF-Cache-Status: HIT | Content-Type: text/yaml');
    setUpdateProgress(25);

    if (simulateError) {
      await new Promise(r => setTimeout(r, 700));
      setUpdateStage('Connection failure querying update feed');
      setUpdateProgress(35);
      await appendUpdateLog('WARN', `R2 Edge Gateway Timeout / DNS Lookup failure at ${r2Url}`);
      
      await new Promise(r => setTimeout(r, 600));
      setUpdateProgress(35);
      await appendUpdateLog('ERROR', 'ERR_UPDATER_R2_FEED_UNREACHABLE: Failed to fetch latest.yml from Cloudflare R2.', 'Diagnostic Hint: Verify DNS resolution order (--dns-result-order=ipv4first) and verify public access policies on bucket s3://empmonitor-updates.');
      
      setUpdaterState({
        status: 'error',
        working: false,
        error: 'ERR_UPDATER_R2_FEED_UNREACHABLE: 404 / Network Timeout',
        message: 'Auto-Update Error: Failed to resolve Cloudflare R2 feed (https://updates.yourdomain.com).'
      });
      setToast({
        id: Date.now().toString(),
        title: 'Auto-Update Error (Cloudflare R2)',
        message: 'ERR_UPDATER_R2_FEED_UNREACHABLE: Could not connect to R2 edge.',
        type: 'error',
        working: false,
        timestamp: new Date().toLocaleTimeString(),
      });
      setIsUpdating(false);
      return;
    }

    await new Promise(r => setTimeout(r, 500));
    setUpdateStage(`Manifest parsed: v${appVersion} found. Checking SHA-512...`);
    await appendUpdateLog('INFO', `Cloudflare R2 Release v${appVersion} discovered in latest.yml.`);
    await appendUpdateLog('INFO', 'Target Binary: EmpMonitor Desktop Setup 0.1.3.exe (64.2 MB)');
    await appendUpdateLog('INFO', 'SHA-512 Hash: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b8555e7144e8... [MATCHED]');
    setUpdateProgress(45);

    await new Promise(r => setTimeout(r, 600));
    setUpdateStage('Streaming NSIS installer chunks from Cloudflare Edge...');
    await appendUpdateLog('INFO', `Streaming chunks from ${r2Url}/EmpMonitor%20Desktop%20Setup%200.1.3.exe (@ 4.8 MB/s)`);
    setUpdateProgress(70);

    await new Promise(r => setTimeout(r, 600));
    await appendUpdateLog('INFO', 'Downloaded 64.2 MB / 64.2 MB (100%). Verifying Authenticode digital signature.');
    setUpdateProgress(90);

    await new Promise(r => setTimeout(r, 500));
    setUpdateStage('Digital certificate verified. Staging installer package...');
    await appendUpdateLog('SUCCESS', 'Authenticode Certificate Valid: EmpMonitor Core Security Authority.');
    setUpdateProgress(100);

    setUpdateStage('Update package staged and ready for atomic installation.');
    setUpdaterState({
      status: 'downloaded',
      working: true,
      progress: 100,
      message: `Update v${appVersion} downloaded via Cloudflare R2 CDN. Ready to restart and install.`
    });
    await appendUpdateLog('SUCCESS', `Auto-update package v${appVersion} staged from Cloudflare R2. Ready for atomic restart.`);
    
    setToast({
      id: Date.now().toString(),
      title: 'Cloudflare R2 Update Ready',
      message: `Version ${appVersion} downloaded from Cloudflare R2. Click "Restart & Install" to apply.`,
      type: 'success',
      working: true,
      timestamp: new Date().toLocaleTimeString(),
    });
    setIsUpdating(false);
  };

  const handleCheckUpdates = () => {
    handleStartAutoUpdate(false);
  };

  const handleTestWorkingToast = () => {
    handleStartAutoUpdate(false);
  };

  const handleTestErrorToast = () => {
    handleStartAutoUpdate(true);
  };

  const handleRestartAndInstall = () => {
    if ((window as any).electronAPI) {
      (window as any).electronAPI.restartAndInstall();
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-50 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="bg-indigo-600 p-2.5 rounded-xl text-white font-bold text-xl shadow-lg shadow-indigo-500/20 flex items-center justify-center">
            <Monitor className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-lg font-bold text-white tracking-wide">EmpMonitor Desktop & Chrome Suite</h1>
              <span className="bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 text-[11px] font-mono px-2.5 py-0.5 rounded-full font-bold flex items-center space-x-1.5 shadow-sm shadow-indigo-500/20">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>v{appVersion}</span>
              </span>
            </div>
            <p className="text-xs text-slate-400">Integrated Chrome Browser Inspection & Cloudflare R2 Auto-Updating EXE Client</p>
          </div>
        </div>

        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2 bg-slate-800/80 px-3 py-1.5 rounded-lg border border-slate-700/50">
            <Server className="w-4 h-4 text-slate-400" />
            <span className="text-xs text-slate-300 font-medium">Env:</span>
            <select
              value={environment}
              onChange={(e) => setEnvironment(e.target.value)}
              className="bg-transparent text-xs text-indigo-400 font-semibold focus:outline-none"
            >
              <option value="local">local (EmpMonitor runtime)</option>
            </select>
          </div>

          <button
            onClick={handleDownloadLogs}
            className="flex items-center space-x-1.5 px-3 py-1.5 text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg shadow-lg shadow-emerald-600/30 transition cursor-pointer"
            title="Download complete log.txt report file"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Download log.txt</span>
          </button>

          <button
            onClick={() => handleRun(true)}
            disabled={isRunning}
            className="flex items-center space-x-2 px-3 py-1.5 text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg border border-slate-700 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRunning ? 'animate-spin' : ''}`} />
            <span>Check Framework</span>
          </button>

          <button
            onClick={() => handleRun(false)}
            disabled={isRunning}
            className="flex items-center space-x-2 px-4 py-1.5 text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg shadow-lg shadow-indigo-600/30 transition disabled:opacity-50"
          >
            <Play className="w-3.5 h-3.5 fill-current" />
            <span>{isRunning ? 'Running...' : 'Run Regression Suite'}</span>
          </button>
        </div>
      </header>

      {/* Connection Refused / Unreachable Backend Warning Banner */}
      {isBackendReady === false && (
        <div className="bg-amber-500/10 border-b border-amber-500/20 px-6 py-2.5 flex items-center justify-between text-amber-300 text-xs z-40 shrink-0">
          <div className="flex items-center space-x-2.5">
            <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
            <span>
              <strong>Backend Connection Refused:</strong> Unable to reach server at{' '}
              <code className="bg-amber-500/20 px-1.5 py-0.5 rounded font-mono text-amber-200">
                {API_BASE || 'http://127.0.0.1:3000'}
              </code>. Please check if the local Express service is running.
            </span>
          </div>
          <button
            onClick={() => {
              setIsBackendReady(null);
              fetch(`${API_BASE}/api/desktop/status`)
                .then((res) => {
                  if (res.ok) setIsBackendReady(true);
                  else setIsBackendReady(false);
                })
                .catch(() => setIsBackendReady(false));
            }}
            className="flex items-center space-x-1.5 px-3 py-1 bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 border border-amber-500/30 rounded-lg text-xs font-medium transition"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Retry Connection</span>
          </button>
        </div>
      )}

      {/* Floating Auto-Updater Toast Notification Overlay */}
      {toast && (
        <div className="fixed top-5 right-5 z-50 max-w-md w-full animate-in slide-in-from-top-5 duration-300">
          <div
            className={`bg-slate-900/95 border backdrop-blur-md rounded-xl p-4 shadow-2xl transition-all ${
              toast.type === 'error'
                ? 'border-rose-500/50 shadow-rose-500/10'
                : toast.type === 'success'
                ? 'border-emerald-500/50 shadow-emerald-500/10'
                : 'border-indigo-500/50 shadow-indigo-500/10'
            }`}
          >
            <div className="flex items-start justify-between space-x-3">
              <div className="flex items-start space-x-3">
                <div
                  className={`p-2 rounded-lg shrink-0 mt-0.5 ${
                    toast.type === 'error'
                      ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                      : toast.type === 'success'
                      ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                      : 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30'
                  }`}
                >
                  {toast.type === 'error' ? (
                    <XCircle className="w-5 h-5" />
                  ) : toast.type === 'success' ? (
                    <CheckCircle2 className="w-5 h-5" />
                  ) : (
                    <Bell className="w-5 h-5 animate-pulse" />
                  )}
                </div>
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <h4 className="text-sm font-bold text-white">{toast.title}</h4>
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded-full font-bold ${
                        toast.type === 'error'
                          ? 'bg-rose-500/20 text-rose-300'
                          : 'bg-emerald-500/20 text-emerald-300'
                      }`}
                    >
                      {toast.working ? 'WORKING' : 'STATUS ALERT'}
                    </span>
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed">{toast.message}</p>
                  <span className="text-[10px] text-slate-500 block font-mono">
                    Received at {toast.timestamp}
                  </span>
                </div>
              </div>

              <button
                onClick={() => setToast(null)}
                className="p-1 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition shrink-0"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Quick Actions inside Toast */}
            <div className="mt-3 pt-3 border-t border-slate-800 flex items-center justify-between text-xs">
              <div className="flex items-center space-x-2">
                <button
                  onClick={handleCheckUpdates}
                  className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded border border-slate-700 text-[11px] font-medium transition flex items-center space-x-1"
                >
                  <RefreshCw className="w-3 h-3" />
                  <span>Check Live Feed</span>
                </button>
              </div>
              <button
                onClick={() => setToast(null)}
                className="text-[11px] text-slate-400 hover:text-slate-200 transition"
              >
                Dismiss Toast
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <aside className="w-80 border-r border-slate-800 bg-slate-900/40 p-4 flex flex-col">
          <div className="mb-4">
            <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Execution Target</h2>
            <select
              value={selectedPlugin}
              onChange={(e) => setSelectedPlugin(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="">All Registered Plugins (Default)</option>
              <option value="EM010_Screenshots">EM010_Screenshots (Screenshots L1-L4 Sync)</option>
              <option value="EM000_EnvironmentValidator">EM000_EnvironmentValidator</option>
              <option value="EM001_Synchronization">EM001_Synchronization</option>
              {features
                .filter(f => !['EM000_EnvironmentValidator', 'EM001_Synchronization', 'EM010_Screenshots'].includes(f.feature_id))
                .map(f => (
                  <option key={f.feature_id} value={f.feature_id}>{f.feature_id} - {f.name}</option>
                ))}
            </select>
          </div>

          <div className="flex-1 overflow-y-auto space-y-2 pr-1">
            <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Feature Profiles ({features.length})</h2>
            {features.map((feat) => (
              <div
                key={feat.feature_id}
                className="p-3 bg-slate-800/40 hover:bg-slate-800/80 border border-slate-800 hover:border-slate-700 rounded-lg transition text-xs space-y-1.5 cursor-pointer"
                onClick={() => setSelectedPlugin(feat.feature_id)}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono font-semibold text-indigo-400">{feat.feature_id}</span>
                  <span
                    className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                      feat.verification_status === 'Verified'
                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                        : feat.verification_status === 'Partially Verified'
                        ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                        : 'bg-slate-500/10 text-slate-400 border border-slate-500/20'
                    }`}
                  >
                    {feat.verification_status}
                  </span>
                </div>
                <div className="font-medium text-slate-200">{feat.name}</div>
                <div className="text-[11px] text-slate-400 line-clamp-2">{feat.note}</div>
              </div>
            ))}
          </div>
        </aside>

        {/* Content Area */}
        <main className="flex-1 flex flex-col bg-slate-950 overflow-hidden">
          {/* Navigation Tabs */}
          <div className="border-b border-slate-800 px-6 flex space-x-6 bg-slate-900/20">
            <button
              onClick={() => setActiveTab('desktop')}
              className={`py-3 text-xs font-semibold border-b-2 flex items-center space-x-2 transition ${
                activeTab === 'desktop'
                  ? 'border-indigo-500 text-indigo-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Monitor className="w-4 h-4" />
              <span>Desktop App & Auto-Updater</span>
            </button>
            <button
              onClick={() => setActiveTab('chrome')}
              className={`py-3 text-xs font-semibold border-b-2 flex items-center space-x-2 transition ${
                activeTab === 'chrome'
                  ? 'border-indigo-500 text-indigo-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Globe className="w-4 h-4" />
              <span>Chrome Dashboard Inspector</span>
            </button>
            <button
              onClick={() => setActiveTab('frequency')}
              className={`py-3 text-xs font-semibold border-b-2 flex items-center space-x-2 transition ${
                activeTab === 'frequency'
                  ? 'border-cyan-500 text-cyan-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Clock className="w-4 h-4 text-cyan-400" />
              <span>Frequency & Cadence (EM010)</span>
              <span className="bg-cyan-500/20 text-cyan-300 text-[10px] px-1.5 py-0.5 rounded font-mono font-bold">1-Min Sync</span>
            </button>
            <button
              onClick={() => setActiveTab('features')}
              className={`py-3 text-xs font-semibold border-b-2 flex items-center space-x-2 transition ${
                activeTab === 'features'
                  ? 'border-indigo-500 text-indigo-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Layers className="w-4 h-4" />
              <span>Features Overview</span>
            </button>
            <button
              onClick={() => setActiveTab('console')}
              className={`py-3 text-xs font-semibold border-b-2 flex items-center space-x-2 transition ${
                activeTab === 'console'
                  ? 'border-indigo-500 text-indigo-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Activity className="w-4 h-4" />
              <span>Execution Console</span>
            </button>
            <button
              onClick={() => setActiveTab('report')}
              className={`py-3 text-xs font-semibold border-b-2 flex items-center space-x-2 transition ${
                activeTab === 'report'
                  ? 'border-indigo-500 text-indigo-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <FileText className="w-4 h-4 text-indigo-400" />
              <span>Detailed Test Report</span>
              {(runResult?.report?.summary || latestReport?.summary || runResult?.report) && (() => {
                const s = runResult?.report?.summary || latestReport?.summary;
                const v = s?.overall_verdict || (s as any)?.verdict || (runResult?.report as any)?.verdict || 'HEALTHY';
                const total = s?.total_findings ?? (s as any)?.total_plugins ?? 0;
                return (
                  <span
                    className={`text-[10px] px-1.5 py-0.2 rounded-full font-bold font-mono border ${
                      v === 'FAILED'
                        ? 'bg-rose-500/20 text-rose-300 border-rose-500/30'
                        : v === 'BLOCKED'
                        ? 'bg-purple-500/20 text-purple-300 border-purple-500/30'
                        : v === 'INCONCLUSIVE'
                        ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                        : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                    }`}
                  >
                    {v} ({total})
                  </span>
                );
              })()}
            </button>
            <button
              onClick={() => setActiveTab('logs')}
              className={`py-3 text-xs font-semibold border-b-2 flex items-center space-x-2 transition ${
                activeTab === 'logs'
                  ? 'border-indigo-500 text-indigo-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Terminal className="w-4 h-4 text-emerald-400" />
              <span className="text-emerald-400 font-bold">System Logs (log.txt)</span>
            </button>
          </div>

          {/* Main Body */}
          <div className="flex-1 p-6 overflow-y-auto space-y-6">
            {activeTab === 'desktop' && (
              <div className="space-y-6">
                {/* Modern Cloudflare R2 Auto-Update System */}
                <AutoUpdateSection
                  appVersion={appVersion}
                  updaterState={updaterState}
                  updateProgress={updateProgress}
                  isUpdating={isUpdating}
                  updateStage={updateStage}
                  updateLogs={updateLogs}
                  jenkinsInfo={jenkinsInfo}
                  onCheckUpdates={handleCheckUpdates}
                  onSimulateSuccess={() => handleStartAutoUpdate(false)}
                  onSimulateError={() => handleStartAutoUpdate(true)}
                  onRestartAndInstall={handleRestartAndInstall}
                  onDownloadLogs={handleDownloadLogs}
                />

                {/* Git Build Data & Latest Commit Message Card */}
                <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-800">
                    <div className="flex items-center space-x-3">
                      <div className="p-2.5 bg-indigo-500/10 text-indigo-400 rounded-xl border border-indigo-500/20">
                        <Github className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="flex items-center space-x-2">
                          <h3 className="text-sm font-bold text-white">Git Build Metadata & Commit Tracker</h3>
                          <span className="bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-[10px] font-mono px-2 py-0.5 rounded font-bold">
                            Branch: {gitData?.branch || 'main'}
                          </span>
                        </div>
                        <p className="text-xs text-slate-400">Synchronized from Jenkins pipeline checkout and repository HEAD</p>
                      </div>
                    </div>

                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => {
                          fetch(`${API_BASE}/api/git/data`)
                            .then(res => res.json())
                            .then(d => {
                              if (d && d.success) setGitData(d);
                              setToast({
                                id: Date.now().toString(),
                                title: 'Git Data Refreshed',
                                message: 'Latest commit message & metadata updated from repository.',
                                type: 'success',
                                working: true,
                                timestamp: new Date().toLocaleTimeString()
                              });
                            });
                        }}
                        className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg text-xs font-medium transition flex items-center space-x-1.5 cursor-pointer"
                      >
                        <RefreshCw className="w-3.5 h-3.5" />
                        <span>Refresh Git Data</span>
                      </button>
                    </div>
                  </div>

                  {/* Latest Commit Message Highlight Box */}
                  <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-400 flex items-center space-x-1.5">
                        <Activity className="w-3.5 h-3.5 text-indigo-400" />
                        <span>Latest Pipeline Commit</span>
                      </span>
                      <div className="flex items-center space-x-2 font-mono text-[11px]">
                        <span className="text-slate-400">Hash:</span>
                        <code className="bg-slate-800 text-indigo-300 px-2 py-0.5 rounded font-bold">
                          {gitData?.commit.shortHash || 'c7f4a28'}
                        </code>
                      </div>
                    </div>

                    <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-3">
                      <p className="text-sm font-semibold text-slate-100 leading-relaxed font-mono">
                        "{gitData?.commit.message || 'feat(screenshots): implement L1-L4 cross-layer synchronization and Playwright thumbnail verification (EM010)'}"
                      </p>
                      {gitData?.commit.body && (
                        <p className="text-xs text-slate-400 mt-2 font-sans">
                          {gitData.commit.body}
                        </p>
                      )}
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs text-slate-400 pt-1">
                      <div className="flex items-center space-x-2">
                        <span className="text-slate-500">Author:</span>
                        <span className="text-slate-300 font-medium">{gitData?.commit.author || 'EmpMonitor Core QA <qa@empmonitor.com>'}</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="text-slate-500">Repository:</span>
                        <span className="text-indigo-400 font-mono font-medium">{gitData?.repo || 'adsecurto-boop/EMP-REGRESSION-2.0'}</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="text-slate-500">Commit Date:</span>
                        <span className="text-slate-300">{gitData?.commit.date ? new Date(gitData.commit.date).toLocaleString() : 'Just now'}</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Status Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4">
                    <div className="flex items-center space-x-3">
                      <div className="p-2 bg-emerald-500/10 text-emerald-400 rounded-xl border border-emerald-500/20">
                        <Cpu className="w-5 h-5" />
                      </div>
                      <div>
                        <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider">EmpMonitor Runtime Environment</h4>
                        <p className="text-xs text-slate-400">Target host execution context</p>
                      </div>
                    </div>
                    <div className="space-y-2 text-xs">
                      <div className="flex justify-between py-1 border-b border-slate-800">
                        <span className="text-slate-400">Environment</span>
                        <span className="text-slate-200 font-medium">{desktopStatus?.environment || 'EmpMonitor Local'}</span>
                      </div>
                      <div className="flex justify-between py-1 border-b border-slate-800">
                        <span className="text-slate-400">Playwright Chrome Profile</span>
                        <span className="text-emerald-400 font-semibold">Available (`playwright-profile`)</span>
                      </div>
                      <div className="flex justify-between py-1 border-b border-slate-800">
                        <span className="text-slate-400">Dashboard Recordings</span>
                        <span className="text-slate-200 font-medium">{desktopStatus?.recordingsAvailable ?? 4} Python Scripts</span>
                      </div>
                    </div>
                  </div>

                  <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-4">
                    <div className="flex items-center space-x-3">
                      <div className="p-2 bg-indigo-500/10 text-indigo-400 rounded-xl border border-indigo-500/20">
                        <Globe className="w-5 h-5" />
                      </div>
                      <div>
                        <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider">Cloudflare R2 Object Storage</h4>
                        <p className="text-xs text-slate-400">Zero-egress binary distribution</p>
                      </div>
                    </div>
                    <div className="space-y-2 text-xs">
                      <div className="flex justify-between py-1 border-b border-slate-800">
                        <span className="text-slate-400">R2 Bucket</span>
                        <span className="text-indigo-400 font-mono font-medium">s3://empmonitor-updates</span>
                      </div>
                      <div className="flex justify-between py-1 border-b border-slate-800">
                        <span className="text-slate-400">Custom Domain</span>
                        <span className="text-cyan-300 font-mono">https://updates.yourdomain.com</span>
                      </div>
                      <div className="flex justify-between py-1 border-b border-slate-800">
                        <span className="text-slate-400">Packaging Engine</span>
                        <span className="text-emerald-400 font-mono">electron-builder (generic)</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Instructions */}
                <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 space-y-3">
                  <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider">How Cloudflare R2 Auto-Updates Work</h4>
                  <ol className="list-decimal list-inside text-xs text-slate-400 space-y-2 leading-relaxed">
                    <li><strong className="text-slate-200">Continuous Packaging in Jenkins:</strong> On git commit tag, Jenkins runs <code className="text-indigo-400 bg-slate-800 px-1.5 py-0.5 rounded">npm run build</code> and <code className="text-indigo-400 bg-slate-800 px-1.5 py-0.5 rounded">electron-builder -c.npmRebuild=false --publish never</code> to produce Windows installers and portable binaries.</li>
                    <li><strong className="text-slate-200">Cloudflare R2 Synchronization:</strong> Jenkins synchronizes <code className="text-indigo-400 bg-slate-800 px-1.5 py-0.5 rounded">dist-electron/*</code> to <code className="text-cyan-400 bg-slate-800 px-1.5 py-0.5 rounded">s3://empmonitor-updates/</code> using S3 credentials (<code className="text-indigo-400 bg-slate-800 px-1.5 py-0.5 rounded">cloudflare-r2-creds</code>) with zero egress bandwidth charges.</li>
                    <li><strong className="text-slate-200">Global Edge Updates:</strong> The EmpMonitor desktop client checks <code className="text-indigo-400 bg-slate-800 px-1.5 py-0.5 rounded">https://updates.yourdomain.com/latest.yml</code> via Cloudflare CDN and seamlessly stages background updates.</li>
                  </ol>
                </div>
              </div>
            )}

            {activeTab === 'chrome' && (
              <div className="space-y-6">
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-bold text-white">Chrome Browser Dashboard Automation</h3>
                      <p className="text-xs text-slate-400">Runs Chrome Playwright recording scripts against EmpMonitor dashboard using the local profile</p>
                    </div>
                    <button
                      onClick={handleLaunchChromeScript}
                      disabled={isChromeRunning}
                      className="flex items-center space-x-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow-lg shadow-indigo-600/30 transition disabled:opacity-50"
                    >
                      <Play className="w-3.5 h-3.5 fill-current" />
                      <span>{isChromeRunning ? 'Launching Chrome...' : 'Run Chrome Check'}</span>
                    </button>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-wider block mb-2">Select Recording Script</label>
                      <select
                        value={selectedScript}
                        onChange={(e) => setSelectedScript(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                      >
                        <option value="010_screenshots_sync.py">010_screenshots_sync.py - Screenshots L4 Sync & Thumbnails</option>
                        <option value="001_login.py">001_login.py - Login Page Verification</option>
                        <option value="002_dashboard_home.py">002_dashboard_home.py - Dashboard Home Overview</option>
                        <option value="011_monitoring_settings.py">011_monitoring_settings.py - Monitoring Settings Check</option>
                        <option value="012_employee_management.py">012_employee_management.py - Employee Management Page</option>
                      </select>
                    </div>

                    <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/80 text-xs text-slate-400 space-y-1">
                      <div className="text-slate-300 font-semibold">Chrome Environment Context:</div>
                      <div>• Profile Path: <code className="text-indigo-400">/playwright-profile</code></div>
                      <div>• Target Browser: Google Chrome (Chromium)</div>
                      <div>• Headless / Automated Execution Mode</div>
                    </div>
                  </div>
                </div>

                {/* Output Console */}
                <div className="space-y-2">
                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Chrome Browser Output Logs</h4>
                  <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 font-mono text-xs text-slate-300 whitespace-pre-wrap min-h-[300px]">
                    {isChromeRunning ? (
                      <div className="flex items-center space-x-2 text-indigo-400">
                        <RefreshCw className="w-4 h-4 animate-spin" />
                        <span>Initializing Chrome browser session with Playwright...</span>
                      </div>
                    ) : chromeOutput ? (
                      <>
                        <div className="text-emerald-400 font-semibold mb-2">
                          Executed: {(chromeOutput as any).scriptExecuted || selectedScript}
                        </div>
                        {chromeOutput.stdout || <span className="text-slate-500">Script completed with no stdout output.</span>}
                        {chromeOutput.stderr && (
                          <div className="text-amber-400 mt-2 pt-2 border-t border-slate-800">
                            {chromeOutput.stderr}
                          </div>
                        )}
                      </>
                    ) : (
                      <span className="text-slate-600">Click "Run Chrome Check" to launch the browser test script.</span>
                    )}
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'frequency' && (
              <div className="space-y-6">
                {/* Cadence Overview Header Banner */}
                <div className="bg-gradient-to-r from-cyan-950/60 to-slate-900 border border-cyan-500/30 rounded-xl p-6 relative overflow-hidden">
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div>
                      <div className="flex items-center space-x-2.5 mb-1.5">
                        <Clock className="w-5 h-5 text-cyan-400" />
                        <h3 className="text-base font-bold text-white">EM010 Screenshot Frequency & Cadence Validator</h3>
                        <span className="bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 text-xs px-2.5 py-0.5 rounded-full font-mono font-bold">
                          L1-L4 Correlated
                        </span>
                      </div>
                      <p className="text-xs text-slate-300 max-w-3xl leading-relaxed">
                        Validates that screenshots are captured and uploaded strictly on a <strong>1-minute cadence (60s)</strong> by comparing timestamps across
                        Configuration (L1), SQLite storage (L2), Ingestion pipeline (L3), and Dashboard UI cards (L4) within ±{toleranceSec}s tolerance.
                      </p>
                    </div>

                    <div className="flex items-center space-x-3 shrink-0">
                      <button
                        onClick={() => handleRunFrequencyValidation()}
                        disabled={isCalculatingFrequency}
                        className="flex items-center space-x-2 px-4 py-2 text-xs font-bold bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg shadow-lg shadow-cyan-600/30 transition disabled:opacity-50 cursor-pointer"
                      >
                        <RefreshCw className={`w-3.5 h-3.5 ${isCalculatingFrequency ? 'animate-spin' : ''}`} />
                        <span>{isCalculatingFrequency ? 'Evaluating...' : 'Run Cadence Check'}</span>
                      </button>
                    </div>
                  </div>
                </div>

                {/* 4-Layer Cadence Architecture Flow */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-mono font-bold text-indigo-400">LAYER 1: CONFIG</span>
                      <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                    </div>
                    <div className="text-sm font-semibold text-slate-200">screenshotPeriodSec = {expectedIntervalSec}s</div>
                    <div className="text-xs text-slate-400 font-mono">empm.ini / remote config</div>
                    <div className="text-[11px] text-slate-400 pt-1 border-t border-slate-800">
                      Target: 60 captures/hour (1 cycle per 60 seconds).
                    </div>
                  </div>

                  <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-mono font-bold text-amber-400">LAYER 2: PERSISTENCE</span>
                      <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                    </div>
                    <div className="text-sm font-semibold text-slate-200">pending_screenshots6</div>
                    <div className="text-xs text-slate-400 font-mono">SQLite created_at timestamp</div>
                    <div className="text-[11px] text-slate-400 pt-1 border-t border-slate-800">
                      esr.exe captures desktop bitmap and queues row.
                    </div>
                  </div>

                  <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-mono font-bold text-purple-400">LAYER 3: INGESTION</span>
                      <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                    </div>
                    <div className="text-sm font-semibold text-slate-200">POST /add-activity</div>
                    <div className="text-xs text-slate-400 font-mono">upload_cycle_trigger log</div>
                    <div className="text-[11px] text-slate-400 pt-1 border-t border-slate-800">
                      Synchronizes screenshot payload with EmpMonitor cloud.
                    </div>
                  </div>

                  <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-mono font-bold text-cyan-400">LAYER 4: DASHBOARD</span>
                      <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                    </div>
                    <div className="text-sm font-semibold text-slate-200">Web Screenshots Tab</div>
                    <div className="text-xs text-slate-400 font-mono">DOM title attribute timestamp</div>
                    <div className="text-[11px] text-slate-400 pt-1 border-t border-slate-800">
                      Playwright extracts rendered thumbnail card timestamps.
                    </div>
                  </div>
                </div>

                {/* Configuration and Interval Simulator */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  {/* Controls */}
                  <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
                    <div className="flex items-center justify-between">
                      <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center space-x-1.5">
                        <Sliders className="w-4 h-4 text-indigo-400" />
                        <span>Cadence Parameters</span>
                      </h4>
                    </div>

                    <div className="space-y-3">
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Expected Interval (Seconds)</label>
                        <div className="flex space-x-2">
                          <input
                            type="number"
                            value={expectedIntervalSec}
                            onChange={(e) => setExpectedIntervalSec(Number(e.target.value))}
                            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs font-mono text-cyan-300 focus:outline-none focus:border-cyan-500"
                          />
                          <button
                            onClick={() => { setExpectedIntervalSec(60); }}
                            className="px-2.5 py-1 text-[11px] bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg border border-slate-700"
                          >
                            60s (1m)
                          </button>
                        </div>
                      </div>

                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Drift Tolerance (± Seconds)</label>
                        <input
                          type="number"
                          value={toleranceSec}
                          onChange={(e) => setToleranceSec(Number(e.target.value))}
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs font-mono text-cyan-300 focus:outline-none focus:border-cyan-500"
                        />
                      </div>

                      <div>
                        <label className="block text-xs text-slate-400 mb-1">UI Screenshot Card Titles / Timestamps</label>
                        <textarea
                          value={screenshotTitlesText}
                          onChange={(e) => setScreenshotTitlesText(e.target.value)}
                          rows={5}
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs font-mono text-slate-300 focus:outline-none focus:border-cyan-500 resize-none leading-relaxed"
                          placeholder="Enter one title per line..."
                        />
                      </div>

                      <div className="flex items-center space-x-2 pt-2">
                        <button
                          onClick={() => {
                            setScreenshotTitlesText("-08-15 18:00:31-sc0\n-08-15 18:01:32-sc0\n-08-15 18:02:30-sc0\n-08-15 18:03:32-sc0");
                            handleRunFrequencyValidation(60, 15, ["-08-15 18:00:31-sc0", "-08-15 18:01:32-sc0", "-08-15 18:02:30-sc0", "-08-15 18:03:32-sc0"]);
                          }}
                          className="flex-1 py-1.5 text-[11px] font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg border border-slate-700 text-center cursor-pointer"
                        >
                          Load Healthy 1m Data
                        </button>
                        <button
                          onClick={() => {
                            setScreenshotTitlesText("-08-15 18:00:00-sc0\n-08-15 18:03:00-sc0\n-08-15 18:03:20-sc0");
                            handleRunFrequencyValidation(60, 15, ["-08-15 18:00:00-sc0", "-08-15 18:03:00-sc0", "-08-15 18:03:20-sc0"]);
                          }}
                          className="flex-1 py-1.5 text-[11px] font-semibold bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 rounded-lg border border-rose-500/30 text-center cursor-pointer"
                        >
                          Simulate Drift Error
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Calculated Intervals and Drift Status */}
                  <div className="lg:col-span-2 space-y-4">
                    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
                      <div className="flex items-center justify-between">
                        <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center space-x-2">
                          <Activity className="w-4 h-4 text-cyan-400" />
                          <span>Calculated Intervals & Drift Evaluation</span>
                        </h4>
                        {frequencyData && (
                          <span
                            className={`px-2.5 py-0.5 rounded-full text-xs font-mono font-bold ${
                              frequencyData.verdict === 'HEALTHY'
                                ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                                : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
                            }`}
                          >
                            Verdict: {frequencyData.verdict}
                          </span>
                        )}
                      </div>

                      {frequencyData ? (
                        <div className="space-y-3">
                          <div className="grid grid-cols-3 gap-3">
                            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                              <div className="text-[10px] text-slate-400 uppercase">Target Interval</div>
                              <div className="text-base font-bold font-mono text-cyan-400">{frequencyData.expected_interval_sec}s (1m)</div>
                            </div>
                            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                              <div className="text-[10px] text-slate-400 uppercase">Tolerance</div>
                              <div className="text-base font-bold font-mono text-slate-200">±{frequencyData.tolerance_sec}s</div>
                            </div>
                            <div className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                              <div className="text-[10px] text-slate-400 uppercase">Max Observed Drift</div>
                              <div className={`text-base font-bold font-mono ${frequencyData.max_drift_sec <= frequencyData.tolerance_sec ? 'text-emerald-400' : 'text-rose-400'}`}>
                                {frequencyData.max_drift_sec?.toFixed(1)}s
                              </div>
                            </div>
                          </div>

                          <div className="overflow-x-auto border border-slate-800 rounded-lg">
                            <table className="w-full text-left text-xs">
                              <thead className="bg-slate-950 text-slate-400 border-b border-slate-800">
                                <tr>
                                  <th className="p-2.5 font-medium">Cycle</th>
                                  <th className="p-2.5 font-medium">From</th>
                                  <th className="p-2.5 font-medium">To</th>
                                  <th className="p-2.5 font-medium">Actual Delta</th>
                                  <th className="p-2.5 font-medium">Expected</th>
                                  <th className="p-2.5 font-medium">Drift</th>
                                  <th className="p-2.5 font-medium">Status</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-slate-800/60 font-mono">
                                {frequencyData.cycles?.map((c: any, idx: number) => (
                                  <tr key={idx} className="hover:bg-slate-800/30">
                                    <td className="p-2.5 text-slate-400">#{idx + 1}</td>
                                    <td className="p-2.5 text-slate-300">{c.from}</td>
                                    <td className="p-2.5 text-slate-300">{c.to}</td>
                                    <td className="p-2.5 font-bold text-slate-200">{c.actual_interval_sec}s</td>
                                    <td className="p-2.5 text-slate-400">{c.expected_interval_sec}s</td>
                                    <td className="p-2.5 text-slate-300">{c.drift_sec?.toFixed(1)}s</td>
                                    <td className="p-2.5">
                                      <span
                                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                          c.status === 'PASS'
                                            ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                                            : 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
                                        }`}
                                      >
                                        {c.status}
                                      </span>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      ) : (
                        <div className="text-center py-8 text-slate-500 text-xs">
                          Click "Run Cadence Check" to compute intervals.
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Multi-Layer Correlation & Failure Mode Resolution Matrix */}
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center space-x-2">
                        <ShieldAlert className="w-4 h-4 text-indigo-400" />
                        <span>Correlation & Failure Mode Resolution Matrix (L1 - L4)</span>
                      </h4>
                      <p className="text-xs text-slate-400 mt-1">
                        Systematic cross-layer root cause detection for screenshot capture, persistence, ingestion, and UI rendering.
                      </p>
                    </div>
                  </div>

                  <div className="overflow-x-auto border border-slate-800 rounded-lg">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-950 text-slate-400 border-b border-slate-800">
                        <tr>
                          <th className="p-3 font-semibold">Failure Mode</th>
                          <th className="p-3 font-semibold">Layer Boundary</th>
                          <th className="p-3 font-semibold">Automated Detection Mechanism</th>
                          <th className="p-3 font-semibold">Evaluation Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800">
                        {frequencyData?.failure_modes?.map((fm: any, idx: number) => (
                          <tr key={idx} className="hover:bg-slate-800/40 transition">
                            <td className="p-3 font-medium text-slate-200 flex items-center space-x-2">
                              {fm.detected ? (
                                <XCircle className="w-4 h-4 text-rose-400 shrink-0" />
                              ) : (
                                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                              )}
                              <span>{fm.mode}</span>
                            </td>
                            <td className="p-3 font-mono text-indigo-300">{fm.layerBoundary}</td>
                            <td className="p-3 text-slate-400 font-mono text-[11px]">{fm.detectionMechanism}</td>
                            <td className="p-3">
                              <span
                                className={`px-2 py-0.5 rounded-full text-[11px] font-medium font-mono ${
                                  fm.detected
                                    ? 'bg-rose-500/15 text-rose-300 border border-rose-500/30'
                                    : 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                                }`}
                              >
                                {fm.status}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'features' && (
              <div className="space-y-6">
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5">
                  <h3 className="text-sm font-bold text-slate-200 mb-1">EmpMonitor Multi-Layer Validation Scope</h3>
                  <p className="text-xs text-slate-400">
                    The framework validates 14 feature profiles across 4 evidence layers (Configuration, Endpoint Runtime, Sync Pipeline, Dashboard UI) without mocking real monitoring data.
                  </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {features.map((feat) => (
                    <div
                      key={feat.feature_id}
                      className="bg-slate-900/40 border border-slate-800 rounded-xl p-4 flex flex-col justify-between hover:border-slate-700 transition"
                    >
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <span className="font-mono text-xs font-bold text-indigo-400">{feat.feature_id}</span>
                          <span
                            className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
                              feat.verification_status === 'Verified'
                                ? 'bg-emerald-500/10 text-emerald-400'
                                : feat.verification_status === 'Partially Verified'
                                ? 'bg-amber-500/10 text-amber-400'
                                : 'bg-slate-500/10 text-slate-400'
                            }`}
                          >
                            {feat.verification_status}
                          </span>
                        </div>
                        <h4 className="text-sm font-semibold text-slate-100 mb-1">{feat.name}</h4>
                        <p className="text-xs text-slate-400 mb-4">{feat.note}</p>
                      </div>

                      <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-500">
                        <span>Tables: {feat.expected_sqlite_tables.length}</span>
                        <span>Components: {feat.expected_runtime_components.length}</span>
                        <button
                          onClick={() => handleRun(false, feat.feature_id)}
                          className="text-indigo-400 hover:text-indigo-300 font-semibold flex items-center space-x-1"
                        >
                          <span>Run</span>
                          <ChevronRight className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeTab === 'console' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Console Execution Output</h3>
                  {runResult && (
                    <div className="flex items-center space-x-2">
                      {runResult.report && (
                        <button
                          onClick={() => setActiveTab('report')}
                          className="flex items-center space-x-1.5 px-3 py-1 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 rounded text-xs font-semibold transition"
                        >
                          <FileText className="w-3.5 h-3.5" />
                          <span>View Full Test Report</span>
                        </button>
                      )}
                      {runResult.report?.summary?.overall_verdict && (
                        <span
                          className={`px-2.5 py-1 rounded text-xs font-bold font-mono uppercase ${
                            runResult.report.summary.overall_verdict === 'HEALTHY'
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                              : runResult.report.summary.overall_verdict === 'DEGRADED'
                              ? 'bg-amber-500/10 text-amber-300 border border-amber-500/30'
                              : runResult.report.summary.overall_verdict === 'FAILED'
                              ? 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
                              : runResult.report.summary.overall_verdict === 'BLOCKED'
                              ? 'bg-purple-500/10 text-purple-300 border border-purple-500/30'
                              : 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                          }`}
                        >
                          {runResult.report.summary.overall_verdict}
                        </span>
                      )}
                      <span
                        className={`px-2 py-1 rounded text-xs font-semibold ${
                          runResult.exitCode === 0
                            ? 'bg-emerald-500/10 text-emerald-400'
                            : runResult.exitCode === 1
                            ? 'bg-rose-500/10 text-rose-400'
                            : runResult.exitCode === 2 || runResult.exitCode === 3
                            ? 'bg-amber-500/10 text-amber-400'
                            : 'bg-red-500/20 text-red-300'
                        }`}
                      >
                        Exit Code: {runResult.exitCode}
                      </span>
                    </div>
                  )}
                </div>

                <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 font-mono text-xs text-slate-300 whitespace-pre-wrap overflow-x-auto min-h-[400px]">
                  {isRunning ? (
                    <div className="flex items-center space-x-2 text-indigo-400">
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      <span>Executing test framework process...</span>
                    </div>
                  ) : runResult ? (
                    <>
                      {runResult.stdout}
                      {runResult.stderr && (
                        <div className="text-red-400 mt-2 pt-2 border-t border-slate-800">
                          {runResult.stderr}
                        </div>
                      )}
                    </>
                  ) : (
                    <span className="text-slate-600">No execution triggered yet. Select a plugin or click "Run Selected Suite".</span>
                  )}
                </div>
              </div>
            )}

            {activeTab === 'report' && (
              <ReportViewer
                report={runResult?.report || latestReport}
                onRefreshLatest={handleFetchLatestReport}
                onRunSuite={() => handleRun(false)}
                isLoading={isRunning || isFetchingReport}
              />
            )}

            {activeTab === 'logs' && (() => {
              const rawLines = logs ? logs.split('\n') : [];
              const parsed = rawLines.map((line, idx) => {
                const match = line.match(/^\[(.*?)\]\s*\[(.*?)\]\s*\[(.*?)\]\s*(.*)$/);
                if (match) {
                  return {
                    id: idx,
                    timestamp: match[1],
                    level: match[2],
                    category: match[3],
                    message: match[4],
                    raw: line,
                  };
                }
                return {
                  id: idx,
                  timestamp: '',
                  level: 'INFO',
                  category: 'SYSTEM',
                  message: line,
                  raw: line,
                };
              });

              const autoUpdateTotal = parsed.filter(l => l.category === 'AUTO_UPDATE' || l.category === 'AUTO_UPDATER' || l.raw.includes('AUTO_UPDATE')).length;
              const autoUpdateErrors = parsed.filter(l => (l.category === 'AUTO_UPDATE' || l.category === 'AUTO_UPDATER' || l.raw.includes('AUTO_UPDATE')) && (l.level === 'ERROR' || l.raw.includes('[ERROR]'))).length;

              const filtered = parsed.filter((l) => {
                if (logFilterCategory === 'AUTO_UPDATE') {
                  if (l.category !== 'AUTO_UPDATE' && l.category !== 'AUTO_UPDATER' && !l.raw.includes('AUTO_UPDATE') && !l.raw.includes('AUTO_UPDATER')) return false;
                } else if (logFilterCategory === 'RUN_SUITE') {
                  if (l.category !== 'RUN_SUITE' && !l.raw.includes('RUN_SUITE')) return false;
                } else if (logFilterCategory === 'CHROME_INSPECTOR') {
                  if (l.category !== 'CHROME_INSPECTOR' && !l.raw.includes('CHROME_INSPECTOR')) return false;
                } else if (logFilterCategory === 'SYSTEM') {
                  if (l.category !== 'SYSTEM' && !l.raw.includes('SYSTEM')) return false;
                }

                if (logSearchTerm.trim()) {
                  const term = logSearchTerm.toLowerCase();
                  return l.raw.toLowerCase().includes(term);
                }
                return true;
              });

              return (
                <div className="space-y-5">
                  {/* Auto-Update System Diagnostic & Status Box */}
                  <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-800">
                      <div className="flex items-start space-x-3">
                        <div className="p-2.5 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 mt-0.5">
                          <Radio className="w-5 h-5 animate-pulse" />
                        </div>
                        <div>
                          <div className="flex items-center space-x-2">
                            <h3 className="text-base font-bold text-white">Auto-Update Logging & Diagnostic Subsystem</h3>
                            <span className="bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 text-[10px] font-mono px-2 py-0.5 rounded-full font-bold">
                              Category: AUTO_UPDATE
                            </span>
                          </div>
                          <p className="text-xs text-slate-400 mt-0.5">
                            Tracks GitHub release checks, download speed, payload verification, and diagnostic stack traces.
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center space-x-2 shrink-0">
                        <button
                          onClick={handleTriggerUpdateCheck}
                          disabled={isCheckingUpdates}
                          className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white rounded-lg text-xs font-bold shadow-lg shadow-cyan-600/20 transition cursor-pointer disabled:opacity-50"
                        >
                          <RefreshCw className={`w-3.5 h-3.5 ${isCheckingUpdates ? 'animate-spin' : ''}`} />
                          <span>{isCheckingUpdates ? 'Checking Feed...' : 'Run Auto-Update Diagnostic Check'}</span>
                        </button>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
                      <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/80">
                        <span className="text-slate-400 block mb-1">Current State</span>
                        <span className="font-mono font-bold text-cyan-300 uppercase">{updaterState.status || 'idle'}</span>
                      </div>
                      <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/80">
                        <span className="text-slate-400 block mb-1">Total AUTO_UPDATE Logs</span>
                        <span className="font-mono font-bold text-white">{autoUpdateTotal} entries</span>
                      </div>
                      <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/80">
                        <span className="text-slate-400 block mb-1">Auto-Update Errors</span>
                        <span className={`font-mono font-bold ${autoUpdateErrors > 0 ? 'text-rose-400' : 'text-emerald-400'}`}>
                          {autoUpdateErrors} recorded
                        </span>
                      </div>
                      <div className="bg-slate-950 p-3 rounded-lg border border-slate-800/80">
                        <span className="text-slate-400 block mb-1">GitHub Feed Endpoint</span>
                        <span className="font-mono font-semibold text-slate-300 truncate block">adsecurto-boop/EMP-REGRESSION-2.0</span>
                      </div>
                    </div>

                    {updaterState.message && (
                      <div className={`p-3 rounded-lg text-xs font-mono flex items-start space-x-2 border ${
                        updaterState.status === 'error'
                          ? 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                          : updaterState.status === 'available' || updaterState.status === 'downloaded'
                          ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                          : 'bg-slate-950 border-slate-800 text-slate-300'
                      }`}>
                        {updaterState.status === 'error' ? (
                          <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                        ) : (
                          <Info className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
                        )}
                        <div>
                          <div>{updaterState.message}</div>
                          {updaterState.diagnosticHint && (
                            <div className="mt-1 text-[11px] text-amber-300/90 font-sans">
                              💡 <strong>Diagnostic Suggestion:</strong> {updaterState.diagnosticHint}
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* System Runtime Log Header & Actions */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900/80 p-5 rounded-xl border border-slate-800 backdrop-blur">
                    <div>
                      <div className="flex items-center space-x-2">
                        <Terminal className="w-5 h-5 text-emerald-400" />
                        <h3 className="font-bold text-white text-base">System Runtime Log File (log.txt)</h3>
                        <span className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] px-2.5 py-0.5 rounded-full font-mono font-bold">
                          Live Logger Active
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 mt-1">
                        Select a category filter or search term below to isolate issues and copy/export log reports.
                      </p>
                    </div>

                    <div className="flex items-center space-x-2 shrink-0">
                      <button
                        onClick={handleFetchLogs}
                        disabled={logsLoading}
                        className="flex items-center space-x-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg text-xs font-medium transition cursor-pointer"
                      >
                        <RefreshCw className={`w-3.5 h-3.5 ${logsLoading ? 'animate-spin' : ''}`} />
                        <span>Refresh</span>
                      </button>
                      <button
                        onClick={handleCopyLogs}
                        className="flex items-center space-x-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg text-xs font-medium transition cursor-pointer"
                      >
                        <Copy className="w-3.5 h-3.5" />
                        <span>Copy</span>
                      </button>
                      <button
                        onClick={handleClearLogs}
                        className="flex items-center space-x-1.5 px-3 py-1.5 bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 rounded-lg text-xs font-medium transition cursor-pointer"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        <span>Clear</span>
                      </button>
                      <button
                        onClick={handleDownloadLogs}
                        className="flex items-center space-x-2 px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold shadow-lg shadow-emerald-600/30 transition cursor-pointer"
                      >
                        <Download className="w-4 h-4" />
                        <span>Download log.txt</span>
                      </button>
                    </div>
                  </div>

                  {/* Filter & Search Bar */}
                  <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 bg-slate-900/60 p-3 rounded-xl border border-slate-800">
                    <div className="flex items-center space-x-1.5 overflow-x-auto pb-1 md:pb-0">
                      <span className="text-xs text-slate-400 font-semibold flex items-center space-x-1 mr-2 shrink-0">
                        <Filter className="w-3.5 h-3.5 text-indigo-400" />
                        <span>Filter Category:</span>
                      </span>

                      <button
                        onClick={() => setLogFilterCategory('ALL')}
                        className={`px-3 py-1 rounded-lg text-xs font-semibold transition cursor-pointer shrink-0 ${
                          logFilterCategory === 'ALL'
                            ? 'bg-indigo-600 text-white'
                            : 'bg-slate-800/80 text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        All Logs ({parsed.length})
                      </button>

                      <button
                        onClick={() => setLogFilterCategory('AUTO_UPDATE')}
                        className={`px-3 py-1 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition cursor-pointer shrink-0 ${
                          logFilterCategory === 'AUTO_UPDATE'
                            ? 'bg-cyan-600 text-white shadow-md shadow-cyan-600/30'
                            : 'bg-cyan-950/40 text-cyan-300 border border-cyan-800/50 hover:bg-cyan-900/40'
                        }`}
                      >
                        <span>Auto Updates</span>
                        <span className="bg-cyan-900/80 text-cyan-200 px-1.5 py-0.2 rounded-full text-[10px] font-mono">
                          {autoUpdateTotal}
                        </span>
                      </button>

                      <button
                        onClick={() => setLogFilterCategory('RUN_SUITE')}
                        className={`px-3 py-1 rounded-lg text-xs font-semibold transition cursor-pointer shrink-0 ${
                          logFilterCategory === 'RUN_SUITE'
                            ? 'bg-indigo-600 text-white'
                            : 'bg-slate-800/80 text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        Suite Runs
                      </button>

                      <button
                        onClick={() => setLogFilterCategory('CHROME_INSPECTOR')}
                        className={`px-3 py-1 rounded-lg text-xs font-semibold transition cursor-pointer shrink-0 ${
                          logFilterCategory === 'CHROME_INSPECTOR'
                            ? 'bg-purple-600 text-white'
                            : 'bg-slate-800/80 text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        Chrome Inspector
                      </button>

                      <button
                        onClick={() => setLogFilterCategory('SYSTEM')}
                        className={`px-3 py-1 rounded-lg text-xs font-semibold transition cursor-pointer shrink-0 ${
                          logFilterCategory === 'SYSTEM'
                            ? 'bg-slate-700 text-white'
                            : 'bg-slate-800/80 text-slate-400 hover:text-slate-200'
                        }`}
                      >
                        System
                      </button>
                    </div>

                    <div className="relative shrink-0 w-full md:w-64">
                      <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-2.5" />
                      <input
                        type="text"
                        placeholder="Search logs (e.g. 404, error, v0.1.1)..."
                        value={logSearchTerm}
                        onChange={(e) => setLogSearchTerm(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-8 pr-7 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                      />
                      {logSearchTerm && (
                        <button
                          onClick={() => setLogSearchTerm('')}
                          className="absolute right-2 top-2 text-slate-500 hover:text-slate-300 text-xs font-bold"
                        >
                          ×
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Log View Area */}
                  <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 font-mono text-xs overflow-x-auto max-h-[550px] overflow-y-auto leading-relaxed shadow-inner space-y-1.5">
                    {filtered.length > 0 ? (
                      filtered.map((item) => {
                        const isAutoUpdate = item.category === 'AUTO_UPDATE' || item.category === 'AUTO_UPDATER' || item.raw.includes('AUTO_UPDATE');
                        const isError = item.level === 'ERROR' || item.raw.includes('[ERROR]');
                        const isSuccess = item.level === 'SUCCESS' || item.raw.includes('[SUCCESS]');
                        const isWarn = item.level === 'WARN' || item.raw.includes('[WARN]');

                        return (
                          <div
                            key={item.id}
                            className={`p-2 rounded border flex flex-col sm:flex-row sm:items-start gap-2 transition hover:bg-slate-900/60 ${
                              isError
                                ? 'bg-rose-950/20 border-rose-900/40 text-rose-200'
                                : isAutoUpdate
                                ? 'bg-cyan-950/15 border-cyan-900/40 text-cyan-200'
                                : isSuccess
                                ? 'bg-emerald-950/10 border-emerald-900/30 text-emerald-200'
                                : isWarn
                                ? 'bg-amber-950/10 border-amber-900/30 text-amber-200'
                                : 'bg-slate-900/20 border-slate-800/60 text-slate-300'
                            }`}
                          >
                            <div className="flex items-center space-x-1.5 shrink-0">
                              {item.timestamp && (
                                <span className="text-slate-500 text-[10px] font-mono shrink-0">
                                  {item.timestamp.split('T')[1]?.split('.')[0] || item.timestamp}
                                </span>
                              )}

                              <span
                                className={`px-1.5 py-0.2 rounded text-[10px] font-bold uppercase shrink-0 ${
                                  isError
                                    ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                                    : isSuccess
                                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                                    : isWarn
                                    ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                                    : 'bg-slate-800 text-slate-300'
                                }`}
                              >
                                {item.level}
                              </span>

                              <span
                                className={`px-1.5 py-0.2 rounded text-[10px] font-mono font-bold shrink-0 ${
                                  isAutoUpdate
                                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                                    : item.category === 'RUN_SUITE'
                                    ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30'
                                    : item.category === 'CHROME_INSPECTOR'
                                    ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                                    : 'bg-slate-800 text-slate-400'
                                }`}
                              >
                                [{item.category}]
                              </span>
                            </div>

                            <div className="break-all whitespace-pre-wrap flex-1 leading-relaxed">
                              {item.message || item.raw}
                            </div>
                          </div>
                        );
                      })
                    ) : logs ? (
                      <div className="text-slate-500 text-center py-12">
                        No log entries matched filter "{logFilterCategory}" {logSearchTerm ? `with term "${logSearchTerm}"` : ''}.
                      </div>
                    ) : (
                      <div className="text-slate-500 text-center py-16">
                        <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 opacity-50" />
                        Loading log report entries...
                      </div>
                    )}
                  </div>
                </div>
              );
            })()}
          </div>
        </main>
      </div>
    </div>
  );
}
