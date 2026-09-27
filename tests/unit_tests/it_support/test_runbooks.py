"""Unit tests for the IT troubleshooting runbook engine (Phase 13-C)."""

import pytest
from langgraph.checkpoint.memory import MemorySaver

from mcp_rag_agent.it_support.models import ITCategory
from mcp_rag_agent.it_support.runbooks.executor import RunbookExecutor
from mcp_rag_agent.it_support.runbooks.graph import create_runbook_subgraph
from mcp_rag_agent.it_support.runbooks.models import (
    Runbook,
    RunbookStatus,
    RunbookStep,
    StepActionType,
    StepOutcome,
)
from mcp_rag_agent.it_support.runbooks.registry import RunbookNotFoundError, RunbookRegistry, get_default_registry
from mcp_rag_agent.it_support.runbooks.tools import create_runbook_tool


def _create_sample_runbook(runbook_id: str = "rb_test_sample", version: str = "1.0.0") -> Runbook:
    """Helper creating a test runbook with step, retry, branching, and escalation."""
    steps = {
        "step_1": RunbookStep(
            step_id="step_1",
            title="Step 1: Check Basics",
            instruction="Please check that power is on.",
            expected_outcome="Power LED is green.",
            action_type=StepActionType.DIAGNOSTIC,
            max_retries=2,
            next_step_on_success="step_2",
            next_step_on_failure="step_fail_alt",
            branches={"reboot_needed": "step_reboot"},
        ),
        "step_reboot": RunbookStep(
            step_id="step_reboot",
            title="Step Reboot: Restart Machine",
            instruction="Restart the system and verify startup.",
            expected_outcome="System reboots cleanly.",
            action_type=StepActionType.INSTRUCTION,
            max_retries=1,
            next_step_on_success="step_2",
            next_step_on_failure="escalated",
        ),
        "step_fail_alt": RunbookStep(
            step_id="step_fail_alt",
            title="Step Fail Alternative: Auxiliary Check",
            instruction="Perform auxiliary hardware diagnostics.",
            expected_outcome="Auxiliary check complete.",
            action_type=StepActionType.DIAGNOSTIC,
            max_retries=1,
            next_step_on_success="step_2",
            next_step_on_failure="escalated",
        ),
        "step_2": RunbookStep(
            step_id="step_2",
            title="Step 2: Verify Functionality",
            instruction="Confirm whether service is responding.",
            expected_outcome="Service operational.",
            action_type=StepActionType.VERIFICATION,
            max_retries=1,
            next_step_on_success="resolved",
            next_step_on_failure="escalated",
        ),
    }
    return Runbook(
        runbook_id=runbook_id,
        title="Sample Test Runbook",
        description="Runbook for automated unit testing.",
        category=ITCategory.HARDWARE,
        version=version,
        initial_step_id="step_1",
        steps=steps,
        tags=["sample", "hardware", "power", "test"],
        escalation_team="Hardware Ops",
    )


class TestRunbookRegistrationAndLookup:
    """Test runbook registration, versioning, and retrieval."""

    def test_default_registry_contains_all_ten_standard_runbooks(self) -> None:
        registry = get_default_registry()
        active = registry.list_active()
        assert len(active) >= 10
        categories = {rb.category for rb in active}
        assert ITCategory.VPN in categories
        assert ITCategory.WIFI in categories
        assert ITCategory.MFA in categories
        assert ITCategory.PASSWORD in categories
        assert ITCategory.ACCESS in categories
        assert ITCategory.EMAIL in categories
        assert ITCategory.HARDWARE in categories
        assert ITCategory.SECURITY in categories

    def test_runbook_registration_and_active_versioning(self) -> None:
        registry = RunbookRegistry(auto_populate=False)
        rb_v1 = _create_sample_runbook(version="1.0.0")
        rb_v2 = _create_sample_runbook(version="2.0.0")

        registry.register(rb_v1)
        assert registry.get("rb_test_sample").version == "1.0.0"

        registry.register(rb_v2)
        # Latest active version becomes default
        assert registry.get("rb_test_sample").version == "2.0.0"
        # Explicit version retrieval
        assert registry.get("rb_test_sample", version="1.0.0").version == "1.0.0"

    def test_lookup_missing_runbook_raises_error(self) -> None:
        registry = RunbookRegistry(auto_populate=False)
        with pytest.raises(RunbookNotFoundError, match="is not registered"):
            registry.get("rb_non_existent")

    def test_category_filtering(self) -> None:
        registry = get_default_registry()
        vpn_runbooks = registry.get_by_category(ITCategory.VPN)
        assert len(vpn_runbooks) >= 1
        assert vpn_runbooks[0].runbook_id == "rb_vpn_troubleshooting"


