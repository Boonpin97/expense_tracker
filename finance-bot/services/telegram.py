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
    from services.firestore import get_all_categories

    DEFAULT_CATEGORIES = {
        "Food & Drink": "🍔",
        "Transport": "🚗",
        "Housing": "🏠",
        "Health": "💊",
        "Entertainment": "🎬",
        "Shopping": "🛍️",
        "Utilities": "💡",
        "Other": "📦",
    }

    # Start with default categories
    categories = [(f"{emoji} {name}", f"cat:{name}") for name, emoji in DEFAULT_CATEGORIES.items()]

    # Add custom categories from Firestore
    all_cats = get_all_categories()
    for cat in all_cats:
        if cat not in DEFAULT_CATEGORIES:
            categories.append((f"🏷️ {cat}", f"cat:{cat}"))

    # Always add "New category" at the end
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


async def send_transaction_keyboard(chat_id: int, transactions: list[dict], prompt: str) -> dict:
    """Send an inline keyboard where each button is a transaction to delete."""
    keyboard = []
    for tx in transactions:
        label = f"❌ {tx['item']} — ${tx['amount']:.2f} ({tx['category']})"
        callback_data = f"del:{tx['_doc_id']}"
        keyboard.append([{"text": label, "callback_data": callback_data}])

    async with httpx.AsyncClient() as client:
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
