import React, { useState, useMemo } from 'react';
import {
  ShieldAlert,
  ShieldCheck,
  HelpCircle,
  Ban,
  AlertTriangle,
  Layers,
  FileCode2,
  CheckCircle2,
  XCircle,
  Clock,
  Search,
  Filter,
  Download,
  Copy,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Info,
  Terminal,
  Cpu,
  FolderTree,
  FileText,
  Activity,
  Maximize2,
  Minimize2,
  RefreshCw,
  SlidersHorizontal,
} from 'lucide-react';
import { StructuredReport, FindingRecord, ReportSection } from '../types';

interface ReportViewerProps {
  report: StructuredReport | null;
  onRefreshLatest?: () => void;
  onRunSuite?: () => void;
  isLoading?: boolean;
}

const LAYER_LABELS: Record<string, { name: string; desc: string; color: string }> = {
  L1: { name: 'L1: Configuration & Static', desc: 'Config files, registry keys, static assets', color: 'text-blue-400 bg-blue-500/10 border-blue-500/30' },
  L2: { name: 'L2: Host Runtime & Processes', desc: 'Active services, processes, SQLite db, local storage', color: 'text-purple-400 bg-purple-500/10 border-purple-500/30' },
  L3: { name: 'L3: Pipeline & Sync', desc: 'Network telemetry, sync endpoints, upload queues', color: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/30' },
  L4: { name: 'L4: Dashboard & UI', desc: 'Web console UI, Playwright DOM verification', color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30' },
};

const VERDICT_CONFIG: Record<string, { label: string; bg: string; text: string; border: string; icon: any; summary: string }> = {
  HEALTHY: {
    label: 'HEALTHY (PASS)',
    bg: 'bg-emerald-500/10',
    text: 'text-emerald-400',
    border: 'border-emerald-500/30',
    icon: ShieldCheck,
    summary: 'All conditions and test hypotheses verified with positive objective evidence.',
  },
  DEGRADED: {
    label: 'DEGRADED',
    bg: 'bg-amber-500/10',
    text: 'text-amber-300',
    border: 'border-amber-500/30',
    icon: AlertTriangle,
    summary: 'Core functionality verified, but operational degradation was observed.',
  },
  FAILED: {
    label: 'FAILED',
    bg: 'bg-rose-500/10',
    text: 'text-rose-400',
    border: 'border-rose-500/30',
    icon: ShieldAlert,
    summary: 'Test hypothesis rejected or defect localized. One or more assertions failed.',
  },
  INCONCLUSIVE: {
    label: 'INCONCLUSIVE',
    bg: 'bg-amber-500/10',
    text: 'text-amber-400',
    border: 'border-amber-500/30',
    icon: HelpCircle,
    summary: 'Insufficient evidence observed to reach a conclusive verdict. Unanswered questions remain.',
  },
  BLOCKED: {
    label: 'BLOCKED',
    bg: 'bg-purple-500/10',
    text: 'text-purple-300',
    border: 'border-purple-500/30',
    icon: Ban,
    summary: 'Preconditions or host installation not met; validation pipeline was blocked from full execution.',
  },
};

export const ReportViewer: React.FC<ReportViewerProps> = ({
  report,
  onRefreshLatest,
  onRunSuite,
  isLoading = false,
}) => {
  const [selectedVerdictFilter, setSelectedVerdictFilter] = useState<string>('ALL');
  const [selectedPluginFilter, setSelectedPluginFilter] = useState<string>('ALL');
  const [selectedLayerFilter, setSelectedLayerFilter] = useState<string>('ALL');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [expandedFindings, setExpandedFindings] = useState<Record<number, boolean>>({});
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({});
  const [showRawJson, setShowRawJson] = useState<boolean>(false);
  const [copiedNotification, setCopiedNotification] = useState<string | null>(null);

  // Safely normalized metadata
  const metadata = useMemo(() => {
    return {
      execution_id: report?.metadata?.execution_id || 'exec_current',
      generated_at: report?.metadata?.generated_at || new Date().toISOString(),
      environment: report?.metadata?.environment || 'local',
      framework_name: report?.metadata?.framework_name || 'empaf',
      framework_version: report?.metadata?.framework_version || '0.1.0',
      validation_standard_version: report?.metadata?.validation_standard_version || '1.0.0',
      host: report?.metadata?.host || 'local',
      organization: report?.metadata?.organization || 'EmpMonitor QA',
    };
  }, [report]);

  // Flatten all findings across sections for unified searching and filtering
  const allFindings = useMemo(() => {
    if (!report) return [];
    const list: { finding: FindingRecord; sectionTitle: string; index: number }[] = [];
    let idx = 0;

    if (Array.isArray(report.sections)) {
      report.sections.forEach((sec) => {
        sec.findings?.forEach((f) => {
          list.push({ finding: f, sectionTitle: sec.title || 'General', index: idx++ });
        });
      });
    } else if (Array.isArray((report as any).results)) {
      (report as any).results.forEach((res: any) => {
        if (Array.isArray(res.assertions)) {
          res.assertions.forEach((ass: any, aIdx: number) => {
            list.push({
              finding: {
                what: ass.name || `Assertion ${aIdx + 1}`,
                where: `Host (${res.plugin_id || res.name || 'Core'})`,
                why: ass.pass ? 'Assertion passed validation checks.' : (ass.error || 'Assertion failed.'),
                verdict: ass.pass ? 'HEALTHY' : 'FAILED',
                confidence: 'HIGH',
                corroboration: ['L1', 'L2'],
                evidence_ids: [`EV-${(res.plugin_id || 'COR').slice(0, 3).toUpperCase()}-${aIdx + 1}`],
              },
              sectionTitle: res.name || res.plugin_id || 'Core',
              index: idx++,
            });
          });
        }
      });
    }

    return list;
  }, [report]);

  // Safely normalized summary
  const summary = useMemo(() => {
    const rawSum = report?.summary;
    const total = rawSum?.total_findings ?? allFindings.length;
    const failed = rawSum?.failed ?? allFindings.filter((f) => f.finding.verdict === 'FAILED').length;
    const blocked = rawSum?.blocked ?? allFindings.filter((f) => f.finding.verdict === 'BLOCKED').length;
    const inconclusive = rawSum?.inconclusive ?? allFindings.filter((f) => f.finding.verdict === 'INCONCLUSIVE').length;
    const degraded = rawSum?.degraded ?? allFindings.filter((f) => f.finding.verdict === 'DEGRADED').length;
    const healthy = rawSum?.healthy ?? Math.max(0, total - failed - blocked - inconclusive - degraded);

    let ov = rawSum?.overall_verdict || (rawSum as any)?.verdict || (report as any)?.verdict;
    if (!ov) {
      if (failed > 0) ov = 'FAILED';
      else if (blocked > 0) ov = 'BLOCKED';
      else if (inconclusive > 0) ov = 'INCONCLUSIVE';
      else if (degraded > 0) ov = 'DEGRADED';
      else ov = 'HEALTHY';
    }

    return {
      overall_verdict: ov,
      lowest_confidence: rawSum?.lowest_confidence || (report as any)?.confidence || 'HIGH',
      total_findings: total,
      healthy: Math.max(0, healthy),
      degraded: Math.max(0, degraded),
      failed: Math.max(0, failed),
      inconclusive: Math.max(0, inconclusive),
      blocked: Math.max(0, blocked),
      layers_covered: rawSum?.layers_covered || ['L1', 'L2', 'L3', 'L4'],
      failure_classes: rawSum?.failure_classes || {},
      duration_seconds: rawSum?.duration_seconds,
    };
  }, [report, allFindings]);

  const pluginNames = useMemo(() => {
    if (!report?.sections) return [];
    return report.sections.map((s) => s.title);
  }, [report]);

  const filteredFindings = useMemo(() => {
    return allFindings.filter(({ finding, sectionTitle }) => {
      // Verdict filter
      if (selectedVerdictFilter !== 'ALL' && finding.verdict !== selectedVerdictFilter) {
        return false;
      }
      // Plugin filter
      if (selectedPluginFilter !== 'ALL' && sectionTitle !== selectedPluginFilter) {
        return false;
      }
      // Layer filter
      if (selectedLayerFilter !== 'ALL') {
        const hasLayer = finding.corroboration?.includes(selectedLayerFilter) || finding.where?.startsWith(selectedLayerFilter);
        if (!hasLayer) return false;
      }
      // Search term
      if (searchTerm.trim()) {
        const query = searchTerm.toLowerCase();
        const matchesWhat = finding.what?.toLowerCase().includes(query);
        const matchesWhere = finding.where?.toLowerCase().includes(query);
        const matchesWhy = finding.why?.toLowerCase().includes(query);
        const matchesEvidence = finding.evidence_ids?.some((ev) => ev.toLowerCase().includes(query));
        const matchesPlugin = sectionTitle.toLowerCase().includes(query);
        const matchesClass = finding.failure_class?.toLowerCase().includes(query);
        return matchesWhat || matchesWhere || matchesWhy || matchesEvidence || matchesPlugin || matchesClass;
      }
      return true;
    });
  }, [allFindings, selectedVerdictFilter, selectedPluginFilter, selectedLayerFilter, searchTerm]);

  const toggleFindingExpand = (index: number) => {
    setExpandedFindings((prev) => ({ ...prev, [index]: !prev[index] }));
  };

  const toggleSectionExpand = (title: string) => {
    setExpandedSections((prev) => ({ ...prev, [title]: prev[title] === false ? true : false }));
  };

  const handleCopyBugSummary = () => {
    if (!report) return;
    const failedFindings = allFindings.filter((f) => f.finding.verdict === 'FAILED' || f.finding.verdict === 'BLOCKED');

    const markdown = [
      `# EmpMonitor Test Execution Report`,
      `**Verdict:** ${summary.overall_verdict} (${summary.lowest_confidence} Confidence)`,
      `**Execution ID:** ${metadata.execution_id}`,
      `**Environment:** ${metadata.environment}`,
      `**Timestamp:** ${metadata.generated_at}`,
      `**Total Findings:** ${summary.total_findings} (Failed: ${summary.failed}, Blocked: ${summary.blocked}, Inconclusive: ${summary.inconclusive}, Healthy: ${summary.healthy})`,
      `\n## Defect & Failure Breakdown:`,
      ...failedFindings.map(
        ({ finding, sectionTitle }, i) =>
          `\n### ${i + 1}. [${finding.verdict}] ${finding.what}\n- **Plugin:** ${sectionTitle}\n- **Location (Where):** \`${finding.where}\`\n- **Root Cause (Why):** ${finding.why}\n- **Evidence IDs:** ${finding.evidence_ids?.join(', ') || 'N/A'}\n- **Failure Class:** ${finding.failure_class || 'None'}\n${
            finding.notes?.length ? `- **Notes:** ${finding.notes.join('; ')}` : ''
          }`
      ),
    ].join('\n');

    navigator.clipboard.writeText(markdown);
    setCopiedNotification('Report summary copied to clipboard in Markdown format!');
    setTimeout(() => setCopiedNotification(null), 3000);
  };

  const handleDownloadJson = () => {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `empmonitor-report-${(metadata.execution_id || 'test').slice(0, 8)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (!report) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-10 text-center space-y-4">
        <div className="w-12 h-12 rounded-full bg-slate-800 flex items-center justify-center mx-auto text-slate-400">
          <FileText className="w-6 h-6" />
        </div>
        <div className="space-y-1">
          <h3 className="text-base font-bold text-slate-200">No Execution Report Available</h3>
          <p className="text-xs text-slate-400 max-w-md mx-auto">
            Execute a test suite run or fetch the latest generated report from disk to inspect detailed test hypotheses, conditions, and objective evidence.
          </p>
        </div>
        <div className="flex items-center justify-center space-x-3 pt-2">
          {onRefreshLatest && (
            <button
              onClick={onRefreshLatest}
              disabled={isLoading}
              className="flex items-center space-x-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-semibold border border-slate-700 transition"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
              <span>Load Latest Report from Disk</span>
            </button>
          )}
          {onRunSuite && (
            <button
              onClick={onRunSuite}
              disabled={isLoading}
              className="flex items-center space-x-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow-lg shadow-indigo-600/30 transition"
            >
              <Activity className="w-3.5 h-3.5" />
              <span>Run Regression Suite Now</span>
            </button>
          )}
        </div>
      </div>
    );
  }

  const verdictMeta = VERDICT_CONFIG[summary.overall_verdict] || VERDICT_CONFIG.INCONCLUSIVE;
  const VerdictIcon = verdictMeta.icon;

  return (
    <div className="space-y-6">
      {/* Toast alert */}
      {copiedNotification && (
        <div className="fixed bottom-6 right-6 z-50 bg-emerald-600 text-white px-4 py-2.5 rounded-xl shadow-2xl text-xs font-semibold flex items-center space-x-2 animate-in fade-in slide-in-from-bottom-3 duration-200">
          <CheckCircle2 className="w-4 h-4" />
          <span>{copiedNotification}</span>
        </div>
      )}

      {/* Top Executive Verdict Banner */}
      <div className={`border rounded-xl p-5 ${verdictMeta.bg} ${verdictMeta.border}`}>
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex items-start space-x-3.5">
            <div className={`p-2.5 rounded-xl border shrink-0 mt-0.5 ${verdictMeta.bg} ${verdictMeta.text} ${verdictMeta.border}`}>
              <VerdictIcon className="w-6 h-6" />
            </div>
            <div className="space-y-1">
              <div className="flex items-center space-x-2.5 flex-wrap gap-y-1">
                <span className={`text-base font-extrabold tracking-tight ${verdictMeta.text}`}>
                  {verdictMeta.label}
                </span>
                <span className="text-xs px-2.5 py-0.5 rounded-full font-bold bg-slate-900/80 text-slate-300 border border-slate-700/50">
                  Confidence: <span className="text-indigo-300">{summary.lowest_confidence}</span>
                </span>
                <span className="text-xs px-2.5 py-0.5 rounded-full font-mono bg-slate-900/80 text-slate-400 border border-slate-700/50">
                  Env: <span className="text-slate-200 font-semibold">{metadata.environment || 'local'}</span>
                </span>
              </div>
              <p className="text-xs text-slate-300 font-medium">
                {verdictMeta.summary}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2 shrink-0">
            <button
              onClick={handleCopyBugSummary}
              className="flex items-center space-x-1.5 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 text-slate-200 border border-slate-700 rounded-lg text-xs font-semibold transition cursor-pointer"
              title="Copy executive summary & defects in markdown format"
            >
              <Copy className="w-3.5 h-3.5 text-slate-400" />
              <span>Copy Bug Summary</span>
            </button>
            <button
              onClick={handleDownloadJson}
              className="flex items-center space-x-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold shadow-lg shadow-indigo-600/20 transition cursor-pointer"
              title="Download raw report.json artifact"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Export JSON</span>
            </button>
          </div>
        </div>

        {/* Aggregate Findings Count Ribbon */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5 mt-5 pt-4 border-t border-slate-800/80 text-xs">
          <div className="bg-slate-950/60 rounded-lg p-2.5 border border-slate-800/60">
            <div className="text-[11px] text-slate-400 font-medium">Total Assertions</div>
            <div className="text-lg font-bold text-slate-100">{summary.total_findings}</div>
          </div>
          <div className="bg-rose-950/30 rounded-lg p-2.5 border border-rose-800/30">
            <div className="text-[11px] text-rose-300/80 font-medium">Failed</div>
            <div className="text-lg font-bold text-rose-400">{summary.failed}</div>
          </div>
          <div className="bg-amber-950/30 rounded-lg p-2.5 border border-amber-800/30">
            <div className="text-[11px] text-amber-300/80 font-medium">Inconclusive</div>
            <div className="text-lg font-bold text-amber-400">{summary.inconclusive}</div>
          </div>
          <div className="bg-purple-950/30 rounded-lg p-2.5 border border-purple-800/30">
            <div className="text-[11px] text-purple-300/80 font-medium">Blocked</div>
            <div className="text-lg font-bold text-purple-300">{summary.blocked}</div>
          </div>
          <div className="bg-emerald-950/30 rounded-lg p-2.5 border border-emerald-800/30">
            <div className="text-[11px] text-emerald-300/80 font-medium">Healthy (Passed)</div>
            <div className="text-lg font-bold text-emerald-400">{summary.healthy}</div>
          </div>
        </div>
      </div>

      {/* Failure Classes & Evidence Layers Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Evidence Layers Covered */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 space-y-3">
          <div className="flex items-center space-x-2 text-xs font-bold text-slate-300 uppercase tracking-wider">
            <Layers className="w-4 h-4 text-indigo-400" />
            <span>Evidence Layers Observed</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
            {Object.entries(LAYER_LABELS).map(([layerKey, layerInfo]) => {
              const isCovered = (summary.layers_covered || []).some((l: any) =>
                typeof l === 'string' ? l === layerKey : l?.label === layerKey || l?.id === layerKey
              );
              return (
                <div
                  key={layerKey}
                  className={`p-2.5 rounded-lg border flex flex-col justify-between transition ${
                    isCovered ? layerInfo.color : 'bg-slate-950/40 border-slate-800/40 opacity-40'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold">{layerInfo.name}</span>
                    <span className={`text-[10px] px-1.5 py-0.2 rounded font-semibold ${isCovered ? 'bg-slate-900' : 'bg-slate-900'}`}>
                      {isCovered ? 'Active' : 'Unobserved'}
                    </span>
                  </div>
                  <p className="text-[10px] opacity-80 mt-1">{layerInfo.desc}</p>
                </div>
              );
            })}
          </div>
        </div>

        {/* Defect Classifications */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 space-y-3">
          <div className="flex items-center space-x-2 text-xs font-bold text-slate-300 uppercase tracking-wider">
            <ShieldAlert className="w-4 h-4 text-rose-400" />
            <span>Defect Classifications</span>
          </div>
          {Object.keys(summary.failure_classes || {}).length > 0 ? (
            <div className="space-y-2">
              {Object.entries(summary.failure_classes).map(([defectClass, count]) => (
                <div
                  key={defectClass}
                  className="flex items-center justify-between p-2 rounded-lg bg-slate-950/60 border border-slate-800/80 text-xs"
                >
                  <span className="font-mono text-indigo-300 font-semibold">{defectClass}</span>
                  <span className="bg-rose-500/20 text-rose-300 border border-rose-500/30 px-2 py-0.5 rounded-full text-xs font-bold font-mono">
                    {count} {count === 1 ? 'finding' : 'findings'}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-4 bg-slate-950/40 rounded-lg text-center text-xs text-slate-400">
              No failure classes recorded for this run.
            </div>
          )}
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search findings by test case, target path, hypothesis why, or evidence ID..."
              className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-4 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div className="flex items-center space-x-2 flex-wrap gap-y-2 text-xs">
            {/* Verdict Filter Buttons */}
            <div className="flex items-center bg-slate-950 border border-slate-800 rounded-lg p-0.5">
              {['ALL', 'FAILED', 'BLOCKED', 'INCONCLUSIVE', 'HEALTHY'].map((v) => (
                <button
                  key={v}
                  onClick={() => setSelectedVerdictFilter(v)}
                  className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition ${
                    selectedVerdictFilter === v
                      ? 'bg-indigo-600 text-white'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {v === 'ALL' ? 'All' : v}
                </button>
              ))}
            </div>

            {/* Plugin Select */}
            {pluginNames.length > 1 && (
              <select
                value={selectedPluginFilter}
                onChange={(e) => setSelectedPluginFilter(e.target.value)}
                className="bg-slate-950 border border-slate-800 text-slate-300 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-indigo-500"
              >
                <option value="ALL">All Plugins ({pluginNames.length})</option>
                {pluginNames.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            )}

            {/* Raw JSON toggle */}
            <button
              onClick={() => setShowRawJson(!showRawJson)}
              className={`px-2.5 py-1.5 rounded-lg border text-xs font-semibold flex items-center space-x-1.5 transition ${
                showRawJson
                  ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40'
                  : 'bg-slate-950 text-slate-400 border-slate-800 hover:text-slate-200'
              }`}
            >
              <FileCode2 className="w-3.5 h-3.5" />
              <span>{showRawJson ? 'Hide JSON' : 'View JSON'}</span>
            </button>
          </div>
        </div>

        <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1">
          <span>
            Showing <strong className="text-slate-200">{filteredFindings.length}</strong> of{' '}
            <strong className="text-slate-200">{allFindings.length}</strong> total test assertions
          </span>
          {searchTerm && (
            <button
              onClick={() => setSearchTerm('')}
              className="text-indigo-400 hover:text-indigo-300 font-semibold"
            >
              Clear Search
            </button>
          )}
        </div>
      </div>

      {/* Raw JSON Accordion View */}
      {showRawJson && (
        <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="font-mono font-bold text-slate-300">report.json Artifact Data</span>
            <button
              onClick={handleDownloadJson}
              className="text-indigo-400 hover:text-indigo-300 font-semibold flex items-center space-x-1"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Download File</span>
            </button>
          </div>
          <pre className="p-3 bg-slate-900 rounded-lg font-mono text-[11px] text-slate-300 overflow-x-auto max-h-96 border border-slate-800">
            {JSON.stringify(report, null, 2)}
          </pre>
        </div>
      )}

      {/* Detailed Test Finding Cards */}
      <div className="space-y-4">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center space-x-2">
          <Activity className="w-4 h-4 text-indigo-400" />
          <span>Detailed Test Cases, Hypotheses & Objective Evidence</span>
        </h3>

        {filteredFindings.length === 0 ? (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 text-center text-slate-400 text-xs">
            No findings match the current filter criteria.
          </div>
        ) : (
          filteredFindings.map(({ finding, sectionTitle, index }) => {
            const isExpanded = expandedFindings[index] !== false; // expanded by default
            const isFailure = finding.verdict === 'FAILED';
            const isBlocked = finding.verdict === 'BLOCKED';
            const isInconclusive = finding.verdict === 'INCONCLUSIVE';
            const isHealthy = finding.verdict === 'HEALTHY';

            return (
              <div
                key={index}
                className={`bg-slate-900 border rounded-xl overflow-hidden transition-all ${
                  isFailure
                    ? 'border-rose-500/40 bg-rose-950/10'
                    : isBlocked
                    ? 'border-purple-500/40 bg-purple-950/10'
                    : isInconclusive
                    ? 'border-amber-500/40 bg-amber-950/10'
                    : 'border-slate-800'
                }`}
              >
                {/* Finding Header */}
                <div
                  onClick={() => toggleFindingExpand(index)}
                  className="p-4 flex items-start justify-between cursor-pointer hover:bg-slate-800/40 transition gap-3"
                >
                  <div className="flex items-start space-x-3">
                    <div className="mt-0.5 shrink-0">
                      {isFailure ? (
                        <XCircle className="w-4 h-4 text-rose-400" />
                      ) : isBlocked ? (
                        <Ban className="w-4 h-4 text-purple-400" />
                      ) : isInconclusive ? (
                        <HelpCircle className="w-4 h-4 text-amber-400" />
                      ) : (
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      )}
                    </div>
                    <div className="space-y-1">
                      <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                        <span
                          className={`text-[10px] font-extrabold uppercase px-2 py-0.5 rounded border ${
                            isFailure
                              ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                              : isBlocked
                              ? 'bg-purple-500/20 text-purple-300 border-purple-500/40'
                              : isInconclusive
                              ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                              : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                          }`}
                        >
                          {finding.verdict}
                        </span>

                        <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                          {sectionTitle}
                        </span>

                        {finding.failure_class && (
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-800/60 font-semibold">
                            {finding.failure_class}
                          </span>
                        )}

                        <span className="text-[10px] text-slate-400">
                          Confidence: <strong className="text-slate-200">{finding.confidence}</strong>
                        </span>
                      </div>

                      <h4 className="text-sm font-bold text-slate-100">{finding.what}</h4>
                    </div>
                  </div>

                  <div className="shrink-0 text-slate-400 mt-1">
                    {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                  </div>
                </div>

                {/* Expanded Details Body */}
                {isExpanded && (
                  <div className="px-4 pb-4 pt-1 space-y-3 border-t border-slate-800/60 text-xs">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
                      {/* Location & Scope ("Where") */}
                      <div className="bg-slate-950/70 border border-slate-800 rounded-lg p-3 space-y-1.5">
                        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center space-x-1.5">
                          <FolderTree className="w-3.5 h-3.5 text-indigo-400" />
                          <span>Test Boundary & Location (Where)</span>
                        </div>
                        <div className="font-mono text-xs text-indigo-300 bg-slate-900 px-2.5 py-1.5 rounded border border-slate-800 break-all">
                          {finding.where}
                        </div>
                      </div>

                      {/* Hypothesis & Root Cause ("Why") */}
                      <div className="bg-slate-950/70 border border-slate-800 rounded-lg p-3 space-y-1.5">
                        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center space-x-1.5">
                          <Info className="w-3.5 h-3.5 text-amber-400" />
                          <span>Hypothesis & Root Cause (Why)</span>
                        </div>
                        <p className="text-xs text-slate-300 leading-relaxed bg-slate-900 px-2.5 py-1.5 rounded border border-slate-800">
                          {finding.why}
                        </p>
                      </div>
                    </div>

                    {/* Objective Evidence & Corroboration */}
                    <div className="flex flex-wrap items-center justify-between gap-2 p-2.5 bg-slate-950/50 rounded-lg border border-slate-800/80 text-[11px]">
                      <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                        <span className="text-slate-400 font-semibold">Objective Evidence IDs:</span>
                        {finding.evidence_ids?.length > 0 ? (
                          finding.evidence_ids.map((evId) => (
                            <span
                              key={evId}
                              className="font-mono text-[10px] font-bold bg-indigo-500/10 text-indigo-300 border border-indigo-500/30 px-2 py-0.5 rounded"
                            >
                              {evId}
                            </span>
                          ))
                        ) : (
                          <span className="text-slate-500">None cited</span>
                        )}
                      </div>

                      <div className="flex items-center space-x-2">
                        <span className="text-slate-400 font-semibold">Layers Corroborated:</span>
                        {finding.corroboration?.map((l) => (
                          <span
                            key={l}
                            className="font-mono text-[10px] font-bold bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded border border-slate-700"
                          >
                            {l}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Diagnostic Notes & Hypothesis Reasoning */}
                    {finding.notes && finding.notes.length > 0 && (
                      <div className="bg-slate-950/80 border border-slate-800/80 rounded-lg p-3 space-y-1.5">
                        <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center space-x-1.5">
                          <FileText className="w-3.5 h-3.5 text-cyan-400" />
                          <span>Validation Standard Diagnostic Notes</span>
                        </div>
                        <ul className="space-y-1 text-[11px] text-slate-300 list-disc list-inside">
                          {finding.notes.map((note, nIdx) => (
                            <li key={nIdx} className="leading-relaxed">
                              {note}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Unresolved Evidence Conflicts (if any) */}
                    {finding.conflicts && finding.conflicts.length > 0 && (
                      <div className="bg-amber-950/30 border border-amber-800/40 rounded-lg p-3 space-y-1">
                        <div className="text-[10px] font-bold uppercase tracking-wider text-amber-300 flex items-center space-x-1.5">
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                          <span>Unresolved Evidence Conflicts</span>
                        </div>
                        <ul className="space-y-1 text-[11px] text-amber-200/90 list-disc list-inside">
                          {finding.conflicts.map((conf, cIdx) => (
                            <li key={cIdx}>{conf}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Section-by-Section Plugin Summary Breakdown */}
      <div className="space-y-4 pt-4 border-t border-slate-800">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center space-x-2">
          <Cpu className="w-4 h-4 text-indigo-400" />
          <span>Execution Unit / Plugin Section Breakdown</span>
        </h3>

        <div className="space-y-3">
          {(report.sections || []).length > 0 ? (
            report.sections?.map((section) => {
              const isSecExpanded = expandedSections[section.title] !== false;
              const secVerdictMeta = VERDICT_CONFIG[section.verdict] || VERDICT_CONFIG.INCONCLUSIVE;

              return (
                <div
                  key={section.title}
                  className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden"
                >
                  <div
                    onClick={() => toggleSectionExpand(section.title)}
                    className="p-4 bg-slate-900/90 flex items-center justify-between cursor-pointer hover:bg-slate-800/60 transition"
                  >
                    <div className="flex items-center space-x-3">
                      <span className="font-mono text-sm font-bold text-indigo-400">{section.title}</span>
                      <span
                        className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded border ${secVerdictMeta.bg} ${secVerdictMeta.text} ${secVerdictMeta.border}`}
                      >
                        {section.verdict}
                      </span>
                      <span className="text-xs text-slate-400 font-mono">
                        Status: <strong className="text-slate-200">{section.status}</strong>
                      </span>
                    </div>

                    <div className="flex items-center space-x-3 text-xs text-slate-400">
                      <span>{section.findings?.length ?? 0} assertions</span>
                      {isSecExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                    </div>
                  </div>

                  {isSecExpanded && section.metadata && Object.keys(section.metadata).length > 0 && (
                    <div className="p-4 bg-slate-950/60 border-t border-slate-800 text-xs space-y-3">
                      <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                        Observed Host Inspection Telemetry
                      </div>
                      <pre className="p-3 bg-slate-900 rounded-lg font-mono text-[11px] text-slate-300 overflow-x-auto max-h-48 border border-slate-800">
                        {JSON.stringify(section.metadata, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              );
            })
          ) : Array.isArray((report as any).results) ? (
            (report as any).results.map((res: any) => {
              const secTitle = res.name || res.plugin_id || 'Plugin';
              const isSecExpanded = expandedSections[secTitle] !== false;
              const secVerdictMeta = VERDICT_CONFIG[res.verdict] || VERDICT_CONFIG.HEALTHY;

              return (
                <div
                  key={secTitle}
                  className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden"
                >
                  <div
                    onClick={() => toggleSectionExpand(secTitle)}
                    className="p-4 bg-slate-900/90 flex items-center justify-between cursor-pointer hover:bg-slate-800/60 transition"
                  >
                    <div className="flex items-center space-x-3">
                      <span className="font-mono text-sm font-bold text-indigo-400">{secTitle}</span>
                      <span
                        className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded border ${secVerdictMeta.bg} ${secVerdictMeta.text} ${secVerdictMeta.border}`}
                      >
                        {res.verdict || 'HEALTHY'}
                      </span>
                    </div>

                    <div className="flex items-center space-x-3 text-xs text-slate-400">
                      <span>{res.assertions?.length ?? 0} assertions</span>
                      {isSecExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                    </div>
                  </div>
                </div>
              );
            })
          ) : (
            <div className="p-4 bg-slate-950/40 rounded-lg text-center text-xs text-slate-400">
              No section-level plugin breakdown available.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
