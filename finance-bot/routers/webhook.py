import os
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request

from routers.reports import _format_report, _get_period_window
from services import telegram
from services.categoriser import (
    PENDING_EXPIRY_SECONDS,
    build_transaction_timestamp,
    handle_category_selection,
    handle_custom_category_input,
    handle_expense,
)
from services.dashboard_auth import hash_password, is_valid_username, validate_password
from services.firestore import (
    add_category_to_list,
    cancel_payment_plan,
    clear_user_state,
    delete_category,
    delete_pending,
    delete_pending_change,
    delete_pending_plan,
    delete_transactions_for_plan,
    delete_transaction,
    get_category_list,
    get_last_transaction,
    get_payment_plan,
    get_pending,
    get_pending_change,
    get_pending_plan,
    get_transaction_by_id,
    get_transactions,
    get_transactions_with_ids,
    get_user_state,
    list_payment_plans,
    reassign_transactions_category,
    remove_category_from_list,
    rename_category,
    save_category,
    save_pending_change,
    set_user_state,
    upsert_web_account,
    delete_web_sessions_for_chat,
    update_category_emoji,
    update_category_order,
    update_payment_plan,
    update_pending_plan,
    update_transaction_category,
    update_transaction_timestamp,
)
from services.interaction_sessions import (
    clear_session,
    get_session,
    is_expired as session_expired,
    start_session,
    update_session,
)
from services.parser import parse_expense, parse_transaction_date
from services.payment_plans import (
    compute_next_due_date,
    compute_split_amounts,
    plan_display_line,
    plan_occurrence_for_index,
)
from services.plan_manager import (
    create_plan_and_post_first_charge,
    pending_plan_expired,
    rewrite_plan_history,
    send_plan_list,
    start_pending_plan,
)

router = APIRouter()

SGT = timezone(timedelta(hours=8))
ALLOWED_CHAT_IDS: set[int] | None = None


def _get_allowed_chat_ids() -> set[int]:
    global ALLOWED_CHAT_IDS
    if ALLOWED_CHAT_IDS is None:
        raw = os.getenv("TELEGRAM_CHAT_IDS", "")
        ALLOWED_CHAT_IDS = {
            int(cid.strip()) for cid in raw.split(",") if cid.strip().lstrip("-").isdigit()
        }
    return ALLOWED_CHAT_IDS


def _is_expired(timestamp_iso: str, expiry_seconds: int = PENDING_EXPIRY_SECONDS) -> bool:
    try:
        created_at = datetime.fromisoformat(timestamp_iso)
        return (datetime.now(SGT) - created_at).total_seconds() > expiry_seconds
    except Exception:
        return False


def _valid_amount(text: str) -> float | None:
    try:
        value = float(text.strip().replace("$", ""))
    except ValueError:
        return None
    return value if value > 0 else None


def _valid_day(text: str) -> int | None:
    try:
        day = int(text.strip())
    except ValueError:
        return None
    return day if 1 <= day <= 31 else None


def _valid_months(text: str) -> int | None:
    try:
        months = int(text.strip())
    except ValueError:
        return None
    return months if months > 0 else None


def _valid_transaction_date(text: str) -> str | None:
    return parse_transaction_date(text)


def _parse_user_date_or_none(text: str) -> datetime | None:
    parsed = parse_transaction_date(text)
    if parsed is None:
        return None
    return datetime.strptime(parsed, "%Y-%m-%d").replace(tzinfo=SGT)


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    absolute = year * 12 + (month - 1) + delta
    return absolute // 12, absolute % 12 + 1


def _get_month_window(year: int, month: int) -> tuple[datetime, datetime, str]:
    start = datetime(year, month, 1, tzinfo=SGT)
    next_year, next_month = _shift_month(year, month, 1)
    end = datetime(next_year, next_month, 1, tzinfo=SGT)
    label = f"Monthly Report ({start.strftime('%b %Y')})"
    return start, end, label


def _parse_month_input_or_none(text: str) -> tuple[int, int] | None:
    cleaned = text.strip()
    if not re.fullmatch(r"\d{4}", cleaned):
        return None
    month = int(cleaned[:2])
    year = 2000 + int(cleaned[2:])
    if not 1 <= month <= 12:
        return None
    return year, month


def _build_monthly_report_buttons(now: datetime) -> list[tuple[str, str]]:
    buttons = [("Current month", f"monthrep:{now.year}{now.month:02d}")]
    for delta in range(-1, -4, -1):
        year, month = _shift_month(now.year, now.month, delta)
        label = datetime(year, month, 1, tzinfo=SGT).strftime("%B")
        buttons.append((label, f"monthrep:{year}{month:02d}"))
    buttons.append(("Earlier months", "monthrep:earlier"))
    return buttons


def _split_plan_edit_notice() -> str:
    return (
        "Editing a split payment changes how the total is spread.\n"
        "- <b>Future only</b>: past auto-generated charges stay as they are, and only future charges change.\n"
        "- <b>Rewrite past auto charges</b>: past auto-generated charges for this plan are rebuilt so the whole plan stays consistent."
    )


def _format_split_edit_result(plan: dict, updates: dict, rewrite_mode: str) -> str:
    old_total = float(plan["total_amount"])
    old_months = int(plan["installment_count"])
    posted = int(plan.get("current_installment_number", 0))
    new_total = float(updates.get("total_amount", old_total))
    new_months = int(updates.get("installment_count", old_months))
    base, final_amount = compute_split_amounts(new_total, new_months)

    lines = []
    if "installment_count" in updates:
        lines.append(
            f"Months changed from <b>{old_months}</b> to <b>{new_months}</b>. "
            f"The rebuilt schedule is <b>${base:.2f}</b> per month"
            + (f", with the last month at <b>${final_amount:.2f}</b>." if final_amount != base else ".")
        )
    if "total_amount" in updates:
        lines.append(
            f"Total cost changed from <b>${old_total:.2f}</b> to <b>${new_total:.2f}</b>. "
            f"The rebuilt schedule is <b>${base:.2f}</b> per month"
            + (f", with the last month at <b>${final_amount:.2f}</b>." if final_amount != base else ".")
        )

    if rewrite_mode == "future":
        lines.append(
            f"Past auto-generated charges are unchanged. "
            f"{posted} installment(s) already posted stay on record; only future installments use the new values."
        )
    else:
        lines.append("Past auto-generated charges for this plan were rebuilt to match the new schedule.")

    return "\n".join(lines)


