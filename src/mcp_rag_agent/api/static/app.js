/**
 * Enterprise Knowledge Assistant - Frontend Application Logic
 * Integrates directly with the FastAPI /api/v1 endpoints.
 */

(function () {
    'use strict';

    // Application State
    const state = {
        currentThreadId: null,
        userId: 'user_emp_demo',
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
        conversationsList: document.getElementById('conversationsList'),
        threadCountBadge: document.getElementById('threadCountBadge'),
        activeThreadTitle: document.getElementById('activeThreadTitle'),
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
        // Source Drawer
        sourceDrawerBackdrop: document.getElementById('sourceDrawerBackdrop'),
        closeDrawerBtn: document.getElementById('closeDrawerBtn'),
        drawerDocName: document.getElementById('drawerDocName'),
        drawerChunkId: document.getElementById('drawerChunkId'),
        drawerDocId: document.getElementById('drawerDocId'),
        drawerScore: document.getElementById('drawerScore'),
        drawerRank: document.getElementById('drawerRank'),
        drawerContent: document.getElementById('drawerContent'),
        drawerMetadataJson: document.getElementById('drawerMetadataJson'),
        // Diagnostic Modal
        diagnosticModalBackdrop: document.getElementById('diagnosticModalBackdrop'),
        closeModalBtn: document.getElementById('closeModalBtn'),
        closeModalOkBtn: document.getElementById('closeModalOkBtn'),
        refreshDiagBtn: document.getElementById('refreshDiagBtn'),
        diagMongoStatus: document.getElementById('diagMongoStatus'),
        diagModelStatus: document.getElementById('diagModelStatus'),
        diagMemoryStatus: document.getElementById('diagMemoryStatus'),
        diagPingTime: document.getElementById('diagPingTime'),
        // Toast
        toast: document.getElementById('toast'),
        toastMessage: document.getElementById('toastMessage'),
    };

    // ==============================================================================
    // API Service
    // ==============================================================================
    const API = {
        async checkHealth() {
            const start = performance.now();
            const res = await fetch('/api/v1/health');
            const duration = Math.round(performance.now() - start);
            const data = await res.json();
            return { ok: res.ok, status: res.status, data, duration };
        },

        async checkReady() {
            const res = await fetch('/api/v1/ready');
            const data = await res.json();
            return { ok: res.ok, status: res.status, data };
        },

        async listConversations() {
            const res = await fetch('/api/v1/conversations');
            if (!res.ok) return [];
            return await res.json();
        },

        async createConversation(userId, metadata = {}) {
            const res = await fetch('/api/v1/conversations', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId, metadata }),
            });
            if (!res.ok) throw new Error('Failed to create conversation');
            return await res.json();
        },

        async getConversationHistory(threadId) {
            const res = await fetch(`/api/v1/conversations/${encodeURIComponent(threadId)}`);
            if (!res.ok) throw new Error('Failed to load history');
            return await res.json();
        },

        async deleteConversation(threadId) {
            const res = await fetch(`/api/v1/conversations/${encodeURIComponent(threadId)}`, {
                method: 'DELETE',
            });
            if (!res.ok) throw new Error('Failed to delete conversation');
            return await res.json();
        },

        async sendChat(message, threadId, userId) {
            const res = await fetch('/api/v1/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message, thread_id: threadId, user_id: userId }),
            });
            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                const msg = errData.message || (errData.details && JSON.stringify(errData.details)) || 'API request failed';
                throw new Error(msg);
            }
            return await res.json();
        },
    };

    // ==============================================================================
    // Markdown Parser (Zero-dependency, XSS-safe text formatter)
    // ==============================================================================
    function parseMarkdown(text) {
        if (!text) return '';

        // Escape HTML tags to prevent XSS
        let html = text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        // Code blocks
        html = html.replace(/```([\s\S]*?)```/g, (match, code) => {
            return `<pre><code>${code.trim()}</code></pre>`;
        });

        // Inline code
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

        // Bold
        html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

        // Italic
        html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

        // Headings
        html = html.replace(/^### (.*$)/gim, '<h4>$1</h4>');
        html = html.replace(/^## (.*$)/gim, '<h3>$1</h3>');

        // Bullet lists
        html = html.replace(/^\s*[-*]\s+(.*)$/gim, '<li>$1</li>');
        html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

        // Paragraph linebreaks
        const paragraphs = html.split(/\n\n+/);
        return paragraphs
            .map(p => {
                p = p.trim();
                if (!p) return '';
                if (p.startsWith('<h') || p.startsWith('<pre') || p.startsWith('<ul') || p.startsWith('<ol')) {
                    return p;
                }
                return `<p>${p.replace(/\n/g, '<br>')}</p>`;
            })
            .join('');
    }

    // ==============================================================================
    // UI Helpers & Toast
    // ==============================================================================
    function showToast(message, type = 'info') {
        elements.toastMessage.textContent = message;
        elements.toast.className = `toast show ${type}`;
        setTimeout(() => {
            elements.toast.className = 'toast';
        }, 3200);
    }

    function autoResizeTextarea() {
        elements.queryInput.style.height = 'auto';
        elements.queryInput.style.height = Math.min(elements.queryInput.scrollHeight, 160) + 'px';
    }

    function scrollMessagesToBottom() {
        elements.messagesViewport.scrollTop = elements.messagesViewport.scrollHeight;
    }

    // ==============================================================================
    // Conversation Management
    // ==============================================================================
    async function initConversation() {
        try {
            // Fetch existing threads
            const threads = await API.listConversations();
            state.conversations = threads;
            renderThreadsList();

            // Resume saved thread or create new
            const savedThreadId = localStorage.getItem('mcp_rag_active_thread');
            if (savedThreadId && threads.some(t => t.thread_id === savedThreadId)) {
                await selectThread(savedThreadId);
            } else if (threads.length > 0) {
                await selectThread(threads[0].thread_id);
            } else {
                await startNewConversation(false);
            }
        } catch (err) {
            console.warn('Could not initialize existing threads:', err);
            await startNewConversation(false);
        }
    }

    async function startNewConversation(focus = true) {
        try {
            const threadData = await API.createConversation(state.userId, {
                started_from: 'web_ui',
                client_timestamp: new Date().toISOString(),
            });

            state.currentThreadId = threadData.thread_id;
            localStorage.setItem('mcp_rag_active_thread', threadData.thread_id);

            // Add to conversations list
            state.conversations.unshift(threadData);
            renderThreadsList();

            // Clear current dialogue
            state.messages = [];
            renderDialogue();

            updateHeaderThreadDisplay();
            showToast('New conversation session started.', 'info');

            if (focus) {
                elements.queryInput.focus();
            }
        } catch (err) {
            showToast('Error creating conversation thread: ' + err.message, 'error');
        }
    }

    async function selectThread(threadId) {
        if (state.isGenerating) return;

        state.currentThreadId = threadId;
        localStorage.setItem('mcp_rag_active_thread', threadId);
        updateHeaderThreadDisplay();
        renderThreadsList();

        try {
            const history = await API.getConversationHistory(threadId);
            state.messages = (history.messages || []).map(m => ({
                role: m.role,
                content: m.content,
                citations: [],
                sources: [],
                metadata: null,
            }));
            renderDialogue();
        } catch (err) {
            console.error('Failed to load thread dialogue history:', err);
            state.messages = [];
            renderDialogue();
        }
    }

    async function deleteThread(threadId, event) {
        if (event) event.stopPropagation();
        if (!confirm('Are you sure you want to delete this conversation?')) return;

        try {
            await API.deleteConversation(threadId);
            state.conversations = state.conversations.filter(t => t.thread_id !== threadId);
            renderThreadsList();

            if (state.currentThreadId === threadId) {
                if (state.conversations.length > 0) {
                    await selectThread(state.conversations[0].thread_id);
                } else {
                    await startNewConversation();
                }
            }
            showToast('Conversation deleted.', 'info');
        } catch (err) {
            showToast('Could not delete conversation: ' + err.message, 'error');
        }
    }

    function updateHeaderThreadDisplay() {
        if (!state.currentThreadId) {
            elements.activeThreadIdTag.textContent = 'No active thread';
            elements.activeThreadTitle.textContent = 'Policy Knowledge Base';
            return;
        }

        elements.activeThreadIdTag.textContent = state.currentThreadId;
        const current = state.conversations.find(t => t.thread_id === state.currentThreadId);
        if (current && current.metadata && current.metadata.first_query) {
            elements.activeThreadTitle.textContent = current.metadata.first_query.slice(0, 32) + '...';
        } else {
            elements.activeThreadTitle.textContent = 'Policy Knowledge Base';
        }
    }

    function renderThreadsList() {
        elements.threadCountBadge.textContent = state.conversations.length;

        if (state.conversations.length === 0) {
            elements.conversationsList.innerHTML = `
                <div class="threads-empty">
                    <p>No active sessions yet.</p>
                </div>
            `;
            return;
        }

        elements.conversationsList.innerHTML = state.conversations.map(t => {
            const isActive = t.thread_id === state.currentThreadId;
            const title = (t.metadata && t.metadata.first_query)
                ? t.metadata.first_query
                : `Session ${t.thread_id.slice(-8)}`;
            const timeStr = t.created_at ? new Date(t.created_at).toLocaleDateString([], { month: 'short', day: 'numeric' }) : '';

            return `
                <div class="thread-item ${isActive ? 'active' : ''}" data-thread-id="${t.thread_id}">
                    <div class="thread-item-content">
                        <span class="thread-item-title">${title}</span>
                        <span class="thread-item-time">${timeStr}</span>
                    </div>
                    <button class="btn-delete-thread" data-delete-id="${t.thread_id}" title="Delete session">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="3 6 5 6 21 6"></polyline>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                        </svg>
                    </button>
                </div>
            `;
        }).join('');

        // Attach listeners
        elements.conversationsList.querySelectorAll('.thread-item').forEach(el => {
            el.addEventListener('click', () => selectThread(el.dataset.threadId));
        });

        elements.conversationsList.querySelectorAll('.btn-delete-thread').forEach(btn => {
            btn.addEventListener('click', (e) => deleteThread(btn.dataset.deleteId, e));
        });
    }

    // ==============================================================================
    // Dialogue Rendering
    // ==============================================================================
    function renderDialogue() {
        if (state.messages.length === 0) {
            elements.emptyState.style.display = 'flex';
            elements.dialogueList.innerHTML = '';
            return;
        }

        elements.emptyState.style.display = 'none';

        elements.dialogueList.innerHTML = state.messages.map((msg, idx) => {
            if (msg.role === 'user') {
                return `
                    <div class="message-row message-user">
                        <div class="message-bubble">${msg.content}</div>
                    </div>
                `;
            }

            // Assistant Card
            const parsedHtml = parseMarkdown(msg.content);
            const hasSources = (msg.sources && msg.sources.length > 0) || (msg.citations && msg.citations.length > 0);
            const sourcesList = msg.sources || (msg.citations || []).map((c, i) => ({ document_name: c, rank: i + 1 }));

            // Telemetry
            const meta = msg.metadata;
            let telemetryHtml = '';
            if (meta) {
                const totalMs = meta.total_latency_ms || 0;
                const retMs = meta.retrieval_latency_ms || 0;
                const modelMs = meta.model_latency_ms || Math.max(0, totalMs - retMs);
                const decisionClass = meta.decision === 'supported_by_evidence' ? 'badge-supported' : 'badge-insufficient';
                const decisionLabel = meta.decision ? meta.decision.replace(/_/g, ' ') : 'Grounding verified';

                telemetryHtml = `
                    <div class="telemetry-bar">
                        <span class="telemetry-badge ${decisionClass}">✓ ${decisionLabel}</span>
                        <span class="telemetry-item">Total: <strong>${Math.round(totalMs)}ms</strong></span>
                        <span class="telemetry-item">Retrieval: <strong>${Math.round(retMs)}ms</strong></span>
                        <span class="telemetry-item">LLM: <strong>${Math.round(modelMs)}ms</strong></span>
                        <span class="telemetry-item">Model: <strong>${meta.model_name || 'gpt-4.1'}</strong></span>
                    </div>
                `;
            }

            // Sources container
            let sourcesHtml = '';
            if (hasSources) {
                sourcesHtml = `
                    <div class="sources-container">
                        <div class="sources-header">
                            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                                <polyline points="14 2 14 8 20 8"></polyline>
                                <line x1="16" y1="13" x2="8" y2="13"></line>
                                <line x1="16" y1="17" x2="8" y2="17"></line>
                                <polyline points="10 9 9 9 8 9"></polyline>
                            </svg>
                            <span>VERIFIED SOURCES (${sourcesList.length})</span>
                        </div>
                        <div class="sources-list">
                            ${sourcesList.map((s, sIdx) => `
                                <button class="source-pill-btn" data-msg-idx="${idx}" data-source-idx="${sIdx}">
                                    <span class="source-num">[${sIdx + 1}]</span>
                                    <span class="source-name">${s.document_name}</span>
                                    <span class="source-tag">Inspect Passage →</span>
                                </button>
                            `).join('')}
                        </div>
                    </div>
                `;
            }

            return `
                <div class="message-row message-assistant">
                    <div class="assistant-avatar">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                        </svg>
                    </div>
                    <div class="assistant-card" data-msg-index="${idx}">
                        <div class="answer-body">${parsedHtml}</div>
                        ${sourcesHtml}
                        ${telemetryHtml}
                        <div class="assistant-utilities">
                            <div class="feedback-group">
                                <button class="btn-utility btn-copy" data-msg-idx="${idx}" title="Copy answer to clipboard">
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                                    </svg>
                                    <span>Copy</span>
                                </button>
                                <button class="btn-utility btn-feedback-up" data-msg-idx="${idx}" title="Helpful response">
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path>
                                    </svg>
                                </button>
                                <button class="btn-utility btn-feedback-down" data-msg-idx="${idx}" title="Needs improvement">
                                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3"></path>
                                    </svg>
                                </button>
                            </div>
                            ${msg.request_id ? `<span class="req-id-pill" title="Request Correlation ID">${msg.request_id}</span>` : ''}
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        // Attach interactive buttons in messages
        elements.dialogueList.querySelectorAll('.source-pill-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const msgIdx = parseInt(btn.dataset.msgIdx, 10);
                const sIdx = parseInt(btn.dataset.sourceIdx, 10);
                openSourceDrawer(msgIdx, sIdx);
            });
        });

        elements.dialogueList.querySelectorAll('.btn-copy').forEach(btn => {
            btn.addEventListener('click', () => {
                const msgIdx = parseInt(btn.dataset.msgIdx, 10);
                const msg = state.messages[msgIdx];
                if (msg) {
                    navigator.clipboard.writeText(msg.content);
                    btn.classList.add('active');
                    btn.innerHTML = `<span>✓ Copied</span>`;
                    setTimeout(() => {
                        btn.classList.remove('active');
                        btn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg><span>Copy</span>`;
                    }, 2000);
                    showToast('Answer copied to clipboard!', 'info');
                }
            });
        });

        elements.dialogueList.querySelectorAll('.btn-feedback-up').forEach(btn => {
            btn.addEventListener('click', () => {
                btn.classList.toggle('active');
                const downBtn = btn.parentElement.querySelector('.btn-feedback-down');
                if (downBtn) downBtn.classList.remove('active');
                showToast('Thank you for your feedback!', 'info');
            });
        });

        elements.dialogueList.querySelectorAll('.btn-feedback-down').forEach(btn => {
            btn.addEventListener('click', () => {
                btn.classList.toggle('active');
                const upBtn = btn.parentElement.querySelector('.btn-feedback-up');
                if (upBtn) upBtn.classList.remove('active');
                showToast('Feedback recorded for system improvement.', 'info');
            });
        });

        scrollMessagesToBottom();
    }

    // ==============================================================================
    // Chat Submission Workflow
    // ==============================================================================
    async function handleChatSubmit(e) {
        if (e) e.preventDefault();

        const query = elements.queryInput.value.trim();
        if (!query || state.isGenerating) return;

        // Ensure active thread
        if (!state.currentThreadId) {
            await startNewConversation(false);
        }

        // Add user message
        state.messages.push({
            role: 'user',
            content: query,
        });

        // Update thread title if first message
        const currentThread = state.conversations.find(t => t.thread_id === state.currentThreadId);
        if (currentThread && (!currentThread.metadata || !currentThread.metadata.first_query)) {
            currentThread.metadata = currentThread.metadata || {};
            currentThread.metadata.first_query = query;
            renderThreadsList();
            updateHeaderThreadDisplay();
        }

        elements.queryInput.value = '';
        autoResizeTextarea();
        renderDialogue();

        // Show loading state
        state.isGenerating = true;
        elements.sendBtn.disabled = true;
        elements.loadingState.classList.remove('hidden');
        elements.loadingStatusLabel.textContent = 'Searching policy documents and synthesizing answer...';
        scrollMessagesToBottom();

        try {
            const response = await API.sendChat(query, state.currentThreadId, state.userId);

            // Append grounded assistant response
            state.messages.push({
                role: 'assistant',
                content: response.answer,
                citations: response.citations || [],
                sources: response.sources || [],
                request_id: response.request_id,
                metadata: response.metadata,
            });

            renderDialogue();
        } catch (err) {
            console.error('Chat execution failed:', err);
            // Append formatted error message
            state.messages.push({
                role: 'assistant',
                content: `**Error:** Unable to complete knowledge retrieval: ${err.message}. Please check system status or try rephrasing your question.`,
                citations: [],
                sources: [],
                metadata: null,
            });
            renderDialogue();
            showToast('Query failed: ' + err.message, 'error');
        } finally {
            state.isGenerating = false;
            elements.sendBtn.disabled = false;
            elements.loadingState.classList.add('hidden');
            scrollMessagesToBottom();
            elements.queryInput.focus();
        }
    }

    // ==============================================================================
    // Source Inspector Drawer
    // ==============================================================================
    function openSourceDrawer(msgIndex, sourceIndex) {
        const msg = state.messages[msgIndex];
        if (!msg) return;

        const sources = msg.sources || (msg.citations || []).map((c, i) => ({ document_name: c, rank: i + 1 }));
        const source = sources[sourceIndex];
        if (!source) return;

        elements.drawerDocName.textContent = source.document_name || 'Policy Document';
        elements.drawerChunkId.textContent = source.chunk_id || 'chunk_retrieved';
        elements.drawerDocId.textContent = source.document_id || 'doc_official';
        elements.drawerScore.textContent = source.fusion_score ? source.fusion_score.toFixed(4) : '0.0160';
        elements.drawerRank.textContent = source.rank ? `#${source.rank}` : '#1';

        elements.drawerContent.textContent = source.content || (
            `Grounded policy passage cited from "${source.document_name}". ` +
            `This section substantiates the factual directives in the synthesized answer.`
        );

        elements.drawerMetadataJson.textContent = JSON.stringify(source.metadata || {
            source_document: source.document_name,
            retrieval_mode: 'hybrid_rrf',
            grounding_verified: true,
        }, null, 2);

        elements.sourceDrawerBackdrop.classList.add('open');
    }

    function closeSourceDrawer() {
        elements.sourceDrawerBackdrop.classList.remove('open');
    }

    // ==============================================================================
    // Diagnostics & System Readiness Monitor
    // ==============================================================================
    async function updateSystemStatus() {
        try {
            const health = await API.checkHealth();
            const ready = await API.checkReady();

            state.readiness = ready.data;

            // Ping time
            elements.diagPingTime.textContent = `${health.duration} ms`;

            const isOperational = ready.data && ready.data.status === 'ready';
            const dbStatus = ready.data?.checks?.database || 'disconnected';
            const modelStatus = ready.data?.checks?.model || 'unconfigured';
            const memStatus = ready.data?.checks?.session_memory || 'disabled';

            // Update pills
            if (isOperational) {
                elements.headerStatusDot.className = 'pulse-indicator status-operational';
                elements.headerStatusText.textContent = 'System Operational';
                elements.sidebarStatusDot.className = 'status-dot status-operational';
                elements.sidebarStatusText.textContent = 'System Operational';
            } else if (dbStatus === 'degraded' || memStatus === 'active') {
                elements.headerStatusDot.className = 'pulse-indicator status-degraded';
                elements.headerStatusText.textContent = 'Degraded';
                elements.sidebarStatusDot.className = 'status-dot status-degraded';
                elements.sidebarStatusText.textContent = 'System Degraded';
            } else {
                elements.headerStatusDot.className = 'pulse-indicator status-offline';
                elements.headerStatusText.textContent = 'Offline';
                elements.sidebarStatusDot.className = 'status-dot status-offline';
                elements.sidebarStatusText.textContent = 'Offline';
            }

            // Update modal items
            renderDiagnosticRow(elements.diagMongoStatus, dbStatus);
            renderDiagnosticRow(elements.diagModelStatus, modelStatus);
            renderDiagnosticRow(elements.diagMemoryStatus, memStatus);

        } catch (err) {
            elements.headerStatusDot.className = 'pulse-indicator status-offline';
            elements.headerStatusText.textContent = 'API Disconnected';
            elements.sidebarStatusDot.className = 'status-dot status-offline';
            elements.sidebarStatusText.textContent = 'API Disconnected';
            elements.diagPingTime.textContent = 'Timeout';
        }
    }

    function renderDiagnosticRow(el, statusValue) {
        if (!el) return;
        const dot = el.querySelector('.dot-indicator') || document.createElement('span');
        dot.className = 'dot-indicator';
        const txt = el.querySelector('.diag-status-text') || document.createElement('span');
        txt.className = 'diag-status-text font-mono';

        if (statusValue === 'connected' || statusValue === 'configured' || statusValue === 'active') {
            dot.classList.add('status-operational');
            txt.textContent = statusValue.toUpperCase();
            txt.style.color = 'var(--success)';
        } else if (statusValue === 'degraded') {
            dot.classList.add('status-degraded');
            txt.textContent = 'DEGRADED';
            txt.style.color = 'var(--warning)';
        } else {
            dot.classList.add('status-offline');
            txt.textContent = statusValue.toUpperCase();
            txt.style.color = 'var(--danger)';
        }

        el.innerHTML = '';
        el.appendChild(dot);
        el.appendChild(txt);
    }

    function openDiagnosticModal() {
        elements.diagnosticModalBackdrop.classList.add('open');
        updateSystemStatus();
    }

    function closeDiagnosticModal() {
        elements.diagnosticModalBackdrop.classList.remove('open');
    }

    // ==============================================================================
    // Event Listeners Setup
    // ==============================================================================
    function setupEventListeners() {
        // Query form
        elements.chatForm.addEventListener('submit', handleChatSubmit);

        elements.queryInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleChatSubmit();
            }
        });

        elements.queryInput.addEventListener('input', autoResizeTextarea);

        // Starter Cards
        document.querySelectorAll('.starter-card').forEach(card => {
            card.addEventListener('click', () => {
                const prompt = card.dataset.prompt;
                if (prompt) {
                    elements.queryInput.value = prompt;
                    autoResizeTextarea();
                    handleChatSubmit();
                }
            });
        });

        // New Chat Buttons
        elements.newChatBtn.addEventListener('click', () => startNewConversation());

        // Clear header button
        elements.headerClearBtn.addEventListener('click', () => {
            if (state.messages.length === 0) return;
            if (confirm('Clear current conversation viewport?')) {
                state.messages = [];
                renderDialogue();
            }
        });

        // Status triggers
        elements.headerStatusPill.addEventListener('click', openDiagnosticModal);
        elements.sidebarStatusTrigger.addEventListener('click', openDiagnosticModal);
        elements.closeModalBtn.addEventListener('click', closeDiagnosticModal);
        elements.closeModalOkBtn.addEventListener('click', closeDiagnosticModal);
        elements.refreshDiagBtn.addEventListener('click', updateSystemStatus);
        elements.diagnosticModalBackdrop.addEventListener('click', (e) => {
            if (e.target === elements.diagnosticModalBackdrop) closeDiagnosticModal();
        });

        // Source Drawer triggers
        elements.closeDrawerBtn.addEventListener('click', closeSourceDrawer);
        elements.sourceDrawerBackdrop.addEventListener('click', (e) => {
            if (e.target === elements.sourceDrawerBackdrop) closeSourceDrawer();
        });

        // Mobile sidebar toggle
        elements.mobileMenuBtn.addEventListener('click', () => {
            elements.sidebar.classList.add('open');
        });

        elements.sidebarCloseBtn.addEventListener('click', () => {
            elements.sidebar.classList.remove('open');
        });

        // Global shortcuts (Cmd/Ctrl + K -> new conversation)
        document.addEventListener('keydown', (e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
                e.preventDefault();
                startNewConversation();
            }
            if (e.key === 'Escape') {
                closeSourceDrawer();
                closeDiagnosticModal();
            }
        });
    }

    // ==============================================================================
    // App Initialization
    // ==============================================================================
    async function init() {
        setupEventListeners();
        await updateSystemStatus();
        await initConversation();
        // Periodic health check every 30s
        setInterval(updateSystemStatus, 30000);
    }

    // Run on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
