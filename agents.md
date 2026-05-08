# Automated Agents

This project runs several automated agents across GCP and Telegram. This document describes what each agent does, when it runs, and how to change it.

---

## Cloud Build — Continuous Deployment

**What it is**: GCP Cloud Build triggers that deploy the FastAPI backend to Cloud Run automatically on every git push.

**Triggers**:
| Branch | Cloud Run Service | Firestore DB |
|---|---|---|
| `development` | `finance-bot-dev` | `developer` |
| `main` | `finance-bot` | `(default)` |

**How it works**: Cloud Build reads the `Dockerfile` in `finance-bot/` and deploys a new Cloud Run revision. No manual `gcloud run deploy` is ever needed.

**To change deployment config**: update the Cloud Build trigger settings in the GCP Console (project `budget-bot-123`, region `asia-southeast1`). Do not add a `cloudbuild.yaml` unless you need to change the build steps.

---

## Cloud Scheduler — Report Triggers

**What it is**: Three Cloud Scheduler jobs that POST to the `finance-bot` Cloud Run service to generate spending reports.

| Job | Schedule (UTC) | SGT equivalent | Endpoint |
|---|---|---|---|
| `finance-bot-daily` | `0 13 * * *` | 9 PM daily | `POST /trigger-report?period=daily` |
| `finance-bot-weekly` | `0 1 * * 1` | 9 AM Monday | `POST /trigger-report?period=weekly` |
| `finance-bot-monthly` | `0 1 1 * *` | 9 AM 1st of month | `POST /trigger-report?period=monthly` |

**Auth**: each request includes the header `X-Scheduler-Token: <SCHEDULER_SECRET>`. The backend rejects requests without a matching secret.

**Handler**: `finance-bot/routers/reports.py` — `POST /trigger-report`

**To add a new report period**: add the period to the handler's `_get_period_window()` function, create the Cloud Scheduler job via `gcloud scheduler jobs create`, and add the corresponding `X-Scheduler-Token` header to the job config.

---

## Cloud Scheduler — Payment Plan Processor

**What it is**: A scheduler job that triggers due payment plan processing. Calls `plan_manager.process_due_plans()`, which queries all active payment plans with a `next_due_date` on or before today and posts the installment as a transaction.

**Handler**: `finance-bot/routers/reports.py` (or a dedicated endpoint — check current `main.py` for the exact route).

**Logic lives in**: `finance-bot/services/plan_manager.py` — `process_due_plans()`

**To extend**: if a new plan type is added, update `plan_occurrence_for_index()` in `payment_plans.py` and `process_due_plans()` in `plan_manager.py`.

---

## Telegram Bot — Webhook Agent

**What it is**: The FastAPI webhook handler that acts as the primary user-facing agent. Telegram calls `POST /webhook` for every message or button tap from an authorised user.

**Entry point**: `finance-bot/routers/webhook.py`

**Authorisation**: only processes updates from chat IDs listed in `TELEGRAM_CHAT_IDS`. All others are silently dropped.

**Update types handled**:

| Type | Trigger | Flows |
|---|---|---|
| `message` — expense text | User sends `Coffee $10` | Parser → categoriser → save or category prompt |
| `message` — bot command | `/start`, `/delete`, `/edit`, `/categories`, `/budget`, `/plans`, `/report`, `/setup` | Various immediate and multi-step flows |
| `message` — free text (in flow) | Reply during an active session | Routes to active `interaction_sessions` flow handler |
| `callback_query` | User taps an inline keyboard button | Category selection, plan actions, edit confirmations, report date picks |

**Multi-step flows** (managed by `interaction_sessions`):
- `dashboard_account` — creates a web dashboard login (username → password → confirm)
- `set_budget` — sets a monthly budget for a category (category → amount)

**Legacy flows** (use older `pending` / `pending_change` collections):
- Category selection for unknown expenses (`pending` collection)
- Transaction editing (`pending_change` collection)
- Payment plan creation (`pending_plans` subcollection)

Do not copy legacy patterns into new flows. New flows must use `interaction_sessions`.

---

## Web Dashboard Session Agent

**What it is**: Stateless session management baked into the dashboard API. Not a background agent — runs inline on every dashboard API request.

**Handler**: `finance-bot/routers/dashboard.py`

**Session lifecycle**:
1. `POST /dashboard/login` — verifies credentials, creates a 24-hour session doc in `web_sessions`, returns a token
2. Every authenticated request reads the token from the `X-Dashboard-Session` header, looks up the session in Firestore, and checks expiry
3. `POST /dashboard/logout` — deletes the session doc

**Session storage**: `web_sessions` Firestore collection (token is stored as a SHA-256 hash).

---

## Claude Code Agents (.agents/)

The `.agents/` directory contains Claude Code skill definitions used during development.

| Skill | Purpose |
|---|---|
| `frontend-design` | Generates production-grade React/UI code with strong aesthetic direction |

Skills are invoked via `/frontend-design` in a Claude Code session. They are development-time tools only — they do not run at deploy time or in production.
