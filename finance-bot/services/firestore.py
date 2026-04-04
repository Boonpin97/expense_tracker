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
        _db = firestore.Client(project=project_id)
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


def get_transactions_with_ids(chat_id: int, start: datetime, end: datetime) -> list[dict]:
    """Like get_transactions but includes the Firestore document ID."""
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
    results = []
    for doc in docs:
        data = doc.to_dict()
        data["_doc_id"] = doc.id
        results.append(data)
    return results


def get_last_transaction(chat_id: int) -> Optional[dict]:
    """Get the most recent transaction for a chat."""
    docs = (
        get_db()
        .collection("transactions")
        .where("chat_id", "==", chat_id)
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .limit(1)
        .stream()
    )
    for doc in docs:
        data = doc.to_dict()
        data["_doc_id"] = doc.id
        return data
    return None


def delete_transaction(doc_id: str) -> None:
    get_db().collection("transactions").document(doc_id).delete()


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


def set_awaiting_custom_category(chat_id: int) -> None:
    get_db().collection("pending").document(str(chat_id)).update({"awaiting_custom_category": True})


def is_awaiting_custom_category(chat_id: int) -> bool:
    pending = get_pending(chat_id)
    return bool(pending and pending.get("awaiting_custom_category"))


# ── User State (for standalone command flows) ─────────────────

def set_user_state(chat_id: int, state: str) -> None:
    get_db().collection("user_state").document(str(chat_id)).set({"state": state})


def get_user_state(chat_id: int) -> Optional[str]:
    doc = get_db().collection("user_state").document(str(chat_id)).get()
    if doc.exists:
        return doc.to_dict().get("state")
    return None


def clear_user_state(chat_id: int) -> None:
    get_db().collection("user_state").document(str(chat_id)).delete()


# ── Category Management ───────────────────────────────────────

def get_all_categories() -> list[str]:
    """Return sorted unique list of all categories in category_map."""
    docs = get_db().collection("category_map").stream()
    categories = {doc.to_dict().get("category") for doc in docs if doc.to_dict().get("category")}
    return sorted(categories)


def delete_category(category_name: str) -> int:
    """Delete all category_map entries with the given category. Returns count deleted."""
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
