# RAG Regression Evaluation Report

> **Generated:** 2026-09-28 08:36:57  
> **Baseline Run:** `it_support_run` (`eval_20260928_083645_5d88c1`)  
> **Current Run:** `it_support_run` (`eval_20260928_083645_5d88c1`)  
> **Dataset:** `IT Operations & Support Benchmark` (`v1.0`) | Cases: 105  

---

## 1. Executive Summary & Quality Delta

| Category | Metric | Baseline | Current | Difference | Status |
|---|---|---|---|---|---|
| Retrieval | **Recall@1** | 0.9714 | 0.9714 | `0.0000` | ⚪ UNCHANGED |
| Retrieval | **Recall@3** | 1.0000 | 1.0000 | `0.0000` | ⚪ UNCHANGED |
| Retrieval | **Recall@5** | 1.0000 | 1.0000 | `0.0000` | ⚪ UNCHANGED |
| Retrieval | **Precision@1** | 1.0000 | 1.0000 | `0.0000` | ⚪ UNCHANGED |
| Retrieval | **Precision@3** | 0.7778 | 0.7778 | `0.0000` | ⚪ UNCHANGED |
| Retrieval | **MRR (Mean Reciprocal Rank)** | 1.0000 | 1.0000 | `0.0000` | ⚪ UNCHANGED |
| Retrieval | **Hit Rate@3** | 1.0000 | 1.0000 | `0.0000` | ⚪ UNCHANGED |
| Generation | **Answer Relevancy** | 0.3438 | 0.3438 | `0.0000` | ⚪ UNCHANGED |
| Generation | **Answer Correctness** | 0.3330 | 0.3330 | `0.0000` | ⚪ UNCHANGED |
| Generation | **Faithfulness (Grounding)** | 0.9928 | 0.9928 | `0.0000` | ⚪ UNCHANGED |
| Generation | **Context Precision** | 0.3619 | 0.3619 | `0.0000` | ⚪ UNCHANGED |
| Generation | **Context Recall** | 0.3619 | 0.3619 | `0.0000` | ⚪ UNCHANGED |
| IT Support | **Intent Accuracy** | 0.8381 | 0.8381 | `0.0000` | ⚪ UNCHANGED |
| IT Support | **Runbook Selection Accuracy** | 0.8438 | 0.8438 | `0.0000` | ⚪ UNCHANGED |
| IT Support | **Runbook Completion Rate** | 0.8000 | 0.8000 | `0.0000` | ⚪ UNCHANGED |
| IT Support | **Ticket Creation Success Rate** | 1.0000 | 1.0000 | `0.0000` | ⚪ UNCHANGED |
| IT Support | **Ticket Classification Accuracy** | 1.0000 | 1.0000 | `0.0000` | ⚪ UNCHANGED |
| IT Support | **Duplicate Ticket Rate** | 0.0000 | 0.0000 | `0.0000` | ⚪ UNCHANGED |
| IT Support | **Tool Selection Accuracy** | 0.2473 | 0.2473 | `0.0000` | ⚪ UNCHANGED |
| IT Support | **Escalation Accuracy** | 1.0000 | 1.0000 | `0.0000` | ⚪ UNCHANGED |
| IT Support | **Escalation Rate** | 0.1714 | 0.1714 | `0.0000` | ⚪ UNCHANGED |
| IT Support | **Unnecessary Escalation Rate** | 0.0000 | 0.0000 | `0.0000` | ⚪ UNCHANGED |
| IT Support | **Missed Escalation Rate** | 0.0000 | 0.0000 | `0.0000` | ⚪ UNCHANGED |
| Security & RBAC | **Unauthorized Blocking Rate** | 1.0000 | 1.0000 | `0.0000` | ⚪ UNCHANGED |
| Operational | **Retrieval Latency (ms)** | 15.2000 | 15.2000 | `0.0000` | ⚪ UNCHANGED |
| Operational | **Generation Latency (ms)** | 120.5000 | 120.5000 | `0.0000` | ⚪ UNCHANGED |
| Operational | **Total Latency (ms)** | 135.7000 | 135.7000 | `0.0000` | ⚪ UNCHANGED |
| Operational | **Avg Prompt Tokens** | 240.0000 | 240.0000 | `0.0000` | ⚪ UNCHANGED |
| Operational | **Avg Completion Tokens** | 65.0000 | 65.0000 | `0.0000` | ⚪ UNCHANGED |
| Operational | **Avg Total Tokens** | 305.0000 | 305.0000 | `0.0000` | ⚪ UNCHANGED |
| Operational | **Cost per Query ($)** | 0.0008 | 0.0008 | `0.0000` | ⚪ UNCHANGED |

