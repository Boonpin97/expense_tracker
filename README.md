# Telegram Finance Bot & Web Dashboard

A Telegram bot that tracks personal expenses with a React web dashboard for browsing and managing financial data.

Users send messages like `Coffee $10` and the bot categorises the expense, stores it in Firestore, tracks income against savings goals and projects, manages recurring payment plans, and sends daily, weekly, and monthly summaries.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Bot interface | Telegram Bot API (webhook mode) |
| Backend | FastAPI (Python), Cloud Run |
| Database | Google Cloud Firestore |
| Scheduler | Google Cloud Scheduler |
| Web dashboard | React 19 + TanStack Router + Vite + Tailwind CSS v4 + shadcn/ui |
| Hosting | Firebase Hosting (web dashboard) |
| CI/CD | Cloud Build (push-triggered — see the warning under [Deployment](#backend-cloud-run)) |

---

## Project Structure

```
expense_tracker/
├── finance-bot/                  # FastAPI backend (Telegram bot + dashboard API)
│   ├── main.py                   # App entry point, lifespan, CORS, router registration
│   ├── routers/
│   │   ├── webhook.py            # POST /webhook — handles all Telegram updates
│   │   ├── reports.py            # POST /trigger-report — called by Cloud Scheduler
│   │   └── dashboard.py          # /dashboard/* — web dashboard REST API
│   ├── services/
│   │   ├── firestore.py          # All Firestore read/write operations
│   │   ├── parser.py             # Parses freeform expense text into item + amount
│   │   ├── categoriser.py        # Category lookup, budget check, keyboard prompt flow
│   │   ├── telegram.py           # Telegram Bot API wrappers and keyboard builders
│   │   ├── interaction_sessions.py  # Shared multi-step flow state management
│   │   ├── payment_plans.py      # Recurring/split payment calculations
│   │   ├── plan_manager.py       # Payment plan lifecycle and due-plan processing
│   │   ├── dashboard_auth.py     # Web account password hashing and session tokens
│   │   └── category_migration.py # One-off category data migration helpers
│   ├── models/
│   │   └── transaction.py        # Pydantic models (Transaction, Inflow, Goal, Project, PaymentPlan, …)
│   ├── tests/                    # unittest test suite
│   ├── Dockerfile
│   └── requirements.txt
├── src/                          # React web dashboard
│   ├── routes/
│   │   ├── __root.tsx            # App shell
│   │   └── index.tsx             # Main dashboard + sign-in page
│   ├── lib/
│   │   ├── dashboard-api.ts      # API client (auth, transactions, categories, budgets)
│   │   └── dashboard-analytics.ts  # Date presets and aggregation helpers
│   ├── components/ui/            # shadcn/ui component library
│   └── styles.css
├── scripts/
│   ├── migrate_category_collections.py  # One-off category subcollection migration
│   ├── clone_category_collections.py   # Copy categories from one user to another
│   ├── deploy_dashboard_web.ps1        # Build + deploy the dashboard to a hosting target
│   └── generate_lovable_static_entry.ps1
├── public/
│   └── logo.png
├── firebase.json                 # Hosting config (prod + dev targets)
├── firestore.rules
├── firestore.indexes.json
├── package.json
└── vite.config.ts
```

---

## Environments

GCP project: `budget-bot-123`

| Resource | Production (`main`) | Development (`development`) |
|---|---|---|
| Cloud Run | `finance-bot` | `finance-bot-dev` |
| Cloud Run URL | `https://finance-bot-jrpmzkxwoa-eu.a.run.app` | `https://finance-bot-dev-jrpmzkxwoa-eu.a.run.app` |
| Firestore DB | `(default)` | `developer` |
| Firebase Hosting | `https://budget-bot-123.web.app` | `https://budget-bot-123-dev.web.app` |

Regions differ per service — Cloud Run is in `asia-southeast3`, while Cloud Scheduler
and both Firestore databases are in `asia-southeast1`. Cloud Build triggers are `global`.

---

## Environment Variables

The backend reads these at runtime (Cloud Run env vars or local `.env`):

```env
TELEGRAM_BOT_TOKEN=          # BotFather token
FIRESTORE_PROJECT_ID=        # GCP project ID (budget-bot-123)
FIRESTORE_DATABASE=          # Firestore database name: (default) for prod, developer for dev
CLOUD_RUN_URL=               # Full Cloud Run service URL (used for webhook registration)
SCHEDULER_SECRET=            # Shared secret — Cloud Scheduler sends this in X-Scheduler-Token
TELEGRAM_WEBHOOK_SECRET=     # Shared secret — Telegram sends this in X-Telegram-Bot-Api-Secret-Token
DASHBOARD_WEB_URL=           # Canonical dashboard URL (e.g. https://budget-bot-123.web.app)
DASHBOARD_WEB_ORIGINS=       # Comma-separated allowed CORS origins
DEV_MODE=                    # Truthy to relax dev-only behaviour
```

> **`TELEGRAM_CHAT_IDS` is no longer used.** Authorisation moved to Firestore — see
> [Authorisation](#authorisation) below. The variable still appears in `.env.example`
> and in Secret Manager for historical reasons, but nothing in the code reads it.

For local development, create `finance-bot/.env` and add a `serviceAccountKey.json` (Cloud Datastore User role) to authenticate Firestore.

---

## Local Development

### Backend

```powershell
cd finance-bot
pip install -r requirements.txt
uvicorn main:app --reload --port 8080
```

Run tests:

```powershell
cd finance-bot
python -m unittest discover -s tests      # 221 tests
python -m unittest tests.test_reports_router   # a single module
```

> Bare `python -m unittest` does **not** work here — there is no `tests/__init__.py`, so it
> discovers nothing and reports `NO TESTS RAN` while exiting 0. Always pass `discover -s tests`.

### Frontend

```powershell
npm install
npm run dev        # Vite dev server at http://localhost:5173
```

---

## Deployment

### Backend (Cloud Run)

Never run `gcloud run deploy`. Cloud Build owns all Cloud Run deployments:

- Push to `development` → deploys to `finance-bot-dev`
- Push to `main` → deploys to `finance-bot`

> ⚠️ **The push trigger is currently not firing.** As of 2026-08-17 both triggers are
> ENABLED and correctly configured, but the GitHub App webhook has stopped delivering, so a
> push creates no build and silently leaves Cloud Run on the old revision. Until the GitHub
> App is reconnected, kick the build off explicitly:
>
> ```powershell
> # prod
> gcloud builds triggers run rmgpgab-finance-bot-asia-southeast1-Boonpin97-expense-trackemsa --branch=main
> # dev
> gcloud builds triggers run rmgpgab-finance-bot-dev-asia-southeast1-Boonpin97-expense-trrhy --branch=development
> ```
>
> This runs the same pipeline, so it is not a manual deploy. Verify afterwards:
> `gcloud run services describe finance-bot --region=asia-southeast3 --format="value(metadata.labels.commit-sha)"`

### Web Dashboard

```powershell
# Build from project root
npm run build

# Deploy to dev (default — always use unless explicitly deploying to prod)
firebase deploy --only hosting:dev

# Deploy to prod (explicit instruction required)
firebase deploy --only hosting:prod
```

If a prod deploy fails with a Firebase uploader `paths[1] undefined` error:

```powershell
Remove-Item .firebase\hosting.*.cache -ErrorAction SilentlyContinue
npm run build
firebase deploy --only hosting:prod
```

---

## Firestore Collections

| Collection | Purpose |
|---|---|
| `transactions` | All expense entries (chat_id, item, amount, category, timestamp, source_type) |
| `inflows` | All income entries (chat_id, item, amount, timestamp, goal_id, project_id) |
| `authorized_chats` | **The Telegram allowlist.** Doc ID = chat ID. Watched by a realtime listener |
| `users/{chat_id}/category_list` | Per-user categories (name, emoji, order) |
| `users/{chat_id}/category_map` | Learned item→category mappings |
| `users/{chat_id}/budgets` | Monthly budget limits per category |
| `users/{chat_id}/goals` | Savings goals (name, target_amount, emoji, order) |
| `users/{chat_id}/projects` | Long-term savings projects (target_amount, initial_amount, deadline) |
| `users/{chat_id}/payment_plans` | Recurring and split payment plan definitions |
| `users/{chat_id}/pending_plans` | In-progress plan creation state |
| `pending` | Temporary transactions awaiting category selection (keyed by chat_id) |
| `pending_change` | Temporary transaction edit state |
| `pending_dashboard_accounts` | In-progress dashboard account creation, keyed by chat_id |
| `user_state` | Legacy single-value flow state (`set_user_state`) — superseded by `interaction_sessions` |
| `web_accounts` | Dashboard login credentials (username, password_hash, chat_id) |
| `web_usernames` | Username→chat_id uniqueness index for dashboard sign-in |
| `web_sessions` | Active dashboard sessions (token hash, expires_at) |
| `dashboard_preferences` | Per-user dashboard UI preferences, keyed by chat_id |
| `interaction_sessions` | Multi-step flow state for bot interactions (flow_type, step, payload, expires_at) |

---

## Core Features

### Expense Logging

Users send freeform text (`Coffee $10`, `Grab $15.50`, `electricity 120`). The parser extracts item and amount, then the categoriser:

1. Normalises the item name and looks up the user's `category_map`
2. **Known item**: saves the transaction immediately and confirms to the user
3. **Unknown item**: saves to `pending` and sends an inline category keyboard; user taps a category to confirm

### Category Management

Users have a personal `category_list` with custom names, emojis, and display order. The bot supports adding, renaming, reordering, and deleting categories via inline keyboards.

### Payment Plans

Two plan types:
- **Recurring**: charges a fixed amount on the same day each month indefinitely
- **Split payment**: splits a total across N monthly installments

Due plans are processed automatically by Cloud Scheduler. Past installments can be rewritten if a plan is edited or deleted.

### Budget Tracking

Users set per-category monthly budget limits. The bot sends a warning after any transaction that causes a category to exceed its budget.

### Income (Inflows)

`/income` records money coming in, stored separately from expenses in the `inflows`
collection. Every report renders an **Inflow** section alongside expenses and computes
a net figure. An inflow can optionally be tagged to a goal or a project.

### Goals and Projects

Two savings constructs, both managed via bot commands and the dashboard:

- **Goals** (`/goals`, `/new_goal`, `/edit_goal`, `/delete_goal`) — a named target amount
  that inflows can be tagged against.
- **Projects** (`/projects`, `/new_projects`, `/edit_projects`, `/delete_projects`) —
  like a goal but cumulative (never resets) and carrying a fixed `deadline` date.

### Reports

Cloud Scheduler triggers the reports (all times SGT):

- **Daily** (10 PM, every day): itemised list of today's transactions and inflows
- **Weekly** (10 PM Sunday): category breakdown for the current week
- **Monthly** (midnight, 1st of month): category breakdown for the completed previous month

Daily and weekly share a single scheduler job (`finance-bot-reports`, `period=auto`) to stay
inside Cloud Scheduler's 3-job free tier; each still arrives as its own Telegram message.

A separate **budget report** (`/budget_report`, or `POST /trigger-budget-report`) compares
month-to-date spending against a pro-rated budget. It is **not** part of any scheduled report
and currently has no scheduler job — it only runs on demand.

### Web Dashboard

React SPA deployed on Firebase Hosting. Features:
- Sign-in with username + password (account created via Telegram bot)
- Expense table with pagination, date range filtering, inline edit and delete
- Inflow (income) management
- Charts: pie (by category), bar (daily/weekly), line (trend)
- Category editor (rename, emoji, reorder)
- Budget manager
- Goal and project management

The API base URL is resolved **at runtime by hostname** (`dashboard-api.ts:112`), not baked in
at build time — so the same `npm run build` output is correct for both the dev and prod sites.

### Authorisation

The bot only processes updates from chat IDs present in the `authorized_chats` Firestore
collection (document ID = chat ID). `firestore.py` attaches an `on_snapshot` listener at
startup, so changes take effect immediately without a redeploy. Updates from any other chat
are silently dropped.

---

## Scripts

### Category Migration

Migrates category data from legacy global or top-level user-scoped documents into the current `users/{chat_id}/...` subcollection structure.

```bash
# Dry run — preview counts without writing
python scripts/migrate_category_collections.py --chat-id <CHAT_ID> --database <DB>  --dry-run

# Migrate and delete source documents
python scripts/migrate_category_collections.py --chat-id <CHAT_ID> --database <DB>

# Migrate without deleting source documents
python scripts/migrate_category_collections.py --chat-id <CHAT_ID> --database <DB> --keep-source
```

### Category Clone

Copies all categories from one user to another (useful for seeding a new account).

```bash
# Dry run
python scripts/clone_category_collections.py \
  --source-chat-id <SOURCE> --target-chat-id <TARGET> --database <DB> --dry-run

# Execute
python scripts/clone_category_collections.py \
  --source-chat-id <SOURCE> --target-chat-id <TARGET> --database <DB>
```

Both scripts read `FIRESTORE_PROJECT_ID` from the environment.

---

## Notes

- All timestamps are stored in ISO 8601 format with `+08:00` (Singapore time)
- The bot enforces an allowlist via the `authorized_chats` Firestore collection (**not** `TELEGRAM_CHAT_IDS`, which is unused); updates from any other chat ID are rejected
- The `interaction_sessions` collection is the canonical store for all multi-step bot flows; do not create ad-hoc pending collections for new features
