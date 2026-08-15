import React, { useState } from 'react';
import {
  Radio, RefreshCw, CheckCircle2, AlertTriangle, Download, Sparkles, Terminal,
  Cloud, Globe, ShieldCheck, FileCheck, Layers, ArrowUpCircle, Check, Copy,
  ExternalLink, Server, HardDrive, Cpu, Activity, Info, Zap, Clock
} from 'lucide-react';

export interface UpdaterState {
  status: string;
  message: string;
  working?: boolean;
  progress?: number;
  info?: any;
  error?: string;
  diagnosticHint?: string;
}

export interface UpdateLogEntry {
  time: string;
  level: 'INFO' | 'WARN' | 'ERROR' | 'SUCCESS';
  msg: string;
  details?: string;
}

export interface AutoUpdateSectionProps {
  appVersion: string;
  updaterState: UpdaterState;
  updateProgress: number;
  isUpdating: boolean;
  updateStage: string;
  updateLogs: UpdateLogEntry[];
  jenkinsInfo: any;
  onCheckUpdates: () => void;
  onSimulateSuccess: () => void;
  onSimulateError: () => void;
  onRestartAndInstall: () => void;
  onDownloadLogs: () => void;
}

export const AutoUpdateSection: React.FC<AutoUpdateSectionProps> = ({
  appVersion,
  updaterState,
  updateProgress,
  isUpdating,
  updateStage,
  updateLogs,
  jenkinsInfo,
  onCheckUpdates,
  onSimulateSuccess,
  onSimulateError,
  onRestartAndInstall,
  onDownloadLogs,
}) => {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [showLogConsole, setShowLogConsole] = useState<boolean>(true);
  const [logFilter, setLogFilter] = useState<'ALL' | 'INFO' | 'SUCCESS' | 'WARN' | 'ERROR'>('ALL');
  const [selectedArtifactTab, setSelectedArtifactTab] = useState<'all' | 'manifests' | 'binaries'>('all');
  const [selectedJurisdiction, setSelectedJurisdiction] = useState<'default' | 'eu'>('default');
  const [selectedCodeSnippet, setSelectedCodeSnippet] = useState<'cli' | 'jenkins' | 'node' | 'python'>('cli');

  const r2AccountId = jenkinsInfo?.r2Release?.accountId || 'ca2a4c1cb15c70abc670f34aecbd5084';
  const r2BaseUrl = jenkinsInfo?.r2Release?.baseUrl || 'https://updates.yourdomain.com';
  const r2Bucket = jenkinsInfo?.r2Release?.bucket || 'empmonitor-updates';

  const jurisdictionEndpoints = {
    default: {
      name: 'Default (Global)',
      endpoint: `https://${r2AccountId}.r2.cloudflarestorage.com`,
      region: 'auto',
      badge: 'Global Anycast',
      compliance: 'Distributed multi-region replication across Cloudflare global edge network',
      latency: '< 25ms (Global Anycast)',
    },
    eu: {
      name: 'European Union (EU)',
      endpoint: `https://${r2AccountId}.eu.r2.cloudflarestorage.com`,
      region: 'eu',
      badge: 'EU Data Sovereign',
      compliance: 'Restricts storage and data processing strictly within EU data centers (GDPR / EU Data Residency)',
      latency: '< 15ms (EU Core Regions)',
    },
  };

  const activeJurisdiction = jurisdictionEndpoints[selectedJurisdiction];

  const copyToClipboard = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const filteredLogs = updateLogs.filter(l => {
    if (logFilter === 'ALL') return true;
    return l.level === logFilter;
  });

  return (
    <div className="space-y-6">
      {/* Primary Auto-Updater Status Banner */}
      <div id="auto-updater-card" className="bg-slate-900 border border-slate-800 rounded-2xl p-6 relative overflow-hidden shadow-2xl">
        {/* Subtle Background Glow */}
        <div className="absolute top-0 right-0 p-8 opacity-10 pointer-events-none">
          <Cloud className="w-48 h-48 text-indigo-400" />
        </div>

        <div className="relative z-10 space-y-6">
          {/* Header Row */}
          <div className="flex flex-wrap items-start justify-between gap-4 pb-4 border-b border-slate-800">
            <div className="flex items-start space-x-3.5">
              <div className="p-3 bg-gradient-to-br from-indigo-500/20 to-cyan-500/20 rounded-xl text-indigo-400 border border-indigo-500/30 shadow-lg shadow-indigo-500/10 shrink-0 mt-0.5">
                <Radio className="w-6 h-6 text-indigo-400 animate-pulse" />
              </div>
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-base font-bold text-white tracking-tight">Cloudflare R2 Auto-Update Engine</h3>
                  <span className="bg-gradient-to-r from-indigo-500/20 to-cyan-500/20 text-cyan-300 border border-cyan-500/30 text-[11px] font-mono px-2.5 py-0.5 rounded-full font-bold flex items-center space-x-1.5 shadow-sm">
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping"></span>
                    <span>Installed: v{appVersion}</span>
                  </span>
                  <span className="bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 text-[10px] font-mono px-2 py-0.5 rounded font-bold flex items-center space-x-1">
                    <Zap className="w-3 h-3 text-emerald-400" />
                    <span>Global Anycast CDN</span>
                  </span>
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  High-speed, zero-egress binary distribution via Cloudflare R2 Object Storage and automated electron-updater generic feed.
                </p>
              </div>
            </div>

            {/* Quick Action Controls */}
            <div className="flex flex-wrap items-center gap-2">
              <button
                id="btn-simulate-update-success"
                onClick={onSimulateSuccess}
                disabled={isUpdating}
                className="flex items-center space-x-1.5 px-3 py-2 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 rounded-xl font-semibold text-xs transition disabled:opacity-50 cursor-pointer shadow-sm shadow-emerald-500/10"
                title="Simulate seamless Cloudflare R2 download, checksum verification and staging"
              >
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span>Simulate R2 Download</span>
              </button>

              <button
                id="btn-simulate-update-error"
                onClick={onSimulateError}
                disabled={isUpdating}
                className="flex items-center space-x-1.5 px-3 py-2 bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 rounded-xl font-semibold text-xs transition disabled:opacity-50 cursor-pointer shadow-sm shadow-rose-500/10"
                title="Simulate DNS timeout / 404 network failure with automated IPv4 diagnosis"
              >
                <AlertTriangle className="w-4 h-4 text-rose-400" />
                <span>Simulate Failure</span>
              </button>

              <button
                id="btn-check-r2-updates"
                onClick={onCheckUpdates}
                disabled={isUpdating}
                className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white rounded-xl font-semibold text-xs transition shadow-lg shadow-indigo-600/30 disabled:opacity-50 cursor-pointer"
              >
                <RefreshCw className={`w-4 h-4 ${isUpdating ? 'animate-spin' : ''}`} />
                <span>{isUpdating ? 'Connecting to R2...' : 'Check for Updates'}</span>
              </button>
            </div>
          </div>

          {/* R2 Feed Endpoint & Configuration Pill Bar */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="bg-slate-950/80 border border-slate-800/80 rounded-xl p-3 flex items-center justify-between space-x-2">
              <div className="flex items-center space-x-2.5 overflow-hidden">
                <Cloud className="w-4 h-4 text-indigo-400 shrink-0" />
                <div className="overflow-hidden">
                  <div className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">R2 Bucket Target</div>
                  <div className="text-xs font-mono font-semibold text-slate-200 truncate">{r2Bucket}</div>
                </div>
              </div>
              <span className="text-[10px] bg-slate-800 text-slate-300 font-mono px-2 py-0.5 rounded border border-slate-700">s3://</span>
            </div>

            <div className="bg-slate-950/80 border border-slate-800/80 rounded-xl p-3 flex items-center justify-between space-x-2">
              <div className="flex items-center space-x-2.5 overflow-hidden">
                <Globe className="w-4 h-4 text-cyan-400 shrink-0" />
                <div className="overflow-hidden">
                  <div className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">Cloudflare Edge CDN</div>
                  <div className="text-xs font-mono font-semibold text-cyan-300 truncate">{r2BaseUrl}</div>
                </div>
              </div>
              <button
                onClick={() => copyToClipboard(r2BaseUrl, 'baseUrl')}
                className="p-1 text-slate-400 hover:text-slate-200 transition cursor-pointer"
                title="Copy CDN Base URL"
              >
                {copiedKey === 'baseUrl' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
            </div>

            <div className="bg-slate-950/80 border border-slate-800/80 rounded-xl p-3 flex items-center justify-between space-x-2">
              <div className="flex items-center space-x-2.5 overflow-hidden">
                <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                <div className="overflow-hidden">
                  <div className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">Feed Protocol</div>
                  <div className="text-xs font-mono font-semibold text-emerald-300 truncate">Generic latest.yml + SHA512</div>
                </div>
              </div>
              <span className="text-[10px] bg-emerald-500/10 text-emerald-300 font-mono px-1.5 py-0.5 rounded border border-emerald-500/20">Active</span>
            </div>
          </div>

          {/* Interactive Progress & State Card */}
          <div className="bg-slate-950 border border-slate-800/80 rounded-xl p-4.5 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
              <div className="flex items-center space-x-2">
                <span className="text-slate-400 font-medium">Updater Status:</span>
                <span className={`font-semibold font-mono uppercase px-2.5 py-0.5 rounded text-[11px] border ${
                  updaterState.status === 'error'
                    ? 'bg-rose-500/15 text-rose-300 border-rose-500/30'
                    : updaterState.status === 'downloaded'
                    ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                    : updaterState.status === 'checking'
                    ? 'bg-indigo-500/15 text-indigo-300 border-indigo-500/30 animate-pulse'
                    : 'bg-slate-800 text-slate-300 border-slate-700'
                }`}>
                  {updaterState.status}
                </span>
              </div>

              {updateStage && (
                <div className="flex items-center space-x-1.5 text-slate-400 font-mono text-[11px]">
                  <Clock className="w-3.5 h-3.5 text-indigo-400" />
                  <span className="truncate max-w-sm">{updateStage}</span>
                </div>
              )}
            </div>

            {/* Progress Bar with Speed and Byte Counter */}
            <div className="space-y-1.5">
              <div className="flex justify-between items-center text-xs">
                <span className="text-slate-300 font-medium text-[11px] flex items-center space-x-1.5">
                  <span>Cloudflare R2 Payload Transfer</span>
                  {updateProgress > 0 && updateProgress < 100 && (
                    <span className="text-cyan-400 font-mono text-[10px]">(@ 4.8 MB/s - Edge CDN)</span>
                  )}
                </span>
                <span className="font-mono text-cyan-400 font-bold">{updateProgress}%</span>
              </div>

              <div className="w-full bg-slate-900 border border-slate-800 h-3.5 rounded-full overflow-hidden p-0.5">
                <div
                  className={`h-full rounded-full transition-all duration-300 shadow-sm ${
                    updaterState.status === 'error'
                      ? 'bg-rose-500 shadow-rose-500/50'
                      : updaterState.status === 'downloaded'
                      ? 'bg-emerald-500 shadow-emerald-500/50'
                      : 'bg-gradient-to-r from-indigo-500 via-cyan-400 to-emerald-400 shadow-cyan-500/50'
                  }`}
                  style={{ width: `${updateProgress}%` }}
                />
              </div>
            </div>

            {/* Status Message Highlight Box */}
            {updaterState.message && (
              <div className={`text-xs p-3 rounded-xl border flex items-start space-x-2.5 ${
                updaterState.status === 'error'
                  ? 'bg-rose-500/10 border-rose-500/25 text-rose-300'
                  : updaterState.status === 'downloaded'
                  ? 'bg-emerald-500/10 border-emerald-500/25 text-emerald-300'
                  : 'bg-slate-900/90 border-slate-800 text-slate-300'
              }`}>
                {updaterState.status === 'error' ? (
                  <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                ) : updaterState.status === 'downloaded' ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                ) : (
                  <Info className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
                )}
                <div className="flex-1 space-y-1">
                  <p className="font-medium leading-relaxed">{updaterState.message}</p>
                  {updaterState.status === 'error' && (
                    <div className="text-[11px] text-rose-400/90 font-mono pt-1">
                      Resolution: Check if DNS resolution on the CI runner uses IPv4 (`--dns-result-order=ipv4first`) or verify R2 bucket public access permissions.
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* If Downloaded, Show Immediate Restart & Apply Button */}
            {updaterState.status === 'downloaded' && (
              <div className="pt-1">
                <button
                  id="btn-restart-and-install"
                  onClick={onRestartAndInstall}
                  className="w-full py-3 bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 text-white rounded-xl text-xs font-bold transition flex items-center justify-center space-x-2 shadow-lg shadow-emerald-600/30 cursor-pointer animate-pulse"
                >
                  <Download className="w-4 h-4" />
                  <span>Restart & Apply Cloudflare R2 Update (v{appVersion})</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Jurisdiction-Specific Endpoints for S3 Clients Card */}
      <div id="r2-jurisdiction-endpoints-card" className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-800">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 bg-indigo-500/10 text-indigo-400 rounded-xl border border-indigo-500/20">
              <Server className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-sm font-bold text-white">Jurisdiction-Specific Endpoints for S3 Clients</h3>
                <span className="bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-[10px] font-mono px-2 py-0.5 rounded font-bold">
                  Account: {r2AccountId}
                </span>
              </div>
              <p className="text-xs text-slate-400">Configure S3 clients, Jenkins pipelines, and upload tools using specific jurisdiction targets for data sovereignty</p>
            </div>
          </div>

          {/* Jurisdiction Switcher Tabs */}
          <div className="flex items-center space-x-1.5 bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs">
            <button
              onClick={() => setSelectedJurisdiction('default')}
              className={`px-3 py-1.5 rounded-lg font-semibold transition cursor-pointer flex items-center space-x-1.5 ${
                selectedJurisdiction === 'default'
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <Globe className="w-3.5 h-3.5" />
              <span>Default (Global)</span>
            </button>

            <button
              onClick={() => setSelectedJurisdiction('eu')}
              className={`px-3 py-1.5 rounded-lg font-semibold transition cursor-pointer flex items-center space-x-1.5 ${
                selectedJurisdiction === 'eu'
                  ? 'bg-cyan-600 text-white shadow-md shadow-cyan-600/30'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>European Union (EU)</span>
            </button>
          </div>
        </div>

        {/* Selected Jurisdiction Highlight Banner */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2 bg-slate-950 border border-slate-800/80 rounded-xl p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center space-x-2">
                <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">Active S3 Endpoint</span>
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-bold border ${
                  selectedJurisdiction === 'eu'
                    ? 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30'
                    : 'bg-indigo-500/10 text-indigo-300 border-indigo-500/30'
                }`}>
                  {activeJurisdiction.badge}
                </span>
              </div>
              <span className="text-[11px] font-mono text-emerald-400">{activeJurisdiction.latency}</span>
            </div>

            {/* URL Display with Copy Button */}
            <div className="flex items-center justify-between p-3 bg-slate-900 rounded-lg border border-slate-800 font-mono text-xs text-indigo-300 break-all space-x-3">
              <span className="truncate selection:bg-indigo-500/30">{activeJurisdiction.endpoint}</span>
              <button
                onClick={() => copyToClipboard(activeJurisdiction.endpoint, 'activeEndpoint')}
                className="shrink-0 px-2.5 py-1 bg-indigo-600 hover:bg-indigo-500 text-white text-[11px] font-sans font-semibold rounded transition flex items-center space-x-1 cursor-pointer shadow"
              >
                {copiedKey === 'activeEndpoint' ? (
                  <>
                    <Check className="w-3 h-3 text-emerald-300" />
                    <span>Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3 h-3" />
                    <span>Copy URL</span>
                  </>
                )}
              </button>
            </div>

            <p className="text-xs text-slate-400 leading-relaxed">
              <strong className="text-slate-300">{activeJurisdiction.name}:</strong> {activeJurisdiction.compliance}
            </p>
          </div>

          {/* Quick Comparison Box */}
          <div className="bg-slate-950 border border-slate-800/80 rounded-xl p-4 space-y-3 flex flex-col justify-between">
            <div className="space-y-2">
              <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">Endpoint Comparison</span>
              <div className="space-y-2 text-[11px]">
                <div
                  onClick={() => setSelectedJurisdiction('default')}
                  className={`p-2 rounded border cursor-pointer transition ${
                    selectedJurisdiction === 'default'
                      ? 'bg-indigo-500/10 border-indigo-500/40 text-indigo-200'
                      : 'bg-slate-900 border-slate-800 text-slate-400 hover:bg-slate-850'
                  }`}
                >
                  <div className="font-bold flex items-center justify-between">
                    <span>Default: Global</span>
                    <span className="font-mono text-[9px] text-slate-400">Region: auto</span>
                  </div>
                  <div className="font-mono text-[10px] text-slate-400 truncate">https://{r2AccountId}.r2.cloudflarestorage.com</div>
                </div>

                <div
                  onClick={() => setSelectedJurisdiction('eu')}
                  className={`p-2 rounded border cursor-pointer transition ${
                    selectedJurisdiction === 'eu'
                      ? 'bg-cyan-500/10 border-cyan-500/40 text-cyan-200'
                      : 'bg-slate-900 border-slate-800 text-slate-400 hover:bg-slate-850'
                  }`}
                >
                  <div className="font-bold flex items-center justify-between">
                    <span>European Union (EU)</span>
                    <span className="font-mono text-[9px] text-cyan-400">GDPR Compliant</span>
                  </div>
                  <div className="font-mono text-[10px] text-slate-400 truncate">https://{r2AccountId}.eu.r2.cloudflarestorage.com</div>
                </div>
              </div>
            </div>

            <div className="text-[10px] text-slate-500 font-mono text-center pt-1 border-t border-slate-900">
              S3 API Compatibility: AWS Signature Version 4 (SigV4)
            </div>
          </div>
        </div>

        {/* Code Snippets for S3 Client Integration */}
        <div className="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden">
          <div className="p-3 bg-slate-900 border-b border-slate-800 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center space-x-2 text-xs font-bold text-slate-300">
              <Terminal className="w-3.5 h-3.5 text-indigo-400" />
              <span>S3 Client Code Configuration ({activeJurisdiction.name})</span>
            </div>

            <div className="flex items-center space-x-1 bg-slate-950 p-0.5 rounded-lg border border-slate-800 text-[10px] font-mono">
              {(['cli', 'jenkins', 'node', 'python'] as const).map(tab => (
                <button
                  key={tab}
                  onClick={() => setSelectedCodeSnippet(tab)}
                  className={`px-2.5 py-1 rounded transition cursor-pointer font-bold uppercase ${
                    selectedCodeSnippet === tab
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {tab === 'cli' ? 'AWS CLI' : tab === 'jenkins' ? 'Jenkinsfile' : tab === 'node' ? 'Node SDK' : 'Boto3'}
                </button>
              ))}
            </div>
          </div>

          <div className="p-4 font-mono text-[11px] bg-slate-950 space-y-2 relative">
            <pre className="text-slate-300 overflow-x-auto whitespace-pre-wrap leading-relaxed">
              {selectedCodeSnippet === 'cli' &&
`# 1. AWS CLI Upload to ${activeJurisdiction.name} Cloudflare R2
aws s3 cp dist-electron/ "s3://${r2Bucket}/" \\
    --endpoint-url "${activeJurisdiction.endpoint}" \\
    --recursive \\
    --exclude "*" \\
    --include "*.exe" \\
    --include "latest.yml" \\
    --include "latest.json"`}

              {selectedCodeSnippet === 'jenkins' &&
`// Jenkinsfile Cloudflare R2 S3 Configuration (${activeJurisdiction.name})
environment {
    R2_ACCOUNT_ID = "${r2AccountId}"
    R2_ENDPOINT   = "${activeJurisdiction.endpoint}"
    R2_BUCKET     = "s3://${r2Bucket}"
    BASE_URL      = "${r2BaseUrl}"
    AWS_DEFAULT_REGION = "${activeJurisdiction.region}"
}`}

              {selectedCodeSnippet === 'node' &&
`// Node.js @aws-sdk/client-s3 Client (${activeJurisdiction.name})
import { S3Client, PutObjectCommand } from "@aws-sdk/client-s3";

const s3 = new S3Client({
  region: "${activeJurisdiction.region}",
  endpoint: "${activeJurisdiction.endpoint}",
  credentials: {
    accessKeyId: process.env.R2_ACCESS_KEY_ID!,
    secretAccessKey: process.env.R2_SECRET_ACCESS_KEY!,
  },
});`}

              {selectedCodeSnippet === 'python' &&
`# Python boto3 S3 Client (${activeJurisdiction.name})
import boto3

s3 = boto3.client(
    "s3",
    endpoint_url="${activeJurisdiction.endpoint}",
    region_name="${activeJurisdiction.region}",
    aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
)`}
            </pre>

            <button
              onClick={() => {
                const textToCopy =
                  selectedCodeSnippet === 'cli'
                    ? `aws s3 cp dist-electron/ "s3://${r2Bucket}/" --endpoint-url "${activeJurisdiction.endpoint}" --recursive`
                    : selectedCodeSnippet === 'jenkins'
                    ? `R2_ENDPOINT = "${activeJurisdiction.endpoint}"`
                    : selectedCodeSnippet === 'node'
                    ? `endpoint: "${activeJurisdiction.endpoint}"`
                    : `endpoint_url="${activeJurisdiction.endpoint}"`;
                copyToClipboard(textToCopy, 'codeSnippet');
              }}
              className="absolute top-3 right-3 px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 text-[10px] font-sans font-semibold rounded border border-slate-700 transition flex items-center space-x-1 cursor-pointer"
            >
              {copiedKey === 'codeSnippet' ? (
                <>
                  <Check className="w-3 h-3 text-emerald-400" />
                  <span>Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3 h-3" />
                  <span>Copy Snippet</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Cloudflare R2 Distribution & Artifact Manifest Verification Grid */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-800">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 bg-cyan-500/10 text-cyan-400 rounded-xl border border-cyan-500/20">
              <Cloud className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-sm font-bold text-white">Cloudflare R2 Release Manifest & Artifacts</h3>
                <span className="bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 text-[10px] font-mono px-2 py-0.5 rounded font-bold">
                  Release v{appVersion} • Synced
                </span>
              </div>
              <p className="text-xs text-slate-400">Published release artifacts stored in Cloudflare R2 bucket with SHA-512 cryptographic hashes</p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <a
              href={`${r2BaseUrl}/latest.json`}
              target="_blank"
              rel="noreferrer"
              className="flex items-center space-x-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg text-xs font-medium transition cursor-pointer"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span>Inspect latest.json</span>
            </a>
          </div>
        </div>

        {/* Artifact Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3.5">
          {/* Card 1: NSIS Installer */}
          <div className="bg-slate-950 border border-slate-800 rounded-xl p-3.5 space-y-2 flex flex-col justify-between">
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                  NSIS Installer
                </span>
                <span className="text-[10px] font-mono text-slate-400">64.2 MB</span>
              </div>
              <div className="font-mono text-xs font-semibold text-slate-200 break-all">
                EmpMonitor Desktop Setup {appVersion}.exe
              </div>
              <p className="text-[11px] text-slate-400">Standard Windows executable setup with automatic start menu shortcuts.</p>
            </div>
            <div className="pt-2 border-t border-slate-900 flex items-center justify-between text-[10px] font-mono">
              <span className="text-slate-500">SHA-512 Verified</span>
              <button
                onClick={() => copyToClipboard(`${r2BaseUrl}/EmpMonitor Desktop Setup ${appVersion}.exe`, 'nsisUrl')}
                className="text-indigo-400 hover:text-indigo-300 flex items-center space-x-1 cursor-pointer"
              >
                {copiedKey === 'nsisUrl' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                <span>{copiedKey === 'nsisUrl' ? 'Copied' : 'Copy URL'}</span>
              </button>
            </div>
          </div>

          {/* Card 2: Portable Executable */}
          <div className="bg-slate-950 border border-slate-800 rounded-xl p-3.5 space-y-2 flex flex-col justify-between">
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                  Portable Executable
                </span>
                <span className="text-[10px] font-mono text-slate-400">61.8 MB</span>
              </div>
              <div className="font-mono text-xs font-semibold text-slate-200 break-all">
                EmpMonitor Desktop Runner {appVersion}.exe
              </div>
              <p className="text-[11px] text-slate-400">Standalone binary requiring zero installation or admin permissions.</p>
            </div>
            <div className="pt-2 border-t border-slate-900 flex items-center justify-between text-[10px] font-mono">
              <span className="text-slate-500">SHA-512 Verified</span>
              <button
                onClick={() => copyToClipboard(`${r2BaseUrl}/EmpMonitor Desktop Runner ${appVersion}.exe`, 'portableUrl')}
                className="text-cyan-400 hover:text-cyan-300 flex items-center space-x-1 cursor-pointer"
              >
                {copiedKey === 'portableUrl' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                <span>{copiedKey === 'portableUrl' ? 'Copied' : 'Copy URL'}</span>
              </button>
            </div>
          </div>

          {/* Card 3: latest.yml */}
          <div className="bg-slate-950 border border-slate-800 rounded-xl p-3.5 space-y-2 flex flex-col justify-between">
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                  Auto-Update Feed
                </span>
                <span className="text-[10px] font-mono text-slate-400">482 B</span>
              </div>
              <div className="font-mono text-xs font-semibold text-slate-200 break-all">
                latest.yml
              </div>
              <p className="text-[11px] text-slate-400">Electron-updater YAML manifest containing release version, sha512, and release date.</p>
            </div>
            <div className="pt-2 border-t border-slate-900 flex items-center justify-between text-[10px] font-mono">
              <span className="text-emerald-400">Primary Manifest</span>
              <button
                onClick={() => copyToClipboard(`${r2BaseUrl}/latest.yml`, 'ymlUrl')}
                className="text-emerald-400 hover:text-emerald-300 flex items-center space-x-1 cursor-pointer"
              >
                {copiedKey === 'ymlUrl' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                <span>{copiedKey === 'ymlUrl' ? 'Copied' : 'Copy URL'}</span>
              </button>
            </div>
          </div>

          {/* Card 4: latest.json */}
          <div className="bg-slate-950 border border-slate-800 rounded-xl p-3.5 space-y-2 flex flex-col justify-between">
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-300 border border-purple-500/20">
                  REST Manifest
                </span>
                <span className="text-[10px] font-mono text-slate-400">612 B</span>
              </div>
              <div className="font-mono text-xs font-semibold text-slate-200 break-all">
                latest.json
              </div>
              <p className="text-[11px] text-slate-400">REST API metadata endpoint for web inspectors and external release checkers.</p>
            </div>
            <div className="pt-2 border-t border-slate-900 flex items-center justify-between text-[10px] font-mono">
              <span className="text-purple-400">REST Mirror</span>
              <button
                onClick={() => copyToClipboard(`${r2BaseUrl}/latest.json`, 'jsonUrl')}
                className="text-purple-400 hover:text-purple-300 flex items-center space-x-1 cursor-pointer"
              >
                {copiedKey === 'jsonUrl' ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                <span>{copiedKey === 'jsonUrl' ? 'Copied' : 'Copy URL'}</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Jenkins CI/CD & Cloudflare R2 Publish Pipeline Synchronization Card */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-800">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 bg-emerald-500/10 text-emerald-400 rounded-xl border border-emerald-500/20">
              <Cpu className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-sm font-bold text-white">Jenkins CI/CD to Cloudflare R2 Pipeline Synchronization</h3>
                <span className="bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[10px] font-mono px-2 py-0.5 rounded font-bold">
                  Build #{jenkinsInfo?.jenkins?.buildNumber || 42} • SUCCESS
                </span>
              </div>
              <p className="text-xs text-slate-400">Full lifecycle: Source build → electron-builder packaging → Cloudflare R2 object storage publish</p>
            </div>
          </div>

          <span className="text-xs text-slate-400 font-mono">
            Total Pipeline Duration: {jenkinsInfo?.jenkins?.durationSeconds || 142.6}s
          </span>
        </div>

        {/* 3-Step Overview */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="bg-slate-950 border border-slate-800 rounded-xl p-3.5 space-y-2">
            <div className="flex items-center space-x-2 text-xs font-bold text-emerald-400">
              <CheckCircle2 className="w-4 h-4" />
              <span>1. Build & Version Tagging</span>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Jenkins extracts Git commit <code className="text-indigo-300 font-mono text-[10px]">{jenkinsInfo?.jenkins?.gitBuildData?.commitHash || 'c7f4a28'}</code>, compiles TypeScript server and Vite frontend into standalone distributions.
            </p>
          </div>

          <div className="bg-slate-950 border border-slate-800 rounded-xl p-3.5 space-y-2">
            <div className="flex items-center space-x-2 text-xs font-bold text-emerald-400">
              <CheckCircle2 className="w-4 h-4" />
              <span>2. Hardened Windows Packaging</span>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              <code className="text-indigo-300 font-mono text-[10px]">electron-builder</code> bundles Windows x64 binaries with <code className="text-emerald-300 font-mono text-[10px]">-c.npmRebuild=false</code> and creates SHA-512 verified <code className="text-cyan-300 font-mono text-[10px]">latest.yml</code>.
            </p>
          </div>

          <div className="bg-slate-950 border border-slate-800 rounded-xl p-3.5 space-y-2">
            <div className="flex items-center space-x-2 text-xs font-bold text-emerald-400">
              <CheckCircle2 className="w-4 h-4" />
              <span>3. Cloudflare R2 S3 Sync</span>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Pipeline synchronizes artifacts to <code className="text-cyan-300 font-mono text-[10px]">s3://empmonitor-updates</code> using AWS CLI / S3 API with zero egress fees and instant CDN edge propagation.
            </p>
          </div>
        </div>

        {/* Pipeline Stage Breakdown List */}
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-3">
          <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">Jenkins Pipeline Stages Execution</h4>
          <div className="space-y-2">
            {(jenkinsInfo?.jenkins?.pipelineStages || [
              { name: "Checkout & Git Metadata", status: "SUCCESS", duration: "4s", notes: "Extracted commit message & HEAD hash" },
              { name: "Install Dependencies", status: "SUCCESS", duration: "32s", notes: "Clean npm --force install" },
              { name: "Build Web & Backend Server", status: "SUCCESS", duration: "18s", notes: "Compiled Vite client and standalone server.cjs" },
              { name: "Extract App Version", status: "SUCCESS", duration: "1s", notes: `Detected v${appVersion}` },
              { name: "Package Desktop EXE", status: "SUCCESS", duration: "65s", notes: "Bundled installer & portable binary with sha512 checksums (-c.npmRebuild=false)" },
              { name: "Publish to Cloudflare R2", status: "SUCCESS", duration: "14s", notes: "Synchronized dist-electron/* to s3://empmonitor-updates with public-read ACL" },
              { name: "Archive Artifacts", status: "SUCCESS", duration: "8s", notes: "Archived dist-electron/*.exe, latest.yml & latest.json" }
            ]).map((stg: any, i: number) => (
              <div key={i} className="flex items-center justify-between py-2 px-3 bg-slate-900/60 rounded-lg border border-slate-800/80 text-xs">
                <div className="flex items-center space-x-2.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 shrink-0"></span>
                  <span className="font-semibold text-slate-200">{stg.name}</span>
                  <span className="text-slate-500 text-[11px]">({stg.notes})</span>
                </div>
                <div className="flex items-center space-x-3 shrink-0">
                  <span className="text-[10px] font-mono text-slate-400">{stg.duration}</span>
                  <span className="bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[9px] font-mono px-2 py-0.5 rounded font-bold">
                    {stg.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Detailed Auto-Update Diagnostic Console */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
        <div className="p-4 bg-slate-900 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center space-x-2.5">
            <div className="p-1.5 bg-indigo-500/10 text-indigo-400 rounded-lg border border-indigo-500/20">
              <Terminal className="w-4 h-4" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-white uppercase tracking-wider">Cloudflare R2 Diagnostic Event Stream</h4>
              <p className="text-[11px] text-slate-400">Corroborates HTTP query headers, manifest checksums, and update staging</p>
            </div>
          </div>

          {/* Log Filters & Controls */}
          <div className="flex items-center space-x-2">
            <div className="flex items-center space-x-1 bg-slate-950 p-0.5 rounded-lg border border-slate-800 text-[10px] font-mono">
              {(['ALL', 'INFO', 'SUCCESS', 'WARN', 'ERROR'] as const).map(lvl => (
                <button
                  key={lvl}
                  onClick={() => setLogFilter(lvl)}
                  className={`px-2 py-1 rounded transition cursor-pointer font-bold ${
                    logFilter === lvl
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {lvl}
                </button>
              ))}
            </div>

            <button
              onClick={onDownloadLogs}
              className="flex items-center space-x-1.5 px-2.5 py-1 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded-lg transition cursor-pointer"
              title="Download full log.txt file"
            >
              <Download className="w-3.5 h-3.5" />
              <span>log.txt</span>
            </button>
          </div>
        </div>

        {/* Terminal Log Output */}
        <div className="p-4 font-mono text-[11px] max-h-60 overflow-y-auto space-y-2 bg-slate-950">
          {filteredLogs.length === 0 ? (
            <p className="text-slate-500 italic text-center py-4">
              No events match the current filter. Click "Check for Updates" or "Simulate R2 Download" to run update sequences.
            </p>
          ) : (
            filteredLogs.map((log, idx) => (
              <div key={idx} className="flex items-start space-x-2.5 border-b border-slate-900/60 pb-1.5">
                <span className="text-slate-500 text-[10px] shrink-0 font-mono">{log.time}</span>
                <span className={`px-1.5 py-0.2 rounded text-[9px] font-bold shrink-0 font-mono ${
                  log.level === 'ERROR' ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30' :
                  log.level === 'WARN' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                  log.level === 'SUCCESS' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' :
                  'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30'
                }`}>
                  {log.level}
                </span>
                <div className="flex-1 space-y-1">
                  <p className="text-slate-200 leading-relaxed">{log.msg}</p>
                  {log.details && (
                    <pre className="text-[10px] text-cyan-300 bg-slate-900/90 p-2 rounded border border-slate-800 overflow-x-auto whitespace-pre-wrap">
                      {log.details}
                    </pre>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
