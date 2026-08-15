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

function addHistoryItem(timeStr, answerStr, provenanceStr = '') {
    if (emptyHistory) {
        emptyHistory.style.display = 'none';
    }

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

    if (historyList) {
        historyList.insertBefore(item, historyList.firstChild);
    }
}
