import os
from datetime import datetime, timedelta, timezone
import httpx

SGT = timezone(timedelta(hours=8))

TELEGRAM_API = "https://api.telegram.org/bot{token}"
_TIMEOUT = httpx.Timeout(10.0)


def _api_url(method: str) -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    return f"{TELEGRAM_API.format(token=token)}/{method}"


async def send_message(chat_id: int, text: str, parse_mode: str = "HTML") -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
            },
        )
        return resp.json()


async def send_message_with_change_category(chat_id: int, text: str, tx_id: str, item_key: str) -> dict:
    keyboard = [
        [{"text": "🔄 Change category", "callback_data": f"chgcat:{tx_id}:{item_key}"}],
        [{"text": "📅 Edit date", "callback_data": f"chgdate:{tx_id}"}],
    ]
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def send_category_keyboard(chat_id: int, item: str, amount: float) -> dict:
    from services.firestore import get_category_list

    # Build buttons from category_list (already ordered, "Other" last)
    categories = []
    for cat in get_category_list():
        emoji = cat.get("emoji", "🏷️")
        name = cat["name"]
        categories.append((f"{emoji} {name}", f"cat:{name}"))

    # Always add "New category" at the very end
    categories.append(("✏️ New category", "cat:__new__"))

    keyboard = []
    row = []
    for label, callback in categories:
        row.append({"text": label, "callback_data": callback})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
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


async def send_transaction_keyboard(chat_id: int, transactions: list[dict], prompt: str) -> dict:
    """Send an inline keyboard where each button is a transaction to delete."""
    ts = datetime.now(SGT).isoformat()
    keyboard = []
    for tx in transactions:
        label = f"❌ {tx['item']} — ${tx['amount']:.2f} ({tx['category']})"
        callback_data = f"del:{tx['_doc_id']}:{ts}"
        keyboard.append([{"text": label, "callback_data": callback_data}])

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": prompt,
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def send_remove_category_keyboard(chat_id: int, categories: list[dict]) -> dict:
    """Send an inline keyboard for removing a category."""
    ts = datetime.now(SGT).isoformat()
    keyboard = []
    for cat in categories:
        label = f"❌ {cat['emoji']} {cat['name']}"
        keyboard.append([{"text": label, "callback_data": f"rmcat:{cat['name']}|{ts}"}])

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": "🗂 Tap a category to remove it:",
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def set_webhook(url: str, secret_token: str) -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("setWebhook"),
            json={
                "url": url,
                "secret_token": secret_token,
            },
        )
        return resp.json()


async def send_budget_category_keyboard(chat_id: int) -> dict:
    """Show category buttons for /set_budget."""
    from services.firestore import get_category_list

    categories = get_category_list()
    keyboard = []
    row = []
    for cat in categories:
        emoji = cat.get("emoji", "🏷️")
        name = cat["name"]
        row.append({"text": f"{emoji} {name}", "callback_data": f"setbudget:{name}"})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": "💰 Select a category to set its monthly budget:",
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def answer_callback_query(callback_query_id: str, text: str = "") -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
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
        {"command": "report", "description": "Daily report for a specific date (YYYY-MM-DD)"},
        {"command": "daily", "description": "Today's spending summary"},
        {"command": "weekly", "description": "This week's spending summary"},
        {"command": "monthly", "description": "This month's spending summary"},
        {"command": "budget_report", "description": "Budget vs spending report"},
        {"command": "set_budget", "description": "Set monthly budget for a category"},
        {"command": "delete_last", "description": "Delete the last recorded transaction"},
        {"command": "delete_today", "description": "Delete a transactions from today"},
        {"command": "delete_past", "description": "Delete a transactions in a specific date"},
        {"command": "new_category", "description": "Add a new spending category"},
        {"command": "remove_category", "description": "Remove a spending category"},
    ]
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("setMyCommands"),
            json={"commands": commands},
        )
        return resp.json()

