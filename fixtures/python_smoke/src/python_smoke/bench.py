from __future__ import annotations

import os

from .core import benchmark_metrics


def main() -> int:
    profile = os.environ.get("BENCH_PROFILE", "fast")
    metrics = benchmark_metrics(profile)
    print(f"STATUS: {metrics['status']}")
    print(f"TIME_MS: {metrics['time_ms']}")
    print(f"OPS_PER_SEC: {metrics['ops_per_sec']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
