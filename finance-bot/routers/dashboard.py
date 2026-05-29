import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from models.transaction import Inflow, PaymentPlan, Transaction
from services.dashboard_auth import (
    build_session_token,
    normalize_username,
    session_expiry,
    verify_password,
)
from services.payment_plans import (
    compute_next_due_date,
    compute_split_amounts,
    month_due_date,
    next_month,
    plan_occurrence_for_index,
)
from services.plan_manager import rewrite_plan_history
from services.firestore import (
    add_category_to_list,
    delete_transactions_for_plan,
    delete_payment_plan,
    delete_web_session,
    delete_transaction,
    get_account_by_username,
    get_budgets,
    get_category_list,
    get_dashboard_preferences,
    get_inflow_by_id,
    get_inflows_with_ids,
    get_payment_plan,
    get_transaction_by_id,
    get_transactions_with_ids,
    get_web_session,
    delete_inflow,
    save_inflow,
    list_payment_plans,
    remove_budget,
    rename_category,
    reassign_transactions_category,
    remove_category_from_list,
    save_payment_plan,
    save_transaction,
    save_web_session,
    set_budget,
    update_dashboard_preferences,
    update_category_emoji,
    update_category_order,
    update_payment_plan,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

COOKIE_NAME = "dashboard_session"
SESSION_HEADER = "x-dashboard-session"
SGT = timezone(timedelta(hours=8))


class LoginRequest(BaseModel):
    username: str
    password: str


class SessionResponse(BaseModel):
    authenticated: bool
    username: Optional[str] = None
    chat_id: Optional[int] = None
    session_token: Optional[str] = None


class TransactionUpdateRequest(BaseModel):
    item: str
    amount: float
    category: str
    timestamp: str


class TransactionCreateRequest(BaseModel):
    item: str
    amount: float
    category: str
    timestamp: str
    payment_type: str
    day_of_month: Optional[int] = None
    installment_count: Optional[int] = None
    create_first_transaction_now: bool = True


class InflowCreateRequest(BaseModel):
    item: str
    amount: float
    timestamp: str


class InflowUpdateRequest(BaseModel):
    item: str
    amount: float
    timestamp: str


class CategoryCreateRequest(BaseModel):
    name: str
    emoji: str = "🏷️"


class CategoryUpdateRequest(BaseModel):
    name: str
    emoji: str = "🏷️"


class CategoryMoveRequest(BaseModel):
    direction: int


class BudgetSetRequest(BaseModel):
    amount: float


class DashboardPreferencesUpdateRequest(BaseModel):
    overview_visible_cards: list[str]


def _dashboard_url() -> str:
    return os.getenv("DASHBOARD_WEB_URL", "https://budget-flow-123.web.app")


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
        token = request.headers.get(SESSION_HEADER)
    if not token:
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
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


def _scheduled_plan_start(timestamp: datetime, day_of_month: int) -> tuple[int, int]:
    candidate_due = month_due_date(timestamp.year, timestamp.month, day_of_month)
    if timestamp.date() <= candidate_due.date():
        return timestamp.year, timestamp.month
    return next_month(timestamp.year, timestamp.month)


def _build_plan_creation_result(plan: dict, create_first_transaction_now: bool, timestamp: datetime) -> dict:
    if not create_first_transaction_now:
        next_due = compute_next_due_date(plan)
        return {
            "current_installment_number": 0,
            "next_due_date": next_due.isoformat() if next_due else "",
            "status": "completed" if next_due is None and plan["plan_type"] == "split_payment" else "active",
        }

    occurrence = plan_occurrence_for_index(plan, 0)
    save_transaction(
        Transaction(
            item=plan["item"],
            amount=occurrence.amount,
            category=plan["category"],
            timestamp=timestamp.isoformat(),
            chat_id=plan["chat_id"],
            source_type=plan["plan_type"],
            source_plan_id=plan["id"],
            occurrence_key=occurrence.occurrence_key,
            auto_generated=True,
        )
    )
    posted_count = 1
    next_due = compute_next_due_date({**plan, "current_installment_number": posted_count})
    status = "completed" if next_due is None and plan["plan_type"] == "split_payment" else "active"
    return {
        "current_installment_number": posted_count,
        "next_due_date": next_due.isoformat() if next_due else "",
        "status": status,
    }


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
        session_token=token,
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
        "categories": get_category_list(session["chat_id"]),
        "budgets": get_budgets(session["chat_id"]),
        "preferences": get_dashboard_preferences(session["chat_id"]),
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


@router.post("/transactions")
async def create_dashboard_transaction(payload: TransactionCreateRequest, request: Request):
    session = _require_session(request)
    item = payload.item.strip()
    category = payload.category.strip()
    payment_type = payload.payment_type.strip()
    timestamp = _parse_dashboard_datetime(payload.timestamp)

    if not item:
        raise HTTPException(status_code=400, detail="Item cannot be empty.")
    if not category:
        raise HTTPException(status_code=400, detail="Category cannot be empty.")
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive.")
    if payment_type not in {"one_time", "recurring", "split_payment"}:
        raise HTTPException(status_code=400, detail="Invalid payment type.")

    if payment_type == "one_time":
        save_transaction(
            Transaction(
                item=item,
                amount=payload.amount,
                category=category,
                timestamp=timestamp.isoformat(),
                chat_id=session["chat_id"],
            )
        )
        return {"ok": True}

    if payload.day_of_month is None or not 1 <= payload.day_of_month <= 31:
        raise HTTPException(status_code=400, detail="Day must be between 1 and 31.")

    if payload.create_first_transaction_now:
        start_year = timestamp.year
        start_month = timestamp.month
    else:
        start_year, start_month = _scheduled_plan_start(timestamp, payload.day_of_month)

    if payment_type == "split_payment":
        if payload.installment_count is None or payload.installment_count < 1:
            raise HTTPException(status_code=400, detail="Months must be a positive integer.")
        base_amount, final_amount = compute_split_amounts(payload.amount, payload.installment_count)
        plan = PaymentPlan(
            chat_id=session["chat_id"],
            plan_type="split_payment",
            item=item,
            category=category,
            day_of_month=payload.day_of_month,
            start_year=start_year,
            start_month=start_month,
            next_due_date=timestamp.isoformat(),
            created_at=datetime.now(SGT).isoformat(),
            total_amount=payload.amount,
            installment_count=payload.installment_count,
            current_installment_number=0,
            base_installment_amount=base_amount,
            final_installment_amount=final_amount,
        )
    else:
        plan = PaymentPlan(
            chat_id=session["chat_id"],
            plan_type="recurring",
            item=item,
            category=category,
            day_of_month=payload.day_of_month,
            start_year=start_year,
            start_month=start_month,
            next_due_date=timestamp.isoformat(),
            created_at=datetime.now(SGT).isoformat(),
            amount=payload.amount,
            current_installment_number=0,
        )

    plan_id = save_payment_plan(plan)
    stored_plan = get_payment_plan(plan_id)
    update_payment_plan(plan_id, **_build_plan_creation_result(stored_plan, payload.create_first_transaction_now, timestamp))
    return {"ok": True}


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


@router.delete("/transactions/{transaction_id}")
async def delete_dashboard_transaction(transaction_id: str, request: Request):
    session = _require_session(request)
    transaction = get_transaction_by_id(transaction_id)
    if not transaction or transaction.get("chat_id") != session["chat_id"]:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    delete_transaction(transaction_id)
    return {"ok": True}


@router.get("/inflows")
async def list_dashboard_inflows(
    request: Request,
    start: str,
    end: str,
):
    session = _require_session(request)
    start_dt = _parse_dashboard_datetime(start)
    end_dt = _parse_dashboard_datetime(end)
    inflows = get_inflows_with_ids(session["chat_id"], start_dt, end_dt)
    inflows.sort(key=lambda inflow: inflow.get("timestamp", ""), reverse=True)
    return {"inflows": inflows}


@router.post("/inflows")
async def create_dashboard_inflow(payload: InflowCreateRequest, request: Request):
    session = _require_session(request)
    item = payload.item.strip()
    if not item:
        raise HTTPException(status_code=400, detail="Item cannot be empty.")
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive.")
    timestamp = _parse_dashboard_datetime(payload.timestamp)
    save_inflow(
        Inflow(
            item=item,
            amount=payload.amount,
            timestamp=timestamp.isoformat(),
            chat_id=session["chat_id"],
            created_at=datetime.now(SGT).isoformat(),
        )
    )
    return {"ok": True}


@router.patch("/inflows/{inflow_id}")
async def update_dashboard_inflow(
    inflow_id: str,
    payload: InflowUpdateRequest,
    request: Request,
):
    session = _require_session(request)
    inflow = get_inflow_by_id(inflow_id)
    if not inflow or inflow.get("chat_id") != session["chat_id"]:
        raise HTTPException(status_code=404, detail="Inflow not found.")

    item = payload.item.strip()
    if not item:
        raise HTTPException(status_code=400, detail="Item cannot be empty.")
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive.")

    from services.firestore import get_db

    get_db().collection("inflows").document(inflow_id).update(
        {
            "item": item,
            "amount": payload.amount,
            "timestamp": _parse_dashboard_datetime(payload.timestamp).isoformat(),
        }
    )
    return {"ok": True}


@router.delete("/inflows/{inflow_id}")
async def delete_dashboard_inflow(inflow_id: str, request: Request):
    session = _require_session(request)
    inflow = get_inflow_by_id(inflow_id)
    if not inflow or inflow.get("chat_id") != session["chat_id"]:
        raise HTTPException(status_code=404, detail="Inflow not found.")
    delete_inflow(inflow_id)
    return {"ok": True}


@router.get("/categories")
async def list_dashboard_categories(request: Request):
    session = _require_session(request)
    return {"categories": get_category_list(session["chat_id"])}


@router.post("/categories")
async def create_dashboard_category(payload: CategoryCreateRequest, request: Request):
    session = _require_session(request)
    name = payload.name.strip().title()
    if not name:
        raise HTTPException(status_code=400, detail="Category name cannot be empty.")
    existing = {category["name"] for category in get_category_list(session["chat_id"])}
    if name in existing:
        raise HTTPException(status_code=400, detail=f"Category {name} already exists.")
    add_category_to_list(session["chat_id"], name, payload.emoji.strip() or "🏷️")
    return {"ok": True}


@router.patch("/categories/{category_name}")
async def update_dashboard_category(
    category_name: str,
    payload: CategoryUpdateRequest,
    request: Request,
):
    session = _require_session(request)
    normalized_name = payload.name.strip().title()
    if not normalized_name:
        raise HTTPException(status_code=400, detail="Category name cannot be empty.")
    if category_name == "Other" and normalized_name != "Other":
        raise HTTPException(status_code=400, detail="The Other category cannot be renamed.")

    if normalized_name == category_name:
        if not update_category_emoji(session["chat_id"], category_name, payload.emoji.strip() or "🏷️"):
            raise HTTPException(status_code=404, detail="Category not found.")
        return {"ok": True}

    existing = {category["name"] for category in get_category_list(session["chat_id"])}
    if normalized_name in existing:
        raise HTTPException(status_code=400, detail=f"Category {normalized_name} already exists.")

    ok, tx_count, map_count = rename_category(session["chat_id"], category_name, normalized_name)
    if not ok:
        raise HTTPException(status_code=404, detail="Category not found.")
    update_category_emoji(session["chat_id"], normalized_name, payload.emoji.strip() or "🏷️")
    return {"ok": True, "tx_count": tx_count, "map_count": map_count}


@router.delete("/categories/{category_name}")
async def delete_dashboard_category(category_name: str, request: Request):
    session = _require_session(request)
    if category_name == "Other":
        raise HTTPException(status_code=400, detail="The Other category cannot be removed.")
    reassigned = reassign_transactions_category(session["chat_id"], category_name, "Other")
    from services.firestore import delete_category

    delete_category(session["chat_id"], category_name)
    if not remove_category_from_list(session["chat_id"], category_name):
        raise HTTPException(status_code=404, detail="Category not found.")
    return {"ok": True, "reassigned": reassigned}


@router.post("/categories/{category_name}/move")
async def move_dashboard_category(
    category_name: str,
    payload: CategoryMoveRequest,
    request: Request,
):
    session = _require_session(request)
    if category_name == "Other":
        raise HTTPException(status_code=400, detail="The Other category cannot be reordered.")
    if payload.direction not in {-1, 1}:
        raise HTTPException(status_code=400, detail="Direction must be -1 or 1.")

    movable = [category for category in get_category_list(session["chat_id"]) if category["name"] != "Other"]
    movable.sort(key=lambda category: category.get("order", 9998))
    index = next((i for i, category in enumerate(movable) if category["name"] == category_name), -1)
    if index == -1:
        raise HTTPException(status_code=404, detail="Category not found.")
    target_index = index + payload.direction
    if target_index < 0 or target_index >= len(movable):
        return {"ok": True}

    target_order = target_index + 1
    if not update_category_order(session["chat_id"], category_name, target_order):
        raise HTTPException(status_code=404, detail="Category not found.")
    return {"ok": True}


@router.get("/budgets")
async def list_dashboard_budgets(request: Request):
    session = _require_session(request)
    return {"budgets": get_budgets(session["chat_id"])}


@router.patch("/budgets/{category_name}")
async def update_dashboard_budget(category_name: str, body: BudgetSetRequest, request: Request):
    session = _require_session(request)
    if body.amount < 0:
        raise HTTPException(status_code=400, detail="Budget amount cannot be negative.")
    if body.amount == 0:
        remove_budget(session["chat_id"], category_name)
    else:
        set_budget(session["chat_id"], category_name, body.amount)
    return {"ok": True}


@router.delete("/budgets/{category_name}")
async def delete_dashboard_budget(category_name: str, request: Request):
    session = _require_session(request)
    remove_budget(session["chat_id"], category_name)
    return {"ok": True}


@router.get("/preferences")
async def get_dashboard_user_preferences(request: Request):
    session = _require_session(request)
    return {"preferences": get_dashboard_preferences(session["chat_id"])}


@router.patch("/preferences")
async def update_dashboard_user_preferences(
    payload: DashboardPreferencesUpdateRequest,
    request: Request,
):
    session = _require_session(request)
    update_dashboard_preferences(
        session["chat_id"],
        overview_visible_cards=payload.overview_visible_cards,
    )
    return {"ok": True}


class PlanUpdateRequest(BaseModel):
    item: Optional[str] = None
    category: Optional[str] = None
    day_of_month: Optional[int] = None
    amount: Optional[float] = None
    total_amount: Optional[float] = None
    installment_count: Optional[int] = None


@router.get("/plans")
async def list_dashboard_plans(request: Request):
    session = _require_session(request)
    plans = list_payment_plans(session["chat_id"])
    return {"plans": plans}


@router.patch("/plans/{plan_id}")
async def update_dashboard_plan(plan_id: str, payload: PlanUpdateRequest, request: Request):
    session = _require_session(request)
    plan = get_payment_plan(plan_id)
    if not plan or plan.get("chat_id") != session["chat_id"]:
        raise HTTPException(status_code=404, detail="Plan not found.")

    updates: dict = {}
    if payload.item is not None:
        item = payload.item.strip()
        if not item:
            raise HTTPException(status_code=400, detail="Item cannot be empty.")
        updates["item"] = item
    if payload.category is not None:
        category = payload.category.strip()
        if not category:
            raise HTTPException(status_code=400, detail="Category cannot be empty.")
        updates["category"] = category
    if payload.day_of_month is not None:
        if not 1 <= payload.day_of_month <= 31:
            raise HTTPException(status_code=400, detail="Day must be between 1 and 31.")
        updates["day_of_month"] = payload.day_of_month
    if payload.amount is not None:
        if plan.get("plan_type") != "recurring":
            raise HTTPException(status_code=400, detail="Use total_amount for split payment plans.")
        if payload.amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive.")
        updates["amount"] = payload.amount
    if payload.total_amount is not None:
        if plan.get("plan_type") != "split_payment":
            raise HTTPException(status_code=400, detail="total_amount is only supported for split payment plans.")
        if payload.total_amount <= 0:
            raise HTTPException(status_code=400, detail="Total amount must be positive.")
        updates["total_amount"] = payload.total_amount
    if payload.installment_count is not None:
        if plan.get("plan_type") != "split_payment":
            raise HTTPException(
                status_code=400,
                detail="installment_count is only supported for split payment plans.",
            )
        posted = int(plan.get("current_installment_number", 0))
        if payload.installment_count < max(1, posted):
            raise HTTPException(
                status_code=400,
                detail=f"Installment count cannot be less than already posted installments ({posted}).",
            )
        updates["installment_count"] = payload.installment_count

    merged = {**plan, **updates}
    if merged.get("plan_type") == "split_payment" and (
        "total_amount" in updates or "installment_count" in updates
    ):
        base, final_amount = compute_split_amounts(
            float(merged["total_amount"]),
            int(merged["installment_count"]),
        )
        updates["base_installment_amount"] = base
        updates["final_installment_amount"] = final_amount
        merged["base_installment_amount"] = base
        merged["final_installment_amount"] = final_amount

    if updates:
        next_due = compute_next_due_date(merged)
        updates["next_due_date"] = next_due.isoformat() if next_due else ""
        if next_due is None and merged["plan_type"] == "split_payment":
            updates["status"] = "completed"
        elif merged["plan_type"] == "split_payment":
            updates["status"] = "active"

        update_payment_plan(plan_id, **updates)
        if merged["plan_type"] == "split_payment":
            await rewrite_plan_history(plan_id)
    return {"ok": True}


@router.delete("/plans/{plan_id}")
async def delete_dashboard_plan(plan_id: str, request: Request, mode: str = "future"):
    session = _require_session(request)
    plan = get_payment_plan(plan_id)
    if not plan or plan.get("chat_id") != session["chat_id"]:
        raise HTTPException(status_code=404, detail="Plan not found.")

    delete_payment_plan(plan_id)
    deleted = 0
    if mode == "all" or plan.get("plan_type") == "split_payment":
        deleted = delete_transactions_for_plan(plan_id)
    return {"ok": True, "deleted": deleted}

