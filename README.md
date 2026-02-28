# cuda-agent
[![Tests](https://github.com/bju12290/cuda-agent/actions/workflows/tests.yml/badge.svg)](https://github.com/bju12290/cuda-agent/actions/workflows/tests.yml)

Config-driven build, test, benchmark, compare, and reporting runner for local software projects, with an initial focus on C++/CUDA workflows.

> Current release: MVP 2

Highlights:

- reproducible local runs with stored artifacts and summaries
- SQLite-backed run history plus `runs`, `report`, and `compare`
- generic `run.cmd` support for Python and Node.js style workflows
- executable-discovery support via `run.exe_glob` for CUDA-style binaries

The core model is intentionally language-agnostic:

- project workspace
- build step
- optional test step
- runnable targets
- parsed metrics
- artifact storage
- policy-based pass/fail rules

Language and toolchain specifics live in commands, target definitions, and future adapters or presets. The current examples are CUDA-oriented, but the schema is being kept generic on purpose.

Recommended target style:

- prefer `run.cmd` for new configs
- use `run.exe_glob` as a convenience mode for compiled executable workflows

## Prerequisites

General:

- Python 3.10+
- Windows is the primary validated environment for this repo today

For the bundled fixture projects:

- Python is enough for `fixtures/python_smoke`
- Node.js is required for `fixtures/node_smoke`

For the CUDA sample config:

- Microsoft C++ build tools available on `PATH` as `cl.exe`
- CUDA toolkit available on `PATH` as `nvcc.exe`
- an external CUDA samples checkout at the path expected by `cuda_samples.yaml`

## Install

From the repo root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e .[dev]
```

After install, either use the console script:

```powershell
.\.venv\Scripts\cuda-agent.exe --help
```

or the module form:

```powershell
.\.venv\Scripts\python.exe -m cuda_agent.cli --help
```

## Quickstart

If you want the least-surprising local validation path, start with the fixture projects in `fixtures/`.

The root `cuda_samples.yaml` file is the primary runnable CUDA example in this repo. The annotated reference template lives at `examples/annotated_cuda_samples.yaml`.

Validate a config:

```powershell
.\.venv\Scripts\cuda-agent.exe --config cuda_samples.yaml validate
```

List targets:

```powershell
.\.venv\Scripts\cuda-agent.exe --config cuda_samples.yaml list
```

Run a target:

```powershell
.\.venv\Scripts\cuda-agent.exe --config cuda_samples.yaml run matrixMul --live
```

List indexed runs:

```powershell
.\.venv\Scripts\cuda-agent.exe --config cuda_samples.yaml runs --limit 20
```

Compare two runs:

```powershell
.\.venv\Scripts\cuda-agent.exe --config cuda_samples.yaml compare <older_run_id> <newer_run_id>
```

## What It Does

The current implementation provides:

- config load, interpolation, and validation
- configure/build execution
- optional test execution
- repeated target runs with warmups
- regex-based stdout metric parsing
- receipt-oriented artifact storage
- Markdown report generation
- SQLite-backed run indexing
- report lookup by run id
- compare output with direction-aware improvement/regression classification

## Current Support

Supported well today:

- Windows-oriented local workflows
- CUDA sample-style executable runs through `run.exe_glob`
- generic command-based targets through `run.cmd`
- Python and Node.js projects expressed as normal commands

Not shipped yet:

- profiler capture
- HTTP API
- patch loop / autonomous optimization
- first-class language-specific presets or adapters

## Documentation

- [Design](docs/design.md)
- [CLI Reference](docs/cli.md)
- [Config Schema](docs/config-schema.md)
- [Testing Guide](docs/testing.md)

## Examples And Fixtures

- [Annotated CUDA Samples Template](examples/annotated_cuda_samples.yaml)
- [Generic Command Example](examples/python_cmd.yaml)
- [Node.js Command Example](examples/node_cmd.yaml)
- [Python Fixture Project](fixtures/python_smoke/agent.yaml)
- [Node.js Fixture Project](fixtures/node_smoke/agent.yaml)
