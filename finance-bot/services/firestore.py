import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from google.cloud import firestore

from models.transaction import Transaction, PendingTransaction, CategoryMapping

SGT = timezone(timedelta(hours=8))

_db: Optional[firestore.Client] = None


def get_db() -> firestore.Client:
    global _db
    if _db is None:
        project_id = os.getenv("FIRESTORE_PROJECT_ID")
        database = os.getenv("FIRESTORE_DATABASE", "(default)")
        _db = firestore.Client(project=project_id, database=database)
    return _db


# ── Category Map ──────────────────────────────────────────────

def get_category(item_key: str) -> Optional[str]:
    doc = get_db().collection("category_map").document(item_key).get()
    if doc.exists:
        return doc.to_dict().get("category")
    return None


def save_category(item_key: str, category: str, confirmed_by_user: bool = True) -> None:
    now = datetime.now(SGT).isoformat()
    mapping = CategoryMapping(
        item_key=item_key,
        category=category,
        confirmed_by_user=confirmed_by_user,
        created_at=now,
    )
    get_db().collection("category_map").document(item_key).set(mapping.model_dump())


# ── Transactions ──────────────────────────────────────────────

def save_transaction(tx: Transaction) -> str:
    doc_ref = get_db().collection("transactions").document()
    tx.id = doc_ref.id
    doc_ref.set(tx.model_dump())
    return doc_ref.id


def get_transactions(chat_id: int, start: datetime, end: datetime) -> list[dict]:
    start_iso = start.isoformat()
    end_iso = end.isoformat()

    docs = (
        get_db()
        .collection("transactions")
        .where("chat_id", "==", chat_id)
        .where("timestamp", ">=", start_iso)
        .where("timestamp", "<", end_iso)
        .stream()
    )
    return [doc.to_dict() for doc in docs]


# ── Pending Transactions (temp storage for category selection) ─

def save_pending(chat_id: int, item: str, amount: float) -> None:
    now = datetime.now(SGT).isoformat()
    pending = PendingTransaction(
        item=item,
        amount=amount,
        chat_id=chat_id,
        timestamp=now,
    )
    get_db().collection("pending").document(str(chat_id)).set(pending.model_dump())


def get_pending(chat_id: int) -> Optional[dict]:
    doc = get_db().collection("pending").document(str(chat_id)).get()
    if doc.exists:
        return doc.to_dict()
    return None


def delete_pending(chat_id: int) -> None:
    get_db().collection("pending").document(str(chat_id)).delete()


# ── Transactions (extended) ───────────────────────────────────

def get_transactions_with_ids(chat_id: int, start: datetime, end: datetime) -> list[dict]:
    docs = (
        get_db()
        .collection("transactions")
        .where("chat_id", "==", chat_id)
        .where("timestamp", ">=", start.isoformat())
        .where("timestamp", "<", end.isoformat())
        .stream()
    )
    result = []
    for doc in docs:
        d = doc.to_dict()
        d["_doc_id"] = doc.id
        result.append(d)
    return result


def get_last_transaction(chat_id: int) -> Optional[dict]:
    docs = (
        get_db()
        .collection("transactions")
        .where("chat_id", "==", chat_id)
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .limit(1)
        .stream()
    )
    for doc in docs:
        d = doc.to_dict()
        d["_doc_id"] = doc.id
        return d
    return None


def get_transaction_by_id(doc_id: str) -> Optional[dict]:
    doc = get_db().collection("transactions").document(doc_id).get()
    if doc.exists:
        d = doc.to_dict()
        d["_doc_id"] = doc.id
        return d
    return None


def delete_transaction(doc_id: str) -> None:
    get_db().collection("transactions").document(doc_id).delete()


def update_transaction_category(doc_id: str, category: str) -> None:
    get_db().collection("transactions").document(doc_id).update({"category": category})


def update_transaction_timestamp(doc_id: str, new_timestamp: str) -> None:
    get_db().collection("transactions").document(doc_id).update({"timestamp": new_timestamp})


def reassign_transactions_category(old_category: str, new_category: str) -> int:
    docs = (
        get_db()
        .collection("transactions")
        .where("category", "==", old_category)
        .stream()
    )
    count = 0
    for doc in docs:
        doc.reference.update({"category": new_category})
        count += 1
    return count