def _format_split_rewrite_projection(plan: dict, pending: dict) -> str:
    field = pending.get("edit_field")
    raw_value = pending.get("edit_value")
    old_total = float(plan["total_amount"])
    old_months = int(plan["installment_count"])
    posted = int(plan.get("current_installment_number", 0))
    old_base, old_final = compute_split_amounts(old_total, old_months)

    new_total = old_total
    new_months = old_months
    if field == "amount" and raw_value is not None:
        new_total = float(raw_value)
    elif field == "months" and raw_value is not None:
        new_months = int(raw_value)

    new_base, new_final = compute_split_amounts(new_total, new_months)
    old_posted_labels = [
        plan_occurrence_for_index(plan, idx).due_date.strftime("%b %Y")
        for idx in range(posted)
    ]

    projected_plan = {
        **plan,
        "total_amount": new_total,
        "installment_count": new_months,
        "base_installment_amount": new_base,
        "final_installment_amount": new_final,
    }
    future_labels = [
        plan_occurrence_for_index(projected_plan, idx).due_date.strftime("%b %Y")
        for idx in range(posted, new_months)
    ]
    rewritten_labels = [
        plan_occurrence_for_index(projected_plan, idx).due_date.strftime("%b %Y")
        for idx in range(new_months)
    ]

    lines = [
        "Should this edit affect only future charges, or also rewrite past auto-generated charges for this plan?",
        "",
        "<b>Projection</b>",
        f"Current plan: <b>${old_total:.2f}</b> over <b>{old_months}</b> months.",
    ]

    if posted > 0:
        lines.append(
            f"Past posted installments now: <b>{', '.join(old_posted_labels)}</b> are currently "
            f"<b>${old_base:.2f}</b>{f' to ${old_final:.2f} on the last month' if old_final != old_base else ''}."
        )
    else:
        lines.append("No past installments have posted yet.")

    lines.append(
        f"Future schedule after this edit: <b>${new_base:.2f}</b> per month"
        + (f", with the last month at <b>${new_final:.2f}</b>." if new_final != new_base else ".")
    )
    if future_labels:
        lines.append(
            f"Projected future months: <b>{', '.join(future_labels)}</b>."
        )

    if posted > 0:
        lines.append("")
        lines.append("<b>If you choose Future only</b>")
        lines.append(
            f"Past <b>{', '.join(old_posted_labels)}</b> stay unchanged at the old amount(s). "
            f"Future <b>{', '.join(future_labels) if future_labels else 'months'}</b> use the new schedule."
        )
        if field == "months":
            lines.append(
                f"Example: posted charges remain at <b>${old_base:.2f}</b>; remaining charges follow the new {new_months}-month setup."
            )
        elif field == "amount":
            lines.append(
                f"Example: posted charges remain at <b>${old_base:.2f}</b>; remaining charges are recalculated from the new total <b>${new_total:.2f}</b>."
            )

        lines.append("")
        lines.append("<b>If you choose Rewrite past auto charges</b>")
        lines.append(
            f"Past and future plan months <b>{', '.join(rewritten_labels)}</b> are all rebuilt to match the new schedule "
            f"of <b>${new_base:.2f}</b>{f' and last month ${new_final:.2f}' if new_final != new_base else ''}."
        )
    else:
        lines.append("")
        lines.append("Since no installments have posted yet, both options will produce the same future schedule.")

    return "\n".join(lines)


async def _send_plan_rewrite_prompt(chat_id: int) -> None:
    pending = get_pending_plan(chat_id)
    if not pending or pending_plan_expired(pending):
        delete_pending_plan(chat_id)
        clear_user_state(chat_id)
        await telegram.send_message(chat_id, "⏰ This plan edit has expired. Start the edit command again.")
        return

    plan = get_payment_plan(pending["selected_plan_id"])
    if not plan:
        delete_pending_plan(chat_id)
        clear_user_state(chat_id)
        await telegram.send_message(chat_id, "⚠️ That plan no longer exists.")
        return

    prompt = "Should this edit affect only future charges, or also rewrite past auto-generated charges for this plan?"
    if plan["plan_type"] == "split_payment":
        prompt = _format_split_rewrite_projection(plan, pending)
    await telegram.send_plan_rewrite_keyboard(chat_id, prompt)


async def _prompt_after_plan_category(chat_id: int, pending: dict) -> None:
    if pending["plan_type"] == "recurring":
        set_user_state(chat_id, "awaiting_recurring_amount")
        await telegram.send_message(chat_id, "Send the monthly amount, e.g. <code>15.90</code>")
    else:
        set_user_state(chat_id, "awaiting_split_total")
        await telegram.send_message(chat_id, "Send the total amount, e.g. <code>100</code>")


async def _apply_plan_edit(chat_id: int, rewrite_mode: str) -> None:
    pending = get_pending_plan(chat_id)
    if not pending or pending_plan_expired(pending):
        delete_pending_plan(chat_id)
        clear_user_state(chat_id)
        await telegram.send_message(chat_id, "⏰ This plan edit has expired. Start the edit command again.")
        return

    plan = get_payment_plan(pending["selected_plan_id"])
    if not plan:
        delete_pending_plan(chat_id)
        clear_user_state(chat_id)
        await telegram.send_message(chat_id, "⚠️ That plan no longer exists.")
        return

    field = pending.get("edit_field")
    raw_value = pending.get("edit_value")
    updates = {}

    if field == "item":
        updates["item"] = raw_value.strip()
    elif field == "category":
        updates["category"] = raw_value.strip().title()
    elif field == "amount":
        amount = float(raw_value)
        if plan["plan_type"] == "recurring":
            updates["amount"] = amount
        else:
            base, final_amount = compute_split_amounts(amount, int(plan["installment_count"]))
            updates["total_amount"] = amount
            updates["base_installment_amount"] = base
            updates["final_installment_amount"] = final_amount
    elif field == "day":
        updates["day_of_month"] = int(raw_value)
    elif field == "months" and plan["plan_type"] == "split_payment":
        months = int(raw_value)
        posted = int(plan.get("current_installment_number", 0))
        if months < max(1, posted):
            await telegram.send_message(chat_id, f"⚠️ Months cannot be less than already posted installments ({posted}).")
            return
        base, final_amount = compute_split_amounts(float(plan["total_amount"]), months)
        updates["installment_count"] = months
        updates["base_installment_amount"] = base
        updates["final_installment_amount"] = final_amount
    else:
        delete_pending_plan(chat_id)
        clear_user_state(chat_id)
        await telegram.send_message(chat_id, "⚠️ Unsupported plan edit.")
        return

    merged = {**plan, **updates}
    next_due = compute_next_due_date(merged)
    updates["next_due_date"] = next_due.isoformat() if next_due else ""
    if next_due is None and merged["plan_type"] == "split_payment":
        updates["status"] = "completed"

    update_payment_plan(plan["id"], **updates)

    detail = ""
    if merged["plan_type"] == "split_payment":
        detail = _format_split_edit_result(plan, updates, rewrite_mode)

    if rewrite_mode == "rewrite":
        rewritten = await rewrite_plan_history(plan["id"])
        msg = f"✅ Plan updated and rewrote {rewritten} auto-generated charge(s)."
    else:
        msg = "✅ Plan updated for future charges."

    if detail:
        msg = f"{msg}\n{detail}"

    delete_pending_plan(chat_id)
    clear_user_state(chat_id)
    await telegram.send_message(chat_id, msg)


