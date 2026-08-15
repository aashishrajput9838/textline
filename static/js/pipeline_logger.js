/**
 * Screenshot Pipeline Log Console Controller for Textline Dashboard.
 */

const MAX_PIPELINE_LOGS = 400;
let currentPipelineId = null;

function handlePipelineLogEvent(data) {
    console.log('[PIPELINE LOG HANDLER FIRED]', data);
    const consoleEl = document.getElementById('pipeline-log-console');
    const badgeEl = document.getElementById('pipeline-id-badge');
    const bannerEl = document.getElementById('pipeline-summary-banner');
    const summaryTextEl = document.getElementById('pipeline-summary-text');
    
    if (!consoleEl) return;

    if (data.pipeline_id && data.pipeline_id !== currentPipelineId) {
        currentPipelineId = data.pipeline_id;
        if (badgeEl) badgeEl.textContent = `ID: ${currentPipelineId}`;
        if (bannerEl) bannerEl.style.display = 'none';
    }

    const entry = document.createElement('div');
    const levelClass = (data.level || 'info').toLowerCase();
    entry.className = `pipeline-log-entry ${levelClass}`;

    let symbol = '✓';
    if (data.level === 'RUNNING') symbol = '→';
    else if (data.level === 'WARNING') symbol = '⚠';
    else if (data.level === 'ERROR') symbol = '✗';
    else if (data.level === 'INFO') symbol = 'ℹ';

    const ts = data.timestamp || new Date().toLocaleTimeString();
    const stageStr = data.stage ? `[${data.stage}]` : '';

    entry.innerHTML = `
        <span class="log-ts">[${ts}]</span>
        <span class="log-sym">${symbol}</span>
        <span class="log-stage">${stageStr}</span>
        <span class="log-msg">${escapeHtml(data.message || '')}</span>
    `;

    consoleEl.appendChild(entry);

    // Cap maximum log entries in DOM (keep latest MAX_PIPELINE_LOGS)
    while (consoleEl.children.length > MAX_PIPELINE_LOGS) {
        consoleEl.removeChild(consoleEl.firstChild);
    }

    // Auto-scroll to bottom
    consoleEl.scrollTop = consoleEl.scrollHeight;

    // Update Summary Banner on PIPELINE_COMPLETE
    if (data.stage === 'PIPELINE_COMPLETE' && bannerEl && summaryTextEl) {
        bannerEl.style.display = 'block';
        const isErr = data.level === 'ERROR' || !!data.error_code;
        bannerEl.className = isErr ? 'pipeline-summary-banner error' : 'pipeline-summary-banner success';
        const statusStr = isErr ? 'ERROR' : 'SUCCESS';
        const errCodeStr = data.error_code ? ` | ERROR CODE: ${data.error_code}` : '';
        const timeStr = data.elapsed_ms ? ` | TOTAL TIME: ${data.elapsed_ms} ms` : '';
        summaryTextEl.textContent = `FINAL STATUS: ${statusStr}${errCodeStr}${timeStr}`;
    }
}

function clearPipelineLogs() {
    const consoleEl = document.getElementById('pipeline-log-console');
    const bannerEl = document.getElementById('pipeline-summary-banner');
    const badgeEl = document.getElementById('pipeline-id-badge');
    if (consoleEl) {
        consoleEl.innerHTML = `
            <div class="pipeline-log-entry info">
                <span class="log-ts">[${new Date().toLocaleTimeString()}]</span>
                <span class="log-sym">ℹ</span>
                <span class="log-stage">[CLEARED]</span>
                <span class="log-msg">Logs cleared by user. Waiting for next screenshot detection...</span>
            </div>
        `;
    }
    if (bannerEl) bannerEl.style.display = 'none';
    if (badgeEl) badgeEl.textContent = 'ID: NONE';
    currentPipelineId = null;
}

function togglePipelineLogConsole() {
    const consoleEl = document.getElementById('pipeline-log-console');
    const toggleBtn = document.getElementById('toggle-pipeline-log-btn');
    if (!consoleEl || !toggleBtn) return;

    if (consoleEl.style.display === 'none') {
        consoleEl.style.display = 'block';
        toggleBtn.innerHTML = '▼ Collapse';
        consoleEl.scrollTop = consoleEl.scrollHeight;
    } else {
        consoleEl.style.display = 'none';
        toggleBtn.innerHTML = '▶ Expand';
    }
}

