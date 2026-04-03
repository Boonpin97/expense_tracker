import re
from typing import Optional

from models.transaction import ParsedExpense


def parse_expense(text: str) -> Optional[ParsedExpense]:
    """Parse freeform text like 'Coffee $10', 'Grab $15.50', 'electricity bill 120'.

    Returns a ParsedExpense with item and amount, or None if unparseable.
    """
    text = text.strip()
    if not text:
        return None

    # Pattern 1: "Item $Amount" or "Item $Amount" (dollar sign before amount)
    match = re.match(r"^(.+?)\s+\$\s*(\d+(?:\.\d{1,2})?)$", text)
    if match:
        item = match.group(1).strip()
        amount = float(match.group(2))
        return ParsedExpense(item=item, amount=amount)

    # Pattern 2: "$Amount Item" (dollar sign before amount, item after)
    match = re.match(r"^\$\s*(\d+(?:\.\d{1,2})?)\s+(.+)$", text)
    if match:
        amount = float(match.group(1))
        item = match.group(2).strip()
        return ParsedExpense(item=item, amount=amount)

    # Pattern 3: "Item Amount" (no dollar sign, amount at end)
    match = re.match(r"^(.+?)\s+(\d+(?:\.\d{1,2})?)$", text)
    if match:
        item = match.group(1).strip()
        amount = float(match.group(2))
        return ParsedExpense(item=item, amount=amount)

    return None
