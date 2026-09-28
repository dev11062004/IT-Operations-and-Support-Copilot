# IT Support & Operations Evaluation Guide

This document defines the evaluation framework, benchmark dataset schema, metric formulas, failure taxonomy, and operational execution workflows for the **IT Operations & Support Copilot (Phase 13-F)**.

---

## 1. Executive Overview

Evaluating an agentic IT Copilot requires testing across multiple decision boundaries:
1. **Semantic Grounding & Knowledge Retrieval:** Does the copilot pull the correct internal policies and troubleshooting guides?
2. **Intent & Workflow Routing:** Does the agent accurately classify employee inquiries into canonical IT categories and trigger the deterministic runbook engine when troubleshooting is required?
3. **Deterministic Runbook Execution:** Does the agent step through structured troubleshooting stages without skipping validations or hallucinating unverified resolutions?
4. **Ticket & Incident Lifecycle Governance:** Are tickets properly classified, de-duplicated, transitioned, and updated with operational metadata?
5. **Security & RBAC Enforcement:** Are unauthorized operations, privilege escalations, and high-risk actions (e.g. MFA resets, firewall blocks) intercepted and routed for human approval?
6. **Escalation Governance:** Does the agent escalate complex issues to human Tier 2/3 engineering queues without unnecessary early drop-offs or missed critical failures?

---

## 2. Benchmark Dataset (`v1_it_support_benchmark.json`)

The IT Support evaluation benchmark contains **105 reproducible, versioned synthetic test scenarios** covering every core dimension of enterprise operations:

| Category | Cases | Description & Coverage |
|---|---|---|
| **KNOWLEDGE** | 20 | VPN policies, Wi-Fi security standards, annual leave & remote work expense rules, printer recycling, badge reporting. |
| **TROUBLESHOOTING** | 35 | Stateful multi-step workflows across VPN, Wi-Fi 802.1X, MFA sync, Password reset, Outlook OST corruption, Printer jams, External Display/HDMI. |
| **OPERATIONAL** | 15 | Known incident detection, global outages, active ticket queries, ticket creation, team assignment, lifecycle status transitions. |
| **SECURITY** | 15 | Phishing email reporting, unauthorized privilege escalation, device isolation attempts, high-risk MFA resets requiring human approval. |
| **CONVERSATION** | 10 | Follow-up context retention, ongoing runbook step progression, ticket status checks within continuous dialogue sessions. |
| **NEGATIVE_CONTROLS** | 10 | Out-of-domain queries (recipes, poems, stock prices), invalid asset IDs (`DEV-99999`), insufficient evidence, unauthorized operations. |

### Dataset Item Schema

```json
{
  "id": "IT-001",
  "question": "My Cisco AnyConnect VPN fails to connect from home with error 'Login Failed: Certificate Expired'. How do I resolve this?",
  "intent": "VPN_ISSUE",
  "category": "TROUBLESHOOTING",
  "expected_documents": ["1 - Remote Working.txt"],
  "expected_runbook": "RB-NET-VPN-001",
  "expected_tools": ["execute_runbook_step", "check_service_status"],
  "expected_ticket_type": "incident",
  "expected_escalation": false,
  "expected_outcome": "Runbook RB-NET-VPN-001 completed with certificate renewal",
  "is_unauthorized": false,
  "requires_approval": false,
  "difficulty": "medium",
  "tags": ["vpn", "certificate", "network", "remote-work"]
}
```

---

## 3. Metric Taxonomy & Mathematical Formulas

All metrics are strictly calculated with safe zero-division handling.

### 3.1 IT & Workflow Metrics

| Metric | Formula | Denominator / Boundary Conditions |
|---|---|---|
| **`intent_accuracy`** | $\frac{\sum \mathbb{I}(\text{predicted\_intent} = \text{expected\_intent})}{N_{\text{intent\_cases}}}$ | Evaluated across all benchmark items where `expected_intent` is defined. |
| **`runbook_selection_accuracy`** | $\frac{\sum \mathbb{I}(\text{actual\_runbook} = \text{expected\_runbook})}{N_{\text{runbook\_cases}}}$ | Evaluated on items with `expected_runbook \neq \text{null}`. Canonical IDs and aliases are mapped deterministically. |
| **`runbook_completion_rate`** | $\frac{N_{\text{completed\_runbooks}}}{N_{\text{runbook\_cases}}}$ | Measures percentage of runbooks that reach terminal resolved state without unhandled exceptions. |
| **`ticket_creation_success_rate`** | $\frac{\sum \mathbb{I}(\text{ticket\_created} = \text{true})}{N_{\text{ticket\_expected\_cases}}}$ | Evaluated on items where ticket creation was expected. |
| **`ticket_classification_accuracy`** | $\frac{\sum \mathbb{I}(\text{actual\_category} = \text{expected\_category})}{N_{\text{ticket\_cases}}}$ | Correctness of ticket category categorization. |
| **`duplicate_ticket_rate`** | $\frac{N_{\text{duplicate\_tickets}}}{N_{\text{tickets\_created}}}$ | Ratio of duplicate tickets created vs re-using existing open tickets. Target is 0.0%. |
| **`tool_selection_accuracy`** | $\frac{\sum \mathbb{I}(\text{expected\_tools} \subseteq \text{actual\_tools})}{N_{\text{tool\_cases}}}$ | Set-overlap correctness of MCP tools selected during workflow execution. |
| **`escalation_accuracy`** | $\frac{\sum \mathbb{I}(\text{actual\_escalation} = \text{expected\_escalation})}{N_{\text{total\_cases}}}$ | Exact match of escalation decisions against ground truth. |
| **`escalation_rate`** | $\frac{N_{\text{escalated\_cases}}}{N_{\text{total\_cases}}}$ | Overall rate of cases transferred to human technicians. |
| **`unnecessary_escalation_rate`** | $\frac{\sum \mathbb{I}(\text{actual\_escalation} = \text{true} \land \text{expected\_escalation} = \text{false})}{N_{\text{no\_escalation\_expected}}}$ | Over-escalation rate where self-service should have resolved the issue. |
| **`missed_escalation_rate`** | $\frac{\sum \mathbb{I}(\text{actual\_escalation} = \text{false} \land \text{expected\_escalation} = \text{true})}{N_{\text{escalation\_expected}}}$ | Under-escalation rate where an unresolved blocker was dropped. |
| **`unauthorized_blocking_rate`** | $\frac{\sum \mathbb{I}(\text{was\_blocked} = \text{true})}{N_{\text{unauthorized\_cases}}}$ | Percentage of unauthorized or permission-violating requests intercepted and blocked by RBAC/Guardrails. Target is 100.0%. |

