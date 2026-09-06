"""SQLite connection manager, schema initialization, and migration runner for SWARAJ core."""

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

SCHEMA_VERSION = 2

CREATE_TABLES_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    created_at_ms INTEGER NOT NULL,
    updated_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at_ms INTEGER NOT NULL,
    updated_at_ms INTEGER NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS events (
    session_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    payload_version INTEGER NOT NULL DEFAULT 1,
    created_at_ms INTEGER NOT NULL,
    PRIMARY KEY (session_id, seq),
    FOREIGN KEY(session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS steps (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    step_index INTEGER NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL,
    tool TEXT,
    side_effect TEXT,
    requires_approval INTEGER NOT NULL DEFAULT 0,
    created_at_ms INTEGER NOT NULL,
    updated_at_ms INTEGER NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS equipment_register (
    tag_id TEXT PRIMARY KEY,
    unit_id TEXT NOT NULL,
    equipment_name TEXT NOT NULL,
    service_description TEXT NOT NULL,
    design_pressure_mpa REAL NOT NULL,
    design_temp_c REAL NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    step_id TEXT,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    input_json TEXT,
    output_json TEXT,
    error TEXT,
    created_at_ms INTEGER NOT NULL,
    updated_at_ms INTEGER NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    type TEXT NOT NULL,
    metadata_json TEXT,
    created_at_ms INTEGER NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS project_policies (
    project_id TEXT NOT NULL,
    tool TEXT NOT NULL,
    resource_pattern TEXT NOT NULL,
    policy_choice TEXT NOT NULL,
    created_at_ms INTEGER NOT NULL,
    PRIMARY KEY (project_id, tool, resource_pattern),
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS kb_documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    dept TEXT NOT NULL,
    classification TEXT NOT NULL,
    effective_date TEXT NOT NULL,
    superseded_by TEXT,
    created_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS kb_chunks (
    id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    heading_path TEXT NOT NULL,
    body_text TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    page INTEGER NOT NULL,
    bbox_json TEXT NOT NULL,
    created_at_ms INTEGER NOT NULL,
    FOREIGN KEY(doc_id) REFERENCES kb_documents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS kb_chunk_roles (
    chunk_id TEXT NOT NULL,
    role TEXT NOT NULL,
    PRIMARY KEY (chunk_id, role),
    FOREIGN KEY(chunk_id) REFERENCES kb_chunks(id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE IF NOT EXISTS kb_chunks_fts USING fts5(
    chunk_id UNINDEXED,
    heading_path,
    body_text,
    tokenize = 'unicode61 remove_diacritics 0'
);

CREATE TABLE IF NOT EXISTS kb_vectors (
    chunk_id TEXT PRIMARY KEY,
    embedding_json TEXT NOT NULL,
    FOREIGN KEY(chunk_id) REFERENCES kb_chunks(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS calc_executions (
    calc_run_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    equipment_tag TEXT NOT NULL,
    title TEXT NOT NULL,
    record_json TEXT NOT NULL,
    verification_passed INTEGER NOT NULL,
    created_at_ms INTEGER NOT NULL,
    FOREIGN KEY(session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_id, updated_at_ms DESC);
CREATE INDEX IF NOT EXISTS idx_events_session_seq ON events(session_id, seq);
CREATE INDEX IF NOT EXISTS idx_steps_session ON steps(session_id, step_index);
CREATE INDEX IF NOT EXISTS idx_tool_calls_session ON tool_calls(session_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_session ON artifacts(session_id);
CREATE INDEX IF NOT EXISTS idx_kb_chunk_roles ON kb_chunk_roles(role, chunk_id);
CREATE INDEX IF NOT EXISTS idx_kb_documents_effective ON kb_documents(effective_date, superseded_by);
CREATE INDEX IF NOT EXISTS idx_kb_chunks_doc ON kb_chunks(doc_id, chunk_index);

CREATE TRIGGER IF NOT EXISTS prevent_event_update
BEFORE UPDATE ON events
BEGIN
    SELECT RAISE(ABORT, 'events table is append-only');
END;

CREATE TRIGGER IF NOT EXISTS prevent_event_delete
BEFORE DELETE ON events
BEGIN
    SELECT RAISE(ABORT, 'events table is append-only');
END;
"""


def current_time_ms() -> int:
    """Return current UTC timestamp in epoch milliseconds."""
    return int(time.time() * 1000)


class DatabaseManager:
    """Manages SQLite database connection, pragmas, and schema migrations."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[aiosqlite.Connection]:
        """Async context manager yielding an open aiosqlite Connection with pragmas enabled."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute("PRAGMA journal_mode = WAL;")
            await conn.execute("PRAGMA synchronous = NORMAL;")
            await conn.execute("PRAGMA foreign_keys = ON;")
            await conn.execute("PRAGMA busy_timeout = 5000;")
            yield conn

    async def initialize_schema(self, conn: aiosqlite.Connection) -> None:
        """Initialize tables and run migrations based on PRAGMA user_version."""
        async with conn.execute("PRAGMA user_version;") as cursor:
            row = await cursor.fetchone()
            current_version = row[0] if row else 0

        if current_version < SCHEMA_VERSION:
            await conn.executescript(CREATE_TABLES_SQL)
            await conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION};")
            await conn.commit()

    async def checkpoint_wal(self, conn: aiosqlite.Connection) -> None:
        """Truncate WAL log file to guarantee physical disk sync for critical audit steps."""
        await conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
