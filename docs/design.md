# CUDA Agent Service - Design Document

## 1. Purpose
Build a reusable, service-grade agentic performance and validation assistant for C++/CUDA projects. The system should provide developer value without requiring "AI magic": it runs repeatable experiments (build -> test -> benchmark -> parse -> store -> report), and later can add an agent loop (profile -> propose -> apply -> verify -> accept/reject).

Implementation direction:

- Initial product focus is C++/CUDA.
- The orchestration model should remain generic enough to support other local project types later, including Python, JavaScript, Java, and similar ecosystems where repeatable build/test/run/report workflows are useful.
- Language-specific behavior should live in adapters, presets, templates, and project commands rather than in a language-specific core schema.

## 2. Non-goals (for early versions)

- Not a fully autonomous CUDA kernel optimizer.
- Not a replacement for human performance engineering.
- Not a one-off script tied to a single sample repo.

## 3. Core design principles

1. Orchestration first, intelligence second: useful even with zero LLM.
2. Receipt-driven: every claim backed by logs, metrics, artifacts.
3. Safe by default: no changes accepted unless tests pass and benchmarks improve.
4. Modular adapters: swap build/profiling/test tooling via thin interfaces.
5. Config-first: projects and targets defined via config files, not hardcoded.
6. Language-agnostic core: model work as build/test/run/parse/store/report so the same system can later support multiple ecosystems.

## 4. Primary user value

- One command to produce a reproducible performance baseline.
- Automatic collection of metrics and artifacts for debugging regressions.
- Clean reports for humans and structured outputs for CI.
- Later: a controlled loop that suggests or tries improvements with gating.

## 5. System overview

The system is a pipeline runner with plug-in adapters and a persistent run store.

### 5.1 Entry points

- CLI (first-class): run experiments, compare runs, export reports.
- HTTP API (optional later): submit runs remotely, retrieve status and artifacts.

### 5.2 Core components

1. Orchestrator: executes pipeline stages and enforces gating rules.
2. Adapters: execute external tools (build, test, benchmark, profiling).
3. Target definitions: define how to run a benchmark and parse outputs.
4. Storage: artifacts on disk plus metadata in SQLite.
5. Reporting: Markdown/JSON summaries, later HTML.
6. Agent loop (later): choose next actions based on profiler and metrics.

## 6. Operational flow (baseline)

### MVP-1: Benchmark Service (no profilers, no patches)

1. Load config
2. Prepare workspace
3. Build
4. Test (optional)
5. Benchmark (N runs)
6. Parse metrics
7. Store artifacts and metadata
8. Generate report

### MVP-2: Profiling (multimodal artifacts)

Adds:

- Run Nsight Systems and/or Nsight Compute
- Store profiler outputs as artifacts
- Extract high-level signals into metrics

### MVP-3: Agentic experimentation (no code changes yet)

Adds:

- Parameter sweeps (run variants)
- Regression detection, stability analysis
- Recommendation generation (human-facing)

### MVP-4: Safe patch loop (gated changes)

Adds:

- Apply candidate changes in an isolated workspace
- Re-run tests and benchmarks
- Accept only on improvement thresholds; else revert

## 7. Configuration-first design

### 7.1 Config file philosophy

- A project is defined by commands and environment.
- A target is defined by how to run and how to parse.
- The orchestrator stays generic.
- The config should not require separate top-level sections per programming language by default; language/toolchain specifics can be expressed through commands, adapters, and presets.

### 7.2 Proposed config structure (YAML)

`agent.yaml` (conceptual):

- `project`: repo/workspace info
- `build`: how to configure/build
- `test`: how to validate correctness
- `targets`: runnable benchmarks with parsers
- `profiling`: optional profiling tool config
- `storage`: where to store runs/artifacts
- `policy`: gating thresholds and run controls

Example (high-level sketch):

```yaml
version: 1
project:
  name: cuda-samples
  workspace: ./

build:
  generator: ninja
  configure:
    cmd: ["cmake", "-S", ".", "-B", "build", "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_CUDA_ARCHITECTURES=75"]
  build:
    cmd: ["cmake", "--build", "build"]

test:
  enabled: false
  cmd: []

targets:
  - id: matrixmul
    display_name: Matrix Multiply (CUDA sample)
    run:
      cmd: ["./build/bin/matrixMul.exe"]
      runs: 10
      warmup_runs: 1
    parse:
      kind: regex
      rules:
        - name: kernel_ms
          pattern: "Time=\\s*([0-9.]+)\\s*msec"
          group: 1
          type: float
        - name: gflops
          pattern: "Performance=\\s*([0-9.]+)\\s*GFlop/s"
          group: 1
          type: float
        - name: pass
          pattern: "Result\\s*=\\s*(PASS|FAIL)"
          group: 1
          type: enum

profiling:
  enabled: false

storage:
  root: ./runs
  db: ./runs/runs.db

policy:
  accept_if:
    tests_pass: true
    improvement_pct_min: 3.0
  fail_if:
    regress_pct_max: 1.0
```

