import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from services.dashboard_auth import (
    build_session_token,
    normalize_username,
    session_expiry,
    verify_password,
)
from services.firestore import (
    add_category_to_list,
    delete_web_session,
    get_account_by_username,
    get_budgets,
    get_category_list,
    get_transaction_by_id,
    get_transactions_with_ids,
    get_web_session,
    rename_category,
    reassign_transactions_category,
    remove_category_from_list,
    save_web_session,
    update_category_emoji,
    update_category_order,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

COOKIE_NAME = "dashboard_session"
SGT = timezone(timedelta(hours=8))


class LoginRequest(BaseModel):
    username: str
    password: str


class SessionResponse(BaseModel):
    authenticated: bool
    username: Optional[str] = None
    chat_id: Optional[int] = None


class TransactionUpdateRequest(BaseModel):
    item: str
    amount: float
    category: str
    timestamp: str


class CategoryCreateRequest(BaseModel):
    name: str
    emoji: str = "🏷️"


class CategoryUpdateRequest(BaseModel):
    name: str
    emoji: str = "🏷️"


class CategoryMoveRequest(BaseModel):
    direction: int


def _dashboard_url() -> str:
    return os.getenv("DASHBOARD_WEB_URL", "https://budget-bot-123.web.app")


def _set_session_cookie(response: Response, token: str, expires_at: datetime) -> None:
    max_age = int((expires_at - datetime.now(SGT)).total_seconds())
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=max_age,
        expires=expires_at.astimezone(timezone.utc),
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        COOKIE_NAME,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
    )


def _session_payload(request: Request) -> Optional[dict]:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    return get_web_session(token)


def _require_session(request: Request) -> dict:
    session = _session_payload(request)
    if not session:
        raise HTTPException(status_code=401, detail="Unauthorized.")
    return session


def _parse_dashboard_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid datetime.") from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SGT)
    return parsed.astimezone(SGT)


@router.get("/auth/session", response_model=SessionResponse)
async def get_dashboard_session(request: Request):
    session = _session_payload(request)
    if not session:
        return SessionResponse(authenticated=False)
    return SessionResponse(
        authenticated=True,
        username=session["username"],
        chat_id=session["chat_id"],
    )


