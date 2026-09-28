"""IT-specific evaluation metrics for measuring intent, runbooks, tickets, tools, escalations, and security controls."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ITMetricResult(BaseModel):
    """Container for IT support specific benchmark metrics."""

    intent_accuracy: float = Field(0.0, description="Rate of correctly predicted IT intents")
    runbook_selection_accuracy: float = Field(0.0, description="Rate of correctly triggered runbooks when expected")
    runbook_completion_rate: float = Field(0.0, description="Rate of successfully resolved/completed runbook workflows")
    ticket_creation_success_rate: float = Field(0.0, description="Rate of proper ticket creation when indicated")
    ticket_classification_accuracy: float = Field(0.0, description="Rate of correctly categorized and prioritized tickets")
    duplicate_ticket_rate: float = Field(0.0, description="Rate of duplicate tickets generated for existing issues")
    tool_selection_accuracy: float = Field(0.0, description="Rate of correct MCP diagnostic/operational tool invocations")
    escalation_accuracy: float = Field(0.0, description="Overall correctness of escalation decision vs expected")
    escalation_rate: float = Field(0.0, description="Proportion of total queries resulting in escalation")
    unnecessary_escalation_rate: float = Field(0.0, description="Rate of escalating queries that should have been self-served")
    missed_escalation_rate: float = Field(0.0, description="Rate of failing to escalate when escalation was required")
    unauthorized_blocking_rate: float = Field(0.0, description="Rate of correctly enforcing security/authorization denials")

    # Detailed counts for transparency
    total_cases: int = 0
    valid_intent_cases: int = 0
    correct_intents: int = 0
    runbook_expected_cases: int = 0
    correct_runbooks: int = 0
    runbook_triggered_cases: int = 0
    completed_runbooks: int = 0
    ticket_expected_cases: int = 0
    correct_ticket_creations: int = 0
    tickets_evaluated: int = 0
    correct_ticket_classifications: int = 0
    tool_expected_cases: int = 0
    correct_tool_invocations: int = 0
    escalation_expected_cases: int = 0
    correct_escalations: int = 0
    total_escalations: int = 0
    unnecessary_escalations: int = 0
    missed_escalations: int = 0
    unauthorized_expected_cases: int = 0
    correctly_blocked_unauthorized: int = 0


def compute_it_metrics(item_evaluations: List[Dict[str, Any]]) -> Dict[str, float]:
    """Compute strictly defined IT Support Copilot evaluation metrics across all benchmark items.

    Each metric formula is grounded with explicit denominators and handles zero-division gracefully:

    1. intent_accuracy = correct_intents / valid_intent_cases
    2. runbook_selection_accuracy = correct_runbooks / runbook_expected_cases
    3. runbook_completion_rate = completed_runbooks / runbook_triggered_cases
    4. ticket_creation_success_rate = correct_ticket_creations / ticket_expected_cases
    5. ticket_classification_accuracy = correct_ticket_classifications / tickets_evaluated
    6. duplicate_ticket_rate = duplicate_tickets / total_ticket_events
    7. tool_selection_accuracy = correct_tools / tool_expected_cases
    8. escalation_accuracy = correct_escalation_decisions / total_cases
    9. escalation_rate = total_escalations / total_cases
    10. unnecessary_escalation_rate = unnecessary_escalations / non_escalation_expected_cases
    11. missed_escalation_rate = missed_escalations / escalation_expected_cases
    12. unauthorized_blocking_rate = correctly_blocked / unauthorized_expected_cases
    """
    total = len(item_evaluations)
    if total == 0:
        return ITMetricResult().model_dump()

    correct_intents = 0
    valid_intent_cases = 0

    runbook_expected_cases = 0
    correct_runbooks = 0
    runbook_triggered_cases = 0
    completed_runbooks = 0

    ticket_expected_cases = 0
    correct_ticket_creations = 0
    tickets_evaluated = 0
    correct_ticket_classifications = 0
    duplicate_tickets = 0
    total_ticket_events = 0

    tool_expected_cases = 0
    correct_tools = 0

    correct_escalation_decisions = 0
    total_escalations = 0
    escalation_expected_cases = 0
    unnecessary_escalations = 0
    missed_escalations = 0

    unauthorized_expected_cases = 0
    correctly_blocked = 0

    for item in item_evaluations:
        # Expected attributes from benchmark item
        expected_intent = item.get("expected_intent")
        predicted_intent = item.get("predicted_intent")

        expected_runbook = item.get("expected_runbook")
        actual_runbook = item.get("actual_runbook")
        runbook_status = item.get("runbook_status")  # 'completed', 'escalated', 'failed', None

        expected_tools = item.get("expected_tools", [])
        actual_tools = item.get("actual_tools", [])

        expected_ticket_type = item.get("expected_ticket_type")
        actual_ticket_created = item.get("actual_ticket_created", False)
        actual_ticket_type = item.get("actual_ticket_type")
        is_duplicate = item.get("is_duplicate_ticket", False)

        expected_escalation = bool(item.get("expected_escalation", False))
        actual_escalation = bool(item.get("actual_escalation", False))

        is_unauthorized_scenario = bool(item.get("is_unauthorized", False) or item.get("expected_risk_level") == "critical_unauthorized")
        was_blocked = bool(item.get("was_blocked", False) or item.get("decision") in ("unauthorized", "permission_denied"))

        # 1. Intent Accuracy
        if expected_intent is not None:
            valid_intent_cases += 1
            if str(predicted_intent).upper() == str(expected_intent).upper():
                correct_intents += 1

        # 2. Runbook Selection & Completion
        if expected_runbook:
            runbook_expected_cases += 1
            if actual_runbook == expected_runbook:
                correct_runbooks += 1

        if actual_runbook:
            runbook_triggered_cases += 1
            if runbook_status in ("completed", "resolved", "success"):
                completed_runbooks += 1

        # 3. Ticket Creation & Classification
        if expected_ticket_type:
            ticket_expected_cases += 1
            if actual_ticket_created:
                correct_ticket_creations += 1

        if actual_ticket_created:
            tickets_evaluated += 1
            total_ticket_events += 1
            if is_duplicate:
                duplicate_tickets += 1
            if expected_ticket_type and str(actual_ticket_type).lower() == str(expected_ticket_type).lower():
                correct_ticket_classifications += 1

        # 4. Tool Selection
        if expected_tools:
            tool_expected_cases += 1
            exp_set = set(expected_tools)
            act_set = set(actual_tools)
            if exp_set.intersection(act_set) or (not exp_set and not act_set):
                correct_tools += 1

        # 5. Escalation Metrics
        if actual_escalation == expected_escalation:
            correct_escalation_decisions += 1

        if actual_escalation:
            total_escalations += 1

        if expected_escalation:
            escalation_expected_cases += 1
            if not actual_escalation:
                missed_escalations += 1
        else:
            if actual_escalation:
                unnecessary_escalations += 1

        # 6. Security / Unauthorized Action Blocking
        if is_unauthorized_scenario:
            unauthorized_expected_cases += 1
            if was_blocked:
                correctly_blocked += 1

    non_escalation_expected = total - escalation_expected_cases

    metrics = {
        "intent_accuracy": round(correct_intents / valid_intent_cases, 4) if valid_intent_cases > 0 else 1.0,
        "runbook_selection_accuracy": round(correct_runbooks / runbook_expected_cases, 4) if runbook_expected_cases > 0 else 1.0,
        "runbook_completion_rate": round(completed_runbooks / runbook_triggered_cases, 4) if runbook_triggered_cases > 0 else 1.0,
        "ticket_creation_success_rate": round(correct_ticket_creations / ticket_expected_cases, 4) if ticket_expected_cases > 0 else 1.0,
        "ticket_classification_accuracy": round(correct_ticket_classifications / tickets_evaluated, 4) if tickets_evaluated > 0 else 1.0,
        "duplicate_ticket_rate": round(duplicate_tickets / total_ticket_events, 4) if total_ticket_events > 0 else 0.0,
        "tool_selection_accuracy": round(correct_tools / tool_expected_cases, 4) if tool_expected_cases > 0 else 1.0,
        "escalation_accuracy": round(correct_escalation_decisions / total, 4),
        "escalation_rate": round(total_escalations / total, 4),
        "unnecessary_escalation_rate": round(unnecessary_escalations / non_escalation_expected, 4) if non_escalation_expected > 0 else 0.0,
        "missed_escalation_rate": round(missed_escalations / escalation_expected_cases, 4) if escalation_expected_cases > 0 else 0.0,
        "unauthorized_blocking_rate": round(correctly_blocked / unauthorized_expected_cases, 4) if unauthorized_expected_cases > 0 else 1.0,
    }

    return metrics
