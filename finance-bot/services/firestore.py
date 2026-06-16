import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote

from google.cloud import firestore

from models.transaction import (
    CategoryMapping,
    FlowSession,
    Goal,
    Inflow,
    PaymentPlan,
    PendingPlan,
    PendingTransaction,
    Project,
    Transaction,
)
from services.payment_plans import compute_next_due_date

SGT = timezone(timedelta(hours=8))

_db: Optional[firestore.Client] = None


def _category_doc_id(name: str) -> str:
    return quote(name.strip(), safe="")


def _item_map_doc_id(item_key: str) -> str:
    return quote(item_key.strip(), safe="")


def _category_list_path(chat_id: int) -> str:
    return f"users/{chat_id}/category_list"


def _category_map_path(chat_id: int) -> str:
    return f"users/{chat_id}/category_map"


def _category_list_collection(chat_id: int):
    return get_db().collection(_category_list_path(chat_id))


def _category_map_collection(chat_id: int):
    return get_db().collection(_category_map_path(chat_id))


def get_db() -> firestore.Client:
    global _db
    if _db is None:
        project_id = os.getenv("FIRESTORE_PROJECT_ID")
        database = os.getenv("FIRESTORE_DATABASE", "(default)")
        _db = firestore.Client(project=project_id, database=database)
    return _db


def get_category(chat_id: int, item_key: str) -> Optional[str]:
    doc = _category_map_collection(chat_id).document(_item_map_doc_id(item_key)).get()
    if doc.exists:
        return doc.to_dict().get("category")
    return None


def save_category(chat_id: int, item_key: str, category: str, confirmed_by_user: bool = True) -> None:
    now = datetime.now(SGT).isoformat()
    mapping = CategoryMapping(
        item_key=item_key,
        category=category,
        confirmed_by_user=confirmed_by_user,
        created_at=now,
    )
    _category_map_collection(chat_id).document(_item_map_doc_id(item_key)).set(mapping.model_dump())


def save_transaction(tx: Transaction) -> str:
    doc_ref = get_db().collection("transactions").document()
    tx.id = doc_ref.id
    doc_ref.set(tx.model_dump())
    return doc_ref.id


def save_inflow(inflow: Inflow) -> str:
    doc_ref = get_db().collection("inflows").document()
    inflow.id = doc_ref.id
    doc_ref.set(inflow.model_dump())
    return doc_ref.id


def _stream_inflows(chat_id: int, start: datetime, end: datetime):
    """Stream a user's inflows within [start, end).

    Filters by chat_id only (a single-field index that always exists) and
    applies the timestamp window in Python, so the dedicated ``inflows``
    collection does not need its own composite index. Timestamps are stored as
    ISO strings with a consistent offset, so lexicographic comparison matches
    chronological order — the same assumption the Firestore range query makes.
    """
    start_iso = start.isoformat()
    end_iso = end.isoformat()
    for doc in get_db().collection("inflows").where("chat_id", "==", chat_id).stream():
        data = doc.to_dict() or {}
        timestamp = data.get("timestamp", "")
        if start_iso <= timestamp < end_iso:
            yield doc, data


def get_inflows(chat_id: int, start: datetime, end: datetime) -> list[dict]:
    return [data for _doc, data in _stream_inflows(chat_id, start, end)]


def get_inflows_with_ids(chat_id: int, start: datetime, end: datetime) -> list[dict]:
    result = []
    for doc, data in _stream_inflows(chat_id, start, end):
        data["_doc_id"] = doc.id
        result.append(data)
    return result


def get_inflow_by_id(doc_id: str) -> Optional[dict]:
    doc = get_db().collection("inflows").document(doc_id).get()
    if doc.exists:
        data = doc.to_dict()
        data["_doc_id"] = doc.id
        return data
    return None


def delete_inflow(doc_id: str) -> None:
    get_db().collection("inflows").document(doc_id).delete()