class TestRunbookSelection:
    """Test heuristic and intent-assisted runbook selection from user queries."""

    def test_selection_by_exact_tag_and_title_keywords(self) -> None:
        registry = get_default_registry()
        rb_vpn = registry.find_for_query("I cannot connect to the corporate VPN")
        assert rb_vpn is not None
        assert rb_vpn.runbook_id == "rb_vpn_troubleshooting"

        rb_wifi = registry.find_for_query("Office Wi-Fi keeps disconnecting")
        assert rb_wifi is not None
        assert rb_wifi.runbook_id == "rb_wifi_troubleshooting"

        rb_mfa = registry.find_for_query("My MFA authenticator code is rejected")
        assert rb_mfa is not None
        assert rb_mfa.runbook_id == "rb_mfa_troubleshooting"

        rb_phish = registry.find_for_query("I clicked a suspicious phishing link in email")
        assert rb_phish is not None
        assert rb_phish.runbook_id == "rb_phishing_incident"

    def test_executor_select_and_start(self) -> None:
        executor = RunbookExecutor()
        result = executor.select_and_start(query="My external laptop monitor is black")
        assert result.runbook_id == "rb_laptop_display"
        assert result.status == RunbookStatus.IN_PROGRESS
        assert result.step_id == "disp_check_cables_dock"


class TestRunbookExecutionLifecycle:
    """Test the Step -> Evaluate -> Branch state machine execution."""

    def test_successful_runbook_completion(self) -> None:
        registry = RunbookRegistry(auto_populate=False)
        registry.register(_create_sample_runbook())
        executor = RunbookExecutor(registry=registry, checkpointer=MemorySaver())

        # Start at step_1
        res1 = executor.start_runbook("rb_test_sample")
        assert res1.status == RunbookStatus.IN_PROGRESS
        assert res1.step_id == "step_1"
        assert "check that power is on" in res1.instruction

        # Evaluate step_1: Success -> advances to step_2
        res2 = executor.execute_step(res1.execution_id, outcome=StepOutcome.SUCCESS)
        assert res2.status == RunbookStatus.IN_PROGRESS
        assert res2.step_id == "step_2"
        assert "whether service is responding" in res2.instruction

        # Evaluate step_2: Success -> reaches terminal RESOLVED
        res3 = executor.execute_step(res1.execution_id, outcome=StepOutcome.SUCCESS)
        assert res3.status == RunbookStatus.RESOLVED
        assert res3.is_terminal is True
        assert res3.step_id is None
        assert "completed successfully" in res3.instruction

    def test_failed_step_transitions_to_failure_path(self) -> None:
        registry = RunbookRegistry(auto_populate=False)
        registry.register(_create_sample_runbook())
        executor = RunbookExecutor(registry=registry, checkpointer=MemorySaver())

        res1 = executor.start_runbook("rb_test_sample")
        # Step 1 reports failure -> goes to step_fail_alt
        res2 = executor.execute_step(res1.execution_id, outcome=StepOutcome.FAILURE)
        assert res2.status == RunbookStatus.IN_PROGRESS
        assert res2.step_id == "step_fail_alt"

    def test_conditional_branching(self) -> None:
        registry = RunbookRegistry(auto_populate=False)
        registry.register(_create_sample_runbook())
        executor = RunbookExecutor(registry=registry, checkpointer=MemorySaver())

        res1 = executor.start_runbook("rb_test_sample")
        # Branch choice 'reboot_needed' defined on step_1
        res2 = executor.execute_step(
            res1.execution_id,
            outcome=StepOutcome.SUCCESS,
            branch_choice="reboot_needed",
        )
        assert res2.status == RunbookStatus.IN_PROGRESS
        assert res2.step_id == "step_reboot"

    def test_step_retry_logic(self) -> None:
        registry = RunbookRegistry(auto_populate=False)
        registry.register(_create_sample_runbook())
        executor = RunbookExecutor(registry=registry, checkpointer=MemorySaver())

        res1 = executor.start_runbook("rb_test_sample")
        assert res1.step_id == "step_1"

        # Retry 1 (max_retries=2) -> remains at step_1 with retry tag
        res_retry1 = executor.execute_step(res1.execution_id, outcome=StepOutcome.RETRY)
        assert res_retry1.step_id == "step_1"
        assert "[Retry Attempt 1/2]" in res_retry1.instruction

        # Retry 2 -> remains at step_1
        res_retry2 = executor.execute_step(res1.execution_id, outcome=StepOutcome.RETRY)
        assert res_retry2.step_id == "step_1"
        assert "[Retry Attempt 2/2]" in res_retry2.instruction

        # Retry 3 -> retries exhausted, falls back to next_step_on_failure ('step_fail_alt')
        res_retry3 = executor.execute_step(res1.execution_id, outcome=StepOutcome.RETRY)
        assert res_retry3.step_id == "step_fail_alt"

    def test_explicit_and_failure_escalation(self) -> None:
        registry = RunbookRegistry(auto_populate=False)
        registry.register(_create_sample_runbook())
        executor = RunbookExecutor(registry=registry, checkpointer=MemorySaver())

        # Direct escalation from step_1
        res1 = executor.start_runbook("rb_test_sample")
        res_esc = executor.execute_step(res1.execution_id, outcome=StepOutcome.ESCALATE)
        assert res_esc.status == RunbookStatus.ESCALATED
        assert res_esc.is_terminal is True
        assert "Escalating ticket to Hardware Ops" in res_esc.instruction


