from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
import glob

from .process import CmdResult, run_cmd, run_cmd_live


@dataclass(frozen=True)
class RunResult:
    target_id: str
    launch_cmd: tuple[str, ...]
    launch_cwd: Path
    launch_label: str
    executable_path: Path | None
    warmups: list[CmdResult]
    runs: list[CmdResult]


def _resolve_workspace(cfg: Mapping[str, Any], *, config_path: str | Path | None) -> Path:
    project = cfg.get("project", {})
    workspace_raw = project.get("workspace", ".")
    ws = Path(workspace_raw)

    if ws.is_absolute():
        return ws

    base = Path(config_path).resolve().parent if config_path is not None else Path.cwd()
    return (base / ws).resolve()


def _has_glob_chars(s: str) -> bool:
    return any(ch in s for ch in ["*", "?", "["])


def _find_executable(workspace: Path, exe_glob: str) -> Path:
    """
    exe_glob rules:
      - if exe_glob has no glob chars, treat as a direct path (relative to workspace if relative)
      - otherwise treat as a glob (relative to workspace if relative)
      - if multiple matches: pick the newest modified
    """
    p = Path(exe_glob)

    # Direct path case (no wildcards)
    if not _has_glob_chars(exe_glob):
        candidate = (workspace / p) if not p.is_absolute() else p
        candidate = candidate.resolve()
        if not candidate.exists():
            raise RuntimeError(f"Executable not found: {candidate}")
        if candidate.is_dir():
            raise RuntimeError(f"Executable path points to a directory, not a file: {candidate}")
        return candidate

    # Glob case
    pattern = str(p) if p.is_absolute() else str(workspace / p)
    matches = [Path(m).resolve() for m in glob.glob(pattern, recursive=True)]
    matches = [m for m in matches if m.is_file()]

    if not matches:
        raise RuntimeError(f"No executable matched exe_glob: {exe_glob!r} (workspace={workspace})")

    # Pick newest
    matches.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return matches[0]


def _resolve_run_spec(target_id: str, run_cfg: Mapping[str, Any], workspace: Path) -> tuple[list[str], Path, str, Path | None]:
    exe_glob = run_cfg.get("exe_glob")
    cmd = run_cfg.get("cmd")

    has_exe_glob = isinstance(exe_glob, str) and bool(exe_glob.strip())
    has_cmd = isinstance(cmd, list) and bool(cmd)
    if has_exe_glob == has_cmd:
        raise RuntimeError(
            f"Target {target_id!r} run must define exactly one of run.exe_glob or run.cmd"
        )

    if has_exe_glob:
        exe_path = _find_executable(workspace, str(exe_glob))
        args = run_cfg.get("args", [])
        if not isinstance(args, list) or not all(isinstance(x, str) for x in args):
            raise RuntimeError(f"Target {target_id!r} run.args must be a list of strings")
        return [str(exe_path), *args], exe_path.parent, str(exe_path), exe_path

    assert isinstance(cmd, list)
    if not all(isinstance(x, str) and x for x in cmd):
        raise RuntimeError(f"Target {target_id!r} run.cmd must be a non-empty list of non-empty strings")
    if "args" in run_cfg:
        raise RuntimeError(f"Target {target_id!r} run.args is not allowed when run.cmd is used")
    return list(cmd), workspace, " ".join(cmd), None


def run_target(
    cfg: Mapping[str, Any],
    target_id: str,
    *,
    config_path: str | Path | None = None,
    live: bool = False,
) -> RunResult:
    workspace = _resolve_workspace(cfg, config_path=config_path)

    env = cfg.get("env")
    env_map = env if isinstance(env, dict) else None

    targets = cfg.get("targets")
    if not isinstance(targets, dict) or target_id not in targets or not isinstance(targets[target_id], dict):
        raise RuntimeError(f"Unknown target: {target_id!r}")

    tcfg = targets[target_id]
    run_cfg = tcfg.get("run")
    if not isinstance(run_cfg, dict):
        raise RuntimeError(f"Target {target_id!r} missing required section: run")

    runs = run_cfg.get("runs", 1)
    warmup_runs = run_cfg.get("warmup_runs", 0)
    if not isinstance(runs, int) or runs < 1:
        raise RuntimeError(f"Target {target_id!r} run.runs must be an int >= 1")
    if not isinstance(warmup_runs, int) or warmup_runs < 0:
        raise RuntimeError(f"Target {target_id!r} run.warmup_runs must be an int >= 0")

    cmd, cwd, launch_label, executable_path = _resolve_run_spec(target_id, run_cfg, workspace)

    runner = run_cmd_live if live else run_cmd

    warmups_res: list[CmdResult] = []
    runs_res: list[CmdResult] = []

    for _ in range(warmup_runs):
        warmups_res.append(runner(cmd, cwd=cwd, env=env_map))

    for _ in range(runs):
        runs_res.append(runner(cmd, cwd=cwd, env=env_map))

    return RunResult(
        target_id=target_id,
        launch_cmd=tuple(cmd),
        launch_cwd=cwd,
        launch_label=launch_label,
        executable_path=executable_path,
        warmups=warmups_res,
        runs=runs_res,
    )
