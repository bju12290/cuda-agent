from __future__ import annotations

from typing import Any, Mapping

from .errors import ValidationError


def _require_mapping(parent: Any, key: str, path: str) -> dict:
    if not isinstance(parent, dict):
        raise ValidationError(f"Invalid '{path}': must be a mapping/object")
    val = parent.get(key)
    if not isinstance(val, dict):
        raise ValidationError(f"Missing or invalid '{path}.{key}' (must be a mapping/object)")
    return val


def _require_str(parent: Any, key: str, path: str) -> str:
    if not isinstance(parent, dict):
        raise ValidationError(f"Invalid '{path}': must be a mapping/object")
    val = parent.get(key)
    if not isinstance(val, str) or not val.strip():
        raise ValidationError(f"Missing or invalid '{path}.{key}' (must be a non-empty string)")
    return val


def _require_list_str(parent: Any, key: str, path: str) -> list[str]:
    if not isinstance(parent, dict):
        raise ValidationError(f"Invalid '{path}': must be a mapping/object")
    val = parent.get(key)
    if not isinstance(val, list) or not all(isinstance(x, str) and x.strip() for x in val):
        raise ValidationError(f"Missing or invalid '{path}.{key}' (must be a list of non-empty strings)")
    return val


def _optional_bool(parent: Any, key: str, path: str) -> bool | None:
    if not isinstance(parent, dict) or key not in parent:
        return None
    val = parent[key]
    if not isinstance(val, bool):
        raise ValidationError(f"Invalid '{path}.{key}' (must be a boolean)")
    return val


def _optional_int(parent: Any, key: str, path: str) -> int | None:
    if not isinstance(parent, dict) or key not in parent:
        return None
    val = parent[key]
    if not isinstance(val, int):
        raise ValidationError(f"Invalid '{path}.{key}' (must be an integer)")
    return val


def _optional_number(parent: Any, key: str, path: str) -> float | None:
    if not isinstance(parent, dict) or key not in parent:
        return None
    val = parent[key]
    if not isinstance(val, (int, float)) or isinstance(val, bool):
        raise ValidationError(f"Invalid '{path}.{key}' (must be a number)")
    return float(val)


def _optional_str(parent: Any, key: str, path: str) -> str | None:
    if not isinstance(parent, dict) or key not in parent:
        return None
    val = parent[key]
    if not isinstance(val, str) or not val.strip():
        raise ValidationError(f"Invalid '{path}.{key}' (must be a non-empty string)")
    return val


def _validate_parse_rule(rule: Any, *, path: str) -> str:
    if not isinstance(rule, dict):
        raise ValidationError(f"Invalid '{path}' (must be a mapping/object)")

    name = _require_str(rule, "name", path)
    _require_str(rule, "pattern", path)

    rtype = rule.get("type", "str")
    if rtype not in {"float", "int", "enum", "str"}:
        raise ValidationError(f"Invalid '{path}.type' (expected one of: float, int, enum, str)")

    units = rule.get("units")
    if units is not None and (not isinstance(units, str) or not units.strip()):
        raise ValidationError(f"Invalid '{path}.units' (must be a non-empty string when present)")

    better = rule.get("better")
    if better is not None and better not in {"higher", "lower"}:
        raise ValidationError(f"Invalid '{path}.better' (expected 'higher' or 'lower' when present)")

    if "required" in rule:
        _optional_bool(rule, "required", path)

    if rtype == "enum":
        enum_vals = rule.get("enum")
        if not isinstance(enum_vals, list) or not enum_vals or not all(isinstance(x, str) and x for x in enum_vals):
            raise ValidationError(f"Invalid '{path}.enum' (must be a non-empty list of strings for enum rules)")

    return name