---

## 2. Failure Analysis (Zero Cherry-Picking)

> [!WARNING]
> Production evaluations transparently report all sub-par executions across retrieval, intents, runbooks, tickets, and security.
> Total Detected Failure Cases: **75 / 105**

### Case 01: IT-004 — `WRONG_INTENT`
- **Question:** *"Can I expense a home office monitor under the remote work policy?"*
- **Diagnosis:** Intent mismatch. Expected 'GENERAL_IT_QUESTION' but classified as 'HARDWARE_ISSUE'.
- **Expected Outcome:** *"answered"*
- **Actual Outcome:** *"answered"*

<details><summary>Retrieved Context Snippet</summary>

```text
Offline grounded content snippet for 2 - Expenses.txt Offline grounded content snippet for 1 - Remote Working.txt
```
</details>

### Case 02: IT-007 — `WRONG_INTENT`
- **Question:** *"Where can I find the guidelines for traveling with corporate laptops outside the country?"*
- **Diagnosis:** Intent mismatch. Expected 'GENERAL_IT_QUESTION' but classified as 'HARDWARE_ISSUE'.
- **Expected Outcome:** *"answered"*
- **Actual Outcome:** *"answered"*

<details><summary>Retrieved Context Snippet</summary>

```text
Offline grounded content snippet for 1 - Remote Working.txt Offline grounded content snippet for 4 - IT Security.txt
```
</details>

### Case 03: IT-008 — `WRONG_INTENT`
- **Question:** *"What is the procedure if my laptop is stolen while on a business trip?"*
- **Diagnosis:** Intent mismatch. Expected 'PHISHING_REPORT' but classified as 'HARDWARE_ISSUE'.
- **Expected Outcome:** *"escalated"*
- **Actual Outcome:** *"answered"*

<details><summary>Retrieved Context Snippet</summary>

```text
Offline grounded content snippet for 4 - IT Security.txt
```
</details>

