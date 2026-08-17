# Clone Deployment Runbook

This runbook moves the bot to a new Google Cloud/Firebase project under a different Google account.

## Manual Prerequisites

These require owner access in the Google account that will own the new project, for example `firebasedouble07@gmail.com`.

1. Create or choose the new Firebase/GCP project.
2. Enable billing for the project. Cloud Run, Cloud Build, Artifact Registry, Scheduler, and Firestore need it.
3. Enable these APIs:

```powershell
gcloud.cmd services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com firestore.googleapis.com cloudscheduler.googleapis.com secretmanager.googleapis.com --project <NEW_PROJECT_ID>
```

4. Create Firestore databases:

```powershell
gcloud.cmd firestore databases create --database="(default)" --location=asia-southeast1 --project <NEW_PROJECT_ID>
gcloud.cmd firestore databases create --database=developer --location=asia-southeast1 --project <NEW_PROJECT_ID>
```

5. Create Firebase Hosting sites, or use the default site plus a dev site:

```powershell
firebase.cmd hosting:sites:create <NEW_PROJECT_ID> --project <NEW_PROJECT_ID>
firebase.cmd hosting:sites:create <NEW_PROJECT_ID>-dev --project <NEW_PROJECT_ID>
```

6. Set hosting targets:

```powershell
firebase.cmd target:apply hosting prod <NEW_PROJECT_ID> --project <NEW_PROJECT_ID>
firebase.cmd target:apply hosting dev <NEW_PROJECT_ID>-dev --project <NEW_PROJECT_ID>
```

## Repo Configuration

Do not reuse the old `serviceAccountKey.json` for the new project. For Cloud Run, prefer the service account attached to the service. For local development against the new project, create a new key with only the minimum Firestore permissions and keep it out of git.

Update `.firebaserc` for the new project:

```json
{
  "projects": {
    "default": "<NEW_PROJECT_ID>"
  },
  "targets": {
    "<NEW_PROJECT_ID>": {
      "hosting": {
        "prod": ["<NEW_PROJECT_ID>"],
        "dev": ["<NEW_PROJECT_ID>-dev"]
      }
    }
  },
  "etags": {}
}
```

Build the web app with the new Cloud Run URL after the backend is deployed:

```powershell
$env:VITE_DASHBOARD_API_BASE_URL="https://<CLOUD_RUN_SERVICE_URL>"
npm.cmd run build
firebase.cmd deploy --only hosting:prod,firestore:rules,firestore:indexes --project <NEW_PROJECT_ID>
```

Or use the repo script:

```powershell
$env:VITE_DASHBOARD_API_BASE_URL="https://<CLOUD_RUN_SERVICE_URL>"
.\scripts\deploy_dashboard_web.ps1 -Environment prod -ProjectId <NEW_PROJECT_ID>
```

## Cloud Run

Deploy from `finance-bot/`:

```powershell
gcloud.cmd run deploy finance-bot `
  --source finance-bot `
  --region asia-southeast1 `
  --allow-unauthenticated `
  --project <NEW_PROJECT_ID> `
  --set-env-vars FIRESTORE_PROJECT_ID=<NEW_PROJECT_ID>,FIRESTORE_DATABASE="(default)",CLOUD_RUN_URL=https://<CLOUD_RUN_SERVICE_URL>,DASHBOARD_WEB_URL=https://<NEW_PROJECT_ID>.web.app `
  --set-secrets TELEGRAM_BOT_TOKEN=TELEGRAM_BOT_TOKEN:latest,SCHEDULER_SECRET=SCHEDULER_SECRET:latest,TELEGRAM_WEBHOOK_SECRET=TELEGRAM_WEBHOOK_SECRET:latest
```

Cloud Run returns the service URL after deploy. Re-run the command once with `CLOUD_RUN_URL` set to that exact URL so the app can register the Telegram webhook.

This bootstrap deploy is the one time `gcloud run deploy` is acceptable — the service must exist
before Cloud Build triggers can update it. After this, all deploys go through Cloud Build.

Pick the Cloud Run region deliberately and record it: whatever you choose here must also be the
Cloud Build trigger's `_DEPLOY_REGION`, and it is the `--region` for every later `gcloud run`
command. It does **not** have to match the Firestore or Scheduler region, and in the original
`budget-bot-123` project it does not — Cloud Run is in `asia-southeast3` while Firestore and
Scheduler are in `asia-southeast1`.

For dev, deploy `finance-bot-dev` with `FIRESTORE_DATABASE=developer` and `DASHBOARD_WEB_URL=https://<NEW_PROJECT_ID>-dev.web.app`.

