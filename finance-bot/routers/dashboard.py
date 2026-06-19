import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from models.transaction import Goal, Inflow, PaymentPlan, Project, Transaction
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
    current_month_window,
    delete_goal,
    delete_project,
    get_dashboard_preferences,
    get_goal_by_id,
    get_goals,
    get_inflow_by_id,
    get_inflows_with_ids,
    get_payment_plan,
    get_project_by_id,
    get_projects,
    get_transaction_by_id,
    get_transactions_with_ids,
    get_web_session,
    delete_inflow,
    move_category,
    move_goal,
    move_project,
    save_goal,
    save_inflow,
    save_project,
    list_payment_plans,
    remove_budget,
    rename_category,
    reassign_transactions_category,
    remove_category_from_list,
    save_payment_plan,
    save_transaction,
    save_web_session,
    set_budget,
    sum_inflows_by_goal,
    sum_inflows_by_project,
    update_dashboard_preferences,
    update_goal,
    update_project,
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
    day_of_month: Optional[int] = None  # recurring
    installment_count: Optional[int] = None  # legacy split input
    start_date: Optional[str] = None  # ISO date the plan starts
    number_of_months: Optional[int] = None  # split: months to spread across
    create_first_transaction_now: bool = True


class InflowCreateRequest(BaseModel):
    item: str
    amount: float
    timestamp: str
    goal_id: Optional[str] = None
    project_id: Optional[str] = None


class InflowUpdateRequest(BaseModel):
    item: str
    amount: float
    timestamp: str
    goal_id: Optional[str] = None
    project_id: Optional[str] = None


class CategoryCreateRequest(BaseModel):
    name: str
    emoji: str = "🏷️"


class CategoryUpdateRequest(BaseModel):
    name: str
    emoji: str = "🏷️"


class CategoryMoveRequest(BaseModel):
    direction: int


class GoalCreateRequest(BaseModel):
    name: str
    target_amount: float
    emoji: str = "🎯"


class GoalUpdateRequest(BaseModel):
    name: Optional[str] = None
    target_amount: Optional[float] = None
    emoji: Optional[str] = None


class MoveRequest(BaseModel):
    direction: int


class ProjectCreateRequest(BaseModel):
    name: str
    target_amount: float
    initial_amount: float = 0.0
    deadline: str
    emoji: str = "🚀"


class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = None
    target_amount: Optional[float] = None
    initial_amount: Optional[float] = None
    deadline: Optional[str] = None
    emoji: Optional[str] = None


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


