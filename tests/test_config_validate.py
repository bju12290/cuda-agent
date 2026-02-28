from __future__ import annotations

from pathlib import Path

import pytest

from cuda_agent.config import load_config_resolved
from cuda_agent.config.errors import ValidationError
from cuda_agent.config.validate import validate_config


def _base_cfg() -> dict:
    return {
        "version": 1,
        "project": {
            "workspace": ".",
        },
        "build": {
            "configure_cmd": ["echo", "configure"],
            "build_cmd": ["echo", "build"],
        },
        "storage": {
            "root": "./runs",
        },
        "targets": {
            "smoke": {
                "run": {
                    "cmd": ["python", "-c", "print('ok')"],
                }
            }
        },
    }


def test_validate_accepts_run_cmd_target() -> None:
    cfg = _base_cfg()
    validate_config(cfg)


def test_validate_accepts_run_exe_glob_target() -> None:
    cfg = _base_cfg()
    cfg["targets"]["smoke"]["run"] = {
        "exe_glob": "bin/tool.exe",
        "args": ["--flag"],
        "runs": 2,
        "warmup_runs": 1,
    }
    validate_config(cfg)


def test_validate_rejects_target_with_both_cmd_and_exe_glob() -> None:
    cfg = _base_cfg()
    cfg["targets"]["smoke"]["run"] = {
        "cmd": ["python", "-c", "print('ok')"],
        "exe_glob": "bin/tool.exe",
    }

    with pytest.raises(ValidationError, match="exactly one of run\\.exe_glob or run\\.cmd"):
        validate_config(cfg)


def test_validate_rejects_target_with_neither_cmd_nor_exe_glob() -> None:
    cfg = _base_cfg()
    cfg["targets"]["smoke"]["run"] = {"runs": 1}

    with pytest.raises(ValidationError, match="exactly one of run\\.exe_glob or run\\.cmd"):
        validate_config(cfg)


def test_validate_rejects_args_with_run_cmd() -> None:
    cfg = _base_cfg()
    cfg["targets"]["smoke"]["run"] = {
        "cmd": ["python", "-c", "print('ok')"],
        "args": ["--unexpected"],
    }

    with pytest.raises(ValidationError, match="run\\.args'.*not allowed when run\\.cmd is used"):
        validate_config(cfg)


def test_validate_rejects_pass_rule_without_parse_definition() -> None:
    cfg = _base_cfg()
    cfg["targets"]["smoke"]["success"] = {
        "pass_rule": "status",
    }

    with pytest.raises(ValidationError, match="target has no parse section"):
        validate_config(cfg)


def test_validate_rejects_pass_rule_missing_from_parse_rules() -> None:
    cfg = _base_cfg()
    cfg["targets"]["smoke"]["parse"] = {
        "kind": "regex",
        "rules": [
            {
                "name": "duration_ms",
                "pattern": r"duration=(\d+)",
                "type": "int",
            }
        ],
    }
    cfg["targets"]["smoke"]["success"] = {
        "pass_rule": "status",
    }

    with pytest.raises(ValidationError, match="must reference a defined parse rule"):
        validate_config(cfg)


def test_validate_rejects_invalid_parse_rule_better_value() -> None:
    cfg = _base_cfg()
    cfg["targets"]["smoke"]["parse"] = {
        "kind": "regex",
        "rules": [
            {
                "name": "latency_ms",
                "pattern": r"latency=(\d+)",
                "type": "int",
                "better": "fastest",
            }
        ],
    }

    with pytest.raises(ValidationError, match="parse\\.rules\\[0\\]\\.better"):
        validate_config(cfg)


def test_fixture_project_configs_load_and_validate() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    for rel_path in ("fixtures/python_smoke/agent.yaml", "fixtures/node_smoke/agent.yaml"):
        cfg = load_config_resolved(str(repo_root / rel_path))
        assert "targets" in cfg
