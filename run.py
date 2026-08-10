"""Command-line entry point for the EmpMonitor Automation Framework.

Starts the framework, executes any registered plugins, and writes the run report.
Contains no validation logic and no feature knowledge: it parses arguments,
delegates to :mod:`framework.core.orchestrator`, and maps the outcome to a
process exit code.

Usage::

    python run.py                      # run against the default environment
    python run.py --environment local  # select an environment overlay
    python run.py --check              # verify the framework starts, then exit
    python run.py --plugin EM001_Login # run a specific plugin only

Exit codes follow the verdict model, so a scheduler or CI job can act on the
outcome without parsing the report:

====  ==========================================================
0     ``HEALTHY`` or ``DEGRADED`` -- the run reached a positive conclusion
1     ``FAILED`` -- a divergence was localised
2     ``INCONCLUSIVE`` -- insufficient evidence; explicitly not a pass
3     ``BLOCKED`` -- preconditions not met; validation did not run
4     The framework itself failed to start or complete
====  ==========================================================

``INCONCLUSIVE`` gets its own non-zero code deliberately: collapsing it into
success would be the exact anti-pattern the Validation Standard forbids.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from framework.core.orchestrator import Orchestrator, bootstrap
from framework.core.reporting import Report
from framework.shared.constants import FRAMEWORK_NAME, FRAMEWORK_VERSION
from framework.shared.exceptions import FrameworkError
from framework.shared.logger import get_logger
from framework.shared.models import Verdict
from framework.shared.utils import json_utils

_LOGGER = get_logger(__name__)

_EXIT_CODES = {
    Verdict.HEALTHY: 0,
    Verdict.DEGRADED: 0,
    Verdict.FAILED: 1,
    Verdict.INCONCLUSIVE: 2,
    Verdict.BLOCKED: 3,
}
_EXIT_FRAMEWORK_ERROR = 4


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser.

    Returns:
        The configured parser.
    """
    parser = argparse.ArgumentParser(
        prog="run.py",
        description=f"{FRAMEWORK_NAME} (v{FRAMEWORK_VERSION})",
    )
    parser.add_argument(
        "--environment",
        "-e",
        default=None,
        help="Environment overlay to load (default: EMPAF_ENVIRONMENT or 'local').",
    )
    parser.add_argument(
        "--config-dir",
        default=None,
        type=Path,
        help="Override the configuration directory.",
    )
    parser.add_argument(
        "--plugin",
        "-p",
        action="append",
        dest="plugins",
        default=None,
        metavar="PLUGIN_ID",
        help="Run only this plugin; repeatable. Default: all enabled plugins.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the framework starts and its configuration is valid, then exit.",
    )
    parser.add_argument(
        "--no-report-file",
        action="store_true",
        help="Do not write the report to disk (it is still summarised on stdout).",
    )
    return parser


def _write_report(report: Report, destination: Path) -> Path:
    """Serialise the report to disk.

    Args:
        report: Report to write.
        destination: Directory to write into.

    Returns:
        The written file path.
    """
    target = destination / "report.json"
    return json_utils.write_json_file(target, report.to_dict())


def _print_summary(report: Report) -> None:
    """Print a concise run summary to stdout.

    Reports verdict *and* confidence together, as the Validation Standard
    requires, and calls out unanswered questions rather than letting a run with
    inconclusive findings read as clean.

    Args:
        report: Report to summarise.
    """
    summary = report.summary
    print()
    print(f"Verdict:     {summary.overall_verdict.value}")
    print(f"Confidence:  {summary.lowest_confidence.name}")
    print(f"Findings:    {summary.total_findings}")
    if summary.total_findings:
        print(
            f"  healthy={summary.healthy} degraded={summary.degraded} "
            f"failed={summary.failed} inconclusive={summary.inconclusive} "
            f"blocked={summary.blocked}"
        )
    if summary.layers_covered:
        print(
            "Layers:      "
            + ", ".join(layer.label for layer in summary.layers_covered)
        )
    if summary.has_unanswered_questions:
        print(
            "Note:        this run left unanswered questions "
            "(inconclusive or blocked findings)."
        )


def main(argv: list[str] | None = None) -> int:
    """Run the framework.

    Args:
        argv: Argument list; defaults to :data:`sys.argv`.

    Returns:
        A process exit code, per this module's exit-code table.
    """
    args = build_parser().parse_args(argv)

    try:
        booted = bootstrap(config_dir=args.config_dir, environment=args.environment)
    except FrameworkError as exc:
        print(f"Framework failed to start: {exc}", file=sys.stderr)
        return _EXIT_FRAMEWORK_ERROR

    if args.check:
        configuration = booted.context.configuration
        print(f"{FRAMEWORK_NAME} v{FRAMEWORK_VERSION}")
        print(f"Environment:      {configuration.environment}")
        print(f"Config sources:   {[str(path) for path in configuration.sources] or 'none'}")
        print(f"Evidence sources: {len(booted.evidence_store.catalog)} registered")
        print(f"Plugins:          {len(booted.registry)} registered")
        print(f"Output root:      {booted.context.resolve_output_root()}")
        print("Framework started successfully.")
        return 0

    try:
        report = Orchestrator.from_bootstrap(booted).run(args.plugins)
    except FrameworkError as exc:
        _LOGGER.critical("Run failed: %s", exc, exc_info=True)
        print(f"Run failed: {exc}", file=sys.stderr)
        return _EXIT_FRAMEWORK_ERROR

    if not args.no_report_file:
        try:
            written = _write_report(report, booted.context.resolve_output_root())
            print(f"Report:      {written}")
        except FrameworkError as exc:
            # A report that cannot be written must not silently vanish, but the
            # run's verdict still stands and is reported below.
            _LOGGER.error("Report could not be written: %s", exc)
            print(f"Report could not be written: {exc}", file=sys.stderr)

    _print_summary(report)
    return _EXIT_CODES.get(report.summary.overall_verdict, _EXIT_FRAMEWORK_ERROR)


if __name__ == "__main__":
    sys.exit(main())
