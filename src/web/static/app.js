// =============================================================================
// MBSE Generator — Frontend JavaScript
// =============================================================================

// =============================================================================
// 1. STATE MANAGEMENT
// =============================================================================

let currentModel = null;       // MBSEModel JSON from server
let currentJobId = null;       // Active job ID
let selectedMode = 'capella';  // 'capella' or 'rhapsody'
let selectedLayers = [];       // Selected layer/diagram keys
let uploadedFile = null;       // File object from upload
let parsedRequirements = [];   // Requirements from server after upload
let conversationHistory = [];  // Chat agent history
let sseSource = null;          // EventSource for SSE
let _stageTimers = {};         // Track start time per stage
let _elapsedInterval = null;   // Interval for updating elapsed time display

// Internal: pending settings during cost confirmation flow
let _pendingSettings = null;

// =============================================================================
// 2. INITIALIZATION (DOMContentLoaded)
// =============================================================================

document.addEventListener('DOMContentLoaded', function () {
    // Mode toggle
    document.querySelectorAll('#mode-toggle .segment').forEach(function (btn) {
        btn.addEventListener('click', function () {
            setMode(btn.getAttribute('data-mode'));
        });
    });

    // Layer checkboxes
    document.querySelectorAll('#capella-layers input[type=checkbox]').forEach(function (cb) {
        cb.addEventListener('change', readSelectedLayers);
    });
    document.querySelectorAll('#rhapsody-diagrams input[type=checkbox]').forEach(function (cb) {
        cb.addEventListener('change', readSelectedLayers);
    });

    // Provider selector — initialize from CURRENT_SETTINGS
    initProvider();

    // Initialize mode from CURRENT_SETTINGS
    if (CURRENT_SETTINGS && CURRENT_SETTINGS.default_mode) {
        setMode(CURRENT_SETTINGS.default_mode);
    }

    // Initialize selected layers from visible checkboxes
    readSelectedLayers();

    // Settings modal model selector change handler
    var modelSelect = document.getElementById('settings-model');
    if (modelSelect) {
        modelSelect.addEventListener('change', function () {
            showModelDetail(this.value);
        });
        if (CURRENT_SETTINGS && CURRENT_SETTINGS.model) {
            modelSelect.value = CURRENT_SETTINGS.model;
            showModelDetail(CURRENT_SETTINGS.model);
        }
    }

    // Close export menu on outside click
    document.addEventListener('click', function (e) {
        var menu = document.getElementById('export-menu');
        if (menu && menu.style.display !== 'none') {
            if (!e.target.closest('.export-dropdown')) {
                menu.style.display = 'none';
            }
        }
    });

    // Check for updates quietly on page load
    checkUpdatesQuietly();

    // Initialize chat resize + example prompts
    initChatResize();
    document.querySelectorAll('.chat-example').forEach(function(ex) {
        ex.addEventListener('click', function() {
            var input = document.getElementById('chat-input');
            if (input) {
                input.value = ex.textContent.replace(/^"|"$/g, '');
                input.focus();
            }
        });
    });

    // Project-based restore
    if (INITIAL_PROJECT && INITIAL_PROJECT.project) {
        currentModel = INITIAL_PROJECT;
        currentJobId = 'project';
        renderTree();
        renderCoverageIndicator();
        switchTab('tree');
        updateProjectUI();
    } else {
        // No project yet — show empty state
        var treeContainer = document.getElementById('tab-tree');
        if (treeContainer) {
            clearChildren(treeContainer);
            treeContainer.appendChild(el('div', {
                className: 'empty-state',
                textContent: 'No project yet. Upload requirements and add your first batch to start building a model.',
            }));
        }
    }

    // Project name editing
    document.getElementById('project-name').addEventListener('blur', async function() {
        var newName = this.textContent.trim();
        if (newName && currentModel) {
            await fetch('/project/rename', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name: newName}),
            });
        }
    });

    // New Project button
    document.getElementById('btn-new-project').addEventListener('click', async function() {
        if (currentModel && currentModel.batches && currentModel.batches.length > 0) {
            if (!confirm('This will archive the current project and start fresh. Continue?')) return;
        }
        var name = prompt('Project name:', 'Untitled Project');
        if (name === null) return;

        var res = await fetch('/project/new', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: name, mode: selectedMode}),
        });
        var data = await res.json();
        currentModel = data;
        currentJobId = 'project';
        renderTree();
        renderCoverageIndicator();
        updateProjectUI();
        unlockModeToggle();
        showToast('New project created.', 'success');
    });

    // Open Project button
    document.getElementById('btn-open-project').addEventListener('click', function() {
        document.getElementById('open-project-input').click();
    });

    document.getElementById('open-project-input').addEventListener('change', async function() {
        var file = this.files[0];
        if (!file) return;
        this.value = '';

        var formData = new FormData();
        formData.append('file', file);

        try {
            var res = await fetch('/project/open', { method: 'POST', body: formData });
            if (!res.ok) {
                var err = await res.json();
                showToast(err.detail || 'Failed to open project', 'error');
                return;
            }
            var data = await res.json();
            currentModel = data;
            currentJobId = 'project';
            renderTree();
            renderCoverageIndicator();
            updateProjectUI();
            switchTab('tree');
            showToast('Project "' + (data.project.name || 'Untitled') + '" loaded.', 'success');
        } catch (e) {
            showToast('Failed to open project: ' + e.message, 'error');
        }
    });

    // Save Project As button
    document.getElementById('btn-save-project').addEventListener('click', function() {
        if (!currentModel || !currentModel.project) {
            showToast('No project to save.', 'error');
            return;
        }
        window.open('/project/download', '_blank');
    });
});

// =============================================================================
// 3. MODE TOGGLE
// =============================================================================

function setMode(mode) {
    selectedMode = mode;

    // Update segment buttons
    document.querySelectorAll('#mode-toggle .segment').forEach(function (btn) {
        btn.classList.toggle('active', btn.getAttribute('data-mode') === mode);
    });

    // Show/hide layer groups
    var capellaGroup = document.getElementById('capella-layers');
    var rhapsodyGroup = document.getElementById('rhapsody-diagrams');
    if (capellaGroup) capellaGroup.style.display = mode === 'capella' ? '' : 'none';
    if (rhapsodyGroup) rhapsodyGroup.style.display = mode === 'rhapsody' ? '' : 'none';

    // Update section label
    var label = document.querySelector('#layer-selection .section-label');
    if (label) label.textContent = mode === 'capella' ? 'Layers' : 'Diagrams';

    readSelectedLayers();
}

function updateProjectUI() {
    var nameEl = document.getElementById('project-name');
    var modifiedEl = document.getElementById('project-modified');

    if (currentModel && currentModel.project) {
        nameEl.textContent = currentModel.project.name || 'Untitled Project';
        if (currentModel.project.last_modified) {
            var d = new Date(currentModel.project.last_modified);
            modifiedEl.textContent = 'Last saved ' + d.toLocaleString();
        }
        // Lock mode toggle if batches exist
        if (currentModel.batches && currentModel.batches.length > 0) {
            lockModeToggle();
        }
    }
}

function lockModeToggle() {
    var toggleBtns = document.querySelectorAll('#mode-toggle .segment-btn');
    toggleBtns.forEach(function(btn) {
        btn.classList.add('locked');
        btn.title = 'Mode is locked for this project';
        btn.style.pointerEvents = 'none';
    });
}

function unlockModeToggle() {
    var toggleBtns = document.querySelectorAll('#mode-toggle .segment-btn');
    toggleBtns.forEach(function(btn) {
        btn.classList.remove('locked');
        btn.title = '';
        btn.style.pointerEvents = '';
    });
}

function readSelectedLayers() {
    var groupId = selectedMode === 'capella' ? 'capella-layers' : 'rhapsody-diagrams';
    var group = document.getElementById(groupId);
    if (!group) { selectedLayers = []; return; }

    selectedLayers = [];
    group.querySelectorAll('input[type=checkbox]:checked').forEach(function (cb) {
        selectedLayers.push(cb.value);
    });
}

// =============================================================================
// 4. FILE UPLOAD
// =============================================================================

function handleDragOver(e) {
    e.preventDefault();
    document.getElementById('upload-zone').classList.add('dragover');
}

function handleDragLeave(e) {
    document.getElementById('upload-zone').classList.remove('dragover');
}

function handleDrop(e) {
    e.preventDefault();
    document.getElementById('upload-zone').classList.remove('dragover');
    var files = e.dataTransfer.files;
    if (files && files.length > 0) {
        processFile(files[0]);
    }
}

function handleFileSelect(input) {
    if (input.files && input.files.length > 0) {
        processFile(input.files[0]);
    }
}