class TestStatePersistenceAndValidation:
    """Test state persistence across turns, checkpointer restoration, and input validation."""

    def test_state_restoration_across_executor_instances(self) -> None:
        shared_checkpointer = MemorySaver()
        registry = RunbookRegistry(auto_populate=False)
        registry.register(_create_sample_runbook())

        # Instance 1 starts runbook
        exec1 = RunbookExecutor(registry=registry, checkpointer=shared_checkpointer)
        res1 = exec1.start_runbook("rb_test_sample", thread_id="session_persisted_99")
        exec_id = res1.execution_id

        # Instance 2 resumes same execution from checkpointer
        exec2 = RunbookExecutor(registry=registry, checkpointer=shared_checkpointer)
        res_resumed = exec2.resume_runbook(exec_id)
        assert res_resumed.step_id == "step_1"
        assert res_resumed.status == RunbookStatus.IN_PROGRESS

        # Instance 2 advances the step
        res2 = exec2.execute_step(exec_id, outcome=StepOutcome.SUCCESS)
        assert res2.step_id == "step_2"

        # Check full persisted state model
        state = exec2.get_state(exec_id)
        assert state is not None
        assert state.current_step_id == "step_2"
        assert len(state.history) == 1
        assert state.history[0].step_id == "step_1"
        assert state.history[0].outcome == StepOutcome.SUCCESS

    def test_advancing_terminal_runbook_raises_value_error(self) -> None:
        registry = RunbookRegistry(auto_populate=False)
        registry.register(_create_sample_runbook())
        executor = RunbookExecutor(registry=registry, checkpointer=MemorySaver())

        res1 = executor.start_runbook("rb_test_sample")
        executor.execute_step(res1.execution_id, outcome=StepOutcome.ESCALATE)

        # Trying to advance after escalation raises ValueError
        with pytest.raises(ValueError, match="already reached terminal status"):
            executor.execute_step(res1.execution_id, outcome=StepOutcome.SUCCESS)

    def test_invalid_outcome_string_raises_value_error(self) -> None:
        registry = RunbookRegistry(auto_populate=False)
        registry.register(_create_sample_runbook())
        executor = RunbookExecutor(registry=registry, checkpointer=MemorySaver())

        res1 = executor.start_runbook("rb_test_sample")
        with pytest.raises(ValueError, match="Invalid outcome"):
            executor.execute_step(res1.execution_id, outcome="unsupported_outcome")

    def test_invalid_graph_transition_raises_error_at_validation(self) -> None:
        invalid_step = RunbookStep(
            step_id="bad_step",
            title="Broken Step",
            instruction="Broken",
            next_step_on_success="non_existent_step",
            next_step_on_failure="escalated",
        )
        broken_runbook = Runbook(
            runbook_id="rb_broken",
            title="Broken Runbook",
            description="Broken",
            category=ITCategory.HARDWARE,
            initial_step_id="bad_step",
            steps={"bad_step": invalid_step},
        )
        with pytest.raises(ValueError, match="points to unknown target 'non_existent_step'"):
            broken_runbook.validate_graph()


class TestRunbookToolIntegration:
    """Test LangChain execute_runbook_step tool interface."""

    def test_tool_list_action(self) -> None:
        tool = create_runbook_tool()
        output = tool.invoke({"action": "list"})
        assert "[AVAILABLE RUNBOOKS]" in output
        assert "rb_vpn_troubleshooting" in output
        assert "rb_wifi_troubleshooting" in output

    def test_tool_start_and_evaluate_flow(self) -> None:
        tool = create_runbook_tool()
        start_res = tool.invoke({"action": "start", "runbook_id": "rb_vpn_troubleshooting"})
        assert "[RUNBOOK STARTED: rb_vpn_troubleshooting" in start_res
        assert "vpn_check_internet" in start_res

        # Extract execution ID
        for line in start_res.splitlines():
            if line.startswith("Execution ID: "):
                exec_id = line.split("Execution ID: ")[1].strip()
                break

        # Advance step via tool
        eval_res = tool.invoke({
            "action": "evaluate",
            "execution_id": exec_id,
            "step_outcome": "success",
            "user_feedback": "Internet loads fine without VPN",
        })
        assert "[RUNBOOK ADVANCED: Step vpn_restart_service]" in eval_res

        # Check status via tool
        status_res = tool.invoke({"action": "status", "execution_id": exec_id})
        assert "[RUNBOOK STATUS]" in status_res
        assert "vpn_restart_service" in status_res
