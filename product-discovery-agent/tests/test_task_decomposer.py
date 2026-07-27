"""Tests for TaskDecomposer (Module 2 requirements 2 and 3)."""

from __future__ import annotations

from coordinator.models import SubagentName
from coordinator.task_decomposer import TaskDecomposer


def test_dark_mode_creates_all_four_tasks() -> None:
    plan = TaskDecomposer().build_plan("dark mode", "Should we build dark mode?")

    task_agents = {task.agent_name for task in plan.tasks}
    assert task_agents == set(SubagentName)
    assert plan.skipped == []


def test_each_task_has_a_reason_and_unique_id() -> None:
    plan = TaskDecomposer().build_plan("dark mode", "Should we build dark mode?")

    task_ids = [task.task_id for task in plan.tasks]
    assert len(task_ids) == len(set(task_ids))
    assert all(task.reason.strip() for task in plan.tasks)


def test_copy_change_question_skips_market_research() -> None:
    plan = TaskDecomposer().build_plan("onboarding", "Should we change the onboarding copy?")

    task_agents = {task.agent_name for task in plan.tasks}
    skipped_agents = {skip.agent_name for skip in plan.skipped}

    assert SubagentName.MARKET_RESEARCH not in task_agents
    assert SubagentName.MARKET_RESEARCH in skipped_agents
    assert SubagentName.CUSTOMER_INSIGHTS in task_agents
    assert SubagentName.TECHNICAL_FEASIBILITY in task_agents
    # A skip must be explained, not silent.
    skip_reason = next(s.reason for s in plan.skipped if s.agent_name == SubagentName.MARKET_RESEARCH)
    assert skip_reason.strip()


def test_customer_insights_task_is_always_critical() -> None:
    plan = TaskDecomposer().build_plan("dark mode", "Should we build dark mode?")
    customer_task = next(t for t in plan.tasks if t.agent_name == SubagentName.CUSTOMER_INSIGHTS)
    assert customer_task.critical is True
