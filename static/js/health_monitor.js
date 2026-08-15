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
        data.results.forEach(item => {
            window.discoveredKeysMap[item.key_id] = item.model;
            window.latestHealthStatus[item.key_id] = { status: item.status, model: item.model };

            const tr = document.createElement('tr');
            const statusClass = (item.status || 'error').toLowerCase();
            
            tr.innerHTML = `
                <td class="key-id-cell">${escapeHtml(item.key_id)}</td>
                <td>${escapeHtml(item.model)}</td>
                <td><span class="badge-status ${statusClass}">${escapeHtml(item.status)}</span></td>
                <td>${item.latency_ms}ms</td>
                <td>${escapeHtml(item.details)}</td>
            `;
            if (tbody) tbody.appendChild(tr);
        });
    }
    if (typeof renderUsageTracker === 'function') {
        renderUsageTracker();
    }
}
