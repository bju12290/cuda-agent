const test = require("node:test");
const assert = require("node:assert/strict");

const { benchmarkMetrics } = require("../src");

test("fast profile is better than slow profile", () => {
  const fast = benchmarkMetrics("fast");
  const slow = benchmarkMetrics("slow");

  assert.equal(fast.status, "PASS");
  assert.equal(slow.status, "PASS");
  assert.ok(fast.latency_ms < slow.latency_ms);
  assert.ok(fast.ops_per_sec > slow.ops_per_sec);
});
