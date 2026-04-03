import os

from fastapi import APIRouter, Request

from services.parser import parse_expense
from services.categoriser import handle_expense, handle_category_selection
from services import telegram

router = APIRouter()

ALLOWED_CHAT_IDS: set[int] | None = None


def _get_allowed_chat_ids() -> set[int]:
    global ALLOWED_CHAT_IDS
    if ALLOWED_CHAT_IDS is None:
        raw = os.getenv("TELEGRAM_CHAT_IDS", "")
        ALLOWED_CHAT_IDS = {
            int(cid.strip()) for cid in raw.split(",") if cid.strip().lstrip("-").isdigit()
        }
    return ALLOWED_CHAT_IDS


@router.post("/webhook")
async def webhook(request: Request):
    data = await request.json()

    # Handle callback_query (category button tap)
    if "callback_query" in data:
        callback = data["callback_query"]
        chat_id = callback["message"]["chat"]["id"]

        if chat_id not in _get_allowed_chat_ids():
            return {"ok": True}

        callback_data = callback.get("data", "")
        callback_query_id = callback["id"]

        if callback_data.startswith("cat:"):
            category = callback_data[4:]
            await handle_category_selection(chat_id, category, callback_query_id)

        return {"ok": True}

    # Handle message (new expense text)
    if "message" in data:
        message = data["message"]
        chat_id = message["chat"]["id"]

        if chat_id not in _get_allowed_chat_ids():
            return {"ok": True}

        text = message.get("text", "")

        # Ignore bot commands
        if text.startswith("/"):
            if text == "/start":
                await telegram.send_message(
                    chat_id,
                    "👋 Welcome! Send me an expense like <b>Coffee $10</b> and I'll track it for you.",
                )
            return {"ok": True}

        parsed = parse_expense(text)
        if parsed is None:
            await telegram.send_message(
                chat_id,
                "🤔 I couldn't understand that. Try something like:\n<code>Coffee $10</code>\n<code>Grab 15.50</code>",
            )
            return {"ok": True}

        await handle_expense(chat_id, parsed.item, parsed.amount)
        return {"ok": True}

    return {"ok": True}
