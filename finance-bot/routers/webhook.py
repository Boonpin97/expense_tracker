import os
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request

from services.parser import parse_expense
from services.categoriser import handle_expense, handle_category_selection, handle_custom_category_input
from services import telegram
from routers.reports import _get_period_window, _format_report
from services.firestore import (
    get_transactions, get_transactions_with_ids, get_last_transaction, delete_transaction,
    is_awaiting_custom_category, set_user_state, get_user_state, clear_user_state,
    get_category_list, add_category_to_list, remove_category_from_list, delete_category,
    reassign_transactions_category,
)

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
        elif callback_data.startswith("rmcat:"):
            category_name = callback_data[6:]
            removed = remove_category_from_list(category_name)
            count = delete_category(category_name)
            tx_count = reassign_transactions_category(category_name, "Other")
            if removed:
                await telegram.answer_callback_query(callback_query_id, f"Removed {category_name}")
                msg = f"🗑️ Removed category <b>{category_name}</b> and {count} item mapping(s)."
                if tx_count > 0:
                    msg += f"\n🔄 {tx_count} transaction(s) reassigned to <b>Other</b>."
                await telegram.send_message(chat_id, msg)
            else:
                await telegram.answer_callback_query(callback_query_id, "Not found")
                await telegram.send_message(chat_id, f"⚠️ Category <b>{category_name}</b> not found.")
        elif callback_data.startswith("chgcat:"):
            # chgcat:<tx_id>:<item_key>
            parts = callback_data[7:].split(":", 1)
            if len(parts) == 2:
                tx_id, item_key = parts
                # Store tx_id and item_key so category selection can update them
                from services.firestore import save_pending_change
                save_pending_change(chat_id, tx_id, item_key)
                await telegram.answer_callback_query(callback_query_id, "")
                await telegram.send_category_keyboard(chat_id, item_key, 0)

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
            elif text == "/new_category":
                set_user_state(chat_id, "awaiting_new_category")
                await telegram.send_message(chat_id, "✏️ Type the name of the new category to add:")
            elif text == "/remove_category":
                categories = get_category_list()
                removable = [c for c in categories if c["name"] != "Other"]
                if not removable:
                    await telegram.send_message(chat_id, "No categories to remove.")
                else:
                    await telegram.send_remove_category_keyboard(chat_id, removable)
            return {"ok": True}

        # Check user state for standalone command flows
        user_state = get_user_state(chat_id)
        if user_state == "awaiting_new_category":
            new_cat = text.strip().title()
            add_category_to_list(new_cat)
            clear_user_state(chat_id)
            await telegram.send_message(chat_id, f"✅ Category <b>{new_cat}</b> added! It will now appear in the category keyboard.")
            return {"ok": True}
        elif user_state and user_state.startswith("awaiting_change_cat:"):
            # awaiting_change_cat:<tx_id>:<item_key>
            parts = user_state.split(":", 2)
            if len(parts) == 3:
                _, tx_id, item_key = parts
                new_cat = text.strip().title()
                from services.firestore import update_transaction_category, save_pending_change, delete_pending_change, save_category
                update_transaction_category(tx_id, new_cat)
                save_category(item_key, new_cat, confirmed_by_user=True)
                add_category_to_list(new_cat)
                delete_pending_change(chat_id)
                clear_user_state(chat_id)
                await telegram.send_message(chat_id, f"🔄 <b>{item_key}</b> recategorised to <b>{new_cat}</b> (new category saved)")
            return {"ok": True}

        # Check if awaiting a custom category name from inline keyboard flow
        if is_awaiting_custom_category(chat_id):
            await handle_custom_category_input(chat_id, text)
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
