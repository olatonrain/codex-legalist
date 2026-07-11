"use strict";
// ── Entry point — imports all modules and exposes globals ──

import { State, showToast, escapeHtml, toggleTheme } from './state.js';
import {
    clearTranscript, addTranscriptEntry, addSystemMessage,
    streamLines, importTranscriptFromGraphState, handleEvidenceFromEntry,
    syncEvidenceFromState, exportTranscript,
} from './transcript.js';
import { renderEvidenceBoard, renderObjectionHistory, renderClerkSummary,
    renderMotionRulings, renderDiscoverySummary } from './evidence.js';
import {
    buildLiveDeliberationSnapshot, renderShadowJuryConversation,
    renderVerdictView, renderVerdictCharts, renderJuryGrid,
    renderDeliberationView, renderConsensusRows, renderDeliberationTranscript,
    renderCaseRecordSummary, renderMiniChart, renderInsightResults,
    requestInsights, toggleInsightExpand, initInsightButtons,
} from './jury.js';
import * as UI from './ui.js';

// ── Expose globals for inline onclick= handlers in innerHTML ──
window.deleteTrial = UI.deleteTrial;
window.loadTrialById = UI.loadTrialById;
window.replaySavedTrial = UI.replaySavedTrial;
window.deleteDocketEntry = UI.deleteDocketEntry;
window.clearCaseDocket = UI.clearCaseDocket;
window.saveTrialToDocket = UI.saveTrialToDocket;
window.toggleInsightExpand = toggleInsightExpand;
window.State = State;
window.showToast = showToast;
window.escapeHtml = escapeHtml;

// ── Bootstrap ──
document.addEventListener('DOMContentLoaded', () => {
    UI.initTabs();
    UI.initBottomTimeline();
    UI.initDrawers();
    UI.initSpeedSlider();
    UI.initSetupForm();
    UI.initCaseTabs();
    UI.initDemoButtons();
    UI.initNavActions();
    UI.initBenchmarkButtons();
    initInsightButtons();
    UI.loadJurisdictions();
    renderMiniChart();
    renderJuryGrid();
    renderDeliberationView();
    UI.updateExportControls();
    UI.checkApiHealth();
    UI.renderCaseDocket();
    UI.switchView('dashboard');
});

// ── Theme toggle ──
document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('themeToggle');
    if (btn) btn.addEventListener('click', toggleTheme);
});
