# Frontend Migration Todo

This file tracks the Flutter web dashboard migration to the React app currently in `lovable/`.

## Goal

Make `lovable/` the new web dashboard frontend for `Expense Bot`, backed by the existing dashboard API and Firebase Hosting targets. Keep the Flutter frontend as the reference implementation until React reaches parity.

## Status Legend

- `[x]` done
- `[-]` in progress
- `[ ]` pending

## Phase 0: Audit and Planning

- [x] Inspect the downloaded `lovable/` app structure and dependency stack.
- [x] Identify the current Flutter dashboard API contract and environment-selection rules.
- [x] Create a persistent migration tracker in the repo.

## Phase 1: React App Foundation

- [x] Add a shared React dashboard API client with:
  - backend base URL selection for dev/prod hosting
  - session-aware requests
  - typed helpers for auth, transactions, categories, and budgets
- [x] Add shared dashboard analytics helpers for date presets, category filters, and summaries.
- [x] Replace Lovable mock data in `lovable/src/routes/index.tsx` with real backend-backed state.
- [x] Add auth gate behavior:
  - session bootstrap on load
  - sign-in form
  - logout flow

## Phase 2: First Live Screens

- [x] Rebuild the analytics-first dashboard against real data.
- [x] Rebuild transactions view against real data.
- [x] Rebuild categories and budget summary sections against real data.
- [-] Preserve the current desired analytics UX:
  - category multi-select
  - date presets
  - custom date range picker
  - straight line chart with visible points

## Phase 3: Cutover Readiness

- [x] Update Firebase Hosting config to serve the React build output instead of Flutter `build/web`.
- [x] Replace the Flutter web deploy script with a React build + deploy flow.
- [x] Verify dev hosting points at the dev backend.
- [x] Test login/session flow on dev hosting.

## Phase 4: Flutter Retirement

- [-] Reach feature parity for the required dashboard flows.
- [ ] Decide whether to archive or remove the Flutter web frontend.
- [ ] Update repo docs to reflect the new frontend stack and deployment flow.

## Current Checkpoint

Prod and dev hosting both now serve `lovable/dist` (React build). The Flutter `build/web` output is no longer deployed anywhere.

Remaining work:
- Analytics UX refinement (category multi-select, date presets, chart polish) is in progress.
- Flutter frontend still exists in `lib/` and `build/web` — retirement decision pending.
