import os
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request

from services.parser import parse_expense
from services.categoriser import handle_expense, handle_category_selection
from services import telegram
from routers.reports import _get_period_window, _format_report
from services.firestore import get_transactions, get_transactions_with_ids, get_last_transaction, delete_transaction

router = APIRouter()

SGT = timezone(timedelta(hours=8))

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
        elif callback_data.startswith("del:"):
            doc_id = callback_data[4:]
            delete_transaction(doc_id)
            await telegram.answer_callback_query(callback_query_id, "Deleted!")
            await telegram.send_message(chat_id, "🗑️ Transaction deleted.")

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
            elif text.startswith("/report"):
                parts = text.split()
                period = parts[1] if len(parts) > 1 else "daily"
                if period not in ("daily", "weekly", "monthly"):
                    await telegram.send_message(
                        chat_id,
                        "Usage: <code>/report daily</code>, <code>/report weekly</code>, or <code>/report monthly</code>",
                    )
                else:
                    start, end, label = _get_period_window(period)
                    transactions = get_transactions(chat_id, start, end)
                    report = _format_report(label, transactions)
                    await telegram.send_message(chat_id, f"<pre>{report}</pre>")
            elif text.startswith("/daily"):
                start, end, label = _get_period_window("daily")
                transactions = get_transactions(chat_id, start, end)
                report = _format_report(label, transactions)
                await telegram.send_message(chat_id, f"<pre>{report}</pre>")
            elif text.startswith("/weekly"):
                start, end, label = _get_period_window("weekly")
                transactions = get_transactions(chat_id, start, end)
                report = _format_report(label, transactions)
                await telegram.send_message(chat_id, f"<pre>{report}</pre>")
            elif text.startswith("/monthly"):
                start, end, label = _get_period_window("monthly")
                transactions = get_transactions(chat_id, start, end)
                report = _format_report(label, transactions)
                await telegram.send_message(chat_id, f"<pre>{report}</pre>")
            elif text.startswith("/delete_last"):
                tx = get_last_transaction(chat_id)
                if tx:
                    delete_transaction(tx["_doc_id"])
                    await telegram.send_message(
                        chat_id,
                        f"🗑️ Deleted: <b>{tx['item']}</b> — ${tx['amount']:.2f} ({tx['category']})",
                    )
                else:
                    await telegram.send_message(chat_id, "No transactions found.")
            elif text.startswith("/delete_today"):
                now = datetime.now(SGT)
                start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end = start + timedelta(days=1)
                txs = get_transactions_with_ids(chat_id, start, end)
                if txs:
                    await telegram.send_transaction_keyboard(
                        chat_id, txs, "Tap a transaction to delete it:"
                    )
                else:
                    await telegram.send_message(chat_id, "No transactions today.")
            elif text.startswith("/delete_past"):
                parts = text.split()
                if len(parts) < 2:
                    await telegram.send_message(
                        chat_id,
                        "Please provide a date.\nUsage: <code>/delete_past 2026-04-01</code>",
                    )
                else:
                    date_str = parts[1]
                    match = re.match(r"^\d{4}-\d{2}-\d{2}$", date_str)
                    if not match:
                        await telegram.send_message(
                            chat_id,
                            "Invalid date format. Use <code>YYYY-MM-DD</code>, e.g. <code>/delete_past 2026-04-01</code>",
                        )
                    else:
                        start = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=SGT)
                        end = start + timedelta(days=1)
                        txs = get_transactions_with_ids(chat_id, start, end)
                        if txs:
                            await telegram.send_transaction_keyboard(
                                chat_id, txs, f"Transactions on {date_str} — tap to delete:"
                            )
                        else:
                            await telegram.send_message(chat_id, f"No transactions on {date_str}.")
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
