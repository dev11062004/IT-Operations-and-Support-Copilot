"""RunbookExecutor coordinating registry, state persistence, and LangGraph workflow."""

import logging
from typing import Any, Optional
from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver

from mcp_rag_agent.it_support.models import ITCategory
from mcp_rag_agent.it_support.runbooks.graph import create_runbook_subgraph
from mcp_rag_agent.it_support.runbooks.models import (
    RunbookExecutionState,
    RunbookStatus,
    StepExecutionRecord,
    StepExecutionResult,
    StepOutcome,
)
from mcp_rag_agent.it_support.runbooks.registry import (
    RunbookNotFoundError,
    RunbookRegistry,
    get_default_registry,
)

logger = logging.getLogger("RunbookExecutor")


class RunbookExecutor:
    """Stateful orchestrator for troubleshooting runbooks backed by LangGraph."""

    def __init__(
        self,
        registry: Optional[RunbookRegistry] = None,
        checkpointer: Optional[Any] = None,
    ) -> None:
        self.registry = registry or get_default_registry()
        # Use provided checkpointer, or try core get_checkpointer, or fallback to MemorySaver
        if checkpointer is not None:
            self.checkpointer = checkpointer
        else:
            try:
                from mcp_rag_agent.core.checkpointer import get_checkpointer

                self.checkpointer = get_checkpointer() or MemorySaver()
            except Exception:
                self.checkpointer = MemorySaver()

        self.graph = create_runbook_subgraph(
            registry=self.registry,
            checkpointer=self.checkpointer,
        )

    def _config(self, thread_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": thread_id}}

    def _state_to_result(self, state_dict: dict[str, Any]) -> StepExecutionResult:
        runbook_id = state_dict["runbook_id"]
        version = state_dict.get("runbook_version", "1.0.0")
        current_step_id = state_dict.get("current_step_id")
        status_val = RunbookStatus(
            state_dict.get("status", RunbookStatus.IN_PROGRESS.value)
        )

        expected = state_dict.get("expected_outcome")
        if not expected and current_step_id:
            try:
                rb = self.registry.get(runbook_id, version=version)
                step = rb.get_step(current_step_id)
                expected = step.expected_outcome
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "[RunbookExecutor] Could not retrieve expected outcome for step '%s' in runbook '%s': %s",
                    current_step_id,
                    runbook_id,
                    exc,
                )

        return StepExecutionResult(
            execution_id=state_dict.get(
                "execution_id", state_dict.get("thread_id", "")
            ),
            runbook_id=runbook_id,
            runbook_version=version,
            step_id=current_step_id,
            status=status_val,
            instruction=state_dict.get("output_instruction", ""),
            expected_outcome=expected,
            next_step_id=state_dict.get("next_step_id"),
            is_terminal=bool(state_dict.get("is_terminal", False)),
            history_count=len(state_dict.get("history", [])),
            message=f"Runbook '{runbook_id}' status: {status_val.value}",
        )

    def start_runbook(
        self,
        runbook_id: str,
        version: Optional[str] = None,
        thread_id: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> StepExecutionResult:
        """Start a new runbook execution from its initial step."""
        runbook = self.registry.get(runbook_id, version=version)
        active_thread = thread_id or f"exec_{uuid4().hex[:12]}"

        initial_state = {
            "execution_id": active_thread,
            "thread_id": active_thread,
            "runbook_id": runbook.runbook_id,
            "runbook_version": runbook.version,
            "current_step_id": runbook.initial_step_id,
            "status": RunbookStatus.NOT_STARTED.value,
            "retry_counts": {},
            "history": [],
            "context": context or {},
            "is_terminal": False,
        }

        cfg = self._config(active_thread)
        output_state = self.graph.invoke(initial_state, config=cfg)
        logger.info(
            f"[RUNBOOK_EXECUTOR] Started runbook '{runbook.runbook_id}' (thread_id={active_thread}) at step '{runbook.initial_step_id}'"
        )
        return self._state_to_result(output_state)

    def execute_step(
        self,
        execution_id: str,
        outcome: StepOutcome | str,
        feedback: Optional[str] = None,
        branch_choice: Optional[str] = None,
        context_updates: Optional[dict[str, Any]] = None,
    ) -> StepExecutionResult:
        """Evaluate the current step outcome and deterministically advance the runbook."""
        cfg = self._config(execution_id)
        current_snapshot = self.graph.get_state(cfg)
        if not current_snapshot or not current_snapshot.values:
            raise KeyError(f"Runbook execution state for '{execution_id}' not found.")

        current_values = current_snapshot.values
        if current_values.get("is_terminal"):
            raise ValueError(
                f"Cannot advance execution '{execution_id}': runbook has already reached terminal status '{current_values.get('status')}'."
            )

        outcome_val = (
            outcome.value if isinstance(outcome, StepOutcome) else str(outcome).lower()
        )
        if outcome_val not in {o.value for o in StepOutcome}:
            raise ValueError(
                f"Invalid outcome '{outcome}'. Must be one of {[o.value for o in StepOutcome]}."
            )

        update_payload: dict[str, Any] = {
            "step_outcome": outcome_val,
            "user_feedback": feedback,
            "branch_choice": branch_choice,
        }
        if context_updates:
            existing_ctx = dict(current_values.get("context", {}))
            existing_ctx.update(context_updates)
            update_payload["context"] = existing_ctx

        advanced_state = self.graph.invoke(update_payload, config=cfg)
        logger.info(
            f"[RUNBOOK_EXECUTOR] Advanced '{execution_id}' with outcome='{outcome_val}'. New status='{advanced_state.get('status')}'"
        )
        return self._state_to_result(advanced_state)

    def get_state(self, execution_id: str) -> Optional[RunbookExecutionState]:
        """Retrieve persisted execution state from checkpointer."""
        cfg = self._config(execution_id)
        snapshot = self.graph.get_state(cfg)
        if not snapshot or not snapshot.values:
            return None

        val = snapshot.values
        history_records = [
            StepExecutionRecord(
                step_id=h.get("step_id", ""),
                attempt=h.get("attempt", 1),
                outcome=StepOutcome(h.get("outcome", StepOutcome.SUCCESS.value)),
                user_feedback=h.get("user_feedback"),
                notes=h.get("notes"),
            )
            for h in val.get("history", [])
        ]

        return RunbookExecutionState(
            execution_id=val.get("execution_id", execution_id),
            thread_id=val.get("thread_id", execution_id),
            runbook_id=val.get("runbook_id", ""),
            runbook_version=val.get("runbook_version", "1.0.0"),
            current_step_id=val.get("current_step_id"),
            status=RunbookStatus(val.get("status", RunbookStatus.NOT_STARTED.value)),
            history=history_records,
            retry_counts=val.get("retry_counts", {}),
            context=val.get("context", {}),
            output_instruction=val.get("output_instruction", ""),
            summary=val.get("summary"),
        )

    def resume_runbook(self, execution_id: str) -> StepExecutionResult:
        """Inspect and return the current pending step instruction without advancing."""
        cfg = self._config(execution_id)
        snapshot = self.graph.get_state(cfg)
        if not snapshot or not snapshot.values:
            raise KeyError(f"Runbook execution state for '{execution_id}' not found.")
        return self._state_to_result(snapshot.values)

    def select_and_start(
        self,
        query: str,
        category: Optional[ITCategory] = None,
        thread_id: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> StepExecutionResult:
        """Select the best matching runbook for a query and initiate execution."""
        runbook = self.registry.find_for_query(query, category=category)
        if not runbook:
            raise RunbookNotFoundError(
                f"No suitable runbook found for query '{query}' (category={category.value if category else None})."
            )
        return self.start_runbook(
            runbook_id=runbook.runbook_id,
            version=runbook.version,
            thread_id=thread_id,
            context=context,
        )
