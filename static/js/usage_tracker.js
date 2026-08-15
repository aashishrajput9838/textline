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

                // Backward-compatible migration for model-wise usage tracking
                Object.keys(usageState.days).forEach(dateStr => {
                    const dayObj = usageState.days[dateStr];
                    if (dayObj && typeof dayObj === 'object') {
                        Object.keys(dayObj).forEach(keyId => {
                            const kData = dayObj[keyId];
                            if (kData && typeof kData === 'object') {
                                if (!kData.models || typeof kData.models !== 'object') {
                                    kData.models = {};
                                    if (kData.used > 0 && kData.model) {
                                        kData.models[kData.model] = kData.used;
                                    }
                                }
                            }
                        });
                    }
                });
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
    const modelName = metadata.model || 'gemini-2.5-flash';

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
            model: modelName,
            models: {}
        };
    }

    const keyData = usageState.days[todayStr][keyId];
    keyData.used = (keyData.used || 0) + 1;
    keyData.last_used = timeStr || new Date().toLocaleTimeString();
    keyData.model = modelName;

    if (!keyData.models || typeof keyData.models !== 'object') {
        keyData.models = {};
    }
    keyData.models[modelName] = (keyData.models[modelName] || 0) + 1;

    lastUsedMeta = {
        key_id: keyId,
        time: keyData.last_used
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

    const defaultModels = ['gemini-flash-latest', 'gemini-2.5-flash', 'gemini-flash-lite-latest'];

    keysToDisplay.forEach(keyId => {
        const keyInfo = dayData[keyId] || { used: 0, last_used: '', model: '', models: {} };
        const usedCount = keyInfo.used || 0;
        const keyLimit = (usageState.key_limits && usageState.key_limits[keyId]) || usageState.daily_limit || DEFAULT_DAILY_LIMIT;
        const remaining = Math.max(keyLimit - usedCount, 0);
        const percent = Math.min(Math.round((usedCount / keyLimit) * 100), 100);

        // Derive Last Active Model strictly from actual request execution provenance (not health matrix)
        const lastActiveModel = keyInfo.model || (usageState.key_last_models && usageState.key_last_models[keyId]) || 'gemini-flash-latest';

        const isLastUsed = (lastUsedMeta.key_id === keyId && selectedDate === todayStr);

        const card = document.createElement('div');
        card.className = 'usage-key-card';

        const shortKeyId = keyId.length > 32 ? keyId.substring(0, 30) + '...' : keyId;

        // Model-wise breakdown row generation
        const modelsMap = keyInfo.models || {};
        const modelSet = new Set([...defaultModels, ...Object.keys(modelsMap)]);
        const modelsToDisplay = Array.from(modelSet);

        let modelRowsHtml = '';
        modelsToDisplay.forEach(modelName => {
            const reqCount = modelsMap[modelName] || 0;
            const pctNum = usedCount > 0 ? (reqCount / usedCount) * 100 : 0;
            const pctStr = usedCount > 0 ? (pctNum % 1 === 0 ? pctNum.toFixed(0) + '%' : pctNum.toFixed(1) + '%') : '0%';

            modelRowsHtml += `
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.03);">
                    <td style="padding: 6px 8px; font-family: 'JetBrains Mono', monospace; color: #60a5fa; font-size: 11px;">
                        ${escapeHtml(modelName)}
                    </td>
                    <td style="padding: 6px 8px; text-align: center; font-weight: 700; color: #f1f5f9; font-size: 11px;">
                        ${reqCount}
                    </td>
                    <td style="padding: 6px 8px; text-align: right; font-size: 11px; color: #94a3b8;">
                        <div style="display: flex; align-items: center; justify-content: flex-end; gap: 8px;">
                            <span>${pctStr}</span>
                            <div style="width: 44px; height: 4px; background: rgba(255,255,255,0.08); border-radius: 2px; overflow: hidden; flex-shrink: 0;">
                                <div style="width: ${pctNum}%; height: 100%; background: linear-gradient(90deg, #6366f1, #818cf8);"></div>
                            </div>
                        </div>
                    </td>
                </tr>
            `;
        });

        card.innerHTML = `
            <div class="usage-key-header">
                <div class="usage-key-title">
                    🔑 <span class="usage-key-id" title="${escapeHtml(keyId)}">${escapeHtml(shortKeyId)}</span>
                    ${isLastUsed ? `<span class="usage-last-used-tag" style="margin-left:8px; font-size:10px; color:#34d399; font-weight:700;">● LAST ACTIVE: ${escapeHtml(lastUsedMeta.time || keyInfo.last_used)}</span>` : ''}
                </div>
                <div class="usage-key-sub" style="font-size: 11px; color: #64748b;">
                    Last Active Model: <b class="model-highlight" style="color: #cbd5e1;">${escapeHtml(lastActiveModel)}</b>
                </div>
            </div>
            <div class="usage-key-body" style="display:flex; flex-direction:column; gap:8px;">
                <div class="usage-metrics-row" style="display:flex; justify-content:space-between; font-size:12px; color:#cbd5e1;">
                    <div>Total Usage: <b>${usedCount} / ${keyLimit}</b></div>
                    <div>Remaining: <b class="remaining-highlight" style="color:#34d399;">${remaining}</b></div>
                </div>
                <div class="usage-progress-bg" style="margin-top: 0.25rem; margin-bottom: 0.25rem;">
                    <div class="usage-progress-fill ${percent >= 80 ? 'high' : ''}" style="width: ${percent}%;"></div>
                </div>
                <div class="usage-progress-footer" style="display:flex; justify-content:space-between; font-size:11px; color:#64748b; margin-bottom: 0.5rem;">
                    <span>${percent}% Used</span>
                    <span>${keyInfo.last_used ? 'Last activity: ' + escapeHtml(keyInfo.last_used) : 'No activity today'}</span>
                </div>

                <div style="background: rgba(0,0,0,0.25); border: 1px solid #141b2a; border-radius: 6px; padding: 10px; margin-top: 4px;">
                    <div style="font-size: 10px; font-weight: 700; color: #64748b; letter-spacing: 0.05em; margin-bottom: 6px; text-transform: uppercase;">
                        MODEL USAGE BREAKDOWN
                    </div>
                    <table style="width: 100%; border-collapse: collapse; font-size: 11px;">
                        <thead>
                            <tr style="border-bottom: 1px solid #1e293b; color: #475569; text-transform: uppercase; font-size: 10px;">
                                <th style="padding: 4px 8px; text-align: left;">MODEL</th>
                                <th style="padding: 4px 8px; text-align: center;">REQUESTS</th>
                                <th style="padding: 4px 8px; text-align: right;">% OF KEY USAGE</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${modelRowsHtml}
                        </tbody>
                    </table>
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