async def _handle_plan_category_selection(chat_id: int, category: str, callback_query_id: str) -> None:
    pending = get_pending_plan(chat_id)
    if not pending or pending_plan_expired(pending):
        delete_pending_plan(chat_id)
        clear_user_state(chat_id)
        await telegram.answer_callback_query(callback_query_id, "Expired.")
        await telegram.send_message(chat_id, "⏰ This plan flow has expired. Start the command again.")
        return

    if category == "__new__":
        set_user_state(chat_id, "awaiting_plan_new_cat_name")
        await telegram.answer_callback_query(callback_query_id, "")
        await telegram.send_message(chat_id, "✏️ Type the name of the new category:")
        return

    update_pending_plan(chat_id, category=category)
    await telegram.answer_callback_query(callback_query_id, f"Saved as {category}")

    user_state = get_user_state(chat_id)
    if user_state == "awaiting_plan_edit_category":
        update_pending_plan(chat_id, edit_value=category)
        set_user_state(chat_id, "awaiting_plan_edit_rewrite")
        await _send_plan_rewrite_prompt(chat_id)
        return

    await _prompt_after_plan_category(chat_id, {**pending, "category": category})


async def _start_plan_edit(chat_id: int, plan_type: str) -> None:
    plans = list_payment_plans(chat_id, plan_type=plan_type, statuses=["active", "completed"])
    if not plans:
        await telegram.send_message(chat_id, "No matching plans found.")
        return
    action = "editrecurring" if plan_type == "recurring" else "editsplit"
    label = "recurring" if plan_type == "recurring" else "split payment"
    prompt = f"Select a {label} plan to edit:"
    if plan_type == "split_payment":
        prompt = f"{prompt}\n\n{_split_plan_edit_notice()}"
    await telegram.send_plan_keyboard(chat_id, plans, action, prompt)


async def _start_plan_delete(chat_id: int, plan_type: str) -> None:
    plans = list_payment_plans(chat_id, plan_type=plan_type, statuses=["active", "completed"])
    if not plans:
        await telegram.send_message(chat_id, "No matching plans found.")
        return
    action = "delrecurring" if plan_type == "recurring" else "delsplit"
    label = "recurring" if plan_type == "recurring" else "split payment"
    await telegram.send_plan_keyboard(chat_id, plans, action, f"Select a {label} plan to stop:")


def _plan_delete_prompt(plan: dict) -> str:
    return (
        f"What do you want to do with this plan?\n\n{plan_display_line(plan)}\n\n"
        "- <b>Stop future only</b>: keep past charges on record.\n"
        "- <b>Stop future + remove past</b>: keep no auto-generated charges from this plan."
    )


async def _get_active_session_or_expire(chat_id: int, flow_type: str) -> dict | None:
    session = get_session(chat_id)
    if not session or session.get("flow_type") != flow_type:
        return None
    if session_expired(session):
        clear_session(chat_id)
        clear_user_state(chat_id)
        if flow_type == "dashboard_account":
            await telegram.send_message(chat_id, "⏰ The dashboard account setup has expired. Send /dashboard_account again.")
        else:
            await telegram.send_message(chat_id, "⏰ This flow has expired. Please start again.")
        return None
    return session


async def _handle_dashboard_account_session(chat_id: int, text: str) -> bool:
    session = await _get_active_session_or_expire(chat_id, "dashboard_account")
    if not session:
        return False

    step = session.get("step")
    payload = session.get("payload", {})
    if step == "awaiting_username":
        username = text.strip()
        if not is_valid_username(username):
            await telegram.send_message(
                chat_id,
                "⚠️ Username must be 3-32 characters using only letters, numbers, dots, underscores, or dashes.",
            )
            return True

        update_session(chat_id, step="awaiting_password", payload_updates={"username": username})
        await telegram.send_message(
            chat_id,
            "Now send the dashboard password you want to use. It will be hashed before storing.",
        )
        return True

    if step == "awaiting_password":
        username = payload.get("username", "").strip()
        if not username:
            clear_session(chat_id)
            clear_user_state(chat_id)
            await telegram.send_message(chat_id, "⚠️ Username setup was lost. Send /dashboard_account again.")
            return True

        password_error = validate_password(text)
        if password_error:
            await telegram.send_message(chat_id, f"⚠️ {password_error}")
            return True

        try:
            upsert_web_account(
                chat_id=chat_id,
                username=username,
                password_hash=hash_password(text),
            )
        except ValueError as exc:
            await telegram.send_message(chat_id, f"⚠️ {exc}")
            return True

        delete_web_sessions_for_chat(chat_id)
        clear_session(chat_id)
        clear_user_state(chat_id)
        await telegram.send_message(
            chat_id,
            "✅ Dashboard login saved.\n"
            "Use your username and password at <a href=\"https://budget-bot-123.web.app\">budget-bot-123.web.app</a>.",
        )
        return True

    clear_session(chat_id)
    clear_user_state(chat_id)
    await telegram.send_message(chat_id, "⚠️ Dashboard setup was interrupted. Send /dashboard_account again.")
    return True


