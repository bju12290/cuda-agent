# Python Smoke Fixture

Minimal Python fixture project for manual `cuda-agent` CLI testing.

The benchmark reads `BENCH_PROFILE` from the environment:

- `fast` -> lower latency, higher throughput
- `slow` -> higher latency, lower throughput

Use the local `agent.yaml` in this directory with:

```powershell
.\.venv\Scripts\cuda-agent.exe --config fixtures\python_smoke\agent.yaml run benchmark --live
```
