# Node Smoke Fixture

Minimal Node.js fixture project for manual `cuda-agent` CLI testing.

The benchmark reads `BENCH_PROFILE` from the environment:

- `fast` -> lower latency, higher throughput
- `slow` -> higher latency, lower throughput

Run it with:

```powershell
.\.venv\Scripts\cuda-agent.exe --config fixtures\node_smoke\agent.yaml run benchmark --live
```
