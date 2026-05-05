# Expense Bot Agent Guide

## Purpose

This repository contains a Telegram finance bot and a Flutter client. Most interactive bot logic lives under `finance-bot/`.

Primary backend stack:
- FastAPI
- Firestore
- Telegram Bot API
- Python tests via `unittest`

## Repo Focus

When working on backend bot behavior, prefer these paths first:
- `finance-bot/routers/webhook.py`
- `finance-bot/services/`
- `finance-bot/models/`
- `finance-bot/tests/`

Do not assume the Flutter app and the Telegram backend share the same runtime or state model.

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

There are two environments, each tied to a branch and deployed automatically via Cloud Build triggers.

| Resource        | Production (`main`)                              | Development (`development`)                          |
|-----------------|--------------------------------------------------|------------------------------------------------------|
| Cloud Run       | `finance-bot`                                    | `finance-bot-dev`                                    |
| Cloud Run URL   | `https://finance-bot-jrpmzkxwoa-as.a.run.app`   | `https://finance-bot-dev-jrpmzkxwoa-as.a.run.app`   |
| Firestore DB    | `(default)`                                      | `developer`                                          |
| Firebase Hosting| `https://budget-bot-123.web.app`                 | `https://budget-bot-123-dev.web.app`                 |

All resources live in region `asia-southeast1` under the same GCP project.

When making changes that touch Firestore, Cloud Run config, or hosting:
- work on the `development` branch to target the dev environment
- only merge to `main` when the feature is ready for production
- never point dev code at the `(default)` Firestore database or the production Cloud Run service

### Deployment Rules

**Cloud Run — never deploy manually.** Cloud Run deployments are handled exclusively by Cloud Build triggers on git push. Do not run `gcloud run deploy` or equivalent. To deploy backend changes, commit and push to the appropriate branch (`development` for dev, `main` for prod).

**Flutter web — always deploy to dev unless told otherwise.** When deploying UI changes, always target the dev hosting site (`budget-bot-123-dev.web.app`):
```
firebase deploy --only hosting:dev
```
Never deploy to the prod hosting site (`budget-bot-123.web.app`) unless explicitly instructed.
