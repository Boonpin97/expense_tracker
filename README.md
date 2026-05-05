# Telegram Finance & Budgeting Bot — Copilot Prompt

## Project Overview

Build a Telegram bot that tracks personal finances and sends spending reports. Users send messages like `Coffee $10` and the bot categorises the expense, stores it, and sends daily, weekly, and monthly summaries.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Bot interface | Telegram Bot API (webhook mode) |
| Backend | FastAPI (Python) |
| Hosting | Google Cloud Run (backend) · Firebase Hosting (web dashboard) |
| Database | Google Cloud Firestore |
| Scheduler | Google Cloud Scheduler |
| Web dashboard | React 19 + TanStack Router + Vite + Tailwind CSS v4 + shadcn/ui |

---

## ⚙️ Required Credentials & Where to Put Them

Before writing any code, complete the following setup steps and collect the values listed. All values go into a `.env` file at the project root. **Do not hardcode any of these into source files.**

---

### 1. Telegram Bot — get your Bot Token

1. Open Telegram and message **@BotFather**
2. Send `/newbot` and follow the prompts to name your bot
3. BotFather will give you a token that looks like: `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`

```env
# .env
TELEGRAM_BOT_TOKEN=<paste your BotFather token here>
```

After deploying to Cloud Run (step 3), come back and register your webhook:
```
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://<your-cloud-run-url>/webhook
```

---

### 2. Firestore — get your project credentials

#### 2a. Create the Firestore database