async function processFile(file) {
    uploadedFile = file;
    var zone = document.getElementById('upload-zone');
    zone.classList.add('uploading');

    var formData = new FormData();
    formData.append('file', file);

    try {
        var res = await fetch('/upload', { method: 'POST', body: formData });
        if (!res.ok) {
            var err = await res.json();
            showToast(err.detail || 'Upload failed', 'error');
            zone.classList.remove('uploading');
            return;
        }
        var data = await res.json();
        parsedRequirements = data.requirements || [];

        // Show file status
        document.getElementById('file-status').style.display = '';
        document.getElementById('file-name').textContent = file.name;
        document.getElementById('req-count').textContent = parsedRequirements.length + ' requirements';

        // Enable generate button
        document.getElementById('generate-btn').disabled = false;

        // Feature 2: populate requirement preview list
        populateReqPreview(parsedRequirements);

        showToast('Loaded ' + parsedRequirements.length + ' requirements from ' + file.name, 'success');
    } catch (e) {
        showToast('Upload failed: ' + e.message, 'error');
    }

    zone.classList.remove('uploading');
}

// =============================================================================
// 4b. REQUIREMENT PREVIEW (Feature 2)
// =============================================================================

function populateReqPreview(reqs) {
    var section = document.getElementById('req-preview-section');
    var list = document.getElementById('req-preview-list');
    if (!section || !list) return;

    clearChildren(list);

    reqs.forEach(function(req) {
        var item = el('div', { className: 'req-preview-item' });

        var cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.className = 'req-checkbox';
        cb.value = req.id;
        cb.checked = true;
        cb.addEventListener('change', updateReqSelectedCount);

        var idSpan = el('span', { className: 'req-preview-id', textContent: req.id });
        var textSpan = el('span', { className: 'req-preview-text', textContent: req.text || '' });
        if (req.text) textSpan.title = req.text;

        item.appendChild(cb);
        item.appendChild(idSpan);
        item.appendChild(textSpan);
        list.appendChild(item);
    });

    section.style.display = '';
    updateReqSelectedCount();
}

function updateReqSelectedCount() {
    var total = document.querySelectorAll('#req-preview-list .req-checkbox').length;
    var checked = document.querySelectorAll('#req-preview-list .req-checkbox:checked').length;
    var countEl = document.getElementById('req-selected-count');
    if (countEl) countEl.textContent = checked + ' of ' + total + ' selected';
}

function reqSelectAll() {
    document.querySelectorAll('#req-preview-list .req-checkbox').forEach(function(cb) { cb.checked = true; });
    updateReqSelectedCount();
}

function reqDeselectAll() {
    document.querySelectorAll('#req-preview-list .req-checkbox').forEach(function(cb) { cb.checked = false; });
    updateReqSelectedCount();
}

// =============================================================================
// 5. PROVIDER SELECTOR
// =============================================================================

function initProvider() {
    var provider = (CURRENT_SETTINGS && CURRENT_SETTINGS.provider) || 'anthropic';
    // Map anthropic/openrouter to 'api' for the simplified toggle
    var uiProvider = (provider === 'local') ? 'local' : 'api';
    setProvider(uiProvider);
}

function setProvider(uiProvider) {
    document.querySelectorAll('#provider-selector .segment').forEach(function (btn) {
        btn.classList.toggle('active', btn.getAttribute('data-provider') === uiProvider);
    });
    // Store the UI choice; gatherSettings resolves 'api' to the actual provider
    if (typeof CURRENT_SETTINGS !== 'undefined') {
        CURRENT_SETTINGS._uiProvider = uiProvider;
    }
}

// =============================================================================
// 6. PIPELINE EXECUTION (GENERATE BUTTON)
// =============================================================================

async function startGenerate() {
    readSelectedLayers();

    if (selectedLayers.length === 0) {
        showToast('Please select at least one layer.', 'error');
        return;
    }
    if (parsedRequirements.length === 0) {
        showToast('Please upload a requirements file first.', 'error');
        return;
    }

    var settings = gatherSettings();
    _pendingSettings = settings;

    try {
        var res = await fetch('/estimate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                mode: settings.mode,
                selected_layers: settings.selected_layers,
                model: settings.model,
            }),
        });
        if (!res.ok) {
            var err = await res.json();
            showToast(err.detail || 'Failed to get estimate', 'error');
            return;
        }
        var estimate = await res.json();
        showCostModal(estimate);
    } catch (e) {
        showToast('Could not estimate cost: ' + e.message, 'error');
    }
}

function gatherSettings() {
    var uiProvider = (CURRENT_SETTINGS && CURRENT_SETTINGS._uiProvider) || 'api';
    var configuredProvider = (CURRENT_SETTINGS && CURRENT_SETTINGS.provider) || 'anthropic';
    // 'api' resolves to whatever is configured in settings (anthropic or openrouter)
    var provider = (uiProvider === 'local') ? 'local' : configuredProvider;

    var model = (CURRENT_SETTINGS && CURRENT_SETTINGS.model) || 'claude-sonnet-4-6';

    var modelSelect = document.getElementById('settings-model');
    if (modelSelect && modelSelect.value) {
        model = modelSelect.value;
    }

    return {
        mode: selectedMode,
        selected_layers: selectedLayers.slice(),
        model: model,
        provider: provider,
    };
}

function showCostModal(estimate) {
    document.getElementById('cost-model-name').textContent = estimate.model || 'Unknown';
    document.getElementById('cost-calls').textContent = estimate.total_calls || 0;
    var minCost = formatCost(estimate.estimated_min_cost || 0);
    var maxCost = formatCost(estimate.estimated_max_cost || 0);
    document.getElementById('cost-range').textContent = minCost + ' \u2013 ' + maxCost;
    document.getElementById('cost-modal').style.display = '';
}

function closeCostModal() {
    document.getElementById('cost-modal').style.display = 'none';
    _pendingSettings = null;
}

async function proceedGenerate(clarifications) {
    document.getElementById('cost-modal').style.display = 'none';

    var settings = _pendingSettings;
    _pendingSettings = null;
    if (!settings) return;

    if (clarifications) {
        settings.clarifications = clarifications;
    }

    // Create project first if none exists
    if (!currentModel || !currentModel.project) {
        await fetch('/project/new', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: 'Untitled Project', mode: selectedMode}),
        });
    }

    // Feature 2: attach selected requirement IDs
    var checkedBoxes = document.querySelectorAll('#req-preview-list .req-checkbox:checked');
    if (checkedBoxes.length > 0) {
        var selectedIds = [];
        checkedBoxes.forEach(function(cb) { selectedIds.push(cb.value); });
        settings.selected_requirements = selectedIds;
    }

    try {
        var res = await fetch('/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings),
        });
        if (!res.ok) {
            var err = await res.json();
            showErrorPopup('Failed to Start Generation', err.detail || 'Unknown server error');
            return;
        }
        var data = await res.json();
        currentJobId = data.job_id;
        showProgressArea(settings);
        connectSSE(currentJobId);
    } catch (e) {
        showToast('Failed to start: ' + e.message, 'error');
    }
}

function showProgressArea(settings) {
    document.getElementById('tab-content').style.display = 'none';
    document.getElementById('progress-area').style.display = '';
    document.getElementById('running-cost').textContent = '';

    // Add spinner to title
    var titleEl = document.querySelector('.progress-title');
    if (titleEl) {
        clearChildren(titleEl);
        var spinner = el('span', { className: 'spinner' });
        titleEl.appendChild(spinner);
        titleEl.appendChild(document.createTextNode('Generating Model'));
    }

    var stagesDiv = document.getElementById('pipeline-stages');
    clearChildren(stagesDiv);

    var stages = [
        { key: 'analyze', label: 'Analyzing Requirements', desc: 'Checking for ambiguity and completeness' },
        { key: 'clarify', label: 'Clarification', desc: 'Resolving any flagged issues' },
        { key: 'generate', label: 'Generating Model Layers', desc: 'Building MBSE elements for each layer' },
        { key: 'link', label: 'Creating Traceability Links', desc: 'Connecting elements across layers' },
        { key: 'instruct', label: 'Writing Recreation Steps', desc: 'Step-by-step instructions for your tool' },
    ];

    stages.forEach(function (s) {
        var row = el('div', { className: 'stage-row stage-pending', id: 'stage-' + s.key });

        // Circle icon
        var icon = el('div', { className: 'stage-icon', id: 'icon-' + s.key });
        row.appendChild(icon);

        // Content area
        var content = el('div', { className: 'stage-content' });

        // Header row: label + timer + badge
        var header = el('div', { className: 'stage-header' });
        var label = el('span', { className: 'stage-label', textContent: s.label });
        var timer = el('span', { className: 'stage-timer', id: 'timer-' + s.key });
        var badge = el('span', { className: 'stage-badge', id: 'badge-' + s.key, textContent: 'Waiting' });
        header.appendChild(label);
        header.appendChild(timer);
        header.appendChild(badge);
        content.appendChild(header);

        // Detail text
        var detail = el('div', { className: 'stage-detail', id: 'detail-' + s.key, textContent: s.desc });
        content.appendChild(detail);

        // Progress bar
        var barWrap = el('div', { className: 'stage-bar-wrap' });
        var bar = el('div', { className: 'stage-bar', id: 'bar-' + s.key });
        barWrap.appendChild(bar);
        content.appendChild(barWrap);

        row.appendChild(content);
        stagesDiv.appendChild(row);
    });
}

