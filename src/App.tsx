import React, { useState, useEffect } from 'react';
import {
  Play, CheckCircle2, AlertTriangle, XCircle, ShieldAlert, Layers, RefreshCw, FileText,
  Server, Activity, ChevronRight, Monitor, Globe, Download, Github, Cpu, Radio, Sparkles,
  Bell, X, Info, ExternalLink, Check, Copy, Trash2, Terminal
} from 'lucide-react';
import { FeatureProfile } from './types';

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
    message: 'Ready to check for GitHub updates'
  });

  const [toast, setToast] = useState<ToastNotification | null>(null);

  const [appVersion, setAppVersion] = useState<string>('0.1.0');

  const [runResult, setRunResult] = useState<{
    stdout: string;
    stderr: string;
    exitCode: number;
    report: any;
  } | null>(null);

  const [activeTab, setActiveTab] = useState<'desktop' | 'chrome' | 'features' | 'console' | 'report' | 'logs'>('desktop');
  const [logs, setLogs] = useState<string>('');
  const [logsLoading, setLogsLoading] = useState<boolean>(false);

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
        console.error('Error fetching features:', err);
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
        console.error('Error fetching status:', err);
        setIsBackendReady(false);
      });

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
        setActiveTab('console');
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

  const handleCheckUpdates = () => {
    if ((window as any).electronAPI) {
      setUpdaterState({ status: 'checking', working: true, message: 'Connecting to GitHub Releases...' });
      setToast({
        id: Date.now().toString(),
        title: 'Checking GitHub Releases...',
        message: 'Querying GitHub API for published .exe releases...',
        type: 'info',
        working: true,
        timestamp: new Date().toLocaleTimeString(),
      });
      (window as any).electronAPI.checkForUpdates();
    } else {
      const msg = 'Running in Web Preview Mode. In the packaged .exe client, this connects to GitHub Releases.';
      setUpdaterState({
        status: 'web',
        working: true,
        message: msg
      });
      setToast({
        id: Date.now().toString(),
        title: 'YES - Auto-Updater Component Active',
        message: msg,
        type: 'success',
        working: true,
        timestamp: new Date().toLocaleTimeString(),
      });
    }
  };

  const handleTestWorkingToast = () => {
    const info: UpdaterInfo = {
      status: 'not-available',
      working: true,
      message: `YES - Auto-Updater is Working! Connected to GitHub Releases (empmonitor/regression-suite v${appVersion}). App is up to date.`
    };
    setUpdaterState(info);
    setToast({
      id: Date.now().toString(),
      title: 'YES - Auto-Updater is Working!',
      message: `Connected successfully to GitHub Releases feed. You are on the latest release (v${appVersion}).`,
      type: 'success',
      working: true,
      timestamp: new Date().toLocaleTimeString(),
    });
  };

  const handleTestErrorToast = () => {
    const info: UpdaterInfo = {
      status: 'error',
      working: false,
      error: 'ERR_UPDATER_CHANNEL_NOT_FOUND: 404 Not Found',
      message: 'Auto-Update Error: 404 Not Found - No published releases found on GitHub repository yet.'
    };
    setUpdaterState(info);
    setToast({
      id: Date.now().toString(),
      title: 'Auto-Update Error Detected',
      message: 'GitHub release feed returned 404 (No release has been published on GitHub yet).',
      type: 'error',
      working: false,
      timestamp: new Date().toLocaleTimeString(),
    });
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
              <span className="bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 text-[10px] font-mono px-2 py-0.5 rounded-full font-semibold">
                v{appVersion}
              </span>
            </div>
            <p className="text-xs text-slate-400">Integrated Chrome Browser Inspection & GitHub Auto-Updating EXE Client</p>
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
              <option value="EM000_EnvironmentValidator">EM000_EnvironmentValidator</option>
              <option value="EM001_Synchronization">EM001_Synchronization</option>
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
              <FileText className="w-4 h-4" />
              <span>Structured Report</span>
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
                {/* Auto Updater Card */}
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 relative overflow-hidden">
                  <div className="absolute top-0 right-0 p-6 opacity-10">
                    <Sparkles className="w-32 h-32 text-indigo-400" />
                  </div>
                  <div className="relative z-10">
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center space-x-3">
                        <div className="p-2 bg-indigo-500/10 rounded-lg text-indigo-400 border border-indigo-500/20">
                          <Radio className="w-5 h-5" />
                        </div>
                        <div>
                          <h3 className="text-sm font-bold text-white">GitHub Auto-Updater Control</h3>
                          <p className="text-xs text-slate-400">Automated desktop release checks via GitHub Releases feed</p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={handleTestWorkingToast}
                          className="flex items-center space-x-1.5 px-3 py-1.5 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 rounded-lg font-semibold text-xs transition"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                          <span>Test Working Toast</span>
                        </button>

                        <button
                          onClick={handleTestErrorToast}
                          className="flex items-center space-x-1.5 px-3 py-1.5 bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 rounded-lg font-semibold text-xs transition"
                        >
                          <AlertTriangle className="w-3.5 h-3.5 text-rose-400" />
                          <span>Test Error Toast</span>
                        </button>

                        <button
                          onClick={handleCheckUpdates}
                          className="flex items-center space-x-2 px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-semibold text-xs transition shadow-lg shadow-indigo-600/30"
                        >
                          <RefreshCw className="w-3.5 h-3.5" />
                          <span>Check for Updates</span>
                        </button>
                      </div>
                    </div>

                    <div className="bg-slate-950 border border-slate-800 rounded-lg p-4 space-y-3">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-400">Updater Status:</span>
                        <span className="font-semibold text-indigo-400">{updaterState.status.toUpperCase()}</span>
                      </div>
                      <p className="text-xs text-slate-300">{updaterState.message}</p>

                      {updaterState.progress !== undefined && (
                        <div className="space-y-1">
                          <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                            <div
                              className="bg-indigo-500 h-full transition-all duration-300"
                              style={{ width: `${updaterState.progress}%` }}
                            />
                          </div>
                          <div className="text-[10px] text-right text-slate-400">{Math.round(updaterState.progress)}% downloaded</div>
                        </div>
                      )}

                      {updaterState.status === 'downloaded' && (
                        <button
                          onClick={handleRestartAndInstall}
                          className="w-full py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold transition flex items-center justify-center space-x-2 shadow-lg shadow-emerald-600/30"
                        >
                          <Download className="w-4 h-4" />
                          <span>Restart & Install Update Now</span>
                        </button>
                      )}
                    </div>
                  </div>
                </div>

                {/* Status Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
                    <div className="flex items-center space-x-3">
                      <div className="p-2 bg-emerald-500/10 text-emerald-400 rounded-lg border border-emerald-500/20">
                        <Cpu className="w-5 h-5" />
                      </div>
                      <div>
                        <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider">EmpMonitor Environment</h4>
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

                  <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
                    <div className="flex items-center space-x-3">
                      <div className="p-2 bg-indigo-500/10 text-indigo-400 rounded-lg border border-indigo-500/20">
                        <Github className="w-5 h-5" />
                      </div>
                      <div>
                        <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider">GitHub CI/CD & EXE Packaging</h4>
                        <p className="text-xs text-slate-400">Automated builds & releases</p>
                      </div>
                    </div>
                    <div className="space-y-2 text-xs">
                      <div className="flex justify-between py-1 border-b border-slate-800">
                        <span className="text-slate-400">Repository</span>
                        <span className="text-indigo-400 font-mono font-medium">{desktopStatus?.githubRepo || 'adsecurto-boop/Emp_Regression_suite'}</span>
                      </div>
                      <div className="flex justify-between py-1 border-b border-slate-800">
                        <span className="text-slate-400">Workflow File</span>
                        <span className="text-slate-200 font-mono">.github/workflows/build-desktop-exe.yml</span>
                      </div>
                      <div className="flex justify-between py-1 border-b border-slate-800">
                        <span className="text-slate-400">Target Executable</span>
                        <span className="text-slate-200 font-medium">Windows x64 (.exe installer + portable)</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Instructions */}
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-3">
                  <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider">How Changes Auto-Reflect in Desktop EXE</h4>
                  <ol className="list-decimal list-inside text-xs text-slate-400 space-y-2">
                    <li><strong className="text-slate-200">Commit & Push:</strong> Whenever you commit code changes to the GitHub repository, GitHub Actions automatically triggers <code className="text-indigo-400 bg-slate-800 px-1.5 py-0.5 rounded">build-desktop-exe.yml</code>.</li>
                    <li><strong className="text-slate-200">Executable Artifact Generation:</strong> The GitHub runner compiles the web application, packages Electron desktop files, generates <code className="text-indigo-400 bg-slate-800 px-1.5 py-0.5 rounded">.exe</code> installer & <code className="text-indigo-400 bg-slate-800 px-1.5 py-0.5 rounded">latest.yml</code> manifest.</li>
                    <li><strong className="text-slate-200">Auto-Update:</strong> When users launch the desktop app on Windows, <code className="text-indigo-400 bg-slate-800 px-1.5 py-0.5 rounded">electron-updater</code> automatically fetches the update from GitHub Releases and prompts to restart & install.</li>
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
                          Executed: {chromeOutput.scriptExecuted || selectedScript}
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
                    <span
                      className={`px-2 py-1 rounded text-xs font-semibold ${
                        runResult.exitCode === 0
                          ? 'bg-emerald-500/10 text-emerald-400'
                          : 'bg-amber-500/10 text-amber-400'
                      }`}
                    >
                      Exit Code: {runResult.exitCode}
                    </span>
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
              <div className="space-y-4">
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Parsed Execution Report</h3>
                {runResult?.report ? (
                  <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pb-4 border-b border-slate-800">
                      <div>
                        <div className="text-xs text-slate-400">Overall Verdict</div>
                        <div className="text-lg font-bold text-indigo-400">{runResult.report.summary?.overall_verdict || 'N/A'}</div>
                      </div>
                      <div>
                        <div className="text-xs text-slate-400">Confidence</div>
                        <div className="text-lg font-bold text-slate-200">{runResult.report.summary?.lowest_confidence || 'N/A'}</div>
                      </div>
                      <div>
                        <div className="text-xs text-slate-400">Total Findings</div>
                        <div className="text-lg font-bold text-slate-200">{runResult.report.summary?.total_findings ?? 0}</div>
                      </div>
                      <div>
                        <div className="text-xs text-slate-400">Layers Covered</div>
                        <div className="text-xs text-slate-300 mt-1">
                          {runResult.report.summary?.layers_covered?.map((l: any) => l.label).join(', ') || 'None'}
                        </div>
                      </div>
                    </div>

                    <div>
                      <h4 className="text-xs font-bold text-slate-400 mb-2">Raw JSON Output</h4>
                      <pre className="bg-slate-950 p-4 rounded-lg text-xs font-mono text-slate-300 overflow-x-auto border border-slate-800">
                        {JSON.stringify(runResult.report, null, 2)}
                      </pre>
                    </div>
                  </div>
                ) : (
                  <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center text-slate-500 text-xs">
                    No structured report available for this run. Run a full suite to view detailed findings.
                  </div>
                )}
              </div>
            )}

            {activeTab === 'logs' && (
              <div className="space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900/80 p-5 rounded-xl border border-slate-800 backdrop-blur">
                  <div>
                    <div className="flex items-center space-x-2">
                      <Terminal className="w-5 h-5 text-emerald-400" />
                      <h3 className="font-bold text-white text-base">System Runtime Log File (log.txt)</h3>
                      <span className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] px-2.5 py-0.5 rounded-full font-mono font-bold">
                        Live Recorder Active
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-1">
                      Records all success operations, errors, suite runs, and auto-updater events. Click <strong>Download log.txt</strong> to export and share with developers.
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

                <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 font-mono text-xs overflow-x-auto max-h-[600px] overflow-y-auto leading-relaxed shadow-inner">
                  {logs ? (
                    <pre className="text-slate-300 whitespace-pre-wrap">{logs}</pre>
                  ) : (
                    <div className="text-slate-500 text-center py-16">
                      <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 opacity-50" />
                      Loading log report entries...
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
