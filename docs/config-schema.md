# CUDA Agent Config Schema

This document defines the currently implemented config schema for `version: 1`.

It describes the schema that the code validates and executes today. The design document includes future directions, but this page is the source of truth for the current implementation.

## Overview

Design goals reflected by the current schema:

- config-first orchestration
- arbitrary target ids
- reusable across local C++/CUDA projects
- extensible toward other local project types and languages
- repeatable runs with receipts and parsed metrics

Current implementation note:

- target execution supports either `run.exe_glob` or `run.cmd`
- `run.cmd` is the primary recommended form for new configs
- parsing is optional and currently supports `kind: regex` only
- the schema is intentionally language-agnostic even though current examples are CUDA-focused

Abstraction intent:

- top-level config models project orchestration, not programming-language categories
- language/toolchain specifics belong in command lists, target definitions, and future adapters or presets
- this avoids locking the schema into separate `python`, `javascript`, `java`, or similar top-level sections too early

## Top-Level Schema

```yaml
version: 1

project:
  workspace: <string>
  name: <string, optional>

env: <mapping<string, scalar>, optional>

build:
  configure_cmd: <list[string]>
  build_cmd: <list[string]>
  build_dir: <string, optional>

test:
  enabled: <bool, optional>
  cmd: <list[string], optional>

storage:
  root: <string>
  db: <string, optional>

policy:
  fail_fast: <bool, optional>
  min_pass_rate: <number 0.0..1.0, optional>

targets:
  <target_id>:
    description: <string, optional>
    run: ...
    parse: ...        # optional
    success: ...      # optional
```

## Required Top-Level Keys

| Key | Type | Required | Notes |
|---|---|---|---|
| `version` | integer | yes | Must equal `1`. |
| `project` | mapping | yes | Must include `project.workspace`. |
| `build` | mapping | yes | Must include `configure_cmd` and `build_cmd`. |
| `storage` | mapping | yes | Must include `storage.root`. |
| `targets` | mapping | yes | Must define at least one target. |

## Top-Level Sections

### `version`

| Field | Type | Required | Rules |
|---|---|---|---|
| `version` | integer | yes | Must equal `1`. |

### `project`

| Field | Type | Required | Rules |
|---|---|---|---|
| `project.workspace` | string | yes | Non-empty. Relative paths resolve from the directory containing the config file. |
| `project.name` | string | no | Non-empty when present. Used for reports and metadata only. |

### `env`

`env` is optional. When present, it must be a mapping of environment variable names to scalar values.

Allowed value types:

- string
- integer
- float
- boolean

Rules:

- keys must be non-empty strings
- values are stringified before subprocess execution
- values apply to build, test, and target execution

### `build`

| Field | Type | Required | Rules |
|---|---|---|---|
| `build.configure_cmd` | list of string | yes | Non-empty strings only. |
| `build.build_cmd` | list of string | yes | Non-empty strings only. |
| `build.build_dir` | string | no | Optional convenience value for interpolation; not required by the runner. |

Execution rules:

- both commands run in the resolved `project.workspace`
- `env` overrides are applied
- configure runs first; build does not run if configure fails

Cross-language note:

- these commands are intentionally generic
- they may represent CMake/Ninja today, but could represent Python, JavaScript, Java, or other toolchain commands in future project configs

### `test`

`test` is optional.

| Field | Type | Required | Rules |
|---|---|---|---|
| `test.enabled` | boolean | no | Defaults to `false` when omitted. |
| `test.cmd` | list of string | no | Must be non-empty if `test.enabled: true`. |

Execution rules:

- tests run after build and before target execution
- tests run in the resolved `project.workspace`
- if tests fail, the pipeline stops and the run is marked failed

Cross-language note:

- the test section is already generic and can represent commands such as `ctest`, `pytest`, `npm test`, `vitest`, `gradle test`, or `mvn test`

### `storage`

