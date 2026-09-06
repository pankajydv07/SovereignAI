"""Session store service providing persistent CRUD and append-only event logging."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite

from storage.db import DatabaseManager, current_time_ms


class SessionStoreError(Exception):
    """Base exception for session store operations."""


class SessionNotFoundError(SessionStoreError):
    """Raised when a requested session is not found in the database."""


class ProjectNotFoundError(SessionStoreError):
    """Raised when a requested project is not found in the database."""


class SessionStore:
    """Async session store maintaining database operations for a project's sessions."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_manager = DatabaseManager(self.db_path)

    @asynccontextmanager
    async def _get_connection(self) -> AsyncIterator[aiosqlite.Connection]:
        """Yield initialized connection with schema ready."""
        async with self.db_manager.connect() as conn:
            await self.db_manager.initialize_schema(conn)
            yield conn

    async def ensure_project(self, project_id: str, name: str, path: str) -> dict[str, Any]:
        """Insert or update a project record."""
        now = current_time_ms()
        async with self._get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO projects (id, name, path, created_at_ms, updated_at_ms)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    path = excluded.path,
                    updated_at_ms = excluded.updated_at_ms
                """,
                (project_id, name, path, now, now),
            )
            await conn.commit()
            return {
                "id": project_id,
                "name": name,
                "path": path,
                "createdAtMs": now,
                "updatedAtMs": now,
            }

    async def create_session(
        self, session_id: str, project_id: str, title: str | None = None
    ) -> dict[str, Any]:
        """Create a new session record in the database."""
        now = current_time_ms()
        session_title = title if title else f"Session {session_id[:8]}"
        status = "active"

        async with self._get_connection() as conn:
            # Check project existence, auto-register default project if missing
            async with conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)) as cur:
                if not await cur.fetchone():
                    await conn.execute(
                        """
                        INSERT INTO projects (id, name, path, created_at_ms, updated_at_ms)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (project_id, f"Project {project_id[:8]}", "/workspace", now, now),
                    )

            await conn.execute(
                """
                INSERT INTO sessions (id, project_id, title, status, created_at_ms, updated_at_ms)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, project_id, session_title, status, now, now),
            )

            # Record session_created initial event
            await conn.execute(
                """
                INSERT INTO events (
                    session_id, seq, event_type, payload, payload_version, created_at_ms
                ) VALUES (?, 1, 'session_created', ?, 1, ?)
                """,
                (
                    session_id,
                    json.dumps({
                        "sessionId": session_id,
                        "projectId": project_id,
                        "title": session_title,
                    }),
                    now,
                ),
            )
            await conn.commit()

        return {
            "sessionId": session_id,
            "projectId": project_id,
            "title": session_title,
            "status": status,
            "createdAtMs": now,
            "updatedAtMs": now,
        }

    async def append_event(
        self,
        session_id: str,
        event_type: str,
        payload: dict[str, Any],
        payload_version: int = 1,
    ) -> dict[str, Any]:
        """Append a semantic event to the session event log with a monotonic sequence number."""
        now = current_time_ms()
        payload_str = json.dumps(payload)

        async with self._get_connection() as conn:
            # Verify session exists
            async with conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)) as cur:
                if not await cur.fetchone():
                    raise SessionNotFoundError(f"Session '{session_id}' does not exist.")

            # Compute next monotonic seq for session_id
            async with conn.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 FROM events WHERE session_id = ?",
                (session_id,),
            ) as cur:
                row = await cur.fetchone()
                next_seq = row[0] if row else 1

            await conn.execute(
                """
                INSERT INTO events (
                    session_id, seq, event_type, payload, payload_version, created_at_ms
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, next_seq, event_type, payload_str, payload_version, now),
            )

            # Touch session updated_at_ms
            await conn.execute(
                "UPDATE sessions SET updated_at_ms = ? WHERE id = ?",
                (now, session_id),
            )
            await conn.commit()

        return {
            "sessionId": session_id,
            "seq": next_seq,
            "eventType": event_type,
            "payload": payload,
            "payloadVersion": payload_version,
            "createdAtMs": now,
        }

    async def get_session(self, session_id: str) -> dict[str, Any]:
        """Fetch session metadata by ID."""
        async with self._get_connection() as conn:
            async with conn.execute(
                """
                SELECT id, project_id, title, status, created_at_ms, updated_at_ms
                FROM sessions WHERE id = ?
                """,
                (session_id,),
            ) as cur:
                row = await cur.fetchone()
                if not row:
                    raise SessionNotFoundError(f"Session '{session_id}' not found.")
                return {
                    "sessionId": row["id"],
                    "projectId": row["project_id"],
                    "title": row["title"],
                    "status": row["status"],
                    "createdAtMs": row["created_at_ms"],
                    "updatedAtMs": row["updated_at_ms"],
                }

    async def load_session_events(self, session_id: str) -> list[dict[str, Any]]:
        """Load all events for a session ordered monotonically by seq."""
        async with self._get_connection() as conn:
            # Check existence first
            await self.get_session(session_id)

            async with conn.execute(
                """
                SELECT session_id, seq, event_type, payload, payload_version, created_at_ms
                FROM events
                WHERE session_id = ?
                ORDER BY seq ASC
                """,
                (session_id,),
            ) as cur:
                rows = await cur.fetchall()
                events = []
                for row in rows:
                    events.append({
                        "sessionId": row["session_id"],
                        "seq": row["seq"],
                        "eventType": row["event_type"],
                        "payload": json.loads(row["payload"]),
                        "payloadVersion": row["payload_version"],
                        "createdAtMs": row["created_at_ms"],
                    })
                return events

    async def resume_session(self, session_id: str) -> dict[str, Any]:
        """Resume an existing session, setting status back to active."""
        now = current_time_ms()
        async with self._get_connection() as conn:
            session = await self.get_session(session_id)

            await conn.execute(
                "UPDATE sessions SET status = 'active', updated_at_ms = ? WHERE id = ?",
                (now, session_id),
            )
            await conn.commit()

            # Log session_resumed event
            await self.append_event(session_id, "session_resumed", {"status": "active"})

            session["status"] = "active"
            session["updatedAtMs"] = now
            return session

    async def close_session(self, session_id: str) -> dict[str, Any]:
        """Close an active session."""
        now = current_time_ms()
        async with self._get_connection() as conn:
            session = await self.get_session(session_id)

            await conn.execute(
                "UPDATE sessions SET status = 'closed', updated_at_ms = ? WHERE id = ?",
                (now, session_id),
            )
            await conn.commit()

            # Log session_closed event
            await self.append_event(session_id, "session_closed", {"status": "closed"})

            session["status"] = "closed"
            session["updatedAtMs"] = now
            return session

    async def list_sessions(self, project_id: str | None = None) -> list[dict[str, Any]]:
        """List sessions optionally filtered by project_id, ordered by recent update."""
        async with self._get_connection() as conn:
            if project_id:
                query = """
                SELECT id, project_id, title, status, created_at_ms, updated_at_ms
                FROM sessions
                WHERE project_id = ?
                ORDER BY updated_at_ms DESC
                """
                params: tuple[Any, ...] = (project_id,)
            else:
                query = """
                SELECT id, project_id, title, status, created_at_ms, updated_at_ms
                FROM sessions
                ORDER BY updated_at_ms DESC
                """
                params = ()

            async with conn.execute(query, params) as cur:
                rows = await cur.fetchall()
                results = []
                for row in rows:
                    results.append({
                        "sessionId": row["id"],
                        "projectId": row["project_id"],
                        "title": row["title"],
                        "status": row["status"],
                        "createdAtMs": row["created_at_ms"],
                        "updatedAtMs": row["updated_at_ms"],
                    })
                return results

    async def save_policy_rule(
        self, project_id: str, tool: str, resource_pattern: str, choice: str
    ) -> dict[str, Any]:
        """Insert or update a project-level policy rule."""
        now = current_time_ms()
        async with self._get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO project_policies (
                    project_id, tool, resource_pattern, policy_choice, created_at_ms
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(project_id, tool, resource_pattern) DO UPDATE SET
                    policy_choice = excluded.policy_choice,
                    created_at_ms = excluded.created_at_ms
                """,
                (project_id, tool, resource_pattern, choice, now),
            )
            await conn.commit()
            return {
                "projectId": project_id,
                "tool": tool,
                "resourcePattern": resource_pattern,
                "choice": choice,
                "createdAtMs": now,
            }

    async def revoke_policy_rule(
        self, project_id: str, tool: str, resource_pattern: str
    ) -> bool:
        """Revoke a persisted project-level policy rule."""
        async with self._get_connection() as conn:
            cur = await conn.execute(
                """
                DELETE FROM project_policies
                WHERE project_id = ? AND tool = ? AND resource_pattern = ?
                """,
                (project_id, tool, resource_pattern),
            )
            await conn.commit()
            return cur.rowcount > 0

    async def list_project_policies(self, project_id: str) -> list[dict[str, Any]]:
        """List all persisted policy rules for a project."""
        async with self._get_connection() as conn:
            async with conn.execute(
                """
                SELECT project_id, tool, resource_pattern, policy_choice, created_at_ms
                FROM project_policies
                WHERE project_id = ?
                ORDER BY created_at_ms DESC
                """,
                (project_id,),
            ) as cur:
                rows = await cur.fetchall()
                return [
                    {
                        "projectId": r["project_id"],
                        "tool": r["tool"],
                        "resourcePattern": r["resource_pattern"],
                        "choice": r["policy_choice"],
                        "createdAtMs": r["created_at_ms"],
                    }
                    for r in rows
                ]