def _resolve_inflow_target(
    chat_id: int,
    goal_id: Optional[str],
    project_id: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    """Validate an income → goal/project assignment."""
    goal_id = (goal_id or "").strip() or None
    project_id = (project_id or "").strip() or None
    if goal_id and not get_goal_by_id(chat_id, goal_id):
        raise HTTPException(status_code=404, detail="Goal not found.")
    if project_id and not get_project_by_id(chat_id, project_id):
        raise HTTPException(status_code=404, detail="Project not found.")
    return goal_id, project_id


def _goal_update_fields(payload: "GoalUpdateRequest") -> dict:
    fields: dict = {}
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Goal name cannot be empty.")
        fields["name"] = name
    if payload.target_amount is not None:
        if payload.target_amount <= 0:
            raise HTTPException(status_code=400, detail="Target amount must be positive.")
        fields["target_amount"] = payload.target_amount
    if payload.emoji is not None and payload.emoji.strip():
        fields["emoji"] = payload.emoji.strip()
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update.")
    return fields


def _project_update_fields(payload: "ProjectUpdateRequest") -> dict:
    fields: dict = {}
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Project name cannot be empty.")
        fields["name"] = name
    if payload.target_amount is not None:
        if payload.target_amount <= 0:
            raise HTTPException(status_code=400, detail="Target amount must be positive.")
        fields["target_amount"] = payload.target_amount
    if payload.initial_amount is not None:
        if payload.initial_amount < 0:
            raise HTTPException(status_code=400, detail="Current amount cannot be negative.")
        fields["initial_amount"] = payload.initial_amount
    if payload.deadline is not None:
        deadline = payload.deadline.strip()
        if not deadline:
            raise HTTPException(status_code=400, detail="Deadline cannot be empty.")
        _parse_dashboard_datetime(deadline)
        fields["deadline"] = deadline
    if payload.emoji is not None and payload.emoji.strip():
        fields["emoji"] = payload.emoji.strip()
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update.")
    return fields


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

    if payment_type == "split_payment":
        # Split plans are defined by an explicit start date + number of months.
        if not payload.start_date:
            raise HTTPException(status_code=400, detail="Start date is required.")
        if payload.number_of_months is None or payload.number_of_months < 1:
            raise HTTPException(status_code=400, detail="Number of months must be a positive integer.")
        start_dt = _parse_dashboard_datetime(payload.start_date)
        base_amount, final_amount = compute_split_amounts(payload.amount, payload.number_of_months)
        plan = PaymentPlan(
            chat_id=session["chat_id"],
            plan_type="split_payment",
            item=item,
            category=category,
            day_of_month=start_dt.day,
            start_year=start_dt.year,
            start_month=start_dt.month,
            next_due_date=start_dt.isoformat(),
            created_at=datetime.now(SGT).isoformat(),
            total_amount=payload.amount,
            installment_count=payload.number_of_months,
            current_installment_number=0,
            base_installment_amount=base_amount,
            final_installment_amount=final_amount,
        )
        plan_id = save_payment_plan(plan)
        stored_plan = get_payment_plan(plan_id)
        update_payment_plan(
            plan_id,
            **_build_plan_creation_result(stored_plan, payload.create_first_transaction_now, start_dt),
        )
        return {"ok": True}

    # Recurring plans are defined by an explicit start date. The start date
    # drives the first charge date and the monthly charge day.
    if not payload.start_date:
        raise HTTPException(status_code=400, detail="Start date is required.")
    start_dt = _parse_dashboard_datetime(payload.start_date)

    plan = PaymentPlan(
        chat_id=session["chat_id"],
        plan_type="recurring",
        item=item,
        category=category,
        day_of_month=start_dt.day,
        start_year=start_dt.year,
        start_month=start_dt.month,
        next_due_date=start_dt.isoformat(),
        created_at=datetime.now(SGT).isoformat(),
        amount=payload.amount,
        current_installment_number=0,
    )

    plan_id = save_payment_plan(plan)
    stored_plan = get_payment_plan(plan_id)
    update_payment_plan(plan_id, **_build_plan_creation_result(stored_plan, payload.create_first_transaction_now, start_dt))
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
    goal_id, project_id = _resolve_inflow_target(session["chat_id"], payload.goal_id, payload.project_id)
    timestamp = _parse_dashboard_datetime(payload.timestamp)
    save_inflow(
        Inflow(
            item=item,
            amount=payload.amount,
            timestamp=timestamp.isoformat(),
            chat_id=session["chat_id"],
            created_at=datetime.now(SGT).isoformat(),
            goal_id=goal_id,
            project_id=project_id,
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
    goal_id, project_id = _resolve_inflow_target(session["chat_id"], payload.goal_id, payload.project_id)

    from services.firestore import get_db

    get_db().collection("inflows").document(inflow_id).update(
        {
            "item": item,
            "amount": payload.amount,
            "timestamp": _parse_dashboard_datetime(payload.timestamp).isoformat(),
            "goal_id": goal_id,
            "project_id": project_id,
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

    # move_category swaps with the neighbour and renormalises order positions;
    # a False result is either out-of-bounds (no-op) or a missing category.
    if not move_category(session["chat_id"], category_name, payload.direction):
        names = {category["name"] for category in get_category_list(session["chat_id"])}
        if category_name not in names:
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


@router.get("/goals")
async def list_dashboard_goals(request: Request):
    session = _require_session(request)
    goals = get_goals(session["chat_id"])
    # Goals are monthly savings targets: progress resets each calendar month.
    start, end = current_month_window()
    sums = sum_inflows_by_goal(session["chat_id"], start, end)
    return {
        "goals": [{**goal, "accumulated": sums.get(goal["id"], 0.0)} for goal in goals],
        "period": "month",
    }


@router.post("/goals")
async def create_dashboard_goal(payload: GoalCreateRequest, request: Request):
    session = _require_session(request)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Goal name cannot be empty.")
    if payload.target_amount <= 0:
        raise HTTPException(status_code=400, detail="Target amount must be positive.")
    goal_id = save_goal(
        Goal(
            chat_id=session["chat_id"],
            name=name,
            target_amount=payload.target_amount,
            created_at=datetime.now(SGT).isoformat(),
            emoji=payload.emoji.strip() or "🎯",
        )
    )
    return {"ok": True, "id": goal_id}


@router.patch("/goals/{goal_id}")
async def update_dashboard_goal(goal_id: str, payload: GoalUpdateRequest, request: Request):
    session = _require_session(request)
    fields = _goal_update_fields(payload)
    if not update_goal(session["chat_id"], goal_id, **fields):
        raise HTTPException(status_code=404, detail="Goal not found.")
    return {"ok": True}


@router.delete("/goals/{goal_id}")
async def delete_dashboard_goal(goal_id: str, request: Request):
    session = _require_session(request)
    if not delete_goal(session["chat_id"], goal_id):
        raise HTTPException(status_code=404, detail="Goal not found.")
    return {"ok": True}


@router.post("/goals/{goal_id}/move")
async def move_dashboard_goal(goal_id: str, payload: MoveRequest, request: Request):
    session = _require_session(request)
    if payload.direction not in {-1, 1}:
        raise HTTPException(status_code=400, detail="Direction must be -1 or 1.")
    if not move_goal(session["chat_id"], goal_id, payload.direction):
        if not get_goal_by_id(session["chat_id"], goal_id):
            raise HTTPException(status_code=404, detail="Goal not found.")
    return {"ok": True}


@router.get("/projects")
async def list_dashboard_projects(request: Request):
    session = _require_session(request)
    projects = get_projects(session["chat_id"])
    # Long-term projects accumulate all-time toward a deadline.
    sums = sum_inflows_by_project(session["chat_id"])
    return {
        "projects": [
            {
                **project,
                "initial_amount": float(project.get("initial_amount", 0.0) or 0.0),
                "accumulated": float(project.get("initial_amount", 0.0) or 0.0)
                + sums.get(project["id"], 0.0),
            }
            for project in projects
        ]
    }


@router.post("/projects")
async def create_dashboard_project(payload: ProjectCreateRequest, request: Request):
    session = _require_session(request)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Project name cannot be empty.")
    if payload.target_amount <= 0:
        raise HTTPException(status_code=400, detail="Target amount must be positive.")
    if payload.initial_amount < 0:
        raise HTTPException(status_code=400, detail="Current amount cannot be negative.")
    deadline = payload.deadline.strip()
    if not deadline:
        raise HTTPException(status_code=400, detail="Deadline is required.")
    # Validate the deadline parses as a date/datetime.
    _parse_dashboard_datetime(deadline)
    project_id = save_project(
        Project(
            chat_id=session["chat_id"],
            name=name,
            target_amount=payload.target_amount,
            initial_amount=payload.initial_amount,
            deadline=deadline,
            created_at=datetime.now(SGT).isoformat(),
            emoji=payload.emoji.strip() or "🚀",
        )
    )
    return {"ok": True, "id": project_id}


@router.patch("/projects/{project_id}")
async def update_dashboard_project(project_id: str, payload: ProjectUpdateRequest, request: Request):
    session = _require_session(request)
    fields = _project_update_fields(payload)
    if not update_project(session["chat_id"], project_id, **fields):
        raise HTTPException(status_code=404, detail="Project not found.")
    return {"ok": True}


@router.delete("/projects/{project_id}")
async def delete_dashboard_project(project_id: str, request: Request):
    session = _require_session(request)
    if not delete_project(session["chat_id"], project_id):
        raise HTTPException(status_code=404, detail="Project not found.")
    return {"ok": True}


@router.post("/projects/{project_id}/move")
async def move_dashboard_project(project_id: str, payload: MoveRequest, request: Request):
    session = _require_session(request)
    if payload.direction not in {-1, 1}:
        raise HTTPException(status_code=400, detail="Direction must be -1 or 1.")
    if not move_project(session["chat_id"], project_id, payload.direction):
        if not get_project_by_id(session["chat_id"], project_id):
            raise HTTPException(status_code=404, detail="Project not found.")
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
    start_date: Optional[str] = None  # ISO date — sets start month + recurring day
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
    if payload.start_date is not None:
        start_dt = _parse_dashboard_datetime(payload.start_date)
        # The start date sets both when the plan begins and the recurring day.
        updates["start_year"] = start_dt.year
        updates["start_month"] = start_dt.month
        updates["day_of_month"] = start_dt.day
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