| Field | Type | Required | Rules |
|---|---|---|---|
| `storage.root` | string | yes | Non-empty. Relative paths resolve from the directory containing the config file. |
| `storage.db` | string | no | SQLite path for the run index. Defaults to `<storage.root>/runs.db` when omitted. Relative paths resolve from the directory containing the config file. |

### `policy`

`policy` is optional.

| Field | Type | Required | Rules |
|---|---|---|---|
| `policy.fail_fast` | boolean | no | Accepted by validation. Not currently used to alter runtime behavior. |
| `policy.min_pass_rate` | number | no | Must be between `0.0` and `1.0` inclusive. Defaults to `1.0`. |

Runtime use:

- the run summary status is `PASS` only if the fraction of passing measured runs is at least `policy.min_pass_rate`

## `targets`

`targets` must be a non-empty mapping. Target ids are arbitrary non-empty strings.

Each target definition may contain:

| Field | Type | Required | Notes |
|---|---|---|---|
| `description` | string | no | Human-readable description only. |
| `run` | mapping | yes | Defines executable discovery and repetition counts. |
| `parse` | mapping | no | Defines stdout parsing rules. |
| `success` | mapping | no | Defines pass/fail interpretation. |

Cross-language note:

- the target abstraction is meant to represent any runnable benchmark, smoke test, validation binary, script entry point, or packaged application run
- target ids are labels chosen by the project, not language- or framework-specific reserved names

## Target `run` Section

```yaml
targets:
  <target_id>:
    run:
      cmd: <list[string], optional>
      exe_glob: <string, optional>
      args: <list[string], optional>
      runs: <int, optional>
      warmup_runs: <int, optional>
```

| Field | Type | Required | Default | Rules |
|---|---|---|---:|---|
| `run.cmd` | list of string | conditional | none | Define exactly one of `run.exe_glob` or `run.cmd`. Runs in `project.workspace`. |
| `run.exe_glob` | string | conditional | none | Define exactly one of `run.exe_glob` or `run.cmd`. Relative paths resolve from `project.workspace`. |
| `run.args` | list of string | no | `[]` | Strings only. |
| `run.runs` | integer | no | `1` | Must be `>= 1`. |
| `run.warmup_runs` | integer | no | `0` | Must be `>= 0`. |

Mode rules:

- prefer `run.cmd` for new configs
- each target must define exactly one of `run.exe_glob` or `run.cmd`
- `run.args` is only valid with `run.exe_glob`
- `run.cmd` is already a fully tokenized command list and should include all arguments directly

Executable resolution rules:

- if `exe_glob` contains no glob metacharacters, it is treated as a direct path
- otherwise it is treated as a recursive glob
- if multiple files match, the newest modified file is selected
- target execution runs from the executable's parent directory so local DLL/shared-library lookup works more reliably

Executable-discovery note:

- `run.exe_glob` exists as a compatibility and convenience mode for compiled executable workflows
- if you can express a target directly as a command, `run.cmd` is the preferred form

Command execution rules:

- `run.cmd` is executed exactly as specified
- command execution runs in the resolved `project.workspace`
- this mode is the intended path for cleaner support across Python, JavaScript, Java, and similar ecosystems

## Target `parse` Section

`parse` is optional. If omitted, the target produces no parsed metrics and only exit-code-based success checks are available.

Current supported form:

```yaml
targets:
  <target_id>:
    parse:
      kind: regex
      rules:
        - name: <string>
          pattern: <string>
          type: <float|int|enum|str, optional>
          units: <string, optional>
          better: <higher|lower, optional>
          required: <bool, optional>
          enum: <list[string], required for enum type>
```

| Field | Type | Required | Rules |
|---|---|---|---|
| `parse.kind` | string | yes | Must equal `regex`. |
| `parse.rules` | list | yes | Must be non-empty. |

Per-rule fields:

