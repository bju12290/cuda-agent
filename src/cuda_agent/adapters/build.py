from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .process import CmdResult, run_cmd, run_cmd_live

@dataclass(frozen=True)
class BuildResult:
    configure: CmdResult
    build: CmdResult | None  # None if configure failed and we short-circuited

def _resolve_workspace(cfg: Mapping[str, Any], *, config_path: str | Path | None) -> Path:
    """
   Resolve project.workspace to an absolute path.

    Rule:
        - If workspace is absolute, use it.
        - If workspace is relative:
            - resolve relative to the directory containing the config file (if provided),
              otherwise relative to the current working directory.
    """
    project = cfg.get("project", {})
    workspace_raw = project.get("workspace", ".")
    ws = Path(workspace_raw)

    if ws.is_absolute():
        return ws

    if config_path is not None:
        base = Path(config_path).resolve().parent
    else:
        base = Path.cwd()

    return (base / ws).resolve()

def configure_and_build(
    cfg: Mapping[str, Any],
    *,
    config_path: str | Path | None = None,
    live: bool = False,
) -> BuildResult:
    """
    Run build.configure_cmd then build.build_cmd in the resolved workspace.

    Returns:
      BuildResult with both command results.
      If configure fails (exit_code != 0), build is not run and build=None.
    """

    runner = run_cmd_live if live else run_cmd

    workspace = _resolve_workspace(cfg, config_path=config_path)

    env = cfg.get("env")
    env_map = env if isinstance(env, dict) else None

    build_cfg = cfg.get("build", {})
    configure_cmd = build_cfg.get("configure_cmd")
    build_cmd = build_cfg.get("build_cmd")

    # (validate.py should already guarantee these are list[str], but keep a hard guard)
    if not isinstance(configure_cmd, list) or not all(isinstance(x, str) and x for x in configure_cmd):
        raise ValueError("build.configure_cmd must be a list of non-empty strings")
    if not isinstance(build_cmd, list) or not all(isinstance(x, str) and x for x in build_cmd):
        raise ValueError("build.build_cmd must be a list of non-empty strings")

    cfg_res = runner(configure_cmd, cwd=workspace, env=env_map)
    if cfg_res.exit_code != 0:
        return BuildResult(configure=cfg_res, build=None)

    bld_res = runner(build_cmd, cwd=workspace, env=env_map)
    return BuildResult(configure=cfg_res, build=bld_res)