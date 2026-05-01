import calendar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


SGT = timezone(timedelta(hours=8))


@dataclass
class PlanOccurrence:
    due_date: datetime
    occurrence_key: str
    installment_number: int
    amount: float
    is_final: bool


def clamp_day(year: int, month: int, day_of_month: int) -> int:
    return min(day_of_month, calendar.monthrange(year, month)[1])


def month_due_date(year: int, month: int, day_of_month: int) -> datetime:
    day = clamp_day(year, month, day_of_month)
    return datetime(year, month, day, tzinfo=SGT)


def next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1


def add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    total = (year * 12 + (month - 1)) + delta
    return total // 12, total % 12 + 1


def compute_split_amounts(total_amount: float, installment_count: int) -> tuple[float, float]:
    base = round(total_amount / installment_count, 2)
    final_amount = round(total_amount - (base * (installment_count - 1)), 2)
    return base, final_amount


def next_due_after(start_year: int, start_month: int, day_of_month: int, months_after: int) -> datetime:
    year, month = add_months(start_year, start_month, months_after)
    return month_due_date(year, month, day_of_month)


def plan_occurrence_for_index(plan: dict, index: int) -> PlanOccurrence:
    due_date = next_due_after(plan["start_year"], plan["start_month"], plan["day_of_month"], index)
    occurrence_key = f"{due_date.year:04d}-{due_date.month:02d}"
    if plan["plan_type"] == "split_payment":
        base = float(plan["base_installment_amount"])
        final_amount = float(plan["final_installment_amount"])
        total = int(plan["installment_count"])
        is_final = index + 1 >= total
        amount = final_amount if is_final else base
        installment_number = index + 1
    else:
        amount = float(plan["amount"])
        installment_number = 1
        is_final = False
    return PlanOccurrence(
        due_date=due_date,
        occurrence_key=occurrence_key,
        installment_number=installment_number,
        amount=amount,
        is_final=is_final,
    )


def occurrence_label(plan: dict, occurrence: PlanOccurrence) -> str:
    if plan["plan_type"] == "split_payment":
        total = int(plan["installment_count"])
        return f"Auto: installment {occurrence.installment_number}/{total}"
    return "Auto: recurring"


def compute_next_due_date(plan: dict) -> datetime | None:
    if plan["plan_type"] == "split_payment":
        posted = int(plan.get("current_installment_number", 0))
        total = int(plan["installment_count"])
        if posted >= total:
            return None
        return plan_occurrence_for_index(plan, posted).due_date
    posted = int(plan.get("current_installment_number", 0))
    return plan_occurrence_for_index(plan, posted).due_date


def due_today(plan: dict, today: datetime) -> bool:
    due = datetime.fromisoformat(plan["next_due_date"]).astimezone(SGT)
    return due.date() == today.date()


def plan_display_line(plan: dict) -> str:
    due = datetime.fromisoformat(plan["next_due_date"]).astimezone(SGT)
    if plan["plan_type"] == "split_payment":
        progress = f"{plan.get('current_installment_number', 0)}/{plan['installment_count']}"
        amount_text = f"${plan['total_amount']:.2f} total"
        extra = f"instalments {progress}"
    else:
        amount_text = f"${plan['amount']:.2f}/month"
        extra = "open-ended"
    return (
        f"<b>{plan['item']}</b> · {plan['category']}\n"
        f"{amount_text} · Day {plan['day_of_month']} · next {due.strftime('%Y-%m-%d')} · {extra}"
    )
