from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence, Optional
import os
import subprocess
import time
import sys
import threading

@dataclass(frozen=True)
class CmdResult:
    cmd: tuple[str, ...]
    cwd: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int

def run_cmd(
        cmd: Sequence[str],
        *,
        cwd: str | Path | None = None,
        env: Optional[Mapping[str, str]] = None,
        timeout_sec: int | None = None,
) -> CmdResult:
    """
    Run a command (tokenized list of strings) and capture stdout/stderr.

    Design decisions:
      - We do NOT throw on non-zero exit codes (we return them). The caller decides.
      - We *do* raise a clear exception if the program cannot be launched
        (e.g., executable not found).
    """
    if not cmd or not all(isinstance(x, str) and x for x in cmd):
        raise ValueError("cmd must be a non-empty sequence of non-empty strings")
    
    cwd_str = str(cwd) if cwd is not None else os.getcwd()

    merged_env = os.environ.copy()
    if env:
        # Only allow string-to-string overrides
        for k, v in env.items():
            merged_env[str(k)] = str(v)

    start = time.perf_counter()

    try:
        proc = subprocess.run(
            list(cmd),
            cwd=cwd_str,
            env=merged_env,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except FileNotFoundError as e:
        # e.g. "cmake" not on PATH
        raise RuntimeError(f"Comand not found: {cmd[0]!r}. Is it installed and on PATH?") from e
    
    dur_ms = int((time.perf_counter() - start) * 1000)

    return CmdResult(
        cmd=tuple(cmd),
        cwd=cwd_str,
        exit_code=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
        duration_ms=dur_ms
    )

def run_cmd_live(
        cmd: Sequence[str],
        *,
        cwd: str | Path | None = None,
        env: Optional[Mapping[str, str]] = None,
) -> CmdResult:
    """
    Run a command and stream output live, while capturing stdout and stderr separately.

    Design choice (v2):
      - We read stdout and stderr concurrently (threads) to avoid deadlocks.
      - Console shows stdout on stdout and stderr on stderr.
    """

    if not cmd or not all(isinstance(x, str) and x for x in cmd):
        raise ValueError("cmd must be a non-empty sequence of non-emtpy strings")

    cwd_str = str(cwd) if cwd is not None else os.getcwd()

    merged_env = os.environ.copy()
    if env:
        for k, v in env.items():
            merged_env[str(k)] = str(v)

    start = time.perf_counter()

    try:
        proc = subprocess.Popen(
            list(cmd),
            cwd=cwd_str,
            env=merged_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # line-buffered best-effort
        )
    except FileNotFoundError as e:
        raise RuntimeError(f"Command not found: {cmd[0]!r}. Is it installed and on Path?") from e

    assert proc.stdout is not None
    assert proc.stderr is not None

    out_chunks: list[str] = []
    err_chunks: list[str] = []

    def _pump(stream, chunks: list[str], sink):
        for line in stream:
            chunks.append(line)
            print(line, end="", file=sink)

    t_out = threading.Thread(target=_pump, args=(proc.stdout, out_chunks, sys.stdout), daemon=True)
    t_err = threading.Thread(target=_pump, args=(proc.stderr, err_chunks, sys.stderr), daemon=True)

    t_out.start()
    t_err.start()

    exit_code = proc.wait()
    t_out.join()
    t_err.join()

    dur_ms = int((time.perf_counter() - start) * 1000)

    return CmdResult(
        cmd=tuple(cmd),
        cwd=cwd_str,
        exit_code=exit_code,
        stdout="".join(out_chunks),
        stderr="".join(err_chunks),
        duration_ms=dur_ms,
    )