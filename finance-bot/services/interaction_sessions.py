from datetime import datetime, timedelta, timezone
from typing import Any

from models.transaction import FlowSession
from services import firestore

SGT = timezone(timedelta(hours=8))
DEFAULT_SESSION_EXPIRY_SECONDS = 180


def _now() -> datetime:
    return datetime.now(SGT)


def start_session(
    chat_id: int,
    flow_type: str,
    step: str,
    payload: dict[str, Any] | None = None,
    expiry_seconds: int = DEFAULT_SESSION_EXPIRY_SECONDS,
) -> dict:
    now = _now()
    session = FlowSession(
        chat_id=chat_id,
        flow_type=flow_type,
        step=step,
        payload=payload or {},
        created_at=now.isoformat(),
        expires_at=(now + timedelta(seconds=expiry_seconds)).isoformat(),
    )
    data = session.model_dump()
    firestore.save_interaction_session(session)
    return data


def get_session(chat_id: int) -> dict | None:
    return firestore.get_interaction_session(chat_id)


def is_expired(session: dict | None) -> bool:
    if not session:
        return True
    expires_at = session.get("expires_at")
    if not expires_at:
        return True
    try:
        return _now() > datetime.fromisoformat(expires_at)
    except ValueError:
        return True


def get_active_session(chat_id: int, flow_type: str | None = None) -> dict | None:
    session = get_session(chat_id)
    if not session or is_expired(session):
        return None
    if flow_type is not None and session.get("flow_type") != flow_type:
        return None
    return session


def update_session(
    chat_id: int,
    step: str | None = None,
    payload_updates: dict[str, Any] | None = None,
) -> dict | None:
    session = get_session(chat_id)
    if not session:
        return None

    updates: dict[str, Any] = {}
    if step is not None:
        updates["step"] = step
    if payload_updates:
        updates["payload"] = {**session.get("payload", {}), **payload_updates}

    if updates:
        firestore.update_interaction_session(chat_id, **updates)
        session.update(updates)
    return session


def clear_session(chat_id: int) -> None:
    firestore.delete_interaction_session(chat_id)
