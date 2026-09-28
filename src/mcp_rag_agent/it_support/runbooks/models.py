"""Typed schemas and contracts for IT troubleshooting runbooks."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from mcp_rag_agent.it_support.models import ITCategory


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RunbookStatus(str, Enum):
    """Lifecycle status of a runbook execution."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    FAILED = "failed"


class StepOutcome(str, Enum):
    """Possible outcomes reported for a runbook step."""

    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"
    ESCALATE = "escalate"


class StepActionType(str, Enum):
    """Type of action demanded by a runbook step."""

    DIAGNOSTIC = "diagnostic"
    INSTRUCTION = "instruction"
    VERIFICATION = "verification"
    AUTOMATED = "automated"


class RunbookStep(BaseModel):
    """A deterministic step within an IT troubleshooting runbook."""

    model_config = ConfigDict(str_strip_whitespace=True)

    step_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    instruction: str = Field(min_length=1, max_length=4000)
    expected_outcome: Optional[str] = Field(default=None, max_length=1000)
    action_type: StepActionType = StepActionType.INSTRUCTION
    max_retries: int = Field(default=2, ge=0, le=10)

    # Deterministic transition targets: step_id, "resolved", or "escalated"
    next_step_on_success: str = Field(min_length=1, max_length=100)
    next_step_on_failure: str = Field(min_length=1, max_length=100)
    next_step_on_escalate: str = Field(default="escalated", max_length=100)
    branches: dict[str, str] = Field(default_factory=dict)


class Runbook(BaseModel):
    """Immutable, structured enterprise runbook procedure."""

    model_config = ConfigDict(str_strip_whitespace=True)

    runbook_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    category: ITCategory
    version: str = Field(default="1.0.0", max_length=50)
    is_active: bool = True
    initial_step_id: str = Field(min_length=1, max_length=100)
    steps: dict[str, RunbookStep] = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    escalation_team: str = Field(default="IT Helpdesk Tier 2", max_length=200)

    def get_step(self, step_id: str) -> RunbookStep:
        if step_id not in self.steps:
            raise KeyError(
                f"Step '{step_id}' not found in runbook '{self.runbook_id}' v{self.version}"
            )
        return self.steps[step_id]

    def validate_graph(self) -> None:
        """Validate that all transitions point to known steps or valid terminal states."""
        terminal_states = {"resolved", "escalated"}
        valid_targets = set(self.steps.keys()) | terminal_states

        if self.initial_step_id not in self.steps:
            raise ValueError(
                f"initial_step_id '{self.initial_step_id}' does not exist in steps."
            )

        for step_id, step in self.steps.items():
            for target_name, target in [
                ("next_step_on_success", step.next_step_on_success),
                ("next_step_on_failure", step.next_step_on_failure),
                ("next_step_on_escalate", step.next_step_on_escalate),
            ]:
                if target not in valid_targets:
                    raise ValueError(
                        f"Step '{step_id}' {target_name} points to unknown target '{target}'."
                    )
            for cond, branch_target in step.branches.items():
                if branch_target not in valid_targets:
                    raise ValueError(
                        f"Step '{step_id}' branch '{cond}' points to unknown target '{branch_target}'."
                    )


class StepExecutionRecord(BaseModel):
    """Audit record of a single step execution attempt."""

    model_config = ConfigDict(str_strip_whitespace=True)

    step_id: str
    attempt: int = 1
    outcome: StepOutcome
    user_feedback: Optional[str] = None
    timestamp: datetime = Field(default_factory=_utc_now)
    notes: Optional[str] = None


class RunbookExecutionState(BaseModel):
    """Stateful tracking container for runbook execution; compatible with checkpoints."""

    model_config = ConfigDict(str_strip_whitespace=True)

    execution_id: str = Field(default_factory=lambda: f"exec_{uuid4().hex[:12]}")
    thread_id: str = Field(min_length=1, max_length=200)
    runbook_id: str = Field(min_length=1, max_length=100)
    runbook_version: str = Field(default="1.0.0", max_length=50)
    current_step_id: Optional[str] = None
    status: RunbookStatus = RunbookStatus.NOT_STARTED
    history: list[StepExecutionRecord] = Field(default_factory=list)
    retry_counts: dict[str, int] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)
    output_instruction: str = ""
    summary: Optional[str] = None
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


class StepEvaluationInput(BaseModel):
    """Input payload when evaluating user feedback or action on the current step."""

    model_config = ConfigDict(str_strip_whitespace=True)

    outcome: StepOutcome
    feedback: Optional[str] = Field(default=None, max_length=4000)
    branch_choice: Optional[str] = Field(default=None, max_length=100)
    context_updates: Optional[dict[str, Any]] = None


class StepExecutionResult(BaseModel):
    """Return contract from advancing or querying the runbook engine."""

    model_config = ConfigDict(str_strip_whitespace=True)

    execution_id: str
    runbook_id: str
    runbook_version: str
    step_id: Optional[str] = None
    status: RunbookStatus
    instruction: str
    expected_outcome: Optional[str] = None
    next_step_id: Optional[str] = None
    is_terminal: bool = False
    history_count: int = 0
    message: str = ""
