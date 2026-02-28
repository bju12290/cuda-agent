from __future__ import annotations

import datetime
import sys
from pathlib import Path
from typing import Any, Mapping

from cuda_agent.adapters.build import configure_and_build
from cuda_agent.adapters.targets import run_target
from cuda_agent.adapters.test import run_tests
from cuda_agent.run_support.artifacts import (
    RunLayout,
    format_cmd_result_block,
    make_run_layout,
    resolve_storage_root,
    write_config_snapshot,
    write_text,
)
from cuda_agent.run_support.environment import write_env_json
from cuda_agent.run_support.reporting import write_report_md
from cuda_agent.run_support.summary import count_bad_runs, expected_exit_code, summarize_run
from cuda_agent.storage.index import IndexedRun, resolve_db_path, upsert_run


def _write_failure_report(
    *,
    layout: RunLayout,
    ts_iso: str,
    target: str,
    live: bool,
    launch: str | None,
    stage: str,
    message: str,
    summary_path: Path | None = None,
    summary_obj: Mapping[str, Any] | None = None,
) -> None:
    write_report_md(
        layout.report_path,
        run_dir=layout.run_dir,
        run_id=layout.run_id,
        ts_iso=ts_iso,
        target=target,
        live=live,
        launch=launch,
        stage=stage,
        stage_status="FAIL",
        message=message,
        build_log_path=layout.build_log_path,
        test_log_path=layout.test_log_path,
        config_snapshot_path=layout.config_snapshot_path,
        env_path=layout.env_path,
        bench_dir=layout.bench_dir,
        summary_path=summary_path,
        summary_obj=summary_obj,
    )


def _index_run(
    cfg: Mapping[str, Any],
    *,
    config_path: str,
    run_id: str,
    target: str,
    status: str,
    stage: str,
    started_at: str,
    finished_at: str,
    launch: str | None,
    run_dir: Path,
    summary_path: Path | None,
    report_path: Path | None,
    live: bool,
    message: str | None,
) -> None:
    project = cfg.get("project", {})
    project_name = project.get("name") if isinstance(project, dict) else None
    if project_name is not None and not isinstance(project_name, str):
        project_name = str(project_name)

    try:
        db_path = resolve_db_path(cfg, config_path=config_path)
        upsert_run(
            db_path,
            IndexedRun(
                run_id=run_id,
                project_name=project_name,
                target_id=target,
                status=status,
                stage=stage,
                started_at=started_at,
                finished_at=finished_at,
                launch=launch,
                run_dir=str(run_dir),
                summary_path=str(summary_path) if summary_path is not None else None,
                report_path=str(report_path) if report_path is not None else None,
                live=live,
                message=message,
            ),
        )
    except Exception as exc:
        print(f"Run index warning: {exc}", file=sys.stderr)


