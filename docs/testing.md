# Testing Guide

This document describes the recommended validation flow for `cuda-agent`.

## Automated Tests

From the repo root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e .[dev]
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp .pytest_tmp tests
```

Expected result:

- dependencies install successfully
- the package imports correctly
- the test suite passes

## Fixture Projects

If you want to verify the CLI without external toolchains first, use the bundled fixture projects:

- `fixtures/python_smoke/agent.yaml`
- `fixtures/node_smoke/agent.yaml`

These are the easiest way to confirm:

- `run.cmd` execution
- parsing
- report generation
- SQLite run indexing
- compare output

## Python Fixture Validation

From the repo root:

```powershell
.\.venv\Scripts\cuda-agent.exe --config fixtures\python_smoke\agent.yaml validate
.\.venv\Scripts\cuda-agent.exe --config fixtures\python_smoke\agent.yaml show --pretty
.\.venv\Scripts\cuda-agent.exe --config fixtures\python_smoke\agent.yaml build --live
.\.venv\Scripts\cuda-agent.exe --config fixtures\python_smoke\agent.yaml run benchmark --live
.\.venv\Scripts\cuda-agent.exe --config fixtures\python_smoke\agent.yaml runs
.\.venv\Scripts\cuda-agent.exe --config fixtures\python_smoke\agent.yaml report <run_id>
.\.venv\Scripts\cuda-agent.exe --config fixtures\python_smoke\agent.yaml compare <older_run_id> <newer_run_id>
```

To force a regression or improvement comparison:

- change `env.BENCH_PROFILE` in `fixtures/python_smoke/agent.yaml` between `fast` and `slow`
- run the benchmark twice
- compare the two run ids

## Node.js Fixture Validation

From the repo root:

```powershell
.\.venv\Scripts\cuda-agent.exe --config fixtures\node_smoke\agent.yaml validate
.\.venv\Scripts\cuda-agent.exe --config fixtures\node_smoke\agent.yaml show --pretty
.\.venv\Scripts\cuda-agent.exe --config fixtures\node_smoke\agent.yaml build --live
.\.venv\Scripts\cuda-agent.exe --config fixtures\node_smoke\agent.yaml run benchmark --live
.\.venv\Scripts\cuda-agent.exe --config fixtures\node_smoke\agent.yaml runs
.\.venv\Scripts\cuda-agent.exe --config fixtures\node_smoke\agent.yaml report <run_id>
.\.venv\Scripts\cuda-agent.exe --config fixtures\node_smoke\agent.yaml compare <older_run_id> <newer_run_id>
```

To force a regression or improvement comparison:

- change `env.BENCH_PROFILE` in `fixtures/node_smoke/agent.yaml` between `fast` and `slow`
- run the benchmark twice
- compare the two run ids

## CUDA Validation

The main CUDA example config in this repo is:

- `cuda_samples.yaml`

Prerequisites:

- Windows shell with both `cl.exe` and `nvcc.exe` on `PATH`
- external CUDA samples checkout at the path expected by `cuda_samples.yaml`

Recommended commands:

```powershell
.\.venv\Scripts\cuda-agent.exe --config cuda_samples.yaml validate
.\.venv\Scripts\cuda-agent.exe --config cuda_samples.yaml list
.\.venv\Scripts\cuda-agent.exe --config cuda_samples.yaml build --live
.\.venv\Scripts\cuda-agent.exe --config cuda_samples.yaml run deviceQuery --live
.\.venv\Scripts\cuda-agent.exe --config cuda_samples.yaml run matrixMul --live
.\.venv\Scripts\cuda-agent.exe --config cuda_samples.yaml runs
.\.venv\Scripts\cuda-agent.exe --config cuda_samples.yaml report <run_id>
.\.venv\Scripts\cuda-agent.exe --config cuda_samples.yaml compare <older_run_id> <newer_run_id>
```

## What Good Output Looks Like

Healthy validation should show:

- `validate` prints `OK`
- `build` succeeds without missing-tool errors
- `run` writes `summary.json` and `report.md`
- `runs` lists indexed history
- `report` prints a readable Markdown report
- `compare` prints status deltas and metric deltas, with improvement/regression labels when direction is known
