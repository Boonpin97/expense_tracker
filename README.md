# Telegram Finance Bot & Web Dashboard

A Telegram bot that tracks personal expenses with a React web dashboard for browsing and managing financial data.

Users send messages like `Coffee $10` and the bot categorises the expense, stores it in Firestore, manages recurring payment plans, and sends daily, weekly, and monthly spending summaries.

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
| CI/CD | Cloud Build (auto-deploy on git push) |

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
│   │   ├── categoriser.py        # Category lookup and inline keyboard prompt flow
│   │   ├── telegram.py           # Telegram Bot API wrappers and keyboard builders
│   │   ├── interaction_sessions.py  # Shared multi-step flow state management
│   │   ├── payment_plans.py      # Recurring/split payment calculations
│   │   ├── plan_manager.py       # Payment plan lifecycle and due-plan processing
│   │   ├── dashboard_auth.py     # Web account password hashing and session tokens
│   │   └── category_migration.py # One-off category data migration helpers
│   ├── models/
│   │   └── transaction.py        # Pydantic models (Transaction, PaymentPlan, FlowSession, …)
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
│   └── clone_category_collections.py   # Copy categories from one user to another
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
| Cloud Run URL | `https://finance-bot-jrpmzkxwoa-as.a.run.app` | `https://finance-bot-dev-jrpmzkxwoa-as.a.run.app` |
| Firestore DB | `(default)` | `developer` |
| Firebase Hosting | `https://budget-bot-123.web.app` | `https://budget-bot-123-dev.web.app` |

All resources are in region `asia-southeast1`.

---

## Environment Variables

The backend reads these at runtime (Cloud Run env vars or local `.env`):

```env
TELEGRAM_BOT_TOKEN=          # BotFather token
TELEGRAM_CHAT_IDS=           # Comma-separated allowlist of authorised Telegram user IDs
FIRESTORE_PROJECT_ID=        # GCP project ID (budget-bot-123)
FIRESTORE_DATABASE=          # Firestore database name: (default) for prod, developer for dev
CLOUD_RUN_URL=               # Full Cloud Run service URL (used for webhook registration)
SCHEDULER_SECRET=            # Shared secret — Cloud Scheduler sends this in X-Scheduler-Token
TELEGRAM_WEBHOOK_SECRET=     # Shared secret — Telegram sends this in X-Telegram-Bot-Api-Secret-Token
DASHBOARD_DEV_ORIGIN=        # Allowed CORS origin for dev (e.g. http://localhost:5173)
```

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
python -m unittest
```

### Frontend

```powershell
npm install
npm run dev        # Vite dev server at http://localhost:5173
```

---

## Deployment

### Backend (Cloud Run)

Never deploy manually. Cloud Build triggers handle all Cloud Run deployments automatically on git push:

- Push to `development` → deploys to `finance-bot-dev`
- Push to `main` → deploys to `finance-bot`

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
| `users/{chat_id}/category_list` | Per-user categories (name, emoji, order) |
| `users/{chat_id}/category_map` | Learned item→category mappings |
| `users/{chat_id}/budgets` | Monthly budget limits per category |
| `users/{chat_id}/payment_plans` | Recurring and split payment plan definitions |
| `users/{chat_id}/pending_plans` | In-progress plan creation state |
| `pending` | Temporary transactions awaiting category selection (keyed by chat_id) |
| `pending_change` | Temporary transaction edit state |
| `web_accounts` | Dashboard login credentials (username, password_hash, chat_id) |
| `web_sessions` | Active dashboard sessions (token hash, expires_at) |
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

### Reports

Cloud Scheduler triggers three report types:
- **Daily** (9 PM SGT): itemised list of today's transactions
- **Weekly** (Monday 9 AM SGT): category breakdown for the past week
- **Monthly** (1st of month 9 AM SGT): category breakdown + budget comparison

### Web Dashboard

React SPA deployed on Firebase Hosting. Features:
- Sign-in with username + password (account created via Telegram bot)
- Expense table with pagination, date range filtering, inline edit and delete
- Charts: pie (by category), bar (daily/weekly), line (trend)
- Category editor (rename, emoji, reorder)
- Budget manager

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
- The bot enforces a single-user allowlist via `TELEGRAM_CHAT_IDS`; updates from any other chat ID are rejected
- The `interaction_sessions` collection is the canonical store for all multi-step bot flows; do not create ad-hoc pending collections for new features
