import logging
import os
import traceback
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request
from routers import webhook, reports
from services import telegram

logger = logging.getLogger(__name__)


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


@app.middleware("http")
async def crash_report_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        if os.getenv("DEV_MODE", "").lower() == "true":
            tb = traceback.format_exc()
            # Telegram message limit is 4096 chars; truncate if needed
            max_len = 3900
            tb_truncated = tb[-max_len:] if len(tb) > max_len else tb
            msg = (
                f"🚨 <b>Crash Report</b>\n"
                f"<code>{request.method} {request.url.path}</code>\n\n"
                f"<pre>{tb_truncated}</pre>"
            )
            raw_ids = os.getenv("TELEGRAM_CHAT_IDS", "")
            chat_ids = [
                int(cid.strip()) for cid in raw_ids.split(",")
                if cid.strip().lstrip("-").isdigit()
            ]
            for chat_id in chat_ids:
                try:
                    await telegram.send_message(chat_id, msg)
                except Exception:
                    pass
        raise exc


@app.get("/health")
async def health():
    return {"status": "ok"}