# ── User State ────────────────────────────────────────────────

def set_user_state(chat_id: int, state: str) -> None:
    get_db().collection("user_state").document(str(chat_id)).set({"state": state})


def get_user_state(chat_id: int) -> Optional[str]:
    doc = get_db().collection("user_state").document(str(chat_id)).get()
    if doc.exists:
        return doc.to_dict().get("state")
    return None


def clear_user_state(chat_id: int) -> None:
    get_db().collection("user_state").document(str(chat_id)).delete()


def is_awaiting_custom_category(chat_id: int) -> bool:
    state = get_user_state(chat_id)
    return state is not None and "awaiting" in state


# ── Pending Category Change ───────────────────────────────────

def save_pending_change(chat_id: int, tx_id: str, item_key: str) -> None:
    get_db().collection("pending_change").document(str(chat_id)).set({
        "tx_id": tx_id,
        "item_key": item_key,
        "timestamp": datetime.now(SGT).isoformat(),
    })


def get_pending_change(chat_id: int) -> Optional[dict]:
    doc = get_db().collection("pending_change").document(str(chat_id)).get()
    if doc.exists:
        return doc.to_dict()
    return None


def delete_pending_change(chat_id: int) -> None:
    get_db().collection("pending_change").document(str(chat_id)).delete()


# ── Category List ─────────────────────────────────────────────

DEFAULT_CATEGORIES = [
    {"name": "Food & Drink", "emoji": "🍔", "order": 1},
    {"name": "Transport", "emoji": "🚗", "order": 2},
    {"name": "Housing", "emoji": "🏠", "order": 3},
    {"name": "Health", "emoji": "💊", "order": 4},
    {"name": "Entertainment", "emoji": "🎬", "order": 5},
    {"name": "Shopping", "emoji": "🛍️", "order": 6},
    {"name": "Utilities", "emoji": "💡", "order": 7},
    {"name": "Other", "emoji": "📦", "order": 9999},
]


def _seed_category_list() -> None:
    coll = get_db().collection("category_list")
    existing = list(coll.limit(1).stream())
    if existing:
        return
    for cat in DEFAULT_CATEGORIES:
        coll.document(cat["name"]).set(cat)


def get_category_list() -> list[dict]:
    _seed_category_list()
    docs = get_db().collection("category_list").stream()
    categories = [doc.to_dict() for doc in docs]
    categories.sort(key=lambda c: c.get("order", 9998))
    return categories


def add_category_to_list(name: str, emoji: str = "🏷️") -> None:
    coll = get_db().collection("category_list")
    all_cats = get_category_list()
    max_order = max((c.get("order", 0) for c in all_cats if c.get("order", 0) < 9999), default=100)
    coll.document(name).set({"name": name, "emoji": emoji, "order": max_order + 1})


def remove_category_from_list(name: str) -> bool:
    doc_ref = get_db().collection("category_list").document(name)
    doc = doc_ref.get()
    if doc.exists:
        doc_ref.delete()
        return True
    return False


def delete_category(category_name: str) -> int:
    docs = (
        get_db()
        .collection("category_map")
        .where("category", "==", category_name)
        .stream()
    )
    count = 0
    for doc in docs:
        doc.reference.delete()
        count += 1
    return count


# ── Authorized Chat IDs ───────────────────────────────────────

_allowed_chat_ids: set[int] = set()
_chat_ids_listener = None


def _on_authorized_chats_snapshot(col_snapshot, changes, read_time):
    global _allowed_chat_ids
    _allowed_chat_ids = set()
    for doc in col_snapshot:
        try:
            _allowed_chat_ids.add(int(doc.id))
        except ValueError:
            pass


def start_authorized_chats_listener() -> None:
    global _chat_ids_listener
    if _chat_ids_listener is not None:
        return
    col_ref = get_db().collection("authorized_chats")
    _chat_ids_listener = col_ref.on_snapshot(_on_authorized_chats_snapshot)


def get_allowed_chat_ids() -> set[int]:
    return _allowed_chat_ids


def add_authorized_chat(chat_id: int) -> None:
    get_db().collection("authorized_chats").document(str(chat_id)).set({})


def remove_authorized_chat(chat_id: int) -> None:
    get_db().collection("authorized_chats").document(str(chat_id)).delete()