| Field | Type | Required | Default | Rules |
|---|---|---|---:|---|
| `name` | string | yes | none | Must be unique within the target. |
| `pattern` | string | yes | none | Python regex pattern applied to stdout. |
| `type` | string | no | `str` | One of `float`, `int`, `enum`, `str`. |
| `units` | string | no | none | Metadata only. |
| `better` | string | no | none | Optional comparison hint. Must be `higher` or `lower`. |
| `required` | boolean | no | `false` | Parse fails for that run if the pattern does not match. |
| `enum` | list of string | conditional | none | Required only for `type: enum`. |

Parsing rules:

- parsing consumes stdout only
- the first capture group is used if present; otherwise the whole match
- parse failure for a measured run counts as a failed measured run in the summary
- `better` lets `compare` classify metric changes as improvements or regressions; when omitted, `compare` falls back to name/unit heuristics

## Target `success` Section

`success` is optional.

```yaml
targets:
  <target_id>:
    success:
      exit_code: <int, optional>
      pass_rule: <string, optional>
```

| Field | Type | Required | Default | Rules |
|---|---|---|---:|---|
| `success.exit_code` | integer | no | `0` | Must be `>= 0`. |
| `success.pass_rule` | string | no | none | Must reference a parse rule name defined under the same target. |

Runtime rules:

- a measured run passes only if its process exit code equals `success.exit_code` or the default `0`
- if `success.pass_rule` is set, that metric must parse to `true` or the string `PASS`
- warmup runs are not counted toward pass/fail totals

## Path Resolution Rules

Relative paths are resolved as follows:

| Field | Base |
|---|---|
| config file path itself | current working directory used to invoke the CLI |
| `project.workspace` | directory containing the config file |
| `storage.root` | directory containing the config file |
| `targets.<id>.run.cmd` | command is executed from resolved `project.workspace` |
| `targets.<id>.run.exe_glob` | resolved `project.workspace` |

## Interpolation Rules

String values support single-pass `${...}` interpolation.

Examples:

```yaml
build:
  build_dir: build-ninja
  configure_cmd:
    - cmake
    - -B
    - "${build.build_dir}"
```

Rules:

- interpolation applies to string values only, not keys
- references resolve against the loaded config mapping
- referenced values must be scalar
- escape a literal placeholder with `\${...}`
- interpolation occurs before validation

## Generic Example

```yaml
version: 1

project:
  name: my-cuda-project
  workspace: ../my-project

build:
  build_dir: build
  configure_cmd:
    - cmake
    - -S
    - .
    - -B
    - "${build.build_dir}"
    - -G
    - Ninja
    - -DCMAKE_BUILD_TYPE=Release
  build_cmd:
    - cmake
    - --build
    - "${build.build_dir}"

test:
  enabled: false
  cmd: []

storage:
  root: ./runs

policy:
  min_pass_rate: 1.0

targets:
  smoke:
    description: Basic runtime sanity check
    run:
      cmd: ["python", "-m", "my_project.smoke_check"]
      runs: 1

  benchmark:
    description: Headless benchmark with parsed metrics
    run:
      cmd: ["python", "-m", "my_project.benchmark"]
      runs: 10
      warmup_runs: 1
    parse:
      kind: regex
      rules:
        - name: kernel_ms
          pattern: "Time=\\s*([0-9.]+)\\s*msec"
          type: float
          units: ms
          better: lower
          required: true
        - name: status
          pattern: "(PASS|FAIL)"
          type: enum
          enum: ["PASS", "FAIL"]
          required: true
    success:
      exit_code: 0
      pass_rule: status
```

Additional examples in this repo:

- `examples/annotated_cuda_samples.yaml`
- `examples/python_cmd.yaml`
- `examples/node_cmd.yaml`

## Relationship To The Design Document

The design document describes a more general long-term direction, including richer adapter models and potentially command-based target definitions. The current schema already matches the design in the important ways:

- arbitrary target ids
- config-defined projects and targets
- optional parsing
- policy-driven pass/fail summary
- artifact-oriented runs
- a core model that can extend beyond CUDA-specific projects

Current implementation gaps relative to the design:

- no profiler schema yet
- no first-class language/toolchain presets or adapters yet
