from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    project_name TEXT,
    target_id TEXT NOT NULL,
    status TEXT NOT NULL,
    stage TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    launch TEXT,
    run_dir TEXT NOT NULL,
    summary_path TEXT,
    report_path TEXT,
    live INTEGER NOT NULL,
    message TEXT
);
"""


@dataclass(frozen=True)
class IndexedRun:
    run_id: str
    project_name: str | None
    target_id: str
    status: str
    stage: str
    started_at: str
    finished_at: str
    launch: str | None
    run_dir: str
    summary_path: str | None
    report_path: str | None
    live: bool
    message: str | None


def resolve_db_path(cfg: Mapping[str, Any], *, config_path: str) -> Path:
    storage = cfg.get("storage", {})
    root_raw = storage.get("root", "./runs") if isinstance(storage, dict) else "./runs"
    db_raw = storage.get("db") if isinstance(storage, dict) else None

    base = Path(config_path).resolve().parent
    root = (base / root_raw).resolve() if not Path(root_raw).is_absolute() else Path(root_raw).resolve()
    root.mkdir(parents=True, exist_ok=True)

    if isinstance(db_raw, str) and db_raw.strip():
        db_path = Path(db_raw)
        return (base / db_path).resolve() if not db_path.is_absolute() else db_path.resolve()

    return (root / "runs.db").resolve()


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path) -> None:
    with _connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL)


def upsert_run(db_path: Path, run: IndexedRun) -> None:
    with _connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.execute(
            """
            INSERT INTO runs (
                run_id,
                project_name,
                target_id,
                status,
                stage,
                started_at,
                finished_at,
                launch,
                run_dir,
                summary_path,
                report_path,
                live,
                message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                project_name = excluded.project_name,
                target_id = excluded.target_id,
                status = excluded.status,
                stage = excluded.stage,
                started_at = excluded.started_at,
                finished_at = excluded.finished_at,
                launch = excluded.launch,
                run_dir = excluded.run_dir,
                summary_path = excluded.summary_path,
                report_path = excluded.report_path,
                live = excluded.live,
                message = excluded.message
            """,
            (
                run.run_id,
                run.project_name,
                run.target_id,
                run.status,
                run.stage,
                run.started_at,
                run.finished_at,
                run.launch,
                run.run_dir,
                run.summary_path,
                run.report_path,
                int(run.live),
                run.message,
            ),
        )


def _row_to_indexed_run(row: sqlite3.Row) -> IndexedRun:
    return IndexedRun(
        run_id=str(row["run_id"]),
        project_name=str(row["project_name"]) if row["project_name"] is not None else None,
        target_id=str(row["target_id"]),
        status=str(row["status"]),
        stage=str(row["stage"]),
        started_at=str(row["started_at"]),
        finished_at=str(row["finished_at"]),
        launch=str(row["launch"]) if row["launch"] is not None else None,
        run_dir=str(row["run_dir"]),
        summary_path=str(row["summary_path"]) if row["summary_path"] is not None else None,
        report_path=str(row["report_path"]) if row["report_path"] is not None else None,
        live=bool(row["live"]),
        message=str(row["message"]) if row["message"] is not None else None,
    )


def get_run(db_path: Path, run_id: str) -> IndexedRun | None:
    if not db_path.exists():
        return None

    with _connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        row = conn.execute(
            """
            SELECT
                run_id,
                project_name,
                target_id,
                status,
                stage,
                started_at,
                finished_at,
                launch,
                run_dir,
                summary_path,
                report_path,
                live,
                message
            FROM runs
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()

    return _row_to_indexed_run(row) if row is not None else None


def list_runs(
    db_path: Path,
    *,
    limit: int = 20,
    target_id: str | None = None,
    status: str | None = None,
) -> list[IndexedRun]:
    if not db_path.exists():
        return []

    where_clauses: list[str] = []
    params: list[object] = []

    if isinstance(target_id, str) and target_id.strip():
        where_clauses.append("LOWER(target_id) = LOWER(?)")
        params.append(target_id.strip())

    if isinstance(status, str) and status.strip():
        where_clauses.append("UPPER(status) = UPPER(?)")
        params.append(status.strip().upper())

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    params.append(int(limit))

    with _connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        rows = conn.execute(
            f"""
            SELECT
                run_id,
                project_name,
                target_id,
                status,
                stage,
                started_at,
                finished_at,
                launch,
                run_dir,
                summary_path,
                report_path,
                live,
                message
            FROM runs
            {where_sql}
            ORDER BY finished_at DESC, run_id DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()

    return [_row_to_indexed_run(row) for row in rows]
