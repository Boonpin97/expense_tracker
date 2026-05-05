import calendar
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from models.transaction import Transaction
from services import firestore, telegram

SGT = timezone(timedelta(hours=8))
PENDING_EXPIRY_SECONDS = 180


async def _check_budget_exceeded(chat_id: int, category: str) -> None:
    """Warn the user if spending in *category* has exceeded the pro-rated budget."""
    budgets = firestore.get_budgets(chat_id)
    monthly_limit = budgets.get(category)
    if monthly_limit is None:
        return

    now = datetime.now(SGT)
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    prorated = monthly_limit / days_in_month * now.day

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    txs = firestore.get_transactions(chat_id, month_start, month_end + timedelta(seconds=1))

    spent = sum(tx["amount"] for tx in txs if tx.get("category") == category)
    if spent > prorated:
        await telegram.send_message(
            chat_id,
            f"❗️ <b>{category}</b> budget exceeded! "
            f"${spent:.2f} spent vs ${prorated:.2f} budget so far this month.",
        )


def _normalise(item: str) -> str:
    return re.sub(r"[^\w\s]", "", item).strip().lower()


def build_transaction_timestamp(
    transaction_date: Optional[str] = None,
    base_timestamp: Optional[str] = None,
) -> str:
    if base_timestamp:
        base_dt = datetime.fromisoformat(base_timestamp).astimezone(SGT)
    else:
        base_dt = datetime.now(SGT)

    if not transaction_date:
        return base_dt.isoformat()

    date_part = datetime.strptime(transaction_date, "%Y-%m-%d").date()
    resolved = datetime.combine(date_part, base_dt.time()).replace(tzinfo=SGT)
    return resolved.isoformat()


def pending_expired(pending: dict) -> bool:
    created_at = pending.get("created_at") or pending.get("timestamp")
    return (datetime.now(SGT) - datetime.fromisoformat(created_at)).total_seconds() > PENDING_EXPIRY_SECONDS


async def handle_expense(
    chat_id: int,
    item: str,
    amount: float,
    transaction_date: Optional[str] = None,
) -> None:
    item_key = _normalise(item)
    category = firestore.get_category(item_key)
    timestamp = build_transaction_timestamp(transaction_date)
    date_was_explicit = transaction_date is not None

    if category:
        tx = Transaction(
            item=item,
            amount=amount,
            category=category,
            timestamp=timestamp,
            chat_id=chat_id,
        )
        tx_id = firestore.save_transaction(tx)
        await telegram.send_transaction_confirmation(
            chat_id,
            item,
            amount,
            category,
            tx_id=tx_id,
            item_key=item_key,
            include_change_date=not date_was_explicit,
        )
        await _check_budget_exceeded(chat_id, category)
    else:
        firestore.save_pending(
            chat_id,
            item,
            amount,
            timestamp=timestamp,
            date_was_explicit=date_was_explicit,
        )
        await telegram.send_category_keyboard(chat_id, item, amount)


