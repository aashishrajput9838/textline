/**
 * API Key Diagnostic & Health Matrix Monitor for Textline Dashboard.
 */

function runKeyHealthCheck() {
    const btn = document.getElementById('test-all-keys-btn');
    const placeholder = document.getElementById('key-health-placeholder');
    const loading = document.getElementById('key-health-loading');
    const wrapper = document.getElementById('key-health-table-wrapper');

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<div class="spinner" style="width:14px;height:14px;border-width:2px;"></div> Testing...';
    }
    
    if (placeholder) placeholder.style.display = 'none';
    if (loading) loading.style.display = 'flex';
    if (wrapper) wrapper.style.display = 'none';

    // Trigger diagnostic scan via WebSocket
    if (typeof socket !== 'undefined') {
        socket.emit('run_key_health_check');
    }
}

function handleKeyHealthProgress(data) {
    const statusText = document.getElementById('key-health-status-text');
    if (statusText && data.message) {
        statusText.textContent = data.message;
    }
}

function handleKeyHealthResults(data) {
    const btn = document.getElementById('test-all-keys-btn');
    const loading = document.getElementById('key-health-loading');
    const wrapper = document.getElementById('key-health-table-wrapper');
    const tbody = document.getElementById('key-health-tbody');
    const summaryBar = document.getElementById('key-health-summary');

    if (btn) {
        btn.disabled = false;
        btn.innerHTML = '🧪 Test All API Keys';
    }
    if (loading) loading.style.display = 'none';
    if (wrapper) wrapper.style.display = 'block';

    if (tbody) tbody.innerHTML = '';
    
    window.discoveredKeysMap = window.discoveredKeysMap || {};
    window.latestHealthStatus = window.latestHealthStatus || {};

    if (data.results && data.results.length > 0) {
        // Calculate dynamic summary counts with accurate classification
        let totalChecks = data.results.length;
        let workingCount = 0;
        let quotaCount = 0;
        let modelUnavailableCount = 0;
        let serviceUnavailableCount = 0;
        let otherErrorCount = 0;

        data.results.forEach(item => {
            const st = (item.status || '').toUpperCase();
            if (st === 'WORKING') workingCount++;
            else if (st === 'QUOTA_EXHAUSTED') quotaCount++;
            else if (st === 'MODEL_UNAVAILABLE' || st === 'UNAVAILABLE') modelUnavailableCount++;
            else if (st === 'SERVICE_UNAVAILABLE') serviceUnavailableCount++;
            else otherErrorCount++;

            window.discoveredKeysMap[item.key_id] = item.model;
            // Record model-specific health states per key
            window.latestHealthStatus[item.key_id] = window.latestHealthStatus[item.key_id] || {};
            window.latestHealthStatus[item.key_id][item.model] = { status: item.status, http_code: item.http_code };
        });

        // Render Summary Bar with precise breakdown
        if (summaryBar) {
            summaryBar.style.display = 'flex';
            let pillsHtml = `<span class="summary-pill total">${totalChecks} Checks</span> · <span class="summary-pill working">${workingCount} Working</span>`;
            if (quotaCount > 0) {
                pillsHtml += ` · <span class="summary-pill quota">${quotaCount} Quota Exhausted</span>`;
            }
            if (modelUnavailableCount > 0) {
                pillsHtml += ` · <span class="summary-pill unavailable">${modelUnavailableCount} Model Unavailable</span>`;
            }
            if (serviceUnavailableCount > 0) {
                pillsHtml += ` · <span class="summary-pill unavailable" style="background:rgba(245,158,11,0.2);color:#fbbf24;border:1px solid rgba(245,158,11,0.4);">${serviceUnavailableCount} Service Unavailable</span>`;
            }
            if (otherErrorCount > 0) {
                pillsHtml += ` · <span class="summary-pill unavailable" style="background:rgba(239,68,68,0.25);color:#f87171;border:1px solid rgba(239,68,68,0.4);">${otherErrorCount} Service/Key Error</span>`;
            }
            summaryBar.innerHTML = pillsHtml;
        }


        // Group rows by key_id
        const grouped = {};
        data.results.forEach(item => {
            if (!grouped[item.key_id]) grouped[item.key_id] = [];
            grouped[item.key_id].push(item);
        });

        Object.keys(grouped).forEach(keyId => {
            const items = grouped[keyId];
            const shortKeyId = keyId.length > 28 ? keyId.substring(0, 26) + '...' : keyId;

            // Render Key Header Row
            const headerTr = document.createElement('tr');
            headerTr.className = 'key-group-row';
            headerTr.innerHTML = `
                <td colspan="5" title="${escapeHtml(keyId)}">
                    🔑 Key: <span style="font-family:'JetBrains Mono',monospace;">${escapeHtml(shortKeyId)}</span>
                </td>
            `;
            if (tbody) tbody.appendChild(headerTr);

            // Render Model Rows under this Key
            items.forEach(item => {
                const tr = document.createElement('tr');
                const statusClass = (item.status || 'error').toLowerCase();
                
                tr.innerHTML = `
                    <td class="key-id-cell" style="padding-left: 1.5rem; color: #475569;">
                        └
                    </td>
                    <td><b style="font-family:'JetBrains Mono',monospace; color:#60a5fa;">${escapeHtml(item.model)}</b></td>
                    <td><span class="badge-status ${statusClass}">${escapeHtml(item.status)}</span></td>
                    <td>${item.latency_ms}ms</td>
                    <td>${escapeHtml(item.details)}</td>
                `;
                if (tbody) tbody.appendChild(tr);
            });
        });
    }

    if (typeof renderUsageTracker === 'function') {
        renderUsageTracker();
    }
}

