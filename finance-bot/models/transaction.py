from pydantic import BaseModel, Field
from typing import Optional


class Transaction(BaseModel):
    id: Optional[str] = None
    item: str
    amount: float
    category: str
    timestamp: str  # ISO 8601 with timezone offset
    chat_id: int
    source_type: str = "manual"
    source_plan_id: Optional[str] = None
    occurrence_key: Optional[str] = None
    auto_generated: bool = False


class Inflow(BaseModel):
    id: Optional[str] = None
    item: str
    amount: float
    timestamp: str  # ISO 8601 with timezone offset — when the income happened
    chat_id: int
    created_at: str
    goal_id: Optional[str] = None
    project_id: Optional[str] = None


class Goal(BaseModel):
    id: Optional[str] = None
    chat_id: int
    name: str
    target_amount: float
    created_at: str
    emoji: str = "🎯"
    order: int = 0


class Project(BaseModel):
    """A long-term savings project: like a Goal but cumulative (never resets)
    and carrying a fixed deadline date."""

    id: Optional[str] = None
    chat_id: int
    name: str
    target_amount: float
    deadline: str  # ISO 8601 date — when the project should be funded by
    created_at: str
    emoji: str = "🚀"
    order: int = 0


class PendingTransaction(BaseModel):
    item: str
    amount: float
    chat_id: int
    timestamp: str
    created_at: str
    date_was_explicit: bool = False


class CategoryMapping(BaseModel):
    item_key: str
    category: str
    confirmed_by_user: bool = False
    created_at: str


class ParsedExpense(BaseModel):
    item: str
    amount: float
    transaction_date: Optional[str] = None


class PaymentPlan(BaseModel):
    id: Optional[str] = None
    chat_id: int
    plan_type: str
    item: str
    category: str
    day_of_month: int
    status: str = "active"
    start_year: int
    start_month: int
    next_due_date: str
    created_at: str
    amount: Optional[float] = None
    total_amount: Optional[float] = None
    installment_count: Optional[int] = None
    current_installment_number: int = 0
    base_installment_amount: Optional[float] = None
    final_installment_amount: Optional[float] = None


class PendingPlan(BaseModel):
    chat_id: int
    plan_type: str
    created_at: str
    item: Optional[str] = None
    category: Optional[str] = None
    amount: Optional[float] = None
    total_amount: Optional[float] = None
    day_of_month: Optional[int] = None
    installment_count: Optional[int] = None
    start_date: Optional[str] = None  # ISO date — split flow start date
    number_of_months: Optional[int] = None  # split flow: months to spread across
    selected_plan_id: Optional[str] = None
    edit_field: Optional[str] = None
    edit_value: Optional[str] = None


class FlowSession(BaseModel):
    chat_id: int
    flow_type: str
    step: str
    payload: dict = Field(default_factory=dict)
    created_at: str
    expires_at: str
