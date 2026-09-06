"""Unit tests for SQLite SessionStore, append-only triggers, and benchmark tests."""

import sqlite3
import time
from pathlib import Path

import pytest

from storage import SessionNotFoundError, SessionStore


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> Path:
    """Fixture returning a temporary database file path."""
    return tmp_path / "test_sessions.db"


@pytest.mark.asyncio
async def test_session_store_lifecycle(tmp_db_path: Path) -> None:
    """Test create, get, append_event, load_events, resume, and close."""
    store = SessionStore(tmp_db_path)
    proj = await store.ensure_project("proj-1", "Test Project", "/tmp/proj1")
    assert proj["id"] == "proj-1"

    session = await store.create_session("sess-1", "proj-1", "Refinery Inspection")
    assert session["sessionId"] == "sess-1"
    assert session["status"] == "active"

    # Append semantic events
    ev1 = await store.append_event(
        "sess-1", "message_started", {"role": "writer", "prompt": "Hello"}
    )
    assert ev1["seq"] == 2  # seq=1 was session_created event
    assert ev1["payloadVersion"] == 1
    assert ev1["createdAtMs"] > 0

    ev2 = await store.append_event(
        "sess-1", "message_completed", {"role": "writer", "content": "World"}
    )
    assert ev2["seq"] == 3

    # Load events
    events = await store.load_session_events("sess-1")
    assert len(events) == 3
    assert events[0]["eventType"] == "session_created"
    assert events[1]["eventType"] == "message_started"
    assert events[2]["eventType"] == "message_completed"
    assert events[1]["seq"] < events[2]["seq"]

    # Close & resume session
    closed = await store.close_session("sess-1")
    assert closed["status"] == "closed"

    resumed = await store.resume_session("sess-1")
    assert resumed["status"] == "active"


@pytest.mark.asyncio
async def test_append_only_trigger_enforcement(tmp_db_path: Path) -> None:
    """Assert BEFORE UPDATE and BEFORE DELETE triggers prevent mutations on events table."""
    store = SessionStore(tmp_db_path)
    await store.create_session("sess-trigger", "proj-1", "Trigger Test")
    await store.append_event("sess-trigger", "test_event", {"data": 123})

    # Direct sqlite3 raw connection to attempt mutation
    raw_conn = sqlite3.connect(tmp_db_path)
    cursor = raw_conn.cursor()

    # Assert UPDATE fails due to trigger
    err_types = (sqlite3.IntegrityError, sqlite3.OperationalError)
    with pytest.raises(err_types, match="events table is append-only"):
        cursor.execute(
            "UPDATE events SET event_type = 'hacked' WHERE session_id = 'sess-trigger'"
        )

    # Assert DELETE fails due to trigger
    with pytest.raises(err_types, match="events table is append-only"):
        cursor.execute("DELETE FROM events WHERE session_id = 'sess-trigger'")

    raw_conn.close()


@pytest.mark.asyncio
async def test_session_not_found(tmp_db_path: Path) -> None:
    """Test exception when requesting nonexistent session."""
    store = SessionStore(tmp_db_path)
    with pytest.raises(SessionNotFoundError):
        await store.get_session("nonexistent")

    with pytest.raises(SessionNotFoundError):
        await store.load_session_events("nonexistent")


@pytest.mark.asyncio
async def test_list_sessions_performance_benchmark(tmp_db_path: Path) -> None:
    """Benchmark list_sessions with 100 sessions loaded to ensure <100ms latency."""
    store = SessionStore(tmp_db_path)
    await store.ensure_project("perf-proj", "Perf Project", "/tmp/perf")

    # Insert 100 sessions
    for i in range(100):
        await store.create_session(f"perf-sess-{i:03d}", "perf-proj", f"Session {i}")

    t0 = time.perf_counter()
    sessions = await store.list_sessions("perf-proj")
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert len(sessions) == 100
    assert elapsed_ms < 100.0, f"list_sessions took {elapsed_ms:.2f}ms, target < 100ms"
