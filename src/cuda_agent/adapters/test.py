from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .process import CmdResult, run_cmd, run_cmd_live


@dataclass(frozen=True)
class TestResult:
    ran: bool
    reason: str | None
    result: CmdResult | None


def _resolve_workspace(cfg: Mapping[str, Any], *, config_path: str | Path | None) -> Path:
    project = cfg.get("project", {})
    workspace_raw = project.get("workspace", ".")
    ws = Path(workspace_raw)

    if ws.is_absolute():
        return ws

    base = Path(config_path).resolve().parent if config_path is not None else Path.cwd()
    return (base / ws).resolve()


def run_tests(
    cfg: Mapping[str, Any],
    *,
    config_path: str | Path | None = None,
    live: bool = False,
) -> TestResult:
    """
    Run test.cmd if test.enabled is true.
    If disabled, return ran=False + reason, and result=None.
    """
    test_cfg = cfg.get("test", {})
    if not isinstance(test_cfg, dict):
        return TestResult(ran=False, reason="missing test config", result=None)

    enabled = bool(test_cfg.get("enabled", False))
    if not enabled:
        return TestResult(ran=False, reason="test.enabled=false", result=None)

    cmd = test_cfg.get("cmd", [])
    if not isinstance(cmd, list) or not cmd or not all(isinstance(x, str) and x for x in cmd):
        raise ValueError("test.cmd must be a non-empty list[str] when test.enabled=true")

    runner = run_cmd_live if live else run_cmd

    workspace = _resolve_workspace(cfg, config_path=config_path)
    env = cfg.get("env")
    env_map = env if isinstance(env, dict) else None

    res = runner(cmd, cwd=workspace, env=env_map)
    return TestResult(ran=True, reason=None, result=res)