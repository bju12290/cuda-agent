from __future__ import annotations

import json
from pathlib import Path
from statistics import fmean, stdev
from typing import Any, Mapping

from cuda_agent.adapters.parse import ParseError, parse_target_output
from cuda_agent.adapters.targets import RunResult


def _metric_payload(metrics: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {name: {"value": metric.value, "units": metric.units} for name, metric in metrics.items()}


def _parse_rule_metadata(cfg: Mapping[str, Any], target: str) -> dict[str, dict[str, str]]:
    targets = cfg.get("targets", {})
    if not isinstance(targets, dict):
        return {}

    target_cfg = targets.get(target, {})
    if not isinstance(target_cfg, dict):
        return {}

    parse_cfg = target_cfg.get("parse", {})
    if not isinstance(parse_cfg, dict):
        return {}

    rules = parse_cfg.get("rules", [])
    if not isinstance(rules, list):
        return {}

    metadata: dict[str, dict[str, str]] = {}
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        name = rule.get("name")
        if not isinstance(name, str) or not name.strip():
            continue

        payload: dict[str, str] = {}
        units = rule.get("units")
        if isinstance(units, str) and units.strip():
            payload["units"] = units
        better = rule.get("better")
        if better in {"higher", "lower"}:
            payload["better"] = better
        metadata[name] = payload
    return metadata


def expected_exit_code(cfg: Mapping[str, Any], target: str) -> int:
    target_cfg = cfg.get("targets", {}).get(target, {})
    success_cfg = target_cfg.get("success", {}) if isinstance(target_cfg, dict) else {}
    if isinstance(success_cfg, dict) and isinstance(success_cfg.get("exit_code"), int):
        return success_cfg["exit_code"]
    return 0


def count_bad_runs(run_result: RunResult, *, expected_exit_code: int) -> int:
    return sum(1 for result in run_result.runs if result.exit_code != expected_exit_code)


def summarize_run(
    cfg: Mapping[str, Any],
    *,
    target: str,
    run_id: str,
    ts_iso: str,
    launch: str,
    launch_cmd: list[str],
    run_result: RunResult,
    bench_dir: Path,
    summary_path: Path,
) -> dict[str, Any]:
    target_cfg = cfg.get("targets", {}).get(target, {})
    has_parse = isinstance(target_cfg, dict) and isinstance(target_cfg.get("parse"), dict)
    pass_rule = None
    success_cfg = target_cfg.get("success", {}) if isinstance(target_cfg, dict) else {}
    if isinstance(success_cfg, dict) and isinstance(success_cfg.get("pass_rule"), str):
        pass_rule = success_cfg["pass_rule"]

    policy = cfg.get("policy", {})
    min_pass_rate = float(policy.get("min_pass_rate", 1.0)) if isinstance(policy, dict) else 1.0
    expected = expected_exit_code(cfg, target)
    parse_rule_metadata = _parse_rule_metadata(cfg, target)

    parsed_runs: list[dict[str, Any]] = []

    for index, result in enumerate(run_result.warmups, start=1):
        stem = f"warmup_{index:03d}"
        (bench_dir / f"{stem}.stdout.txt").write_text(result.stdout or "", encoding="utf-8")
        (bench_dir / f"{stem}.stderr.txt").write_text(result.stderr or "", encoding="utf-8")

    for index, result in enumerate(run_result.runs, start=1):
        stem = f"run_{index:03d}"
        (bench_dir / f"{stem}.stdout.txt").write_text(result.stdout or "", encoding="utf-8")
        (bench_dir / f"{stem}.stderr.txt").write_text(result.stderr or "", encoding="utf-8")

        metrics_dict: dict[str, dict[str, Any]] = {}
        parse_error: str | None = None
        if has_parse:
            try:
                metrics_dict = _metric_payload(parse_target_output(cfg, target, result.stdout or ""))
            except ParseError as exc:
                parse_error = str(exc)

        run_record = {
            "index": index,
            "exit_code": result.exit_code,
            "duration_ms": result.duration_ms,
            "metrics": metrics_dict,
            "parse_error": parse_error,
        }
        (bench_dir / f"{stem}.metrics.json").write_text(json.dumps(run_record, indent=2), encoding="utf-8")
        parsed_runs.append(
            {
                "exit_code": result.exit_code,
                "duration_ms": result.duration_ms,
                "metrics": metrics_dict,
                "parse_error": parse_error,
            }
        )

    numeric: dict[str, dict[str, Any]] = {}
    by_name: dict[str, list[Any]] = {}
    for parsed_run in parsed_runs:
        for name, payload in parsed_run["metrics"].items():
            by_name.setdefault(name, []).append(payload.get("value"))

    for name, values in by_name.items():
        numeric_values = [value for value in values if isinstance(value, (int, float))]
        if not numeric_values:
            continue
        mean = fmean(float(value) for value in numeric_values)
        sigma = stdev(float(value) for value in numeric_values) if len(numeric_values) > 1 else 0.0
        mean_abs = abs(mean)
        numeric[name] = {
            "n": len(numeric_values),
            "min": min(numeric_values),
            "max": max(numeric_values),
            "mean": mean,
            "stdev": sigma,
            "cv": (sigma / mean_abs) if mean_abs > 0 else None,
        }
        rule_meta = parse_rule_metadata.get(name, {})
        units = rule_meta.get("units")
        better = rule_meta.get("better")
        if units:
            numeric[name]["units"] = units
        if better:
            numeric[name]["better"] = better

    passed = 0
    failed = 0
    for parsed_run in parsed_runs:
        ok_exit = parsed_run["exit_code"] == expected
        ok_parse = parsed_run.get("parse_error") is None
        ok_rule = True
        if pass_rule:
            metric = parsed_run["metrics"].get(pass_rule)
            value = metric.get("value") if isinstance(metric, dict) else None
            ok_rule = (value is True) or (isinstance(value, str) and value.upper() == "PASS")

        if ok_exit and ok_parse and ok_rule:
            passed += 1
        else:
            failed += 1

    total = len(parsed_runs)
    pass_rate = (passed / total) if total else 0.0
    status = "PASS" if pass_rate >= min_pass_rate else "FAIL"

    summary = {
        "version": 1,
        "run_id": run_id,
        "project": cfg.get("project", {}),
        "target": target,
        "launch": launch,
        "launch_cmd": launch_cmd,
        "summary": {
            "timestamp": ts_iso,
            "total_runs": len(run_result.runs),
            "warmup_runs": len(run_result.warmups),
            "expected_exit_code": expected,
            "pass_rule": pass_rule,
            "passed": passed,
            "failed": failed,
            "pass_rate": pass_rate,
            "min_pass_rate": min_pass_rate,
            "status": status,
            "bad_exit_code_runs": count_bad_runs(run_result, expected_exit_code=expected),
            "parse_error_runs": sum(1 for parsed_run in parsed_runs if parsed_run.get("parse_error") is not None),
        },
        "runs": parsed_runs,
        "aggregates": {"numeric": numeric},
    }

    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    return summary
