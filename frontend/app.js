/**
 * Meeting Summarizer - Frontend Client Logic
 * Handles file selection, drag-and-drop, API communication,
 * tab switching, and meeting history navigation.
 */

document.addEventListener('DOMContentLoaded', () => {
    // -----------------------------------------------------------------------
    // DOM Elements
    // -----------------------------------------------------------------------
    const systemStatusBadge = document.getElementById('systemStatusBadge');
    const systemStatusText = document.getElementById('systemStatusText');

    // Upload & Form
    const dropzone = document.getElementById('dropzone');
    const audioFileInput = document.getElementById('audioFileInput');
    const fileInfoBar = document.getElementById('fileInfoBar');
    const selectedFileName = document.getElementById('selectedFileName');
    const selectedFileSize = document.getElementById('selectedFileSize');
    const btnClearFile = document.getElementById('btnClearFile');
    const btnProcess = document.getElementById('btnProcess');
    const uploadErrorAlert = document.getElementById('uploadErrorAlert');
    const uploadErrorMessage = document.getElementById('uploadErrorMessage');

    // History
    const historyList = document.getElementById('historyList');
    const btnRefreshHistory = document.getElementById('btnRefreshHistory');

    // Display States
    const emptyWelcomeState = document.getElementById('emptyWelcomeState');
    const loadingState = document.getElementById('loadingState');
    const resultsState = document.getElementById('resultsState');
    const loadingSubtitle = document.getElementById('loadingSubtitle');

    // Results Elements
    const resMeetingIdBadge = document.getElementById('resMeetingIdBadge');
    const resMeetingFilename = document.getElementById('resMeetingFilename');
    const resMeetingTime = document.getElementById('resMeetingTime');
    const resSummaryText = document.getElementById('resSummaryText');
    const resDecisionsList = document.getElementById('resDecisionsList');
    const resActionsTableBody = document.getElementById('resActionsTableBody');
    const resTranscriptText = document.getElementById('resTranscriptText');
    const badgeDecisionsCount = document.getElementById('badgeDecisionsCount');
    const badgeActionsCount = document.getElementById('badgeActionsCount');
    const btnCopyTranscript = document.getElementById('btnCopyTranscript');

    // Tabs
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabPanels = document.querySelectorAll('.tab-panel');

    // -----------------------------------------------------------------------
    // State
    // -----------------------------------------------------------------------
    let currentSelectedFile = null;
    let activeMeetingId = null;
    let progressTimeouts = [];

    // -----------------------------------------------------------------------
    // Initialization
    // -----------------------------------------------------------------------
    checkHealth();
    loadMeetingHistory();

    // -----------------------------------------------------------------------
    // System Health Check
    // -----------------------------------------------------------------------
    async function checkHealth() {
        try {
            const res = await fetch('/health');
            if (res.ok) {
                systemStatusBadge.classList.add('online');
                systemStatusText.textContent = 'Online';
            } else {
                systemStatusText.textContent = 'Server unavailable';
            }
        } catch (err) {
            systemStatusText.textContent = 'Backend offline';
        }
    }

    // -----------------------------------------------------------------------
    // File Selection & Drag & Drop Handling
    // -----------------------------------------------------------------------
    dropzone.addEventListener('click', () => audioFileInput.click());

    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            handleFileSelection(e.dataTransfer.files[0]);
        }
    });

    audioFileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            handleFileSelection(e.target.files[0]);
        }
    });

    btnClearFile.addEventListener('click', (e) => {
        e.stopPropagation();
        clearSelectedFile();
    });

    function handleFileSelection(file) {
        hideError();
        const validExtensions = ['.wav', '.mp3', '.aac', '.ogg', '.flac'];
        const fileName = file.name.toLowerCase();
        const isValidExt = validExtensions.some(ext => fileName.endsWith(ext));

        if (!isValidExt) {
            showError(`Unsupported audio format. Please upload WAV, MP3, AAC, OGG, or FLAC.`);
            return;
        }

        const maxBytes = 20 * 1024 * 1024; // 20 MB
        if (file.size > maxBytes) {
            showError(`File exceeds maximum size of 20 MB (${(file.size / (1024 * 1024)).toFixed(2)} MB).`);
            return;
        }

        if (file.size === 0) {
            showError('Selected audio file is empty.');
            return;
        }

        currentSelectedFile = file;
        selectedFileName.textContent = file.name;
        selectedFileSize.textContent = formatBytes(file.size);
        fileInfoBar.classList.remove('hidden');
        btnProcess.disabled = false;
    }

    function clearSelectedFile() {
        currentSelectedFile = null;
        audioFileInput.value = '';
        fileInfoBar.classList.add('hidden');
        btnProcess.disabled = true;
        hideError();
    }

    function formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function showError(message) {
        uploadErrorMessage.textContent = message;
        uploadErrorAlert.classList.remove('hidden');
    }

    function hideError() {
        uploadErrorAlert.classList.add('hidden');
        uploadErrorMessage.textContent = '';
    }

    // -----------------------------------------------------------------------
    // Stage Progression Configuration & UI
    // -----------------------------------------------------------------------
    const stepConfigs = [
        { id: 'step1', label: '1. Audio Upload & Validation', msg: 'Uploading and validating audio stream...' },
        { id: 'step2', label: '2. Gemini Audio Transcription', msg: 'Transcribing speech to verbatim text...' },
        { id: 'step3', label: '3. Structured Summarization', msg: 'Extracting executive summary, decisions, and action items...' },
        { id: 'step4', label: '4. Persistence & Output', msg: 'Saving meeting record to database...' }
    ];

    /**
     * Set stage visual state:
     * - Indices < activeIndex: completed (green checkmark ✅)
     * - Index === activeIndex: active (pulsing / working ⏳)
     * - Indices > activeIndex: neutral (pending ⚪)
     * If activeIndex >= 4, all stages are marked completed ✅
     */
    function renderStageState(activeIndex) {
        stepConfigs.forEach((cfg, idx) => {
            const el = document.getElementById(cfg.id);
            if (!el) return;
            const iconEl = el.querySelector('.step-icon');
            const labelEl = el.querySelector('.step-label');

            if (idx < activeIndex) {
                el.className = 'step-item completed';
                if (iconEl) iconEl.textContent = '✅';
            } else if (idx === activeIndex) {
                el.className = 'step-item active';
                if (iconEl) iconEl.textContent = '⏳';
            } else {
                el.className = 'step-item';
                if (iconEl) iconEl.textContent = '⚪';
            }
            if (labelEl) labelEl.textContent = cfg.label;
        });

        if (activeIndex < stepConfigs.length) {
            loadingSubtitle.textContent = stepConfigs[activeIndex].msg;
        }
    }

    function startProgressSequence() {
        clearAllTimeouts();

        // Stage 1 active immediately
        renderStageState(0);

        // Stage 2 active after 2.5 seconds (Stage 1 becomes completed)
        const t1 = setTimeout(() => {
            renderStageState(1);
        }, 2500);

        // Stage 3 active after 8.0 seconds (Stage 1 & 2 become completed)
        const t2 = setTimeout(() => {
            renderStageState(2);
        }, 8000);

        // Stage 4 active after 16.0 seconds (Stage 1, 2, 3 become completed, stays here until response arrives)
        const t3 = setTimeout(() => {
            renderStageState(3);
        }, 16000);

        progressTimeouts = [t1, t2, t3];
    }

    function clearAllTimeouts() {
        progressTimeouts.forEach(t => clearTimeout(t));
        progressTimeouts = [];
    }

    // -----------------------------------------------------------------------
    // Meeting Processing (POST /process)
    // -----------------------------------------------------------------------
    btnProcess.addEventListener('click', async () => {
        if (!currentSelectedFile) return;

        hideError();
        showProcessingState();

        const formData = new FormData();
        formData.append('audio', currentSelectedFile, currentSelectedFile.name);

        try {
            const res = await fetch('/process', {
                method: 'POST',
                body: formData,
            });

            if (!res.ok) {
                const errorData = await res.json().catch(() => ({}));
                const msg = errorData.detail || `Processing failed with status ${res.status}`;
                throw new Error(msg);
            }

            const meetingData = await res.json();

            // Stop all progression timers immediately
            clearAllTimeouts();

            // Mark all 4 stages completed
            renderStageState(4);
            loadingSubtitle.textContent = 'Processing complete! Rendering results...';

            // Brief pause so user sees all green checkmarks
            await new Promise(r => setTimeout(r, 400));

            displayMeetingResults(meetingData);
            clearSelectedFile();
            loadMeetingHistory(meetingData.id);
        } catch (err) {
            hideProcessingState();
            showError(err.message || 'An error occurred during audio processing.');
        }
    });

    // -----------------------------------------------------------------------
    // UI State Management (Welcome / Loading / Results)
    // -----------------------------------------------------------------------
    function showProcessingState() {
        emptyWelcomeState.classList.add('hidden');
        resultsState.classList.add('hidden');
        loadingState.classList.remove('hidden');
        btnProcess.disabled = true;

        startProgressSequence();
    }

    function hideProcessingState() {
        clearAllTimeouts();
        loadingState.classList.add('hidden');
        if (currentSelectedFile) {
            btnProcess.disabled = false;
        }
    }

    // -----------------------------------------------------------------------
    // Render Results
    // -----------------------------------------------------------------------
    function displayMeetingResults(meeting) {
        hideProcessingState();
        emptyWelcomeState.classList.add('hidden');
        resultsState.classList.remove('hidden');

        activeMeetingId = meeting.id;

        // Meta Header
        resMeetingIdBadge.textContent = `Meeting #${meeting.id}`;
        resMeetingFilename.textContent = meeting.filename;
        resMeetingTime.textContent = `Processed on: ${formatDate(meeting.created_at)}`;

        // Executive Summary
        resSummaryText.textContent = meeting.summary || 'No summary generated.';

        // Key Decisions
        resDecisionsList.innerHTML = '';
        const decisions = meeting.decisions || [];
        badgeDecisionsCount.textContent = decisions.length;

        if (decisions.length === 0) {
            const emptyItem = document.createElement('li');
            emptyItem.textContent = 'No explicit decisions recorded in transcript.';
            emptyItem.style.borderLeftColor = 'var(--text-muted)';
            emptyItem.style.color = 'var(--text-muted)';
            resDecisionsList.appendChild(emptyItem);
        } else {
            decisions.forEach(dec => {
                const li = document.createElement('li');
                li.textContent = dec;
                resDecisionsList.appendChild(li);
            });
        }

        // Action Items Table
        resActionsTableBody.innerHTML = '';
        const actionItems = meeting.action_items || [];
        badgeActionsCount.textContent = actionItems.length;

        if (actionItems.length === 0) {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td colspan="3" style="text-align:center; color: var(--text-muted); padding: 20px;">No action items extracted.</td>`;
            resActionsTableBody.appendChild(tr);
        } else {
            actionItems.forEach(item => {
                const tr = document.createElement('tr');

                const ownerTag = (item.owner && item.owner !== 'Not specified')
                    ? `<span class="tag-owner">${escapeHtml(item.owner)}</span>`
                    : `<span class="tag-unassigned">Not specified</span>`;

                const deadlineTag = (item.deadline && item.deadline !== 'Not specified')
                    ? `<span class="tag-deadline">${escapeHtml(item.deadline)}</span>`
                    : `<span class="tag-unassigned">Not specified</span>`;

                tr.innerHTML = `
                    <td><strong>${escapeHtml(item.task)}</strong></td>
                    <td>${ownerTag}</td>
                    <td>${deadlineTag}</td>
                `;
                resActionsTableBody.appendChild(tr);
            });
        }

        // Verbatim Transcript
        resTranscriptText.textContent = meeting.transcript || 'No transcript available.';

        // Highlight active item in history list
        updateHistoryActiveState(meeting.id);
    }

    function formatDate(isoString) {
        if (!isoString) return 'Unknown date';
        try {
            const date = new Date(isoString);
            return date.toLocaleString();
        } catch {
            return isoString;
        }
    }

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // -----------------------------------------------------------------------
    // Meeting History (GET /meetings, GET /meetings/{id})
    // -----------------------------------------------------------------------
    btnRefreshHistory.addEventListener('click', () => loadMeetingHistory(activeMeetingId));

    async function loadMeetingHistory(selectedId = null) {
        try {
            const res = await fetch('/meetings');
            if (!res.ok) throw new Error('Failed to fetch meeting history.');

            const meetings = await res.json();
            renderHistoryList(meetings, selectedId);
        } catch (err) {
            historyList.innerHTML = `<div class="empty-history-state" style="color: var(--error-text);">Failed to load history.</div>`;
        }
    }

    function renderHistoryList(meetings, activeId) {
        historyList.innerHTML = '';

        if (!meetings || meetings.length === 0) {
            historyList.innerHTML = `<div class="empty-history-state">No stored meetings yet.</div>`;
            return;
        }

        meetings.forEach(m => {
            const item = document.createElement('div');
            item.className = `history-item ${m.id === activeId ? 'active' : ''}`;
            item.dataset.id = m.id;

            item.innerHTML = `
                <div class="history-item-top">
                    <span class="history-filename">${escapeHtml(m.filename)}</span>
                    <span class="history-badge">#${m.id}</span>
                </div>
                <p class="history-summary-snippet">${escapeHtml(m.summary)}</p>
                <span class="history-time">${formatDate(m.created_at)}</span>
            `;

            item.addEventListener('click', () => fetchAndDisplayMeeting(m.id));
            historyList.appendChild(item);
        });
    }

    function updateHistoryActiveState(activeId) {
        const items = historyList.querySelectorAll('.history-item');
        items.forEach(el => {
            if (parseInt(el.dataset.id, 10) === activeId) {
                el.classList.add('active');
            } else {
                el.classList.remove('active');
            }
        });
    }

    async function fetchAndDisplayMeeting(meetingId) {
        hideError();
        try {
            const res = await fetch(`/meetings/${meetingId}`);
            if (!res.ok) throw new Error(`Could not load meeting #${meetingId}`);

            const meetingData = await res.json();
            displayMeetingResults(meetingData);
        } catch (err) {
            showError(err.message);
        }
    }

    // -----------------------------------------------------------------------
    // Tab Navigation
    // -----------------------------------------------------------------------
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTabId = btn.dataset.tab;

            tabButtons.forEach(b => b.classList.remove('active'));
            tabPanels.forEach(p => {
                p.classList.add('hidden');
                p.classList.remove('active');
            });

            btn.classList.add('active');
            const activePanel = document.getElementById(targetTabId);
            if (activePanel) {
                activePanel.classList.remove('hidden');
                activePanel.classList.add('active');
            }
        });
    });

    // -----------------------------------------------------------------------
    // Copy Transcript Utility
    // -----------------------------------------------------------------------
    btnCopyTranscript.addEventListener('click', async () => {
        const text = resTranscriptText.textContent;
        if (!text) return;

        try {
            await navigator.clipboard.writeText(text);
            const originalText = btnCopyTranscript.textContent;
            btnCopyTranscript.textContent = '✅ Copied!';
            setTimeout(() => {
                btnCopyTranscript.textContent = originalText;
            }, 2000);
        } catch {
            showError('Failed to copy to clipboard.');
        }
    });
});
