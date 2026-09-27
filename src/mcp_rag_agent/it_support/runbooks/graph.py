"""LangGraph subgraph for stateful IT troubleshooting runbooks (Step -> Evaluate -> Branch)."""

import logging
from typing import Any, Optional, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from mcp_rag_agent.it_support.runbooks.models import Runbook, RunbookStatus, StepOutcome
from mcp_rag_agent.it_support.runbooks.registry import RunbookRegistry, get_default_registry

logger = logging.getLogger("RunbookGraph")


class RunbookGraphState(TypedDict, total=False):
    """Execution state container passed through the LangGraph runbook subgraph."""

    execution_id: str
    thread_id: str
    runbook_id: str
    runbook_version: str
    current_step_id: Optional[str]
    status: str
    step_outcome: Optional[str]
    user_feedback: Optional[str]
    branch_choice: Optional[str]
    retry_counts: dict[str, int]
    history: list[dict[str, Any]]
    context: dict[str, Any]
    output_instruction: str
    expected_outcome: Optional[str]
    next_step_id: Optional[str]
    is_terminal: bool
    error: Optional[str]


def _get_runbook_from_state(state: RunbookGraphState, registry: RunbookRegistry) -> Runbook:
    runbook_id = state["runbook_id"]
    version = state.get("runbook_version")
    return registry.get(runbook_id, version=version)


