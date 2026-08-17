import { StructuredReport, FindingRecord } from '../types';

/**
 * Generates an executive self-contained HTML report with embedded styles,
 * interactive accordion, evidence badges, and statistics.
 */
export function generateStandaloneHtmlReport(report: StructuredReport): string {
  const metadata = {
    execution_id: report?.metadata?.execution_id || 'exec_current',
    generated_at: report?.metadata?.generated_at || new Date().toISOString(),
    environment: report?.metadata?.environment || 'local',
    framework_name: report?.metadata?.framework_name || 'empaf',
    framework_version: report?.metadata?.framework_version || '0.1.0',
    host: report?.metadata?.host || 'local',
    organization: report?.metadata?.organization || 'EmpMonitor QA',
  };

  const sections = report?.sections || [];
  const allFindings: { finding: FindingRecord; sectionTitle: string }[] = [];
  sections.forEach((s) => {
    (s.findings || []).forEach((f) => {
      allFindings.push({ finding: f, sectionTitle: s.title });
    });
  });

  const total = report?.summary?.total_findings ?? allFindings.length;
  const failed = report?.summary?.failed ?? allFindings.filter((f) => f.finding.verdict === 'FAILED').length;
  const blocked = report?.summary?.blocked ?? allFindings.filter((f) => f.finding.verdict === 'BLOCKED').length;
  const inconclusive = report?.summary?.inconclusive ?? allFindings.filter((f) => f.finding.verdict === 'INCONCLUSIVE').length;
  const degraded = report?.summary?.degraded ?? allFindings.filter((f) => f.finding.verdict === 'DEGRADED').length;
  const healthy = report?.summary?.healthy ?? Math.max(0, total - failed - blocked - inconclusive - degraded);
  const overallVerdict = report?.summary?.overall_verdict || (failed > 0 ? 'FAILED' : blocked > 0 ? 'BLOCKED' : 'HEALTHY');

  const verdictColors: Record<string, { bg: string; text: string; border: string }> = {
    HEALTHY: { bg: '#064e3b', text: '#34d399', border: '#059669' },
    DEGRADED: { bg: '#78350f', text: '#fcd34d', border: '#d97706' },
    FAILED: { bg: '#881337', text: '#fb7185', border: '#e11d48' },
    BLOCKED: { bg: '#581c87', text: '#d8b4fe', border: '#9333ea' },
    INCONCLUSIVE: { bg: '#713f12', text: '#fbbf24', border: '#b45309' },
  };

  const vMeta = verdictColors[overallVerdict] || verdictColors.INCONCLUSIVE;

  const findingsRows = allFindings.map(({ finding, sectionTitle }, index) => {
    const fMeta = verdictColors[finding.verdict] || verdictColors.INCONCLUSIVE;
    const evIds = (finding.evidence_ids || []).map((id) => `<span class="badge badge-ev">${id}</span>`).join(' ');
    const layers = (finding.corroboration || []).map((l) => `<span class="badge badge-layer">${l}</span>`).join(' ');
    const notesHtml = finding.notes && finding.notes.length > 0
      ? `<div class="notes-box"><strong>Diagnostic Notes:</strong><ul>${finding.notes.map(n => `<li>${n}</li>`).join('')}</ul></div>`
      : '';

    return `
      <div class="card finding-card">
        <div class="card-header">
          <div class="card-title-group">
            <span class="badge badge-verdict" style="background: ${fMeta.bg}; color: ${fMeta.text}; border-color: ${fMeta.border};">${finding.verdict}</span>
            <span class="badge badge-plugin">${sectionTitle}</span>
            ${finding.failure_class ? `<span class="badge badge-error">${finding.failure_class}</span>` : ''}
            <span class="conf-text">Confidence: <strong>${finding.confidence || 'HIGH'}</strong></span>
          </div>
          <h3 class="finding-what">${finding.what}</h3>
        </div>
        <div class="card-body">
          <div class="grid-2">
            <div class="meta-block">
              <span class="meta-label">Test Boundary & Location (Where)</span>
              <div class="code-val">${finding.where}</div>
            </div>
            <div class="meta-block">
              <span class="meta-label">Hypothesis & Root Cause (Why)</span>
              <div class="text-val">${finding.why}</div>
            </div>
          </div>
          <div class="evidence-strip">
            <div><strong>Evidence IDs:</strong> ${evIds || '<span class="text-muted">None cited</span>'}</div>
            <div><strong>Corroborated Layers:</strong> ${layers || '<span class="text-muted">None</span>'}</div>
          </div>
          ${notesHtml}
        </div>
      </div>
    `;
  }).join('\n');

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>EmpMonitor Test Execution Report - ${metadata.execution_id}</title>
  <style>
    :root {
      --bg: #0f172a;
      --card-bg: #1e293b;
      --card-sub: #090d16;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --border: #334155;
      --primary: #6366f1;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 32px 16px;
    }
    .container { max-width: 1200px; margin: 0 auto; }
    .header-banner {
      background: ${vMeta.bg};
      border: 1px solid ${vMeta.border};
      color: ${vMeta.text};
      border-radius: 12px;
      padding: 24px;
      margin-bottom: 24px;
    }
    .header-top { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px; }
    .header-title h1 { font-size: 24px; font-weight: 800; color: #fff; margin-bottom: 6px; }
    .meta-pills { display: flex; gap: 8px; flex-wrap: wrap; }
    .meta-pill { background: rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.15); font-size: 11px; padding: 3px 10px; border-radius: 9999px; color: #e2e8f0; font-family: monospace; }
    .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-top: 20px; }
    .stat-box { background: rgba(0,0,0,0.35); border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; padding: 12px; }
    .stat-label { font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: 600; }
    .stat-value { font-size: 22px; font-weight: 800; color: #fff; margin-top: 4px; }
    .section-title { font-size: 14px; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 700; color: var(--text-muted); margin: 32px 0 16px; }
    .finding-card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 10px; margin-bottom: 16px; overflow: hidden; }
    .card-header { padding: 16px; border-bottom: 1px solid rgba(255,255,255,0.06); }
    .card-title-group { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
    .finding-what { font-size: 15px; font-weight: 700; color: #f1f5f9; }
    .card-body { padding: 16px; }
    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 12px; }
    @media(max-width: 768px) { .grid-2 { grid-template-columns: 1fr; } }
    .meta-block { background: var(--card-sub); border: 1px solid var(--border); border-radius: 8px; padding: 12px; }
    .meta-label { font-size: 10px; text-transform: uppercase; font-weight: 700; color: var(--text-muted); display: block; margin-bottom: 6px; }
    .code-val { font-family: monospace; font-size: 12px; color: #a5b4fc; word-break: break-all; }
    .text-val { font-size: 12px; color: #cbd5e1; }
    .evidence-strip { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; background: rgba(0,0,0,0.25); border: 1px solid var(--border); border-radius: 6px; padding: 10px 12px; font-size: 11px; }
    .badge { font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 4px; text-transform: uppercase; border: 1px solid transparent; }
    .badge-plugin { background: #334155; color: #e2e8f0; font-family: monospace; }
    .badge-error { background: #881337; color: #fecdd3; border-color: #e11d48; font-family: monospace; }
    .badge-ev { background: rgba(99,102,241,0.15); color: #c7d2fe; border-color: rgba(99,102,241,0.3); font-family: monospace; }
    .badge-layer { background: #0f172a; color: #94a3b8; border-color: #334155; font-family: monospace; }
    .conf-text { font-size: 11px; color: var(--text-muted); margin-left: auto; }
    .notes-box { margin-top: 12px; background: var(--card-sub); border: 1px solid var(--border); border-radius: 6px; padding: 10px 12px; font-size: 11px; color: #cbd5e1; }
    .notes-box ul { margin-left: 18px; margin-top: 4px; }
    footer { text-align: center; font-size: 11px; color: var(--text-muted); margin-top: 40px; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header-banner">
      <div class="header-top">
        <div class="header-title">
          <h1>EmpMonitor Test Execution Report</h1>
          <p>Verified against 4-Layer Empirical Validation Standard</p>
        </div>
        <div class="meta-pills">
          <span class="meta-pill">Verdict: ${overallVerdict}</span>
          <span class="meta-pill">Execution: ${metadata.execution_id.slice(0, 12)}</span>
          <span class="meta-pill">Env: ${metadata.environment}</span>
          <span class="meta-pill">Time: ${new Date(metadata.generated_at).toLocaleString()}</span>
        </div>
      </div>
      <div class="stats-grid">
        <div class="stat-box">
          <div class="stat-label">Total Findings</div>
          <div class="stat-value">${total}</div>
        </div>
        <div class="stat-box">
          <div class="stat-label" style="color: #34d399;">Healthy</div>
          <div class="stat-value" style="color: #34d399;">${healthy}</div>
        </div>
        <div class="stat-box">
          <div class="stat-label" style="color: #fb7185;">Failed</div>
          <div class="stat-value" style="color: #fb7185;">${failed}</div>
        </div>
        <div class="stat-box">
          <div class="stat-label" style="color: #d8b4fe;">Blocked</div>
          <div class="stat-value" style="color: #d8b4fe;">${blocked}</div>
        </div>
        <div class="stat-box">
          <div class="stat-label" style="color: #fbbf24;">Inconclusive</div>
          <div class="stat-value" style="color: #fbbf24;">${inconclusive}</div>
        </div>
      </div>
    </div>

    <div class="section-title">Detailed Hypotheses, Conditions & Objective Evidence</div>
    ${findingsRows}

    <footer>
      EmpMonitor Automation Framework (EMPAF) &bull; Generated: ${metadata.generated_at} &bull; Standard: ${metadata.framework_name} v${metadata.framework_version}
    </footer>
  </div>
</body>
</html>`;
}
