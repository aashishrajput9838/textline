/**
 * UI Controller and DOM Helper Utilities for Textline.
 */

// UI DOM Element References
const connectionDot = document.getElementById('connection-dot');
const connectionText = document.getElementById('connection-text');
const statusBadge = document.getElementById('status-badge');
const statusMessage = document.getElementById('status-message');
const timestampEl = document.getElementById('timestamp');

const previewImage = document.getElementById('preview-image');
const emptyPreview = document.getElementById('empty-preview');

const answerText = document.getElementById('answer-text');
const emptyAnswer = document.getElementById('empty-answer');
const copyBtn = document.getElementById('copy-btn');

const historyList = document.getElementById('history-list');
const emptyHistory = document.getElementById('empty-history');

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function copyAnswerToClipboard() {
    const text = answerText.textContent;
    if (text) {
        navigator.clipboard.writeText(text).then(() => {
            const originalText = copyBtn.innerHTML;
            copyBtn.innerHTML = '✅ Copied!';
            setTimeout(() => {
                copyBtn.innerHTML = originalText;
            }, 2000);
        }).catch(err => {
            console.error('Failed to copy: ', err);
        });
    }
}

const SESSION_HISTORY_KEY = 'textline_history_v1';

function saveSessionHistoryItem(timeStr, answerStr, provenanceStr) {
    try {
        const raw = sessionStorage.getItem(SESSION_HISTORY_KEY);
        const list = raw ? JSON.parse(raw) : [];
        list.unshift({ timeStr, answerStr, provenanceStr });
        sessionStorage.setItem(SESSION_HISTORY_KEY, JSON.stringify(list.slice(0, 50)));
    } catch (e) {
        console.warn('Failed to save session history to sessionStorage:', e);
    }
}

function loadSessionHistory() {
    const listEl = document.getElementById('history-list');
    const emptyEl = document.getElementById('empty-history');
    if (!listEl) return;

    try {
        const raw = sessionStorage.getItem(SESSION_HISTORY_KEY);
        if (raw) {
            const list = JSON.parse(raw);
            if (Array.isArray(list) && list.length > 0) {
                if (emptyEl) emptyEl.style.display = 'none';
                listEl.innerHTML = '';
                list.forEach(item => {
                    renderHistoryDOM(item.timeStr, item.answerStr, item.provenanceStr);
                });
            }
        }
    } catch (e) {
        console.warn('Failed to load session history:', e);
    }
}

function renderHistoryDOM(timeStr, answerStr, provenanceStr = '') {
    const listEl = document.getElementById('history-list');
    const emptyEl = document.getElementById('empty-history');
    if (!listEl) return;
    if (emptyEl) emptyEl.style.display = 'none';

    const item = document.createElement('div');
    item.className = 'history-item';
    
    const mainContainer = document.createElement('div');
    mainContainer.style.display = 'flex';
    mainContainer.style.flexDirection = 'column';
    mainContainer.style.gap = '0.3rem';
    mainContainer.style.width = '100%';

    if (provenanceStr) {
        const metaTag = document.createElement('div');
        metaTag.style.fontSize = '0.75rem';
        metaTag.style.color = '#818cf8';
        metaTag.style.fontWeight = '600';
        metaTag.textContent = provenanceStr;
        mainContainer.appendChild(metaTag);
    }

    const content = document.createElement('div');
    content.className = 'history-content';
    content.textContent = answerStr;
    mainContainer.appendChild(content);

    const timeEl = document.createElement('div');
    timeEl.className = 'history-time';
    timeEl.textContent = timeStr;

    item.appendChild(mainContainer);
    item.appendChild(timeEl);

    listEl.appendChild(item);
}

function addHistoryItem(timeStr, answerStr, provenanceStr = '') {
    saveSessionHistoryItem(timeStr, answerStr, provenanceStr);
    const listEl = document.getElementById('history-list');
    if (listEl) {
        const emptyEl = document.getElementById('empty-history');
        if (emptyEl) emptyEl.style.display = 'none';

        const item = document.createElement('div');
        item.className = 'history-item';

        const mainContainer = document.createElement('div');
        mainContainer.style.display = 'flex';
        mainContainer.style.flexDirection = 'column';
        mainContainer.style.gap = '0.3rem';
        mainContainer.style.width = '100%';

        if (provenanceStr) {
            const metaTag = document.createElement('div');
            metaTag.style.fontSize = '0.75rem';
            metaTag.style.color = '#818cf8';
            metaTag.style.fontWeight = '600';
            metaTag.textContent = provenanceStr;
            mainContainer.appendChild(metaTag);
        }

        const content = document.createElement('div');
        content.className = 'history-content';
        content.textContent = answerStr;
        mainContainer.appendChild(content);

        const timeEl = document.createElement('div');
        timeEl.className = 'history-time';
        timeEl.textContent = timeStr;

        item.appendChild(mainContainer);
        item.appendChild(timeEl);

        listEl.insertBefore(item, listEl.firstChild);
    }
}

/**
 * Initialize Route Navigation Active Highlight & History Loading.
 */
function initRouteNavigation() {
    const currentPath = window.location.pathname;
    const navItems = document.querySelectorAll('.nav-item');

    navItems.forEach(item => {
        const href = item.getAttribute('href');
        if (href === currentPath || (currentPath === '/' && href === '/monitor')) {
            item.classList.add('active');
        } else if (href && !href.startsWith('#')) {
            item.classList.remove('active');
        }
    });

    loadSessionHistory();
}

// Auto initialize on DOM Content Loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initRouteNavigation);
} else {
    initRouteNavigation();
}
