"""Unit tests for SWARAJ Resource-Scoped Policy Engine, Planner, Tiered Critique, and Recovery."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from agent.budget import RunBudget, RunBudgetTracker
from agent.critique import TieredCritique
from agent.planner import Planner, PlanStep
from agent.policy import PolicyDecision, PolicyEngine
from storage.session_store import SessionStore
from tools.base import SideEffect, ToolResult
from tools.fs_read import FsReadTool
from tools.fs_write import FsWriteTool


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "sessions_test.db"


@pytest.fixture
async def session_store(temp_db_path: Path) -> SessionStore:
    store = SessionStore(temp_db_path)
    await store.ensure_project("proj_1", "Test Project", "/tmp")
    return store


# 1. Resource-Pattern Policy Matching & Exec Prefix Safety
@pytest.mark.asyncio
async def test_policy_engine_resource_pattern_matching(session_store: SessionStore) -> None:
    engine = PolicyEngine(session_store=session_store)
    project_id = "proj_1"

    # Save rule scoped to docs/**
    await session_store.save_policy_rule(project_id, "fs_write", "docs/**", "always_allow")

    # Match inside docs/** -> AUTO
    dec1, pat1 = await engine.decide(
        None, "fs_write", "docs/readme.md", SideEffect.WRITE, project_id
    )
    assert dec1 == PolicyDecision.AUTO
    assert pat1 == "docs/**"

    # Outside docs/** -> ASK
    dec2, pat2 = await engine.decide(
        None, "fs_write", "src/main.py", SideEffect.WRITE, project_id
    )
    assert dec2 == PolicyDecision.ASK
    assert pat2 is None


@pytest.mark.asyncio
async def test_policy_engine_exec_command_prefix_safety(session_store: SessionStore) -> None:
    engine = PolicyEngine(session_store=session_store)
    project_id = "proj_1"

    # Save rule for git status *
    await session_store.save_policy_rule(project_id, "bash", "git status *", "always_allow")

    # git status -> AUTO
    dec1, _ = await engine.decide(None, "bash", "git status", SideEffect.EXEC, project_id)
    assert dec1 == PolicyDecision.AUTO

    # git push --force -> ASK
    dec2, _ = await engine.decide(None, "bash", "git push --force", SideEffect.EXEC, project_id)
    assert dec2 == PolicyDecision.ASK


# 2. Policy Rule Revocation Test
@pytest.mark.asyncio
async def test_policy_rule_revocation(session_store: SessionStore) -> None:
    engine = PolicyEngine(session_store=session_store)
    project_id = "proj_1"

    await session_store.save_policy_rule(project_id, "fs_write", "notes.md", "always_allow")
    dec1, _ = await engine.decide(None, "fs_write", "notes.md", SideEffect.WRITE, project_id)
    assert dec1 == PolicyDecision.AUTO

    # Revoke rule
    revoked = await session_store.revoke_policy_rule(project_id, "fs_write", "notes.md")
    assert revoked is True

    dec2, _ = await engine.decide(None, "fs_write", "notes.md", SideEffect.WRITE, project_id)
    assert dec2 == PolicyDecision.ASK


# 3. DENY Observation Adaptation Test
@pytest.mark.asyncio
async def test_deny_observation_adaptation(session_store: SessionStore) -> None:
    engine = PolicyEngine(session_store=session_store)
    project_id = "proj_1"

    await session_store.save_policy_rule(project_id, "fs_write", "secret.env", "deny")
    dec, pat = await engine.decide(None, "fs_write", "secret.env", SideEffect.WRITE, project_id)

    assert dec == PolicyDecision.DENY
    assert pat == "secret.env"


# 4. Plan Edit Dependency Validation Test
def test_planner_edit_dependency_validation() -> None:
    mock_ollama = MagicMock()
    planner = Planner(ollama_client=mock_ollama)

    step1 = PlanStep(
        step_index=1,
        description="Read data",
        tool="fs_read",
        side_effect="read",
        requires_approval=False,
    )
    step2 = PlanStep(
        step_index=2,
        description="Process data",
        tool="fs_write",
        side_effect="write",
        requires_approval=True,
        dependencies=[1],
    )
    orig_steps = [step1, step2]

    # Client deletes Step 1, leaving Step 2 with dangling dependency
    edited_steps = [step2]
    warnings = planner.validate_plan_edits(orig_steps, edited_steps)

    assert len(warnings) == 1
    assert "depends on Step 1 which was deleted" in warnings[0]


# 5. Tier 2 Critique Budget Accounting Test
@pytest.mark.asyncio
async def test_tier2_critique_budget_accounting() -> None:
    mock_ollama = MagicMock()

    async def mock_critique_stream(*args: Any, **kwargs: Any) -> Any:
        yield {
            "message": {"content": "PASS: Step completed cleanly"},
            "done": True,
            "prompt_eval_count": 40,
            "eval_count": 10,
        }

    mock_ollama.stream_chat = mock_critique_stream

    tracker = RunBudgetTracker(budget=RunBudget(max_run_tokens=1000))
    critique = TieredCritique(ollama_client=mock_ollama)
    tool = FsReadTool()
    res = ToolResult.ok(
        {"content": "data", "start_line": 1, "end_line": 1, "total_lines": 1, "total_bytes": 4}
    )

    crit_res = await critique.evaluate_step(
        tool=tool,
        result=res,
        step_description="Read file",
        model_tag="qwen3-planner",
        budget_tracker=tracker,
        requires_model_critique=True,
    )

    assert crit_res.passed is True
    assert tracker.total_tokens == 50  # 40 prompt + 10 eval


# 6. Interrupted Step Idempotency Decider Test
def test_interrupted_step_idempotency_decider() -> None:
    read_tool = FsReadTool()
    write_tool = FsWriteTool()

    assert TieredCritique.decide_interrupted_resume(read_tool) == "auto_retry"
    assert TieredCritique.decide_interrupted_resume(write_tool) == "prompt_user"
