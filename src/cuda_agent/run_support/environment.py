from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


def _try_cmd(cmd: Sequence[str], *, cwd: str | None = None, timeout_s: int = 10) -> dict[str, Any]:
    try:
        cp = subprocess.run(
            list(cmd),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        stdout = cp.stdout or ""
        stderr = cp.stderr or ""
        if len(stdout) > 20000:
            stdout = stdout[:20000] + "\n... <stdout truncated> ..."
        if len(stderr) > 20000:
            stderr = stderr[:20000] + "\n... <stderr truncated> ..."
        return {
            "cmd": list(cmd),
            "ok": cp.returncode == 0,
            "exit_code": cp.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
    except FileNotFoundError:
        return {"cmd": list(cmd), "ok": False, "error": "not found"}
    except Exception as exc:
        return {"cmd": list(cmd), "ok": False, "error": repr(exc)}


def _resolve_workspace(cfg: Mapping[str, Any], *, config_path: str) -> Path:
    base = Path(config_path).resolve().parent
    project = cfg.get("project", {}) if isinstance(cfg.get("project"), dict) else {}
    workspace_raw = project.get("workspace", ".")
    workspace = Path(workspace_raw)
    return (base / workspace).resolve() if not workspace.is_absolute() else workspace.resolve()


def write_env_json(
    path: Path,
    cfg: Mapping[str, Any],
    *,
    ts_iso: str,
    run_id: str,
    target: str,
    live: bool,
    config_path: str,
    launch: str | None,
    launch_cmd: list[str] | None,
) -> None:
    workspace = _resolve_workspace(cfg, config_path=config_path)
    env_cfg = cfg.get("env", {}) if isinstance(cfg.get("env"), dict) else {}

    whitelist = [
        "PATH",
        "CUDA_PATH",
        "CUDA_HOME",
        "CUDA_ROOT",
        "LD_LIBRARY_PATH",
        "DYLD_LIBRARY_PATH",
        "CC",
        "CXX",
        "CUDACXX",
        "NVCC",
    ]
    env_whitelist = {key: os.environ.get(key) for key in whitelist if os.environ.get(key) is not None}

    payload = {
        "timestamp": ts_iso,
        "run_id": run_id,
        "target": target,
        "live": bool(live),
        "launch": launch,
        "launch_cmd": launch_cmd,
        "config_path": str(Path(config_path).resolve()),
        "workspace": str(workspace),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        },
        "python": {
            "executable": sys.executable,
            "version": sys.version,
        },
        "env_from_config": env_cfg,
        "env_whitelist": env_whitelist,
        "tools": {
            "nvcc_version": _try_cmd(["nvcc", "--version"], cwd=str(workspace)),
            "nvidia_smi": _try_cmd(
                ["nvidia-smi", "--query-gpu=name,driver_version,cuda_version", "--format=csv,noheader"],
                cwd=str(workspace),
            ),
            "git_head": _try_cmd(["git", "rev-parse", "HEAD"], cwd=str(workspace)),
        },
    }

    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
