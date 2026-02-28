from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import yaml

from cuda_agent.pipeline.baseline import execute_baseline_run
from cuda_agent.storage.index import list_runs, resolve_db_path


def test_execute_baseline_run_supports_run_cmd_and_writes_artifacts(tmp_path: Path) -> None:
    config_path = tmp_path / "agent.yaml"
    cfg = {
        "version": 1,
        "project": {
            "workspace": ".",
        },
        "build": {
            "configure_cmd": [sys.executable, "-c", "print('configure-ok')"],
            "build_cmd": [sys.executable, "-c", "print('build-ok')"],
        },
        "test": {
            "enabled": True,
            "cmd": [sys.executable, "-c", "print('test-ok')"],
        },
        "storage": {
            "root": "./runs",
        },
        "policy": {
            "min_pass_rate": 1.0,
        },
        "targets": {
            "smoke": {
                "run": {
                    "cmd": [
                        sys.executable,
                        "-c",
                        "print('STATUS: PASS'); print('TIME_MS: 12.5')",
                    ],
                    "runs": 2,
                    "warmup_runs": 1,
                },
                "parse": {
                    "kind": "regex",
                    "rules": [
                        {
                            "name": "status",
                            "pattern": r"STATUS:\s*(PASS|FAIL)",
                            "type": "enum",
                            "enum": ["PASS", "FAIL"],
                            "required": True,
                        },
                        {
                            "name": "time_ms",
                            "pattern": r"TIME_MS:\s*([0-9.]+)",
                            "type": "float",
                            "units": "ms",
                            "required": True,
                        },
                    ],
                },
                "success": {
                    "exit_code": 0,
                    "pass_rule": "status",
                },
            }
        },
    }
    config_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    exit_code = execute_baseline_run(cfg, target="smoke", config_path=str(config_path), live=False)

    assert exit_code == 0

    runs_root = tmp_path / "runs"
    run_dirs = [path for path in runs_root.iterdir() if path.is_dir()]
    assert len(run_dirs) == 1

    run_dir = run_dirs[0]
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    env = json.loads((run_dir / "env.json").read_text(encoding="utf-8"))
    report = (run_dir / "report.md").read_text(encoding="utf-8")

    assert summary["summary"]["status"] == "PASS"
    assert summary["summary"]["total_runs"] == 2
    assert summary["summary"]["warmup_runs"] == 1
    assert summary["launch_cmd"][0] == sys.executable
    assert env["launch_cmd"][0] == sys.executable
    assert summary["aggregates"]["numeric"]["time_ms"]["units"] == "ms"
    assert "launch" in report
    assert (run_dir / "bench" / "warmup_001.stdout.txt").exists()
    assert (run_dir / "bench" / "run_001.metrics.json").exists()
    db_path = tmp_path / "runs" / "runs.db"
    assert db_path.exists()
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT status, target_id FROM runs WHERE run_id = ?", (summary["run_id"],)).fetchone()
    assert row == ("PASS", "smoke")


