# Expense Bot Agent Guide

## Purpose

This repository contains a Telegram finance bot and a React web dashboard. Most interactive bot logic lives under `finance-bot/`. The web dashboard lives at the project root (`src/`).

Primary backend stack:
- FastAPI
- Firestore
- Telegram Bot API
- Python tests via `unittest`

Frontend stack (web dashboard):
- React 19 + TanStack Router
- Vite + Tailwind CSS v4 + shadcn/ui
- Deployed via Firebase Hosting

## Repo Focus

When working on backend bot behavior, prefer these paths first:
- `finance-bot/routers/webhook.py` — Telegram message and callback_query handler
- `finance-bot/routers/reports.py` — scheduled report endpoint (daily/weekly/monthly)
- `finance-bot/routers/dashboard.py` — web dashboard REST API (auth, transactions, categories, budgets)
- `finance-bot/services/firestore.py` — all Firestore reads and writes
- `finance-bot/services/categoriser.py` — expense categorisation and pending flow
- `finance-bot/services/telegram.py` — Telegram API wrappers and keyboard builders
- `finance-bot/services/interaction_sessions.py` — shared multi-step flow state
- `finance-bot/services/payment_plans.py` — recurring/split payment calculations
- `finance-bot/services/plan_manager.py` — payment plan lifecycle and due-plan processing
- `finance-bot/services/dashboard_auth.py` — password hashing and session token management
- `finance-bot/services/category_migration.py` — one-off category data migration helpers
- `finance-bot/models/`
- `finance-bot/tests/`

When working on one-off data scripts, work inside `scripts/`:
- `scripts/migrate_category_collections.py` — migrates legacy category docs into user subcollections
- `scripts/clone_category_collections.py` — copies categories from one user to another

When working on the web dashboard, work inside `src/`:
- `src/routes/index.tsx` — main dashboard page and sign-in screen
- `src/lib/dashboard-api.ts` — API client (auth, transactions, categories, budgets)
- `src/lib/dashboard-analytics.ts` — analytics helpers

Do not assume the React dashboard and the Telegram backend share the same runtime or state model.

## Interactive Flow Policy

Any new command or feature that waits for a later user reply or button click must use `finance-bot/services/interaction_sessions.py`.

Do not implement expiration ad hoc with raw timestamps, custom pending collections, or callback-specific timeout logic unless explicitly modifying legacy code.

Any new multi-step flow must include:
- expiry behavior
- cleanup behavior for expired state
- tests that verify expiry

If a feature needs a different timeout from the default, make that an explicit argument to the shared session helper. Do not hard-code a separate timeout check in the handler.

## Legacy Flow Rule

This codebase still contains older flows that use:
- `set_user_state(...)`
- `save_pending_*`
- callback timestamps

Do not copy those patterns into new features.

If touching a legacy flow:
- prefer migrating it toward `interaction_sessions`
- if full migration is too large, keep the change scoped and preserve current behavior

## Command Design Rules

For any new Telegram command:
- decide whether it is immediate or delayed
- if immediate, no expiry handling is needed
- if delayed, it must use the shared session path

Examples of delayed interactions:
- asking the user for another message later
- sending inline buttons that remain actionable
- multi-step setup or edit flows

## Payment Plan Rules

Payment plan logic is split across two services:

- `payment_plans.py` — pure calculations (due dates, split amounts, occurrence keys). No Firestore, no Telegram. Testable in isolation.
- `plan_manager.py` — orchestration: creates plans in Firestore, posts first charges, processes due plans, handles rewrites.

When modifying plan behavior, keep calculations in `payment_plans.py` and side effects in `plan_manager.py`.

Plan creation is a multi-step flow. The in-progress state lives in `users/{chat_id}/pending_plans` (a legacy collection predating `interaction_sessions`). Do not migrate it unless that is the explicit goal of the task.

## Testing Rules

For backend changes, add or update focused tests in `finance-bot/tests/`.

Minimum expectation for new multi-step flows:
- happy path test
- expiry test

Before finishing backend work, run relevant tests from `finance-bot/`:

```powershell
python -m unittest
```

If the full suite is too broad, run the affected test modules and state exactly what was run.

## Data and Time Rules

Keep these concepts separate:
- business timestamp: when a transaction happened
- flow timestamp: when an interactive session started
- session expiry: when a delayed interaction should stop being valid

Never use a user-entered transaction date as the creation time for an expiring interaction.

## Firestore Rules

Do not introduce a new Firestore collection for temporary interactive state unless there is a strong reason that `interaction_sessions` cannot represent it.

Prefer extending shared session payload over creating one-off pending documents.

## Change Discipline

Keep changes scoped.

Do not perform unrelated refactors while fixing a bot command or flow unless the refactor is required for correctness.

If you add a helper, make sure it reduces duplication that already exists in the repo.

## Environments

GCP project: `budget-bot-123`

Every resource is paired: one for production, one for development. They are fully isolated — different Cloud Run services, different Firestore databases, different hosting URLs, and different git branches. **Never mix them.**

| Resource | Production (`main` branch) | Development (`development` branch) |
|---|---|---|
| Cloud Run service | `finance-bot` | `finance-bot-dev` |
| Cloud Run URL | `https://finance-bot-jrpmzkxwoa-as.a.run.app` | `https://finance-bot-dev-jrpmzkxwoa-as.a.run.app` |
| Firestore database | `(default)` | `developer` |
| Firebase Hosting | `https://budget-bot-123.web.app` | `https://budget-bot-123-dev.web.app` |

All resources are in region `asia-southeast1`.

### Branch Check Before Starting Work

**Before making any changes**, check which branch is currently active:

```powershell
git branch --show-current
```

- If it is `development` — proceed normally; all changes target the dev environment.
- If it is `main` — stop and confirm with the user before doing anything. Production changes must be intentional.
- If it is any other branch — ask the user which environment they intend to target before proceeding.

Never assume the user is on the correct branch. If there is any doubt, ask.

### Default Environment is Dev

When the user asks to deploy, test, or make changes without specifying an environment, **always default to dev**. Only target production when the user explicitly says "prod", "production", or "main".

This applies to:
- Firebase Hosting deploys — default to `hosting:dev`
- Backend changes — default to committing/pushing to `development`
- Any Firestore operation that targets a specific database — default to `developer`
- Any reference to a Cloud Run URL — default to the dev URL

If a request is ambiguous (e.g. "deploy this" or "push the changes"), confirm: _"Deploy to dev or prod?"_ before proceeding.

### Deployment Rules

**Cloud Run — never deploy manually.** Cloud Run is deployed exclusively by Cloud Build on git push. Do not run `gcloud run deploy`. To deploy backend changes:
- Dev: commit and push to `development`
- Prod: commit and push to `main` (confirm with user first)

**React web dashboard — always deploy to dev unless told otherwise.**

```powershell
# Build from the project root
npm run build

# Deploy to dev (default)
firebase deploy --only hosting:dev

# Deploy to prod — only when explicitly instructed
firebase deploy --only hosting:prod
```

If a prod deploy fails with a Firebase uploader `paths[1] undefined` error, delete the stale hosting cache and rebuild:

```powershell
Remove-Item .firebase\hosting.*.cache -ErrorAction SilentlyContinue
npm run build
firebase deploy --only hosting:prod
```

### Environment Isolation Rules

- Never point dev code at the `(default)` Firestore database or the production Cloud Run URL.
- Never push to `main` as part of a dev-cycle change — only when explicitly merging a tested feature to production.
- Never deploy to `hosting:prod` unless the user has said "production" or "prod" in that request.
