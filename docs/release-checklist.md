# Release Checklist

This checklist is for freezing and publishing the current MVP 2 state of `cuda-agent`.

## Scope Check

Confirm the release description matches the implementation:

- config-driven local runner
- build, optional test, run, parse, store, report
- SQLite-backed run index
- `runs`, `report`, and `compare`
- generic command-based targets via `run.cmd`
- executable-discovery targets via `run.exe_glob`

Do not describe the project as having first-class language-specific adapters for Python, Node.js, or Java yet. The current release supports those ecosystems through generic command-based targets.

## Repo Hygiene

- remove local-only files and outputs before publishing - OK
- verify `runs/` is not committed - OK
- verify `examples/runs/` is not committed - OK
- verify no stray scratch files remain in the repo root
- confirm the README, CLI reference, and config schema agree on the current feature set - OK
- choose and add a real `LICENSE` file before public release - OK
- ensure `cuda_samples.yaml` remains the primary runnable CUDA config and `examples/annotated_cuda_samples.yaml` remains the documented template

## Packaging Check - DONE

From the repo root in a fresh virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e .[dev]
.\.venv\Scripts\cuda-agent.exe --help
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider --basetemp .pytest_tmp tests
```

Expected result:

- install succeeds
- `cuda-agent` console script is available
- test suite passes

## CUDA Manual Test - DONE

Run these from the repo root in a Visual Studio developer shell or another shell where both `cl.exe` and `nvcc.exe` are on `PATH`.

```powershell
.\.venv\Scripts\cuda-agent.exe --config cuda_samples.yaml validate
.\.venv\Scripts\cuda-agent.exe --config cuda_samples.yaml list
.\.venv\Scripts\cuda-agent.exe --config cuda_samples.yaml build --live
.\.venv\Scripts\cuda-agent.exe --config cuda_samples.yaml run deviceQuery --live
.\.venv\Scripts\cuda-agent.exe --config cuda_samples.yaml run matrixMul --live
.\.venv\Scripts\cuda-agent.exe --config cuda_samples.yaml runs
.\.venv\Scripts\cuda-agent.exe --config cuda_samples.yaml runs --target matrixMul
.\.venv\Scripts\cuda-agent.exe --config cuda_samples.yaml runs --status FAIL
.\.venv\Scripts\cuda-agent.exe --config cuda_samples.yaml report <run_id>
.\.venv\Scripts\cuda-agent.exe --config cuda_samples.yaml compare <older_run_id> <newer_run_id>
```

Verify:

- build succeeds
- both CUDA sample targets run successfully
- reports and summaries are written
- run history indexing works
- compare shows direction-aware improvement/regression output

## Python Manual Test - DONE

Use the bundled fixture project at `fixtures/python_smoke/agent.yaml`.

Recommended minimum flow:

```powershell
.\.venv\Scripts\cuda-agent.exe --config fixtures\python_smoke\agent.yaml validate
.\.venv\Scripts\cuda-agent.exe --config fixtures\python_smoke\agent.yaml show --pretty
.\.venv\Scripts\cuda-agent.exe --config fixtures\python_smoke\agent.yaml build --live
.\.venv\Scripts\cuda-agent.exe --config fixtures\python_smoke\agent.yaml run benchmark --live
.\.venv\Scripts\cuda-agent.exe --config fixtures\python_smoke\agent.yaml runs
.\.venv\Scripts\cuda-agent.exe --config fixtures\python_smoke\agent.yaml report <run_id>
.\.venv\Scripts\cuda-agent.exe --config fixtures\python_smoke\agent.yaml compare <older_run_id> <newer_run_id>
```

Verify:

- working directory resolution is correct
- `run.cmd` launches correctly
- parse rules extract expected metrics
- compare classifies lower-is-better metrics such as latency/time correctly

Optional compare variation:

- change `env.BENCH_PROFILE` in `fixtures/python_smoke/agent.yaml` from `fast` to `slow` between two runs to force a regression signal

## Node.js Manual Test - DONE

Use the bundled fixture project at `fixtures/node_smoke/agent.yaml`.

Recommended minimum flow:

```powershell
.\.venv\Scripts\cuda-agent.exe --config fixtures\node_smoke\agent.yaml validate
.\.venv\Scripts\cuda-agent.exe --config fixtures\node_smoke\agent.yaml show --pretty
.\.venv\Scripts\cuda-agent.exe --config fixtures\node_smoke\agent.yaml build --live
.\.venv\Scripts\cuda-agent.exe --config fixtures\node_smoke\agent.yaml run benchmark --live
.\.venv\Scripts\cuda-agent.exe --config fixtures\node_smoke\agent.yaml runs
.\.venv\Scripts\cuda-agent.exe --config fixtures\node_smoke\agent.yaml report <run_id>
.\.venv\Scripts\cuda-agent.exe --config fixtures\node_smoke\agent.yaml compare <older_run_id> <newer_run_id>
```

Verify:

- npm-based commands execute cleanly on Windows
- parse rules extract throughput and latency metrics
- compare classifies higher-is-better metrics such as throughput correctly

Optional compare variation:

- change `env.BENCH_PROFILE` in `fixtures/node_smoke/agent.yaml` from `fast` to `slow` between two runs to force a regression signal

## Documentation Check

- README install instructions work as written - OK
- README quickstart commands work as written - OK
- `docs/cli.md` matches current command behavior - OK
- `docs/config-schema.md` matches current validation rules - OK
- example configs validate successfully - OK

## Portfolio Site Page
- Write MD file for Portfolio Site
- Get Relevant Screenshots

## Publish Decision

Release when all of the following are true:

- automated tests pass
- CUDA manual flow passes
- Python manual flow passes
- Node.js manual flow passes
- package install path works in a fresh venv
- docs match observed behavior
- license has been added
