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

> ⚠️ **Push triggering is currently broken.** As of 2026-08-17 a push to either branch creates
> no build — the triggers are ENABLED and correct, but the GitHub App webhook stopped
> delivering (last webhook-fired builds: 2026-07-20). Until it is reconnected, start the build
> yourself with `gcloud builds triggers run <trigger-name> --branch=<branch>`, which runs the
> identical pipeline. Then confirm the live revision actually moved:
> `gcloud run services describe finance-bot --region=asia-southeast3 --format="value(metadata.labels.commit-sha)"`

**To change deployment config**: update the Cloud Build trigger settings in the GCP Console (project `budget-bot-123`). The triggers are `global`, not regional; they deploy Cloud Run into `asia-southeast3` via the trigger's `_DEPLOY_REGION` substitution. Do not add a `cloudbuild.yaml` unless you need to change the build steps.

---

## Cloud Scheduler — Report Triggers

**What it is**: Cloud Scheduler jobs that POST to the `finance-bot` Cloud Run service to generate spending reports. They live in `--location=asia-southeast1` and their cron is stored in the `Asia/Singapore` time zone (not UTC).

| Job | Schedule (SGT) | Endpoint |
|---|---|---|
| `finance-bot-reports` | `0 22 * * *` — 10 PM daily | `POST /trigger-report?period=auto` |
| `finance-bot-monthly` | `0 0 1 * *` — midnight, 1st of month | `POST /trigger-report?period=monthly` |

**Why `auto`**: Cloud Scheduler's free tier covers only 3 jobs per billing account. The daily and weekly reports already fired at the same minute, so they were merged into one job. `period=auto` resolves at request time via `_resolve_auto_periods()` — always daily, plus weekly on Sundays. Each period is still sent as its own Telegram message, so users see no difference. Monthly is deliberately excluded from `auto` because it still has its own job.

**Budget upkeep**: with `finance-bot-recurring` (below) this is 3 jobs — exactly the free-tier limit. Adding a fourth job starts incurring charges, so prefer folding new periods into `auto` over creating jobs.

**Auth**: each request includes the header `X-Scheduler-Token: <SCHEDULER_SECRET>`. The backend rejects requests without a matching secret.

**Handler**: `finance-bot/routers/reports.py` — `POST /trigger-report`

**To add a new report period**: add the period to `_get_period_window()`, then add it to `_resolve_auto_periods()` so it rides the existing job. Only create a new Cloud Scheduler job if the period genuinely needs a different fire time — and remember it will push you past the free tier.

---

## Cloud Scheduler — Payment Plan Processor

**What it is**: `finance-bot-recurring` (`0 8 * * *` SGT) triggers due payment plan processing. Calls `plan_manager.process_due_plans()`, which queries all active payment plans with a `next_due_date` on or before today and posts the installment as a transaction.

Kept as its own job rather than merged into `finance-bot-reports`: it posts real charges, and Cloud Scheduler retries the whole endpoint on failure, so a failing report should never be able to re-run payment processing.

**Handler**: `finance-bot/routers/reports.py` — `POST /trigger-recurring-payments`

**Logic lives in**: `finance-bot/services/plan_manager.py` — `process_due_plans()`

**To extend**: if a new plan type is added, update `plan_occurrence_for_index()` in `payment_plans.py` and `process_due_plans()` in `plan_manager.py`.

---

## Telegram Bot — Webhook Agent

**What it is**: The FastAPI webhook handler that acts as the primary user-facing agent. Telegram calls `POST /webhook` for every message or button tap from an authorised user.

**Entry point**: `finance-bot/routers/webhook.py`

**Authorisation**: only processes updates from chat IDs present in the `authorized_chats`
Firestore collection (document ID = chat ID). `firestore.start_authorized_chats_listener()`
attaches an `on_snapshot` listener at startup, so adding or removing a chat takes effect
immediately without a redeploy. All other updates are silently dropped.
`TELEGRAM_CHAT_IDS` is **not** used — nothing in the codebase reads it.

**Update types handled**:

| Type | Trigger | Flows |
|---|---|---|
| `message` — expense text | User sends `Coffee $10` | Parser → categoriser → save or category prompt |
| `message` — bot command | See the command table below | Various immediate and multi-step flows |
| `message` — free text (in flow) | Reply during an active session | Routes to active `interaction_sessions` flow handler |
| `callback_query` | User taps an inline keyboard button | Category selection, plan actions, edit confirmations, report date picks |

**Commands** (dispatch chain starts at `webhook.py:2084`):

| Area | Commands |
|---|---|
| Start | `/start` |
| Reports | `/daily`, `/weekly`, `/monthly`, `/budget_report` |
| Income | `/income` |
| Goals | `/goals`, `/new_goal`, `/edit_goal`, `/delete_goal` |
| Projects | `/projects`, `/new_projects`, `/edit_projects`, `/delete_projects` |
| Budgets | `/set_budget`, `/remove_budget`, `/list_budget` |
| Categories | `/new_category`, `/edit_category`, `/remove_category` |
| Deleting expenses | `/delete_last`, `/delete_today`, `/delete_past` |
| Recurring plans | `/set_recurring`, `/list_recurring`, `/edit_recurring`, `/delete_recurring` |
| Split payments | `/split_payment`, `/list_split_payment`, `/edit_split_payment`, `/delete_split_payment` |
| Dashboard account | `/create_account`, `/change_password` |

There is no `/help`, `/delete`, `/edit`, `/categories`, `/budget`, `/plans`, `/report`, or
`/setup` — earlier revisions of this document listed those, but they were never implemented.

**Multi-step flows** (managed by `interaction_sessions`, default expiry 180s):
- `dashboard_account` — creates a web dashboard login (username → password → confirm)
- `set_budget` — sets a monthly budget for a category (category → amount)
- `inflow` — records an income entry, optionally tagged to a goal or project
- `new_goal` / `edit_goal` / `delete_goal` — savings goal lifecycle
- `new_project` / `edit_project` / `delete_project` — long-term project lifecycle

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
1. `POST /dashboard/auth/login` — verifies credentials, creates a 24-hour session doc in `web_sessions` (`SESSION_TTL = timedelta(days=1)`), returns a token
2. Every authenticated request reads the token from the `X-Dashboard-Session` header, looks up the session in Firestore, and checks expiry
3. `POST /dashboard/auth/logout` — deletes the session doc

The router mounts at `prefix="/dashboard"`, so every route below is reachable at
`/dashboard/<path>`: `auth/login`, `auth/logout`, `auth/session`, `bootstrap`, `transactions`,
`inflows`, `categories`, `budgets`, `goals`, `projects`, `plans`, `preferences`.

Passwords are stored as `pbkdf2_sha256` hashes; session tokens are stored as a plain SHA-256
digest of the token (`dashboard_auth.py:69`).

**Session storage**: `web_sessions` Firestore collection (token is stored as a SHA-256 hash).

---

## Claude Code Agents (.agents/)

The `.agents/` directory contains Claude Code skill definitions used during development.

| Skill | Purpose |
|---|---|
| `frontend-design` | Generates production-grade React/UI code with strong aesthetic direction |

Skills are invoked via `/frontend-design` in a Claude Code session. They are development-time tools only — they do not run at deploy time or in production.

## Editing rules

After a feature is requested or edited, if user doesn't specific if its for the telegram bot or web app only, do it for both.

### Deployment Rules

**Accounts**
- Check Firebase and Google Cloud CLI account should be techie.projects3@gmail.com

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