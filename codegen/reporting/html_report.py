"""HTML report generator for test execution summary and evidence.
"""

import html
from pathlib import Path
from codegen.reporting.models import ExecutionSummary, TestResult


class HTMLReportGenerator:
    """Generates professional HTML test execution reports."""

    @staticmethod
    def generate(summary: ExecutionSummary, output_path: Path) -> Path:
        """Write execution summary to test_report.html."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        html_content = HTMLReportGenerator._build_html(summary)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        return output_path

    @staticmethod
    def _status_badge(status: str) -> str:
        s = status.upper()
        if "PASS" in s and "SKIP" not in s:
            return '<span class="badge pass">PASS</span>'
        elif "FAIL" in s:
            return '<span class="badge fail">FAIL</span>'
        else:
            return '<span class="badge skip">SKIP</span>'

    @staticmethod
    def _overall_badge(status: str) -> str:
        s = status.upper()
        if s == "PASSED":
            return '<span class="badge overall-pass">PASSED</span>'
        elif s == "PASSED WITH SKIPS":
            return '<span class="badge overall-skip">PASSED WITH SKIPS</span>'
        else:
            return '<span class="badge overall-fail">FAILED</span>'

    @staticmethod
    def _build_html(summary: ExecutionSummary) -> str:
        failed_tests = [t for t in summary.tests if t.status == "FAIL"]

        # Build table rows
        rows_html = []
        for t in summary.tests:
            td_data = html.escape(str(t.test_data)) if t.test_data else "-"
            rows_html.append(f"""
            <tr>
                <td><strong>{html.escape(t.test_id)}</strong></td>
                <td>{html.escape(t.module)}</td>
                <td>{html.escape(t.title)}</td>
                <td><code>{td_data}</code></td>
                <td>{html.escape(t.expected)}</td>
                <td>{html.escape(t.actual)}</td>
                <td class="text-center">{HTMLReportGenerator._status_badge(t.status)}</td>
                <td class="text-right">{t.duration_seconds:.2f}s</td>
            </tr>
            """)

        # Build failure details section
        failures_html = []
        if failed_tests:
            for ft in failed_tests:
                img_html = ""
                if ft.screenshot_path and Path(ft.screenshot_path).exists():
                    rel_img = Path(ft.screenshot_path).name
                    img_html = f'''
                    <div class="evidence-box">
                        <strong>Screenshot Evidence:</strong><br>
                        <a href="screenshots/{rel_img}" target="_blank">
                            <img src="screenshots/{rel_img}" alt="Failure Screenshot" class="screenshot-img" />
                        </a>
                    </div>
                    '''

                trace_html = ""
                if ft.trace_path:
                    trace_html = f'<p><strong>Playwright Trace:</strong> <code>{html.escape(ft.trace_path)}</code></p>'

                failures_html.append(f"""
                <div class="card failure-card">
                    <div class="card-header">
                        <h3>{html.escape(ft.test_id)}: {html.escape(ft.title)} ({html.escape(ft.module)})</h3>
                        {HTMLReportGenerator._status_badge(ft.status)}
                    </div>
                    <div class="card-body">
                        <p><strong>Test File:</strong> <code>{html.escape(ft.test_file)}</code></p>
                        <p><strong>Expected Result:</strong> {html.escape(ft.expected)}</p>
                        <p><strong>Actual Result:</strong> {html.escape(ft.actual)}</p>
                        <p><strong>Failure Reason:</strong> {html.escape(ft.failure_reason or "Assertion / Execution Failure")}</p>
                        <div class="error-trace">
                            <pre>{html.escape(ft.exception_message)}</pre>
                        </div>
                        {img_html}
                        {trace_html}
                    </div>
                </div>
                """)

        failed_section = ""
        if failed_tests:
            failed_section = f"""
            <section class="section">
                <h2>🚨 Failed Test Cases & Failure Evidence</h2>
                {''.join(failures_html)}
            </section>
            """

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EMPMonitor Regression Test Report</title>
    <style>
        :root {{
            --primary: #1e293b;
            --accent: #2563eb;
            --bg: #f8fafc;
            --card-bg: #ffffff;
            --text: #0f172a;
            --muted: #64748b;
            --border: #e2e8f0;
            --pass-bg: #dcfce7;
            --pass-text: #15803d;
            --fail-bg: #fee2e2;
            --fail-text: #b91c1c;
            --skip-bg: #fef3c7;
            --skip-text: #b45309;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 24px;
            line-height: 1.5;
        }}
        .container {{
            max-width: 1280px;
            margin: 0 auto;
        }}
        header {{
            background: var(--card-bg);
            padding: 24px 32px;
            border-radius: 12px;
            border: 1px solid var(--border);
            margin-bottom: 24px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }}
        h1 {{
            margin: 0 0 8px 0;
            font-size: 26px;
            color: var(--primary);
        }}
        .subtitle {{
            color: var(--muted);
            margin: 0;
            font-size: 14px;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        .stat-card {{
            background: var(--card-bg);
            padding: 20px;
            border-radius: 10px;
            border: 1px solid var(--border);
            text-align: center;
        }}
        .stat-val {{
            font-size: 28px;
            font-weight: 700;
            margin-top: 4px;
        }}
        .stat-label {{
            font-size: 13px;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .meta-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 12px;
            background: var(--card-bg);
            padding: 20px 24px;
            border-radius: 10px;
            border: 1px solid var(--border);
            margin-bottom: 24px;
            font-size: 14px;
        }}
        .badge {{
            padding: 4px 10px;
            border-radius: 9999px;
            font-weight: 600;
            font-size: 12px;
            display: inline-block;
        }}
        .badge.pass {{ background: var(--pass-bg); color: var(--pass-text); }}
        .badge.fail {{ background: var(--fail-bg); color: var(--fail-text); }}
        .badge.skip {{ background: var(--skip-bg); color: var(--skip-text); }}
        .badge.overall-pass {{ background: var(--pass-bg); color: var(--pass-text); font-size: 14px; padding: 6px 14px; }}
        .badge.overall-fail {{ background: var(--fail-bg); color: var(--fail-text); font-size: 14px; padding: 6px 14px; }}
        .badge.overall-skip {{ background: var(--skip-bg); color: var(--skip-text); font-size: 14px; padding: 6px 14px; }}
        .table-card {{
            background: var(--card-bg);
            border-radius: 10px;
            border: 1px solid var(--border);
            overflow: hidden;
            margin-bottom: 32px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}
        th {{
            background: #f1f5f9;
            padding: 12px 16px;
            text-align: left;
            font-weight: 600;
            color: var(--primary);
            border-bottom: 1px solid var(--border);
        }}
        td {{
            padding: 12px 16px;
            border-bottom: 1px solid var(--border);
            vertical-align: top;
        }}
        tr:last-child td {{ border-bottom: none; }}
        code {{
            background: #f1f5f9;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 12px;
        }}
        .text-center {{ text-align: center; }}
        .text-right {{ text-align: right; }}
        .failure-card {{
            background: var(--card-bg);
            border: 1px solid #fca5a5;
            border-radius: 10px;
            margin-bottom: 20px;
            overflow: hidden;
        }}
        .failure-card .card-header {{
            background: #fef2f2;
            padding: 16px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #fecaca;
        }}
        .failure-card .card-header h3 {{ margin: 0; font-size: 16px; color: var(--fail-text); }}
        .failure-card .card-body {{ padding: 20px; }}
        .error-trace {{
            background: #1e293b;
            color: #f8fafc;
            padding: 16px;
            border-radius: 8px;
            overflow-x: auto;
            font-size: 12px;
            margin: 12px 0;
        }}
        .error-trace pre {{ margin: 0; white-space: pre-wrap; word-break: break-word; }}
        .screenshot-img {{
            max-width: 100%;
            max-height: 400px;
            border-radius: 8px;
            border: 1px solid var(--border);
            margin-top: 8px;
        }}
        .evidence-box {{
            margin-top: 16px;
            padding: 12px;
            background: #f8fafc;
            border: 1px solid var(--border);
            border-radius: 8px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>EMPMonitor Regression Test Report</h1>
            <p class="subtitle">Automated Playwright QA Execution Results</p>
        </header>

        <div class="summary-grid">
            <div class="stat-card">
                <div class="stat-label">Total Tests</div>
                <div class="stat-val" style="color: var(--primary);">{summary.total}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Passed</div>
                <div class="stat-val" style="color: var(--pass-text);">{summary.passed}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Failed</div>
                <div class="stat-val" style="color: var(--fail-text);">{summary.failed}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Skipped</div>
                <div class="stat-val" style="color: var(--skip-text);">{summary.skipped}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Pass Percentage</div>
                <div class="stat-val" style="color: var(--accent);">{summary.pass_percentage:.1f}%</div>
            </div>
        </div>

        <div class="meta-grid">
            <div><strong>Application:</strong> EmpMonitor</div>
            <div><strong>Environment:</strong> {html.escape(summary.environment)}</div>
            <div><strong>Browser:</strong> {html.escape(summary.browser)}</div>
            <div><strong>Base URL:</strong> <code>{html.escape(summary.base_url)}</code></div>
            <div><strong>Execution Date/Time:</strong> {html.escape(summary.timestamp)}</div>
            <div><strong>Overall Verdict:</strong> {HTMLReportGenerator._overall_badge(summary.overall_status)}</div>
        </div>

        <section class="section">
            <h2>📋 Executed Test Cases</h2>
            <div class="table-card">
                <table>
                    <thead>
                        <tr>
                            <th>TC ID</th>
                            <th>Module</th>
                            <th>Test Case</th>
                            <th>Test Data</th>
                            <th>Expected Result</th>
                            <th>Actual Result</th>
                            <th class="text-center">Status</th>
                            <th class="text-right">Duration</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(rows_html)}
                    </tbody>
                </table>
            </div>
        </section>

        {failed_section}
    </div>
</body>
</html>
"""
