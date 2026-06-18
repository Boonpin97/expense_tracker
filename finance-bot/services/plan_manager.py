import logging
from datetime import datetime, timedelta, timezone

from models.transaction import PaymentPlan, PendingPlan, Transaction
from services import firestore, telegram
from services.categoriser import _check_budget_exceeded
from services.payment_plans import (
    compute_next_due_date,
    compute_split_amounts,
    occurrence_label,
    plan_display_line,
    plan_occurrence_for_index,
)


SGT = timezone(timedelta(hours=8))
PENDING_PLAN_EXPIRY_SECONDS = 600

logger = logging.getLogger(__name__)


def _normalise(item: str) -> str:
    import re

    return re.sub(r"[^\w\s]", "", item).strip().lower()


def pending_plan_expired(pending: dict | None) -> bool:
    if not pending:
        return True
    created_at = pending.get("created_at")
    if not created_at:
        return True
    return (datetime.now(SGT) - datetime.fromisoformat(created_at)).total_seconds() > PENDING_PLAN_EXPIRY_SECONDS


def start_pending_plan(chat_id: int, plan_type: str) -> None:
    firestore.save_pending_plan(
        PendingPlan(chat_id=chat_id, plan_type=plan_type, created_at=datetime.now(SGT).isoformat())
    )


async def send_plan_list(chat_id: int, plan_type: str) -> None:
    plans = firestore.list_payment_plans(chat_id, plan_type=plan_type, statuses=["active", "completed"])
    if not plans:
        label = "recurring payments" if plan_type == "recurring" else "split payments"
        await telegram.send_message(chat_id, f"No {label} found.")
        return
    title = "Recurring payments" if plan_type == "recurring" else "Split payments"
    lines = [f"<b>{title}</b>"]
    for idx, plan in enumerate(plans, start=1):
        status = plan.get("status", "active")
        lines.append(f"\n{idx}. {plan_display_line(plan)}\nStatus: {status}")
    await telegram.send_message(chat_id, "\n".join(lines))


async def create_plan_and_post_first_charge(chat_id: int, pending: dict) -> None:
    now = datetime.now(SGT)
    first_charge_time = now
    if pending["plan_type"] == "split_payment":
        # Split plans are defined by an explicit start date + number of months.
        # The start date drives the schedule and dates the first charge.
        raw_start = pending.get("start_date")
        start = datetime.fromisoformat(raw_start).replace(tzinfo=SGT) if raw_start else now
        months = int(pending.get("number_of_months") or pending.get("installment_count"))
        base, final_amount = compute_split_amounts(float(pending["total_amount"]), months)
        plan = PaymentPlan(
            chat_id=chat_id,
            plan_type="split_payment",
            item=pending["item"],
            category=pending["category"],
            day_of_month=start.day,
            start_year=start.year,
            start_month=start.month,
            next_due_date=start.isoformat(),
            created_at=now.isoformat(),
            total_amount=float(pending["total_amount"]),
            installment_count=months,
            current_installment_number=0,
            base_installment_amount=base,
            final_installment_amount=final_amount,
        )
        first_charge_time = start
    else:
        raw_start = pending.get("start_date")
        start = datetime.fromisoformat(raw_start).replace(tzinfo=SGT) if raw_start else now
        plan = PaymentPlan(
            chat_id=chat_id,
            plan_type="recurring",
            item=pending["item"],
            category=pending["category"],
            day_of_month=int(pending.get("day_of_month") or start.day),
            start_year=start.year,
            start_month=start.month,
            next_due_date=start.isoformat(),
            created_at=now.isoformat(),
            amount=float(pending["amount"]),
            current_installment_number=0,
        )
        first_charge_time = start

    plan_id = firestore.save_payment_plan(plan)
    plan_data = firestore.get_payment_plan(plan_id)
    await post_next_occurrence(plan_data, timestamp=first_charge_time)
    firestore.delete_pending_plan(chat_id)
    firestore.clear_user_state(chat_id)