Notes:

- Paths are conceptual; the agent should resolve platform-specific executable locations.
- Parser `kind` can expand later (regex, JSON, custom script).
- For non-compiled or non-executable-first ecosystems, equivalent command-based target definitions may be preferable to executable discovery.

## 8. Data model (what gets stored)

### 8.1 Run record (SQLite)

- `run_id` (uuid)
- `project_name`, `target_id`
- `git_commit` (optional)
- `status` (queued/running/succeeded/failed)
- `started_at`, `finished_at`
- `toolchain` metadata (nvcc version, compiler version)
- `notes` (free text)

### 8.2 Metrics

For each run:

- `kernel_ms` (float)
- `gflops` (float)
- `pass` (bool)
- derived stats: avg/min/max/stddev

### 8.3 Artifacts (filesystem plus index)

Folder layout (example):

```text
runs/
  <run_id>/
    config_snapshot.yaml
    env.json
    build.log
    test.log
    bench/
      run_001.stdout.txt
      run_001.stderr.txt
      run_001.metrics.json
      ...
    profiling/
      capture.nsys-rep
      kernel.ncu-rep
    summary.json
    report.md
```

## 9. Adapter interfaces (conceptual)

Each adapter should return structured results:

- exit code
- stdout/stderr
- wall time
- produced files

Extension intent:

- Adapters are the main extension point for supporting additional toolchains and languages while preserving the same run model.
- Future examples could include Python test/benchmark adapters, JavaScript package-script adapters, or Java build/run adapters.

### 9.1 BuildAdapter

- `configure()`
- `build()`

### 9.2 TestAdapter

- `run_tests()`

### 9.3 BenchmarkAdapter

- `run_once()`
- `run_many()` (with warmup, repetitions)

### 9.4 ProfilerAdapter

- `profile_systems()` (Nsight Systems)
- `profile_compute()` (Nsight Compute)

## 10. Reporting

Reports must be readable and comparable.

Minimum report sections:

- What ran (project/target/commit/toolchain)
- Pass/fail summary
- Performance summary (avg/min/max/stddev)
- Run-to-run stability notes
- Artifact list (paths)
- If comparing: delta vs baseline

Outputs:

- `report.md` (human)
- `summary.json` (machine)

## 11. CLI (minimum commands)

- `agent init` -> scaffold `agent.yaml`
- `agent run <target>` -> execute pipeline
- `agent list` -> show past runs
- `agent report <run_id>` -> re-render report
- `agent compare <run_id_a> <run_id_b>` -> delta summary

## 12. Failure handling

- Build/test failures: mark run failed, store logs, stop.
- Benchmark failures/parse failures: mark run failed or partial, store raw output.
- Profiling failures: mark profiling stage failed but allow baseline bench if configured.
- Never silently succeed: always emit status and reason.

## 13. Security and safety boundaries

- Commands come from config: treat as trusted only in local dev; warn in service mode.
- For service mode: run in a sandboxed workspace; avoid arbitrary remote execution.
- Never auto-apply patches by default; require explicit enable and gating.

Cross-language note:

- Supporting more languages increases the variety of commands and tools invoked, but should not change the core safety boundary: commands remain explicit, config-defined, and auditable.

## 14. Implementation roadmap

### Milestone 1 - Baseline runner

- Config loader
- Build plus run target N times
- Regex parser
- Artifact storage
- Markdown plus JSON report

### Milestone 2 - Run history plus compare

- SQLite run index
- Compare two runs

### Milestone 3 - Profiling artifacts

- Nsight Systems capture plus artifact storage
- Extract a small set of headline metrics

### Milestone 4 - Agentic experiments

- Parameter sweeps
- Stability detection
- Recommendations

### Milestone 5 - Safe patch loop

- Patch application (isolated)
- Accept/reject based on tests and performance thresholds

---

## Working definition

A "run" is an immutable experiment: same config snapshot, toolchain metadata, artifacts, metrics, and report. The system's credibility comes from repeatability and receipts.

That definition should hold regardless of programming language or toolchain.