def test_runs_cli_lists_indexed_runs(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "agent.yaml"
    cfg = {
        "version": 1,
        "project": {
            "name": "smoke-project",
            "workspace": ".",
        },
        "build": {
            "configure_cmd": [sys.executable, "-c", "print('configure-ok')"],
            "build_cmd": [sys.executable, "-c", "print('build-ok')"],
        },
        "storage": {
            "root": "./runs",
        },
        "targets": {
            "smoke": {
                "run": {
                    "cmd": [sys.executable, "-c", "print('STATUS: PASS')"],
                },
                "parse": {
                    "kind": "regex",
                    "rules": [
                        {
                            "name": "status",
                            "pattern": r"STATUS:\s*(PASS|FAIL)",
                            "type": "enum",
                            "enum": ["PASS", "FAIL"],
                            "required": True,
                        }
                    ],
                },
                "success": {
                    "pass_rule": "status",
                },
            }
        },
    }
    config_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    from cuda_agent.cli.main import main

    assert execute_baseline_run(cfg, target="smoke", config_path=str(config_path), live=False) == 0
    capsys.readouterr()

    exit_code = main(["--config", str(config_path), "runs", "--limit", "5"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "smoke-project" in captured.out
    assert "smoke" in captured.out


def test_runs_cli_filters_by_target_and_status(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "agent.yaml"
    cfg = {
        "version": 1,
        "project": {
            "name": "filter-project",
            "workspace": ".",
        },
        "build": {
            "configure_cmd": [sys.executable, "-c", "print('configure-ok')"],
            "build_cmd": [sys.executable, "-c", "print('build-ok')"],
        },
        "storage": {
            "root": "./runs",
        },
        "targets": {
            "matrixMul": {
                "run": {
                    "cmd": [sys.executable, "-c", "print('STATUS: PASS')"],
                },
                "parse": {
                    "kind": "regex",
                    "rules": [
                        {
                            "name": "status",
                            "pattern": r"STATUS:\s*(PASS|FAIL)",
                            "type": "enum",
                            "enum": ["PASS", "FAIL"],
                            "required": True,
                        }
                    ],
                },
                "success": {
                    "pass_rule": "status",
                },
            },
            "deviceQuery": {
                "run": {
                    "cmd": [sys.executable, "-c", "print('STATUS: FAIL')"],
                },
                "parse": {
                    "kind": "regex",
                    "rules": [
                        {
                            "name": "status",
                            "pattern": r"STATUS:\s*(PASS|FAIL)",
                            "type": "enum",
                            "enum": ["PASS", "FAIL"],
                            "required": True,
                        }
                    ],
                },
                "success": {
                    "pass_rule": "status",
                },
            },
        },
    }
    config_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    from cuda_agent.cli.main import main

    assert execute_baseline_run(cfg, target="matrixMul", config_path=str(config_path), live=False) == 0
    capsys.readouterr()
    assert execute_baseline_run(cfg, target="deviceQuery", config_path=str(config_path), live=False) == 1
    capsys.readouterr()

    exit_code = main(["--config", str(config_path), "runs", "--target", "matrixMul", "--status", "pass"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "matrixMul" in captured.out
    assert "PASS" in captured.out
    assert "deviceQuery" not in captured.out
    assert "FAIL" not in captured.out


def test_runs_cli_target_filter_is_case_insensitive(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "agent.yaml"
    cfg = {
        "version": 1,
        "project": {
            "name": "case-project",
            "workspace": ".",
        },
        "build": {
            "configure_cmd": [sys.executable, "-c", "print('configure-ok')"],
            "build_cmd": [sys.executable, "-c", "print('build-ok')"],
        },
        "storage": {
            "root": "./runs",
        },
        "targets": {
            "matrixMul": {
                "run": {
                    "cmd": [sys.executable, "-c", "print('STATUS: PASS')"],
                },
                "parse": {
                    "kind": "regex",
                    "rules": [
                        {
                            "name": "status",
                            "pattern": r"STATUS:\s*(PASS|FAIL)",
                            "type": "enum",
                            "enum": ["PASS", "FAIL"],
                            "required": True,
                        }
                    ],
                },
                "success": {
                    "pass_rule": "status",
                },
            }
        },
    }
    config_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    db_path = resolve_db_path(cfg, config_path=str(config_path))
    from cuda_agent.storage.index import IndexedRun, upsert_run

    upsert_run(
        db_path,
        IndexedRun(
            run_id="legacy-run",
            project_name="case-project",
            target_id="MatrixMul",
            status="FAIL",
            stage="RUN",
            started_at="2026-02-28T00:00:00",
            finished_at="2026-02-28T00:00:01",
            launch=None,
            run_dir=str(tmp_path / "runs" / "legacy-run"),
            summary_path=None,
            report_path=None,
            live=False,
            message="legacy casing",
        ),
    )

    from cuda_agent.cli.main import main

    exit_code = main(["--config", str(config_path), "runs", "--target", "matrixMul", "--status", "FAIL"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "MatrixMul" in captured.out
    assert "FAIL" in captured.out


def test_compare_cli_reads_indexed_summaries(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "agent.yaml"
    cfg = {
        "version": 1,
        "project": {
            "name": "compare-project",
            "workspace": ".",
        },
        "build": {
            "configure_cmd": [sys.executable, "-c", "print('configure-ok')"],
            "build_cmd": [sys.executable, "-c", "print('build-ok')"],
        },
        "storage": {
            "root": "./runs",
        },
        "targets": {
            "bench": {
                "run": {
                    "cmd": [
                        sys.executable,
                        "-c",
                        "print('STATUS: PASS'); print('TIME_MS: 10.0'); print('OPS_PER_SEC: 100.0')",
                    ],
                },
                "parse": {
                    "kind": "regex",
                    "rules": [
                        {
                            "name": "status",
                            "pattern": r"STATUS:\s*(PASS|FAIL)",
                            "type": "enum",
                            "enum": ["PASS", "FAIL"],
                            "required": True,
                        },
                        {
                            "name": "time_ms",
                            "pattern": r"TIME_MS:\s*([0-9.]+)",
                            "type": "float",
                            "units": "ms",
                            "required": True,
                        },
                        {
                            "name": "ops_per_sec",
                            "pattern": r"OPS_PER_SEC:\s*([0-9.]+)",
                            "type": "float",
                            "units": "ops_per_sec",
                            "better": "higher",
                            "required": True,
                        },
                    ],
                },
                "success": {
                    "pass_rule": "status",
                },
            }
        },
    }
    config_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    from cuda_agent.cli.main import main

    assert execute_baseline_run(cfg, target="bench", config_path=str(config_path), live=False) == 0

    cfg["targets"]["bench"]["run"]["cmd"] = [
        sys.executable,
        "-c",
        "print('STATUS: PASS'); print('TIME_MS: 12.5'); print('OPS_PER_SEC: 120.0')",
    ]
    config_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    assert execute_baseline_run(cfg, target="bench", config_path=str(config_path), live=False) == 0
    capsys.readouterr()

    runs = list_runs(resolve_db_path(cfg, config_path=str(config_path)), limit=5)
    assert len(runs) == 2
    baseline_run = runs[1]
    candidate_run = runs[0]

    exit_code = main(["--config", str(config_path), "compare", baseline_run.run_id, candidate_run.run_id])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "# CUDA Agent Compare" in captured.out
    assert baseline_run.run_id in captured.out
    assert candidate_run.run_id in captured.out
    assert "time_ms (ms)" in captured.out
    assert "ops_per_sec (ops_per_sec)" in captured.out
    assert "regression" in captured.out
    assert "improvement" in captured.out
    assert "12.5" in captured.out


def test_report_cli_prints_indexed_report(tmp_path: Path, capsys) -> None:
    config_path = tmp_path / "agent.yaml"
    cfg = {
        "version": 1,
        "project": {
            "name": "report-project",
            "workspace": ".",
        },
        "build": {
            "configure_cmd": [sys.executable, "-c", "print('configure-ok')"],
            "build_cmd": [sys.executable, "-c", "print('build-ok')"],
        },
        "storage": {
            "root": "./runs",
        },
        "targets": {
            "smoke": {
                "run": {
                    "cmd": [sys.executable, "-c", "print('STATUS: PASS')"],
                },
                "parse": {
                    "kind": "regex",
                    "rules": [
                        {
                            "name": "status",
                            "pattern": r"STATUS:\s*(PASS|FAIL)",
                            "type": "enum",
                            "enum": ["PASS", "FAIL"],
                            "required": True,
                        }
                    ],
                },
                "success": {
                    "pass_rule": "status",
                },
            }
        },
    }
    config_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    from cuda_agent.cli.main import main

    assert execute_baseline_run(cfg, target="smoke", config_path=str(config_path), live=False) == 0
    capsys.readouterr()

    runs = list_runs(resolve_db_path(cfg, config_path=str(config_path)), limit=5)
    assert len(runs) == 1

    exit_code = main(["--config", str(config_path), "report", runs[0].run_id])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "# CUDA Agent Report" in captured.out
    assert runs[0].run_id in captured.out