function connectSSE(jobId) {
    if (sseSource) {
        sseSource.close();
        sseSource = null;
    }
    sseSource = new EventSource('/stream/' + jobId);

    sseSource.onmessage = function (e) {
        try {
            var event = JSON.parse(e.data);
            handlePipelineEvent(event);
        } catch (err) {
            console.error('SSE parse error', err);
        }
    };

    sseSource.onerror = function () {
        sseSource.close();
        sseSource = null;
    };
}

function handlePipelineEvent(event) {
    var stage = event.stage;
    var status = event.status;
    var detail = event.detail || '';
    var cost = event.cost || '';

    if (cost) {
        document.getElementById('running-cost').textContent = cost;
    }

    if (stage === 'done') {
        if (sseSource) { sseSource.close(); sseSource = null; }
        _stopAllTimers();
        var titleEl = document.querySelector('.progress-title');
        if (titleEl) {
            clearChildren(titleEl);
            var check = el('span', { textContent: '\u2713', style: 'color: #4ade80; font-size: 18px;' });
            titleEl.appendChild(check);
            titleEl.appendChild(document.createTextNode(' Model Complete'));
        }
        document.getElementById('running-cost').textContent = detail;
        fetchAndDisplayModel(currentJobId);
        return;
    }

    if (stage === 'cancelled') {
        if (sseSource) { sseSource.close(); sseSource = null; }
        _stopAllTimers();
        hideProgressArea();
        showToast('Job cancelled.', 'info');
        return;
    }

    if (stage === 'error') {
        if (sseSource) { sseSource.close(); sseSource = null; }
        _stopAllTimers();
        hideProgressArea();
        showErrorPopup('Pipeline Failed', detail);
        return;
    }

    // Check for clarification trigger from analyze stage
    if (stage === 'analyze' && status === 'complete' && event.data) {
        var flagged = (event.data && event.data.flagged) || [];
        if (flagged.length > 0) {
            showClarificationModal(flagged);
        }
    }

    var stageRow = document.getElementById('stage-' + stage);
    var bar = document.getElementById('bar-' + stage);
    var detailEl = document.getElementById('detail-' + stage);
    var badge = document.getElementById('badge-' + stage);
    var icon = document.getElementById('icon-' + stage);

    if (!stageRow) return;

    var timer = document.getElementById('timer-' + stage);

    if (status === 'running') {
        stageRow.className = 'stage-row stage-running';
        if (badge) badge.textContent = 'Running';
        if (icon) icon.textContent = '';
        if (detailEl) detailEl.textContent = detail;
        // Start elapsed timer for this stage
        if (!_stageTimers[stage]) {
            _stageTimers[stage] = Date.now();
            _startElapsedUpdater();
        }
    } else if (status === 'complete') {
        stageRow.className = 'stage-row stage-complete';
        if (badge) badge.textContent = 'Done';
        if (icon) icon.textContent = '\u2713';
        if (detailEl) detailEl.textContent = detail;
        // Freeze the timer at final value
        if (_stageTimers[stage] && timer) {
            var elapsed = Math.round((Date.now() - _stageTimers[stage]) / 1000);
            timer.textContent = _formatElapsed(elapsed);
            timer.classList.add('timer-done');
        }
        delete _stageTimers[stage];
    } else if (status === 'layer_complete') {
        // Partial progress within generate stage -- keep it running
        if (detailEl) detailEl.textContent = detail;
    }
}

async function fetchAndDisplayModel(jobId) {
    try {
        // Fetch full project instead of just job result
        var res = await fetch('/project');
        if (res.ok) {
            var data = await res.json();
            if (data.project) {
                currentModel = data;
                currentJobId = jobId;
            }
        } else {
            // Fallback to job endpoint
            var jobRes = await fetch('/job/' + jobId);
            if (!jobRes.ok) {
                var err = await jobRes.json();
                showToast('Failed to load model: ' + (err.detail || 'unknown error'), 'error');
                hideProgressArea();
                return;
            }
            currentModel = await jobRes.json();
            currentJobId = jobId;
        }
        hideProgressArea();
        renderTree();
        renderCoverageIndicator();
        switchTab('tree');
        updateProjectUI();
        showToast('Model generated successfully!', 'success');
    } catch (e) {
        showToast('Failed to load model: ' + e.message, 'error');
        hideProgressArea();
    }
}

function hideProgressArea() {
    document.getElementById('progress-area').style.display = 'none';
    document.getElementById('tab-content').style.display = '';
}

async function cancelJob() {
    if (!currentJobId) return;
    try {
        await fetch('/cancel/' + currentJobId, { method: 'POST' });
    } catch (e) {
        // ignore
    }
    if (sseSource) { sseSource.close(); sseSource = null; }
    hideProgressArea();
    showToast('Cancellation requested.', 'info');
}

// =============================================================================
// 7. TREE RENDERING
// =============================================================================

function renderTree() {
    var container = document.getElementById('tab-tree');
    clearChildren(container);

    if (!currentModel || !currentModel.layers) {
        container.appendChild(el('div', {
            className: 'empty-state',
            textContent: 'No model loaded. Generate a model first.',
        }));
        return;
    }

    var layers = currentModel.layers;
    var layerKeys = Object.keys(layers);

    if (layerKeys.length === 0) {
        container.appendChild(el('div', {
            className: 'empty-state',
            textContent: 'Model contains no layers.',
        }));
        return;
    }

    layerKeys.forEach(function (layerKey) {
        var layerData = layers[layerKey];
        var layerSection = renderLayerSection(layerKey, layerData);
        container.appendChild(layerSection);
    });
}

function renderLayerSection(layerKey, layerData) {
    var displayName = (CAPELLA_LAYERS && CAPELLA_LAYERS[layerKey]) ||
                      (RHAPSODY_DIAGRAMS && RHAPSODY_DIAGRAMS[layerKey]) ||
                      layerKey;

    var totalCount = 0;
    if (layerData && typeof layerData === 'object') {
        Object.values(layerData).forEach(function (coll) {
            if (Array.isArray(coll)) totalCount += coll.length;
        });
    }

    var section = el('div', { className: 'layer-section', id: 'layer-section-' + layerKey });

    var header = el('div', { className: 'layer-header' });
    var arrow = el('span', { className: 'layer-arrow open', textContent: '\u25be' });
    var title = el('span', { className: 'layer-title', textContent: displayName });
    var countBadge = el('span', { className: 'layer-count', textContent: totalCount + ' elements' });
    var regenBtn = el('button', { className: 'btn-regen', title: 'Regenerate this layer', textContent: '\u21ba Regen' });
    regenBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        regenLayer(layerKey);
    });

    header.appendChild(arrow);
    header.appendChild(title);
    header.appendChild(countBadge);
    header.appendChild(regenBtn);

    var body = el('div', { className: 'layer-body', id: 'layer-body-' + layerKey });

    header.addEventListener('click', function () {
        var isOpen = body.style.display !== 'none';
        body.style.display = isOpen ? 'none' : '';
        arrow.textContent = isOpen ? '\u25b8' : '\u25be';
        arrow.classList.toggle('open', !isOpen);
    });

    section.appendChild(header);
    section.appendChild(body);

    if (layerData && typeof layerData === 'object') {
        Object.keys(layerData).forEach(function (collKey) {
            var collection = layerData[collKey];
            if (!Array.isArray(collection)) return;
            var collSection = renderCollection(layerKey, collKey, collection);
            body.appendChild(collSection);
        });
    }

    return section;
}

function renderCollection(layerKey, collKey, elements) {
    var collLabel = collKey.charAt(0).toUpperCase() + collKey.slice(1).replace(/_/g, ' ');

    var section = el('div', { className: 'collection-section', id: 'coll-' + layerKey + '-' + collKey });

    var header = el('div', { className: 'collection-header' });
    var arrow = el('span', { className: 'collection-arrow', textContent: '\u25be' });
    header.appendChild(arrow);
    header.appendChild(el('span', { className: 'collection-name', textContent: collLabel }));
    header.appendChild(el('span', { className: 'collection-count', textContent: '(' + elements.length + ')' }));

    var listDiv = el('div', { className: 'element-list', id: 'list-' + layerKey + '-' + collKey });

    elements.forEach(function (elem) {
        listDiv.appendChild(renderElementRow(layerKey, collKey, elem));
    });

    var addBtn = el('button', { className: 'btn-add-element', textContent: '+ Add' });
    addBtn.addEventListener('click', function () {
        showAddElementForm(layerKey, collKey, listDiv, addBtn);
    });

    // Collapsible collection
    header.addEventListener('click', function () {
        var isOpen = listDiv.style.display !== 'none';
        listDiv.style.display = isOpen ? 'none' : '';
        addBtn.style.display = isOpen ? 'none' : '';
        arrow.textContent = isOpen ? '\u25b8' : '\u25be';
    });

    section.appendChild(header);
    section.appendChild(listDiv);
    section.appendChild(addBtn);
    return section;
}

