"""LangChain tool integration exposing execute_runbook_step to agent runners."""

import json
import logging
from typing import Any, Literal, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field

from mcp_rag_agent.it_support.runbooks.executor import RunbookExecutor
from mcp_rag_agent.it_support.runbooks.models import StepOutcome

logger = logging.getLogger("RunbookTool")


class RunbookToolInput(BaseModel):
    """Input parameters for the execute_runbook_step tool."""

    model_config = ConfigDict(str_strip_whitespace=True)

    action: Literal["start", "evaluate", "status", "list"] = Field(
        description="Action to perform: 'start' to begin troubleshooting, 'evaluate' to submit outcome of current step, 'status' to view current state, or 'list' to see available runbooks."
    )
    query: Optional[str] = Field(
        default=None,
        description="User's IT problem description (used to automatically select the appropriate runbook if runbook_id is omitted).",
    )
    runbook_id: Optional[str] = Field(
        default=None,
        description="Explicit runbook ID to execute (e.g., 'rb_vpn_troubleshooting', 'rb_wifi_troubleshooting').",
    )
    execution_id: Optional[str] = Field(
        default=None,
        description="Active execution identifier from a previous start or evaluate call. Required for 'evaluate' and 'status'.",
    )
    step_outcome: Optional[Literal["success", "failure", "retry", "escalate"]] = Field(
        default=None,
        description="Result of attempting the current step: 'success' if it worked, 'failure' if it didn't, 'retry' to re-attempt, or 'escalate' to stop and escalate.",
    )
    user_feedback: Optional[str] = Field(
        default=None,
        description="Optional diagnostic observations, error messages, or user comments from the step attempt.",
    )
    branch_choice: Optional[str] = Field(
        default=None,
        description="Optional explicit branch choice if the step defined conditional branching options.",
    )


def create_runbook_tool(executor: Optional[RunbookExecutor] = None) -> StructuredTool:
    """Create the execute_runbook_step LangChain StructuredTool."""
    active_executor = executor or RunbookExecutor()

    def _execute(
        action: str,
        query: Optional[str] = None,
        runbook_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        step_outcome: Optional[str] = None,
        user_feedback: Optional[str] = None,
        branch_choice: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Synchronous wrapper for runbook actions."""
        try:
            if action == "list":
                runbooks = active_executor.registry.list_active()
                items = [
                    {
                        "runbook_id": rb.runbook_id,
                        "title": rb.title,
                        "category": rb.category.value,
                        "tags": rb.tags,
                    }
                    for rb in runbooks
                ]
                return f"[AVAILABLE RUNBOOKS]\n{json.dumps(items, indent=2)}"

            if action == "start":
                if runbook_id:
                    result = active_executor.start_runbook(runbook_id=runbook_id)
                elif query:
                    result = active_executor.select_and_start(query=query)
                else:
                    return "Error: Either 'runbook_id' or 'query' must be provided to start a runbook."

                return (
                    f"[RUNBOOK STARTED: {result.runbook_id} v{result.runbook_version}]\n"
                    f"Execution ID: {result.execution_id}\n"
                    f"Status: {result.status.value}\n"
                    f"Current Step: {result.step_id}\n"
                    f"Instruction for User:\n{result.instruction}\n"
                    f"Expected Outcome: {result.expected_outcome or 'N/A'}\n"
                    f"Action Required: Present this instruction to the user, wait for their result, then call execute_runbook_step with action='evaluate' and execution_id='{result.execution_id}'."
                )

            if action == "evaluate":
                if not execution_id:
                    return "Error: 'execution_id' is required for action='evaluate'."
                if not step_outcome:
                    return "Error: 'step_outcome' ('success', 'failure', 'retry', 'escalate') is required for action='evaluate'."

                outcome_enum = StepOutcome(step_outcome.lower())
                result = active_executor.execute_step(
                    execution_id=execution_id,
                    outcome=outcome_enum,
                    feedback=user_feedback,
                    branch_choice=branch_choice,
                )

                if result.is_terminal:
                    return (
                        f"[RUNBOOK TERMINAL: {result.status.value.upper()}]\n"
                        f"Execution ID: {result.execution_id}\n"
                        f"Runbook: {result.runbook_id}\n"
                        f"Final Status: {result.status.value}\n"
                        f"Summary:\n{result.instruction}\n"
                        f"Total Troubleshooting Steps: {result.history_count}"
                    )

                return (
                    f"[RUNBOOK ADVANCED: Step {result.step_id}]\n"
                    f"Execution ID: {result.execution_id}\n"
                    f"Status: {result.status.value}\n"
                    f"Next Instruction for User:\n{result.instruction}\n"
                    f"Expected Outcome: {result.expected_outcome or 'N/A'}\n"
                    f"Action Required: Present this instruction to the user, wait for their result, then call execute_runbook_step with action='evaluate' and execution_id='{result.execution_id}'."
                )

            if action == "status":
                if not execution_id:
                    return "Error: 'execution_id' is required for action='status'."
                state = active_executor.get_state(execution_id)
                if not state:
                    return f"Error: No active execution found for ID '{execution_id}'."
                return (
                    f"[RUNBOOK STATUS]\n"
                    f"Execution ID: {state.execution_id}\n"
                    f"Runbook ID: {state.runbook_id} (v{state.runbook_version})\n"
                    f"Status: {state.status.value}\n"
                    f"Current Step: {state.current_step_id or 'None (Terminal)'}\n"
                    f"History: {len(state.history)} steps completed"
                )

            return f"Error: Unrecognized action '{action}'. Must be 'start', 'evaluate', 'status', or 'list'."
        except Exception as exc:
            logger.error(f"[RUNBOOK_TOOL_ERROR] {str(exc)}", exc_info=True)
            return f"[RUNBOOK ERROR] {str(exc)}"

    return StructuredTool.from_function(
        func=_execute,
        name="execute_runbook_step",
        description=(
            "Execute and guide users through interactive, step-by-step IT troubleshooting runbooks. "
            "Supports starting a runbook, evaluating step outcomes (success, failure, retry, escalate), "
            "and progressing through deterministic enterprise diagnosis workflows."
        ),
        args_schema=RunbookToolInput,
    )
