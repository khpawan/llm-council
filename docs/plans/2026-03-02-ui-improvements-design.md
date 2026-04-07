# UI Improvements Design — Settings, Export, UX Flow

**Date:** 2026-03-02
**Branch:** feature/azure-foundry-cli-council

## Goals

1. Full settings page to configure Azure Foundry models from the UI
2. Markdown export of council runs
3. Better UX: multi-turn conversations, per-query algorithm picker, stage-aware progress

## 1. Settings Page

**Route:** `#settings` (hash-based routing, no react-router dependency)
**Access:** Gear icon in sidebar header, next to "+ New Conversation"

### Form Sections

1. **Provider** — Toggle between OpenRouter and Azure Foundry
2. **Azure Foundry Connection** — Endpoint URL, API key (masked input), API version dropdown
3. **Deployments** — Dynamic list of deployment entries (name + model label). Add/remove rows. "Add deployment" button at bottom.
4. **Council Configuration** — Checkboxes to select which deployments are council members, dropdown to pick chairman from the same list.
5. **Defaults** — Default algorithm picker (6 options), ranking aggregation method (average_rank vs borda).

### Persistence

- Backend saves to `data/config.json` (not `.env`)
- On startup: load `config.json` if exists, fall back to `.env` values
- `reload_config()` function applies changes without restart
- API key masked in GET responses

### Backend Endpoints

- `GET /api/config` — Returns current config (key masked)
- `POST /api/config` — Validates and saves config
- `POST /api/config/test` — Pings one deployment to verify connectivity

## 2. Per-Query Algorithm Toolbar

**Position:** Horizontal bar between messages area and input textarea.

**Contents:**
- Algorithm dropdown — 6 options: peer_review, consensus_only, chairman_only, red_team, audience_split, claim_evidence
- Short helper text that updates based on selection

**Behavior:**
- Defaults to whatever was set in Settings
- Can be overridden per message
- Resets to default after each send
- Sent with API request via existing `algorithm` field

## 3. Multi-Turn Fix

- Keep input form visible at all times (currently disappears after first message)
- Each follow-up triggers a new council run within the same conversation

## 4. Stage-Aware Progress Indicators

Replace generic spinner with descriptive progress:
- "Stage 1: Collecting responses from 3 models..."
- "Stage 2: Peer review in progress..."
- "Stage 3: Chairman synthesizing final answer..."

## 5. Markdown Export

**Trigger:** "Export as Markdown" button in the header of each assistant message block.

**Contents of exported .md file:**
- Query and timestamp
- Algorithm used
- Stage 1: Each model's response under its own heading
- Stage 2: Each model's evaluation + parsed rankings + aggregate rankings table
- Stage 3: Final synthesized answer
- Metadata footer: models used, chairman, algorithm, ranking method

**Implementation:** Pure client-side — assemble markdown string from state, trigger blob download.
**Filename:** `council-run-YYYY-MM-DD-HHMMSS.md`

## 6. Architecture

### New Backend Files/Changes

- `backend/config.py` — Refactor: load from `config.json` first, `.env` fallback. Add `reload_config()`, `get_config_masked()`, `save_config()`.
- `backend/main.py` — Add 3 new endpoints: GET/POST `/api/config`, POST `/api/config/test`

### New Frontend Files

- `Settings.jsx` + `Settings.css` — Full settings page
- `AlgorithmToolbar.jsx` + `AlgorithmToolbar.css` — Dropdown + helper text
- `ExportButton.jsx` — Markdown assembly + download

### Frontend Changes

- `App.jsx` — Hash-based routing (`#settings` vs `#chat`), multi-turn input fix, algorithm state
- `api.js` — Add `getConfig()`, `saveConfig()`, `testConfig()`
- `ChatInterface.jsx` — Keep input visible, integrate toolbar, stage-aware progress
- `Sidebar.jsx` — Add gear icon for settings

### No New Dependencies

- Hash routing avoids react-router
- Export is pure JS string + blob download