function renderElementRow(layerKey, collKey, elem) {
    var row = el('div', { className: 'element-row', id: 'elem-row-' + (elem.id || '') });

    var idBadge = el('span', { className: 'element-id', textContent: elem.id || '?' });
    var name = el('span', { className: 'element-name', textContent: elem.name || elem.id || '(unnamed)' });

    row.appendChild(idBadge);
    row.appendChild(name);

    if (elem.type) {
        row.appendChild(el('span', { className: 'element-type', textContent: elem.type }));
    }

    var actions = el('div', { className: 'element-actions' });

    var editBtn = el('button', { className: 'btn-icon-small', title: 'Edit', textContent: '\u270e' });
    editBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        startInlineEdit(row, layerKey, collKey, elem);
    });

    var deleteBtn = el('button', { className: 'btn-icon-small btn-delete', title: 'Delete', textContent: '\u2715' });
    deleteBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        deleteElement(elem.id, layerKey, collKey);
    });

    actions.appendChild(editBtn);
    actions.appendChild(deleteBtn);
    row.appendChild(actions);

    // Click row to expand/collapse details
    row.addEventListener('click', function (e) {
        if (e.target.closest('.element-actions') || e.target.closest('button')) return;
        toggleElementDetails(row, elem);
    });

    return row;
}

function toggleElementDetails(row, elem) {
    // Check if details panel already exists right after this row
    var existing = row.nextElementSibling;
    if (existing && existing.classList.contains('element-details')) {
        existing.remove();
        return;
    }

    var details = el('div', { className: 'element-details' });
    var skipKeys = { id: 1, name: 1, type: 1 };

    Object.keys(elem).forEach(function (key) {
        if (skipKeys[key]) return;
        var val = elem[key];
        if (val === null || val === undefined || val === '') return;

        var field = el('div', { className: 'detail-field' });
        var keyEl = el('span', { className: 'detail-key', textContent: key.replace(/_/g, ' ') });
        var valEl = el('span', { className: 'detail-value' });

        if (Array.isArray(val)) {
            if (val.length === 0) return;
            if (typeof val[0] === 'object') {
                // Array of objects (e.g., scenario steps)
                val.forEach(function (item, i) {
                    var line = Object.entries(item).map(function (kv) {
                        return kv[0] + ': ' + kv[1];
                    }).join(', ');
                    var stepEl = el('div', { textContent: (i + 1) + '. ' + line, style: 'padding: 1px 0; color: #999;' });
                    valEl.appendChild(stepEl);
                });
            } else {
                valEl.textContent = val.join(', ');
            }
        } else if (typeof val === 'object') {
            valEl.textContent = JSON.stringify(val);
        } else {
            valEl.textContent = String(val);
        }

        field.appendChild(keyEl);
        field.appendChild(valEl);
        details.appendChild(field);
    });

    if (details.children.length === 0) {
        var empty = el('div', { className: 'detail-field' });
        empty.appendChild(el('span', { className: 'detail-value', textContent: 'No additional properties' }));
        details.appendChild(empty);
    }

    // Feature 3: Traceability section
    var relatedLinks = (currentModel && currentModel.links || []).filter(function(link) {
        return link.source === elem.id || link.target === elem.id;
    });
    if (relatedLinks.length > 0) {
        var traceHeader = el('div', { className: 'detail-trace-header', textContent: 'Traceability' });
        details.appendChild(traceHeader);
        relatedLinks.forEach(function(link) {
            var traceRow = el('div', { className: 'detail-trace-row' });
            if (link.source === elem.id) {
                traceRow.textContent = '\u2192 ' + link.type + ' \u2192 ' + link.target;
            } else {
                traceRow.textContent = '\u2190 ' + link.type + ' \u2190 ' + link.source;
            }
            if (link.description) {
                traceRow.title = link.description;
            }
            details.appendChild(traceRow);
        });
    }

    row.parentNode.insertBefore(details, row.nextSibling);
}

async function regenLayer(layerKey) {
    if (!currentModel) {
        showToast('No model to regenerate layer for.', 'error');
        return;
    }
    showToast('Regenerating layer ' + layerKey + '...', 'info');
    try {
        var settings = gatherSettings();
        settings.selected_layers = [layerKey];
        var res = await fetch('/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings),
        });
        if (!res.ok) {
            var err = await res.json();
            showToast(err.detail || 'Regen failed', 'error');
            return;
        }
        var data = await res.json();
        await pollJobUntilComplete(data.job_id, function (completedModel) {
            if (completedModel && completedModel.layers && completedModel.layers[layerKey]) {
                currentModel.layers[layerKey] = completedModel.layers[layerKey];
                renderTree();
                showToast('Layer ' + layerKey + ' regenerated.', 'success');
            }
        });
    } catch (e) {
        showToast('Regen failed: ' + e.message, 'error');
    }
}

async function pollJobUntilComplete(jobId, onComplete) {
    var maxWait = 120000;
    var start = Date.now();
    while (Date.now() - start < maxWait) {
        await sleep(2000);
        try {
            var res = await fetch('/job/' + jobId);
            if (res.ok) {
                var model = await res.json();
                onComplete(model);
                return;
            }
        } catch (e) {
            // keep polling
        }
    }
    showToast('Regen timed out.', 'error');
}

function sleep(ms) {
    return new Promise(function (resolve) { setTimeout(resolve, ms); });
}

// =============================================================================
// 8. OUTPUT TABS
// =============================================================================

function switchTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(function (btn) {
        btn.classList.toggle('active', btn.getAttribute('data-tab') === tabName);
    });

    document.querySelectorAll('.tab-pane').forEach(function (pane) {
        pane.classList.remove('active');
    });

    var activePane = document.getElementById('tab-' + tabName);
    if (activePane) activePane.classList.add('active');

    if (tabName === 'links') renderLinksTab();
    if (tabName === 'instructions') renderInstructionsTab();
    if (tabName === 'json') renderJsonTab();
    if (tabName === 'batches') renderBatchesTab();
}

function renderLinksTab() {
    var tbody = document.getElementById('links-tbody');
    if (!tbody) return;
    clearChildren(tbody);

    if (!currentModel || !currentModel.links || currentModel.links.length === 0) {
        var row = document.createElement('tr');
        var td = document.createElement('td');
        td.colSpan = 3;
        td.textContent = 'No links in this model.';
        td.style.textAlign = 'center';
        td.style.color = '#666';
        row.appendChild(td);
        tbody.appendChild(row);
        return;
    }

    currentModel.links.forEach(function (link) {
        var row = document.createElement('tr');
        row.appendChild(el('td', { textContent: link.source }));
        row.appendChild(el('td', { className: 'link-type', textContent: link.type }));
        row.appendChild(el('td', { textContent: link.target }));
        tbody.appendChild(row);
    });
}

