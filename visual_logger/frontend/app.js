/**
 * Visual Logger - Enhanced Client Application
 * Real-time agent monitoring with comprehensive visualization
 */

class ResizeManager {
    constructor() {
        this.resizing = null;
        this.startX = 0;
        this.startWidth = 0;
        this.bindEvents();
    }

    bindEvents() {
        document.addEventListener('mousemove', (e) => this.onMouseMove(e));
        document.addEventListener('mouseup', () => this.onMouseUp());
    }

    initResizer(resizerId, elementId, options = {}) {
        const resizer = document.getElementById(resizerId);
        const element = document.getElementById(elementId);
        
        if (!resizer || !element) return;

        resizer.addEventListener('mousedown', (e) => {
            this.resizing = { element, options };
            this.startX = e.clientX;
            this.startWidth = element.getBoundingClientRect().width;
            resizer.classList.add('resizing');
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
        });
    }

    onMouseMove(e) {
        if (!this.resizing) return;

        const delta = e.clientX - this.startX;
        let newWidth = this.startWidth + delta;
        
        // Handle inverse direction (resizing from right side)
        if (this.resizing.options.inverse) {
            newWidth = this.startWidth - delta;
        }

        if (newWidth > 150 && newWidth < 800) { // Min/Max constraints
            this.resizing.element.style.width = `${newWidth}px`;
        }
    }

    onMouseUp() {
        if (!this.resizing) return;
        
        document.querySelectorAll('.resizer').forEach(r => r.classList.remove('resizing'));
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        this.resizing = null;
    }
}

class VisualLogger {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 2000;
        this.resizer = new ResizeManager();
        
        this.state = {
            connected: false,
            sessionActive: false,
            sessionStartTime: null,
            actions: [],
            events: [], // Unified timeline
            modelRequests: [], // Token tracking
            totalInputTokens: 0,
            totalOutputTokens: 0,
            files: {},
            todos: [],
            tests: [],
            testFilterFailures: false,
            testDeduplicate: true,
            selectedFile: null,
            diffMode: 'split',
            theme: 'dark',
            selectedAction: null,
            graphZoom: 1,
            graphPan: { x: 0, y: 0 },
            isPanning: false,
            showLineTokens: true  // Toggle for per-line token display
        };
        
        this.elements = {};
        this.sessionTimer = null;
        
