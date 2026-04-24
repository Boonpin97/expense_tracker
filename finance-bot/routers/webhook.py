import os
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request, HTTPException

from services.parser import parse_expense
from services.categoriser import handle_expense, handle_category_selection, handle_custom_category_input, PENDING_EXPIRY_SECONDS
from services import telegram
from routers.reports import _get_period_window, _format_report
from services.firestore import (
    get_transactions, get_transactions_with_ids, get_last_transaction, delete_transaction, get_transaction_by_id,
    is_awaiting_custom_category, set_user_state, get_user_state, clear_user_state,
    get_category_list, add_category_to_list, remove_category_from_list, delete_category,
    reassign_transactions_category, get_pending, delete_pending, get_pending_change, delete_pending_change,
    save_pending_change, update_transaction_category, save_category,
    update_category_emoji, update_category_order, rename_category,
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


def _is_expired(timestamp_iso: str) -> bool:
    try:
        created_at = datetime.fromisoformat(timestamp_iso)
        return (datetime.now(SGT) - created_at).total_seconds() > PENDING_EXPIRY_SECONDS
    except Exception:
        return False


@router.post("/webhook")
async def webhook(request: Request):
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    if secret:
        token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if token != secret:
            raise HTTPException(status_code=403, detail="Forbidden")

    data = await request.json()

    # Handle callback_query (button tap)
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
            remainder = callback_data[4:]
            # Format: del:<doc_id>:<timestamp> (timestamp optional for backward compat)
            colon_pos = remainder.find(":")
            if colon_pos != -1:
                doc_id = remainder[:colon_pos]
                ts = remainder[colon_pos + 1:]
                if _is_expired(ts):
                    await telegram.answer_callback_query(callback_query_id, "⏰ Expired.")
                    await telegram.send_message(chat_id, "⏰ These delete options have expired. Please send the command again.")
                    return {"ok": True}
            else:
                doc_id = remainder
            tx = get_transaction_by_id(doc_id)
            delete_transaction(doc_id)
            await telegram.answer_callback_query(callback_query_id, "Deleted!")
            if tx:
                ts = datetime.fromisoformat(tx["timestamp"]).astimezone(SGT)
                date_str = ts.strftime("%d %b %Y, %I:%M %p")
                await telegram.send_message(
                    chat_id,
                    f"🗑️ Deleted: <b>{tx['item']}</b>\n"
                    f"💰 ${tx['amount']:.2f} · 🏷️ {tx['category']}\n"
                    f"🕐 {date_str}",
                )
            else:
                await telegram.send_message(chat_id, "🗑️ Transaction deleted.")

        elif callback_data.startswith("rmcat:"):
            remainder = callback_data[6:]
            # Format: rmcat:<name>|<timestamp> (timestamp optional for backward compat)
            if "|" in remainder:
                category_name, ts = remainder.split("|", 1)
                if _is_expired(ts):
                    await telegram.answer_callback_query(callback_query_id, "⏰ Expired.")
                    await telegram.send_message(chat_id, "⏰ These options have expired. Please send /remove_category again.")
                    return {"ok": True}
            else:
                category_name = remainder
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
                save_pending_change(chat_id, tx_id, item_key)
                await telegram.answer_callback_query(callback_query_id, "")
                await telegram.send_category_keyboard(chat_id, item_key, 0)

        elif callback_data.startswith("editcat:"):
            remainder = callback_data[8:]
            if "|" in remainder:
                category_name, ts = remainder.split("|", 1)
                if _is_expired(ts):
                    await telegram.answer_callback_query(callback_query_id, "⏰ Expired.")
                    await telegram.send_message(chat_id, "⏰ These options have expired. Please send /edit_category again.")
                    return {"ok": True}
            else:
                category_name = remainder
            cat = next((c for c in get_category_list() if c["name"] == category_name), None)
            if not cat:
                await telegram.answer_callback_query(callback_query_id, "Not found")
                await telegram.send_message(chat_id, f"⚠️ Category <b>{category_name}</b> not found.")
                return {"ok": True}
            await telegram.answer_callback_query(callback_query_id, "")
            await telegram.send_edit_category_field_keyboard(chat_id, category_name, cat.get("emoji", "🏷️"))

        elif callback_data.startswith("editfield:"):
            remainder = callback_data[10:]
            # editfield:<field>:<name>|<ts>
            if "|" in remainder:
                body, ts = remainder.split("|", 1)
                if _is_expired(ts):
                    await telegram.answer_callback_query(callback_query_id, "⏰ Expired.")
                    await telegram.send_message(chat_id, "⏰ These options have expired. Please send /edit_category again.")
                    return {"ok": True}
            else:
                body = remainder
            field, _, category_name = body.partition(":")
            if field not in ("emoji", "name", "order") or not category_name:
                await telegram.answer_callback_query(callback_query_id, "Invalid")
                return {"ok": True}
            now_iso = datetime.now(SGT).isoformat()
            set_user_state(chat_id, f"awaiting_edit_cat_{field}:{category_name}|{now_iso}")
            await telegram.answer_callback_query(callback_query_id, "")
            if field == "emoji":
                prompt = f"Send the new emoji for <b>{category_name}</b>:"
            elif field == "name":
                prompt = f"Send the new name for <b>{category_name}</b>:"
            else:
                max_order = len([c for c in get_category_list() if c["name"] != "Other"])
                prompt = (
                    f"Send the new order number for <b>{category_name}</b> "
                    f"(1 = top, max {max_order}). Existing categories at or below this "
                    f"number will shift down by 1."
                )
            await telegram.send_message(chat_id, prompt)

        return {"ok": True}

    # Handle message
    if "message" in data:
        message = data["message"]
        chat_id = message["chat"]["id"]

        if chat_id not in _get_allowed_chat_ids():
            return {"ok": True}

        text = message.get("text", "")

        if text.startswith("/"):
            if text == "/start":
                await telegram.send_message(
                    chat_id,
                    "👋 Welcome! Send me an expense like <b>Coffee $10</b> and I'll track it for you.",
                )
            elif text.startswith("/report"):
                parts = text.split()
                if len(parts) < 2:
                    await telegram.send_message(chat_id, "Usage: <code>/report 2026-04-01</code>")
                else:
                    arg = parts[1]
                    if not re.match(r"^\d{4}-\d{2}-\d{2}$", arg):
                        await telegram.send_message(chat_id, "Invalid date. Use <code>YYYY-MM-DD</code>, e.g. <code>/report 2026-04-01</code>")
                    else:
                        try:
                            day_start = datetime.strptime(arg, "%Y-%m-%d").replace(tzinfo=SGT)
                            day_end = day_start + timedelta(days=1)
                            label = f"Daily Report ({day_start.strftime('%d %b %Y')})"
                            transactions = get_transactions(chat_id, day_start, day_end)
                            report = _format_report(label, transactions)
                            await telegram.send_message(chat_id, f"<pre>{report}</pre>")
                        except ValueError:
                            await telegram.send_message(chat_id, "Invalid date. Use <code>YYYY-MM-DD</code>, e.g. <code>/report 2026-04-01</code>")
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
                    ts = datetime.fromisoformat(tx["timestamp"]).astimezone(SGT)
                    date_str = ts.strftime("%d %b %Y, %I:%M %p")
                    await telegram.send_message(
                        chat_id,
                        f"🗑️ Deleted: <b>{tx['item']}</b>\n"
                        f"💰 ${tx['amount']:.2f} · 🏷️ {tx['category']}\n"
                        f"🕐 {date_str}",
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
                set_user_state(chat_id, f"awaiting_new_cat_name|{datetime.now(SGT).isoformat()}")
                await telegram.send_message(chat_id, "✏️ Type the name of the new category:")
            elif text == "/remove_category":
                categories = get_category_list()
                removable = [c for c in categories if c["name"] != "Other"]
                if not removable:
                    await telegram.send_message(chat_id, "No categories to remove.")
                else:
                    await telegram.send_remove_category_keyboard(chat_id, removable)
            elif text == "/edit_category":
                categories = get_category_list()
                if not categories:
                    await telegram.send_message(chat_id, "No categories to edit.")
                else:
                    await telegram.send_edit_category_keyboard(chat_id, categories)
            return {"ok": True}

        # Check user state for multi-step flows
        user_state = get_user_state(chat_id)

        # /new_category step 1: name
        if user_state and user_state.startswith("awaiting_new_cat_name|"):
            ts = user_state[len("awaiting_new_cat_name|"):]
            if _is_expired(ts):
                clear_user_state(chat_id)
                await telegram.send_message(chat_id, "⏰ The /new_category request has expired. Please send /new_category again.")
                return {"ok": True}
            name = text.strip().title()
            existing = [c["name"] for c in get_category_list()]
            if name in existing:
                clear_user_state(chat_id)
                await telegram.send_message(chat_id, f"⚠️ Category <b>{name}</b> already exists.")
                return {"ok": True}
            set_user_state(chat_id, f"awaiting_new_cat_emoji:{name}|{ts}")
            await telegram.send_message(chat_id, f"Now send an emoji for <b>{name}</b>:")
            return {"ok": True}

        # /new_category step 2: emoji
        elif user_state and user_state.startswith("awaiting_new_cat_emoji:"):
            remainder = user_state[len("awaiting_new_cat_emoji:"):]
            if "|" in remainder:
                name, ts = remainder.rsplit("|", 1)
                if _is_expired(ts):
                    clear_user_state(chat_id)
                    await telegram.send_message(chat_id, "⏰ The /new_category request has expired. Please send /new_category again.")
                    return {"ok": True}
            else:
                name = remainder
            emoji = text.strip()
            add_category_to_list(name, emoji)
            clear_user_state(chat_id)
            await telegram.send_message(chat_id, f"✅ Category {emoji} <b>{name}</b> added!")
            return {"ok": True}

        # Inline ✏️ new category (new expense) step 1: name
        elif user_state == "awaiting_inline_cat_name":
            pending = get_pending(chat_id)
            if pending and _is_expired(pending.get("timestamp", "")):
                delete_pending(chat_id)
                clear_user_state(chat_id)
                await telegram.send_message(chat_id, "⏰ This flow has expired. Please resend the expense to try again.")
                return {"ok": True}
            name = text.strip().title()
            existing = [c["name"] for c in get_category_list()]
            if name in existing:
                clear_user_state(chat_id)
                await handle_custom_category_input(chat_id, name, next(c["emoji"] for c in get_category_list() if c["name"] == name))
                return {"ok": True}
            set_user_state(chat_id, f"awaiting_inline_cat_emoji:{name}")
            await telegram.send_message(chat_id, f"Now send an emoji for <b>{name}</b>:")
            return {"ok": True}

        # Inline ✏️ new category (new expense) step 2: emoji
        elif user_state and user_state.startswith("awaiting_inline_cat_emoji:"):
            pending = get_pending(chat_id)
            if pending and _is_expired(pending.get("timestamp", "")):
                delete_pending(chat_id)
                clear_user_state(chat_id)
                await telegram.send_message(chat_id, "⏰ This flow has expired. Please resend the expense to try again.")
                return {"ok": True}
            name = user_state[len("awaiting_inline_cat_emoji:"):]
            emoji = text.strip()
            clear_user_state(chat_id)
            await handle_custom_category_input(chat_id, name, emoji)
            return {"ok": True}

        # Change category ✏️ new category step 1: name
        elif user_state and user_state.startswith("awaiting_change_new_name:"):
            pending_change = get_pending_change(chat_id)
            if pending_change and _is_expired(pending_change.get("timestamp", "")):
                delete_pending_change(chat_id)
                clear_user_state(chat_id)
                await telegram.send_message(chat_id, "⏰ The change category option has expired. Tap 🔄 Change category again to retry.")
                return {"ok": True}
            remainder = user_state[len("awaiting_change_new_name:"):]
            tx_id, item_key = remainder.split(":", 1)
            name = text.strip().title()
            existing = [c["name"] for c in get_category_list()]
            if name in existing:
                update_transaction_category(tx_id, name)
                save_category(item_key, name, confirmed_by_user=True)
                delete_pending_change(chat_id)
                clear_user_state(chat_id)
                await telegram.send_message(chat_id, f"🔄 <b>{item_key}</b> recategorised to <b>{name}</b>")
                return {"ok": True}
            set_user_state(chat_id, f"awaiting_change_new_emoji:{name}:{tx_id}:{item_key}")
            await telegram.send_message(chat_id, f"Now send an emoji for <b>{name}</b>:")
            return {"ok": True}

        # Change category ✏️ new category step 2: emoji
        elif user_state and user_state.startswith("awaiting_change_new_emoji:"):
            pending_change = get_pending_change(chat_id)
            if pending_change and _is_expired(pending_change.get("timestamp", "")):
                delete_pending_change(chat_id)
                clear_user_state(chat_id)
                await telegram.send_message(chat_id, "⏰ The change category option has expired. Tap 🔄 Change category again to retry.")
                return {"ok": True}
            remainder = user_state[len("awaiting_change_new_emoji:"):]
            name, tx_id, item_key = remainder.split(":", 2)
            emoji = text.strip()
            update_transaction_category(tx_id, name)
            save_category(item_key, name, confirmed_by_user=True)
            add_category_to_list(name, emoji)
            delete_pending_change(chat_id)
            clear_user_state(chat_id)
            await telegram.send_message(chat_id, f"🔄 <b>{item_key}</b> recategorised to {emoji} <b>{name}</b> (new category saved)")
            return {"ok": True}

        # /edit_category — emoji
        elif user_state and user_state.startswith("awaiting_edit_cat_emoji:"):
            remainder = user_state[len("awaiting_edit_cat_emoji:"):]
            if "|" in remainder:
                category_name, ts = remainder.rsplit("|", 1)
                if _is_expired(ts):
                    clear_user_state(chat_id)
                    await telegram.send_message(chat_id, "⏰ The /edit_category request has expired. Please send /edit_category again.")
                    return {"ok": True}
            else:
                category_name = remainder
            emoji = text.strip()
            ok = update_category_emoji(category_name, emoji)
            clear_user_state(chat_id)
            if ok:
                await telegram.send_message(chat_id, f"✅ Updated emoji for <b>{category_name}</b> → {emoji}")
            else:
                await telegram.send_message(chat_id, f"⚠️ Category <b>{category_name}</b> not found.")
            return {"ok": True}

        # /edit_category — name
        elif user_state and user_state.startswith("awaiting_edit_cat_name:"):
            remainder = user_state[len("awaiting_edit_cat_name:"):]
            if "|" in remainder:
                category_name, ts = remainder.rsplit("|", 1)
                if _is_expired(ts):
                    clear_user_state(chat_id)
                    await telegram.send_message(chat_id, "⏰ The /edit_category request has expired. Please send /edit_category again.")
                    return {"ok": True}
            else:
                category_name = remainder
            new_name = text.strip().title()
            if category_name == "Other":
                clear_user_state(chat_id)
                await telegram.send_message(chat_id, "⚠️ The <b>Other</b> category cannot be renamed.")
                return {"ok": True}
            if not new_name:
                clear_user_state(chat_id)
                await telegram.send_message(chat_id, "⚠️ Name cannot be empty.")
                return {"ok": True}
            if new_name == category_name:
                clear_user_state(chat_id)
                await telegram.send_message(chat_id, "ℹ️ Name unchanged.")
                return {"ok": True}
            existing = [c["name"] for c in get_category_list()]
            if new_name in existing:
                clear_user_state(chat_id)
                await telegram.send_message(chat_id, f"⚠️ Category <b>{new_name}</b> already exists.")
                return {"ok": True}
            ok, tx_count, map_count = rename_category(category_name, new_name)
            clear_user_state(chat_id)
            if ok:
                msg = f"✅ Renamed <b>{category_name}</b> → <b>{new_name}</b>"
                if tx_count or map_count:
                    msg += f"\n🔄 Updated {tx_count} transaction(s) and {map_count} item mapping(s)."
                await telegram.send_message(chat_id, msg)
            else:
                await telegram.send_message(chat_id, f"⚠️ Could not rename <b>{category_name}</b>.")
            return {"ok": True}

        # /edit_category — order
        elif user_state and user_state.startswith("awaiting_edit_cat_order:"):
            remainder = user_state[len("awaiting_edit_cat_order:"):]
            if "|" in remainder:
                category_name, ts = remainder.rsplit("|", 1)
                if _is_expired(ts):
                    clear_user_state(chat_id)
                    await telegram.send_message(chat_id, "⏰ The /edit_category request has expired. Please send /edit_category again.")
                    return {"ok": True}
            else:
                category_name = remainder
            if category_name == "Other":
                clear_user_state(chat_id)
                await telegram.send_message(chat_id, "⚠️ The <b>Other</b> category's order cannot be changed.")
                return {"ok": True}
            raw = text.strip()
            try:
                order = int(raw)
            except ValueError:
                clear_user_state(chat_id)
                await telegram.send_message(chat_id, "⚠️ Order must be an integer. Try /edit_category again.")
                return {"ok": True}
            non_other = [c for c in get_category_list() if c["name"] != "Other"]
            max_order = len(non_other)
            if order < 1 or order > max_order:
                clear_user_state(chat_id)
                await telegram.send_message(
                    chat_id,
                    f"⚠️ Order must be between <b>1</b> and <b>{max_order}</b>. Try /edit_category again.",
                )
                return {"ok": True}
            ok = update_category_order(category_name, order)
            clear_user_state(chat_id)
            if ok:
                await telegram.send_message(chat_id, f"✅ Updated order for <b>{category_name}</b> → {order}")
            else:
                await telegram.send_message(chat_id, f"⚠️ Category <b>{category_name}</b> not found.")
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