1. Go to [https://console.firebase.google.com](https://console.firebase.google.com)
2. Create a new project (or use an existing GCP project)
3. Navigate to **Firestore Database → Create database**
4. Choose **Native mode** and select a region close to your users (e.g. `asia-southeast1` for Singapore)

#### 2b. Create a service account

1. In the GCP Console, go to **IAM & Admin → Service Accounts**
2. Click **Create Service Account**
3. Give it a name (e.g. `finance-bot-sa`)
4. Assign the role: **Cloud Datastore User**
5. Click **Done**, then open the service account → **Keys → Add Key → JSON**
6. Download the JSON file and save it as `serviceAccountKey.json` in the project root
7. **Add `serviceAccountKey.json` to `.gitignore` immediately**

```env
# .env
GOOGLE_APPLICATION_CREDENTIALS=./serviceAccountKey.json
FIRESTORE_PROJECT_ID=<your GCP project ID, found in the JSON file under "project_id">
```

#### 2c. Firestore collections to create manually (optional, auto-created on first write)

| Collection | Purpose |
|---|---|
| `transactions` | Every expense logged by the user |
| `category_map` | Learned item→category mappings |

---

### 3. Cloud Run — deploy the backend

#### 3a. Install prerequisites

```bash
# Install Google Cloud CLI: https://cloud.google.com/sdk/docs/install
gcloud auth login
gcloud config set project <YOUR_GCP_PROJECT_ID>
```

#### 3b. Deploy command (run from project root)

```bash
gcloud run deploy finance-bot \
  --source . \
  --region asia-southeast1 \
  --allow-unauthenticated \
  --set-env-vars TELEGRAM_BOT_TOKEN=<your-token>,FIRESTORE_PROJECT_ID=<your-project-id>
```

After deployment, GCP will output a URL like:
```
https://finance-bot-<hash>-as.a.run.app
```

```env
# .env
CLOUD_RUN_URL=<paste the full Cloud Run service URL here>
```

Use this URL to register the Telegram webhook (see step 1).

---

### 4. Cloud Scheduler — set up cron jobs

Run these three commands to create the daily, weekly, and monthly report triggers. Replace `<CLOUD_RUN_URL>` with your deployed service URL and `<YOUR_GCP_PROJECT_ID>` with your project ID.

```bash
# Daily report — every day at 9 PM Singapore time (UTC+8 = 13:00 UTC)
gcloud scheduler jobs create http finance-bot-daily \
  --schedule="0 13 * * *" \
  --uri="<CLOUD_RUN_URL>/trigger-report?period=daily" \
  --http-method=POST \
  --location=asia-southeast1

# Weekly report — every Monday at 9 AM Singapore time
gcloud scheduler jobs create http finance-bot-weekly \
  --schedule="0 1 * * 1" \
  --uri="<CLOUD_RUN_URL>/trigger-report?period=weekly" \
  --http-method=POST \
  --location=asia-southeast1

# Monthly report — 1st of every month at 9 AM Singapore time
gcloud scheduler jobs create http finance-bot-monthly \
  --schedule="0 1 1 * *" \
  --uri="<CLOUD_RUN_URL>/trigger-report?period=monthly" \
  --http-method=POST \
  --location=asia-southeast1
```

```env
# .env — add the Telegram user/chat ID so the scheduler knows who to message
TELEGRAM_CHAT_ID=<your Telegram user ID — get it by messaging @userinfobot>
```

---

## 🌐 Web Dashboard

A React web dashboard is served at the Firebase Hosting URLs below. It connects to the same backend API as the bot.

| Environment | URL |
|---|---|
| Production | https://budget-bot-123.web.app |
| Development | https://budget-bot-123-dev.web.app |

### Dashboard structure

```
lovable/
├── src/
│   ├── routes/
│   │   ├── __root.tsx          # App shell (head, body, Scripts)
│   │   └── index.tsx           # Dashboard + sign-in page
│   ├── lib/
│   │   ├── dashboard-api.ts    # API client (auth, transactions, categories, budgets)
│   │   └── dashboard-analytics.ts  # Analytics helpers (date presets, summaries)
│   ├── components/ui/          # shadcn/ui component library
│   └── styles.css
├── public/
│   └── logo.png                # App icon shown on the sign-in screen
└── package.json
```

### Build & deploy

```powershell
# Build
cd lovable
npm run build

# Deploy to dev (default)
firebase deploy --only hosting:dev

# Deploy to prod (explicit instruction required)
firebase deploy --only hosting:prod
```

> **Note:** Cloud Run (backend) is deployed automatically by Cloud Build on git push — never run `gcloud run deploy` manually.

---

## 📁 Project Structure to Generate

```
finance-bot/
├── main.py                  # FastAPI app entry point
├── routers/
│   ├── webhook.py           # POST /webhook — handles Telegram updates
│   └── reports.py           # POST /trigger-report — called by Cloud Scheduler
├── services/
│   ├── parser.py            # Parses "Coffee $10" into {item, amount}
│   ├── categoriser.py       # Looks up category_map, prompts user if unknown
│   ├── firestore.py         # All Firestore read/write operations
│   └── telegram.py          # Wrapper for Telegram Bot API calls
├── models/
│   └── transaction.py       # Pydantic models for Transaction and CategoryMap
├── .env                     # ← All secrets go here (never commit this)
├── .env.example             # Safe template with placeholder values
├── .gitignore               # Must include .env and serviceAccountKey.json
├── Dockerfile               # For Cloud Run deployment
├── requirements.txt
└── README.md
```

---

## 🗃️ Firestore Data Models

### Collection: `transactions`

```python
# Each document represents one expense entry
{
    "id": "auto-generated",
    "item": "Coffee",           # Original item name as typed by user
    "amount": 10.00,            # Float, in SGD (or user's local currency)
    "category": "Food & Drink", # Resolved category
    "timestamp": "2024-01-15T21:00:00+08:00",  # ISO 8601 with timezone
    "chat_id": 123456789        # Telegram chat ID of the user
}
```

### Collection: `category_map`

```python
# Document ID = item name lowercased and stripped (e.g. "coffee", "grab")
{
    "item_key": "coffee",       # Normalised item name (document ID)
    "category": "Food & Drink", # User-confirmed category
    "confirmed_by_user": True,  # False if auto-guessed, True if user picked it
    "created_at": "2024-01-15T21:00:00+08:00"
}
```

---

## 🤖 Core Logic to Implement

### Message parsing (`services/parser.py`)

- Accept freeform text like `Coffee $10`, `Grab $15.50`, `electricity bill 120`
- Extract the item name and dollar amount using regex
- Return `{"item": "Coffee", "amount": 10.00}` or `None` if unparseable
- Reply with a friendly error if the format is unrecognised

### Category engine (`services/categoriser.py`)

1. Normalise the item name (lowercase, strip punctuation)
2. Query `category_map` collection for an exact match on the document ID
3. **If found**: use the stored category, save the transaction, confirm to the user
4. **If not found**: send a Telegram inline keyboard with preset categories:
   - 🍔 Food & Drink
   - 🚗 Transport
   - 🏠 Housing
   - 💊 Health
   - 🎬 Entertainment
   - 🛍️ Shopping
   - 💡 Utilities
   - ➕ Other (prompts user to type a custom category)
5. On user selection: save both the transaction and the new `category_map` entry

### Webhook handler (`routers/webhook.py`)

- Handle two types of Telegram updates:
  - `message` — a new expense text from the user
  - `callback_query` — a category button tap from the inline keyboard
- On `callback_query`, retrieve the pending transaction from a temporary Firestore document (keyed by `chat_id`), apply the chosen category, save the final transaction, and delete the temp document

### Report generator (`routers/reports.py`)

- Accept `?period=daily|weekly|monthly` query parameter
- Query `transactions` where `timestamp` falls within the period window
- Group results by `category` and sum amounts
- Format and send a Telegram message like:

```
📊 Weekly Report (13–19 Jan)
─────────────────────────
🍔 Food & Drink     $142.50
🚗 Transport         $38.00
🛍️ Shopping          $95.00
─────────────────────────
💰 Total            $275.50
```

---

## 🐳 Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

> Cloud Run expects the app to listen on port **8080**.

---

## 📦 requirements.txt

```
fastapi
uvicorn[standard]
python-telegram-bot==20.*
google-cloud-firestore
python-dotenv
pydantic
httpx
```

---

## 🔒 .env.example (commit this, not .env)

```env
TELEGRAM_BOT_TOKEN=your-telegram-bot-token-here
TELEGRAM_CHAT_ID=your-telegram-user-id-here
FIRESTORE_PROJECT_ID=your-gcp-project-id-here
GOOGLE_APPLICATION_CREDENTIALS=./serviceAccountKey.json
CLOUD_RUN_URL=https://your-service-url.a.run.app
```

---

## ✅ Implementation Checklist for Copilot

Generate the files in this order:

1. `models/transaction.py` — Pydantic schemas
2. `services/firestore.py` — all DB reads and writes
3. `services/parser.py` — message parsing logic
4. `services/telegram.py` — send message and inline keyboard helpers
5. `services/categoriser.py` — category lookup and user prompt flow
6. `routers/webhook.py` — Telegram webhook endpoint
7. `routers/reports.py` — scheduled report endpoint
8. `main.py` — FastAPI app setup, router registration, health check endpoint
9. `Dockerfile` and `requirements.txt`
10. `.env.example` and `.gitignore`

---

## Notes

- All timestamps should be stored in **ISO 8601 format with timezone offset** (`+08:00` for Singapore)
- The `/trigger-report` endpoint should be protected. Add a `X-Scheduler-Token` header check using a shared secret stored in `.env` as `SCHEDULER_SECRET`, and set the same header in Cloud Scheduler job configurations using `--headers X-Scheduler-Token=<secret>`
- The bot is single-user by default. The `TELEGRAM_CHAT_ID` env var acts as an allowlist — reject webhook updates from any other chat ID
- If you extend this to multi-user later, partition all Firestore queries by `chat_id`