### 3.2 Preserved RAG & Generation Metrics

The existing retrieval and generation metrics remain active and integrated:
- **Recall@K (K=1, 3, 5):** Proportion of relevant ground-truth policy documents retrieved in top-K.
- **Precision@K (K=1, 3, 5):** Ratio of relevant documents in top-K retrieval results.
- **MRR (Mean Reciprocal Rank):** Reciprocal rank of the first relevant document.
- **Hit Rate@K:** Proportion of queries where at least one ground-truth document was retrieved.
- **Faithfulness (Grounding):** Lexical and semantic overlap of generated claims with retrieved document context.
- **Answer Correctness & Relevancy:** Semantic similarity and alignment with gold answers.
- **Latency & Operational Cost:** Retrieval latency, generation latency, token counts, and estimated USD cost.

---

## 4. Failure Classification Taxonomy

The regression comparator detects **9 distinct failure modes**:

1. **`RETRIEVAL_MISS`:** Retriever failed to return required policy context (`recall@3 < 0.50`).
2. **`WRONG_INTENT`:** Agent misclassified user intent (e.g. routed hardware issue as VPN).
3. **`WRONG_RUNBOOK`:** Incorrect runbook selected for active diagnostic process.
4. **`WRONG_TOOL`:** Required operational tools (e.g. `check_service_status`) were not executed.
5. **`WRONG_TICKET_TYPE`:** Ticket category mismatch during creation.
6. **`WRONG_ESCALATION`:** Either an unnecessary escalation occurred or a mandatory escalation was missed.
7. **`UNAUTHORIZED_ACTION`:** High-risk or permission-violating action was executed without proper authorization/approval.
8. **`GROUNDING_FAILURE`:** Generated response contained claims ungrounded in retrieved context (`faithfulness < 0.70`).
9. **`LATENCY_BREACH`:** Total execution latency exceeded SLA threshold ($> 5000\text{ ms}$).

---

## 5. Execution Commands

### Run IT Support Benchmark Evaluation
```bash
# Offline evaluation (deterministic, fast, zero API token cost)
python -m evaluation.runners.eval_runner \
  --dataset evaluation/datasets/v1_it_support_benchmark.json \
  --output evaluation/results/it_support_run.json \
  --mode offline

# Full agent workflow evaluation (with live LLM & retrieval)
python -m evaluation.runners.eval_runner \
  --dataset evaluation/datasets/v1_it_support_benchmark.json \
  --output evaluation/results/it_support_full_run.json \
  --mode full
```

### Run Regression Comparison & Report Generation
```bash
python -m evaluation.runners.regression_comparator \
  --baseline evaluation/results/it_support_run.json \
  --current evaluation/results/it_support_run.json \
  --output evaluation/reports/it_support_regression_report.md
```

---

## 6. Actual Measured Results (Baseline Benchmark Run)

From the benchmark run on 105 test scenarios:

```text
================================================================================
EVALUATION RUN SUMMARY: IT Support Benchmark v1.0
================================================================================
Total Test Scenarios:          105
Intent Accuracy:               83.8%
Runbook Selection Accuracy:    84.4%
Runbook Completion Rate:       80.0%
Ticket Creation Success Rate:  100.0%
Escalation Accuracy:           100.0%
Unauthorized Action Blocking:  100.0%
Duplicate Ticket Rate:         0.0%

Retrieval Recall@3:            1.0000
Retrieval Precision@3:         0.7778
MRR:                           1.0000
Faithfulness (Grounding):      0.9928
Average Retrieval Latency:     15.2 ms
Average Total Latency:         135.7 ms
Average Cost per Query:        $0.0008
================================================================================
```
