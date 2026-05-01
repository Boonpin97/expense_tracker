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
    keyboard = [[{"text": "🔄 Change category", "callback_data": f"chgcat:{tx_id}:{item_key}"}]]
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


async def send_transaction_confirmation(
    chat_id: int,
    item: str,
    amount: float,
    category: str,
    tx_id: str | None = None,
    item_key: str | None = None,
    note: str | None = None,
) -> dict:
    text = f"✅ <b>{item}</b> — ${amount:.2f} → {category}"
    if note:
        text += f"\n<i>{note}</i>"
    if tx_id and item_key:
        return await send_message_with_change_category(chat_id, text, tx_id, item_key)
    return await send_message(chat_id, text)


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


async def send_edit_category_keyboard(chat_id: int, categories: list[dict]) -> dict:
    """Send an inline keyboard for picking which category to edit."""
    ts = datetime.now(SGT).isoformat()
    keyboard = []
    row = []
    for cat in categories:
        label = f"{cat['emoji']} {cat['name']}"
        row.append({"text": label, "callback_data": f"editcat:{cat['name']}|{ts}"})
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
                "text": "✏️ Tap a category to edit:",
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def send_edit_category_field_keyboard(chat_id: int, category_name: str, emoji: str) -> dict:
    """Send an inline keyboard with 3 fields: emoji, name, order."""
    ts = datetime.now(SGT).isoformat()
    keyboard = [[
        {"text": "😀 Emoji", "callback_data": f"editfield:emoji:{category_name}|{ts}"},
        {"text": "📝 Name", "callback_data": f"editfield:name:{category_name}|{ts}"},
        {"text": "🔢 Order", "callback_data": f"editfield:order:{category_name}|{ts}"},
    ]]
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": f"Editing {emoji} <b>{category_name}</b> — what do you want to change?",
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def send_plan_keyboard(chat_id: int, plans: list[dict], action: str, prompt: str) -> dict:
    keyboard = []
    for plan in plans:
        plan_type = "Recurring" if plan["plan_type"] == "recurring" else "Split"
        label = f"{plan_type}: {plan['item']}"
        keyboard.append([{"text": label, "callback_data": f"{action}:{plan['id']}"}])
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


async def send_plan_edit_field_keyboard(chat_id: int, plan_id: str) -> dict:
    keyboard = [
        [
            {"text": "Name", "callback_data": f"editplanfield:item:{plan_id}"},
            {"text": "Category", "callback_data": f"editplanfield:category:{plan_id}"},
        ],
        [
            {"text": "Amount", "callback_data": f"editplanfield:amount:{plan_id}"},
            {"text": "Day", "callback_data": f"editplanfield:day:{plan_id}"},
        ],
        [
            {"text": "Months", "callback_data": f"editplanfield:months:{plan_id}"},
        ],
    ]
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": "Choose what to edit:",
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def send_plan_rewrite_keyboard(chat_id: int) -> dict:
    keyboard = [[
        {"text": "Future only", "callback_data": "planrewrite:future"},
        {"text": "Rewrite past auto charges", "callback_data": "planrewrite:rewrite"},
    ]]
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": "Should this edit affect only future charges, or also rewrite past auto-generated charges for this plan?",
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
        {"command": "delete_last", "description": "Delete the last recorded transaction"},
        {"command": "delete_today", "description": "Delete a transactions from today"},
        {"command": "delete_past", "description": "Delete a transactions in a specific date"},
        {"command": "new_category", "description": "Add a new spending category"},
        {"command": "remove_category", "description": "Remove a spending category"},
        {"command": "edit_category", "description": "Edit a category's emoji, name, or order"},
        {"command": "set_recurring", "description": "Create a monthly recurring payment"},
        {"command": "list_recurring", "description": "List recurring payment plans"},
        {"command": "edit_recurring", "description": "Edit a recurring payment plan"},
        {"command": "delete_recurring", "description": "Delete a recurring payment plan"},
        {"command": "split_payment", "description": "Split one payment across monthly charges"},
        {"command": "list_split_payment", "description": "List split payment plans"},
        {"command": "edit_split_payment", "description": "Edit a split payment plan"},
        {"command": "delete_split_payment", "description": "Delete a split payment plan"},
    ]
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("setMyCommands"),
            json={"commands": commands},
        )
        return resp.json()