function renderInstructionsTab() {
    var list = document.getElementById('instructions-list');
    if (!list) return;
    clearChildren(list);
    list.className = 'instructions-container';

    if (!currentModel || !currentModel.instructions) {
        list.appendChild(el('div', { className: 'empty-state', textContent: 'No instructions available.' }));
        return;
    }

    var steps = currentModel.instructions.steps || [];
    var toolName = currentModel.instructions.tool || '';

    if (steps.length === 0) {
        list.appendChild(el('div', { className: 'empty-state', textContent: 'No steps generated.' }));
        return;
    }

    // Header with tool name and copy-all button
    var header = el('div', { className: 'instructions-header' });
    if (toolName) {
        header.appendChild(el('span', { className: 'instructions-tool', textContent: toolName }));
    }
    header.appendChild(el('span', { className: 'instructions-count', textContent: steps.length + ' steps' }));
    var copyAllBtn = el('button', { className: 'btn-copy-all', textContent: 'Copy All' });
    copyAllBtn.addEventListener('click', function() {
        var allText = steps.map(function(s) {
            return 'Step ' + (s.step || '') + ': ' + (s.action || '') + '\n' + (s.detail || '');
        }).join('\n\n');
        copyToClipboard(allText);
    });
    header.appendChild(copyAllBtn);
    list.appendChild(header);

    // Group steps by layer
    var layerGroups = {};
    var layerOrder = [];
    steps.forEach(function(step) {
        var layer = step.layer || 'general';
        if (!layerGroups[layer]) {
            layerGroups[layer] = [];
            layerOrder.push(layer);
        }
        layerGroups[layer].push(step);
    });

    layerOrder.forEach(function(layer) {
        var layerDisplay = layer.replace(/_/g, ' ').replace(/\b\w/g, function(c) { return c.toUpperCase(); });

        var section = el('div', { className: 'instructions-layer-section' });
        var layerHeader = el('div', { className: 'instructions-layer-header' });
        layerHeader.appendChild(el('span', { className: 'instructions-layer-name', textContent: layerDisplay }));
        layerHeader.appendChild(el('span', { className: 'instructions-layer-count', textContent: layerGroups[layer].length + ' steps' }));
        section.appendChild(layerHeader);

        layerGroups[layer].forEach(function(step) {
            var card = el('div', { className: 'instruction-card' });

            var cardHeader = el('div', { className: 'instruction-card-header' });
            var stepNum = el('span', { className: 'instruction-step-num', textContent: step.step || '?' });
            var action = el('span', { className: 'instruction-action', textContent: step.action || '' });
            var copyBtn = el('button', { className: 'instruction-copy', title: 'Copy step', textContent: '\u2398' });
            copyBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                copyToClipboard((step.action || '') + ': ' + (step.detail || ''));
            });
            cardHeader.appendChild(stepNum);
            cardHeader.appendChild(action);
            cardHeader.appendChild(copyBtn);
            card.appendChild(cardHeader);

            if (step.detail) {
                var detail = el('div', { className: 'instruction-detail', textContent: step.detail });
                card.appendChild(detail);
            }

            section.appendChild(card);
        });

        list.appendChild(section);
    });
}

function renderJsonTab() {
    var pre = document.getElementById('json-output');
    if (!pre) return;
    pre.textContent = currentModel ? JSON.stringify(currentModel, null, 2) : 'No model loaded.';
}

function renderBatchesTab() {
    var container = document.getElementById('batch-list');
    if (!container) return;
    clearChildren(container);

    if (!currentModel || !currentModel.batches || currentModel.batches.length === 0) {
        container.appendChild(el('div', {className: 'empty-state', textContent: 'No batches yet. Upload requirements and add your first batch.'}));
        return;
    }

    // Build a lookup of requirement ID -> requirement object
    var reqLookup = {};
    if (currentModel.requirements) {
        currentModel.requirements.forEach(function(r) { reqLookup[r.id] = r; });
    }

    // Render newest first
    var batches = currentModel.batches.slice().reverse();
    batches.forEach(function(batch) {
        var card = el('div', {className: 'batch-card'});

        var header = el('div', {className: 'batch-card-header'});
        var headerLeft = el('div', {className: 'batch-header-left'});
        headerLeft.appendChild(el('span', {className: 'batch-id', textContent: batch.id}));
        var ts = new Date(batch.timestamp);
        headerLeft.appendChild(el('span', {className: 'batch-time', textContent: ts.toLocaleString()}));
        header.appendChild(headerLeft);
        var expandArrow = el('span', {className: 'batch-expand-arrow', textContent: '\u25b8'});
        header.appendChild(expandArrow);
        card.appendChild(header);

        var meta = el('div', {className: 'batch-card-meta'});
        meta.appendChild(el('span', {className: 'batch-source', textContent: batch.source_file}));
        meta.appendChild(el('span', {className: 'batch-reqs', textContent: batch.requirement_ids.length + ' requirements'}));
        card.appendChild(meta);

        var stats = el('div', {className: 'batch-card-stats'});
        stats.appendChild(el('span', {className: 'batch-layers', textContent: batch.layers_generated.join(', ')}));
        stats.appendChild(el('span', {className: 'batch-model', textContent: batch.model}));
        stats.appendChild(el('span', {className: 'batch-cost', textContent: '$' + batch.cost.toFixed(4)}));
        card.appendChild(stats);

        // Expandable requirements detail
        var detailDiv = el('div', {className: 'batch-detail', style: 'display:none'});
        var detailHeader = el('div', {className: 'batch-detail-header', textContent: 'Requirements in this batch'});
        detailDiv.appendChild(detailHeader);

        if (batch.requirement_ids && batch.requirement_ids.length > 0) {
            batch.requirement_ids.forEach(function(reqId) {
                var row = el('div', {className: 'batch-req-row'});
                row.appendChild(el('span', {className: 'batch-req-id', textContent: reqId}));
                var req = reqLookup[reqId];
                var text = req ? req.text : '(requirement text not available)';
                var textSpan = el('span', {className: 'batch-req-text', textContent: text});
                textSpan.title = text;
                row.appendChild(textSpan);
                detailDiv.appendChild(row);
            });
        } else {
            detailDiv.appendChild(el('div', {className: 'batch-req-row', textContent: 'No requirement IDs recorded.'}));
        }

        card.appendChild(detailDiv);

        // Toggle expand on card click
        header.style.cursor = 'pointer';
        header.addEventListener('click', function() {
            var showing = detailDiv.style.display !== 'none';
            detailDiv.style.display = showing ? 'none' : '';
            expandArrow.textContent = showing ? '\u25b8' : '\u25be';
            card.classList.toggle('batch-card-expanded', !showing);
        });

        container.appendChild(card);
    });
}

// =============================================================================
// 9. INLINE EDITING
// =============================================================================

function startInlineEdit(row, layerKey, collKey, elem) {
    if (row.querySelector('.edit-input')) return;

    var nameSpan = row.querySelector('.element-name');
    if (!nameSpan) return;

    var originalName = nameSpan.textContent;
    nameSpan.style.display = 'none';

    var input = document.createElement('input');
    input.type = 'text';
    input.className = 'edit-input';
    input.value = originalName;

    var saveBtn = el('button', { className: 'btn-save-edit', textContent: '\u2713' });
    var cancelBtn = el('button', { className: 'btn-cancel-edit', textContent: '\u2715' });

    saveBtn.addEventListener('click', function () {
        saveInlineEdit(row, layerKey, collKey, elem, input.value, nameSpan);
    });

    cancelBtn.addEventListener('click', function () {
        input.remove();
        saveBtn.remove();
        cancelBtn.remove();
        nameSpan.style.display = '';
    });

    input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') saveBtn.click();
        if (e.key === 'Escape') cancelBtn.click();
    });

    row.insertBefore(input, nameSpan.nextSibling);
    row.insertBefore(saveBtn, input.nextSibling);
    row.insertBefore(cancelBtn, saveBtn.nextSibling);
    input.focus();
    input.select();
}

async function saveInlineEdit(row, layerKey, collKey, elem, newName, nameSpan) {
    if (!currentJobId) {
        showToast('No active job to save edits to.', 'error');
        return;
    }

    var input = row.querySelector('.edit-input');
    var saveBtn = row.querySelector('.btn-save-edit');
    var cancelBtn = row.querySelector('.btn-cancel-edit');

    try {
        var res = await fetch('/job/' + currentJobId + '/edit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tool_name: 'modify_element',
                arguments: {
                    element_id: elem.id,
                    updates: { name: newName },
                },
            }),
        });
        var data = await res.json();
        if (!data.success) {
            showToast('Edit failed: ' + data.message, 'error');
            return;
        }

        // Update local model
        if (currentModel && currentModel.layers[layerKey] && currentModel.layers[layerKey][collKey]) {
            var coll = currentModel.layers[layerKey][collKey];
            for (var i = 0; i < coll.length; i++) {
                if (coll[i].id === elem.id) {
                    coll[i].name = newName;
                    break;
                }
            }
        }

        nameSpan.textContent = newName;
        nameSpan.style.display = '';
        if (input) input.remove();
        if (saveBtn) saveBtn.remove();
        if (cancelBtn) cancelBtn.remove();

        showToast('Element updated.', 'success');
    } catch (e) {
        showToast('Edit failed: ' + e.message, 'error');
    }
}

async function deleteElement(elementId, layerKey, collKey) {
    if (!elementId) return;
    if (!confirm('Delete element ' + elementId + '? This action cannot be undone.')) return;
    if (!currentJobId) {
        showToast('No active job.', 'error');
        return;
    }

    try {
        var res = await fetch('/job/' + currentJobId + '/edit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tool_name: 'remove_element',
                arguments: { element_id: elementId, cascade: true },
            }),
        });
        var data = await res.json();
        if (!data.success) {
            showToast('Delete failed: ' + data.message, 'error');
            return;
        }

        if (currentModel && currentModel.layers[layerKey] && currentModel.layers[layerKey][collKey]) {
            currentModel.layers[layerKey][collKey] = currentModel.layers[layerKey][collKey].filter(
                function (e) { return e.id !== elementId; }
            );
        }

        renderTree();
        showToast('Element deleted.', 'success');
    } catch (e) {
        showToast('Delete failed: ' + e.message, 'error');
    }
}

