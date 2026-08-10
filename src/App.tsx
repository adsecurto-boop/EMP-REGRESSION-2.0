import React, { useState, useEffect } from 'react';
import { Play, CheckCircle2, AlertTriangle, XCircle, ShieldAlert, Layers, RefreshCw, FileText, Server, Activity, ChevronRight } from 'lucide-react';
import { FeatureProfile, RunReport } from './types';

export default function App() {
  const [features, setFeatures] = useState<FeatureProfile[]>([]);
  const [selectedPlugin, setSelectedPlugin] = useState<string>('');
  const [environment, setEnvironment] = useState<string>('local');
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [runResult, setRunResult] = useState<{
    stdout: string;
    stderr: string;
    exitCode: number;
    report: any;
  } | null>(null);
  const [activeTab, setActiveTab] = useState<'features' | 'console' | 'report'>('features');

  useEffect(() => {
    fetch('/api/features')
      .then((res) => res.json())
      .then((data) => setFeatures(data))
      .catch((err) => console.error(err));
  }, []);

  const handleRun = (checkOnly = false, pluginOverride?: string) => {
    setIsRunning(true);
    setRunResult(null);

    fetch('/api/run', {
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

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top Navigation / Header */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-50 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="bg-indigo-600 p-2 rounded-lg text-white font-bold text-xl shadow-lg shadow-indigo-500/20">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-white tracking-wide">EmpMonitor Automation Framework</h1>
            <p className="text-xs text-slate-400">Multi-Layer Evidence & Regression Validation Suite (v0.1.0)</p>
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
              <option value="local">local</option>
            </select>
          </div>

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
            <span>{isRunning ? 'Running...' : 'Run Selected Suite'}</span>
          </button>
        </div>
      </header>

      {/* Main Content Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar / Plugin Selector */}
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

        {/* Workspace Display */}
        <main className="flex-1 flex flex-col bg-slate-950 overflow-hidden">
          {/* Tabs */}
          <div className="border-b border-slate-800 px-6 flex space-x-6 bg-slate-900/20">
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
              <span>Execution Logs & Console</span>
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
          </div>

          {/* Tab Content */}
          <div className="flex-1 p-6 overflow-y-auto">
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
          </div>
        </main>
      </div>
    </div>
  );
}
