import os
import httpx

TELEGRAM_API = "https://api.telegram.org/bot{token}"


def _api_url(method: str) -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    return f"{TELEGRAM_API.format(token=token)}/{method}"


async def send_message(chat_id: int, text: str, parse_mode: str = "HTML") -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
            },
        )
        return resp.json()


async def send_category_keyboard(chat_id: int, item: str, amount: float) -> dict:
    categories = [
        ("🍔 Food & Drink", "cat:Food & Drink"),
        ("🚗 Transport", "cat:Transport"),
        ("🏠 Housing", "cat:Housing"),
        ("💊 Health", "cat:Health"),
        ("🎬 Entertainment", "cat:Entertainment"),
        ("🛍️ Shopping", "cat:Shopping"),
        ("💡 Utilities", "cat:Utilities"),
        ("➕ Other", "cat:Other"),
    ]

    keyboard = []
    row = []
    for label, callback in categories:
        row.append({"text": label, "callback_data": callback})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": f"What category is <b>{item}</b> (${amount:.2f})?",
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def answer_callback_query(callback_query_id: str, text: str = "") -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _api_url("answerCallbackQuery"),
            json={
                "callback_query_id": callback_query_id,
                "text": text,
            },
        )
        return resp.json()


async def set_my_commands() -> dict:
    commands = [
        {"command": "start", "description": "Welcome message"},
        {"command": "report", "description": "Spending report for a date range"},
        {"command": "daily", "description": "Today's spending summary"},
        {"command": "weekly", "description": "This week's spending summary"},
        {"command": "monthly", "description": "This month's spending summary"},
        {"command": "delete_last", "description": "Delete the last recorded transaction"},
        {"command": "delete_today", "description": "Delete all transactions from today"},
        {"command": "delete_past", "description": "Delete transactions in a date range"},
        {"command": "new_category", "description": "Add a new spending category"},
        {"command": "remove_category", "description": "Remove a spending category"},
    ]
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _api_url("setMyCommands"),
            json={"commands": commands},
        )
        return resp.json()