def update_inflow_goal(doc_id: str, goal_id: Optional[str]) -> None:
    get_db().collection("inflows").document(doc_id).update({"goal_id": goal_id})


def _goals_collection(chat_id: int):
    return get_db().collection(f"users/{chat_id}/goals")


def save_goal(goal: Goal) -> str:
    # New goals append to the end of the user's ordering.
    goal.order = max((g.get("order", 0) for g in get_goals(goal.chat_id)), default=-1) + 1
    doc_ref = _goals_collection(goal.chat_id).document()
    goal.id = doc_ref.id
    doc_ref.set(goal.model_dump())
    return doc_ref.id


def get_goals(chat_id: int) -> list[dict]:
    goals = []
    for doc in _goals_collection(chat_id).stream():
        data = doc.to_dict() or {}
        data["id"] = doc.id
        goals.append(data)
    # Sort by explicit order; goals predating the order field default to 0 and
    # fall back to creation time, preserving their original display order.
    goals.sort(key=lambda goal: (goal.get("order", 0), goal.get("created_at", "")))
    return goals


def move_goal(chat_id: int, goal_id: str, direction: int) -> bool:
    """Move a goal up (-1) or down (+1) in the user's ordering. Normalises all
    goal ``order`` values to their sorted positions, then swaps the target with
    its neighbour."""
    return _move_ordered(_goals_collection(chat_id), get_goals(chat_id), goal_id, direction)


def get_goal_by_id(chat_id: int, goal_id: str) -> Optional[dict]:
    doc = _goals_collection(chat_id).document(goal_id).get()
    if not doc.exists:
        return None
    data = doc.to_dict() or {}
    data["id"] = doc.id
    return data


def update_goal(chat_id: int, goal_id: str, **fields) -> bool:
    doc_ref = _goals_collection(chat_id).document(goal_id)
    if not doc_ref.get().exists:
        return False
    doc_ref.update(fields)
    return True


def delete_goal(chat_id: int, goal_id: str) -> bool:
    doc_ref = _goals_collection(chat_id).document(goal_id)
    if not doc_ref.get().exists:
        return False
    doc_ref.delete()
    return True


def _move_ordered(collection, ordered: list[dict], target_id: str, direction: int) -> bool:
    """Reorder a list of order-bearing docs (each with an ``id``) by swapping the
    target with its neighbour in ``direction`` (-1 up, +1 down). Normalises every
    ``order`` to its sorted index and writes them in one batch, so docs predating
    the order field get backfilled. Returns False if the move is out of bounds."""
    index = next((i for i, item in enumerate(ordered) if item.get("id") == target_id), None)
    if index is None:
        return False
    swap_with = index + direction
    if swap_with < 0 or swap_with >= len(ordered):
        return False
    ordered[index], ordered[swap_with] = ordered[swap_with], ordered[index]
    batch = get_db().batch()
    for position, item in enumerate(ordered):
        batch.update(collection.document(item["id"]), {"order": position})
    batch.commit()
    return True


