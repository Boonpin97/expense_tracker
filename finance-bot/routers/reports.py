import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, HTTPException, Query

from services.firestore import get_category_list, get_transactions
from services.telegram import send_message

router = APIRouter()

SGT = timezone(timedelta(hours=8))


def _get_period_window(period: str) -> tuple[datetime, datetime, str]:
    now = datetime.now(SGT)

    if period == "daily":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        label = f"Daily Report ({start.strftime('%d %b')})"
    elif period == "weekly":
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)
        end_display = (end - timedelta(days=1))
        label = f"Weekly Report ({start.strftime('%d')}–{end_display.strftime('%d %b')})"
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


def _format_report(label: str, transactions: list[dict]) -> str:
    if not transactions:
        return f"📊 {label}\n─────────────────────────\nNo expenses recorded.\n─────────────────────────"

    by_category: dict[str, float] = defaultdict(float)
    for tx in transactions:
        by_category[tx["category"]] += tx["amount"]

    grand_total = sum(by_category.values())
    lines = [f"📊 {label}", "─────────────────────────"]

    category_emoji = {c["name"]: c.get("emoji", "📦") for c in get_category_list()}

    for cat, total in sorted(by_category.items(), key=lambda x: -x[1]):
        emoji = category_emoji.get(cat, "📦")
        pct = (total / grand_total * 100) if grand_total else 0
        lines.append(f"{emoji} {cat:<16} ${total:>8.2f}  {pct:>5.1f}%")

    lines.append("─────────────────────────")
    lines.append(f"💰 Total{' ' * 12}${grand_total:>8.2f}  100.0%")

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
        report = _format_report(label, transactions)
        await send_message(chat_id, f"<pre>{report}</pre>")
        total_tx += len(transactions)

    return {"ok": True, "period": period, "transactions_count": total_tx}
