from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from routers import webhook, reports

app = FastAPI(title="Telegram Finance Bot")

app.include_router(webhook.router)
app.include_router(reports.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
