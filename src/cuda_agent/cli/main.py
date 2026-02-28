from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from cuda_agent.adapters.build import configure_and_build
from cuda_agent.config import load_config_resolved
from cuda_agent.config.errors import ConfigError
from cuda_agent.pipeline.baseline import execute_baseline_run
from cuda_agent.run_support.compare import load_summary, render_compare_text, resolve_report_path, resolve_summary_path
from cuda_agent.storage.index import get_run, list_runs, resolve_db_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cuda-agent", description="CUDA Agent (v1)")
    parser.add_argument(
        "--config",
        default="agent.yaml",
        help="Path to agent.yaml (default: agent.yaml)",
    )

    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate", help="Load + interpolate + validate config")
    sub.add_parser("list", help="List target IDs from config")
    runs = sub.add_parser("runs", help="List indexed runs from SQLite storage")
    runs.add_argument("--limit", type=int, default=20, help="Maximum number of runs to show (default: 20)")
    runs.add_argument("--target", help="Filter indexed runs by target id")
    runs.add_argument("--status", help="Filter indexed runs by status, for example PASS or FAIL")
    report = sub.add_parser("report", help="Print the stored Markdown report for an indexed run")
    report.add_argument("run_id", help="Indexed run id to print")
    compare = sub.add_parser("compare", help="Compare two indexed runs using stored summary.json files")
    compare.add_argument("run_id_a", help="Baseline run id")
    compare.add_argument("run_id_b", help="Candidate run id")

    show = sub.add_parser("show", help="Print resolved config as JSON")
    show.add_argument("--pretty", action="store_true", help="Pretty-print JSON")

    build = sub.add_parser("build", help="Run build.configure_cmd then build.build_cmd")
    build.add_argument(
        "--live",
        action="store_true",
        help="Stream build output live instead of capturing it",
    )

    run = sub.add_parser("run", help="Run a target executable defined in config")
    run.add_argument("target", help="Target id under targets")
    run.add_argument("--live", action="store_true", help="Stream target output live")
    return parser


def _handle_build(cfg: dict[str, object], *, config_path: str, live: bool) -> int:
    if not live:
        print("Running configure/build... this can take a few minutes. Use '--live' to stream output.")

    result = configure_and_build(cfg, config_path=config_path, live=live)
    if result.configure.exit_code != 0:
        print("CONFIGURE FAILED", file=sys.stderr)
        print(f"exit={result.configure.exit_code} ms={result.configure.duration_ms}", file=sys.stderr)
        if not live:
            if result.configure.stdout.strip():
                print("\n--- stdout ---\n" + result.configure.stdout, file=sys.stderr)
            if result.configure.stderr.strip():
                print("\n--- stderr ---\n" + result.configure.stderr, file=sys.stderr)
        else:
            print("(Output was streamed live above.)", file=sys.stderr)
        return result.configure.exit_code or 1

    if result.build is None:
        print("BUILD SKIPPED (configure failed)", file=sys.stderr)
        return 1

    if result.build.exit_code != 0:
        print("BUILD FAILED", file=sys.stderr)
        print(f"exit={result.build.exit_code} ms={result.build.duration_ms}", file=sys.stderr)
        if not live:
            if result.build.stdout.strip():
                print("\n--- stdout ---\n" + result.build.stdout, file=sys.stderr)
            if result.build.stderr.strip():
                print("\n--- stderr ---\n" + result.build.stderr, file=sys.stderr)
        else:
            print("(Output was streamed live above.)", file=sys.stderr)
        return result.build.exit_code or 1

    print(f"OK (configure {result.configure.duration_ms}ms, build {result.build.duration_ms}ms)")
    return 0


def _lookup_run(cfg: dict[str, object], *, config_path: str, run_id: str):
    return get_run(resolve_db_path(cfg, config_path=config_path), run_id)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        cfg = load_config_resolved(args.config)
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    if args.cmd == "validate":
        print("OK")
        return 0

    if args.cmd == "list":
        targets = cfg.get("targets", {})
        for target_id in targets.keys():
            print(target_id)
        return 0

    if args.cmd == "show":
        print(json.dumps(cfg, indent=2 if args.pretty else None))
        return 0

    if args.cmd == "runs":
        if args.limit < 1:
            print("Argument error: --limit must be >= 1", file=sys.stderr)
            return 2

        rows = list_runs(
            resolve_db_path(cfg, config_path=args.config),
            limit=args.limit,
            target_id=args.target,
            status=args.status,
        )
        if not rows:
            print("No indexed runs found.")
            return 0

        for row in rows:
            project = row.project_name or "-"
            launch = row.launch or "-"
            print(
                f"{row.finished_at}  {row.status:<4}  {row.target_id:<16}  {project:<20}  {row.run_id}  {launch}"
            )
        return 0

    if args.cmd == "report":
        row = _lookup_run(cfg, config_path=args.config, run_id=args.run_id)
        if row is None:
            print(f"Run not found in index: {args.run_id}", file=sys.stderr)
            return 2

        report_path = resolve_report_path(row)
        if not report_path.exists():
            print(f"Indexed report file not found: {report_path}", file=sys.stderr)
            return 2

        print(report_path.read_text(encoding="utf-8").rstrip())
        return 0

    if args.cmd == "compare":
        baseline_run = _lookup_run(cfg, config_path=args.config, run_id=args.run_id_a)
        candidate_run = _lookup_run(cfg, config_path=args.config, run_id=args.run_id_b)

        if baseline_run is None:
            print(f"Run not found in index: {args.run_id_a}", file=sys.stderr)
            return 2
        if candidate_run is None:
            print(f"Run not found in index: {args.run_id_b}", file=sys.stderr)
            return 2

        baseline_summary_path = resolve_summary_path(baseline_run)
        candidate_summary_path = resolve_summary_path(candidate_run)
        if not baseline_summary_path.exists():
            print(f"Indexed summary file not found: {baseline_summary_path}", file=sys.stderr)
            return 2
        if not candidate_summary_path.exists():
            print(f"Indexed summary file not found: {candidate_summary_path}", file=sys.stderr)
            return 2

        baseline_summary = load_summary(baseline_summary_path)
        candidate_summary = load_summary(candidate_summary_path)
        print(
            render_compare_text(
                baseline_run=baseline_run,
                baseline_summary=baseline_summary,
                candidate_run=candidate_run,
                candidate_summary=candidate_summary,
            ).rstrip()
        )
        return 0

    if args.cmd == "build":
        return _handle_build(cfg, config_path=args.config, live=args.live)

    if args.cmd == "run":
        return execute_baseline_run(
            cfg,
            target=args.target,
            config_path=args.config,
            live=args.live,
        )

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