@router.post("/webhook")
async def webhook(request: Request):
    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    if secret:
        token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if token != secret:
            raise HTTPException(status_code=403, detail="Forbidden")

    data = await request.json()

    if "callback_query" in data:
        callback = data["callback_query"]
        chat_id = callback["message"]["chat"]["id"]

        if chat_id not in _get_allowed_chat_ids():
            return {"ok": True}

        callback_data = callback.get("data", "")
        callback_query_id = callback["id"]

        if callback_data.startswith("cat:") and get_user_state(chat_id) in {
            "awaiting_plan_category",
            "awaiting_plan_edit_category",
        }:
            await _handle_plan_category_selection(chat_id, callback_data[4:], callback_query_id)

        elif callback_data.startswith("cat:"):
            category = callback_data[4:]
            await handle_category_selection(chat_id, category, callback_query_id)

        elif callback_data.startswith("del:"):
            remainder = callback_data[4:]
            colon_pos = remainder.find(":")
            if colon_pos != -1:
                doc_id = remainder[:colon_pos]
                ts = remainder[colon_pos + 1:]
                if _is_expired(ts):
                    await telegram.answer_callback_query(callback_query_id, "⏰ Expired.")
                    await telegram.send_message(chat_id, "⏰ These delete options have expired. Please send the command again.")
                    return {"ok": True}
            else:
                doc_id = remainder
            tx = get_transaction_by_id(doc_id)
            delete_transaction(doc_id)
            await telegram.answer_callback_query(callback_query_id, "Deleted!")
            if tx:
                ts = datetime.fromisoformat(tx["timestamp"]).astimezone(SGT)
                date_str = ts.strftime("%d %b %Y, %I:%M %p")
                await telegram.send_message(
                    chat_id,
                    f"🗑️ Deleted: <b>{tx['item']}</b>\n💰 ${tx['amount']:.2f} · 🏷️ {tx['category']}\n🕐 {date_str}",
                )
            else:
                await telegram.send_message(chat_id, "🗑️ Transaction deleted.")

        elif callback_data.startswith("rmcat:"):
            remainder = callback_data[6:]
            if "|" in remainder:
                category_name, ts = remainder.split("|", 1)
                if _is_expired(ts):
                    await telegram.answer_callback_query(callback_query_id, "⏰ Expired.")
                    await telegram.send_message(chat_id, "⏰ These options have expired. Please send /remove_category again.")
                    return {"ok": True}
            else:
                category_name = remainder
            removed = remove_category_from_list(category_name)
            count = delete_category(category_name)
            tx_count = reassign_transactions_category(category_name, "Other")
            if removed:
                await telegram.answer_callback_query(callback_query_id, f"Removed {category_name}")
                msg = f"🗑️ Removed category <b>{category_name}</b> and {count} item mapping(s)."
                if tx_count > 0:
                    msg += f"\n🔄 {tx_count} transaction(s) reassigned to <b>Other</b>."
                await telegram.send_message(chat_id, msg)
            else:
                await telegram.answer_callback_query(callback_query_id, "Not found")
                await telegram.send_message(chat_id, f"⚠️ Category <b>{category_name}</b> not found.")

        elif callback_data.startswith("chgcat:"):
            parts = callback_data[7:].split(":", 1)
            if len(parts) == 2:
                tx_id, item_key = parts
                save_pending_change(chat_id, tx_id, item_key)
                await telegram.answer_callback_query(callback_query_id, "")
                await telegram.send_category_keyboard(chat_id, item_key, 0)

        elif callback_data.startswith("chgdate:"):
            tx_id = callback_data.split(":", 1)[1]
            tx = get_transaction_by_id(tx_id)
            if not tx:
                await telegram.answer_callback_query(callback_query_id, "Not found")
                await telegram.send_message(chat_id, "⚠️ That transaction no longer exists.")
                return {"ok": True}

            item_key = tx.get("item", "transaction")
            save_pending_change(chat_id, tx_id, item_key)
            set_user_state(chat_id, f"awaiting_change_date:{tx_id}")
            await telegram.answer_callback_query(callback_query_id, "")
            await telegram.send_message(chat_id, "Send the new transaction date in <code>DDMMYY</code> format, for example <code>130126</code>.")

        elif callback_data.startswith("monthrep:"):
            target = callback_data.split(":", 1)[1]
            await telegram.answer_callback_query(callback_query_id, "")
            if target == "earlier":
                set_user_state(chat_id, "awaiting_monthly_report_month")
                await telegram.send_message(chat_id, "Enter the month in <code>MMYY</code> format, for example <code>0126</code>.")
                return {"ok": True}

            if not re.fullmatch(r"\d{6}", target):
                await telegram.send_message(chat_id, "⚠️ Invalid month selection.")
                return {"ok": True}

            year = int(target[:4])
            month = int(target[4:])
            if not 1 <= month <= 12:
                await telegram.send_message(chat_id, "⚠️ Invalid month selection.")
                return {"ok": True}

            start, end, label = _get_month_window(year, month)
            transactions = get_transactions(chat_id, start, end)
            report = _format_report(label, transactions)
            await telegram.send_message(chat_id, f"<pre>{report}</pre>")

        elif callback_data.startswith("editcat:"):
            remainder = callback_data[8:]
            if "|" in remainder:
                category_name, ts = remainder.split("|", 1)
                if _is_expired(ts):
                    await telegram.answer_callback_query(callback_query_id, "⏰ Expired.")
                    await telegram.send_message(chat_id, "⏰ These options have expired. Please send /edit_category again.")
                    return {"ok": True}
            else:
                category_name = remainder
            cat = next((c for c in get_category_list() if c["name"] == category_name), None)
            if not cat:
                await telegram.answer_callback_query(callback_query_id, "Not found")
                await telegram.send_message(chat_id, f"⚠️ Category <b>{category_name}</b> not found.")
                return {"ok": True}
            await telegram.answer_callback_query(callback_query_id, "")
            await telegram.send_edit_category_field_keyboard(chat_id, category_name, cat.get("emoji", "🏷️"))

        elif callback_data.startswith("editfield:"):
            remainder = callback_data[10:]
            if "|" in remainder:
                body, ts = remainder.split("|", 1)
                if _is_expired(ts):
                    await telegram.answer_callback_query(callback_query_id, "⏰ Expired.")
                    await telegram.send_message(chat_id, "⏰ These options have expired. Please send /edit_category again.")
                    return {"ok": True}
            else:
                body = remainder
            field, _, category_name = body.partition(":")
            if field not in ("emoji", "name", "order") or not category_name:
                await telegram.answer_callback_query(callback_query_id, "Invalid")
                return {"ok": True}
            now_iso = datetime.now(SGT).isoformat()
            set_user_state(chat_id, f"awaiting_edit_cat_{field}:{category_name}|{now_iso}")
            await telegram.answer_callback_query(callback_query_id, "")
            if field == "emoji":
                prompt = f"Send the new emoji for <b>{category_name}</b>:"
            elif field == "name":
                prompt = f"Send the new name for <b>{category_name}</b>:"
            else:
                max_order = len([c for c in get_category_list() if c["name"] != "Other"])
                prompt = f"Send the new order number for <b>{category_name}</b> (1 = first item, {max_order} = last item)"
            await telegram.send_message(chat_id, prompt)

        elif callback_data.startswith("editrecurring:"):
            plan_id = callback_data.split(":", 1)[1]
            plan = get_payment_plan(plan_id)
            if not plan:
                await telegram.answer_callback_query(callback_query_id, "Not found")
                return {"ok": True}
            start_pending_plan(chat_id, plan["plan_type"])
            update_pending_plan(chat_id, selected_plan_id=plan_id)
            await telegram.answer_callback_query(callback_query_id, "")
            await telegram.send_plan_edit_field_keyboard(chat_id, plan_id, plan["plan_type"])

        elif callback_data.startswith("delrecurring:") or callback_data.startswith("delsplit:"):
            plan_id = callback_data.split(":", 1)[1]
            plan = get_payment_plan(plan_id)
            if not plan:
                await telegram.answer_callback_query(callback_query_id, "Not found")
                return {"ok": True}
            await telegram.answer_callback_query(callback_query_id, "")
            await telegram.send_plan_delete_mode_keyboard(chat_id, plan_id, _plan_delete_prompt(plan))

        elif callback_data.startswith("plandelmode:"):
            _, mode, plan_id = callback_data.split(":", 2)
            plan = get_payment_plan(plan_id)
            if not plan:
                await telegram.answer_callback_query(callback_query_id, "Not found")
                return {"ok": True}
            cancel_payment_plan(plan_id)
            removed = 0
            if mode == "all":
                removed = delete_transactions_for_plan(plan_id)
                await telegram.answer_callback_query(callback_query_id, "Stopped and removed")
                await telegram.send_message(
                    chat_id,
                    f"🛑 Stopped future charges and removed <b>{removed}</b> past auto-generated charge(s) for:\n{plan_display_line(plan)}",
                )
            else:
                await telegram.answer_callback_query(callback_query_id, "Stopped")
                await telegram.send_message(
                    chat_id,
                    f"🛑 Stopped future charges for:\n{plan_display_line(plan)}\nPast charges from this plan are still on record.",
                )

        elif callback_data.startswith("editplanfield:"):
            _, field, plan_id = callback_data.split(":", 2)
            plan = get_payment_plan(plan_id)
            if not plan:
                await telegram.answer_callback_query(callback_query_id, "Not found")
                return {"ok": True}
            if field == "months" and plan["plan_type"] != "split_payment":
                await telegram.answer_callback_query(callback_query_id, "Not applicable")
                return {"ok": True}
            update_pending_plan(chat_id, selected_plan_id=plan_id, edit_field=field)
            await telegram.answer_callback_query(callback_query_id, "")
            if field == "category":
                set_user_state(chat_id, "awaiting_plan_edit_category")
                await telegram.send_category_keyboard(chat_id, plan["item"], plan.get("amount") or plan.get("total_amount") or 0)
            else:
                state = {
                    "item": "awaiting_plan_edit_item",
                    "amount": "awaiting_plan_edit_amount",
                    "day": "awaiting_plan_edit_day",
                    "months": "awaiting_plan_edit_months",
                }[field]
                set_user_state(chat_id, state)
                prompts = {
                    "item": "Send the new transaction name:",
                    "amount": (
                        "Send the new total amount.\n"
                        "Example: changing $100 over 4 months to $50 will recalculate the schedule.\n"
                        f"{_split_plan_edit_notice()}" if plan["plan_type"] == "split_payment" else "Send the new amount:"
                    ),
                    "day": "Send the new charge day (1-31):",
                    "months": (
                        "Send the new number of months.\n"
                        "Example: changing $100 over 4 months to 2 months rebuilds the plan as $50 + $50.\n"
                        f"{_split_plan_edit_notice()}"
                    ),
                }
                await telegram.send_message(chat_id, prompts[field])

        elif callback_data.startswith("planrewrite:"):
            mode = callback_data.split(":", 1)[1]
            await telegram.answer_callback_query(callback_query_id, "")
            await _apply_plan_edit(chat_id, mode)

        return {"ok": True}

    if "message" not in data:
        return {"ok": True}

    message = data["message"]
    chat_id = message["chat"]["id"]

    if chat_id not in _get_allowed_chat_ids():
        return {"ok": True}

    text = message.get("text", "")

    if text.startswith("/"):
        if text == "/start":
            await telegram.send_message(chat_id, "👋 Welcome! Send me an expense like <b>Coffee $10</b> and I'll track it for you.")
        elif text.startswith("/report"):
            parts = text.split()
            if len(parts) < 2:
                await telegram.send_message(chat_id, "Usage: <code>/report 130126</code>")
            else:
                arg = parts[1]
                day_start = _parse_user_date_or_none(arg)
                if day_start is None:
                    await telegram.send_message(chat_id, "Invalid date. Use <code>DDMMYY</code>, e.g. <code>/report 130126</code>")
                else:
                    day_end = day_start + timedelta(days=1)
                    label = f"Daily Report ({day_start.strftime('%d %b %Y')})"
                    transactions = get_transactions(chat_id, day_start, day_end)
                    report = _format_report(label, transactions)
                    await telegram.send_message(chat_id, f"<pre>{report}</pre>")
        elif text.startswith("/daily"):
            start, end, label = _get_period_window("daily")
            transactions = get_transactions(chat_id, start, end)
            report = _format_report(label, transactions)
            await telegram.send_message(chat_id, f"<pre>{report}</pre>")
        elif text.startswith("/weekly"):
            start, end, label = _get_period_window("weekly")
            transactions = get_transactions(chat_id, start, end)
            report = _format_report(label, transactions)
            await telegram.send_message(chat_id, f"<pre>{report}</pre>")
        elif text.startswith("/monthly"):
            now = datetime.now(SGT)
            buttons = _build_monthly_report_buttons(now)
            await telegram.send_monthly_report_keyboard(
                chat_id,
                buttons,
                "Choose a month for the report:",
            )
        elif text.startswith("/delete_last"):
            tx = get_last_transaction(chat_id)
            if tx:
                delete_transaction(tx["_doc_id"])
                ts = datetime.fromisoformat(tx["timestamp"]).astimezone(SGT)
                date_str = ts.strftime("%d %b %Y, %I:%M %p")
                await telegram.send_message(chat_id, f"🗑️ Deleted: <b>{tx['item']}</b>\n💰 ${tx['amount']:.2f} · 🏷️ {tx['category']}\n🕐 {date_str}")
            else:
                await telegram.send_message(chat_id, "No transactions found.")
        elif text.startswith("/delete_today"):
            now = datetime.now(SGT)
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
            txs = get_transactions_with_ids(chat_id, start, end)
            if txs:
                await telegram.send_transaction_keyboard(chat_id, txs, "Tap a transaction to delete it:")
            else:
                await telegram.send_message(chat_id, "No transactions today.")
        elif text.startswith("/delete_past"):
            parts = text.split()
            if len(parts) < 2:
                await telegram.send_message(chat_id, "Please provide a date.\nUsage: <code>/delete_past 130126</code>")
            else:
                date_str = parts[1]
                start = _parse_user_date_or_none(date_str)
                if start is None:
                    await telegram.send_message(chat_id, "Invalid date format. Use <code>DDMMYY</code>, e.g. <code>/delete_past 130126</code>")
                else:
                    date_str = start.strftime("%d/%m/%Y")
                    end = start + timedelta(days=1)
                    txs = get_transactions_with_ids(chat_id, start, end)
                    if txs:
                        await telegram.send_transaction_keyboard(chat_id, txs, f"Transactions on {date_str} — tap to delete:")
                    else:
                        await telegram.send_message(chat_id, f"No transactions on {date_str}.")
        elif text == "/new_category":
            set_user_state(chat_id, f"awaiting_new_cat_name|{datetime.now(SGT).isoformat()}")
            await telegram.send_message(chat_id, "✏️ Type the name of the new category:")
        elif text == "/remove_category":
            categories = get_category_list()
            removable = [c for c in categories if c["name"] != "Other"]
            if not removable:
                await telegram.send_message(chat_id, "No categories to remove.")
            else:
                await telegram.send_remove_category_keyboard(chat_id, removable)
        elif text == "/edit_category":
            categories = get_category_list()
            if not categories:
                await telegram.send_message(chat_id, "No categories to edit.")
            else:
                await telegram.send_edit_category_keyboard(chat_id, categories)
        elif text == "/dashboard_account":
            clear_user_state(chat_id)
            start_session(chat_id, "dashboard_account", "awaiting_username")
            await telegram.send_message(
                chat_id,
                "Choose a dashboard username using 3-32 letters, numbers, dots, underscores, or dashes.",
            )
        elif text == "/set_recurring":
            start_pending_plan(chat_id, "recurring")
            set_user_state(chat_id, "awaiting_recurring_item")
            await telegram.send_message(chat_id, "Send the transaction name for this recurring payment:")
        elif text == "/split_payment":
            start_pending_plan(chat_id, "split_payment")
            set_user_state(chat_id, "awaiting_split_item")
            await telegram.send_message(chat_id, "Send the transaction name for this split payment:")
        elif text == "/list_recurring":
            await send_plan_list(chat_id, "recurring")
        elif text == "/list_split_payment":
            await send_plan_list(chat_id, "split_payment")
        elif text == "/edit_recurring":
            await _start_plan_edit(chat_id, "recurring")
        elif text == "/delete_recurring":
            await _start_plan_delete(chat_id, "recurring")
        elif text == "/delete_split_payment":
            await _start_plan_delete(chat_id, "split_payment")
        return {"ok": True}

    if await _handle_dashboard_account_session(chat_id, text):
        return {"ok": True}

    user_state = get_user_state(chat_id)

    if user_state and user_state.startswith("awaiting_new_cat_name|"):
        ts = user_state[len("awaiting_new_cat_name|"):]
        if _is_expired(ts):
            clear_user_state(chat_id)
            await telegram.send_message(chat_id, "⏰ The /new_category request has expired. Please send /new_category again.")
            return {"ok": True}
        name = text.strip().title()
        existing = [c["name"] for c in get_category_list()]
        if name in existing:
            clear_user_state(chat_id)
            await telegram.send_message(chat_id, f"⚠️ Category <b>{name}</b> already exists.")
            return {"ok": True}
        set_user_state(chat_id, f"awaiting_new_cat_emoji:{name}|{ts}")
        await telegram.send_message(chat_id, f"Now send an emoji for <b>{name}</b>:")
        return {"ok": True}

    if user_state and user_state.startswith("awaiting_new_cat_emoji:"):
        remainder = user_state[len("awaiting_new_cat_emoji:"):]
        if "|" in remainder:
            name, ts = remainder.rsplit("|", 1)
            if _is_expired(ts):
                clear_user_state(chat_id)
                await telegram.send_message(chat_id, "⏰ The /new_category request has expired. Please send /new_category again.")
                return {"ok": True}
        else:
            name = remainder
        add_category_to_list(name, text.strip())
        clear_user_state(chat_id)
        await telegram.send_message(chat_id, f"✅ Category {text.strip()} <b>{name}</b> added!")
        return {"ok": True}

    if user_state == "awaiting_inline_cat_name":
        pending = get_pending(chat_id)
        if pending and _is_expired(pending.get("timestamp", "")):
            delete_pending(chat_id)
            clear_user_state(chat_id)
            await telegram.send_message(chat_id, "⏰ This flow has expired. Please resend the expense to try again.")
            return {"ok": True}
        name = text.strip().title()
        existing = [c["name"] for c in get_category_list()]
        if name in existing:
            clear_user_state(chat_id)
            await handle_custom_category_input(chat_id, name, next(c["emoji"] for c in get_category_list() if c["name"] == name))
            return {"ok": True}
        set_user_state(chat_id, f"awaiting_inline_cat_emoji:{name}")
        await telegram.send_message(chat_id, f"Now send an emoji for <b>{name}</b>:")
        return {"ok": True}

    if user_state and user_state.startswith("awaiting_inline_cat_emoji:"):
        pending = get_pending(chat_id)
        if pending and _is_expired(pending.get("timestamp", "")):
            delete_pending(chat_id)
            clear_user_state(chat_id)
            await telegram.send_message(chat_id, "⏰ This flow has expired. Please resend the expense to try again.")
            return {"ok": True}
        name = user_state[len("awaiting_inline_cat_emoji:"):]
        clear_user_state(chat_id)
        await handle_custom_category_input(chat_id, name, text.strip())
        return {"ok": True}

    if user_state and user_state.startswith("awaiting_change_new_name:"):
        pending_change = get_pending_change(chat_id)
        if pending_change and _is_expired(pending_change.get("timestamp", "")):
            delete_pending_change(chat_id)
            clear_user_state(chat_id)
            await telegram.send_message(chat_id, "⏰ The change category option has expired. Tap 🔄 Change category again to retry.")
            return {"ok": True}
        remainder = user_state[len("awaiting_change_new_name:"):]
        tx_id, item_key = remainder.split(":", 1)
        name = text.strip().title()
        existing = [c["name"] for c in get_category_list()]
        if name in existing:
            update_transaction_category(tx_id, name)
            save_category(item_key, name, confirmed_by_user=True)
            delete_pending_change(chat_id)
            clear_user_state(chat_id)
            await telegram.send_message(chat_id, f"🔄 <b>{item_key}</b> recategorised to <b>{name}</b>")
            return {"ok": True}
        set_user_state(chat_id, f"awaiting_change_new_emoji:{name}:{tx_id}:{item_key}")
        await telegram.send_message(chat_id, f"Now send an emoji for <b>{name}</b>:")
        return {"ok": True}

    if user_state and user_state.startswith("awaiting_change_date:"):
        pending_change = get_pending_change(chat_id)
        if pending_change and _is_expired(pending_change.get("timestamp", "")):
            delete_pending_change(chat_id)
            clear_user_state(chat_id)
            await telegram.send_message(chat_id, "⏰ The change date option has expired. Tap 🗓 Change date again to retry.")
            return {"ok": True}

        tx_id = user_state[len("awaiting_change_date:"):]
        tx = get_transaction_by_id(tx_id)
        if not tx:
            delete_pending_change(chat_id)
            clear_user_state(chat_id)
            await telegram.send_message(chat_id, "⚠️ That transaction no longer exists.")
            return {"ok": True}

        parsed_date = _valid_transaction_date(text)
        if parsed_date is None:
            await telegram.send_message(chat_id, "⚠️ Invalid date format. Use <code>DDMMYY</code>, for example <code>130126</code>.")
            return {"ok": True}

        new_timestamp = build_transaction_timestamp(parsed_date, tx["timestamp"])
        update_transaction_timestamp(tx_id, new_timestamp)
        delete_pending_change(chat_id)
        clear_user_state(chat_id)
        await telegram.send_message(chat_id, f"🗓 Updated <b>{tx['item']}</b> to <b>{parsed_date}</b>.")
        return {"ok": True}

    if user_state == "awaiting_monthly_report_month":
        parsed_month = _parse_month_input_or_none(text)
        if parsed_month is None:
            await telegram.send_message(chat_id, "⚠️ Invalid month format. Use <code>MMYY</code>, for example <code>0126</code>.")
            return {"ok": True}

        year, month = parsed_month
        clear_user_state(chat_id)
        start, end, label = _get_month_window(year, month)
        transactions = get_transactions(chat_id, start, end)
        report = _format_report(label, transactions)
        await telegram.send_message(chat_id, f"<pre>{report}</pre>")
        return {"ok": True}

    if user_state and user_state.startswith("awaiting_change_new_emoji:"):
        pending_change = get_pending_change(chat_id)
        if pending_change and _is_expired(pending_change.get("timestamp", "")):
            delete_pending_change(chat_id)
            clear_user_state(chat_id)
            await telegram.send_message(chat_id, "⏰ The change category option has expired. Tap 🔄 Change category again to retry.")
            return {"ok": True}
        remainder = user_state[len("awaiting_change_new_emoji:"):]
        name, tx_id, item_key = remainder.split(":", 2)
        emoji = text.strip()
        update_transaction_category(tx_id, name)
        save_category(item_key, name, confirmed_by_user=True)
        add_category_to_list(name, emoji)
        delete_pending_change(chat_id)
        clear_user_state(chat_id)
        await telegram.send_message(chat_id, f"🔄 <b>{item_key}</b> recategorised to {emoji} <b>{name}</b> (new category saved)")
        return {"ok": True}

    if user_state and user_state.startswith("awaiting_edit_cat_emoji:"):
        remainder = user_state[len("awaiting_edit_cat_emoji:"):]
        if "|" in remainder:
            category_name, ts = remainder.rsplit("|", 1)
            if _is_expired(ts):
                clear_user_state(chat_id)
                await telegram.send_message(chat_id, "⏰ The /edit_category request has expired. Please send /edit_category again.")
                return {"ok": True}
        else:
            category_name = remainder
        ok = update_category_emoji(category_name, text.strip())
        clear_user_state(chat_id)
        await telegram.send_message(chat_id, f"✅ Updated emoji for <b>{category_name}</b> → {text.strip()}" if ok else f"⚠️ Category <b>{category_name}</b> not found.")
        return {"ok": True}

    if user_state and user_state.startswith("awaiting_edit_cat_name:"):
        remainder = user_state[len("awaiting_edit_cat_name:"):]
        if "|" in remainder:
            category_name, ts = remainder.rsplit("|", 1)
            if _is_expired(ts):
                clear_user_state(chat_id)
                await telegram.send_message(chat_id, "⏰ The /edit_category request has expired. Please send /edit_category again.")
                return {"ok": True}
        else:
            category_name = remainder
        new_name = text.strip().title()
        if category_name == "Other":
            clear_user_state(chat_id)
            await telegram.send_message(chat_id, "⚠️ The <b>Other</b> category cannot be renamed.")
            return {"ok": True}
        if not new_name:
            clear_user_state(chat_id)
            await telegram.send_message(chat_id, "⚠️ Name cannot be empty.")
            return {"ok": True}
        existing = [c["name"] for c in get_category_list()]
        if new_name in existing:
            clear_user_state(chat_id)
            await telegram.send_message(chat_id, f"⚠️ Category <b>{new_name}</b> already exists.")
            return {"ok": True}
        ok, tx_count, map_count = rename_category(category_name, new_name)
        clear_user_state(chat_id)
        if ok:
            msg = f"✅ Renamed <b>{category_name}</b> → <b>{new_name}</b>"
            if tx_count or map_count:
                msg += f"\n🔄 Updated {tx_count} transaction(s) and {map_count} item mapping(s)."
            await telegram.send_message(chat_id, msg)
        else:
            await telegram.send_message(chat_id, f"⚠️ Could not rename <b>{category_name}</b>.")
        return {"ok": True}

    if user_state and user_state.startswith("awaiting_edit_cat_order:"):
        remainder = user_state[len("awaiting_edit_cat_order:"):]
        if "|" in remainder:
            category_name, ts = remainder.rsplit("|", 1)
            if _is_expired(ts):
                clear_user_state(chat_id)
                await telegram.send_message(chat_id, "⏰ The /edit_category request has expired. Please send /edit_category again.")
                return {"ok": True}
        else:
            category_name = remainder
        if category_name == "Other":
            clear_user_state(chat_id)
            await telegram.send_message(chat_id, "⚠️ The <b>Other</b> category's order cannot be changed.")
            return {"ok": True}
        order = _valid_months(text)
        non_other = [c for c in get_category_list() if c["name"] != "Other"]
        max_order = len(non_other)
        if order is None or order < 1 or order > max_order:
            clear_user_state(chat_id)
            await telegram.send_message(chat_id, f"⚠️ Order must be between <b>1</b> and <b>{max_order}</b>. Try /edit_category again.")
            return {"ok": True}
        ok = update_category_order(category_name, order)
        clear_user_state(chat_id)
        await telegram.send_message(chat_id, f"✅ Updated order for <b>{category_name}</b> → {order}" if ok else f"⚠️ Category <b>{category_name}</b> not found.")
        return {"ok": True}

    if user_state == "awaiting_recurring_item":
        update_pending_plan(chat_id, item=text.strip())
        set_user_state(chat_id, "awaiting_plan_category")
        await telegram.send_category_keyboard(chat_id, text.strip(), 0)
        return {"ok": True}

    if user_state == "awaiting_split_item":
        update_pending_plan(chat_id, item=text.strip())
        set_user_state(chat_id, "awaiting_plan_category")
        await telegram.send_category_keyboard(chat_id, text.strip(), 0)
        return {"ok": True}

    if user_state == "awaiting_recurring_amount":
        amount = _valid_amount(text)
        if amount is None:
            await telegram.send_message(chat_id, "⚠️ Amount must be a positive number.")
            return {"ok": True}
        update_pending_plan(chat_id, amount=amount)
        set_user_state(chat_id, "awaiting_recurring_day")
        await telegram.send_message(chat_id, "Great, I will add it to the expense this month. Additionally, which day of the month should it charge from the next month onwards? Send a number from 1 to 31.")
        return {"ok": True}

    if user_state == "awaiting_recurring_day":
        day = _valid_day(text)
        if day is None:
            await telegram.send_message(chat_id, "⚠️ Day must be a number from 1 to 31.")
            return {"ok": True}
        update_pending_plan(chat_id, day_of_month=day)
        pending = get_pending_plan(chat_id)
        await create_plan_and_post_first_charge(chat_id, pending)
        return {"ok": True}

    if user_state == "awaiting_split_total":
        amount = _valid_amount(text)
        if amount is None:
            await telegram.send_message(chat_id, "⚠️ Amount must be a positive number.")
            return {"ok": True}
        update_pending_plan(chat_id, total_amount=amount)
        set_user_state(chat_id, "awaiting_split_day")
        await telegram.send_message(chat_id, "Which day of the month should each monthly charge post? Send a number from 1 to 31.")
        return {"ok": True}

    if user_state == "awaiting_split_day":
        day = _valid_day(text)
        if day is None:
            await telegram.send_message(chat_id, "⚠️ Day must be a number from 1 to 31.")
            return {"ok": True}
        update_pending_plan(chat_id, day_of_month=day)
        set_user_state(chat_id, "awaiting_split_count")
        await telegram.send_message(chat_id, "How many months should this be split across?")
        return {"ok": True}

    if user_state == "awaiting_split_count":
        months = _valid_months(text)
        if months is None:
            await telegram.send_message(chat_id, "⚠️ Months must be a positive integer.")
            return {"ok": True}
        update_pending_plan(chat_id, installment_count=months)
        pending = get_pending_plan(chat_id)
        await create_plan_and_post_first_charge(chat_id, pending)
        return {"ok": True}

    if user_state == "awaiting_plan_new_cat_name":
        pending = get_pending_plan(chat_id)
        if pending_plan_expired(pending):
            delete_pending_plan(chat_id)
            clear_user_state(chat_id)
            await telegram.send_message(chat_id, "⏰ This plan flow has expired. Start the command again.")
            return {"ok": True}
        name = text.strip().title()
        existing = [c["name"] for c in get_category_list()]
        if name in existing:
            update_pending_plan(chat_id, category=name)
            if pending.get("edit_field") == "category":
                update_pending_plan(chat_id, edit_value=name)
                set_user_state(chat_id, "awaiting_plan_edit_rewrite")
                await _send_plan_rewrite_prompt(chat_id)
            else:
                await _prompt_after_plan_category(chat_id, {**pending, "category": name})
            return {"ok": True}
        update_pending_plan(chat_id, category=name)
        set_user_state(chat_id, f"awaiting_plan_new_cat_emoji:{name}")
        await telegram.send_message(chat_id, f"Now send an emoji for <b>{name}</b>:")
        return {"ok": True}

    if user_state and user_state.startswith("awaiting_plan_new_cat_emoji:"):
        pending = get_pending_plan(chat_id)
        if pending_plan_expired(pending):
            delete_pending_plan(chat_id)
            clear_user_state(chat_id)
            await telegram.send_message(chat_id, "⏰ This plan flow has expired. Start the command again.")
            return {"ok": True}
        name = user_state[len("awaiting_plan_new_cat_emoji:"):]
        emoji = text.strip()
        add_category_to_list(name, emoji)
        if pending.get("edit_field") == "category":
            update_pending_plan(chat_id, edit_value=name)
            set_user_state(chat_id, "awaiting_plan_edit_rewrite")
            await _send_plan_rewrite_prompt(chat_id)
        else:
            await _prompt_after_plan_category(chat_id, {**pending, "category": name})
        return {"ok": True}

    if user_state in {"awaiting_plan_edit_item", "awaiting_plan_edit_amount", "awaiting_plan_edit_day", "awaiting_plan_edit_months"}:
        pending = get_pending_plan(chat_id)
        if pending_plan_expired(pending):
            delete_pending_plan(chat_id)
            clear_user_state(chat_id)
            await telegram.send_message(chat_id, "⏰ This plan edit has expired. Start the edit command again.")
            return {"ok": True}
        raw_value = text.strip()
        if user_state == "awaiting_plan_edit_amount":
            amount = _valid_amount(raw_value)
            if amount is None:
                await telegram.send_message(chat_id, "⚠️ Amount must be a positive number.")
                return {"ok": True}
            raw_value = str(amount)
        elif user_state == "awaiting_plan_edit_day":
            day = _valid_day(raw_value)
            if day is None:
                await telegram.send_message(chat_id, "⚠️ Day must be a number from 1 to 31.")
                return {"ok": True}
            raw_value = str(day)
        elif user_state == "awaiting_plan_edit_months":
            months = _valid_months(raw_value)
            if months is None:
                await telegram.send_message(chat_id, "⚠️ Months must be a positive integer.")
                return {"ok": True}
            raw_value = str(months)
        update_pending_plan(chat_id, edit_value=raw_value)
        set_user_state(chat_id, "awaiting_plan_edit_rewrite")
        await _send_plan_rewrite_prompt(chat_id)
        return {"ok": True}

    parsed = parse_expense(text)
    if parsed is None:
        await telegram.send_message(chat_id, "🤔 I couldn't understand that. Try something like:\n<code>Coffee $10</code>\n<code>Grab 15.50</code>\n<code>Coffee $10 130126</code>")
        return {"ok": True}

    await handle_expense(
        chat_id,
        parsed.item,
        parsed.amount,
        transaction_date=parsed.transaction_date,
    )
    return {"ok": True}