async def handle_category_selection(chat_id: int, category: str, callback_query_id: str) -> None:
    if category == "__new__":
        pending_change = firestore.get_pending_change(chat_id)
        if pending_change:
            # Change-category flow: check pending_change expiry
            change_ts = pending_change.get("timestamp")
            if change_ts and (datetime.now(SGT) - datetime.fromisoformat(change_ts)).total_seconds() > PENDING_EXPIRY_SECONDS:
                firestore.delete_pending_change(chat_id)
                await telegram.answer_callback_query(callback_query_id, "⏰ This selection has expired.")
                await telegram.send_message(chat_id, "⏰ The change category option has expired. Tap 🔄 Change category again to retry.")
                return
            firestore.set_user_state(chat_id, f"awaiting_change_new_name:{pending_change['tx_id']}:{pending_change['item_key']}")
        else:
            # New expense flow: check pending expiry before entering name input
            pending = firestore.get_pending(chat_id)
            if not pending:
                await telegram.answer_callback_query(callback_query_id, "No pending expense found.")
                return
            if pending_expired(pending):
                firestore.delete_pending(chat_id)
                await telegram.answer_callback_query(callback_query_id, "⏰ This selection has expired.")
                await telegram.send_message(
                    chat_id,
                    f"⏰ The category buttons for <b>{pending['item']}</b> have expired. Please resend the expense to try again.",
                )
                return
            firestore.set_user_state(chat_id, "awaiting_inline_cat_name")
        await telegram.answer_callback_query(callback_query_id, "")
        await telegram.send_message(chat_id, "✏️ Type the name of the new category:")
        return

    # Check if this is a category change (not a new transaction)
    pending_change = firestore.get_pending_change(chat_id)
    if pending_change:
        change_ts = pending_change.get("timestamp")
        if change_ts and (datetime.now(SGT) - datetime.fromisoformat(change_ts)).total_seconds() > PENDING_EXPIRY_SECONDS:
            firestore.delete_pending_change(chat_id)
            firestore.clear_user_state(chat_id)
            await telegram.answer_callback_query(callback_query_id, "⏰ This selection has expired.")
            await telegram.send_message(chat_id, "⏰ The change category option has expired. Tap 🔄 Change category again to retry.")
            return
        tx_id = pending_change["tx_id"]
        item_key = pending_change["item_key"]
        firestore.update_transaction_category(tx_id, category)
        firestore.save_category(item_key, category, confirmed_by_user=True)
        firestore.delete_pending_change(chat_id)
        await telegram.answer_callback_query(callback_query_id, f"Changed to {category}")
        await telegram.send_message(chat_id, f"🔄 <b>{item_key}</b> recategorised to <b>{category}</b>")
        return

    pending = firestore.get_pending(chat_id)
    if not pending:
        await telegram.answer_callback_query(callback_query_id, "No pending expense found.")
        return

    item = pending["item"]
    amount = pending["amount"]
    timestamp = pending["timestamp"]
    include_change_date = not pending.get("date_was_explicit", False)

    if pending_expired(pending):
        firestore.delete_pending(chat_id)
        await telegram.answer_callback_query(callback_query_id, "⏰ This selection has expired.")
        await telegram.send_message(
            chat_id,
            f"⏰ The category buttons for <b>{item}</b> have expired. Please resend the expense to try again.",
        )
        return

    item_key = _normalise(item)

    tx = Transaction(
        item=item,
        amount=amount,
        category=category,
        timestamp=timestamp,
        chat_id=chat_id,
    )
    tx_id = firestore.save_transaction(tx)
    firestore.save_category(item_key, category, confirmed_by_user=True)
    firestore.delete_pending(chat_id)

    await telegram.answer_callback_query(callback_query_id, f"Saved as {category}")
    await telegram.send_transaction_confirmation(
        chat_id,
        item,
        amount,
        category,
        tx_id=tx_id,
        item_key=item_key,
        include_change_date=include_change_date,
    )
    await _check_budget_exceeded(chat_id, category)


async def handle_custom_category_input(chat_id: int, category_name: str, emoji: str = "🏷️") -> None:
    pending = firestore.get_pending(chat_id)
    if not pending:
        await telegram.send_message(chat_id, "⚠️ No pending expense found. Please send your expense again.")
        return

    item = pending["item"]
    amount = pending["amount"]
    timestamp = pending["timestamp"]
    include_change_date = not pending.get("date_was_explicit", False)

    if pending_expired(pending):
        firestore.delete_pending(chat_id)
        await telegram.send_message(
            chat_id,
            f"⏰ The category buttons for <b>{item}</b> have expired. Please resend the expense to try again.",
        )
        return

    item_key = _normalise(item)
    category = category_name.strip().title()

    tx = Transaction(
        item=item,
        amount=amount,
        category=category,
        timestamp=timestamp,
        chat_id=chat_id,
    )
    tx_id = firestore.save_transaction(tx)
    firestore.save_category(item_key, category, confirmed_by_user=True)
    firestore.add_category_to_list(category, emoji)
    firestore.delete_pending(chat_id)

    await telegram.send_transaction_confirmation(
        chat_id,
        item,
        amount,
        category,
        tx_id=tx_id,
        item_key=item_key,
        note="New category saved",
        include_change_date=include_change_date,
    )
    await _check_budget_exceeded(chat_id, category)
