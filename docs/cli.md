# CUDA Agent CLI Reference

This document describes the currently implemented CLI surface for `cuda-agent`.

Scope note:

- current examples are CUDA-oriented
- the CLI shape is intended to remain language-agnostic
- future ecosystems such as Python, JavaScript, or Java should fit the same build/test/run/report workflow, even if they eventually use different presets or adapters
- `run.cmd` is the primary recommended target-launch form for new configs

## Invocation

```text
cuda-agent [--config PATH] <command> [command options]
```

Global options:

| Option | Type | Default | Description |
|---|---|---:|---|
| `--config` | path | `agent.yaml` | Path to the config file to load, interpolate, and validate. |

## Commands

### `validate`

Load the config, apply interpolation, validate the resolved schema, and exit.

```text
cuda-agent --config agent.yaml validate
```

Behavior:

- prints `OK` on success
- prints a config error to stderr on failure
- does not build or run anything

Exit codes:

| Code | Meaning |
|---:|---|
| `0` | Config loaded and validated successfully. |
| `2` | Config load, interpolation, or validation failed. |

### `list`

List target ids from the resolved config.

```text
cuda-agent --config agent.yaml list
```

Behavior:

- prints one target id per line
- order follows the resolved YAML mapping order

Exit codes:

| Code | Meaning |
|---:|---|
| `0` | Target ids were listed successfully. |
| `2` | Config load, interpolation, or validation failed. |

### `runs`

List indexed runs from the SQLite run index under `storage.db`.

```text
cuda-agent --config agent.yaml runs
cuda-agent --config agent.yaml runs --limit 50
cuda-agent --config agent.yaml runs --target matrixMul --status FAIL
```

Options:

| Option | Type | Default | Description |
|---|---|---:|---|
| `--limit` | integer | `20` | Maximum number of runs to print. Must be at least `1`. |
| `--target` | string | none | Filter indexed runs to a specific target id. Matching is case-insensitive. |
| `--status` | string | none | Filter indexed runs by status. Matching is case-insensitive; typical values are `PASS` and `FAIL`. |

Behavior:

- reads the run index from `storage.db`
- prints one indexed run per line in newest-first order
- applies `--target` and `--status` filters when provided
- prints `No indexed runs found.` when the database has no rows yet

Exit codes:

| Code | Meaning |
|---:|---|
| `0` | Run history printed successfully or no runs were found. |
| `2` | Config load, interpolation, validation, or argument validation failed. |

### `report <run_id>`

Print the stored Markdown report for an indexed run.

```text
cuda-agent --config agent.yaml report <run_id>
```

Behavior:

- resolves the run through `storage.db`
- prints the stored `report.md` content to stdout
- fails if the run id is not indexed or the report file no longer exists

Exit codes:

| Code | Meaning |
|---:|---|
| `0` | Report printed successfully. |
| `2` | Config load/validation failed, the run id was not indexed, or the report file was missing. |

### `compare <run_id_a> <run_id_b>`

Compare two indexed runs using their stored `summary.json` files.

```text
cuda-agent --config agent.yaml compare <run_id_a> <run_id_b>
```

Behavior:

- resolves both runs through `storage.db`
- loads each run's stored `summary.json`
- prints status deltas and shared numeric aggregate deltas
- classifies metric changes as improvements or regressions when direction can be determined from stored metadata or name/unit heuristics
- treats the first run id as the baseline and the second as the candidate

Exit codes:

| Code | Meaning |
|---:|---|
| `0` | Comparison printed successfully. |
| `2` | Config load/validation failed, a run id was not indexed, or a stored summary file was missing. |

### `show`

Print the resolved config as JSON after interpolation and validation.

```text
cuda-agent --config agent.yaml show
cuda-agent --config agent.yaml show --pretty
```

Options:

| Option | Type | Default | Description |
|---|---|---:|---|
| `--pretty` | flag | off | Pretty-print the JSON output. |

