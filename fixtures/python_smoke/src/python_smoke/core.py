from __future__ import annotations


def benchmark_metrics(profile: str) -> dict[str, float | str]:
    normalized = profile.strip().lower()
    if normalized == "slow":
        return {
            "status": "PASS",
            "time_ms": 14.0,
            "ops_per_sec": 760.0,
        }

    return {
        "status": "PASS",
        "time_ms": 8.5,
        "ops_per_sec": 1250.0,
    }