function showAddElementForm(layerKey, collKey, listDiv, addBtn) {
    var existing = listDiv.parentNode.querySelector('.add-element-form');
    if (existing) { existing.remove(); return; }

    var form = el('div', { className: 'add-element-form' });

    var idInput = document.createElement('input');
    idInput.type = 'text';
    idInput.className = 'edit-input';
    idInput.placeholder = 'ID (e.g. OE-99)';

    var nameInput = document.createElement('input');
    nameInput.type = 'text';
    nameInput.className = 'edit-input';
    nameInput.placeholder = 'Name';

    var typeInput = document.createElement('input');
    typeInput.type = 'text';
    typeInput.className = 'edit-input';
    typeInput.placeholder = 'Type (optional)';

    var saveBtn = el('button', { className: 'btn-save-edit', textContent: '\u2713 Add' });
    var cancelBtn = el('button', { className: 'btn-cancel-edit', textContent: '\u2715 Cancel' });

    saveBtn.addEventListener('click', async function () {
        var newId = idInput.value.trim();
        var newName = nameInput.value.trim();
        var newType = typeInput.value.trim();

        if (!newId || !newName) {
            showToast('ID and Name are required.', 'error');
            return;
        }

        var newElem = { id: newId, name: newName };
        if (newType) newElem.type = newType;

        await addElement(layerKey, collKey, newElem);
        form.remove();
    });

    cancelBtn.addEventListener('click', function () { form.remove(); });

    form.appendChild(idInput);
    form.appendChild(nameInput);
    form.appendChild(typeInput);
    form.appendChild(saveBtn);
    form.appendChild(cancelBtn);

    addBtn.parentNode.insertBefore(form, addBtn);
    idInput.focus();
}

async function addElement(layerKey, collKey, newElem) {
    if (!currentJobId) {
        showToast('No active job.', 'error');
        return;
    }

    try {
        var res = await fetch('/job/' + currentJobId + '/edit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tool_name: 'add_element',
                arguments: { layer: layerKey, collection: collKey, element: newElem },
            }),
        });
        var data = await res.json();
        if (!data.success) {
            showToast('Add failed: ' + data.message, 'error');
            return;
        }

        if (currentModel && currentModel.layers[layerKey]) {
            if (!currentModel.layers[layerKey][collKey]) {
                currentModel.layers[layerKey][collKey] = [];
            }
            currentModel.layers[layerKey][collKey].push(newElem);
        }

        renderTree();
        showToast('Element added.', 'success');
    } catch (e) {
        showToast('Add failed: ' + e.message, 'error');
    }
}

// =============================================================================
// 10. CHAT AGENT
// =============================================================================

function toggleChat() {
    // No-op: chat panel is always visible now
}

async function sendChat() {
    if (!currentJobId) {
        showToast('No active job. Generate a model first.', 'error');
        return;
    }

    var input = document.getElementById('chat-input');
    var message = input.value.trim();
    if (!message) return;

    input.value = '';
    input.style.height = 'auto';
    appendChatMessage('user', message);

    var sendBtn = document.querySelector('.btn-send');
    if (sendBtn) sendBtn.disabled = true;

    var loadingEl = appendChatMessage('agent', '\u2026', true);

    try {
        var res = await fetch('/job/' + currentJobId + '/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message }),
        });

        if (!res.ok) {
            var err = await res.json();
            loadingEl.remove();
            appendChatMessage('agent', 'Error: ' + (err.detail || 'unknown error'));
        } else {
            var data = await res.json();
            loadingEl.remove();
            appendChatMessage('agent', data.response || '(no response)');

            if (data.model) {
                currentModel = data.model;
                renderTree();
                renderCoverageIndicator();
                var activeTab = document.querySelector('.tab-btn.active');
                if (activeTab) {
                    var tabName = activeTab.getAttribute('data-tab');
                    if (tabName === 'links') renderLinksTab();
                    if (tabName === 'instructions') renderInstructionsTab();
                    if (tabName === 'json') renderJsonTab();
                }
            }
        }
    } catch (e) {
        loadingEl.remove();
        appendChatMessage('agent', 'Error: ' + e.message);
    }

    if (sendBtn) sendBtn.disabled = false;
    input.focus();
}

function appendChatMessage(role, text, isLoading) {
    var history = document.getElementById('chat-history');
    // Remove welcome message on first real message
    var welcome = history.querySelector('.chat-welcome');
    if (welcome) welcome.remove();

    var wrapper = el('div', {
        className: 'chat-message chat-' + role + (isLoading ? ' chat-loading' : ''),
    });

    var label = el('div', { className: 'chat-msg-label', textContent: role === 'user' ? 'You' : 'Agent' });
    wrapper.appendChild(label);

    var body = el('div', { className: 'chat-msg-body' });
    if (role === 'agent' && !isLoading) {
        body.innerHTML = renderMarkdown(text);
    } else {
        body.textContent = text;
    }
    wrapper.appendChild(body);

    history.appendChild(wrapper);
    history.scrollTop = history.scrollHeight;
    return wrapper;
}

function renderMarkdown(text) {
    // Simple markdown renderer (no external dependencies)
    var html = text
        // Escape HTML
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        // Code blocks
        .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
        // Inline code
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        // Bold
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        // Italic
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        // Unordered lists
        .replace(/^[-*] (.+)$/gm, '<li>$1</li>')
        // Wrap consecutive <li> in <ul>
        .replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>')
        // Paragraphs (double newline)
        .replace(/\n\n/g, '</p><p>')
        // Single newlines to <br> (except inside pre/code)
        .replace(/\n/g, '<br>');
    return '<p>' + html + '</p>';
}

function initChatResize() {
    var panel = document.getElementById('chat-panel');
    var handle = document.getElementById('chat-resize-handle');
    if (!handle || !panel) return;

    var startY, startHeight;

    handle.addEventListener('mousedown', function(e) {
        startY = e.clientY;
        startHeight = panel.offsetHeight;
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
        e.preventDefault();
    });

    function onMouseMove(e) {
        var delta = startY - e.clientY;
        var newHeight = Math.max(120, Math.min(window.innerHeight * 0.7, startHeight + delta));
        panel.style.height = newHeight + 'px';
    }

    function onMouseUp() {
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
    }
}

// =============================================================================
// 11. EXPORT
// =============================================================================

// clearSession is superseded by New Project; kept as no-op for compatibility
function clearSession() {
    showToast('Use "New Project" to start fresh.', 'info');
}

function toggleExportMenu() {
    var menu = document.getElementById('export-menu');
    if (!menu) return;
    menu.style.display = menu.style.display === 'none' ? '' : 'none';
}

function exportModel(format) {
    if (!currentJobId) {
        showToast('No active model to export.', 'error');
        return;
    }
    var url = '/job/' + currentJobId + '/export/' + format;
    window.open(url, '_blank');
    document.getElementById('export-menu').style.display = 'none';
}

// =============================================================================
// 12. SETTINGS MODAL
// =============================================================================

function openSettings() {
    var anthKey = document.getElementById('settings-anthropic-key');
    var orKey = document.getElementById('settings-openrouter-key');
    var localUrl = document.getElementById('settings-local-url');

    if (anthKey) anthKey.value = '';
    if (orKey) orKey.value = '';
    if (localUrl) localUrl.value = CURRENT_SETTINGS.local_url || '';

    var anthStatus = document.getElementById('anthropic-key-status');
    var orStatus = document.getElementById('openrouter-key-status');
    if (anthStatus) {
        anthStatus.textContent = CURRENT_SETTINGS.has_anthropic_key ? 'Key configured' : 'No key set';
        anthStatus.style.color = CURRENT_SETTINGS.has_anthropic_key ? '#5a5' : '#c88';
    }
    if (orStatus) {
        orStatus.textContent = CURRENT_SETTINGS.has_openrouter_key ? 'Key configured' : 'No key set';
        orStatus.style.color = CURRENT_SETTINGS.has_openrouter_key ? '#5a5' : '#888';
    }

    var modelSelect = document.getElementById('settings-model');
    if (modelSelect && CURRENT_SETTINGS.model) {
        modelSelect.value = CURRENT_SETTINGS.model;
        showModelDetail(CURRENT_SETTINGS.model);
    }

    document.querySelectorAll('.modal-settings .segment[data-value]').forEach(function (btn) {
        btn.classList.toggle('active', btn.getAttribute('data-value') === (CURRENT_SETTINGS.default_mode || 'capella'));
    });

    loadCostHistory();

    document.getElementById('settings-modal').style.display = '';
}

function closeSettings() {
    document.getElementById('settings-modal').style.display = 'none';
}

function setSettingsMode(mode) {
    document.querySelectorAll('.modal-settings .segment[data-value]').forEach(function (btn) {
        btn.classList.toggle('active', btn.getAttribute('data-value') === mode);
    });
}