def _advance_plan(plan: dict) -> None:
    """Move the plan to its next occurrence: bump the counter, recompute the next
    due date, and complete the plan if a split has no occurrences left."""
    updated_count = int(plan.get("current_installment_number", 0)) + 1
    next_due = compute_next_due_date({**plan, "current_installment_number": updated_count})
    status = "completed" if next_due is None and plan["plan_type"] == "split_payment" else "active"
    firestore.update_payment_plan(
        plan["id"],
        current_installment_number=updated_count,
        next_due_date=next_due.isoformat() if next_due else "",
        status=status,
    )


async def post_next_occurrence(plan: dict, timestamp: datetime | None = None) -> bool:
    if plan.get("status") != "active":
        return False
    occurrence = plan_occurrence_for_index(plan, int(plan.get("current_installment_number", 0)))
    if firestore.find_transaction_by_plan_occurrence(plan["id"], occurrence.occurrence_key):
        # The charge for this occurrence already exists but the plan counter was
        # not advanced (e.g. a prior run saved the transaction then failed before
        # updating the plan). Reconcile the plan forward so it stops being pinned
        # to an already-charged occurrence and re-evaluated on every run.
        _advance_plan(plan)
        return False
    tx_time = (timestamp or occurrence.due_date.replace(hour=0, minute=0, second=0, microsecond=0)).astimezone(SGT)
    tx = Transaction(
        item=plan["item"],
        amount=occurrence.amount,
        category=plan["category"],
        timestamp=tx_time.isoformat(),
        chat_id=plan["chat_id"],
        source_type=plan["plan_type"],
        source_plan_id=plan["id"],
        occurrence_key=occurrence.occurrence_key,
        auto_generated=True,
    )
    firestore.save_transaction(tx)
    _advance_plan(plan)
    item_key = _normalise(plan["item"])
    await telegram.send_transaction_confirmation(
        plan["chat_id"],
        plan["item"],
        occurrence.amount,
        plan["category"],
        note=occurrence_label(plan, occurrence),
    )
    await _check_budget_exceeded(plan["chat_id"], plan["category"])
    return True


async def process_due_plans(today: datetime | None = None) -> int:
    now = today or datetime.now(SGT)
    plans = firestore.list_due_payment_plans(now)
    count = 0
    for plan in plans:
        # Isolate each plan: a failure on one (Telegram error, malformed plan,
        # transient Firestore error) must not abort the run and silently skip
        # every remaining plan. Skipped plans wouldn't be retried until their
        # next due date, so the charge would be lost.
        try:
            # No explicit timestamp: post_next_occurrence dates the charge to the
            # occurrence's own due date, so a caught-up overdue charge is recorded
            # in the month it was actually due, not the day it was processed.
            posted = await post_next_occurrence(plan)
        except Exception:
            logger.exception("Failed to process due payment plan %s", plan.get("id"))
            continue
        if posted:
            count += 1
    return count


async def rewrite_plan_history(plan_id: str) -> int:
    plan = firestore.get_payment_plan(plan_id)
    if not plan:
        return 0
    firestore.delete_transactions_for_plan(plan_id)
    now = datetime.now(SGT)
    if plan["plan_type"] == "split_payment":
        total = int(plan["installment_count"])
        limit = min(total, ((now.year - plan["start_year"]) * 12 + now.month - plan["start_month"] + 1))
    else:
        limit = max(0, ((now.year - plan["start_year"]) * 12 + now.month - plan["start_month"] + 1))
    rewritten = 0
    for index in range(limit):
        occurrence = plan_occurrence_for_index(plan, index)
        tx_time = occurrence.due_date.replace(hour=0, minute=0, second=0, microsecond=0)
        tx = Transaction(
            item=plan["item"],
            amount=occurrence.amount,
            category=plan["category"],
            timestamp=tx_time.isoformat(),
            chat_id=plan["chat_id"],
            source_type=plan["plan_type"],
            source_plan_id=plan_id,
            occurrence_key=occurrence.occurrence_key,
            auto_generated=True,
        )
        firestore.save_transaction(tx)
        rewritten += 1
    current_installment_number = rewritten
    next_due = compute_next_due_date({**plan, "current_installment_number": current_installment_number})
    status = "completed" if next_due is None and plan["plan_type"] == "split_payment" else plan.get("status", "active")
    firestore.update_payment_plan(
        plan_id,
        current_installment_number=current_installment_number,
        next_due_date=next_due.isoformat() if next_due else "",
        status=status,
    )
    return rewritten
