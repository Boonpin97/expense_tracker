import calendar
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, HTTPException, Query

from services.firestore import get_category_list, get_inflows, get_transactions, get_budgets
from services.plan_manager import process_due_plans
from services.telegram import send_message

router = APIRouter()

SGT = timezone(timedelta(hours=8))


def _get_period_window(period: str) -> tuple[datetime, datetime, str]:
    now = datetime.now(SGT)

    if period == "daily":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        label = f"Daily Report ({start.strftime('%d/%m/%y')})"
    elif period == "weekly":
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)
        end_display = (end - timedelta(days=1))
        label = f"Weekly Report ({start.strftime('%d/%m/%y')}–{end_display.strftime('%d/%m/%y')})"
    elif period == "monthly":
        first_of_current = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # If triggered on the 1st, report the previous month
        if now.day == 1:
            if first_of_current.month == 1:
                start = first_of_current.replace(year=first_of_current.year - 1, month=12)
            else:
                start = first_of_current.replace(month=first_of_current.month - 1)
            end = first_of_current
        else:
            start = first_of_current
            if start.month == 12:
                end = start.replace(year=start.year + 1, month=1)
            else:
                end = start.replace(month=start.month + 1)
        label = f"Monthly Report ({start.strftime('%b %Y')})"
    else:
        raise HTTPException(status_code=400, detail="period must be daily, weekly, or monthly")

    return start, end, label


_DIVIDER = "─────────────────────────"
_LABEL_WIDTH = 14


def _amount_cell(value: float) -> str:
    """Render a signed dollar amount in a fixed-width cell (avoids -0.00)."""
    if value == 0:
        value = 0.0
    return f"${value:>9.2f}"


def _summary_lines(expense_total: float, income_total: float) -> list[str]:
    """Shared Expense / Income / Net summary block.

    Expenses are shown as a negative total; net is income minus expenses.
    """
    net = income_total - expense_total
    return [
        _DIVIDER,
        f"💰 {'Expense':<{_LABEL_WIDTH}} {_amount_cell(-expense_total)}",
        f"💵 {'Income':<{_LABEL_WIDTH}} {_amount_cell(income_total)}",
        f"📈 {'Net':<{_LABEL_WIDTH}} {_amount_cell(net)}",
    ]


def _format_report(
    chat_id: int,
    label: str,
    transactions: list[dict],
    inflows: list[dict] | None = None,
) -> str:
    inflows = inflows or []
    income_total = sum(inflow.get("amount", 0.0) for inflow in inflows)

    by_category: dict[str, float] = defaultdict(float)
    for tx in transactions:
        by_category[tx["category"]] += tx["amount"]
    expense_total = sum(by_category.values())

    if not transactions and not inflows:
        return f"📊 {label}\n{_DIVIDER}\nNo expenses recorded.\n{_DIVIDER}"

    category_emoji = {c["name"]: c.get("emoji", "📦") for c in get_category_list(chat_id)}

    lines = [f"📊 {label}", _DIVIDER, "Expenses"]
    if transactions:
        for cat, total in sorted(by_category.items(), key=lambda x: -x[1]):
            emoji = category_emoji.get(cat, "📦")
            pct = (total / expense_total * 100) if expense_total else 0
            lines.append(f"{emoji} {cat:<{_LABEL_WIDTH}} {_amount_cell(-total)}  {pct:>5.1f}%")
    else:
        lines.append("None recorded.")

    lines.append(_DIVIDER)
    lines.append("Inflow")
    if inflows:
        for inflow in sorted(inflows, key=lambda i: i.get("timestamp", "")):
            lines.append(f"💵 {inflow.get('item', ''):<{_LABEL_WIDTH}} {_amount_cell(inflow.get('amount', 0.0))}")
    else:
        lines.append("None recorded.")

    lines.extend(_summary_lines(expense_total, income_total))
    return "\n".join(lines)


def _format_daily_report(
    chat_id: int,
    label: str,
    transactions: list[dict],
    inflows: list[dict] | None = None,
) -> str:
    inflows = inflows or []
    income_total = sum(inflow.get("amount", 0.0) for inflow in inflows)
    expense_total = sum(tx.get("amount", 0.0) for tx in transactions)

    if not transactions and not inflows:
        return f"📊 {label}\n{_DIVIDER}\nNo expenses recorded.\n{_DIVIDER}"

    category_emoji = {c["name"]: c.get("emoji", "📦") for c in get_category_list(chat_id)}

    lines = [f"📊 {label}", _DIVIDER, "Expenses"]
    if transactions:
        for tx in sorted(transactions, key=lambda t: t.get("timestamp", "")):
            emoji = category_emoji.get(tx.get("category", ""), "📦")
            item = tx.get("item", "")
            ts = datetime.fromisoformat(tx["timestamp"]).astimezone(SGT)
            time_str = ts.strftime("%I:%M %p")
            lines.append(f"{emoji} {item:<{_LABEL_WIDTH}} {_amount_cell(-tx.get('amount', 0.0))}  {time_str}")
    else:
        lines.append("None recorded.")

    lines.append(_DIVIDER)
    lines.append("Inflow")
    if inflows:
        for inflow in sorted(inflows, key=lambda i: i.get("timestamp", "")):
            item = inflow.get("item", "")
            ts = datetime.fromisoformat(inflow["timestamp"]).astimezone(SGT)
            time_str = ts.strftime("%I:%M %p")
            lines.append(f"💵 {item:<{_LABEL_WIDTH}} {_amount_cell(inflow.get('amount', 0.0))}  {time_str}")
    else:
        lines.append("None recorded.")

    lines.extend(_summary_lines(expense_total, income_total))
    return "\n".join(lines)


