/**
 * Real-Time Socket.IO Connection & Event Dispatcher for Textline Dashboard.
 */

const socket = io();

// Monitor State Persistence (sessionStorage)
const _MONITOR_STATE_KEY = 'textline_monitor_state_v1';
const _MAX_PERSISTED_LOGS = 200;

function _loadMonitorState() {
    try {
        const raw = sessionStorage.getItem(_MONITOR_STATE_KEY);
        return raw ? JSON.parse(raw) : {};
    } catch (e) { return {}; }
}

function saveMonitorState(updates) {
    try {
        const state = _loadMonitorState();
        Object.assign(state, updates);
        sessionStorage.setItem(_MONITOR_STATE_KEY, JSON.stringify(state));
    } catch (e) {
        console.warn('[MonitorState] Failed to save:', e);
    }
}

// Socket Connection Handlers
socket.on('connect', () => {
    if (connectionDot) connectionDot.className = 'status-dot online';
    if (connectionText) connectionText.textContent = 'Live Connected';
});

socket.on('disconnect', () => {
    if (connectionDot) connectionDot.className = 'status-dot offline';
    if (connectionText) connectionText.textContent = 'Disconnected';
});

// Handle Status Updates
socket.on('status_update', (data) => {
    const statusKey = data.status || 'idle';
    if (statusBadge) {
        statusBadge.textContent = statusKey.toUpperCase();
        statusBadge.className = `status-badge ${statusKey}`;
    }
    
    if (statusMessage) statusMessage.textContent = data.message || '';
    if (data.timestamp && timestampEl) {
        timestampEl.textContent = data.timestamp;
    }

    const provTagEl = document.getElementById('status-provenance-tag');

    const activeRouteEl = document.getElementById('active-route-display');

    if (statusKey === 'processing') {
        if (activeRouteEl) {
            activeRouteEl.textContent = 'Selecting active route...';
            activeRouteEl.style.color = '#60a5fa';
        }
        saveMonitorState({
            status: statusKey,
            message: data.message || '',
            timestamp: data.timestamp || '',
            pipelineId: data.pipeline_id || '',
            activeRouteStr: 'Selecting active route...',
            activeRouteColor: '#60a5fa'
        });
    } else if (statusKey === 'idle') {
        if (activeRouteEl) {
            if (window.lastSuccessfulRouteStr) {
                activeRouteEl.textContent = window.lastSuccessfulRouteStr;
                activeRouteEl.style.color = '#34d399';
            } else {
                activeRouteEl.textContent = 'None (Idle)';
                activeRouteEl.style.color = 'var(--text-muted)';
            }
        }
    } else if (statusKey === 'error') {
        if (activeRouteEl) {
            activeRouteEl.textContent = 'Execution Error (Route Failed)';
            activeRouteEl.style.color = '#f87171';
        }
        saveMonitorState({
            status: statusKey,
            message: data.message || '',
            timestamp: data.timestamp || '',
            activeRouteStr: 'Execution Error (Route Failed)',
            activeRouteColor: '#f87171'
        });
    }

    if (statusKey === 'success' && data.answer) {
        // Display Answer via textContent (SAFE FROM INJECTION)
        if (answerText) {
            answerText.textContent = data.answer;
            answerText.style.display = 'block';
        }
        if (emptyAnswer) emptyAnswer.style.display = 'none';
        if (copyBtn) copyBtn.style.display = 'inline-flex';

        // Display Generation Provenance Metadata Panel & Status Tag
        const meta = data.metadata || {
            provider: 'Google Gemini',
            model: 'gemini-flash-latest',
            key_id: '1_textline_gemini_9838_AlReasoningValidationSystem',
            is_fallback: false
        };

        console.log("PROVENANCE EVENT:", meta);

        if (activeRouteEl) {
            const shortKey = meta.key_id ? (meta.key_id.length > 25 ? meta.key_id.substring(0, 23) + '...' : meta.key_id) : 'Key';
            const fbText = meta.is_fallback ? ' ⚡ (Fallback Active)' : '';
            const routeStr = `${shortKey} → ${meta.model}${fbText}`;
            window.lastSuccessfulRouteStr = routeStr;
            activeRouteEl.textContent = routeStr;
            activeRouteEl.style.color = '#34d399';
        }

        if (provTagEl) {
            provTagEl.textContent = `${meta.provider} · ${meta.model} · ${meta.key_id}`;
            provTagEl.style.display = 'inline-flex';
        }


        const provModelEl = document.getElementById('prov-provider-model');
        const provKeyEl = document.getElementById('prov-key-id');
        const provFallbackEl = document.getElementById('prov-fallback');
        const provModelFallbackEl = document.getElementById('prov-model-fallback');
        const provKeyFallbackEl = document.getElementById('prov-key-fallback');
        const provAttemptsEl = document.getElementById('prov-attempts');
        const provContainer = document.getElementById('provenance-container');

        if (provModelEl) provModelEl.textContent = `${meta.provider} · ${meta.model}`;
        if (provKeyEl) provKeyEl.textContent = meta.key_id;
        
        if (provFallbackEl) {
            provFallbackEl.textContent = meta.is_fallback ? 'Yes' : 'No';
            provFallbackEl.className = meta.is_fallback ? 'prov-badge fallback-yes' : 'prov-badge';
        }
        if (provModelFallbackEl) {
            provModelFallbackEl.textContent = meta.model_fallback ? 'Yes' : 'No';
            provModelFallbackEl.className = meta.model_fallback ? 'prov-badge fallback-yes' : 'prov-badge';
        }
        if (provKeyFallbackEl) {
            provKeyFallbackEl.textContent = meta.key_fallback ? 'Yes' : 'No';
            provKeyFallbackEl.className = meta.key_fallback ? 'prov-badge fallback-yes' : 'prov-badge';
        }
        if (provAttemptsEl) {
            provAttemptsEl.textContent = meta.attempt_count || 1;
        }

        if (provContainer) provContainer.style.display = 'flex';

        // Persist Monitor state for cross-page restoration
        saveMonitorState({
            status: 'success',
            answer: data.answer,
            message: data.message || 'Done! Answer copied to clipboard.',
            timestamp: data.timestamp || '',
            metadata: meta,
            pipelineId: data.pipeline_id || '',
            activeRouteStr: window.lastSuccessfulRouteStr || '',
            activeRouteColor: '#34d399',
            provenanceTag: `${meta.provider} · ${meta.model} · ${meta.key_id}`
        });

        // Record Daily Key Usage
        if (typeof recordGenerationUsage === 'function') {
            recordGenerationUsage(meta, data.timestamp || new Date().toLocaleTimeString());
        }

        // Add to Session History
        const provStr = `${meta.provider} · ${meta.model} · ${meta.key_id}`;
        if (typeof addHistoryItem === 'function') {
            addHistoryItem(data.timestamp || new Date().toLocaleTimeString(), data.answer, provStr);
        }
    } else if (provTagEl && statusKey !== 'success') {
        provTagEl.style.display = 'none';
    }
});

