from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from cuda_agent.storage.index import IndexedRun


def resolve_summary_path(run: IndexedRun) -> Path:
    if run.summary_path:
        return Path(run.summary_path)
    return Path(run.run_dir) / "summary.json"


def resolve_report_path(run: IndexedRun) -> Path:
    if run.report_path:
        return Path(run.report_path)
    return Path(run.run_dir) / "report.md"


def load_summary(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        obj = json.load(handle)
    if not isinstance(obj, dict):
        raise ValueError(f"Summary at {path} is not a JSON object")
    return obj


def _fmt_num(value: Any) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.6g}"
    except Exception:
        return str(value)


def _fmt_pct(value: Any) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value) * 100:.3g}%"
    except Exception:
        return "N/A"


def _numeric_aggregates(summary: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    aggregates = summary.get("aggregates", {})
    if not isinstance(aggregates, dict):
        return {}

    numeric = aggregates.get("numeric", {})
    if not isinstance(numeric, dict):
        return {}

    return {str(name): stats for name, stats in numeric.items() if isinstance(stats, dict)}


def _metric_units(summary: Mapping[str, Any], metric_name: str) -> str | None:
    numeric = _numeric_aggregates(summary)
    stats = numeric.get(metric_name)
    if isinstance(stats, dict) and isinstance(stats.get("units"), str) and stats["units"].strip():
        return stats["units"]

    runs = summary.get("runs", [])
    if not isinstance(runs, list):
        return None

    for run in runs:
        if not isinstance(run, dict):
            continue
        metrics = run.get("metrics", {})
        if not isinstance(metrics, dict):
            continue
        payload = metrics.get(metric_name)
        if isinstance(payload, dict) and isinstance(payload.get("units"), str) and payload["units"].strip():
            return payload["units"]
    return None


def _metric_better(summary: Mapping[str, Any], metric_name: str) -> str | None:
    numeric = _numeric_aggregates(summary)
    stats = numeric.get(metric_name)
    if isinstance(stats, dict):
        better = stats.get("better")
        if better in {"higher", "lower"}:
            return str(better)
    return None


def _infer_metric_better(metric_name: str, units: str | None) -> str | None:
    name = metric_name.lower()
    units_norm = (units or "").strip().lower()

    lower_markers = (
        "latency",
        "time",
        "duration",
        "delay",
        "p50",
        "p90",
        "p95",
        "p99",
        "error",
        "loss",
    )
    higher_markers = (
        "throughput",
        "bandwidth",
        "gflops",
        "tflops",
        "fps",
        "ops_per_sec",
        "ops/sec",
        "qps",
        "requests_per_sec",
        "rps",
        "score",
    )
    lower_units = {"s", "sec", "secs", "second", "seconds", "ms", "us", "ns"}
    higher_units = {"ops_per_sec", "ops/sec", "qps", "rps", "fps", "gflops", "tflops", "gbps"}

    if any(marker in name for marker in lower_markers):
        return "lower"
    if any(marker in name for marker in higher_markers):
        return "higher"
    if units_norm in lower_units:
        return "lower"
    if units_norm in higher_units:
        return "higher"
    return None


def _metric_direction(summary_a: Mapping[str, Any], summary_b: Mapping[str, Any], metric_name: str) -> str | None:
    explicit = _metric_better(summary_b, metric_name) or _metric_better(summary_a, metric_name)
    if explicit:
        return explicit

    units = _metric_units(summary_b, metric_name) or _metric_units(summary_a, metric_name)
    return _infer_metric_better(metric_name, units)


def _direction_label(direction: str | None) -> str:
    if direction == "higher":
        return "higher is better"
    if direction == "lower":
        return "lower is better"
    return "unknown"


def _assessment(direction: str | None, baseline_mean: Any, candidate_mean: Any) -> str:
    if not isinstance(baseline_mean, (int, float)) or not isinstance(candidate_mean, (int, float)):
        return "unknown"
    if float(candidate_mean) == float(baseline_mean):
        return "no change"
    if direction == "higher":
        return "improvement" if float(candidate_mean) > float(baseline_mean) else "regression"
    if direction == "lower":
        return "improvement" if float(candidate_mean) < float(baseline_mean) else "regression"
    return "change"


def render_compare_text(
    *,
    baseline_run: IndexedRun,
    baseline_summary: Mapping[str, Any],
    candidate_run: IndexedRun,
    candidate_summary: Mapping[str, Any],
) -> str:
    baseline_status = baseline_summary.get("summary", {}) if isinstance(baseline_summary.get("summary"), dict) else {}
    candidate_status = candidate_summary.get("summary", {}) if isinstance(candidate_summary.get("summary"), dict) else {}

    lines = [
        "# CUDA Agent Compare",
        "",
        "## Baseline",
        f"- run_id: `{baseline_run.run_id}`",
        f"- project: `{baseline_run.project_name or '-'}`",
        f"- target: `{baseline_run.target_id}`",
        f"- status: `{baseline_run.status}`",
        f"- finished_at: `{baseline_run.finished_at}`",
        f"- launch: `{baseline_run.launch or '-'}`",
        f"- summary: `{resolve_summary_path(baseline_run)}`",
        f"- report: `{resolve_report_path(baseline_run)}`",
        "",
        "## Candidate",
        f"- run_id: `{candidate_run.run_id}`",
        f"- project: `{candidate_run.project_name or '-'}`",
        f"- target: `{candidate_run.target_id}`",
        f"- status: `{candidate_run.status}`",
        f"- finished_at: `{candidate_run.finished_at}`",
        f"- launch: `{candidate_run.launch or '-'}`",
        f"- summary: `{resolve_summary_path(candidate_run)}`",
        f"- report: `{resolve_report_path(candidate_run)}`",
        "",
        "## Status",
        f"- summary_status: `{baseline_status.get('status', baseline_run.status)}` -> `{candidate_status.get('status', candidate_run.status)}`",
        f"- pass_rate: `{_fmt_pct(baseline_status.get('pass_rate'))}` -> `{_fmt_pct(candidate_status.get('pass_rate'))}`",
        f"- stage: `{baseline_run.stage}` -> `{candidate_run.stage}`",
        "",
    ]

    baseline_numeric = _numeric_aggregates(baseline_summary)
    candidate_numeric = _numeric_aggregates(candidate_summary)
    shared_metrics = sorted(set(baseline_numeric) & set(candidate_numeric))

    if not shared_metrics:
        lines.extend(
            [
                "## Shared Numeric Aggregates",
                "",
                "No shared numeric aggregates found.",
                "",
            ]
        )
        return "\n".join(lines)

    lines.extend(
        [
            "## Shared Numeric Aggregates",
            "",
            "| metric | direction | baseline_mean | candidate_mean | delta | delta_pct | assessment |",
            "|---|---|---:|---:|---:|---:|---|",
        ]
    )

    highlights: list[str] = []

    for name in shared_metrics:
        baseline_stats = baseline_numeric[name]
        candidate_stats = candidate_numeric[name]
        baseline_mean = baseline_stats.get("mean")
        candidate_mean = candidate_stats.get("mean")
        delta = None
        delta_pct = None
        if isinstance(baseline_mean, (int, float)) and isinstance(candidate_mean, (int, float)):
            delta = float(candidate_mean) - float(baseline_mean)
            if float(baseline_mean) != 0.0:
                delta_pct = delta / abs(float(baseline_mean))

        units = _metric_units(candidate_summary, name) or _metric_units(baseline_summary, name)
        direction = _metric_direction(baseline_summary, candidate_summary, name)
        assessment = _assessment(direction, baseline_mean, candidate_mean)
        display_name = f"{name} ({units})" if units else name
        display_name = display_name.replace("|", "\\|")
        lines.append(
            f"| {display_name} | {_direction_label(direction)} | {_fmt_num(baseline_mean)} | {_fmt_num(candidate_mean)} | {_fmt_num(delta)} | {_fmt_pct(delta_pct)} | {assessment} |"
        )
        if assessment in {"improvement", "regression"}:
            highlights.append(
                f"- `{display_name}`: {assessment} ({_direction_label(direction)}, baseline {_fmt_num(baseline_mean)}, candidate {_fmt_num(candidate_mean)})"
            )

    lines.append("")
    if highlights:
        lines.extend(["## Highlights", ""])
        lines.extend(highlights)
        lines.append("")
    return "\n".join(lines)
