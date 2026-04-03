from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class Transaction(BaseModel):
    id: Optional[str] = None
    item: str
    amount: float
    category: str
    timestamp: str  # ISO 8601 with timezone offset
    chat_id: int


class PendingTransaction(BaseModel):
    item: str
    amount: float
    chat_id: int
    timestamp: str


class CategoryMapping(BaseModel):
    item_key: str
    category: str
    confirmed_by_user: bool = False
    created_at: str


class ParsedExpense(BaseModel):
    item: str
    amount: float