## Secrets

Create these in Secret Manager before deploying Cloud Run:

```powershell
"<telegram bot token>" | gcloud.cmd secrets create TELEGRAM_BOT_TOKEN --data-file=- --project <NEW_PROJECT_ID>
"<scheduler shared secret>" | gcloud.cmd secrets create SCHEDULER_SECRET --data-file=- --project <NEW_PROJECT_ID>
"<telegram webhook secret>" | gcloud.cmd secrets create TELEGRAM_WEBHOOK_SECRET --data-file=- --project <NEW_PROJECT_ID>
```

Grant the Cloud Run service account access to these secrets if the deploy command does not do it automatically.

## Authorising Telegram Users

There is no `TELEGRAM_CHAT_IDS` secret — the allowlist lives in Firestore. After the backend is
up, add one document per authorised chat to the `authorized_chats` collection, using the chat ID
as the document ID (contents are ignored). The backend watches the collection with an
`on_snapshot` listener, so changes apply immediately with no redeploy.

## Cloud Scheduler

Create the scheduler jobs after Cloud Run is deployed. Replace `<SCHEDULER_SECRET>` with the same value stored in Secret Manager.

**Create exactly three jobs.** Cloud Scheduler's free tier covers 3 jobs per billing account;
a fourth starts incurring charges. The daily and weekly reports are deliberately merged into a
single `period=auto` job — do not split them back out.

```powershell
gcloud.cmd scheduler jobs create http finance-bot-reports --location asia-southeast1 --time-zone "Asia/Singapore" --schedule "0 22 * * *" --uri "https://<CLOUD_RUN_SERVICE_URL>/trigger-report?period=auto" --http-method POST --headers "X-Scheduler-Token=<SCHEDULER_SECRET>" --project <NEW_PROJECT_ID>
gcloud.cmd scheduler jobs create http finance-bot-monthly --location asia-southeast1 --time-zone "Asia/Singapore" --schedule "0 0 1 * *" --uri "https://<CLOUD_RUN_SERVICE_URL>/trigger-report?period=monthly" --http-method POST --headers "X-Scheduler-Token=<SCHEDULER_SECRET>" --project <NEW_PROJECT_ID>
gcloud.cmd scheduler jobs create http finance-bot-recurring --location asia-southeast1 --time-zone "Asia/Singapore" --schedule "0 8 * * *" --uri "https://<CLOUD_RUN_SERVICE_URL>/trigger-recurring-payments" --http-method POST --headers "X-Scheduler-Token=<SCHEDULER_SECRET>" --project <NEW_PROJECT_ID>
```

`period=auto` sends the daily report every night and appends the weekly report on Sundays.
Without `--time-zone`, Cloud Scheduler defaults to UTC and the reports fire 8 hours early.

## Cloud Build Triggers

The existing project uses console-managed Cloud Build triggers, not `cloudbuild.yaml`. Recreate those triggers manually in the new project unless you want to add build config to this repo.

Required trigger behavior:

- Push to `development` deploys Cloud Run service `finance-bot-dev` with Firestore database `developer`.
- Push to `main` deploys Cloud Run service `finance-bot` with Firestore database `(default)`.
- Build context is `finance-bot/` and Dockerfile is `finance-bot/Dockerfile`.

## Data Migration

Export from the old project and import into the new one:

```powershell
gcloud.cmd firestore export gs://<OLD_EXPORT_BUCKET>/firestore-export --project budget-bot-123 --database="(default)"
gcloud.cmd firestore import gs://<OLD_EXPORT_BUCKET>/firestore-export --project <NEW_PROJECT_ID> --database="(default)"
```

Firestore exports require a Cloud Storage bucket accessible by both projects or a copied export in the target project.
