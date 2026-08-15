/**
 * Daily API Key Usage Tracker Engine for Textline Dashboard.
 */

const USAGE_STORAGE_KEY = 'textline_usage_v1';
const DEFAULT_DAILY_LIMIT = 100;

let usageState = {
    version: 1,
    daily_limit: DEFAULT_DAILY_LIMIT,
    key_limits: {},
    days: {},
    processed_event_ids: {}
};

let lastUsedMeta = {
    key_id: '',
    time: ''
};

function loadUsageData() {
    try {
        const raw = localStorage.getItem(USAGE_STORAGE_KEY);
        if (raw) {
            const parsed = JSON.parse(raw);
            if (parsed && typeof parsed === 'object') {
                usageState.version = parsed.version || 1;
                usageState.daily_limit = parsed.daily_limit || DEFAULT_DAILY_LIMIT;
                usageState.key_limits = parsed.key_limits || {};
                usageState.days = parsed.days || {};
                usageState.processed_event_ids = parsed.processed_event_ids || {};
            }
        }
        const badge = document.getElementById('usage-persistence-status');
        if (badge) {
            badge.textContent = 'localStorage persistent';
            badge.className = 'usage-persistence-badge';
        }
    } catch (e) {
        console.warn('localStorage access failed. Using session memory.', e);
        const badge = document.getElementById('usage-persistence-status');
        if (badge) {
            badge.textContent = 'Persistence unavailable';
            badge.style.color = '#fbbf24';
            badge.style.borderColor = 'rgba(245, 158, 11, 0.4)';
        }
    }
}

function saveUsageData() {
    try {
        localStorage.setItem(USAGE_STORAGE_KEY, JSON.stringify(usageState));
    } catch (e) {
        console.warn('Failed to save usage data to localStorage:', e);
    }
}