def _validate_target(target_id: str, target_cfg: Any) -> None:
    path = f"targets.{target_id}"
    if not isinstance(target_cfg, dict):
        raise ValidationError(f"Invalid '{path}' (must be a mapping/object)")

    description = target_cfg.get("description")
    if description is not None and (not isinstance(description, str) or not description.strip()):
        raise ValidationError(f"Invalid '{path}.description' (must be a non-empty string when present)")

    run_cfg = _require_mapping(target_cfg, "run", path)
    exe_glob = run_cfg.get("exe_glob")
    cmd = run_cfg.get("cmd")

    has_exe_glob = isinstance(exe_glob, str) and bool(exe_glob.strip())
    has_cmd = isinstance(cmd, list) and bool(cmd)
    if has_exe_glob == has_cmd:
        raise ValidationError(f"Invalid '{path}.run' (must define exactly one of run.exe_glob or run.cmd)")

    if has_exe_glob:
        _require_str(run_cfg, "exe_glob", f"{path}.run")
    else:
        if not isinstance(cmd, list) or not all(isinstance(x, str) and x.strip() for x in cmd):
            raise ValidationError(f"Invalid '{path}.run.cmd' (must be a non-empty list of non-empty strings)")

    args = run_cfg.get("args", [])
    if not isinstance(args, list) or not all(isinstance(x, str) for x in args):
        raise ValidationError(f"Invalid '{path}.run.args' (must be a list of strings)")
    if has_cmd and "args" in run_cfg:
        raise ValidationError(f"Invalid '{path}.run.args' (not allowed when run.cmd is used)")

    runs = run_cfg.get("runs", 1)
    if not isinstance(runs, int) or runs < 1:
        raise ValidationError(f"Invalid '{path}.run.runs' (must be an integer >= 1)")

    warmup_runs = run_cfg.get("warmup_runs", 0)
    if not isinstance(warmup_runs, int) or warmup_runs < 0:
        raise ValidationError(f"Invalid '{path}.run.warmup_runs' (must be an integer >= 0)")

    parse_cfg = target_cfg.get("parse")
    parse_rule_names: set[str] = set()
    if parse_cfg is not None:
        if not isinstance(parse_cfg, dict):
            raise ValidationError(f"Invalid '{path}.parse' (must be a mapping/object)")
        kind = parse_cfg.get("kind")
        if kind != "regex":
            raise ValidationError(f"Invalid '{path}.parse.kind' (expected 'regex')")

        rules = parse_cfg.get("rules")
        if not isinstance(rules, list) or not rules:
            raise ValidationError(f"Invalid '{path}.parse.rules' (must be a non-empty list)")

        for index, rule in enumerate(rules):
            rule_name = _validate_parse_rule(rule, path=f"{path}.parse.rules[{index}]")
            if rule_name in parse_rule_names:
                raise ValidationError(f"Duplicate parse rule name '{rule_name}' under '{path}.parse.rules'")
            parse_rule_names.add(rule_name)

    success_cfg = target_cfg.get("success")
    if success_cfg is not None:
        if not isinstance(success_cfg, dict):
            raise ValidationError(f"Invalid '{path}.success' (must be a mapping/object)")

        exit_code = _optional_int(success_cfg, "exit_code", f"{path}.success")
        if exit_code is not None and exit_code < 0:
            raise ValidationError(f"Invalid '{path}.success.exit_code' (must be >= 0)")

        pass_rule = _optional_str(success_cfg, "pass_rule", f"{path}.success")
        if pass_rule is not None:
            if parse_cfg is None:
                raise ValidationError(f"Invalid '{path}.success.pass_rule' (target has no parse section)")
            if pass_rule not in parse_rule_names:
                raise ValidationError(
                    f"Invalid '{path}.success.pass_rule' (must reference a defined parse rule)"
                )


def validate_config(cfg: Mapping[str, Any]) -> None:
    """
    Validate the resolved config.

    Current schema is generic across projects:
        - version must exist and equal 1
        - project.workspace must exist
        - build.configure_cmd and build.build_cmd are required
        - storage.root is required
        - targets must be a non-empty mapping of target ids to target definitions

    Raises:
        ValidationError on any invalid config.
    """
    if "version" not in cfg:
        raise ValidationError("Missing required key: 'version'")

    version = cfg["version"]
    if version != 1:
        raise ValidationError(f"Unsupported config version: {version!r} (expected 1)")

    project = cfg.get("project")
    if not isinstance(project, dict):
        raise ValidationError("Missing or invalid 'project' section (must be a mapping/object)")

    workspace = project.get("workspace")
    if not isinstance(workspace, str) or not workspace.strip():
        raise ValidationError("Missing or invalid 'project.workspace' (must be a non-empty string)")

    name = project.get("name")
    if name is not None and (not isinstance(name, str) or not name.strip()):
        raise ValidationError("Invalid 'project.name' (must be a non-empty string when present)")

    build = _require_mapping(cfg, "build", "<root>")
    _require_list_str(build, "configure_cmd", "build")
    _require_list_str(build, "build_cmd", "build")
    if "build_dir" in build:
        _require_str(build, "build_dir", "build")

    storage = _require_mapping(cfg, "storage", "<root>")
    _require_str(storage, "root", "storage")

    env = cfg.get("env")
    if env is not None:
        if not isinstance(env, dict):
            raise ValidationError("Invalid 'env' section (must be a mapping/object)")
        for key, value in env.items():
            if not isinstance(key, str) or not key.strip():
                raise ValidationError("Invalid 'env' key (must be a non-empty string)")
            if not isinstance(value, (str, int, float, bool)) or value is None:
                raise ValidationError(f"Invalid 'env.{key}' (must be a scalar value)")

    test_cfg = cfg.get("test")
    if test_cfg is not None:
        if not isinstance(test_cfg, dict):
            raise ValidationError("Invalid 'test' section (must be a mapping/object)")
        enabled = test_cfg.get("enabled", False)
        if not isinstance(enabled, bool):
            raise ValidationError("Invalid 'test.enabled' (must be a boolean)")
        cmd = test_cfg.get("cmd", [])
        if not isinstance(cmd, list) or not all(isinstance(x, str) and x.strip() for x in cmd):
            raise ValidationError("Invalid 'test.cmd' (must be a list of non-empty strings)")
        if enabled and not cmd:
            raise ValidationError("Invalid 'test.cmd' (must be non-empty when test.enabled=true)")

    policy = cfg.get("policy")
    if policy is not None:
        if not isinstance(policy, dict):
            raise ValidationError("Invalid 'policy' section (must be a mapping/object)")
        fail_fast = _optional_bool(policy, "fail_fast", "policy")
        _ = fail_fast
        min_pass_rate = _optional_number(policy, "min_pass_rate", "policy")
        if min_pass_rate is not None and not (0.0 <= min_pass_rate <= 1.0):
            raise ValidationError("Invalid 'policy.min_pass_rate' (must be between 0.0 and 1.0)")

    targets = cfg.get("targets")
    if not isinstance(targets, dict):
        raise ValidationError("Missing or invalid 'targets' section (must be a mapping/object)")
    if not targets:
        raise ValidationError("Missing or invalid 'targets' section (must define at least one target)")

    for target_id, target_cfg in targets.items():
        if not isinstance(target_id, str) or not target_id.strip():
            raise ValidationError("Invalid target id under 'targets' (must be a non-empty string)")
        _validate_target(target_id, target_cfg)
