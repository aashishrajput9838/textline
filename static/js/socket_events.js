/**
 * Real-Time Socket.IO Connection & Event Dispatcher for Textline Dashboard.
 */

const socket = io();

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