// Handle Image Preview Emit
socket.on('image_preview', (data) => {
    if (data.image_url) {
        if (previewImage) {
            previewImage.src = data.image_url;
            previewImage.style.display = 'block';
        }
        if (emptyPreview) emptyPreview.style.display = 'none';

        // Persist image URL for Monitor state restoration
        saveMonitorState({ imageUrl: data.image_url });
    }
});

// Diagnostic: log ALL socket events to console
socket.onAny(function(eventName, ...args) {
    if (eventName === 'pipeline_log') {
        console.log('[PIPELINE LOG RECEIVED]', JSON.stringify(args[0]));
    } else {
        console.log('[SOCKET EVENT]', eventName, JSON.stringify(args).substring(0, 200));
    }
});

// Register Pipeline Log Event
socket.on('pipeline_log', (data) => {
    if (typeof handlePipelineLogEvent === 'function') {
        handlePipelineLogEvent(data);
    }

    // Persist pipeline log entry for Monitor state restoration
    try {
        const state = _loadMonitorState();
        if (!Array.isArray(state.pipelineLogs)) state.pipelineLogs = [];
        state.pipelineLogs.push({
            timestamp: data.timestamp || '',
            stage: data.stage || '',
            message: data.message || '',
            level: data.level || 'INFO'
        });
        if (state.pipelineLogs.length > _MAX_PERSISTED_LOGS) {
            state.pipelineLogs = state.pipelineLogs.slice(-_MAX_PERSISTED_LOGS);
        }
        if (data.pipeline_id) state.pipelineId = data.pipeline_id;

        // Persist pipeline summary banner on PIPELINE_COMPLETE
        if (data.stage === 'PIPELINE_COMPLETE') {
            const isErr = data.level === 'ERROR' || !!data.error_code;
            const statusStr = isErr ? 'ERROR' : 'SUCCESS';
            const errCodeStr = data.error_code ? ` | ERROR CODE: ${data.error_code}` : '';
            const timeStr = data.elapsed_ms ? ` | TOTAL TIME: ${data.elapsed_ms} ms` : '';
            state.pipelineSummary = {
                visible: true,
                className: isErr ? 'pipeline-summary-banner error' : 'pipeline-summary-banner success',
                text: `FINAL STATUS: ${statusStr}${errCodeStr}${timeStr}`
            };
        }

        sessionStorage.setItem(_MONITOR_STATE_KEY, JSON.stringify(state));
    } catch (e) { /* silent */ }
});

// Register Key Health Event Listeners
socket.on('key_health_progress', (data) => {
    if (typeof handleKeyHealthProgress === 'function') {
        handleKeyHealthProgress(data);
    }
});

socket.on('key_health_results', (data) => {
    if (typeof handleKeyHealthResults === 'function') {
        handleKeyHealthResults(data);
    }
});