@router.post("/auth/login", response_model=SessionResponse)
async def login_dashboard(request: LoginRequest, response: Response):
    username = normalize_username(request.username)
    account = get_account_by_username(username)
    if not account or not account.get("active", True):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    stored_hash = account.get("password_hash", "")
    if not verify_password(request.password, stored_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    token = build_session_token()
    expires_at = session_expiry()
    save_web_session(
        token=token,
        chat_id=account["chat_id"],
        username=account["username"],
        expires_at=expires_at,
    )
    _set_session_cookie(response, token, expires_at)
    return SessionResponse(
        authenticated=True,
        username=account["username"],
        chat_id=account["chat_id"],
    )


@router.post("/auth/logout")
async def logout_dashboard(request: Request, response: Response):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        delete_web_session(token)
    _clear_session_cookie(response)
    return {"ok": True}


@router.get("/bootstrap")
async def get_dashboard_bootstrap(request: Request):
    session = _require_session(request)
    return {
        "account": {
            "username": session["username"],
            "chat_id": session["chat_id"],
            "dashboard_url": _dashboard_url(),
        },
        "categories": get_category_list(),
        "budgets": get_budgets(session["chat_id"]),
    }


@router.get("/transactions")
async def list_dashboard_transactions(
    request: Request,
    start: str,
    end: str,
    category: Optional[str] = None,
):
    session = _require_session(request)
    start_dt = _parse_dashboard_datetime(start)
    end_dt = _parse_dashboard_datetime(end)
    transactions = get_transactions_with_ids(session["chat_id"], start_dt, end_dt)
    if category:
        transactions = [tx for tx in transactions if tx.get("category") == category]
    transactions.sort(key=lambda tx: tx.get("timestamp", ""), reverse=True)
    return {"transactions": transactions}


@router.patch("/transactions/{transaction_id}")
async def update_dashboard_transaction(
    transaction_id: str,
    payload: TransactionUpdateRequest,
    request: Request,
):
    session = _require_session(request)
    transaction = get_transaction_by_id(transaction_id)
    if not transaction or transaction.get("chat_id") != session["chat_id"]:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    item = payload.item.strip()
    category = payload.category.strip()
    if not item:
        raise HTTPException(status_code=400, detail="Item cannot be empty.")
    if not category:
        raise HTTPException(status_code=400, detail="Category cannot be empty.")
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive.")

    transaction["item"] = item
    transaction["amount"] = payload.amount
    transaction["category"] = category
    transaction["timestamp"] = _parse_dashboard_datetime(payload.timestamp).isoformat()

    from services.firestore import get_db

    get_db().collection("transactions").document(transaction_id).update(
        {
            "item": transaction["item"],
            "amount": transaction["amount"],
            "category": transaction["category"],
            "timestamp": transaction["timestamp"],
        }
    )
    return {"ok": True}


@router.get("/categories")
async def list_dashboard_categories(request: Request):
    _require_session(request)
    return {"categories": get_category_list()}


@router.post("/categories")
async def create_dashboard_category(payload: CategoryCreateRequest, request: Request):
    _require_session(request)
    name = payload.name.strip().title()
    if not name:
        raise HTTPException(status_code=400, detail="Category name cannot be empty.")
    existing = {category["name"] for category in get_category_list()}
    if name in existing:
        raise HTTPException(status_code=400, detail=f"Category {name} already exists.")
    add_category_to_list(name, payload.emoji.strip() or "🏷️")
    return {"ok": True}


@router.patch("/categories/{category_name}")
async def update_dashboard_category(
    category_name: str,
    payload: CategoryUpdateRequest,
    request: Request,
):
    _require_session(request)
    normalized_name = payload.name.strip().title()
    if not normalized_name:
        raise HTTPException(status_code=400, detail="Category name cannot be empty.")
    if category_name == "Other" and normalized_name != "Other":
        raise HTTPException(status_code=400, detail="The Other category cannot be renamed.")

    if normalized_name == category_name:
        if not update_category_emoji(category_name, payload.emoji.strip() or "🏷️"):
            raise HTTPException(status_code=404, detail="Category not found.")
        return {"ok": True}

    existing = {category["name"] for category in get_category_list()}
    if normalized_name in existing:
        raise HTTPException(status_code=400, detail=f"Category {normalized_name} already exists.")

    ok, tx_count, map_count = rename_category(category_name, normalized_name)
    if not ok:
        raise HTTPException(status_code=404, detail="Category not found.")
    update_category_emoji(normalized_name, payload.emoji.strip() or "🏷️")
    return {"ok": True, "tx_count": tx_count, "map_count": map_count}


@router.delete("/categories/{category_name}")
async def delete_dashboard_category(category_name: str, request: Request):
    _require_session(request)
    if category_name == "Other":
        raise HTTPException(status_code=400, detail="The Other category cannot be removed.")
    reassigned = reassign_transactions_category(category_name, "Other")
    from services.firestore import delete_category

    delete_category(category_name)
    if not remove_category_from_list(category_name):
        raise HTTPException(status_code=404, detail="Category not found.")
    return {"ok": True, "reassigned": reassigned}


@router.post("/categories/{category_name}/move")
async def move_dashboard_category(
    category_name: str,
    payload: CategoryMoveRequest,
    request: Request,
):
    _require_session(request)
    if category_name == "Other":
        raise HTTPException(status_code=400, detail="The Other category cannot be reordered.")
    if payload.direction not in {-1, 1}:
        raise HTTPException(status_code=400, detail="Direction must be -1 or 1.")

    movable = [category for category in get_category_list() if category["name"] != "Other"]
    movable.sort(key=lambda category: category.get("order", 9998))
    index = next((i for i, category in enumerate(movable) if category["name"] == category_name), -1)
    if index == -1:
        raise HTTPException(status_code=404, detail="Category not found.")
    target_index = index + payload.direction
    if target_index < 0 or target_index >= len(movable):
        return {"ok": True}

    target_order = target_index + 1
    if not update_category_order(category_name, target_order):
        raise HTTPException(status_code=404, detail="Category not found.")
    return {"ok": True}


@router.get("/budgets")
async def list_dashboard_budgets(request: Request):
    session = _require_session(request)
    return {"budgets": get_budgets(session["chat_id"])}

