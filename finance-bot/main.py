import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from routers import webhook, reports
from services import telegram


@asynccontextmanager
async def lifespan(app: FastAPI):
    cloud_run_url = os.getenv("CLOUD_RUN_URL")
    webhook_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    try:
        if cloud_run_url and webhook_secret:
            await telegram.set_webhook(f"{cloud_run_url}/webhook", webhook_secret)
        await telegram.set_my_commands()
    except Exception as e:
        print(f"[startup] Telegram setup failed (non-fatal): {e}")
    yield


app = FastAPI(title="Telegram Finance Bot", lifespan=lifespan)

app.include_router(webhook.router)
app.include_router(reports.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
