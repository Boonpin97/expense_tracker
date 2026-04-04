import re
from datetime import datetime, timedelta, timezone

from models.transaction import Transaction
from services import firestore, telegram

SGT = timezone(timedelta(hours=8))


def _normalise(item: str) -> str:
    return re.sub(r"[^\w\s]", "", item).strip().lower()


async def handle_expense(chat_id: int, item: str, amount: float) -> None:
    item_key = _normalise(item)
    category = firestore.get_category(item_key)

    if category:
        tx = Transaction(
            item=item,
            amount=amount,
            category=category,
            timestamp=datetime.now(SGT).isoformat(),
            chat_id=chat_id,
        )
        tx_id = firestore.save_transaction(tx)
        await telegram.send_message_with_change_category(
            chat_id,
            f"✅ <b>{item}</b> — ${amount:.2f} → {category}",
            tx_id,
            item_key,
        )
    else:
        firestore.save_pending(chat_id, item, amount)
        await telegram.send_category_keyboard(chat_id, item, amount)


async def handle_category_selection(chat_id: int, category: str, callback_query_id: str) -> None:
    if category == "__new__":
        # Check if this is a change-category flow or new-expense flow
        pending_change = firestore.get_pending_change(chat_id)
        if pending_change:
            firestore.set_user_state(chat_id, f"awaiting_change_new_name:{pending_change['tx_id']}:{pending_change['item_key']}")
        else:
            firestore.set_user_state(chat_id, "awaiting_inline_cat_name")
        await telegram.answer_callback_query(callback_query_id, "")
        await telegram.send_message(chat_id, "✏️ Type the name of the new category:")
        return

    # Check if this is a category change (not a new transaction)
    pending_change = firestore.get_pending_change(chat_id)
    if pending_change:
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
    item_key = _normalise(item)

    tx = Transaction(
        item=item,
        amount=amount,
        category=category,
        timestamp=timestamp,
        chat_id=chat_id,
    )
    firestore.save_transaction(tx)
    firestore.save_category(item_key, category, confirmed_by_user=True)
    firestore.delete_pending(chat_id)

    await telegram.answer_callback_query(callback_query_id, f"Saved as {category}")
    await telegram.send_message(
        chat_id,
        f"✅ <b>{item}</b> — ${amount:.2f} → {category}",
    )


async def handle_custom_category_input(chat_id: int, category_name: str, emoji: str = "🏷️") -> None:
    pending = firestore.get_pending(chat_id)
    if not pending:
        await telegram.send_message(chat_id, "⚠️ No pending expense found. Please send your expense again.")
        return

    item = pending["item"]
    amount = pending["amount"]
    timestamp = pending["timestamp"]
    item_key = _normalise(item)
    category = category_name.strip().title()

    tx = Transaction(
        item=item,
        amount=amount,
        category=category,
        timestamp=timestamp,
        chat_id=chat_id,
    )
    firestore.save_transaction(tx)
    firestore.save_category(item_key, category, confirmed_by_user=True)
    firestore.add_category_to_list(category, emoji)
    firestore.delete_pending(chat_id)

    await telegram.send_message(
        chat_id,
        f"✅ <b>{item}</b> — ${amount:.2f} → {category} (new category saved)",
    )
