/**
 * Monitor State Persistence & Restoration for Textline Dashboard.
 * Restores the latest Monitor session state from sessionStorage
 * when the user navigates back to /monitor after visiting another page.
 */

const MONITOR_STATE_KEY = 'textline_monitor_state_v1';

function restoreMonitorState() {
    try {
        const raw = sessionStorage.getItem(MONITOR_STATE_KEY);
        if (!raw) return;

        const state = JSON.parse(raw);
        if (!state || typeof state !== 'object') return;

        // Restore screenshot preview
        if (state.imageUrl) {
            const imgEl = document.getElementById('preview-image');
            const emptyEl = document.getElementById('empty-preview');
            if (imgEl) {
                imgEl.src = state.imageUrl;
                imgEl.style.display = 'block';
            }
            if (emptyEl) emptyEl.style.display = 'none';
        }

        // Restore answer text
        if (state.answer) {
            const ansEl = document.getElementById('answer-text');
            const emptyAns = document.getElementById('empty-answer');
            const copyEl = document.getElementById('copy-btn');
            if (ansEl) {
                ansEl.textContent = state.answer;
                ansEl.style.display = 'block';
            }
            if (emptyAns) emptyAns.style.display = 'none';
            if (copyEl) copyEl.style.display = 'inline-flex';
        }

        // Restore status badge
        if (state.status) {
            const badge = document.getElementById('status-badge');
            if (badge) {
                badge.textContent = state.status.toUpperCase();
                badge.className = `status-badge ${state.status}`;
            }
        }

        // Restore status message
        if (state.message) {
            const msgEl = document.getElementById('status-message');
            if (msgEl) msgEl.textContent = state.message;
        }

        // Restore timestamp
        if (state.timestamp) {
            const tsEl = document.getElementById('timestamp');
            if (tsEl) tsEl.textContent = state.timestamp;
        }

        // Restore active route display
        if (state.activeRouteStr) {
            const routeEl = document.getElementById('active-route-display');
            if (routeEl) {
                routeEl.textContent = state.activeRouteStr;
                routeEl.style.color = state.activeRouteColor || '#34d399';
            }
            window.lastSuccessfulRouteStr = state.activeRouteStr;
        }

        // Restore provenance tag
        if (state.provenanceTag) {
            const provTag = document.getElementById('status-provenance-tag');
            if (provTag) {
                provTag.textContent = state.provenanceTag;
                provTag.style.display = 'inline-flex';
            }
        }

        // Restore provenance panel
        const meta = state.metadata;
        if (meta && state.status === 'success') {
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
            if (provAttemptsEl) provAttemptsEl.textContent = meta.attempt_count || 1;
            if (provContainer) provContainer.style.display = 'flex';
        }

        // Restore pipeline logs
        if (Array.isArray(state.pipelineLogs) && state.pipelineLogs.length > 0) {
            const consoleEl = document.getElementById('pipeline-log-console');
            if (consoleEl) {
                consoleEl.innerHTML = '';
                state.pipelineLogs.forEach(log => {
                    const entry = document.createElement('div');
                    const levelClass = (log.level || 'info').toLowerCase();
                    entry.className = `pipeline-log-entry ${levelClass}`;

                    let symbol = '✓';
                    if (log.level === 'RUNNING') symbol = '→';
                    else if (log.level === 'WARNING') symbol = '⚠';
                    else if (log.level === 'ERROR') symbol = '✗';
                    else if (log.level === 'INFO') symbol = 'ℹ';

                    const stageStr = log.stage ? `[${log.stage}]` : '';
                    entry.innerHTML = `
                        <span class="log-ts">[${escapeHtml(log.timestamp || '')}]</span>
                        <span class="log-sym">${symbol}</span>
                        <span class="log-stage">${stageStr}</span>
                        <span class="log-msg">${escapeHtml(log.message || '')}</span>
                    `;
                    consoleEl.appendChild(entry);
                });
                consoleEl.scrollTop = consoleEl.scrollHeight;
            }
        }

        // Restore pipeline ID badge
        if (state.pipelineId) {
            const badgeEl = document.getElementById('pipeline-id-badge');
            if (badgeEl) badgeEl.textContent = `ID: ${state.pipelineId}`;
        }

        // Restore pipeline summary banner
        if (state.pipelineSummary && state.pipelineSummary.visible) {
            const bannerEl = document.getElementById('pipeline-summary-banner');
            const summaryTextEl = document.getElementById('pipeline-summary-text');
            if (bannerEl && summaryTextEl) {
                bannerEl.style.display = 'block';
                bannerEl.className = state.pipelineSummary.className || 'pipeline-summary-banner success';
                summaryTextEl.textContent = state.pipelineSummary.text || '';
            }
        }

    } catch (e) {
        console.warn('[MonitorRestore] Failed to restore monitor state:', e);
    }
}

// Restore on script load (only runs on /monitor since loaded via index.html block)
restoreMonitorState();