        this.init();
    }
    
    init() {
        this.cacheElements();
        this.bindEvents();
        this.connect();
        this.startSessionTimer();
        
        // Initialize Resizers
        this.resizer.initResizer('sidebarResizer', 'sidebar');
        this.resizer.initResizer('flowResizer', 'flowDetails', { inverse: true });
        this.resizer.initResizer('actionPanelResizer', 'actionPanel', { inverse: true });
        
        // Zoom controls
        this.initZoomControls();

        mermaid.initialize({ 
            startOnLoad: false, 
            theme: 'dark', 
            securityLevel: 'loose',
            flowchart: { curve: 'basis' }
        });
    }
    
    cacheElements() {
        this.elements = {
            connectionStatus: document.getElementById('connectionStatus'),
            sessionStatus: document.getElementById('sessionStatus'),
            fileTree: document.getElementById('fileTree'),
            fileCount: document.getElementById('fileCount'),
            diffContainer: document.getElementById('diffContainer'),
            diffHeader: document.getElementById('diffHeader'),
            diffStats: document.getElementById('diffStats'),
            actionLog: document.getElementById('actionLog'), // May be null if panel removed
            actionCount: document.getElementById('actionCount'), // May be null
            thinkingContainer: document.getElementById('thinkingContainer'),
            timelineContainer: document.getElementById('timelineContainer'),
            flowContainer: document.getElementById('flowContainer'),
            flowSvg: document.getElementById('flowSvg'),
            todoList: document.getElementById('todoList'),
            todoProgress: document.getElementById('todoProgress'),
            lastAction: document.getElementById('lastAction'),
            actionProgress: document.getElementById('actionProgress'),
            sessionTime: document.getElementById('sessionTime'),
            versionA: document.getElementById('versionA'),
            versionB: document.getElementById('versionB'),
            toastContainer: document.getElementById('toastContainer'),
            actionModal: document.getElementById('actionModal'),
            modalBody: document.getElementById('modalBody'),
            modalTitle: document.getElementById('modalTitle'),
            modalClose: document.getElementById('modalClose'),
            modalOverlay: document.getElementById('modalOverlay'),
            // New elements
            mermaidGraph: document.getElementById('mermaidGraph'),
            detailsContent: document.getElementById('detailsContent'),
            detailsPlaceholder: document.querySelector('.details-placeholder'),
            detailsTitle: document.getElementById('detailsTitle'),
            detailsStatus: document.getElementById('detailsStatus'),
            detailsTime: document.getElementById('detailsTime'),
            detailsArgs: document.getElementById('detailsArgs'),
            detailsResult: document.getElementById('detailsResult'),
            detailsResults: document.getElementById('detailsResult'),
            detailsFiles: document.getElementById('detailsFiles'),
            testsFilterToggle: document.getElementById('testsFilterToggle'),
            testsDeduplicateToggle: document.getElementById('testsDeduplicateToggle'),
            testsClearBtn: document.getElementById('testsClearBtn')
        };
    }
    
    bindEvents() {
        // Tab switching
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => this.switchTab(tab.dataset.tab));
        });
        
        // Diff mode toggle
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.addEventListener('click', () => this.setDiffMode(btn.dataset.mode));
        });
        
        // Theme toggle
        document.getElementById('themeBtn').addEventListener('click', () => this.toggleTheme());
        
        // Clear button
        document.getElementById('clearBtn').addEventListener('click', () => this.clearSession());
        
        // Version selectors
        this.elements.versionA.addEventListener('change', () => this.updateDiff());
        this.elements.versionB.addEventListener('change', () => this.updateDiff());
        
        // Modal close
        this.elements.modalClose.addEventListener('click', () => this.closeModal());
        this.elements.modalOverlay.addEventListener('click', () => this.closeModal());
        
        // Export button
        document.getElementById('exportBtn').addEventListener('click', () => this.exportCurrentTab());

        // Tests filter
        if (this.elements.testsFilterToggle) {
            this.elements.testsFilterToggle.addEventListener('click', () => {
                this.state.testFilterFailures = !this.state.testFilterFailures;
                this.updateTestsFilterButton();
                this.renderTests();
            });
        }

        // Tests deduplicate toggle
        if (this.elements.testsDeduplicateToggle) {
            this.elements.testsDeduplicateToggle.addEventListener('click', () => {
                this.state.testDeduplicate = !this.state.testDeduplicate;
                this.updateTestsDeduplicateButton();
                this.renderTests();
            });
        }

        // Clear Tests button
        if (this.elements.testsClearBtn) {
            this.elements.testsClearBtn.addEventListener('click', () => this.clearTests());
        }
    }
    
    initZoomControls() {
        const zoomIn = document.getElementById('zoomIn');
        const zoomOut = document.getElementById('zoomOut');
        const zoomReset = document.getElementById('zoomReset');
        const viewport = document.getElementById('graphViewport');
        const graph = document.getElementById('mermaidGraph');
        
        if (!zoomIn || !zoomOut || !zoomReset || !viewport || !graph) return;
        
        zoomIn.addEventListener('click', () => {
            this.state.graphZoom = Math.min(this.state.graphZoom + 0.2, 3);
            this.applyZoom();
        });
        
        zoomOut.addEventListener('click', () => {
            this.state.graphZoom = Math.max(this.state.graphZoom - 0.2, 0.4);
            this.applyZoom();
        });
        
        zoomReset.addEventListener('click', () => {
            this.state.graphZoom = 1;
            this.state.graphPan = { x: 0, y: 0 };
            this.applyZoom();
        });
        
        // Token line toggle
        const toggleLineTokens = document.getElementById('toggleLineTokens');
        if (toggleLineTokens) {
            toggleLineTokens.addEventListener('click', () => {
                this.state.showLineTokens = !this.state.showLineTokens;
                toggleLineTokens.classList.toggle('active', this.state.showLineTokens);
                this.updateFlowGraph();
            });
        }
        
        // Pan with mouse drag
        let startPan = { x: 0, y: 0 };
        viewport.addEventListener('mousedown', (e) => {
            if (e.button !== 0) return; // Only left click
            this.state.isPanning = true;
            startPan = { x: e.clientX - this.state.graphPan.x, y: e.clientY - this.state.graphPan.y };
            viewport.style.cursor = 'grabbing';
        });
        
        document.addEventListener('mousemove', (e) => {
            if (!this.state.isPanning) return;
            this.state.graphPan.x = e.clientX - startPan.x;
            this.state.graphPan.y = e.clientY - startPan.y;
            this.applyZoom();
        });
        
        document.addEventListener('mouseup', () => {
            if (this.state.isPanning) {
                this.state.isPanning = false;
                viewport.style.cursor = 'grab';
            }
        });
        
        // Zoom with scroll wheel - centered on mouse position
        viewport.addEventListener('wheel', (e) => {
            e.preventDefault();
            const rect = viewport.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;
            
            const oldZoom = this.state.graphZoom;
            const delta = e.deltaY > 0 ? -0.1 : 0.1;
            const newZoom = Math.max(0.4, Math.min(3, oldZoom + delta));
            
            // Calculate new pan to keep mouse position stable
            const zoomRatio = newZoom / oldZoom;
            this.state.graphPan.x = mouseX - (mouseX - this.state.graphPan.x) * zoomRatio;
            this.state.graphPan.y = mouseY - (mouseY - this.state.graphPan.y) * zoomRatio;
            
            this.state.graphZoom = newZoom;
            this.applyZoom();
        });
        
        viewport.style.cursor = 'grab';
    }
    
    applyZoom() {
        const graph = document.getElementById('mermaidGraph');
        if (!graph) return;
        graph.style.transform = `translate(${this.state.graphPan.x}px, ${this.state.graphPan.y}px) scale(${this.state.graphZoom})`;
    }
    
    // =========================================================================
    // WEBSOCKET CONNECTION
    // =========================================================================
    
    connect() {
        const wsUrl = `ws://${window.location.host}/ws`;
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            this.state.connected = true;
            this.reconnectAttempts = 0;
            this.lastPongTime = Date.now();
            this.startPingPong();
            this.updateConnectionStatus(true);
            this.showToast('Connected to Visual Logger', 'success');
        };

        this.ws.onclose = () => {
            this.state.connected = false;
            this.stopPingPong();
            this.updateConnectionStatus(false);
            this.attemptReconnect();
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
        
        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            } catch (e) {
                console.error('Failed to parse message:', e);
            }
        };

        // Handle ping/pong for connection keepalive
        this.pingInterval = null;
        this.lastPongTime = Date.now();
    }
    
    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            setTimeout(() => this.connect(), this.reconnectDelay);
        }
    }

    startPingPong() {
        // Send pong responses to server pings
        this.pingInterval = setInterval(() => {
            // Check if we haven't received a pong in too long (connection might be dead)
            const timeSinceLastPong = Date.now() - this.lastPongTime;
            if (timeSinceLastPong > 45000) { // 45 seconds without pong
                console.warn('Connection appears dead, reconnecting...');
                this.ws.close();
                return;
            }
        }, 30000); // Check every 30 seconds
    }

    stopPingPong() {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
    }
    
    updateConnectionStatus(connected) {
        const dot = this.elements.connectionStatus.querySelector('.status-dot');
        const text = this.elements.connectionStatus.querySelector('.status-text');
        
        if (connected) {
            dot.classList.add('connected');
            text.textContent = 'Connected';
        } else {
            dot.classList.remove('connected');
            text.textContent = 'Disconnected';
        }
    }
    
    // =========================================================================
    // MESSAGE HANDLING
    // =========================================================================
    
    handleMessage(msg) {
        switch (msg.type) {
            case 'connection_established':
                // Connection confirmed, update pong time
                this.lastPongTime = Date.now();
                break;
            case 'ping':
                // Respond to server ping with pong
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send(JSON.stringify({ type: 'pong' }));
                    this.lastPongTime = Date.now();
                }
                break;
            case 'state_sync':
                this.syncState(msg.data);
                break;
            case 'session_start':
                this.handleSessionStart(msg.data);
                break;
            case 'session_end':
                this.handleSessionEnd(msg.data);
                break;
            case 'action':
                this.handleAction(msg.data);
                break;
            case 'file_snapshot':
                this.handleFileSnapshot(msg.data);
                break;
            case 'file_change':
                this.handleFileChange(msg.data);
                break;
            case 'thinking':
                this.handleThinking(msg.data);
                break;
            case 'model_text':
                this.handleModelText(msg.data);
                break;
            case 'model_request':
                this.handleModelRequest(msg.data);
                break;
            case 'todo_sync':
                this.handleTodoSync(msg.data);
                break;
            case 'test_result':
                this.handleTestResult(msg.data);
                break;
            case 'test_summary':
                this.handleTestSummary(msg.data);
                break;
        }
    }
    
    syncState(data) {
        if (data.active) {
            this.state.sessionActive = true;
            this.elements.sessionStatus.textContent = 'Active';
            this.elements.sessionStatus.classList.add('active');
        }

        // Rebuild state from sync payload
        this.state.actions = data.actions || [];
        this.state.modelRequests = data.model_requests || data.modelRequests || [];
        this.state.tests = data.tests || [];
        this.state.events = [];
        
        // Reconstruct unified events timeline (tool_calls + model_requests)
        const reconstructedEvents = [];
        this.state.actions.forEach(action => {
            reconstructedEvents.push({
                type: 'tool_call',
                data: action,
                timestamp: action.timestamp
            });
        });
        this.state.modelRequests.forEach(req => {
            reconstructedEvents.push({
                type: 'model_request',
                data: req,
                timestamp: req.timestamp
            });
        });
        // Sort by timestamp to preserve execution order
        reconstructedEvents.sort((a, b) => {
            if (a.timestamp && b.timestamp) {
                return new Date(a.timestamp) - new Date(b.timestamp);
            }
            return 0;
        });
        this.state.events = reconstructedEvents;
        
        // Recalculate token totals from model_requests
        this.state.totalInputTokens = 0;
        this.state.totalOutputTokens = 0;
        this.state.modelRequests.forEach(req => {
            this.state.totalInputTokens += req.inputTokens || req.input_tokens || 0;
            this.state.totalOutputTokens += req.outputTokens || req.output_tokens || 0;
        });
        this.updateTokenDisplay();
        
        // Re-render UI pieces
        this.renderActionsFromState();
        this.updateFlowGraph();
        
        if (data.file_history) {
            Object.keys(data.file_history).forEach(path => {
                this.state.files[path] = {
                    history: data.file_history[path],
                    additions: 0,
                    deletions: 0
                };
            });
            this.updateFileTree();
        }
        
        if (data.todos) {
            this.state.todos = data.todos;
            this.renderTodos();
        }
        
        if (data.tests) {
            this.renderTests();
            this.updateTestSummaryCounts();
        }
    }
    
    handleSessionStart(data) {
        this.state.sessionActive = true;
        this.state.sessionStartTime = new Date(data.start_time);
        this.state.actions = [];
        this.state.events = [];
        this.state.files = {};
        this.state.todos = [];
        this.state.tests = [];
        
        this.elements.sessionStatus.textContent = 'Active';
        this.elements.sessionStatus.classList.add('active');
        
        this.clearUI();
        this.showToast('Session started', 'info');
    }
    
    handleSessionEnd(data) {
        this.state.sessionActive = false;
        this.elements.sessionStatus.textContent = 'Completed';
        this.elements.sessionStatus.classList.remove('active');
        this.showToast('Session ended', 'info');
    }
    
    handleAction(action, syncing = false) {
        // Add ID if missing (from sync)
        if (!action.id) action.id = this.state.actions.length;
        
        this.state.actions.push(action);
        
        // Add to unified events
        this.state.events.push({
            type: 'tool_call',
            data: action,
            timestamp: action.timestamp
        });
        
        this.addActionToLog(action);
        this.addToTimeline(action);
        this.updateActionProgress();
        
        if (!syncing) {
            this.updateFlowGraph();
            this.elements.lastAction.textContent = `Last: ${action.name}`;
        }
    }
    
    handleFileSnapshot(data) {
        if (!this.state.files[data.path]) {
            this.state.files[data.path] = {
                history: [],
                additions: 0,
                deletions: 0
            };
        }
    }
    
    handleFileChange(data) {
        const { path, diff, action_id } = data;
        
        if (!this.state.files[path]) {
            this.state.files[path] = {
                history: [],
                additions: 0,
                deletions: 0
            };
        }
        
        this.state.files[path].additions += diff.additions;
        this.state.files[path].deletions += diff.deletions;
        this.state.files[path].latestDiff = diff;
        
        this.updateFileTree();
        
        if (!this.state.selectedFile || this.state.selectedFile === path) {
            this.selectFile(path);
        }
        
        const filename = path.split('/').pop();
        this.showToast(`File modified: ${filename} (+${diff.additions} -${diff.deletions})`, 'success');
    }
    
    handleThinking(data) {
        this.logThinkingBubble(data, 'agent-thought', '💭 Thought');
        
        // Add to unified events
        this.state.events.push({
            type: 'thinking',
            data: data,
            timestamp: data.timestamp
        });
        
        this.updateFlowGraph();
    }
    
    handleModelText(data) {
        this.logThinkingBubble(data, 'model-response', '🤖 Response');
        
        // Add to unified events
        this.state.events.push({
            type: 'model_text',
            data: data,
            timestamp: data.timestamp
        });
        
        this.updateFlowGraph();
    }
    
    logThinkingBubble(data, className, title) {
        const container = this.elements.thinkingContainer;
        
        const emptyState = container.querySelector('.empty-state');
        if (emptyState) emptyState.remove();
        
        const bubble = document.createElement('div');
        bubble.className = `thinking-bubble ${className}`;
        bubble.innerHTML = `
            <div class="bubble-header">
                <span class="bubble-title">${title}</span>
                <span class="thinking-timestamp">${this.formatTime(data.timestamp)}</span>
            </div>
            <div class="thinking-content">${this.escapeHtml(data.content)}</div>
        `;
        
        container.appendChild(bubble);
        container.scrollTop = container.scrollHeight;
        this.notifyTab('thinking');
    }
    
    handleTodoSync(data) {
        this.state.todos = data.todos || [];
        this.renderTodos();
    }
    
    handleModelRequest(data) {
        // Track the model request with token usage
        const request = {
            id: data.request_id,
            inputTokens: data.input_tokens,
            outputTokens: data.output_tokens,
            cumulativeBefore: data.cumulative_before,
            cumulativeAfter: data.cumulative_after,
            toolCalls: data.tool_calls || [],
            isParallel: data.is_parallel,
            timestamp: data.timestamp,
            chatHistory: data.chat_history
        };
        
        this.state.modelRequests.push(request);
        
        // FIX: Add to unified events so it appears in the flow and triggers grouping
        this.state.events.push({
            type: 'model_request',
            data: data, 
            timestamp: data.timestamp
        });

        // Track cumulative totals for input and output separately
        this.state.totalInputTokens += request.inputTokens || 0;
        this.state.totalOutputTokens += request.outputTokens || 0;
        
        // Always update flow graph when we get a model request
        this.updateFlowGraph();
        
        // Update token display
        this.updateTokenDisplay();
    }
    
    updateTokenDisplay() {
        const inputEl = document.getElementById('totalInputTokens');
        const outputEl = document.getElementById('totalOutputTokens');
        
        if (inputEl) {
            inputEl.textContent = `↓ ${this.state.totalInputTokens.toLocaleString()}`;
            inputEl.title = `Total input tokens: ${this.state.totalInputTokens.toLocaleString()}`;
        }
        if (outputEl) {
            outputEl.textContent = `↑ ${this.state.totalOutputTokens.toLocaleString()}`;
            outputEl.title = `Total output tokens: ${this.state.totalOutputTokens.toLocaleString()}`;
        }
    }
    
    notifyTab(tabName) {
        const tab = document.querySelector(`.tab[data-tab="${tabName}"]`);
        if (tab && !tab.classList.contains('active')) {
            tab.classList.add('has-update');
            setTimeout(() => tab.classList.remove('has-update'), 2000);
        }
    }
    
    // =========================================================================
    // TODO LIST
    // =========================================================================
    
    renderTodos() {
        const container = this.elements.todoList;
        container.innerHTML = '';
        
        if (this.state.todos.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <span class="empty-icon">📝</span>
                    <span class="empty-text">No tasks yet</span>
                </div>
            `;
            this.elements.todoProgress.textContent = '0/0';
            return;
        }
        
        const completed = this.state.todos.filter(t => t.completed).length;
        this.elements.todoProgress.textContent = `${completed}/${this.state.todos.length}`;
        
        this.state.todos.forEach((todo, idx) => {
            const item = document.createElement('div');
            item.className = `todo-item ${todo.completed ? 'completed' : ''} ${todo.is_current ? 'current' : ''}`;
            item.innerHTML = `
                <div class="todo-header">
                    <span class="todo-status">${todo.completed ? '✓' : todo.is_current ? '⏳' : '○'}</span>
                    <span class="todo-title">${this.escapeHtml(todo.title)}</span>
                </div>
                <div class="todo-description">${this.escapeHtml(todo.description)}</div>
            `;
            container.appendChild(item);
        });
    }
    
    // =========================================================================
    // ACTION LOG WITH CLICKABLE DETAILS
    // =========================================================================
    
    addActionToLog(action) {
        // Action Log panel has been removed - actions are now shown in Timeline tab
        // This method is kept as a no-op for backward compatibility
        if (this.elements.actionCount) {
            this.elements.actionCount.textContent = this.state.actions.length;
        }
    }
    
    showActionDetails(action) {
        this.elements.modalTitle.textContent = `${action.name} - Full Details`;
        this.elements.modalBody.innerHTML = `
            <div class="modal-section">
                <h4>Status</h4>
                <p class="${action.success === false ? 'error' : 'success'}">
                    ${action.success === false ? '✗ Failed' : '✓ Success'}
                </p>
            </div>
            <div class="modal-section">
                <h4>Timestamp</h4>
                <p>${this.formatTime(action.timestamp)}</p>
            </div>
            <div class="modal-section">
                <h4>Arguments</h4>
                <pre class="code-block">${this.escapeHtml(JSON.stringify(action.args_full || action.args, null, 2))}</pre>
            </div>
            <div class="modal-section">
                <h4>Result</h4>
                <pre class="code-block">${this.escapeHtml(action.result_full || action.result)}</pre>
            </div>
        `;
        this.elements.actionModal.classList.add('active');
    }
    
    closeModal() {
        this.elements.actionModal.classList.remove('active');
    }
    
    // =========================================================================
    // FLOW GRAPH VISUALIZATION
    // =========================================================================
    
    async updateFlowGraph() {
        // Always use the simple event-based flow that includes all event types
        // (model_text, thinking, tool_call)
        return this.renderSimpleFlow();
    }
    
    buildStepsFromRequests() {
        // Build steps from model_requests, preserving original indices
        const steps = [];
        this.state.modelRequests.forEach((req, originalIdx) => {
            if (req.toolCalls && req.toolCalls.length > 0) {
                steps.push({
                    originalIndex: originalIdx,  // Keep original index for click handling
                    requestId: req.id,
                    inputTokens: req.inputTokens,
                    outputTokens: req.outputTokens,
                    cumulativeBefore: req.cumulativeBefore,
                    toolCalls: req.toolCalls,
                    timestamp: req.timestamp,
                    chatHistory: req.chatHistory
                });
            }
        });
        return steps;
    }
    
    async renderSimpleFlow() {
        // Simple event-based flow visualization
        const events = this.state.events;
        console.log('renderSimpleFlow called with', events.length, 'events:', events.map(e => e.type));
        if (events.length === 0) return;
        
        const graphContainer = document.getElementById('mermaidGraph');
        if (!graphContainer) return;
        
        let graphDef = 'graph TD;\n';
        
        // First pass: identify which tool_calls belong to parallel groups
        // based on model_request events that have is_parallel=true
        const parallelGroups = new Map(); // idx -> group_id
        let groupCounter = 0;
        
        // Find model_request events and group the tool_calls that belong to them.
        // Backend logs model_request *after* running the tools, so we search
        // immediately preceding tool_call events first, then fall back to
        // following tool_call events for older ordering.
        for (let i = 0; i < events.length; i++) {
            const event = events[i];
            
            const isParallel = event.data && (event.data.is_parallel || event.data.isParallel);

            if (event.type === 'model_request' && isParallel) {
                const tools = event.data.tool_calls || event.data.toolCalls || [];
                const numTools = tools.length;
                
                if (numTools > 1) {
                    const groupId = groupCounter++;
                    const groupIndices = [];

                    // Prefer tool calls right before the model_request (current backend order)
                    for (let j = i - 1; j >= 0 && groupIndices.length < numTools; j--) {
                        const prevEvent = events[j];
                        if (prevEvent.type === 'model_request') break; // stop at previous turn
                        if (prevEvent.type === 'tool_call' && !parallelGroups.has(j)) {
                            // unshift to preserve original order
                            groupIndices.unshift(j);
                        }
                    }

                    // If not enough were found (legacy ordering), grab ones after
                    if (groupIndices.length < numTools) {
                        for (let j = i + 1; j < events.length && groupIndices.length < numTools; j++) {
                            const nextEvent = events[j];
                            if (nextEvent.type === 'model_request') break; // next turn
                            if (nextEvent.type === 'tool_call' && !parallelGroups.has(j)) {
                                groupIndices.push(j);
                            }
                        }
                    }

                    groupIndices.forEach(gIdx => parallelGroups.set(gIdx, groupId));
                }
            }
        }
        
        // Build token map: associate tool_calls with their model_request's token count
        // Each model_request follows its tool_calls, so we look backwards from each model_request
        const tokenMap = new Map(); // idx -> {input, output}
        for (let i = 0; i < events.length; i++) {
            const event = events[i];
            if (event.type === 'model_request') {
                const inputTokens = event.data.input_tokens || event.data.inputTokens || 0;
                const outputTokens = event.data.output_tokens || event.data.outputTokens || 0;
                const tools = event.data.tool_calls || event.data.toolCalls || [];
                const numTools = tools.length || 1; // At least 1 for single tool requests
                
                // Associate preceding tool_calls with this model_request's tokens
                let foundTools = 0;
                for (let j = i - 1; j >= 0 && foundTools < numTools; j--) {
                    const prevEvent = events[j];
                    if (prevEvent.type === 'model_request') break;
                    if (prevEvent.type === 'tool_call' && !tokenMap.has(j)) {
                        tokenMap.set(j, { input: inputTokens, output: outputTokens });
                        foundTools++;
                    }
                }
            }
        }
        
        // Second pass: build the graph with proper grouping
        let prevNodeIds = [];
        let processedGroups = new Set();
        
        for (let idx = 0; idx < events.length; idx++) {
            const event = events[idx];
            const nodeId = `node${idx}`;
            
            // Skip model_request events in the visual flow (they're metadata)
            if (event.type === 'model_request') {
                continue;
            }
            
            // Check if this is part of a parallel group
            if (parallelGroups.has(idx)) {
                const groupId = parallelGroups.get(idx);
                
                // Only process each group once (when we hit its first member)
                if (processedGroups.has(groupId)) {
                    continue;
                }
                processedGroups.add(groupId);
                
                // Find all indices in this group
                const groupIndices = [];
                for (const [eIdx, gId] of parallelGroups.entries()) {
                    if (gId === groupId) groupIndices.push(eIdx);
                }
                
                // Generate subgraph for parallel tools
                graphDef += `    subgraph parallel_${groupId} [" "]\n`;
                graphDef += `    direction LR\n`;
                
                const groupNodeIds = [];
                groupIndices.forEach(gIdx => {
                    const gEvent = events[gIdx];
                    const gNodeId = `node${gIdx}`;
                    graphDef += this.generateNodeDef(gEvent, gIdx);
                    groupNodeIds.push(gNodeId);
                });
                
                graphDef += `    end\n`;
                
                // Link from previous nodes to all nodes in parallel group with token labels
                // Get token info for this group (all share same tokens)
                const firstGroupIdx = groupIndices[0];
                const groupTokenInfo = tokenMap.get(firstGroupIdx);
                const tokenLabel = (this.state.showLineTokens && groupTokenInfo) ? `|${groupTokenInfo.input.toLocaleString()}t|` : '';
                
                prevNodeIds.forEach(prevId => {
                    groupNodeIds.forEach(currId => {
                        graphDef += `    ${prevId} -->${tokenLabel} ${currId};\n`;
                    });
                });
                
                prevNodeIds = groupNodeIds;
            } else {
                // Regular single node
                graphDef += this.generateNodeDef(event, idx);
                
                // Get token info for edge label
                const edgeTokenInfo = tokenMap.get(idx);
                const edgeTokenLabel = (this.state.showLineTokens && edgeTokenInfo) ? `|${edgeTokenInfo.input.toLocaleString()}t|` : '';
                
                prevNodeIds.forEach(prevId => {
                    graphDef += `    ${prevId} -->${edgeTokenLabel} ${nodeId};\n`;
                });
                
                prevNodeIds = [nodeId];
            }
        }

        graphDef += '    classDef success fill:#162420,stroke:#00ff9f,stroke-width:2px,color:#e6edf3;\n';
        graphDef += '    classDef error fill:#4a1515,stroke:#ff4444,stroke-width:2px,color:#ff4444;\n';
        graphDef += '    classDef thought fill:#1a1a2e,stroke:#6e7681,stroke-width:1px,stroke-dasharray:5 5,color:#8b949e;\n';
        graphDef += '    classDef modelText fill:#0d1117,stroke:#58a6ff,stroke-width:1px,stroke-dasharray:3 3,color:#58a6ff;\n';
        graphDef += '    classDef complete fill:#1a3a1a,stroke:#4ade80,stroke-width:3px,color:#e6edf3;\n';
        graphDef += '    classDef parallel fill:#2d2d44,stroke:#bd93f9,stroke-width:2px,color:#f8f8f2,stroke-dasharray: 2 2;\n';
        
        try {
            const { svg } = await mermaid.render('mermaidGraphSvg', graphDef);
            graphContainer.innerHTML = svg;
            this.bindFlowNodeClicks();
        } catch (e) {
            console.error('Mermaid render error:', e);
        }
    }
    
    bindFlowNodeClicksForSteps() {
        const graphContainer = document.getElementById('mermaidGraph');
        if (!graphContainer) return;
        
        const nodes = graphContainer.querySelectorAll('.node');
        nodes.forEach(node => {
            // Extract step and tool index from node id (e.g., "flowchart-s0t1-123")
            const match = node.id.match(/s(\d+)t(\d+)/);
            if (match) {
                const stepIdx = parseInt(match[1], 10);
                const toolIdx = parseInt(match[2], 10);
                node.style.cursor = 'pointer';
                node.addEventListener('click', () => this.showStepDetails(stepIdx, toolIdx));
            }
        });
    }
    
    showStepDetails(stepIdx, toolIdx) {
        const step = this.state.modelRequests[stepIdx];
        if (!step) return;
        
        const tool = step.toolCalls[toolIdx];
        if (!tool) return;
        
        const detailsPanel = document.getElementById('detailsContent');
        const placeholder = document.querySelector('.details-placeholder');
        
        if (placeholder) placeholder.style.display = 'none';
        detailsPanel.classList.remove('hidden');
        
        document.getElementById('detailsTitle').textContent = tool.name;
        
        const statusEl = document.getElementById('detailsStatus');
        statusEl.textContent = tool.success === false ? 'Failed' : 'Success';
        statusEl.className = `tag ${tool.success === false ? 'error' : 'success'}`;
        statusEl.style.display = '';
        
        document.getElementById('detailsTime').textContent = this.formatTime(step.timestamp);
        
        document.getElementById('detailsArgs').parentElement.style.display = '';
        document.getElementById('detailsResult').parentElement.style.display = '';
        document.getElementById('detailsArgs').textContent = JSON.stringify(tool.args, null, 2);
        document.getElementById('detailsResult').textContent = tool.result || '(No result)';
        document.getElementById('detailsFiles').innerHTML = '';
        
        // Show token info for this step
        const tokenInfo = `Input: ${step.inputTokens.toLocaleString()} | Cumulative before: ${step.cumulativeBefore.toLocaleString()}`;
        document.getElementById('detailsFiles').innerHTML = `<div class="token-step-info">${tokenInfo}</div>`;
        
        // Chat history download
        this.renderChatHistory(step.chatHistory, document.getElementById('detailsChatHistory'), document.getElementById('toggleChatHistory'));
    }
    
    generateNodeDef(event, idx) {
        const nodeId = `node${idx}`;
        let nodeDef = '';
        
        if (event.type === 'tool_call') {
            const action = event.data;
            const name = action.name.replace(/["\n\[\]<>]/g, '');
            // Create a brief args summary
            let argsSummary = '';
            if (action.args) {
                const keys = Object.keys(action.args);
                if (keys.length > 0) {
                    const firstArg = this.truncate(String(action.args[keys[0]]), 20).replace(/["\n\[\]<>]/g, '');
                    argsSummary = ` - ${firstArg}`;
                }
            }
            
            // Special styling for complete_task
            if (action.name === 'complete_task') {
                const isFailed = action.success === false || (action.result && String(action.result).trim().startsWith('Error:'));
                if (isFailed) {
                    nodeDef = `    ${nodeId}[["✗ ${name}"]]:::error;\n`;
                } else {
                    nodeDef = `    ${nodeId}[["✓ ${name}"]]:::complete;\n`;
                }
            } else {
                const isFailed = action.success === false || (action.result && String(action.result).trim().startsWith('Error:'));
                const styleClass = isFailed ? ':::error' : ':::success';
                nodeDef = `    ${nodeId}["${name}${argsSummary}"]${styleClass};\n`;
            }
            
        } else if (event.type === 'thinking') {
            const content = this.truncate(event.data.content, 35).replace(/["\n\[\]<>]/g, '');
            nodeDef = `    ${nodeId}("💭 ${content}"):::thought;\n`;
            
        } else if (event.type === 'model_text') {
            const content = this.truncate(event.data.content, 35).replace(/["\n\[\]<>]/g, '');
            nodeDef = `    ${nodeId}("🤖 ${content}"):::modelText;\n`;
            
        } else if (event.type === 'model_request' && (event.data.isParallel || event.data.is_parallel)) {
            // Render parallel tools as a grouped node
            const tools = event.data.toolCalls || event.data.tool_calls || [];
            const toolNames = tools.map(t => t.name).join(', ');
            const tokens = (event.data.inputTokens || event.data.input_tokens || 0).toLocaleString();
            nodeDef = `    ${nodeId}[/"⚡ Parallel: ${toolNames} (${tokens} tokens)"/]:::parallel;\n`;
        }
        
        return nodeDef;
    }
    
    bindFlowNodeClicks() {
        const graphContainer = document.getElementById('mermaidGraph');
        if (!graphContainer) return;
        
        // Find all node groups in the SVG
        const nodes = graphContainer.querySelectorAll('.node');
        nodes.forEach(node => {
            // Extract index from node id (e.g., "flowchart-node0-123" -> 0)
            const match = node.id.match(/node(\d+)/);
            if (match) {
                const idx = parseInt(match[1], 10);
                node.style.cursor = 'pointer';
                node.addEventListener('click', () => this.showFlowDetails(idx));
            }
        });
    }

    showFlowDetails(index) {
        const event = this.state.events[index];
        if (!event) return;
        
        const detailsPanel = document.getElementById('detailsContent');
        const placeholder = document.querySelector('.details-placeholder');
        
        if (placeholder) placeholder.style.display = 'none';
        detailsPanel.classList.remove('hidden');
        
        const chatHistoryContainer = document.getElementById('detailsChatHistory');
        const toggleBtn = document.getElementById('toggleChatHistory');
        
        // Handle different event types
        if (event.type === 'tool_call') {
            const action = event.data;
            
            // Populate details
            document.getElementById('detailsTitle').textContent = action.name;
            
            const statusEl = document.getElementById('detailsStatus');
            statusEl.textContent = action.success === false ? 'Failed' : 'Success';
            statusEl.className = `tag ${action.success === false ? 'error' : 'success'}`;
            statusEl.style.display = '';
            
            document.getElementById('detailsTime').textContent = this.formatTime(action.timestamp);
            
            document.getElementById('detailsArgs').textContent = JSON.stringify(action.args_full || action.args, null, 2);
            document.getElementById('detailsResult').textContent = action.result_full || action.result || '(No result)';
            
            // Show args/result sections
            document.getElementById('detailsArgs').parentElement.style.display = '';
            document.getElementById('detailsResult').parentElement.style.display = '';
            
            // Related files
            this.renderRelatedFiles(action.id);
            
            // Chat History
            this.renderChatHistory(action.chat_history, chatHistoryContainer, toggleBtn);
            
        } else if (event.type === 'thinking') {
            document.getElementById('detailsTitle').textContent = '💭 Thought';
            document.getElementById('detailsStatus').style.display = 'none';
            document.getElementById('detailsTime').textContent = this.formatTime(event.data.timestamp);
            
            document.getElementById('detailsArgs').parentElement.style.display = 'none';
            document.getElementById('detailsResult').parentElement.style.display = '';
            document.getElementById('detailsResult').textContent = event.data.content;
            
            document.getElementById('detailsFiles').innerHTML = '';
            
            this.renderChatHistory(event.data.chat_history, chatHistoryContainer, toggleBtn);
            
        } else if (event.type === 'model_text') {
            document.getElementById('detailsTitle').textContent = '🤖 Model Response';
            document.getElementById('detailsStatus').style.display = 'none';
            document.getElementById('detailsTime').textContent = this.formatTime(event.data.timestamp);
            
            document.getElementById('detailsArgs').parentElement.style.display = 'none';
            document.getElementById('detailsResult').parentElement.style.display = '';
            document.getElementById('detailsResult').textContent = event.data.content;
            
            document.getElementById('detailsFiles').innerHTML = '';
            
            this.renderChatHistory(event.data.chat_history, chatHistoryContainer, toggleBtn);
        }
    }
    
    renderRelatedFiles(actionIdx) {
        const files = Object.entries(this.state.files).filter(([path, data]) => {
           return data.history && data.history.some(h => h.action_id === actionIdx);
        });
        
        const filesContainer = document.getElementById('detailsFiles');
        filesContainer.innerHTML = '';
        
        if (files.length > 0) {
            files.forEach(([path, data]) => {
                const item = document.createElement('div');
                item.className = 'file-item';
                item.style.padding = '8px';
                item.innerHTML = `<span class="file-name">${path.split('/').pop()}</span>`;
                item.style.cursor = 'pointer';
                item.onclick = () => {
                    this.switchTab('diff');
                    this.selectFile(path);
                };
                filesContainer.appendChild(item);
            });
        } else {
            filesContainer.innerHTML = '<span class="text-tertiary" style="font-size: 11px;">No files modified in this step</span>';
        }
    }
    
    renderChatHistory(chatHistory, container, toggleBtn) {
        if (!chatHistory || chatHistory.length === 0) {
            container.innerHTML = '';
            toggleBtn.style.display = 'none';
            return;
        }
        
        toggleBtn.style.display = '';
        toggleBtn.textContent = '📥 Download';
        container.innerHTML = '';
        
        // Store chat history for download
        toggleBtn.onclick = () => this.downloadChatHistory(chatHistory);
    }
    
    downloadChatHistory(chatHistory) {
        // Generate markdown content
        let markdown = '# Chat History Snapshot\n\n';
        markdown += `**Exported at:** ${new Date().toISOString()}\n\n---\n\n`;
        
        chatHistory.forEach((entry, idx) => {
            const roleIcon = entry.role === 'user' ? '👤' : '🤖';
            markdown += `## ${roleIcon} ${entry.role.toUpperCase()}\n\n`;
            
            entry.parts.forEach(p => {
                if (p.type === 'text') {
                    markdown += p.text + '\n\n';
                } else if (p.type === 'function_call') {
                    markdown += `**Tool Call:** \`${p.name}\`\n\`\`\`json\n${JSON.stringify(p.args, null, 2)}\n\`\`\`\n\n`;
                }
            });
            
            markdown += '---\n\n';
        });
        
        // Create and trigger download
        const blob = new Blob([markdown], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `chat_history_${Date.now()}.md`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        this.showToast('Chat history downloaded', 'success');
    }
    
    // =========================================================================
    // FILE TREE & DIFF VIEWER
    // =========================================================================
    
    updateFileTree() {
        const container = this.elements.fileTree;
        container.innerHTML = '';
        
        const files = Object.entries(this.state.files);
        this.elements.fileCount.textContent = files.length;
        
        if (files.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <span class="empty-icon">📂</span>
                    <span class="empty-text">No files modified yet</span>
                </div>
            `;
            return;
        }
        
        files.forEach(([path, data]) => {
            const filename = path.split('/').pop();
            const dirPath = path.split('/').slice(0, -1).join('/');
            const icon = this.getFileIcon(filename);
            
            const item = document.createElement('div');
            item.className = `file-item ${this.state.selectedFile === path ? 'active' : ''}`;
            item.innerHTML = `
                <span class="file-icon">${icon}</span>
                <div class="file-info">
                    <div class="file-name">${this.escapeHtml(filename)}</div>
                    <div class="file-path">${this.escapeHtml(dirPath)}</div>
                </div>
                <div class="file-stats">
                    <span class="add">+${data.additions}</span>
                    <span class="del">-${data.deletions}</span>
                </div>
            `;
            
            item.addEventListener('click', () => this.selectFile(path));
            container.appendChild(item);
        });
    }
    
    selectFile(path) {
        this.state.selectedFile = path;
        
        document.querySelectorAll('.file-item').forEach(item => item.classList.remove('active'));
        document.querySelectorAll('.file-item').forEach(item => {
            if (item.querySelector('.file-path').textContent === path.split('/').slice(0, -1).join('/') &&
                item.querySelector('.file-name').textContent === path.split('/').pop()) {
                item.classList.add('active');
            }
        });
        
        this.elements.diffHeader.querySelector('.diff-filename').textContent = path;
        this.updateDiff();
        this.updateVersionSelectors(path);
    }
    
    updateDiff() {
        const path = this.state.selectedFile;
        if (!path || !this.state.files[path]) return;
        
        const file = this.state.files[path];
        const diff = file.latestDiff;
        
        if (!diff) {
            this.elements.diffContainer.innerHTML = `
                <div class="diff-empty">
                    <div class="diff-empty-icon">📄</div>
                    <div class="diff-empty-text">No changes to display</div>
                </div>
            `;
            return;
        }
        
        this.elements.diffStats.innerHTML = `
            <span class="stat additions">+${diff.additions}</span>
            <span class="stat deletions">-${diff.deletions}</span>
        `;
        
        if (this.state.diffMode === 'split') {
            this.renderSplitDiff(diff);
        } else {
            this.renderUnifiedDiff(diff);
        }
    }
    
    renderSplitDiff(diff) {
        const container = this.elements.diffContainer;
        let leftHtml = '';
        let rightHtml = '';
        
        diff.side_by_side.forEach(line => {
            const leftNum = line.old_line || '';
            const rightNum = line.new_line || '';
            const leftContent = this.escapeHtml(line.old_content);
            const rightContent = this.escapeHtml(line.new_content);
            
            let leftClass = '';
            let rightClass = '';
            
            switch (line.type) {
                case 'delete':
                    leftClass = 'delete';
                    break;
                case 'insert':
                    rightClass = 'insert';
                    break;
                case 'change':
                    leftClass = 'delete';
                    rightClass = 'insert';
                    break;
            }
            
            leftHtml += `
                <div class="diff-line ${leftClass}">
                    <span class="diff-line-number">${leftNum}</span>
                    <span class="diff-line-content">${leftContent}</span>
                </div>
            `;
            
            rightHtml += `
                <div class="diff-line ${rightClass}">
                    <span class="diff-line-number">${rightNum}</span>
                    <span class="diff-line-content">${rightContent}</span>
                </div>
            `;
        });
        
        container.innerHTML = `
            <div class="diff-split">
                <div class="diff-pane">
                    <div class="diff-pane-header">Original</div>
                    ${leftHtml}
                </div>
                <div class="diff-pane">
                    <div class="diff-pane-header">Modified</div>
                    ${rightHtml}
                </div>
            </div>
        `;
    }
    
    renderUnifiedDiff(diff) {
        const container = this.elements.diffContainer;
        const lines = diff.unified.split('\n');
        
        let html = '<div class="diff-unified">';
        
        lines.forEach(line => {
            let lineClass = '';
            if (line.startsWith('+') && !line.startsWith('+++')) {
                lineClass = 'insert';
            } else if (line.startsWith('-') && !line.startsWith('---')) {
                lineClass = 'delete';
            } else if (line.startsWith('@@')) {
                lineClass = 'hunk-header';
            }
            
            html += `
                <div class="diff-line ${lineClass}">
                    <span class="diff-line-content">${this.escapeHtml(line)}</span>
                </div>
            `;
        });
        
        html += '</div>';
        container.innerHTML = html;
    }
    
    updateVersionSelectors(path) {
        const file = this.state.files[path];
        if (!file || !file.history) return;
        
        const versionA = this.elements.versionA;
        const versionB = this.elements.versionB;
        
        versionA.innerHTML = '<option value="0">Original</option>';
        versionB.innerHTML = '';
        
        file.history.forEach((entry, idx) => {
            if (idx > 0) {
                versionA.innerHTML += `<option value="${idx}">Version ${idx}</option>`;
            }
            versionB.innerHTML += `<option value="${idx}">${idx === file.history.length - 1 ? 'Latest' : `Version ${idx}`}</option>`;
        });
        
        versionB.value = file.history.length - 1;
    }
    
    // =========================================================================
    // TIMELINE
    // =========================================================================
    
    addToTimeline(action) {
        const container = this.elements.timelineContainer;
        
        const emptyState = container.querySelector('.empty-state');
        if (emptyState) emptyState.remove();
        
        const item = document.createElement('div');
        item.className = 'timeline-item';
        item.innerHTML = `
            <div class="timeline-dot ${action.success === false ? 'error' : ''}"></div>
            <div class="timeline-content">
                <div class="timeline-header">
                    <span class="timeline-action">${this.escapeHtml(action.name)}</span>
                    <span class="timeline-time">${this.formatTime(action.timestamp)}</span>
                </div>
                <div class="timeline-details">${this.formatArgs(action.args)}</div>
            </div>
        `;
        
        container.appendChild(item);
    }
    
    // =========================================================================
    // UI CONTROLS
    // =========================================================================

    renderActionsFromState() {
        // Clear and rebuild action log & timeline from current state.actions
        if (this.elements.actionLog) {
            this.elements.actionLog.innerHTML = '';
            this.state.actions.forEach(action => this.addActionToLog(action));
        }
        if (this.elements.timelineContainer) {
            this.elements.timelineContainer.innerHTML = '';
            this.state.actions.forEach(action => this.addToTimeline(action));
        }
        this.updateActionProgress();
    }
    
    updateTestsFilterButton() {
        const btn = this.elements.testsFilterToggle;
        if (!btn) return;
        btn.textContent = this.state.testFilterFailures ? 'Show all tests' : 'Show failures only';
        btn.classList.toggle('active', this.state.testFilterFailures);
    }

    updateTestsDeduplicateButton() {
        const btn = this.elements.testsDeduplicateToggle;
        if (!btn) return;
        btn.classList.toggle('active', this.state.testDeduplicate);
    }
    
    updateActionProgress() {
        this.elements.actionProgress.textContent = `Actions: ${this.state.actions.length}`;
    }
    
    clearUI() {
        if (this.elements.actionLog) {
            this.elements.actionLog.innerHTML = `
                <div class="empty-state">
                    <span class="empty-icon">⚙️</span>
                    <span class="empty-text">Waiting for actions...</span>
                </div>
            `;
        }
        if (this.elements.actionCount) {
            this.elements.actionCount.textContent = '0';
        }
        
        this.elements.fileTree.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">📂</span>
                <span class="empty-text">No files modified yet</span>
            </div>
        `;
        this.elements.fileCount.textContent = '0';
        
        this.elements.thinkingContainer.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">💭</span>
                <span class="empty-text">Agent thoughts will appear here</span>
            </div>
        `;
        
        this.elements.timelineContainer.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">📊</span>
                <span class="empty-text">Action timeline will appear here</span>
            </div>
        `;
        
        this.elements.diffContainer.innerHTML = `
            <div class="diff-empty">
                <div class="diff-empty-icon">⚡</div>
                <div class="diff-empty-text">Select a modified file to view changes</div>
                <div class="diff-empty-hint">Files will appear as they are modified during the session</div>
            </div>
        `;
        
        this.elements.todoList.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">📝</span>
                <span class="empty-text">No tasks yet</span>
            </div>
        `;
        
        // Reset tests container
        const testsContainer = document.getElementById('testsContainer');
        if (testsContainer) {
            testsContainer.innerHTML = `
                <div class="empty-state">
                    <span class="empty-icon">🧪</span>
                    <span class="empty-text">No test results available</span>
                    <span class="empty-subtext">Run tests to see results here</span>
                </div>`;
        }
        this.updateTestSummaryCounts();
        
        this.elements.flowSvg.innerHTML = '';
        const emptyFlow = this.elements.flowContainer.querySelector('.flow-empty');
        if (emptyFlow) emptyFlow.style.display = 'flex';
    }
    
    switchTab(tabName) {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelector(`.tab[data-tab="${tabName}"]`).classList.add('active');
        
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        document.getElementById(`${tabName}Tab`).classList.add('active');
        
        if (tabName === 'flow') {
            setTimeout(() => this.updateFlowGraph(), 100);
        }
    }
    
    setDiffMode(mode) {
        this.state.diffMode = mode;
        document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
        document.querySelector(`.mode-btn[data-mode="${mode}"]`).classList.add('active');
        this.updateDiff();
    }
    
    toggleTheme() {
        const html = document.documentElement;
        const current = html.getAttribute('data-theme') || 'dark';
        const next = current === 'dark' ? 'light' : 'dark';
        html.setAttribute('data-theme', next);
        this.state.theme = next;
    }
    
    clearSession() {
        this.state.actions = [];
        this.state.events = [];
        this.state.modelRequests = [];
        this.state.files = {};
        this.state.todos = [];
        this.state.tests = [];
        this.state.totalInputTokens = 0;
        this.state.totalOutputTokens = 0;
        this.state.selectedFile = null;
        this.clearUI();
        this.updateTokenDisplay();
        this.showToast('Session cleared', 'info');
    }
    
    clearTests() {
        this.state.tests = [];
        this.renderTests();
        this.updateTestSummaryCounts();
        this.showToast('Test results cleared', 'info');
    }
    
    startSessionTimer() {
        this.sessionTimer = setInterval(() => {
            if (this.state.sessionActive && this.state.sessionStartTime) {
                const elapsed = Math.floor((Date.now() - this.state.sessionStartTime.getTime()) / 1000);
                const mins = Math.floor(elapsed / 60).toString().padStart(2, '0');
                const secs = (elapsed % 60).toString().padStart(2, '0');
                this.elements.sessionTime.textContent = `${mins}:${secs}`;
            }
        }, 1000);
    }
    
    // =========================================================================
    // UTILITIES
    // =========================================================================
    
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        
        this.elements.toastContainer.appendChild(toast);
        
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(20px)';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
    
    formatTime(timestamp) {
        if (!timestamp) return '';
        const date = new Date(timestamp);
        return date.toLocaleTimeString('en-US', { 
            hour12: false, 
            hour: '2-digit', 
            minute: '2-digit', 
            second: '2-digit' 
        });
    }
    
    formatArgs(args) {
        if (!args || typeof args !== 'object') return '';
        return Object.entries(args)
            .map(([k, v]) => `${k}=${this.truncate(String(v), 50)}`)
            .join(', ');
    }
    
    truncate(str, len) {
        if (!str) return '';
        str = String(str);
        return str.length > len ? str.substring(0, len) + '...' : str;
    }
    
    escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
    
    getFileIcon(filename) {
        const ext = filename.split('.').pop().toLowerCase();
        const icons = {
            'py': '🐍',
            'js': '📜',
            'ts': '📘',
            'json': '📋',
            'md': '📝',
            'html': '🌐',
            'css': '🎨',
            'txt': '📄'
        };
        return icons[ext] || '📄';
    }
    
    // =========================================================================
    // EXPORT TO MARKDOWN
    // =========================================================================
    
    exportCurrentTab() {
        const activeTab = document.querySelector('.tab.active');
        if (!activeTab) return;
        
        const tabName = activeTab.dataset.tab;
        let markdown = '';
        
        switch (tabName) {
            case 'flow':
                markdown = this.exportFlowToMarkdown();
                break;
            case 'diff':
                markdown = this.exportDiffToMarkdown();
                break;
            case 'thinking':
                markdown = this.exportThinkingToMarkdown();
                break;
            case 'timeline':
                markdown = this.exportTimelineToMarkdown();
                break;
            case 'tests':
                markdown = this.exportTestsToMarkdown();
                break;
        }
        
        if (markdown) {
            this.downloadMarkdown(markdown, `visual-logger-${tabName}-${Date.now()}.md`);
            this.showToast(`Exported ${tabName} tab to markdown`, 'success');
        }
    }
    
    exportFlowToMarkdown() {
        let md = '# Process Flow\n\n';
        md += `**Session**: ${this.state.sessionStartTime ? this.state.sessionStartTime.toLocaleString() : 'N/A'}\n\n`;
        md += `**Total Actions**: ${this.state.actions.length}\n\n`;
        
        if (this.state.actions.length === 0) {
            md += '*No actions recorded yet.*\n';
            return md;
        }
        
        md += '## Action Flow\n\n';
        md += '```mermaid\n';
        md += 'graph TD\n';
        
        this.state.actions.forEach((action, idx) => {
            const nodeId = `A${idx}`;
            const label = action.name.replace(/[^\w]/g, '_');
            const style = action.success === false ? ':::error' : ':::success';
            md += `    ${nodeId}["${action.name}"]${style}\n`;
            if (idx > 0) {
                md += `    A${idx - 1} --> ${nodeId}\n`;
            }
        });
        
        md += '\n';
        md += '    classDef success fill:#00ff9f,stroke:#00d4aa,color:#000\n';
        md += '    classDef error fill:#ff6b6b,stroke:#ff5252,color:#000\n';
        md += '```\n\n';
        
        md += '## Action Details\n\n';
        this.state.actions.forEach((action, idx) => {
            md += `### ${idx + 1}. ${action.name}\n\n`;
            md += `- **Status**: ${action.success === false ? '[error] Failed' : '[success] Success'}\n`;
            md += `- **Time**: ${this.formatTime(action.timestamp)}\n`;
            md += `- **Arguments**:\n\n`;
            md += '```json\n';
            md += JSON.stringify(action.args_full || action.args, null, 2);
            md += '\n```\n\n';
            if (action.result) {
                md += `- **Result**:\n\n`;
                md += '```\n';
                md += action.result_full || action.result;
                md += '\n```\n\n';
            }
            md += '---\n\n';
        });
        
        return md;
    }
    
    exportDiffToMarkdown() {
        let md = '# File Changes\n\n';
        md += `**Session**: ${this.state.sessionStartTime ? this.state.sessionStartTime.toLocaleString() : 'N/A'}\n\n`;
        
        const files = Object.entries(this.state.files);
        
        if (files.length === 0) {
            md += '*No files modified yet.*\n';
            return md;
        }
        
        md += '## Summary\n\n';
        md += '| File | Additions | Deletions |\n';
        md += '|------|-----------|----------|\n';
        
        files.forEach(([path, data]) => {
            md += `| \`${path}\` | +${data.additions} | -${data.deletions} |\n`;
        });
        
        md += '\n---\n\n';
        
        files.forEach(([path, data]) => {
            const filename = path.split('/').pop();
            md += `## ${filename}\n\n`;
            md += `**Path**: \`${path}\`\n\n`;
            md += `**Changes**: +${data.additions} -${data.deletions}\n\n`;
            
            if (data.latestDiff && data.latestDiff.unified) {
                md += '### Diff\n\n';
                md += '```diff\n';
                md += data.latestDiff.unified;
                md += '\n```\n\n';
            }
            
            md += '---\n\n';
        });
        
        return md;
    }
    
    exportThinkingToMarkdown() {
        let md = '# Thoughts & Chat\n\n';
        md += `**Session**: ${this.state.sessionStartTime ? this.state.sessionStartTime.toLocaleString() : 'N/A'}\n\n`;
        
        const bubbles = this.elements.thinkingContainer.querySelectorAll('.thinking-bubble');
        
        if (bubbles.length === 0) {
            md += '*No thoughts or responses recorded yet.*\n';
            return md;
        }
        
        md += '## Conversation Flow\n\n';
        
        bubbles.forEach((bubble, idx) => {
            const isThought = bubble.classList.contains('agent-thought');
            const timestamp = bubble.querySelector('.thinking-timestamp').textContent;
            const content = bubble.querySelector('.thinking-content').textContent;
            
            if (isThought) {
                md += `### 💭 Agent Thought (${timestamp})\n\n`;
            } else {
                md += `### 🤖 Model Response (${timestamp})\n\n`;
            }
            
            md += `${content}\n\n`;
            md += '---\n\n';
        });
        
        return md;
    }
    
    exportTimelineToMarkdown() {
        let md = '# Timeline\n\n';
        md += `**Session**: ${this.state.sessionStartTime ? this.state.sessionStartTime.toLocaleString() : 'N/A'}\n\n`;
        
        if (this.state.actions.length === 0) {
            md += '*No actions recorded yet.*\n';
            return md;
        }
        
        md += '## Chronological Events\n\n';
        
        this.state.actions.forEach((action, idx) => {
            const time = this.formatTime(action.timestamp);
            const status = action.success === false ? '[error]' : '[success]';
            
            md += `### ${time} - ${status} ${action.name}\n\n`;
            
            if (Object.keys(action.args || {}).length > 0) {
                md += '**Parameters**: ';
                const params = Object.entries(action.args)
                    .map(([k, v]) => `${k}=${this.truncate(String(v), 50)}`)
                    .join(', ');
                md += `\`${params}\`\n\n`;
            }
            
            if (action.result) {
                md += '**Result**: ';
                md += `\`${this.truncate(action.result, 100)}\`\n\n`;
            }
            
            if (idx < this.state.actions.length - 1) {
                md += '↓\n\n';
            }
        });
        
        md += '\n---\n\n';
        md += `**Total Actions**: ${this.state.actions.length}\n`;
        md += `**Session Duration**: ${this.elements.sessionTime.textContent}\n`;
        
        return md;
    }
    
    exportTestsToMarkdown() {
        let md = '# Test Results\n\n';
        md += `**Session**: ${this.state.sessionStartTime ? this.state.sessionStartTime.toLocaleString() : 'N/A'}\n\n`;
        
        if (this.state.tests.length === 0) {
            md += '*No tests recorded.*\n';
            return md;
        }
        
        const passed = this.state.tests.filter(t => t.status !== 'failed').length;
        const failed = this.state.tests.filter(t => t.status === 'failed').length;
        
        md += `**Total**: ${this.state.tests.length} | **Passed**: ${passed} | **Failed**: ${failed}\n\n`;
        md += '---\n\n';
        
        this.state.tests.forEach((test) => {
            const status = test.status === 'failed' ? '[error]' : '[success]';
            md += `### ${status} ${test.test_name}\n`;
            md += `**File**: \`${test.source_file}\`\n\n`;
            if (test.status === 'failed') {
               md += `**Error**: \n\`\`\`\n${test.error_msg}\n\`\`\`\n\n`;
               md += `**Traceback**: \n\`\`\`\n${test.traceback}\n\`\`\`\n\n`;
            }
            md += '---\n\n';
        });
        return md;
    }
    
    downloadMarkdown(content, filename) {
        const blob = new Blob([content], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
    
    // =========================================================================
    // TESTS TAB HANDLING
    // =========================================================================
    
    handleTestResult(data) {
        this.state.tests.push(data);
        this.renderTests();
        this.updateTestSummaryCounts();
        this.notifyTab('tests');
        
        // Show immediate toast for failures
        if (data.status === 'failed') {
            this.showToast(`Test Failed: ${data.test_name}`, 'error');
        }
    }
    
    handleTestSummary(data) {
        // Update summary numbers
        const total = document.getElementById('testsTotal');
        const passed = document.getElementById('testsPassed');
        const failed = document.getElementById('testsFailed');
        const duration = document.getElementById('testsDuration');
        
        if (total) total.textContent = data.total;
        if (passed) passed.textContent = data.passed;
        if (failed) failed.textContent = data.failed;
        if (duration) duration.textContent = `${data.duration.toFixed(2)}s`;
        
        // Keep counts in sync even if some test_result events arrive before summary
        this.updateTestSummaryCounts();
    }
    
    updateTestSummaryCounts() {
        const totalEl = document.getElementById('testsTotal');
        const passedEl = document.getElementById('testsPassed');
        const failedEl = document.getElementById('testsFailed');
        if (!totalEl || !passedEl || !failedEl) return;
        
        const total = this.state.tests.length;
        const failed = this.state.tests.filter(t => t.status === 'failed').length;
        const passed = total - failed;
        
        totalEl.textContent = total;
        passedEl.textContent = passed;
        failedEl.textContent = failed;
    }
    
    renderTests() {
        const container = document.getElementById('testsContainer');
        if (!container) return;
        
        container.innerHTML = '';
        
        let filtered = this.state.tests;

        // Deduplicate if enabled: keep only the last occurrence of each (source_file, test_name)
        if (this.state.testDeduplicate) {
            const seen = new Set();
            // Iterate backwards to find the latest ones
            const unique = [];
            for (let i = filtered.length - 1; i >= 0; i--) {
                const t = filtered[i];
                const key = `${t.source_file}::${t.test_name}`;
                if (!seen.has(key)) {
                    seen.add(key);
                    unique.unshift(t);
                }
            }
            filtered = unique;
        }

        // Then filter by failures if needed
        filtered = filtered.filter(t => !this.state.testFilterFailures || t.status === 'failed');
        
        if (filtered.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <span class="empty-icon">🧪</span>
                    <span class="empty-text">${this.state.testFilterFailures ? 'No failing tests' : 'No test results available'}</span>
                    <span class="empty-subtext">${this.state.testFilterFailures ? 'Switch to all tests to view passes' : 'Run tests to see results here'}</span>
                </div>`;
            return;
        }
        
        // Sort tests: failed first, then by source file, then name
        const sorted = [...filtered].sort((a, b) => {
            if (a.status !== b.status) return a.status === 'failed' ? -1 : 1;
            if (a.source_file !== b.source_file) return a.source_file.localeCompare(b.source_file);
            return a.test_name.localeCompare(b.test_name);
        });
        
        // Group by source file
        const groups = new Map();
        sorted.forEach(test => {
            if (!groups.has(test.source_file)) groups.set(test.source_file, []);
            groups.get(test.source_file).push(test);
        });
        
        let html = '';
        groups.forEach((tests, file) => {
            const failedCount = tests.filter(t => t.status === 'failed').length;
            const passedCount = tests.length - failedCount;
            html += `
                <div class="test-file-card">
                    <div class="test-file-header" data-toggle="collapse">
                        <div>
                            <div class="file-name">${this.escapeHtml(file)}</div>
                            <div class="file-meta">${tests.length} test${tests.length !== 1 ? 's' : ''} • ${failedCount} fail • ${passedCount} pass</div>
                        </div>
                        <div class="file-badges">
                            <span class="badge ${failedCount ? 'badge-fail' : 'badge-pass'}">${failedCount ? '[error]' + failedCount : '[success] All pass'}</span>
                            <span class="chevron">▾</span>
                        </div>
                    </div>
                    <div class="test-list">
                        ${tests.map(test => {
                            const isFailed = test.status === 'failed';
                            const duration = test.duration ? `${test.duration.toFixed(3)}s` : '';
                            const error = isFailed ? this.escapeHtml(test.error_msg || 'Failure') : '';
                            const traceback = isFailed ? this.escapeHtml(test.traceback || '') : '';
                            return `
                                <div class="test-item ${isFailed ? 'failed' : 'passed'}">
                                    <div class="test-item-top">
                                        <span class="test-icon">${isFailed ? '[error]' : '[success]'}</span>
                                        <span class="test-name">${this.escapeHtml(test.test_name)}</span>
                                        <span class="test-duration">${duration}</span>
                                    </div>
                                    ${isFailed ? `
                                        <div class="test-error">${error}</div>
                                        <details class="test-trace">
                                            <summary>Traceback</summary>
                                            <pre>${traceback}</pre>
                                        </details>
                                    ` : ''}
                                </div>
                            `;
                        }).join('')}
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
        
        // Wire up collapsible behavior
        container.querySelectorAll('.test-file-header').forEach(header => {
            header.addEventListener('click', () => {
                const card = header.closest('.test-file-card');
                card.classList.toggle('collapsed');
            });
        });
    }

}

// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
    window.visualLogger = new VisualLogger();
});
