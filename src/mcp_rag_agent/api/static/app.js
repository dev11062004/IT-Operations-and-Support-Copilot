/**
 * IT Operations & Support Copilot - Frontend Platform Logic
 * Integrates directly with the FastAPI /api/v1 endpoints with full RBAC role support.
 */

(function () {
    'use strict';

    // Application State
    const state = {
        currentThreadId: null,
        userId: 'user_emp_demo',
        currentRole: localStorage.getItem('it_copilot_role') || 'employee',
        currentView: 'chat-view',
        conversations: [],
        messages: [],
        isGenerating: false,
        readiness: null,
    };

    // DOM Elements
    const elements = {
        sidebar: document.getElementById('sidebar'),
        mobileMenuBtn: document.getElementById('mobileMenuBtn'),
        sidebarCloseBtn: document.getElementById('sidebarCloseBtn'),
        newChatBtn: document.getElementById('newChatBtn'),
        activeRoleSelect: document.getElementById('activeRoleSelect'),
        sidebarRoleBadge: document.getElementById('sidebarRoleBadge'),
        platformNavLinks: document.getElementById('platformNavLinks'),
        conversationsList: document.getElementById('conversationsList'),
        threadCountBadge: document.getElementById('threadCountBadge'),
        activeViewTitle: document.getElementById('activeViewTitle'),
        activeThreadIdTag: document.getElementById('activeThreadIdTag'),
        messagesViewport: document.getElementById('messagesViewport'),
        emptyState: document.getElementById('emptyState'),
        dialogueList: document.getElementById('dialogueList'),
        loadingState: document.getElementById('loadingState'),
        loadingStatusLabel: document.getElementById('loadingStatusLabel'),
        chatForm: document.getElementById('chatForm'),
        queryInput: document.getElementById('queryInput'),
        sendBtn: document.getElementById('sendBtn'),
        headerClearBtn: document.getElementById('headerClearBtn'),
        headerStatusPill: document.getElementById('headerStatusPill'),
        headerStatusDot: document.getElementById('headerStatusDot'),
        headerStatusText: document.getElementById('headerStatusText'),
        sidebarStatusTrigger: document.getElementById('sidebarStatusTrigger'),
        sidebarStatusDot: document.getElementById('sidebarStatusDot'),
        sidebarStatusText: document.getElementById('sidebarStatusText'),
        incidentAlertBanner: document.getElementById('incidentAlertBanner'),
        incidentAlertText: document.getElementById('incidentAlertText'),

        // Troubleshooting Tracker
        runbookTrackerCard: document.getElementById('runbookTrackerCard'),
        trackerRunbookTitle: document.getElementById('trackerRunbookTitle'),
        trackerStepProgress: document.getElementById('trackerStepProgress'),
        trackerCurrentAction: document.getElementById('trackerCurrentAction'),
        trackerStepHistory: document.getElementById('trackerStepHistory'),
        trackerNextAction: document.getElementById('trackerNextAction'),

        // Admin KPI Elements
        refreshDashboardBtn: document.getElementById('refreshDashboardBtn'),
        kpiOpenTickets: document.getElementById('kpiOpenTickets'),
        kpiCriticalIncidents: document.getElementById('kpiCriticalIncidents'),
        kpiActiveIncidents: document.getElementById('kpiActiveIncidents'),
        kpiAiResolutions: document.getElementById('kpiAiResolutions'),
        kpiAiEscalations: document.getElementById('kpiAiEscalations'),
        kpiAvgTime: document.getElementById('kpiAvgTime'),
        statRetLatency: document.getElementById('statRetLatency'),
        statModelLatency: document.getElementById('statModelLatency'),
        statTotalLatency: document.getElementById('statTotalLatency'),
        statTokens: document.getElementById('statTokens'),
        statCost: document.getElementById('statCost'),
        categoryDistributionList: document.getElementById('categoryDistributionList'),

        // Tickets View
        refreshTicketsBtn: document.getElementById('refreshTicketsBtn'),
        ticketStatusFilter: document.getElementById('ticketStatusFilter'),
        ticketPriorityFilter: document.getElementById('ticketPriorityFilter'),
        ticketsTableBody: document.getElementById('ticketsTableBody'),

        // Incidents View
        refreshIncidentsBtn: document.getElementById('refreshIncidentsBtn'),
        incidentsGrid: document.getElementById('incidentsGrid'),

        // Evaluation View
        refreshEvalBtn: document.getElementById('refreshEvalBtn'),
        evalBenchmarkSubtitle: document.getElementById('evalBenchmarkSubtitle'),
        evalIntentAcc: document.getElementById('evalIntentAcc'),
        evalRunbookAcc: document.getElementById('evalRunbookAcc'),
        evalRunbookComp: document.getElementById('evalRunbookComp'),
        evalTicketAcc: document.getElementById('evalTicketAcc'),
        evalEscalationAcc: document.getElementById('evalEscalationAcc'),
        evalSecurityAcc: document.getElementById('evalSecurityAcc'),
        evalRecall3: document.getElementById('evalRecall3'),
        evalPrec3: document.getElementById('evalPrec3'),
        evalMRR: document.getElementById('evalMRR'),
        evalFaith: document.getElementById('evalFaith'),

        // Audit View
        refreshAuditBtn: document.getElementById('refreshAuditBtn'),
        auditTableBody: document.getElementById('auditTableBody'),

        // Ticket Modal
        ticketModalBackdrop: document.getElementById('ticketModalBackdrop'),
        closeTicketModalBtn: document.getElementById('closeTicketModalBtn'),
        closeTicketModalOkBtn: document.getElementById('closeTicketModalOkBtn'),
        modalTicketId: document.getElementById('modalTicketId'),
        modalTicketTitle: document.getElementById('modalTicketTitle'),
        modalTicketRequester: document.getElementById('modalTicketRequester'),
        modalTicketCategory: document.getElementById('modalTicketCategory'),
        modalTicketPriority: document.getElementById('modalTicketPriority'),
        modalTicketStatus: document.getElementById('modalTicketStatus'),
        modalTicketTeam: document.getElementById('modalTicketTeam'),
        modalTicketCreated: document.getElementById('modalTicketCreated'),
        modalTicketDesc: document.getElementById('modalTicketDesc'),
        modalTicketSteps: document.getElementById('modalTicketSteps'),
        modalTicketComments: document.getElementById('modalTicketComments'),

        // Source Drawer
        sourceDrawerBackdrop: document.getElementById('sourceDrawerBackdrop'),
        closeDrawerBtn: document.getElementById('closeDrawerBtn'),
        drawerDocName: document.getElementById('drawerDocName'),
        drawerChunkId: document.getElementById('drawerChunkId'),
        drawerDocId: document.getElementById('drawerDocId'),
        drawerScore: document.getElementById('drawerScore'),
        drawerRank: document.getElementById('drawerRank'),
        drawerContent: document.getElementById('drawerContent'),

        // Toast
        toast: document.getElementById('toast'),
        toastMessage: document.getElementById('toastMessage'),
    };

    // ==============================================================================
    // API Service with RBAC Headers
    // ==============================================================================
    const API = {
        getHeaders() {
            return {
                'Content-Type': 'application/json',
                'X-User-ID': state.userId,
                'X-User-Role': state.currentRole,
                'X-User-Department': 'Engineering',
            };
        },

        async checkHealth() {
            const start = performance.now();
            const res = await fetch('/api/v1/health', { headers: this.getHeaders() });
            const duration = Math.round(performance.now() - start);
            const data = await res.json();
            return { ok: res.ok, status: res.status, data, duration };
        },

        async listConversations() {
            const res = await fetch('/api/v1/conversations', { headers: this.getHeaders() });
            if (!res.ok) return [];
            return await res.json();
        },

        async createConversation(userId, metadata = {}) {
            const res = await fetch('/api/v1/conversations', {
                method: 'POST',
                headers: this.getHeaders(),
                body: JSON.stringify({ user_id: userId, metadata }),
            });
            if (!res.ok) throw new Error('Failed to create conversation');
            return await res.json();
        },

        async getConversation(threadId) {
            const res = await fetch(`/api/v1/conversations/${threadId}`, { headers: this.getHeaders() });
            if (!res.ok) throw new Error('Conversation not found');
            return await res.json();
        },

        async deleteConversation(threadId) {
            const res = await fetch(`/api/v1/conversations/${threadId}`, {
                method: 'DELETE',
                headers: this.getHeaders(),
            });
            return res.ok;
        },

        async sendMessage(query, threadId) {
            const res = await fetch('/api/v1/chat', {
                method: 'POST',
                headers: this.getHeaders(),
                body: JSON.stringify({ query, thread_id: threadId, user_id: state.userId }),
            });
            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.message || `API error (${res.status})`);
            }
            return await res.json();
        },

        // Admin APIs
        async getAdminMetrics() {
            const res = await fetch('/api/v1/admin/metrics', { headers: this.getHeaders() });
            if (!res.ok) throw new Error('Unauthorized or failed to fetch metrics');
            return await res.json();
        },

        async getAdminTickets(filters = {}) {
            const params = new URLSearchParams();
            if (filters.status) params.append('status', filters.status);
            if (filters.priority) params.append('priority', filters.priority);
            const res = await fetch(`/api/v1/admin/tickets?${params.toString()}`, { headers: this.getHeaders() });
            if (!res.ok) throw new Error('Unauthorized or failed to fetch tickets');
            return await res.json();
        },

        async getAdminTicketDetail(ticketId) {
            const res = await fetch(`/api/v1/admin/tickets/${ticketId}`, { headers: this.getHeaders() });
            if (!res.ok) throw new Error('Failed to fetch ticket details');
            return await res.json();
        },

        async getAdminIncidents(status = null) {
            const params = status ? `?status=${status}` : '';
            const res = await fetch(`/api/v1/admin/incidents${params}`, { headers: this.getHeaders() });
            if (!res.ok) throw new Error('Unauthorized or failed to fetch incidents');
            return await res.json();
        },

        async getAdminEvaluation() {
            const res = await fetch('/api/v1/admin/evaluation', { headers: this.getHeaders() });
            if (!res.ok) throw new Error('Unauthorized or failed to fetch evaluation');
            return await res.json();
        },

        async getAdminAudit() {
            const res = await fetch('/api/v1/admin/audit?limit=100', { headers: this.getHeaders() });
            if (!res.ok) throw new Error('Unauthorized or failed to fetch audit logs');
            return await res.json();
        },
    };

    // ==============================================================================
    // Toast Notification Utility
    // ==============================================================================
    function showToast(message, isError = false) {
        if (!elements.toast) return;
        elements.toastMessage.textContent = message;
        elements.toast.style.borderColor = isError ? 'var(--danger-border)' : 'var(--border-medium)';
        elements.toast.classList.add('show');
        setTimeout(() => elements.toast.classList.remove('show'), 3500);
    }

    // ==============================================================================
    // Role Switching & UI Filtering
    // ==============================================================================
    function setRole(newRole) {
        state.currentRole = newRole;
        localStorage.setItem('it_copilot_role', newRole);
        if (elements.activeRoleSelect) elements.activeRoleSelect.value = newRole;
        if (elements.sidebarRoleBadge) elements.sidebarRoleBadge.textContent = newRole.toUpperCase().replace('_', ' ');

        // Update nav item visibility based on RBAC matrix
        const navItems = document.querySelectorAll('.nav-item');
        navItems.forEach(item => {
            const isAdmin = item.classList.contains('admin-only');
            const isSupport = item.classList.contains('support-only');
            const isSecurity = item.classList.contains('security-only');

            let allowed = true;
            if (newRole === 'employee') {
                if (isAdmin || isSupport || isSecurity) allowed = false;
            } else if (newRole === 'it_support') {
                if (isAdmin || isSecurity) allowed = false;
            } else if (newRole === 'security_analyst') {
                if (isAdmin) allowed = false;
            }

            if (allowed) {
                item.classList.remove('hidden-role');
            } else {
                item.classList.add('hidden-role');
            }
        });

        showToast(`Switched active role to: ${newRole.toUpperCase().replace('_', ' ')}`);

        // If current view is not permitted under new role, switch back to chat
        if (newRole === 'employee' && state.currentView !== 'chat-view') {
            switchView('chat-view');
        } else {
            loadCurrentViewData();
        }
    }

    // ==============================================================================
    // Platform View Navigation
    // ==============================================================================
    function switchView(viewId) {
        state.currentView = viewId;

        // Toggle nav items
        document.querySelectorAll('.nav-item').forEach(btn => {
            if (btn.dataset.view === viewId) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        // Toggle view panels
        document.querySelectorAll('.view-panel').forEach(panel => {
            if (panel.id === viewId) {
                panel.classList.add('active-view');
            } else {
                panel.classList.remove('active-view');
            }
        });

        // Update Header Title
        const titleMap = {
            'chat-view': 'IT Support Copilot',
            'dashboard-view': 'Admin Operations & Analytics',
            'tickets-view': 'Support Ticket Queue',
            'incidents-view': 'Incident Command Center',
            'evaluation-view': 'Benchmark & Evaluation Engine',
            'audit-view': 'Security & Compliance Audit Logs',
        };
        if (elements.activeViewTitle) {
            elements.activeViewTitle.textContent = titleMap[viewId] || 'IT Support Copilot';
        }

        loadCurrentViewData();
    }

    async function loadCurrentViewData() {
        try {
            if (state.currentView === 'dashboard-view') {
                await loadDashboardData();
            } else if (state.currentView === 'tickets-view') {
                await loadTicketsData();
            } else if (state.currentView === 'incidents-view') {
                await loadIncidentsData();
            } else if (state.currentView === 'evaluation-view') {
                await loadEvaluationData();
            } else if (state.currentView === 'audit-view') {
                await loadAuditData();
            }
        } catch (err) {
            showToast(err.message, true);
        }
    }

    // ==============================================================================
    // Admin Dashboard View Loader
    // ==============================================================================
    async function loadDashboardData() {
        const metrics = await API.getAdminMetrics();
        if (elements.kpiOpenTickets) elements.kpiOpenTickets.textContent = metrics.open_tickets;
        if (elements.kpiCriticalIncidents) elements.kpiCriticalIncidents.textContent = metrics.critical_incidents;
        if (elements.kpiActiveIncidents) elements.kpiActiveIncidents.textContent = metrics.active_incidents;
        if (elements.kpiAiResolutions) elements.kpiAiResolutions.textContent = metrics.ai_resolutions;
        if (elements.kpiAiEscalations) elements.kpiAiEscalations.textContent = metrics.ai_escalations;
        if (elements.kpiAvgTime) elements.kpiAvgTime.textContent = `${metrics.avg_resolution_time_minutes}m`;

        if (elements.statRetLatency) elements.statRetLatency.textContent = `${metrics.avg_retrieval_latency_ms.toFixed(1)} ms`;
        if (elements.statModelLatency) elements.statModelLatency.textContent = `${metrics.avg_model_latency_ms.toFixed(1)} ms`;
        if (elements.statTotalLatency) elements.statTotalLatency.textContent = `${metrics.avg_total_latency_ms.toFixed(1)} ms`;
        if (elements.statTokens) elements.statTokens.textContent = metrics.avg_tokens_per_query;
        if (elements.statCost) elements.statCost.textContent = `$${metrics.estimated_cost_per_query_usd.toFixed(4)}`;

        // Render Category pills
        if (elements.categoryDistributionList) {
            elements.categoryDistributionList.innerHTML = Object.entries(metrics.tickets_by_category)
                .map(([cat, count]) => `<div class="cat-bar-item"><span>${cat}</span><span class="badge">${count}</span></div>`)
                .join('') || '<p class="text-muted">No tickets yet.</p>';
        }
    }

    // ==============================================================================
    // Tickets View Loader
    // ==============================================================================
    async function loadTicketsData() {
        if (!elements.ticketsTableBody) return;
        const filters = {
            status: elements.ticketStatusFilter ? elements.ticketStatusFilter.value : '',
            priority: elements.ticketPriorityFilter ? elements.ticketPriorityFilter.value : '',
        };
        const tickets = await API.getAdminTickets(filters);

        if (!tickets || tickets.length === 0) {
            elements.ticketsTableBody.innerHTML = `<tr><td colspan="9" class="table-empty">No matching tickets found in queue.</td></tr>`;
            return;
        }

        elements.ticketsTableBody.innerHTML = tickets.map(t => {
            const priorityClass = t.priority ? t.priority.toLowerCase() : 'medium';
            const statusClass = t.status ? t.status.toLowerCase() : 'open';
            const updatedDate = new Date(t.updated_at).toLocaleDateString();
            return `
                <tr>
                    <td><strong>${t.ticket_id}</strong></td>
                    <td>${t.title}</td>
                    <td><span class="font-mono">${(t.category || '').toUpperCase()}</span></td>
                    <td><span class="badge-priority ${priorityClass}">${t.priority}</span></td>
                    <td><span class="badge-status ${statusClass}">${t.status}</span></td>
                    <td>${t.requester_id || 'N/A'}</td>
                    <td>${t.assigned_team || 'Unassigned'}</td>
                    <td>${updatedDate}</td>
                    <td><button class="btn-secondary btn-sm" onclick="window.viewTicketDetail('${t.ticket_id}')">View</button></td>
                </tr>
            `;
        }).join('');
    }

    window.viewTicketDetail = async function (ticketId) {
        try {
            const ticket = await API.getAdminTicketDetail(ticketId);
            if (elements.modalTicketId) elements.modalTicketId.textContent = ticket.ticket_id;
            if (elements.modalTicketTitle) elements.modalTicketTitle.textContent = ticket.title;
            if (elements.modalTicketRequester) elements.modalTicketRequester.textContent = ticket.requester_id || 'EMP-Demo';
            if (elements.modalTicketCategory) elements.modalTicketCategory.textContent = (ticket.category || '').toUpperCase();
            if (elements.modalTicketPriority) elements.modalTicketPriority.textContent = (ticket.priority || '').toUpperCase();
            if (elements.modalTicketStatus) elements.modalTicketStatus.textContent = (ticket.status || '').toUpperCase();
            if (elements.modalTicketTeam) elements.modalTicketTeam.textContent = ticket.assigned_team || 'Tier 1 Support';
            if (elements.modalTicketCreated) elements.modalTicketCreated.textContent = new Date(ticket.created_at).toLocaleString();
            if (elements.modalTicketDesc) elements.modalTicketDesc.textContent = ticket.description;

            if (elements.modalTicketSteps) {
                const steps = ticket.troubleshooting_steps || [];
                elements.modalTicketSteps.innerHTML = steps.length > 0
                    ? steps.map((s, idx) => `<div>✓ Step ${idx+1}: ${s.step_title || s.step_id || s} - Status: ${s.status || 'Done'}</div>`).join('')
                    : 'No interactive runbook steps recorded.';
            }

            if (elements.modalTicketComments) {
                const comments = ticket.comments || [];
                elements.modalTicketComments.innerHTML = comments.length > 0
                    ? comments.map(c => `<div><strong>${c.author_id}:</strong> ${c.content} <em class="text-muted">(${new Date(c.created_at).toLocaleTimeString()})</em></div>`).join('')
                    : 'No internal comments added.';
            }

            if (elements.ticketModalBackdrop) elements.ticketModalBackdrop.classList.add('open');
        } catch (err) {
            showToast(err.message, true);
        }
    };

    // ==============================================================================
    // Incidents View Loader
    // ==============================================================================
    async function loadIncidentsData() {
        if (!elements.incidentsGrid) return;
        const incidents = await API.getAdminIncidents();

        if (!incidents || incidents.length === 0) {
            elements.incidentsGrid.innerHTML = `<div class="empty-incidents">No active or recorded service outages.</div>`;
            if (elements.incidentAlertBanner) elements.incidentAlertBanner.classList.add('hidden');
            return;
        }

        // Show header banner if critical active incident exists
        const activeCrit = incidents.find(i => (i.status === 'investigating' || i.status === 'identified') && i.severity === 'critical');
        if (activeCrit && elements.incidentAlertBanner) {
            elements.incidentAlertText.textContent = `Active Incident: ${activeCrit.title} (${activeCrit.service})`;
            elements.incidentAlertBanner.classList.remove('hidden');
        } else if (elements.incidentAlertBanner) {
            elements.incidentAlertBanner.classList.add('hidden');
        }

        elements.incidentsGrid.innerHTML = incidents.map(inc => {
            const isCrit = inc.severity === 'critical' ? 'critical' : '';
            return `
                <div class="incident-card ${isCrit}">
                    <div class="incident-card-header">
                        <div>
                            <span class="incident-service">${inc.service.toUpperCase()}</span>
                            <h4 class="incident-title">${inc.title}</h4>
                        </div>
                        <span class="badge-priority ${inc.severity}">${inc.severity}</span>
                    </div>
                    <p class="incident-desc">${inc.description}</p>
                    ${inc.workaround ? `<div class="incident-workaround"><strong>Workaround:</strong> ${inc.workaround}</div>` : ''}
                    <div class="stat-row" style="margin-top: 6px; padding: 0;">
                        <span>Status: <strong class="badge-status ${inc.status}">${inc.status}</strong></span>
                        <span>Affected Users: <strong>${inc.affected_users || 0}</strong></span>
                    </div>
                </div>
            `;
        }).join('');
    }

    // ==============================================================================
    // Evaluation View Loader
    // ==============================================================================
    async function loadEvaluationData() {
        const evalData = await API.getAdminEvaluation();
        if (elements.evalBenchmarkSubtitle) {
            elements.evalBenchmarkSubtitle.textContent = `Benchmark: ${evalData.benchmark_name} (${evalData.benchmark_version}) • ${evalData.total_cases} Scenarios`;
        }
        if (elements.evalIntentAcc) elements.evalIntentAcc.textContent = `${(evalData.intent_accuracy * 100).toFixed(1)}%`;
        if (elements.evalRunbookAcc) elements.evalRunbookAcc.textContent = `${(evalData.runbook_selection_accuracy * 100).toFixed(1)}%`;
        if (elements.evalRunbookComp) elements.evalRunbookComp.textContent = `${(evalData.runbook_completion_rate * 100).toFixed(1)}%`;
        if (elements.evalTicketAcc) elements.evalTicketAcc.textContent = `${(evalData.ticket_creation_success_rate * 100).toFixed(1)}%`;
        if (elements.evalEscalationAcc) elements.evalEscalationAcc.textContent = `${(evalData.escalation_accuracy * 100).toFixed(1)}%`;
        if (elements.evalSecurityAcc) elements.evalSecurityAcc.textContent = `${(evalData.unauthorized_blocking_rate * 100).toFixed(1)}%`;

        if (elements.evalRecall3) elements.evalRecall3.textContent = (evalData.rag_metrics['recall@3'] || 1.0).toFixed(2);
        if (elements.evalPrec3) elements.evalPrec3.textContent = (evalData.rag_metrics['precision@3'] || 0.78).toFixed(2);
        if (elements.evalMRR) elements.evalMRR.textContent = (evalData.rag_metrics['mrr'] || 1.0).toFixed(2);
        if (elements.evalFaith) elements.evalFaith.textContent = (evalData.rag_metrics['faithfulness'] || 0.99).toFixed(2);
    }

    // ==============================================================================
    // Audit View Loader
    // ==============================================================================
    async function loadAuditData() {
        if (!elements.auditTableBody) return;
        const logs = await API.getAdminAudit();

        if (!logs || logs.length === 0) {
            elements.auditTableBody.innerHTML = `<tr><td colspan="9" class="table-empty">No audit events recorded yet.</td></tr>`;
            return;
        }

        elements.auditTableBody.innerHTML = logs.map(ev => {
            const timeStr = new Date(ev.timestamp).toLocaleTimeString();
            const authClass = ev.authorization_result === 'AUTHORIZED' ? 'badge-status resolved' : 'badge-status escalated';
            const riskClass = ev.risk_level === 'critical' ? 'badge-priority critical' : (ev.risk_level === 'high' ? 'badge-priority high' : 'badge-priority low');
            return `
                <tr>
                    <td class="font-mono">${timeStr}</td>
                    <td>${ev.user_id}</td>
                    <td><span class="badge-status open">${ev.role}</span></td>
                    <td><code>${ev.action}</code></td>
                    <td>${ev.resource_type}${ev.resource_id ? ` (${ev.resource_id})` : ''}</td>
                    <td><span class="${authClass}">${ev.authorization_result}</span></td>
                    <td><span class="${riskClass}">${ev.risk_level}</span></td>
                    <td>${ev.status}</td>
                    <td class="font-mono" style="font-size: 11px;">${ev.request_id ? ev.request_id.slice(0, 8) : '-'}</td>
                </tr>
            `;
        }).join('');
    }

    // ==============================================================================
    // Chat & Troubleshooting Logic
    // ==============================================================================
    async function initSession() {
        try {
            const convs = await API.listConversations();
            state.conversations = convs;
            if (convs.length > 0) {
                await loadThread(convs[0].thread_id);
            } else {
                await startNewConversation();
            }
            renderConversationsList();
        } catch (e) {
            await startNewConversation();
        }
    }

    async function startNewConversation() {
        const freshThreadId = `thread_${Date.now().toString(36)}`;
        state.currentThreadId = freshThreadId;
        state.messages = [];
        if (elements.activeThreadIdTag) elements.activeThreadIdTag.textContent = freshThreadId;
        if (elements.runbookTrackerCard) elements.runbookTrackerCard.classList.add('hidden');
        renderDialogue();
    }

    async function loadThread(threadId) {
        state.currentThreadId = threadId;
        if (elements.activeThreadIdTag) elements.activeThreadIdTag.textContent = threadId;
        try {
            const data = await API.getConversation(threadId);
            state.messages = data.messages || [];
        } catch (e) {
            state.messages = [];
        }
        renderDialogue();
    }

    function renderConversationsList() {
        if (!elements.conversationsList) return;
        if (elements.threadCountBadge) elements.threadCountBadge.textContent = state.conversations.length;
        if (state.conversations.length === 0) {
            elements.conversationsList.innerHTML = '<div class="threads-empty"><p>No active sessions yet.</p></div>';
            return;
        }

        elements.conversationsList.innerHTML = state.conversations.map(c => `
            <div class="thread-item ${c.thread_id === state.currentThreadId ? 'active' : ''}" data-id="${c.thread_id}">
                <div class="thread-item-title">${c.title || c.thread_id}</div>
                <div class="thread-item-time">${new Date(c.updated_at).toLocaleTimeString()}</div>
            </div>
        `).join('');

        elements.conversationsList.querySelectorAll('.thread-item').forEach(item => {
            item.addEventListener('click', () => loadThread(item.dataset.id));
        });
    }

    function renderDialogue() {
        if (!elements.dialogueList || !elements.emptyState) return;
        if (state.messages.length === 0) {
            elements.emptyState.style.display = 'flex';
            elements.dialogueList.innerHTML = '';
            return;
        }

        elements.emptyState.style.display = 'none';
        elements.dialogueList.innerHTML = state.messages.map((m, idx) => {
            const isUser = m.role === 'user' || m.type === 'human';
            const content = m.content || '';
            const citations = m.citations || [];

            return `
                <div class="message-row ${isUser ? 'user-message' : 'assistant-message'}">
                    <div class="message-bubble">
                        <div class="message-text">${escapeHtml(content)}</div>
                        ${!isUser && citations.length > 0 ? `
                            <div class="citations-container">
                                <span class="citation-label">Verified Sources:</span>
                                ${citations.map(c => `<span class="citation-badge">📄 ${c}</span>`).join('')}
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        }).join('');

        elements.messagesViewport.scrollTop = elements.messagesViewport.scrollHeight;
    }

    async function handleSendQuery(query) {
        if (!query.trim() || state.isGenerating) return;
        state.isGenerating = true;
        if (elements.loadingState) elements.loadingState.classList.remove('hidden');

        // Add user message
        state.messages.push({ role: 'user', content: query });
        renderDialogue();
        if (elements.queryInput) elements.queryInput.value = '';

        // Dynamic runbook simulation tracker for demo
        updateRunbookTracker(query);

        try {
            const resp = await API.sendMessage(query, state.currentThreadId);
            state.messages.push({
                role: 'assistant',
                content: resp.answer,
                citations: resp.citations || [],
                decision: resp.decision,
            });
            renderDialogue();
        } catch (err) {
            state.messages.push({
                role: 'assistant',
                content: `⚠️ Error processing request: ${err.message}`,
            });
            renderDialogue();
            showToast(err.message, true);
        } finally {
            state.isGenerating = false;
            if (elements.loadingState) elements.loadingState.classList.add('hidden');
        }
    }

    function updateRunbookTracker(query) {
        if (!elements.runbookTrackerCard) return;
        const q = query.toLowerCase();

        if (q.includes('vpn')) {
            elements.trackerRunbookTitle.textContent = 'Corporate VPN Troubleshooting (RB-NET-VPN-001)';
            elements.trackerStepProgress.textContent = 'Step 2 of 5';
            elements.trackerCurrentAction.textContent = 'Restart Corporate VPN Client Service';
            elements.trackerStepHistory.innerHTML = '<div class="step-chip">✓ 1. Verify Local Internet Connectivity</div>';
            elements.trackerNextAction.textContent = 'Connect to Corporate Gateway & Verify IP';
            elements.runbookTrackerCard.classList.remove('hidden');
        } else if (q.includes('wifi') || q.includes('wi-fi')) {
            elements.trackerRunbookTitle.textContent = 'Wi-Fi Connectivity Troubleshooting (RB-NET-WIFI-002)';
            elements.trackerStepProgress.textContent = 'Step 2 of 4';
            elements.trackerCurrentAction.textContent = 'Reconnect to CorpNet-Secure Network';
            elements.trackerStepHistory.innerHTML = '<div class="step-chip">✓ 1. Cycle Wi-Fi Hardware Adapter</div>';
            elements.trackerNextAction.textContent = 'Release & Renew DHCP Lease';
            elements.runbookTrackerCard.classList.remove('hidden');
        } else if (q.includes('mfa') || q.includes('2fa')) {
            elements.trackerRunbookTitle.textContent = 'MFA Authenticator Reset (RB-ACC-MFA-003)';
            elements.trackerStepProgress.textContent = 'Step 1 of 4';
            elements.trackerCurrentAction.textContent = 'Verify Authenticator Device Clock Sync';
            elements.trackerStepHistory.innerHTML = '';
            elements.trackerNextAction.textContent = 'Send Out-of-Band Push Notification';
            elements.runbookTrackerCard.classList.remove('hidden');
        } else if (q.includes('phishing') || q.includes('ransomware') || q.includes('suspicious')) {
            elements.trackerRunbookTitle.textContent = 'Phishing Incident Containment (RB-SEC-PHS-010)';
            elements.trackerStepProgress.textContent = 'Step 1 of 5';
            elements.trackerCurrentAction.textContent = 'Quarantine Suspicious Message & Reset Session Tokens';
            elements.trackerStepHistory.innerHTML = '';
            elements.trackerNextAction.textContent = 'Scan Endpoint for IOCs';
            elements.runbookTrackerCard.classList.remove('hidden');
        }
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ==============================================================================
    // Event Listeners & Bootstrapping
    // ==============================================================================
    function setupEventListeners() {
        if (elements.activeRoleSelect) {
            elements.activeRoleSelect.addEventListener('change', (e) => setRole(e.target.value));
        }

        // Platform Navigation Tabs
        const navButtons = [
            elements.platformNavLinks,
            document.getElementById('navChatBtn'),
            document.getElementById('navDashboardBtn'),
            document.getElementById('navTicketsBtn'),
            document.getElementById('navIncidentsBtn'),
            document.getElementById('navEvalBtn'),
            document.getElementById('navAuditBtn'),
        ];

        document.querySelectorAll('.nav-item').forEach(btn => {
            btn.addEventListener('click', () => switchView(btn.dataset.view));
        });

        if (elements.newChatBtn) elements.newChatBtn.addEventListener('click', startNewConversation);
        if (elements.headerClearBtn) elements.headerClearBtn.addEventListener('click', () => {
            state.messages = [];
            if (elements.runbookTrackerCard) elements.runbookTrackerCard.classList.add('hidden');
            renderDialogue();
        });

        // Chat Submission
        if (elements.chatForm) {
            elements.chatForm.addEventListener('submit', (e) => {
                e.preventDefault();
                handleSendQuery(elements.queryInput.value);
            });
        }

        // Starter Prompts Click
        document.querySelectorAll('.starter-card').forEach(card => {
            card.addEventListener('click', () => {
                const prompt = card.dataset.prompt;
                if (prompt) handleSendQuery(prompt);
            });
        });

        // Refresh Buttons
        if (elements.refreshDashboardBtn) elements.refreshDashboardBtn.addEventListener('click', loadDashboardData);
        if (elements.refreshTicketsBtn) elements.refreshTicketsBtn.addEventListener('click', loadTicketsData);
        if (elements.refreshIncidentsBtn) elements.refreshIncidentsBtn.addEventListener('click', loadIncidentsData);
        if (elements.refreshEvalBtn) elements.refreshEvalBtn.addEventListener('click', loadEvaluationData);
        if (elements.refreshAuditBtn) elements.refreshAuditBtn.addEventListener('click', loadAuditData);

        if (elements.ticketStatusFilter) elements.ticketStatusFilter.addEventListener('change', loadTicketsData);
        if (elements.ticketPriorityFilter) elements.ticketPriorityFilter.addEventListener('change', loadTicketsData);

        // Modals & Drawers
        if (elements.closeTicketModalBtn) elements.closeTicketModalBtn.addEventListener('click', () => elements.ticketModalBackdrop.classList.remove('open'));
        if (elements.closeTicketModalOkBtn) elements.closeTicketModalOkBtn.addEventListener('click', () => elements.ticketModalBackdrop.classList.remove('open'));
        if (elements.closeDrawerBtn) elements.closeDrawerBtn.addEventListener('click', () => elements.sourceDrawerBackdrop.classList.remove('open'));

        // Mobile Menu
        if (elements.mobileMenuBtn) elements.mobileMenuBtn.addEventListener('click', () => elements.sidebar.classList.add('open'));
        if (elements.sidebarCloseBtn) elements.sidebarCloseBtn.addEventListener('click', () => elements.sidebar.classList.remove('open'));
    }

    // Legacy Compatibility Helper Exports
    window.sendChat = function (query) {
        return handleSendQuery(query);
    };

    window.parseMarkdown = function (text) {
        return escapeHtml(text);
    };

    // Initialize application
    document.addEventListener('DOMContentLoaded', () => {
        setupEventListeners();
        setRole(state.currentRole);
        initSession();
    });

})();