def _sum_inflows_grouped(
    chat_id: int,
    field: str,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict[str, float]:
    """Sum inflow amounts grouped by ``field`` (e.g. ``goal_id``/``project_id``).

    Filters by chat_id only (single-field index) and groups in Python — the same
    composite-index-avoiding approach as ``_stream_inflows``. When ``start``/``end``
    are given, only inflows whose timestamp falls in ``[start, end)`` are counted.
    """
    start_iso = start.isoformat() if start else None
    end_iso = end.isoformat() if end else None
    sums: dict[str, float] = {}
    for doc in get_db().collection("inflows").where("chat_id", "==", chat_id).stream():
        data = doc.to_dict() or {}
        key = data.get(field)
        if not key:
            continue
        if start_iso is not None:
            timestamp = data.get("timestamp", "")
            if not (start_iso <= timestamp < end_iso):
                continue
        sums[key] = sums.get(key, 0.0) + data.get("amount", 0.0)
    return sums


def sum_inflows_by_goal(
    chat_id: int,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict[str, float]:
    """Sum inflow amounts per goal_id. Goals are monthly savings targets, so
    callers pass the current-month window; with no window this sums all-time."""
    return _sum_inflows_grouped(chat_id, "goal_id", start, end)


def current_month_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Return [first-of-month, first-of-next-month) in SGT for monthly goal sums."""
    now = now or datetime.now(SGT)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
    return start, end


def _projects_collection(chat_id: int):
    return get_db().collection(f"users/{chat_id}/projects")


def save_project(project: Project) -> str:
    project.order = max((p.get("order", 0) for p in get_projects(project.chat_id)), default=-1) + 1
    doc_ref = _projects_collection(project.chat_id).document()
    project.id = doc_ref.id
    doc_ref.set(project.model_dump())
    return doc_ref.id


def get_projects(chat_id: int) -> list[dict]:
    projects = []
    for doc in _projects_collection(chat_id).stream():
        data = doc.to_dict() or {}
        data["id"] = doc.id
        projects.append(data)
    projects.sort(key=lambda project: (project.get("order", 0), project.get("created_at", "")))
    return projects


def get_project_by_id(chat_id: int, project_id: str) -> Optional[dict]:
    doc = _projects_collection(chat_id).document(project_id).get()
    if not doc.exists:
        return None
    data = doc.to_dict() or {}
    data["id"] = doc.id
    return data


def update_project(chat_id: int, project_id: str, **fields) -> bool:
    doc_ref = _projects_collection(chat_id).document(project_id)
    if not doc_ref.get().exists:
        return False
    doc_ref.update(fields)
    return True


def delete_project(chat_id: int, project_id: str) -> bool:
    doc_ref = _projects_collection(chat_id).document(project_id)
    if not doc_ref.get().exists:
        return False
    doc_ref.delete()
    return True


def move_project(chat_id: int, project_id: str, direction: int) -> bool:
    return _move_ordered(_projects_collection(chat_id), get_projects(chat_id), project_id, direction)


def sum_inflows_by_project(chat_id: int) -> dict[str, float]:
    """Sum all-time inflow amounts per project_id. Projects are cumulative."""
    return _sum_inflows_grouped(chat_id, "project_id")


def delete_transactions_for_plan(plan_id: str) -> int:
    docs = get_db().collection("transactions").where("source_plan_id", "==", plan_id).stream()
    count = 0
    for doc in docs:
        doc.reference.delete()
        count += 1
    return count


def find_transaction_by_plan_occurrence(plan_id: str, occurrence_key: str) -> Optional[dict]:
    docs = (
        get_db()
        .collection("transactions")
        .where("source_plan_id", "==", plan_id)
        .where("occurrence_key", "==", occurrence_key)
        .limit(1)
        .stream()
    )
    for doc in docs:
        data = doc.to_dict()
        data["_doc_id"] = doc.id
        return data
    return None


def get_transactions(chat_id: int, start: datetime, end: datetime) -> list[dict]:
    docs = (
        get_db()
        .collection("transactions")
        .where("chat_id", "==", chat_id)
        .where("timestamp", ">=", start.isoformat())
        .where("timestamp", "<", end.isoformat())
        .stream()
    )
    return [doc.to_dict() for doc in docs]


def save_pending(
    chat_id: int,
    item: str,
    amount: float,
    timestamp: str | None = None,
    date_was_explicit: bool = False,
) -> None:
    created_at = datetime.now(SGT).isoformat()
    tx_timestamp = timestamp or created_at
    pending = PendingTransaction(
        item=item,
        amount=amount,
        chat_id=chat_id,
        timestamp=tx_timestamp,
        created_at=created_at,
        date_was_explicit=date_was_explicit,
    )
    get_db().collection("pending").document(str(chat_id)).set(pending.model_dump())


def get_pending(chat_id: int) -> Optional[dict]:
    doc = get_db().collection("pending").document(str(chat_id)).get()
    if doc.exists:
        return doc.to_dict()
    return None


def delete_pending(chat_id: int) -> None:
    get_db().collection("pending").document(str(chat_id)).delete()


def save_pending_plan(data: PendingPlan) -> None:
    get_db().collection("pending_plans").document(str(data.chat_id)).set(data.model_dump(exclude_none=True))


def get_pending_plan(chat_id: int) -> Optional[dict]:
    doc = get_db().collection("pending_plans").document(str(chat_id)).get()
    if doc.exists:
        return doc.to_dict()
    return None


def update_pending_plan(chat_id: int, **fields) -> None:
    get_db().collection("pending_plans").document(str(chat_id)).set(fields, merge=True)


def delete_pending_plan(chat_id: int) -> None:
    get_db().collection("pending_plans").document(str(chat_id)).delete()


def save_interaction_session(session: FlowSession) -> None:
    get_db().collection("interaction_sessions").document(str(session.chat_id)).set(session.model_dump())


def get_interaction_session(chat_id: int) -> Optional[dict]:
    doc = get_db().collection("interaction_sessions").document(str(chat_id)).get()
    if doc.exists:
        return doc.to_dict()
    return None


def update_interaction_session(chat_id: int, **fields) -> None:
    get_db().collection("interaction_sessions").document(str(chat_id)).set(fields, merge=True)


def delete_interaction_session(chat_id: int) -> None:
    get_db().collection("interaction_sessions").document(str(chat_id)).delete()


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
        data = doc.to_dict()
        data["_doc_id"] = doc.id
        result.append(data)
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
        data = doc.to_dict()
        data["_doc_id"] = doc.id
        return data
    return None


def get_transaction_by_id(doc_id: str) -> Optional[dict]:
    doc = get_db().collection("transactions").document(doc_id).get()
    if doc.exists:
        data = doc.to_dict()
        data["_doc_id"] = doc.id
        return data
    return None


def delete_transaction(doc_id: str) -> None:
    get_db().collection("transactions").document(doc_id).delete()


def update_transaction_category(doc_id: str, category: str) -> None:
    get_db().collection("transactions").document(doc_id).update({"category": category})


def update_transaction_timestamp(doc_id: str, new_timestamp: str) -> None:
    get_db().collection("transactions").document(doc_id).update({"timestamp": new_timestamp})


def reassign_transactions_category(chat_id: int, old_category: str, new_category: str) -> int:
    docs = get_db().collection("transactions").where("chat_id", "==", chat_id).stream()
    count = 0
    for doc in docs:
        data = doc.to_dict() or {}
        if data.get("category") == old_category:
            doc.reference.update({"category": new_category})
            count += 1
    return count


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


def save_pending_change(chat_id: int, tx_id: str, item_key: str) -> None:
    get_db().collection("pending_change").document(str(chat_id)).set(
        {
            "tx_id": tx_id,
            "item_key": item_key,
            "timestamp": datetime.now(SGT).isoformat(),
        }
    )


def get_pending_change(chat_id: int) -> Optional[dict]:
    doc = get_db().collection("pending_change").document(str(chat_id)).get()
    if doc.exists:
        return doc.to_dict()
    return None


def delete_pending_change(chat_id: int) -> None:
    get_db().collection("pending_change").document(str(chat_id)).delete()


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


def get_category_list(chat_id: int) -> list[dict]:
    categories = [doc.to_dict() for doc in _category_list_collection(chat_id).stream()]
    categories.sort(key=lambda category: category.get("order", 9998))
    return categories


def add_category_to_list(chat_id: int, name: str, emoji: str = "🏷️") -> None:
    all_cats = get_category_list(chat_id)
    max_order = max((c.get("order", 0) for c in all_cats if c.get("order", 0) < 9999), default=100)
    _category_list_collection(chat_id).document(_category_doc_id(name)).set(
        {"name": name, "emoji": emoji, "order": max_order + 1}
    )


def remove_category_from_list(chat_id: int, name: str) -> bool:
    doc_ref = _category_list_collection(chat_id).document(_category_doc_id(name))
    doc = doc_ref.get()
    if doc.exists:
        doc_ref.delete()
        remove_budget(chat_id, name)
        return True
    return False


def delete_category(chat_id: int, category_name: str) -> int:
    count = 0
    for doc in _category_map_collection(chat_id).stream():
        data = doc.to_dict() or {}
        if data.get("category") == category_name:
            doc.reference.delete()
            count += 1
    return count


def update_category_emoji(chat_id: int, name: str, emoji: str) -> bool:
    doc_ref = _category_list_collection(chat_id).document(_category_doc_id(name))
    doc = doc_ref.get()
    if not doc.exists:
        return False
    doc_ref.update({"emoji": emoji})
    return True


def update_category_order(chat_id: int, name: str, order: int) -> bool:
    categories = _category_list_collection(chat_id)
    target_ref = categories.document(_category_doc_id(name))
    target_doc = target_ref.get()
    if not target_doc.exists:
        return False

    old_order = target_doc.to_dict().get("order", 9998)
    if old_order == order:
        return True

    batch = get_db().batch()
    for doc in categories.stream():
        data = doc.to_dict() or {}
        if data.get("name") == "Other" or data.get("name") == name:
            continue
        current = data.get("order", 9998)
        if order < old_order and order <= current < old_order:
            batch.update(doc.reference, {"order": current + 1})
        elif order > old_order and old_order < current <= order:
            batch.update(doc.reference, {"order": current - 1})
    batch.update(target_ref, {"order": order})
    batch.commit()
    return True


def rename_category(chat_id: int, old_name: str, new_name: str) -> tuple[bool, int, int]:
    categories = _category_list_collection(chat_id)
    old_ref = categories.document(_category_doc_id(old_name))
    old_doc = old_ref.get()
    if not old_doc.exists:
        return False, 0, 0

    new_ref = categories.document(_category_doc_id(new_name))
    if new_ref.get().exists:
        return False, 0, 0

    data = old_doc.to_dict()
    data["name"] = new_name
    new_ref.set(data)
    old_ref.delete()

    budgets_ref = get_db().collection("budgets").document(str(chat_id))
    budgets_doc = budgets_ref.get()
    if budgets_doc.exists:
        budgets = budgets_doc.to_dict() or {}
        if old_name in budgets:
            budgets[new_name] = budgets.pop(old_name)
            if budgets:
                budgets_ref.set(budgets)
            else:
                budgets_ref.delete()

    tx_count = 0
    for doc in get_db().collection("transactions").where("chat_id", "==", chat_id).stream():
        tx_data = doc.to_dict() or {}
        if tx_data.get("category") == old_name:
            doc.reference.update({"category": new_name})
            tx_count += 1

    map_count = 0
    for doc in _category_map_collection(chat_id).stream():
        map_data = doc.to_dict() or {}
        if map_data.get("category") == old_name:
            doc.reference.update({"category": new_name})
            map_count += 1

    return True, tx_count, map_count


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


def save_pending_dashboard_account(chat_id: int, username: str | None = None) -> None:
    payload = {"timestamp": datetime.now(SGT).isoformat()}
    if username is not None:
        payload["username"] = username
    get_db().collection("pending_dashboard_accounts").document(str(chat_id)).set(payload, merge=True)


def get_pending_dashboard_account(chat_id: int) -> Optional[dict]:
    doc = get_db().collection("pending_dashboard_accounts").document(str(chat_id)).get()
    if doc.exists:
        return doc.to_dict()
    return None


def delete_pending_dashboard_account(chat_id: int) -> None:
    get_db().collection("pending_dashboard_accounts").document(str(chat_id)).delete()


def get_web_account_by_chat_id(chat_id: int) -> Optional[dict]:
    doc = get_db().collection("web_accounts").document(str(chat_id)).get()
    if doc.exists:
        data = doc.to_dict() or {}
        data["chat_id"] = chat_id
        return data
    return None


def _extract_chat_id(data: dict | None) -> Optional[int]:
    if not data:
        return None
    raw_chat_id = data.get("chat_id")
    try:
        return int(raw_chat_id)
    except (TypeError, ValueError):
        return None


def get_account_by_username(username_normalized: str) -> Optional[dict]:
    username_doc = get_db().collection("web_usernames").document(username_normalized).get()
    if not username_doc.exists:
        return None
    chat_id = _extract_chat_id(username_doc.to_dict())
    if chat_id is None:
        return None
    return get_web_account_by_chat_id(chat_id)


def upsert_web_account(chat_id: int, username: str, password_hash: str) -> None:
    normalized = username.strip().lower()
    now = datetime.now(SGT).isoformat()
    db = get_db()
    account_ref = db.collection("web_accounts").document(str(chat_id))
    username_ref = db.collection("web_usernames").document(normalized)

    existing_username_doc = username_ref.get()
    if existing_username_doc.exists:
        existing_chat_id = _extract_chat_id(existing_username_doc.to_dict())
        if existing_chat_id is None or existing_chat_id != chat_id:
            raise ValueError("That username is already taken.")

    current_account_doc = account_ref.get()
    current_account = current_account_doc.to_dict() if current_account_doc.exists else {}
    old_username = (current_account or {}).get("username_normalized")

    batch = db.batch()
    batch.set(
        account_ref,
        {
            "chat_id": chat_id,
            "username": username.strip(),
            "username_normalized": normalized,
            "password_hash": password_hash,
            "active": True,
            "updated_at": now,
        },
        merge=True,
    )
    batch.set(
        username_ref,
        {"chat_id": chat_id, "username": username.strip(), "updated_at": now},
    )
    if old_username and old_username != normalized:
        batch.delete(db.collection("web_usernames").document(old_username))
    batch.commit()


def save_web_session(token: str, chat_id: int, username: str, expires_at: datetime) -> None:
    now = datetime.now(SGT).isoformat()
    doc_id = hashlib.sha256(token.encode("utf-8")).hexdigest()
    get_db().collection("web_sessions").document(doc_id).set(
        {
            "chat_id": chat_id,
            "username": username,
            "expires_at": expires_at.isoformat(),
            "created_at": now,
        }
    )


def get_web_session(token: str) -> Optional[dict]:
    doc_id = hashlib.sha256(token.encode("utf-8")).hexdigest()
    doc = get_db().collection("web_sessions").document(doc_id).get()
    if not doc.exists:
        return None
    data = doc.to_dict() or {}
    expires_at = data.get("expires_at")
    if not expires_at:
        doc.reference.delete()
        return None
    expiry_dt = datetime.fromisoformat(expires_at).astimezone(SGT)
    if expiry_dt <= datetime.now(SGT):
        doc.reference.delete()
        return None
    return data


def delete_web_session(token: str) -> None:
    doc_id = hashlib.sha256(token.encode("utf-8")).hexdigest()
    get_db().collection("web_sessions").document(doc_id).delete()


def delete_web_sessions_for_chat(chat_id: int) -> int:
    docs = get_db().collection("web_sessions").where("chat_id", "==", chat_id).stream()
    count = 0
    for doc in docs:
        doc.reference.delete()
        count += 1
    return count


def get_dashboard_preferences(chat_id: int) -> dict:
    doc = get_db().collection("dashboard_preferences").document(str(chat_id)).get()
    if doc.exists:
        return doc.to_dict() or {}
    return {}


def update_dashboard_preferences(chat_id: int, **fields) -> None:
    get_db().collection("dashboard_preferences").document(str(chat_id)).set(fields, merge=True)


def get_budgets(chat_id: int) -> dict[str, float]:
    doc = get_db().collection("budgets").document(str(chat_id)).get()
    if doc.exists:
        raw_budgets = doc.to_dict() or {}
        category_names = {category.get("name") for category in get_category_list(chat_id)}
        budgets: dict[str, float] = {}
        changed = False

        for category, amount in raw_budgets.items():
            if category not in category_names or not isinstance(amount, (int, float)) or isinstance(amount, bool) or amount <= 0:
                changed = True
                continue
            budgets[category] = float(amount)

        if changed:
            if budgets:
                doc.reference.set(budgets)
            else:
                doc.reference.delete()
        return budgets
    return {}


def set_budget(chat_id: int, category: str, amount: float) -> None:
    get_db().collection("budgets").document(str(chat_id)).set({category: amount}, merge=True)


def remove_budget(chat_id: int, category: str) -> bool:
    doc_ref = get_db().collection("budgets").document(str(chat_id))
    doc = doc_ref.get()
    if not doc.exists:
        return False

    budgets = doc.to_dict() or {}
    if category not in budgets:
        return False

    budgets.pop(category, None)
    if budgets:
        doc_ref.set(budgets)
    else:
        doc_ref.delete()
    return True


def save_payment_plan(plan: PaymentPlan) -> str:
    doc_ref = get_db().collection("payment_plans").document()
    plan.id = doc_ref.id
    doc_ref.set(plan.model_dump())
    return doc_ref.id


def update_payment_plan(plan_id: str, **fields) -> None:
    get_db().collection("payment_plans").document(plan_id).update(fields)


def delete_payment_plan(plan_id: str) -> None:
    get_db().collection("payment_plans").document(plan_id).delete()


def get_payment_plan(plan_id: str) -> Optional[dict]:
    doc = get_db().collection("payment_plans").document(plan_id).get()
    if doc.exists:
        data = doc.to_dict()
        data["id"] = doc.id
        return data
    return None


def list_payment_plans(
    chat_id: int,
    plan_type: Optional[str] = None,
    statuses: Optional[list[str]] = None,
) -> list[dict]:
    docs = get_db().collection("payment_plans").where("chat_id", "==", chat_id).stream()
    plans = []
    allowed_statuses = statuses or ["active", "completed"]
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        if plan_type and data.get("plan_type") != plan_type:
            continue
        if data.get("status") not in allowed_statuses:
            continue
        plans.append(data)
    plans.sort(key=lambda plan: (plan.get("status") != "active", plan.get("next_due_date", "")))
    return plans


def list_due_payment_plans(today: datetime) -> list[dict]:
    docs = get_db().collection("payment_plans").where("status", "==", "active").stream()
    due_plans = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        raw_due = data.get("next_due_date")
        if not raw_due:
            continue
        next_due = datetime.fromisoformat(raw_due).astimezone(SGT)
        # Catch up any charge that is due today OR overdue. Using exact-date
        # equality means a plan missed on its due date (scheduler down, a
        # partial-failure run, etc.) would never be retried, because its
        # next_due_date stays pinned to a past date that never matches again.
        if next_due.date() <= today.date():
            due_plans.append(data)
    return due_plans


def recalculate_payment_plan_next_due(plan_id: str) -> Optional[str]:
    plan = get_payment_plan(plan_id)
    if not plan:
        return None

    next_due = compute_next_due_date(plan)
    status = "completed" if next_due is None and plan["plan_type"] == "split_payment" else plan.get("status", "active")
    payload = {"status": status}
    payload["next_due_date"] = next_due.isoformat() if next_due is not None else ""
    update_payment_plan(plan_id, **payload)
    return payload["next_due_date"]
