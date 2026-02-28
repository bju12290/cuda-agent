from __future__ import annotations

import sys
from pathlib import Path

from cuda_agent.adapters.targets import run_target


def _base_cfg(workspace: Path) -> dict:
    return {
        "version": 1,
        "project": {
            "workspace": str(workspace),
        },
        "build": {
            "configure_cmd": ["echo", "configure"],
            "build_cmd": ["echo", "build"],
        },
        "storage": {
            "root": "./runs",
        },
        "targets": {},
    }


def test_run_target_uses_workspace_for_run_cmd(tmp_path: Path) -> None:
    cfg = _base_cfg(tmp_path)
    cfg["targets"]["cwd_check"] = {
        "run": {
            "cmd": [
                sys.executable,
                "-c",
                "import pathlib; print(pathlib.Path.cwd())",
            ],
            "runs": 1,
            "warmup_runs": 0,
        }
    }

    result = run_target(cfg, "cwd_check")

    assert result.launch_cwd == tmp_path.resolve()
    assert result.executable_path is None
    assert result.launch_cmd == (
        sys.executable,
        "-c",
        "import pathlib; print(pathlib.Path.cwd())",
    )
    assert result.runs[0].stdout.strip() == str(tmp_path.resolve())


def test_run_target_uses_executable_parent_for_exe_glob() -> None:
    exe_path = Path(sys.executable).resolve()
    cfg = _base_cfg(Path.cwd())
    cfg["targets"]["python_exec"] = {
        "run": {
            "exe_glob": str(exe_path),
            "args": ["-c", "print('adapter-ok')"],
            "runs": 1,
        }
    }

    result = run_target(cfg, "python_exec")

    assert result.executable_path == exe_path
    assert result.launch_cwd == exe_path.parent
    assert result.launch_cmd[0] == str(exe_path)
    assert result.runs[0].stdout.strip() == "adapter-ok"
