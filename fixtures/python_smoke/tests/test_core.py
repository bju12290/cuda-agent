from __future__ import annotations

import unittest

from python_smoke.core import benchmark_metrics


class BenchmarkMetricsTests(unittest.TestCase):
    def test_fast_profile_is_better_than_slow_profile(self) -> None:
        fast = benchmark_metrics("fast")
        slow = benchmark_metrics("slow")

        self.assertEqual(fast["status"], "PASS")
        self.assertEqual(slow["status"], "PASS")
        self.assertLess(float(fast["time_ms"]), float(slow["time_ms"]))
        self.assertGreater(float(fast["ops_per_sec"]), float(slow["ops_per_sec"]))


if __name__ == "__main__":
    unittest.main()
