from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .artifacts import write_text


def _relative_path(run_dir: Path, path: Path) -> str:
    try:
        rel = path.relative_to(run_dir)
        return "./" + str(rel).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def _fmt_num(value: Any) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value):.6g}"
    except Exception:
        return str(value)


def _fmt_pct_ratio(value: Any) -> str:
    if value is None:
        return "N/A"
    try:
        return f"{float(value) * 100:.3g}%"
    except Exception:
        return "N/A"


def render_report_md(
    *,
    run_dir: Path,
    run_id: str,
    ts_iso: str,
    target: str,
    live: bool,
    launch: str | None,
    stage: str,
    stage_status: str,
    message: str | None,
    build_log_path: Path,
    test_log_path: Path,
    config_snapshot_path: Path,
    env_path: Path,
    bench_dir: Path,
    summary_path: Path | None,
    summary_obj: Mapping[str, Any] | None,
) -> str:
    if summary_obj and isinstance(summary_obj.get("summary"), dict):
        overall_status = str(summary_obj["summary"].get("status", stage_status))
    else:
        overall_status = stage_status if stage_status != "OK" else "PASS"

    lines: list[str] = [
        "# CUDA Agent Report",
        "",
        "## Run",
        f"- **run_id:** `{run_id}`",
        f"- **timestamp:** `{ts_iso}`",
        f"- **target:** `{target}`",
        f"- **launch:** `{launch or 'N/A'}`",
        f"- **live:** `{bool(live)}`",
        f"- **status:** `{overall_status}`",
        f"- **stage:** `{stage}`",
    ]
    if message:
        lines.append(f"- **message:** {message}")
    lines.extend(
        [
            "",
            "## Artifacts",
            f"- `build.log`: `{_relative_path(run_dir, build_log_path)}`",
            f"- `test.log`: `{_relative_path(run_dir, test_log_path)}`",
            f"- `config_snapshot.yaml`: `{_relative_path(run_dir, config_snapshot_path)}`",
            f"- `env.json`: `{_relative_path(run_dir, env_path)}`",
            f"- `bench/`: `{_relative_path(run_dir, bench_dir)}/`",
        ]
    )
    if summary_path is not None:
        lines.append(f"- `summary.json`: `{_relative_path(run_dir, summary_path)}`")
    lines.append("")

    if summary_obj and isinstance(summary_obj.get("summary"), dict):
        summary = summary_obj["summary"]
        lines.extend(
            [
                "## Summary",
                f"- **total_runs:** `{summary.get('total_runs')}`",
                f"- **warmup_runs:** `{summary.get('warmup_runs')}`",
                f"- **pass_rule:** `{summary.get('pass_rule')}`",
                f"- **passed:** `{summary.get('passed')}`",
                f"- **failed:** `{summary.get('failed')}`",
                f"- **pass_rate:** `{_fmt_num(summary.get('pass_rate'))}` (min `{_fmt_num(summary.get('min_pass_rate'))}`)",
                "",
            ]
        )

        aggregates = summary_obj.get("aggregates", {})
        numeric = aggregates.get("numeric") if isinstance(aggregates, dict) else None
        if isinstance(numeric, dict) and numeric:
            lines.extend(
                [
                    "## Numeric aggregates",
                    "",
                    "| metric | n | min | mean | max | stdev | cv |",
                    "|---|---:|---:|---:|---:|---:|---:|",
                ]
            )
            for name, stats in sorted(numeric.items()):
                if not isinstance(stats, dict):
                    continue
                metric = str(name).replace("|", "\\|")
                lines.append(
                    f"| {metric} | {stats.get('n', '')} | {_fmt_num(stats.get('min'))} | {_fmt_num(stats.get('mean'))} | {_fmt_num(stats.get('max'))} | {_fmt_num(stats.get('stdev'))} | {_fmt_pct_ratio(stats.get('cv'))} |"
                )
            lines.extend(["", "## Stability notes", ""])

            cv_items: list[tuple[float, str]] = []
            for name, stats in numeric.items():
                if not isinstance(stats, dict):
                    continue
                cv = stats.get("cv")
                if isinstance(cv, (int, float)):
                    cv_items.append((float(cv), str(name)))

            if not cv_items:
                lines.extend(["- No CV values computed (missing metrics or mean == 0).", ""])
            else:
                very_stable: list[str] = []
                stable: list[str] = []
                noisy: list[tuple[float, str]] = []
                for cv, name in cv_items:
                    if cv <= 0.01:
                        very_stable.append(name)
                    elif cv <= 0.05:
                        stable.append(name)
                    else:
                        noisy.append((cv, name))

                if very_stable:
                    lines.append(f"- **Very stable (CV <= 1%)**: {', '.join(f'`{name}`' for name in sorted(very_stable))}")
                if stable:
                    lines.append(f"- **Stable-ish (1% < CV <= 5%)**: {', '.join(f'`{name}`' for name in sorted(stable))}")
                if noisy:
                    lines.append("- **Noisiest (CV > 5%)** (top 5):")
                    noisy.sort(reverse=True)
                    for cv, name in noisy[:5]:
                        lines.append(f"  - `{name}`: CV {_fmt_pct_ratio(cv)}")
                lines.append("")

    lines.extend(
        [
            "## Notes",
            "- `build.log` / `test.log` include full stdout/stderr for reproducibility.",
            "- `bench/` contains per-run stdout/stderr and parsed per-run metrics JSON.",
            "",
        ]
    )
    return "\n".join(lines)


def write_report_md(
    path: Path,
    *,
    run_dir: Path,
    run_id: str,
    ts_iso: str,
    target: str,
    live: bool,
    launch: str | None,
    stage: str,
    stage_status: str,
    message: str | None,
    build_log_path: Path,
    test_log_path: Path,
    config_snapshot_path: Path,
    env_path: Path,
    bench_dir: Path,
    summary_path: Path | None,
    summary_obj: Mapping[str, Any] | None,
) -> None:
    write_text(
        path,
        render_report_md(
            run_dir=run_dir,
            run_id=run_id,
            ts_iso=ts_iso,
            target=target,
            live=live,
            launch=launch,
            stage=stage,
            stage_status=stage_status,
            message=message,
            build_log_path=build_log_path,
            test_log_path=test_log_path,
            config_snapshot_path=config_snapshot_path,
            env_path=env_path,
            bench_dir=bench_dir,
            summary_path=summary_path,
            summary_obj=summary_obj,
        ),
    )