Exit codes:

| Code | Meaning |
|---:|---|
| `0` | Resolved config printed successfully. |
| `2` | Config load, interpolation, or validation failed. |

### `build`

Run the configured build pipeline:

1. `build.configure_cmd`
2. `build.build_cmd`

```text
cuda-agent --config agent.yaml build
cuda-agent --config agent.yaml build --live
```

Options:

| Option | Type | Default | Description |
|---|---|---:|---|
| `--live` | flag | off | Stream subprocess stdout/stderr live instead of printing captured output on failure. |

Behavior:

- both commands run in `project.workspace`
- `env` overrides are applied to both commands
- build stops if configure fails

Cross-language note:

- `build.configure_cmd` and `build.build_cmd` are generic command lists
- in other ecosystems these could map to commands like `python -m build`, `npm run build`, `gradle build`, `mvn package`, or similar

Exit codes:

| Code | Meaning |
|---:|---|
| `0` | Configure and build both succeeded. |
| non-zero | The subprocess exit code for configure or build, or `1` if unavailable. |
| `2` | Config load, interpolation, or validation failed. |

### `run <target>`

Run the baseline pipeline for a single target:

1. write run receipts directory
2. configure and build
3. optionally run tests
4. resolve target launch command
5. run warmups
6. run measured iterations
7. parse metrics
8. write `summary.json` and `report.md`

```text
cuda-agent --config agent.yaml run benchmark
cuda-agent --config agent.yaml run benchmark --live
```

Arguments:

| Argument | Type | Description |
|---|---|---|
| `target` | string | Target id under `targets`. |

Options:

| Option | Type | Default | Description |
|---|---|---:|---|
| `--live` | flag | off | Stream subprocess stdout/stderr live for build, test, and target runs. |

Behavior:

- creates a new immutable run directory under `storage.root`
- writes config snapshot, environment metadata, build/test logs, raw target stdout/stderr, per-run metrics JSON, summary JSON, and report Markdown
- validates pass/fail using target success rules plus `policy.min_pass_rate`

Cross-language note:

- targets can now use either `run.exe_glob` or `run.cmd`
- `run.cmd` is the preferred and more general path for Python, JavaScript, Java, and similar ecosystems
- `run.exe_glob` remains useful for compiled-binary workflows such as CUDA samples

Exit codes:

| Code | Meaning |
|---:|---|
| `0` | Run completed and summary status was `PASS`. |
| `1` | Run completed but summary status was `FAIL`, or build/test failed with exit code `1`. |
| `2` | Config failed to load or validate, target resolution failed, or summary/report generation failed. |
| other non-zero | Underlying configure, build, or test subprocess exit code when surfaced directly. |

## Run Artifacts

Each `run` command creates a directory under `storage.root` with this layout:

```text
runs/
  <run_id>/
    config_snapshot.yaml
    env.json
    build.log
    test.log
    bench/
      warmup_001.stdout.txt
      warmup_001.stderr.txt
      run_001.stdout.txt
      run_001.stderr.txt
      run_001.metrics.json
      ...
    summary.json
    report.md
```

Notes:

- `summary.json` contains per-run parsed metrics and numeric aggregates
- `report.md` is a human-readable rendering of the summary and artifact list
- completed and failed baseline runs are also indexed in `storage.db`

## Current Scope

Implemented now:

- `validate`
- `list`
- `runs`
- `report`
- `compare`
- `show`
- `build`
- `run`

Not implemented yet from the design roadmap:

- `init`
- profiler capture commands
- HTTP API

Multi-language status:

- the CLI model is already generic enough for broader project support
- first-class multi-language support is not implemented yet as dedicated presets or adapters
- target execution now supports a general command-based form, while executable discovery remains available for compiled workflows

Example configs in this repo:

- `examples/python_cmd.yaml`
- `examples/node_cmd.yaml`