@router.post("/trigger-report")
async def trigger_report(
    period: str = Query(...),
    x_scheduler_token: str = Header(None, alias="X-Scheduler-Token"),
):
    expected_secret = os.getenv("SCHEDULER_SECRET", "")
    if not expected_secret or x_scheduler_token != expected_secret:
        raise HTTPException(status_code=403, detail="Forbidden")

    from services.firestore import get_allowed_chat_ids
    chat_ids = list(get_allowed_chat_ids())
    if not chat_ids:
        raise HTTPException(status_code=500, detail="No authorized chat IDs configured")

    start, end, label = _get_period_window(period)
    total_tx = 0
    for chat_id in chat_ids:
        transactions = get_transactions(chat_id, start, end)
        inflows = get_inflows(chat_id, start, end)
        formatter = _format_daily_report if period == "daily" else _format_report
        report = formatter(chat_id, label, transactions, inflows)
        await send_message(chat_id, f"<pre>{report}</pre>")
        total_tx += len(transactions)

    return {"ok": True, "period": period, "transactions_count": total_tx}


def _format_budget_report(chat_id: int) -> str:
    """Build a budget report comparing month-to-date spending vs pro-rated budget."""
    budgets = get_budgets(chat_id)
    if not budgets:
        return ""

    now = datetime.now(SGT)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    current_day = now.day

    transactions = get_transactions(chat_id, month_start, month_end + timedelta(seconds=1))

    by_category: dict[str, float] = defaultdict(float)
    for tx in transactions:
        by_category[tx["category"]] += tx["amount"]

    category_emoji = {c["name"]: c.get("emoji", "📦") for c in get_category_list(chat_id)}

    lines = [
        f"📋 Budget Report ({now.strftime('%d/%m/%y')})",
        f"Day {current_day} of {days_in_month}",
        "─────────────────────────────────",
    ]

    for cat, monthly_amount in sorted(budgets.items()):
        emoji = category_emoji.get(cat, "📦")
        spent = by_category.get(cat, 0.0)
        prorated = monthly_amount / days_in_month * current_day
        status = "❗️" if spent > prorated else "😊"
        lines.append(f"{emoji} {cat:<16} ${spent:>8.2f} / {prorated:>5.2f} {status}")

    lines.append("─────────────────────────────────")
    total_spent = sum(by_category.get(cat, 0.0) for cat in budgets)
    total_prorated = sum(amt / days_in_month * current_day for amt in budgets.values())
    lines.append(f"💰 Total{' ' * 12}${total_spent:>8.2f} / ${total_prorated:>8.2f}")

    return "\n".join(lines)


@router.post("/trigger-budget-report")
async def trigger_budget_report(
    x_scheduler_token: str = Header(None, alias="X-Scheduler-Token"),
):
    expected_secret = os.getenv("SCHEDULER_SECRET", "")
    if not expected_secret or x_scheduler_token != expected_secret:
        raise HTTPException(status_code=403, detail="Forbidden")

    from services.firestore import get_allowed_chat_ids
    chat_ids = list(get_allowed_chat_ids())
    if not chat_ids:
        raise HTTPException(status_code=500, detail="No authorized chat IDs configured")

    for chat_id in chat_ids:
        report = _format_budget_report(chat_id)
        if not report:
            await send_message(
                chat_id,
                "No monthly budget found yet. You can set a monthly budget via the command /set_budget",
            )
        else:
            await send_message(chat_id, f"<pre>{report}</pre>")

    return {"ok": True}


@router.post("/trigger-recurring-payments")
async def trigger_recurring_payments(
    x_scheduler_token: str = Header(None, alias="X-Scheduler-Token"),
):
    expected_secret = os.getenv("SCHEDULER_SECRET", "")
    if not expected_secret or x_scheduler_token != expected_secret:
        raise HTTPException(status_code=403, detail="Forbidden")

    processed = await process_due_plans()
    return {"ok": True, "processed": processed}