function getLocalDateString(d = new Date()) {
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

function recordGenerationUsage(metadata, timeStr) {
    if (!metadata || !metadata.key_id) return;
    const keyId = metadata.key_id;

    const genId = metadata.generation_id || `gen_${Date.now()}_${keyId}`;
    if (usageState.processed_event_ids[genId]) {
        console.log("Duplicate generation event skipped:", genId);
        return;
    }
    
    usageState.processed_event_ids[genId] = Date.now();

    const todayStr = getLocalDateString();
    if (!usageState.days[todayStr]) {
        usageState.days[todayStr] = {};
    }
    if (!usageState.days[todayStr][keyId]) {
        usageState.days[todayStr][keyId] = {
            used: 0,
            last_used: '',
            model: metadata.model || 'gemini-2.5-flash'
        };
    }

    usageState.days[todayStr][keyId].used = (usageState.days[todayStr][keyId].used || 0) + 1;
    usageState.days[todayStr][keyId].last_used = timeStr || new Date().toLocaleTimeString();
    usageState.days[todayStr][keyId].model = metadata.model || usageState.days[todayStr][keyId].model;

    lastUsedMeta = {
        key_id: keyId,
        time: usageState.days[todayStr][keyId].last_used
    };

    saveUsageData();
    renderUsageTracker();
}

function renderUsageTracker() {
    const dateSelect = document.getElementById('usage-date-select');
    const container = document.getElementById('usage-tracker-container');
    if (!container) return;

    const todayStr = getLocalDateString();
    
    const allDates = Object.keys(usageState.days || {});
    if (!allDates.includes(todayStr)) {
        allDates.push(todayStr);
    }
    allDates.sort().reverse();

    const selectedDate = (dateSelect && dateSelect.value) ? dateSelect.value : todayStr;
    
    if (dateSelect) {
        const currentOptCount = dateSelect.options.length;
        if (currentOptCount !== allDates.length) {
            dateSelect.innerHTML = '';
            allDates.forEach(dStr => {
                const opt = document.createElement('option');
                opt.value = dStr;
                opt.textContent = dStr === todayStr ? `Today (${dStr})` : dStr;
                dateSelect.appendChild(opt);
            });
            dateSelect.value = selectedDate;
        }
    }

    const dayData = (usageState.days && usageState.days[selectedDate]) || {};

    const activeKeysMap = window.discoveredKeysMap || {
        "1_textline_gemini_9838_AlReasoningValidationSystem": "gemini-2.5-flash",
        "2_textline_gemini_9838_AcademicUniverseService": "gemini-2.5-flash"
    };

    const keysToDisplay = new Set([
        ...Object.keys(activeKeysMap),
        ...Object.keys(dayData)
    ]);

    container.innerHTML = '';

    if (keysToDisplay.size === 0) {
        container.innerHTML = '<div class="placeholder-text" style="text-align:left;">No configured Gemini keys found.</div>';
        return;
    }

    keysToDisplay.forEach(keyId => {
        const keyInfo = dayData[keyId] || { used: 0, last_used: '', model: activeKeysMap[keyId] || 'gemini-2.5-flash' };
        const usedCount = keyInfo.used || 0;
        const keyLimit = (usageState.key_limits && usageState.key_limits[keyId]) || usageState.daily_limit || DEFAULT_DAILY_LIMIT;
        const remaining = Math.max(keyLimit - usedCount, 0);
        const percent = Math.min(Math.round((usedCount / keyLimit) * 100), 100);

        const healthState = (window.latestHealthStatus && window.latestHealthStatus[keyId]) || { status: 'WORKING', model: keyInfo.model };
        const statusBadgeClass = (healthState.status || 'WORKING').toLowerCase();

        const isLastUsed = (lastUsedMeta.key_id === keyId && selectedDate === todayStr);

        const card = document.createElement('div');
        card.className = 'usage-key-card';

        card.innerHTML = `
            <div class="usage-key-header">
                <div class="usage-key-title">
                    <span class="usage-key-id">${escapeHtml(keyId)}</span>
                    <span class="badge-status ${statusBadgeClass}">${escapeHtml(healthState.status || 'WORKING')}</span>
                    ${isLastUsed ? `<span class="usage-last-used-tag">● LAST USED: ${escapeHtml(lastUsedMeta.time || keyInfo.last_used)}</span>` : ''}
                </div>
                <div class="usage-key-sub">
                    Model: <b class="model-highlight">${escapeHtml(keyInfo.model || healthState.model || 'gemini-2.5-flash')}</b>
                </div>
            </div>
            <div class="usage-key-body">
                <div class="usage-metrics-row">
                    <div>Used Today: <b>${usedCount} / ${keyLimit}</b></div>
                    <div>Remaining (configured limit): <b class="remaining-highlight">${remaining}</b></div>
                </div>
                <div class="usage-progress-bg" style="margin-top: 0.5rem; margin-bottom: 0.25rem;">
                    <div class="usage-progress-fill ${percent >= 80 ? 'high' : ''}" style="width: ${percent}%;"></div>
                </div>
                <div class="usage-progress-footer">
                    <span>${percent}% Used</span>
                    <span>${keyInfo.last_used ? 'Last activity: ' + escapeHtml(keyInfo.last_used) : 'No activity today'}</span>
                </div>
            </div>
        `;

        container.appendChild(card);
    });
}

function configureDailyLimit() {
    const currentLimit = usageState.daily_limit || DEFAULT_DAILY_LIMIT;
    const input = prompt(`Configure default Daily Limit per key:`, currentLimit);
    if (input !== null) {
        const val = parseInt(input.trim(), 10);
        if (!isNaN(val) && val > 0) {
            usageState.daily_limit = val;
            saveUsageData();
            renderUsageTracker();
            alert(`Daily limit set to ${val} requests/day per key.`);
        } else if (input.trim() !== "") {
            alert(`Invalid limit. Please enter a positive number.`);
        }
    }
}

// Initialize Usage Tracker on Script Load
loadUsageData();
renderUsageTracker();
