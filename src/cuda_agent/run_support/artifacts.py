from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from cuda_agent.adapters.process import CmdResult


@dataclass(frozen=True)
class RunLayout:
    run_id: str
    run_dir: Path
    bench_dir: Path
    build_log_path: Path
    test_log_path: Path
    config_snapshot_path: Path
    env_path: Path
    summary_path: Path
    report_path: Path


def resolve_storage_root(cfg: Mapping[str, Any], *, config_path: str) -> Path:
    storage = cfg.get("storage", {})
    root_raw = storage.get("root", "./runs") if isinstance(storage, dict) else "./runs"
    base = Path(config_path).resolve().parent
    root = (base / root_raw).resolve() if not Path(root_raw).is_absolute() else Path(root_raw).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def make_run_layout(storage_root: Path) -> RunLayout:
    for _ in range(10):
        run_id = str(uuid.uuid4())
        run_dir = storage_root / run_id
        try:
            run_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            continue

        bench_dir = run_dir / "bench"
        bench_dir.mkdir(parents=True, exist_ok=True)
        return RunLayout(
            run_id=run_id,
            run_dir=run_dir,
            bench_dir=bench_dir,
            build_log_path=run_dir / "build.log",
            test_log_path=run_dir / "test.log",
            config_snapshot_path=run_dir / "config_snapshot.yaml",
            env_path=run_dir / "env.json",
            summary_path=run_dir / "summary.json",
            report_path=run_dir / "report.md",
        )

    raise RuntimeError("Failed to create a unique run directory (uuid collision?)")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def write_config_snapshot(path: Path, cfg: Mapping[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(dict(cfg), handle, sort_keys=False)


def format_cmd_result_block(title: str, result: CmdResult) -> str:
    cmd = json.dumps(list(result.cmd))
    parts = [
        f"=== {title} ===",
        f"cmd: {cmd}",
        f"cwd: {result.cwd}",
        f"exit_code: {result.exit_code}",
        f"duration_ms: {result.duration_ms}",
        "",
        "--- stdout ---",
        result.stdout.rstrip(),
        "",
        "--- stderr ---",
        result.stderr.rstrip(),
        "",
    ]
    return "\n".join(parts)
