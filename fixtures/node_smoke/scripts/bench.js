const { benchmarkMetrics } = require("../src");

const profile = process.env.BENCH_PROFILE || "fast";
const metrics = benchmarkMetrics(profile);

console.log(`STATUS: ${metrics.status}`);
console.log(`LATENCY_MS: ${metrics.latency_ms}`);
console.log(`OPS_PER_SEC: ${metrics.ops_per_sec}`);