function showModelDetail(modelId) {
    var panel = document.getElementById('model-detail-panel');
    if (!panel) return;
    clearChildren(panel);

    var model = null;
    if (Array.isArray(MODEL_CATALOGUE)) {
        model = MODEL_CATALOGUE.find(function (m) { return m.id === modelId; });
    }
    if (!model) return;

    if (model.description) {
        panel.appendChild(el('div', { className: 'model-detail-desc', textContent: model.description }));
    }

    var rows = [
        { label: 'Provider', value: model.provider },
        { label: 'Price', value: model.price },
    ];

    if (model.pros && model.pros.length) {
        rows.push({ label: 'Pros', value: model.pros.join(', ') });
    }
    if (model.cons && model.cons.length) {
        rows.push({ label: 'Cons', value: model.cons.join(', ') });
    }

    rows.forEach(function (r) {
        if (!r.value) return;
        var row = el('div', { className: 'model-detail-row' });
        row.appendChild(el('span', { className: 'model-detail-label', textContent: r.label + ': ' }));
        row.appendChild(el('span', { textContent: r.value }));
        panel.appendChild(row);
    });
}

async function saveSettings() {
    var body = {};

    var anthKey = document.getElementById('settings-anthropic-key');
    var orKey = document.getElementById('settings-openrouter-key');
    var localUrl = document.getElementById('settings-local-url');
    var modelSelect = document.getElementById('settings-model');

    if (anthKey && anthKey.value.trim()) body.anthropic_key = anthKey.value.trim();
    if (orKey && orKey.value.trim()) body.openrouter_key = orKey.value.trim();
    if (localUrl && localUrl.value.trim()) body.local_url = localUrl.value.trim();
    if (modelSelect) body.model = modelSelect.value;

    var activeModeBtn = document.querySelector('.modal-settings .segment[data-value].active');
    if (activeModeBtn) body.default_mode = activeModeBtn.getAttribute('data-value');

    var activeProviderBtn = document.querySelector('#provider-selector .segment.active');
    if (activeProviderBtn) body.provider = activeProviderBtn.getAttribute('data-provider');

    try {
        var res = await fetch('/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        var data = await res.json();
        if (data.status === 'ok') {
            if (body.model) CURRENT_SETTINGS.model = body.model;
            if (body.provider) CURRENT_SETTINGS.provider = body.provider;
            if (body.default_mode) CURRENT_SETTINGS.default_mode = body.default_mode;
            if (body.anthropic_key) CURRENT_SETTINGS.has_anthropic_key = true;
            if (body.openrouter_key) CURRENT_SETTINGS.has_openrouter_key = true;

            closeSettings();
            showToast('Settings saved.', 'success');
        } else {
            showToast('Failed to save settings.', 'error');
        }
    } catch (e) {
        showToast('Failed to save settings: ' + e.message, 'error');
    }
}

async function loadCostHistory() {
    var body = document.getElementById('cost-history-body');
    if (!body) return;
    clearChildren(body);
    body.appendChild(document.createTextNode('Loading...'));

    try {
        var res = await fetch('/cost-history');
        var data = await res.json();

        clearChildren(body);

        var summary = el('div', { className: 'cost-history-summary' });
        summary.appendChild(el('div', { textContent: 'Total runs: ' + (data.total_runs || 0) }));
        summary.appendChild(el('div', { textContent: 'Total spend: ' + formatCost(data.total_spend || 0) }));
        summary.appendChild(el('div', { textContent: 'Average per run: ' + formatCost(data.avg_per_run || 0) }));
        body.appendChild(summary);

        if (data.runs && data.runs.length > 0) {
            body.appendChild(el('div', { className: 'cost-history-subheader', textContent: 'Recent runs:' }));

            data.runs.slice(-5).reverse().forEach(function (run) {
                var row = el('div', { className: 'cost-history-row' });
                var ts = run.timestamp ? new Date(run.timestamp).toLocaleString() : 'Unknown time';
                var cost = run.totals ? formatCost(run.totals.cost_usd || 0) : '$0.00';
                row.appendChild(el('span', { className: 'cost-hist-time', textContent: ts }));
                row.appendChild(el('span', { className: 'cost-hist-cost', textContent: cost }));
                body.appendChild(row);
            });
        }
    } catch (e) {
        clearChildren(body);
        body.appendChild(document.createTextNode('Could not load cost history.'));
    }
}

// =============================================================================
// 13. GIT-BASED UPDATES
// =============================================================================

async function checkUpdatesQuietly() {
    try {
        var res = await fetch('/check-updates');
        var data = await res.json();

        if (data.available) {
            var updateBtn = document.getElementById('update-btn');
            if (updateBtn) {
                updateBtn.textContent = 'Update (' + data.behind + ')';
                updateBtn.classList.add('update-available');
                updateBtn.onclick = checkAndUpdate;
            }
        }
    } catch (e) {
        // Silently ignore
    }
}

async function checkAndUpdate() {
    var btn = document.getElementById('update-btn');
    if (!btn) return;

    btn.textContent = 'Checking...';
    btn.disabled = true;

    try {
        var res = await fetch('/check-updates');
        var data = await res.json();

        if (data.error) {
            showToast(data.error, 'error');
            btn.textContent = 'Update';
            btn.disabled = false;
            return;
        }

        if (data.available) {
            showUpdateBanner(data.behind, data.commits || []);
            btn.textContent = 'Update (' + data.behind + ')';
            btn.disabled = false;
        } else {
            showToast('Already up to date.', 'success');
            btn.textContent = 'Update';
            btn.disabled = false;
        }
    } catch (e) {
        showToast('Could not check for updates.', 'error');
        btn.textContent = 'Update';
        btn.disabled = false;
    }
}

function showUpdateBanner(count, commits) {
    var existing = document.getElementById('update-banner');
    if (existing) existing.remove();

    var banner = el('div', { className: 'update-banner update-banner-pulse', id: 'update-banner' });

    var text = el('span', { className: 'update-banner-text', id: 'update-banner-text' });
    text.appendChild(document.createTextNode(count + ' update(s) available'));

    if (commits && commits.length > 0) {
        var ul = document.createElement('ul');
        ul.className = 'update-commit-list';
        commits.slice(0, 5).forEach(function (msg) {
            ul.appendChild(el('li', { textContent: msg }));
        });
        text.appendChild(ul);
    }

    var updateNowBtn = el('button', { className: 'btn-primary btn-update-now', textContent: 'Update Now' });
    updateNowBtn.addEventListener('click', function () {
        installUpdateFromBanner(banner);
    });

    banner.appendChild(text);
    banner.appendChild(updateNowBtn);

    document.body.insertBefore(banner, document.body.firstChild);
}

async function installUpdateFromBanner(banner) {
    var textEl = banner.querySelector('.update-banner-text');
    if (textEl) {
        clearChildren(textEl);
        textEl.appendChild(document.createTextNode('Updating...'));
    }

    try {
        var res = await fetch('/update', { method: 'POST' });
        var data = await res.json();

        if (data.status === 'ok' && data.updated) {
            // Show restart notice — do NOT auto-dismiss
            if (textEl) {
                clearChildren(textEl);
                textEl.appendChild(document.createTextNode(
                    'Update applied! Please restart the server to activate changes.'
                ));
            }
            var nowBtn = banner.querySelector('.btn-update-now');
            if (nowBtn) nowBtn.remove();
        } else if (data.status === 'ok') {
            if (textEl) {
                clearChildren(textEl);
                textEl.appendChild(document.createTextNode(data.message || 'Already up to date.'));
            }
            setTimeout(function () { if (banner.parentNode) banner.remove(); }, 3000);
        } else {
            if (textEl) {
                clearChildren(textEl);
                textEl.appendChild(document.createTextNode('Update failed: ' + (data.message || 'unknown error')));
            }
        }
    } catch (e) {
        if (textEl) {
            clearChildren(textEl);
            textEl.appendChild(document.createTextNode('Update failed.'));
        }
    }
}

// =============================================================================
// 14. CLARIFICATION FLOW
// =============================================================================

function showClarificationModal(flaggedItems) {
    var container = document.getElementById('clarify-items');
    if (!container) return;
    clearChildren(container);

    flaggedItems.forEach(function (item) {
        var itemDiv = el('div', { className: 'clarify-item' });

        itemDiv.appendChild(el('span', { className: 'clarify-req-id', textContent: item.id || item.req_id || '' }));
        itemDiv.appendChild(el('p', { className: 'clarify-req-text', textContent: item.text || '' }));
        itemDiv.appendChild(el('p', { className: 'clarify-issue', textContent: 'Issue: ' + (item.issue || item.problem || '') }));

        if (item.suggestion) {
            itemDiv.appendChild(el('p', { className: 'clarify-suggestion', textContent: 'Suggestion: ' + item.suggestion }));
        }

        itemDiv.appendChild(el('label', { textContent: 'Your clarification:' }));

        var input = document.createElement('input');
        input.type = 'text';
        input.className = 'clarify-input';
        input.placeholder = item.suggestion || 'Enter clarification...';
        input.setAttribute('data-req-id', item.id || item.req_id || '');
        itemDiv.appendChild(input);

        container.appendChild(itemDiv);
    });

    document.getElementById('clarify-modal').style.display = '';
}

function submitClarifications() {
    var inputs = document.querySelectorAll('#clarify-items .clarify-input');
    var clarifications = {};
    inputs.forEach(function (input) {
        var reqId = input.getAttribute('data-req-id');
        var value = input.value.trim();
        if (reqId && value) {
            clarifications[reqId] = value;
        }
    });

    document.getElementById('clarify-modal').style.display = 'none';
    proceedGenerate(clarifications);
}

// =============================================================================
// 15. TOAST NOTIFICATIONS
// =============================================================================

function _formatElapsed(seconds) {
    if (seconds < 60) return seconds + 's';
    var m = Math.floor(seconds / 60);
    var s = seconds % 60;
    return m + 'm ' + (s < 10 ? '0' : '') + s + 's';
}

function _startElapsedUpdater() {
    if (_elapsedInterval) return; // already running
    _elapsedInterval = setInterval(function () {
        var anyRunning = false;
        Object.keys(_stageTimers).forEach(function (stage) {
            var timer = document.getElementById('timer-' + stage);
            if (timer) {
                var elapsed = Math.round((Date.now() - _stageTimers[stage]) / 1000);
                timer.textContent = _formatElapsed(elapsed);
                anyRunning = true;
            }
        });
        if (!anyRunning) {
            clearInterval(_elapsedInterval);
            _elapsedInterval = null;
        }
    }, 1000);
}

function _stopAllTimers() {
    _stageTimers = {};
    if (_elapsedInterval) {
        clearInterval(_elapsedInterval);
        _elapsedInterval = null;
    }
}

function showToast(message, type) {
    type = type || 'info';
    var toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    toast.textContent = message;
    document.getElementById('toast-container').appendChild(toast);
    setTimeout(function () { toast.remove(); }, 4000);
}

function showErrorPopup(title, detail) {
    // Remove any existing error popup
    var existing = document.getElementById('error-popup-overlay');
    if (existing) existing.remove();

    var overlay = el('div', { className: 'modal-overlay', id: 'error-popup-overlay' });
    var modal = el('div', { className: 'modal error-modal' });

    // Header
    var header = el('div', { className: 'error-modal-header' });
    var icon = el('span', { className: 'error-modal-icon', textContent: '\u26a0' });
    var titleEl = el('h3', { className: 'error-modal-title', textContent: title || 'Error' });
    header.appendChild(icon);
    header.appendChild(titleEl);
    modal.appendChild(header);

    // Detail text
    var detailEl = el('div', { className: 'error-modal-detail' });
    // Split long error messages into readable lines
    var lines = String(detail || 'An unknown error occurred.').split(/[.!]\s+/);
    lines.forEach(function (line) {
        line = line.trim();
        if (!line) return;
        var p = el('p', { textContent: line + (line.endsWith('.') ? '' : '.') });
        detailEl.appendChild(p);
    });
    modal.appendChild(detailEl);

    // Tip
    var tip = el('div', { className: 'error-modal-tip' });
    tip.appendChild(el('span', { textContent: 'Tip: ', style: 'color: #7c7cff; font-weight: 500;' }));
    tip.appendChild(document.createTextNode('Try a different model in Settings, or reduce the number of selected layers.'));
    modal.appendChild(tip);

    // Close button
    var btnRow = el('div', { className: 'modal-actions' });
    var closeBtn = el('button', { className: 'btn-modal-primary', textContent: 'Dismiss' });
    closeBtn.addEventListener('click', function () { overlay.remove(); });
    btnRow.appendChild(closeBtn);
    modal.appendChild(btnRow);

    // Close on overlay click
    overlay.addEventListener('click', function (e) {
        if (e.target === overlay) overlay.remove();
    });

    overlay.appendChild(modal);
    document.body.appendChild(overlay);
}

// =============================================================================
// 16. COVERAGE INDICATOR (Feature 5)
// =============================================================================

function renderCoverageIndicator() {
    var indicator = document.getElementById('coverage-indicator');
    if (!indicator) return;
    clearChildren(indicator);

    if (!currentModel || !currentModel.requirements || !currentModel.links) {
        indicator.style.display = 'none';
        return;
    }

    var totalReqs = currentModel.requirements.length;
    if (totalReqs === 0) {
        indicator.style.display = 'none';
        return;
    }

    var linkedReqIds = new Set();
    currentModel.links.forEach(function(link) {
        currentModel.requirements.forEach(function(req) {
            if (link.target === req.id || link.source === req.id) {
                linkedReqIds.add(req.id);
            }
        });
    });
    var covered = linkedReqIds.size;
    var pct = Math.round((covered / totalReqs) * 100);

    indicator.style.display = '';

    var label = el('span', { className: 'coverage-label', textContent: 'Requirement Coverage' });
    var stats = el('span', { className: 'coverage-stats', textContent: covered + '/' + totalReqs + ' (' + pct + '%)' });
    var barTrack = el('div', { className: 'coverage-bar-track' });
    var barFill = el('div', { className: 'coverage-bar-fill' });
    barFill.style.width = pct + '%';
    if (pct === 100) barFill.classList.add('full');
    barTrack.appendChild(barFill);

    indicator.appendChild(label);
    indicator.appendChild(stats);
    indicator.appendChild(barTrack);

    // Show uncovered requirements as clickable list
    var uncovered = currentModel.requirements.filter(function(req) {
        return !linkedReqIds.has(req.id);
    });

    if (uncovered.length > 0) {
        var toggle = el('button', { className: 'coverage-toggle', textContent: uncovered.length + ' uncovered \u25be' });
        var detailsDiv = el('div', { className: 'coverage-details', style: 'display:none' });

        uncovered.forEach(function(req) {
            var row = el('div', { className: 'coverage-uncovered-row' });
            var idSpan = el('span', { className: 'coverage-uncovered-id', textContent: req.id });
            var textSpan = el('span', { className: 'coverage-uncovered-text', textContent: req.text });
            textSpan.title = req.text;
            row.appendChild(idSpan);
            row.appendChild(textSpan);
            detailsDiv.appendChild(row);
        });

        toggle.addEventListener('click', function() {
            var showing = detailsDiv.style.display !== 'none';
            detailsDiv.style.display = showing ? 'none' : '';
            toggle.textContent = uncovered.length + ' uncovered ' + (showing ? '\u25be' : '\u25b4');
        });

        indicator.appendChild(toggle);
        indicator.appendChild(detailsDiv);
    }
}

// =============================================================================
// 17. UTILITY FUNCTIONS
// =============================================================================

function formatCost(amount) {
    if (typeof amount !== 'number') amount = parseFloat(amount) || 0;
    if (amount === 0) return '$0.00';
    if (amount < 0.001) return '$' + amount.toFixed(6);
    if (amount < 0.01) return '$' + amount.toFixed(4);
    return '$' + amount.toFixed(4);
}

function formatTokens(count) {
    if (typeof count !== 'number') count = parseInt(count) || 0;
    return count.toLocaleString();
}

function copyToClipboard(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function () {
            showToast('Copied to clipboard.', 'success');
        }).catch(function () {
            _fallbackCopy(text);
        });
    } else {
        _fallbackCopy(text);
    }
}

function _fallbackCopy(text) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.top = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    try {
        document.execCommand('copy');
        showToast('Copied to clipboard.', 'success');
    } catch (e) {
        showToast('Could not copy to clipboard.', 'error');
    }
    ta.remove();
}

// Safe DOM element creator — all text set via textContent, never innerHTML
function el(tag, attrs, children) {
    var elem = document.createElement(tag);
    if (attrs) {
        Object.keys(attrs).forEach(function (key) {
            if (key === 'textContent') {
                elem.textContent = attrs[key];
            } else if (key === 'className') {
                elem.className = attrs[key];
            } else if (key === 'onclick') {
                elem.addEventListener('click', attrs[key]);
            } else if (key === 'style') {
                elem.setAttribute('style', attrs[key]);
            } else {
                elem.setAttribute(key, attrs[key]);
            }
        });
    }
    if (children) {
        children.forEach(function (child) {
            if (typeof child === 'string') {
                elem.appendChild(document.createTextNode(child));
            } else if (child) {
                elem.appendChild(child);
            }
        });
    }
    return elem;
}

// Safe way to empty a DOM node without innerHTML
function clearChildren(node) {
    while (node.firstChild) {
        node.removeChild(node.firstChild);
    }
}