def execute_baseline_run(
    cfg: Mapping[str, Any],
    *,
    target: str,
    config_path: str,
    live: bool,
) -> int:
    started_at = datetime.datetime.now().isoformat(timespec="seconds")
    layout = make_run_layout(resolve_storage_root(cfg, config_path=config_path))

    print(f"Run dir: {layout.run_dir}")
    if not live:
        print("Running pipeline (build -> test -> benchmark)... this may take time. Use '--live' to stream output.")

    write_config_snapshot(layout.config_snapshot_path, cfg)
    write_env_json(
        layout.env_path,
        cfg,
        ts_iso=started_at,
        run_id=layout.run_id,
        target=target,
        live=live,
        config_path=config_path,
        launch=None,
        launch_cmd=None,
    )

    build_result = configure_and_build(cfg, config_path=config_path, live=live)
    build_log_parts = [f"run_id: {layout.run_id}", f"timestamp: {started_at}", ""]
    build_log_parts.append(format_cmd_result_block("configure", build_result.configure))
    if build_result.build is None:
        build_log_parts.append("=== build ===\nSKIPPED (configure failed)\n")
    else:
        build_log_parts.append(format_cmd_result_block("build", build_result.build))
    write_text(layout.build_log_path, "\n".join(build_log_parts))

    if build_result.configure.exit_code != 0:
        finished_at = datetime.datetime.now().isoformat(timespec="seconds")
        write_text(layout.test_log_path, f"run_id: {layout.run_id}\ntimestamp: {started_at}\n\nSKIPPED (configure failed)\n")
        print(f"CONFIGURE FAILED - see {layout.build_log_path}", file=sys.stderr)
        _write_failure_report(
            layout=layout,
            ts_iso=started_at,
            target=target,
            live=live,
            launch=None,
            stage="BUILD",
            message="Configure failed. See build.log.",
        )
        _index_run(
            cfg,
            config_path=config_path,
            run_id=layout.run_id,
            target=target,
            status="FAIL",
            stage="BUILD",
            started_at=started_at,
            finished_at=finished_at,
            launch=None,
            run_dir=layout.run_dir,
            summary_path=None,
            report_path=layout.report_path,
            live=live,
            message="Configure failed. See build.log.",
        )
        return build_result.configure.exit_code or 1

    if build_result.build is None or build_result.build.exit_code != 0:
        finished_at = datetime.datetime.now().isoformat(timespec="seconds")
        write_text(layout.test_log_path, f"run_id: {layout.run_id}\ntimestamp: {started_at}\n\nSKIPPED (build failed)\n")
        print(f"BUILD FAILED - see {layout.build_log_path}", file=sys.stderr)
        _write_failure_report(
            layout=layout,
            ts_iso=started_at,
            target=target,
            live=live,
            launch=None,
            stage="BUILD",
            message="Build failed. See build.log.",
        )
        _index_run(
            cfg,
            config_path=config_path,
            run_id=layout.run_id,
            target=target,
            status="FAIL",
            stage="BUILD",
            started_at=started_at,
            finished_at=finished_at,
            launch=None,
            run_dir=layout.run_dir,
            summary_path=None,
            report_path=layout.report_path,
            live=live,
            message="Build failed. See build.log.",
        )
        return (build_result.build.exit_code if build_result.build else 1) or 1

    test_result = run_tests(cfg, config_path=config_path, live=live)
    if not test_result.ran:
        write_text(layout.test_log_path, f"run_id: {layout.run_id}\ntimestamp: {started_at}\n\nSKIPPED ({test_result.reason})\n")
    else:
        assert test_result.result is not None
        write_text(
            layout.test_log_path,
            "\n".join(
                [
                    f"run_id: {layout.run_id}",
                    f"timestamp: {started_at}",
                    "",
                    format_cmd_result_block("test", test_result.result),
                ]
            ),
        )
        if test_result.result.exit_code != 0:
            finished_at = datetime.datetime.now().isoformat(timespec="seconds")
            print(f"TEST FAILED - see {layout.test_log_path}", file=sys.stderr)
            _write_failure_report(
                layout=layout,
                ts_iso=started_at,
                target=target,
                live=live,
                launch=None,
                stage="TEST",
                message="Tests failed. See test.log.",
            )
            _index_run(
                cfg,
                config_path=config_path,
                run_id=layout.run_id,
                target=target,
                status="FAIL",
                stage="TEST",
                started_at=started_at,
                finished_at=finished_at,
                launch=None,
                run_dir=layout.run_dir,
                summary_path=None,
                report_path=layout.report_path,
                live=live,
                message="Tests failed. See test.log.",
            )
            return test_result.result.exit_code or 1

    try:
        run_result = run_target(cfg, target, config_path=config_path, live=live)
    except RuntimeError as exc:
        finished_at = datetime.datetime.now().isoformat(timespec="seconds")
        message = f"Run error: {exc}"
        print(message, file=sys.stderr)
        _write_failure_report(
            layout=layout,
            ts_iso=started_at,
            target=target,
            live=live,
            launch=None,
            stage="RUN",
            message=message,
        )
        _index_run(
            cfg,
            config_path=config_path,
            run_id=layout.run_id,
            target=target,
            status="FAIL",
            stage="RUN",
            started_at=started_at,
            finished_at=finished_at,
            launch=None,
            run_dir=layout.run_dir,
            summary_path=None,
            report_path=layout.report_path,
            live=live,
            message=message,
        )
        return 2

    launch = run_result.launch_label
    write_env_json(
        layout.env_path,
        cfg,
        ts_iso=started_at,
        run_id=layout.run_id,
        target=target,
        live=live,
        config_path=config_path,
        launch=launch,
        launch_cmd=list(run_result.launch_cmd),
    )

    expected = expected_exit_code(cfg, target)
    bad_run_count = count_bad_runs(run_result, expected_exit_code=expected)
    if bad_run_count:
        print(f"RUN FAILED (expected exit={expected})", file=sys.stderr)
        print(f"launch={run_result.launch_label}", file=sys.stderr)
        print(f"bad_runs={bad_run_count}/{len(run_result.runs)}", file=sys.stderr)
        if not live and run_result.runs:
            last_bad = next(result for result in reversed(run_result.runs) if result.exit_code != expected)
            if (last_bad.stdout or "").strip():
                print("\n--- stdout ---\n" + last_bad.stdout, file=sys.stderr)
            if (last_bad.stderr or "").strip():
                print("\n--- stderr ---\n" + last_bad.stderr, file=sys.stderr)
        else:
            print("(Output was streamed live above.)", file=sys.stderr)

    if not bad_run_count:
        print(f"OK (launch={launch}, runs={len(run_result.runs)}, warmups={len(run_result.warmups)})")
    else:
        print(f"DONE with failures (launch={launch}, runs={len(run_result.runs)}, warmups={len(run_result.warmups)})", file=sys.stderr)

    if not live and run_result.runs:
        last = run_result.runs[-1]
        if last.stdout.strip():
            print("\n--- stdout ---\n" + last.stdout)
        if last.stderr.strip():
            print("\n--- stderr ---\n" + last.stderr)

    try:
        summary = summarize_run(
            cfg,
            target=target,
            run_id=layout.run_id,
            ts_iso=started_at,
            launch=launch,
            launch_cmd=list(run_result.launch_cmd),
            run_result=run_result,
            bench_dir=layout.bench_dir,
            summary_path=layout.summary_path,
        )
    except Exception as exc:
        finished_at = datetime.datetime.now().isoformat(timespec="seconds")
        message = f"Summary/write error: {exc}"
        print(message, file=sys.stderr)
        _write_failure_report(
            layout=layout,
            ts_iso=started_at,
            target=target,
            live=live,
            launch=launch,
            stage="PARSE",
            message=message,
            summary_path=layout.summary_path,
            summary_obj=None,
        )
        _index_run(
            cfg,
            config_path=config_path,
            run_id=layout.run_id,
            target=target,
            status="FAIL",
            stage="PARSE",
            started_at=started_at,
            finished_at=finished_at,
            launch=launch,
            run_dir=layout.run_dir,
            summary_path=layout.summary_path,
            report_path=layout.report_path,
            live=live,
            message=message,
        )
        return 2

    status = str(summary["summary"]["status"])
    pass_rate = float(summary["summary"]["pass_rate"])
    print(f"Summary: {status} (pass_rate={pass_rate:.0%})")
    print(f"Run dir: {layout.summary_path.parent}")
    print(f"Summary written: {layout.summary_path}")

    write_report_md(
        layout.report_path,
        run_dir=layout.run_dir,
        run_id=layout.run_id,
        ts_iso=started_at,
        target=target,
        live=live,
        launch=launch,
        stage="DONE",
        stage_status="OK",
        message=None,
        build_log_path=layout.build_log_path,
        test_log_path=layout.test_log_path,
        config_snapshot_path=layout.config_snapshot_path,
        env_path=layout.env_path,
        bench_dir=layout.bench_dir,
        summary_path=layout.summary_path,
        summary_obj=summary,
    )
    print(f"Report written: {layout.report_path}")
    _index_run(
        cfg,
        config_path=config_path,
        run_id=layout.run_id,
        target=target,
        status=status,
        stage="DONE",
        started_at=started_at,
        finished_at=datetime.datetime.now().isoformat(timespec="seconds"),
        launch=launch,
        run_dir=layout.run_dir,
        summary_path=layout.summary_path,
        report_path=layout.report_path,
        live=live,
        message=None,
    )
    return 0 if status == "PASS" else 1
