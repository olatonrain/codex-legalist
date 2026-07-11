# MEMORY — Codex legalist

## Last Session
2026-07-11 (session 3) — Phase 4 module split completed successfully using `acorn` AST-based extraction. `static/app.js` split into 6 files (state.js, transcript.js, evidence.js, jury.js, ui.js, app.js entry point). `<script type="module">` in index.html.

## Done
- **Phase 4 — Module Split (AST-based):**
  - Wrote `_acorn_split.mjs` using `acorn` parser: walks AST to classify each top-level statement → state.js, transcript.js, evidence.js, jury.js, or ui.js
  - Page-range extraction: each statement "owns" lines from its start to the next statement, preserving trailing comments in the correct module
  - Generated 5 clean module files (all pass `node --check`):
    - `state.js` (254 lines): State object, globals, helpers, constants, theme IIFE
    - `transcript.js` (174 lines): transcript management functions
    - `evidence.js` (150 lines): evidence display functions
    - `jury.js` (539 lines): jury grid, verdict charts, deliberation, insight functions
    - `ui.js` (2315 lines): all remaining UI functions
  - Rewrote `app.js` (59 lines) as ES module entry point: imports from all modules, exposes globals (`window.State`, `window.showToast`, etc.), registers `DOMContentLoaded` bootstrap
  - `index.html` updated to `<script type="module" src="/static/app.js">`
  - All named imports resolve correctly; zero missing export errors
- **Counsel Insights** (from session 2): 4 insight functions migrated to jury.js, wired via entry point bootstrap
- All 118 tests pass; zero ruff lint errors; all frontend JS valid

## Decisions
- Use `acorn` for AST-based extraction instead of regex brace-matching — reliable handling of template literals, nested braces, comments
- **Page-range attribution**: each top-level statement owns lines from its first line to the line before the next statement (regardless of module), so trailing comments follow the preceding function
- All module files kept in `static/` next to `app.js` entry point — no subdirectory
- No barrel re-exports — each module directly imports from its dependents

## Next Steps
- Phase 8 (optional): Playwright E2E test for main trial + insight flow
- Commit and push to GitHub

## Blockers & Open Questions
- (none)