def create_runbook_subgraph(
    registry: Optional[RunbookRegistry] = None,
    checkpointer: Optional[Any] = None,
):
    """Build and compile the LangGraph runbook state machine.

    Target Workflow:
        START
          ↓ (entry router)
        STEP (initial or advancing step)  OR  EVALUATE (evaluating user response)
          ↓                                     ↓
         END                                  BRANCH
                                           ├── next step → STEP → END
                                           ├── resolved  → RESOLVE → END
                                           └── escalation → ESCALATE → END
    """
    active_registry = registry or get_default_registry()

    def entry_router(state: RunbookGraphState) -> str:
        """Route to evaluate if step_outcome is present, otherwise display current step."""
        if state.get("step_outcome"):
            return "evaluate_node"
        return "step_node"

    def step_node(state: RunbookGraphState) -> dict[str, Any]:
        """Present the current step instruction and expected outcome to the user/agent."""
        runbook = _get_runbook_from_state(state, active_registry)
        step_id = state.get("current_step_id") or runbook.initial_step_id
        step = runbook.get_step(step_id)

        retry_count = state.get("retry_counts", {}).get(step_id, 0)
        instruction = step.instruction
        if retry_count > 0:
            instruction = f"[Retry Attempt {retry_count}/{step.max_retries}] {instruction}"

        return {
            "current_step_id": step_id,
            "status": RunbookStatus.IN_PROGRESS.value,
            "output_instruction": instruction,
            "expected_outcome": step.expected_outcome,
            "is_terminal": False,
            "step_outcome": None,
            "user_feedback": None,
            "branch_choice": None,
        }

    def evaluate_node(state: RunbookGraphState) -> dict[str, Any]:
        """Evaluate the reported outcome and determine the deterministic next step."""
        runbook = _get_runbook_from_state(state, active_registry)
        current_step_id = state.get("current_step_id")
        if not current_step_id:
            raise ValueError("Cannot evaluate outcome: current_step_id is missing from state.")

        step = runbook.get_step(current_step_id)
        raw_outcome = state.get("step_outcome") or "failure"
        outcome_str = raw_outcome.lower().strip()

        retry_counts = dict(state.get("retry_counts", {}))
        current_retries = retry_counts.get(current_step_id, 0)

        # 1. Deterministic Transition Calculation
        if outcome_str == StepOutcome.SUCCESS.value:
            branch_choice = state.get("branch_choice")
            if branch_choice and branch_choice in step.branches:
                next_step = step.branches[branch_choice]
            else:
                next_step = step.next_step_on_success

        elif outcome_str == StepOutcome.RETRY.value:
            if current_retries < step.max_retries:
                retry_counts[current_step_id] = current_retries + 1
                next_step = current_step_id
            else:
                # Max retries exhausted, fall back to failure route
                next_step = step.next_step_on_failure

        elif outcome_str == StepOutcome.ESCALATE.value:
            next_step = step.next_step_on_escalate

        elif outcome_str == StepOutcome.FAILURE.value:
            branch_choice = state.get("branch_choice")
            if branch_choice and branch_choice in step.branches:
                next_step = step.branches[branch_choice]
            else:
                next_step = step.next_step_on_failure
        else:
            raise ValueError(f"Unrecognized step outcome: '{raw_outcome}'. Must be success, failure, retry, or escalate.")

        # 2. Record Step Execution in History
        history_entry = {
            "step_id": current_step_id,
            "attempt": current_retries + 1,
            "outcome": outcome_str,
            "user_feedback": state.get("user_feedback"),
            "next_step": next_step,
        }
        updated_history = list(state.get("history", [])) + [history_entry]

        return {
            "next_step_id": next_step,
            "retry_counts": retry_counts,
            "history": updated_history,
        }

    def branch_router(state: RunbookGraphState) -> str:
        """Route to terminal states or transition to the next step."""
        next_step = state.get("next_step_id")
        if next_step == "resolved":
            return "resolve_node"
        if next_step == "escalated":
            return "escalate_node"
        return "advance_step_node"

    def advance_step_node(state: RunbookGraphState) -> dict[str, Any]:
        """Set current_step_id to next_step_id before displaying next step."""
        next_step = state.get("next_step_id")
        return {"current_step_id": next_step}

    def resolve_node(state: RunbookGraphState) -> dict[str, Any]:
        """Terminal resolution node marking runbook complete."""
        runbook = _get_runbook_from_state(state, active_registry)
        summary = (
            f"Runbook '{runbook.title}' completed successfully. "
            f"Total steps executed: {len(state.get('history', []))}."
        )
        return {
            "status": RunbookStatus.RESOLVED.value,
            "is_terminal": True,
            "current_step_id": None,
            "output_instruction": summary,
        }

    def escalate_node(state: RunbookGraphState) -> dict[str, Any]:
        """Terminal escalation node preparing support handoff."""
        runbook = _get_runbook_from_state(state, active_registry)
        summary = (
            f"Runbook '{runbook.title}' diagnosis unsuccessful or requires elevated permissions. "
            f"Escalating ticket to {runbook.escalation_team}. "
            f"History summary: {len(state.get('history', []))} troubleshooting attempts logged."
        )
        return {
            "status": RunbookStatus.ESCALATED.value,
            "is_terminal": True,
            "current_step_id": None,
            "output_instruction": summary,
        }

    # Build the StateGraph
    workflow = StateGraph(RunbookGraphState)

    # Add Nodes
    workflow.add_node("step_node", step_node)
    workflow.add_node("evaluate_node", evaluate_node)
    workflow.add_node("advance_step_node", advance_step_node)
    workflow.add_node("resolve_node", resolve_node)
    workflow.add_node("escalate_node", escalate_node)

    # Conditional entry from START
    workflow.add_conditional_edges(
        START,
        entry_router,
        {
            "step_node": "step_node",
            "evaluate_node": "evaluate_node",
        },
    )

    # Step node ends turn to await user execution/response
    workflow.add_edge("step_node", END)

    # Evaluate node branches based on next_step_id
    workflow.add_conditional_edges(
        "evaluate_node",
        branch_router,
        {
            "advance_step_node": "advance_step_node",
            "resolve_node": "resolve_node",
            "escalate_node": "escalate_node",
        },
    )

    # Advance node transitions directly into step_node for the new step
    workflow.add_edge("advance_step_node", "step_node")

    # Terminal nodes finish the graph
    workflow.add_edge("resolve_node", END)
    workflow.add_edge("escalate_node", END)

    return workflow.compile(checkpointer=checkpointer)