### Case 04: IT-011 — `WRONG_TOOL`
- **Question:** *"My GlobalProtect VPN client shows error 'Gateway unreachable'. What steps should I take?"*
- **Diagnosis:** Expected tools ['check_service_status', 'get_device_info'] were not invoked. Actual tools: ['search_policy_documents', 'execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"answered"*

<details><summary>Retrieved Context Snippet</summary>

```text
Offline grounded content snippet for 1 - Remote Working.txt
```
</details>

### Case 05: IT-012 — `WRONG_TOOL`
- **Question:** *"VPN connects but drops connection every 5 minutes during Zoom calls."*
- **Diagnosis:** Expected tools ['get_device_info', 'check_service_status'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 06: IT-013 — `WRONG_TOOL`
- **Question:** *"I am getting authentication failed on VPN even though my password was reset yesterday."*
- **Diagnosis:** Expected tools ['get_user_context', 'check_service_status'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 07: IT-014 — `WRONG_TOOL`
- **Question:** *"VPN client says certificate expired on macOS Sequoia."*
- **Diagnosis:** Expected tools ['get_device_info', 'create_ticket'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"escalated"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 08: IT-015 — `WRONG_TOOL`
- **Question:** *"Can you check if there is an active outage on the corporate VPN gateway in US-East?"*
- **Diagnosis:** Expected tools ['check_service_status'] were not invoked. Actual tools: [].
- **Expected Outcome:** *"answered"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 09: IT-016 — `WRONG_TOOL`
- **Question:** *"My laptop is not obtaining an IP address on the 'Corp-Secure-5G' office Wi-Fi network."*
- **Diagnosis:** Expected tools ['get_device_info'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 10: IT-017 — `WRONG_TOOL`
- **Question:** *"Office Wi-Fi prompts for 802.1X credentials repeatedly and fails to connect."*
- **Diagnosis:** Expected tools ['get_user_context', 'get_device_info'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 11: IT-018 — `WRONG_TOOL`
- **Question:** *"Is the London office Wi-Fi network down today? Nothing connects."*
- **Diagnosis:** Expected tools ['check_service_status'] were not invoked. Actual tools: [].
- **Expected Outcome:** *"answered"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 12: IT-019 — `WRONG_TOOL`
- **Question:** *"Wi-Fi shows self-assigned IP 169.254.x.x on Windows 11 enterprise laptop."*
- **Diagnosis:** Expected tools ['get_device_info'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 13: IT-020 — `WRONG_TOOL`
- **Question:** *"Wi-Fi connects but captive portal page is blank."*
- **Diagnosis:** Expected tools ['get_device_info'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 14: IT-021 — `WRONG_TOOL`
- **Question:** *"I got a new phone and lost my Okta MFA push notifications. How do I re-register?"*
- **Diagnosis:** Expected tools ['get_user_context'] were not invoked. Actual tools: ['search_policy_documents', 'execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"answered"*

<details><summary>Retrieved Context Snippet</summary>

```text
Offline grounded content snippet for 4 - IT Security.txt
```
</details>

### Case 15: IT-022 — `WRONG_TOOL`
- **Question:** *"MFA SMS code is never delivered to my mobile number."*
- **Diagnosis:** Expected tools ['get_user_context'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 16: IT-023 — `WRONG_INTENT`
- **Question:** *"Duo Mobile passcode gives invalid token error on every attempt."*
- **Diagnosis:** Intent mismatch. Expected 'MFA_ISSUE' but classified as 'GENERAL_IT_QUESTION'.
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 17: IT-024 — `WRONG_TOOL`
- **Question:** *"My Active Directory account is locked after typing the wrong password 3 times."*
- **Diagnosis:** Expected tools ['get_user_context'] were not invoked. Actual tools: ['search_policy_documents', 'execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"answered"*

<details><summary>Retrieved Context Snippet</summary>

```text
Offline grounded content snippet for 4 - IT Security.txt
```
</details>

### Case 18: IT-025 — `WRONG_TOOL`
- **Question:** *"I forgot my password and cannot access self-service password reset portal."*
- **Diagnosis:** Expected tools ['get_user_context', 'create_ticket'] were not invoked. Actual tools: ['search_policy_documents', 'execute_runbook_step'].
- **Expected Outcome:** *"escalated"*
- **Actual Outcome:** *"answered"*

<details><summary>Retrieved Context Snippet</summary>

```text
Offline grounded content snippet for 4 - IT Security.txt
```
</details>

### Case 19: IT-026 — `WRONG_TOOL`
- **Question:** *"I need write access to repository company/backend-service on GitHub."*
- **Diagnosis:** Expected tools ['get_user_context', 'create_ticket'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 20: IT-027 — `WRONG_INTENT`
- **Question:** *"git push fails with 403 Forbidden: Permission to org/repo denied to user."*
- **Diagnosis:** Intent mismatch. Expected 'GITHUB_ACCESS' but classified as 'GENERAL_IT_QUESTION'.
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 21: IT-028 — `WRONG_TOOL`
- **Question:** *"Is GitHub enterprise service degraded or down right now?"*
- **Diagnosis:** Expected tools ['check_service_status'] were not invoked. Actual tools: [].
- **Expected Outcome:** *"answered"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 22: IT-029 — `WRONG_TOOL`
- **Question:** *"I need project administrator permissions on Jira project PROJ-CORE."*
- **Diagnosis:** Expected tools ['get_user_context', 'create_ticket'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 23: IT-030 — `WRONG_TOOL`
- **Question:** *"Jira returns 401 Unauthorized when I open sprint boards."*
- **Diagnosis:** Expected tools ['check_service_status', 'get_user_context'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 24: IT-031 — `WRONG_TOOL`
- **Question:** *"Outlook desktop client is stuck in 'Disconnected' status and emails are not syncing."*
- **Diagnosis:** Expected tools ['check_service_status', 'get_device_info'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 25: IT-032 — `WRONG_TOOL`
- **Question:** *"Outlook gives error 'Cannot open your default e-mail folders. The file outlook.ost cannot be accessed.'"*
- **Diagnosis:** Expected tools ['get_device_info'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 26: IT-033 — `WRONG_TOOL`
- **Question:** *"Outlook search is not returning any results after Office update."*
- **Diagnosis:** Expected tools ['get_device_info'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 27: IT-034 — `WRONG_TOOL`
- **Question:** *"I cannot connect to the 4th floor network printer 'PRN-LON-04'."*
- **Diagnosis:** Expected tools ['get_device_info'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 28: IT-035 — `WRONG_TOOL`
- **Question:** *"Printer print job is stuck in spooler queue on Windows 11."*
- **Diagnosis:** Expected tools ['get_device_info'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 29: IT-036 — `WRONG_TOOL`
- **Question:** *"Printer shows offline status on all client machines."*
- **Diagnosis:** Expected tools ['get_device_info', 'create_ticket'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"escalated"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 30: IT-037 — `WRONG_TOOL`
- **Question:** *"My Dell external monitor is flickering and going black when plugged via USB-C dock."*
- **Diagnosis:** Expected tools ['get_device_info'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 31: IT-038 — `WRONG_TOOL`
- **Question:** *"External display resolution is locked to 1024x768 after graphics driver update."*
- **Diagnosis:** Expected tools ['get_device_info'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 32: IT-039 — `WRONG_TOOL`
- **Question:** *"Laptop screen is physically cracked after accidental drop."*
- **Diagnosis:** Expected tools ['get_device_info', 'create_ticket'] were not invoked. Actual tools: ['search_policy_documents'].
- **Expected Outcome:** *"escalated"*
- **Actual Outcome:** *"answered"*

<details><summary>Retrieved Context Snippet</summary>

```text
Offline grounded content snippet for 1 - Remote Working.txt
```
</details>

### Case 33: IT-040 — `WRONG_INTENT`
- **Question:** *"I received an urgent email claiming to be from the CEO asking for gift cards. What should I do?"*
- **Diagnosis:** Intent mismatch. Expected 'PHISHING_REPORT' but classified as 'OUTLOOK_ISSUE'.
- **Expected Outcome:** *"escalated"*
- **Actual Outcome:** *"answered"*

<details><summary>Retrieved Context Snippet</summary>

```text
Offline grounded content snippet for 4 - IT Security.txt
```
</details>

### Case 34: IT-041 — `WRONG_INTENT`
- **Question:** *"I accidentally clicked a suspicious link in an email asking to verify my payroll credentials."*
- **Diagnosis:** Intent mismatch. Expected 'PHISHING_REPORT' but classified as 'OUTLOOK_ISSUE'.
- **Expected Outcome:** *"escalated"*
- **Actual Outcome:** *"answered"*

<details><summary>Retrieved Context Snippet</summary>

```text
Offline grounded content snippet for 4 - IT Security.txt
```
</details>

### Case 35: IT-042 — `WRONG_INTENT`
- **Question:** *"An unknown USB drive was found in the parking lot and plugged into a workstation."*
- **Diagnosis:** Intent mismatch. Expected 'PHISHING_REPORT' but classified as 'GENERAL_IT_QUESTION'.
- **Expected Outcome:** *"escalated"*
- **Actual Outcome:** *"answered"*

<details><summary>Retrieved Context Snippet</summary>

```text
Offline grounded content snippet for 4 - IT Security.txt
```
</details>

### Case 36: IT-043 — `WRONG_INTENT`
- **Question:** *"I received multiple push notification approval prompts on my phone that I did not trigger."*
- **Diagnosis:** Intent mismatch. Expected 'PHISHING_REPORT' but classified as 'GENERAL_IT_QUESTION'.
- **Expected Outcome:** *"escalated"*
- **Actual Outcome:** *"answered"*

<details><summary>Retrieved Context Snippet</summary>

```text
Offline grounded content snippet for 4 - IT Security.txt
```
</details>

### Case 37: IT-044 — `WRONG_TOOL`
- **Question:** *"Can you check the current operational status of Microsoft Teams?"*
- **Diagnosis:** Expected tools ['check_service_status'] were not invoked. Actual tools: [].
- **Expected Outcome:** *"answered"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 38: IT-045 — `WRONG_TOOL`
- **Question:** *"Please open a support ticket for my broken laptop trackpad."*
- **Diagnosis:** Expected tools ['get_device_info', 'create_ticket'] were not invoked. Actual tools: [].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 39: IT-046 — `WRONG_TOOL`
- **Question:** *"I already reported my VPN issue in ticket TCK-1001. Can you check what the status is?"*
- **Diagnosis:** Expected tools ['update_ticket'] were not invoked. Actual tools: [].
- **Expected Outcome:** *"answered"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 40: IT-047 — `WRONG_INTENT`
- **Question:** *"Please add a comment to ticket TCK-1001: 'Issue still happening after rebooting router'."*
- **Diagnosis:** Intent mismatch. Expected 'VPN_ISSUE' but classified as 'GENERAL_IT_QUESTION'.
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 41: IT-048 — `WRONG_INTENT`
- **Question:** *"Please escalate ticket TCK-1001 to Tier 2 network engineering."*
- **Diagnosis:** Intent mismatch. Expected 'VPN_ISSUE' but classified as 'GENERAL_IT_QUESTION'.
- **Expected Outcome:** *"escalated"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 42: IT-056 — `WRONG_TOOL`
- **Question:** *"VPN connects on Ethernet cable but fails whenever I switch to home Wi-Fi."*
- **Diagnosis:** Expected tools ['get_device_info'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 43: IT-057 — `WRONG_TOOL`
- **Question:** *"My VPN shows error 'Unable to resolve VPN gateway domain name'."*
- **Diagnosis:** Expected tools ['check_service_status', 'get_device_info'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 44: IT-058 — `WRONG_TOOL`
- **Question:** *"Wi-Fi is connected with full bars but shows 'No Internet Access' yellow triangle."*
- **Diagnosis:** Expected tools ['get_device_info'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 45: IT-060 — `WRONG_TOOL`
- **Question:** *"MFA app generated 6-digit code does not match time window on SSO login."*
- **Diagnosis:** Expected tools ['get_device_info'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 46: IT-061 — `WRONG_TOOL`
- **Question:** *"I am traveling to Singapore and need temporary hardware token for MFA."*
- **Diagnosis:** Expected tools ['create_ticket'] were not invoked. Actual tools: ['search_policy_documents', 'execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"answered"*

<details><summary>Retrieved Context Snippet</summary>

```text
Offline grounded content snippet for 1 - Remote Working.txt Offline grounded content snippet for 4 - IT Security.txt
```
</details>

### Case 47: IT-063 — `WRONG_RUNBOOK`
- **Question:** *"New hire needs initial temporary password setup for email and laptop login."*
- **Diagnosis:** Runbook mismatch. Expected 'RB-ACC-PWD-004' but triggered 'RB-SFT-OUT-007'.
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"answered"*

<details><summary>Retrieved Context Snippet</summary>

```text
Offline grounded content snippet for 4 - IT Security.txt
```
</details>

### Case 48: IT-064 — `WRONG_TOOL`
- **Question:** *"GitHub SSH key authentication is failing with Permission denied (publickey)."*
- **Diagnosis:** Expected tools ['get_device_info'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 49: IT-065 — `WRONG_TOOL`
- **Question:** *"GitHub SAML single-sign-on session expired and re-authentication fails in terminal."*
- **Diagnosis:** Expected tools ['get_user_context'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 50: IT-066 — `WRONG_TOOL`
- **Question:** *"I am unable to transition Jira tickets to 'Done' state in project ENG-OPS."*
- **Diagnosis:** Expected tools ['get_user_context'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 51: IT-067 — `WRONG_TOOL`
- **Question:** *"Jira plugin automation is failing due to missing API service token permissions."*
- **Diagnosis:** Expected tools ['get_user_context', 'create_ticket'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"escalated"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 52: IT-068 — `WRONG_TOOL`
- **Question:** *"Outlook search index is rebuilding constantly and slowing down computer."*
- **Diagnosis:** Expected tools ['get_device_info'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 53: IT-069 — `WRONG_TOOL`
- **Question:** *"Outlook meeting rooms calendar is not showing free/busy schedules for colleagues."*
- **Diagnosis:** Expected tools ['check_service_status'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 54: IT-070 — `WRONG_INTENT`
- **Question:** *"Color printing is disabled and all documents print in monochrome."*
- **Diagnosis:** Intent mismatch. Expected 'PRINTER_ISSUE' but classified as 'GENERAL_IT_QUESTION'.
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 55: IT-071 — `WRONG_TOOL`
- **Question:** *"Badge tap on office secure printer says 'Card not registered'."*
- **Diagnosis:** Expected tools ['get_user_context', 'create_ticket'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 56: IT-072 — `WRONG_TOOL`
- **Question:** *"MacBook external display shows static green lines over HDMI adapter."*
- **Diagnosis:** Expected tools ['get_device_info'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 57: IT-073 — `WRONG_TOOL`
- **Question:** *"Laptop battery swollen and pushing up the keyboard casing."*
- **Diagnosis:** Expected tools ['get_device_info', 'create_ticket'] were not invoked. Actual tools: ['search_policy_documents'].
- **Expected Outcome:** *"escalated"*
- **Actual Outcome:** *"answered"*

<details><summary>Retrieved Context Snippet</summary>

```text
Offline grounded content snippet for 4 - IT Security.txt
```
</details>

### Case 58: IT-074 — `WRONG_INTENT`
- **Question:** *"Received an SMS message claiming my bank account is frozen with a shortlink."*
- **Diagnosis:** Intent mismatch. Expected 'PHISHING_REPORT' but classified as 'GENERAL_IT_QUESTION'.
- **Expected Outcome:** *"escalated"*
- **Actual Outcome:** *"answered"*

<details><summary>Retrieved Context Snippet</summary>

```text
Offline grounded content snippet for 4 - IT Security.txt
```
</details>

### Case 59: IT-075 — `WRONG_TOOL`
- **Question:** *"Ransomware note appeared on local shared drive folder saying files are encrypted."*
- **Diagnosis:** Expected tools ['create_ticket'] were not invoked. Actual tools: ['search_policy_documents', 'execute_runbook_step'].
- **Expected Outcome:** *"escalated"*
- **Actual Outcome:** *"answered"*

<details><summary>Retrieved Context Snippet</summary>

```text
Offline grounded content snippet for 4 - IT Security.txt
```
</details>

### Case 60: IT-076 — `WRONG_TOOL`
- **Question:** *"Check if Jira service is experiencing degraded performance globally."*
- **Diagnosis:** Expected tools ['check_service_status'] were not invoked. Actual tools: [].
- **Expected Outcome:** *"answered"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 61: IT-077 — `WRONG_TOOL`
- **Question:** *"Check if Outlook Exchange mail servers are currently operational."*
- **Diagnosis:** Expected tools ['check_service_status'] were not invoked. Actual tools: [].
- **Expected Outcome:** *"answered"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 62: IT-085 — `WRONG_INTENT`
- **Question:** *"What is the policy on printing personal documents in the office?"*
- **Diagnosis:** Intent mismatch. Expected 'PRINTER_ISSUE' but classified as 'GENERAL_IT_QUESTION'.
- **Expected Outcome:** *"answered"*
- **Actual Outcome:** *"answered"*

<details><summary>Retrieved Context Snippet</summary>

```text
Offline grounded content snippet for 5 - Sustainability.txt
```
</details>

### Case 63: IT-086 — `WRONG_TOOL`
- **Question:** *"VPN tunnel connects but internal DNS names fail to resolve."*
- **Diagnosis:** Expected tools ['get_device_info'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 64: IT-087 — `WRONG_TOOL`
- **Question:** *"VPN software won't open on Windows 11 after reboot."*
- **Diagnosis:** Expected tools ['get_device_info'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 65: IT-088 — `WRONG_TOOL`
- **Question:** *"Wi-Fi adapter is completely missing from device manager on Dell Latitude."*
- **Diagnosis:** Expected tools ['get_device_info', 'create_ticket'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"escalated"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 66: IT-089 — `WRONG_TOOL`
- **Question:** *"Wi-Fi speeds are under 1 Mbps only in Conference Room B."*
- **Diagnosis:** Expected tools ['create_ticket'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"escalated"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 67: IT-090 — `WRONG_TOOL`
- **Question:** *"MFA prompt loop: every login requires 5 consecutive push approvals."*
- **Diagnosis:** Expected tools ['get_user_context'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 68: IT-091 — `WRONG_INTENT`
- **Question:** *"Account locked due to sync error on mobile email client."*
- **Diagnosis:** Intent mismatch. Expected 'PASSWORD_RESET' but classified as 'OUTLOOK_ISSUE'.
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 69: IT-092 — `WRONG_TOOL`
- **Question:** *"GitHub pull request merge blocked due to required branch protection rule."*
- **Diagnosis:** Expected tools ['get_user_context'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 70: IT-093 — `WRONG_TOOL`
- **Question:** *"Cannot access Jira Service Management queue for Tier 1 support team."*
- **Diagnosis:** Expected tools ['get_user_context', 'create_ticket'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 71: IT-094 — `WRONG_TOOL`
- **Question:** *"Outlook rules stopped working automatically and incoming emails go to wrong folders."*
- **Diagnosis:** Expected tools ['get_device_info'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 72: IT-095 — `WRONG_TOOL`
- **Question:** *"Office printer is displaying error 'Load Paper in Tray 2'."*
- **Diagnosis:** Expected tools ['get_device_info'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 73: IT-096 — `WRONG_TOOL`
- **Question:** *"DisplayPort monitor goes to sleep immediately after waking laptop from sleep."*
- **Diagnosis:** Expected tools ['get_device_info'] were not invoked. Actual tools: ['execute_runbook_step'].
- **Expected Outcome:** *"resolved"*
- **Actual Outcome:** *"refusal"*

<details><summary>Retrieved Context Snippet</summary>

```text
[NO RETRIEVED CONTEXT]
```
</details>

### Case 74: IT-097 — `WRONG_INTENT`
- **Question:** *"Received an unexpected password reset email from Microsoft 365."*
- **Diagnosis:** Intent mismatch. Expected 'PHISHING_REPORT' but classified as 'PASSWORD_RESET'.
- **Expected Outcome:** *"escalated"*
- **Actual Outcome:** *"answered"*

<details><summary>Retrieved Context Snippet</summary>

```text
Offline grounded content snippet for 4 - IT Security.txt
```
</details>

### Case 75: IT-102 — `WRONG_INTENT`
- **Question:** *"Can I install personal software like Spotify on my work laptop?"*
- **Diagnosis:** Intent mismatch. Expected 'GENERAL_IT_QUESTION' but classified as 'HARDWARE_ISSUE'.
- **Expected Outcome:** *"answered"*
- **Actual Outcome:** *"answered"*

<details><summary>Retrieved Context Snippet</summary>

```text
Offline grounded content snippet for 4 - IT Security.txt
```
</details>

---

## 3. SLA & Quality Thresholds
- **Recall Threshold:** $\ge 0.50$
- **Faithfulness Threshold:** $\ge 0.70$
- **Correctness Threshold:** $\ge 0.60$
- **Latency SLA:** $\le 5000$ ms
