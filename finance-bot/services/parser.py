import re
from datetime import datetime
from typing import Optional

from models.transaction import ParsedExpense

DATE_PATTERN = r"\d{6}"


def parse_transaction_date(text: str) -> Optional[str]:
    text = text.strip()
    if not re.fullmatch(DATE_PATTERN, text):
        return None
    try:
        parsed = datetime.strptime(text, "%d%m%y")
    except ValueError:
        return None
    return parsed.strftime("%Y-%m-%d")


def parse_expense(text: str) -> Optional[ParsedExpense]:
    """Parse freeform text like 'Coffee $10', 'Grab $15.50', 'Coffee $10 130126'.

    Returns a ParsedExpense with item, amount, and an optional transaction_date.
    """
    text = text.strip()
    if not text:
        return None

    transaction_date = None
    match = re.match(rf"^(.*\S)\s+({DATE_PATTERN})$", text)
    if match:
        parsed_date = parse_transaction_date(match.group(2))
        if parsed_date is None:
            return None
        text = match.group(1).strip()
        transaction_date = parsed_date

    # Pattern 1: "Item $Amount" or "Item $Amount" (dollar sign before amount)
    match = re.match(r"^(.+?)\s+\$\s*(\d+(?:\.\d{1,2})?)$", text)
    if match:
        item = match.group(1).strip()
        amount = float(match.group(2))
        return ParsedExpense(item=item, amount=amount, transaction_date=transaction_date)

    # Pattern 2: "$Amount Item" (dollar sign before amount, item after)
    match = re.match(r"^\$\s*(\d+(?:\.\d{1,2})?)\s+(.+)$", text)
    if match:
        amount = float(match.group(1))
        item = match.group(2).strip()
        return ParsedExpense(item=item, amount=amount, transaction_date=transaction_date)

    # Pattern 3: "Item Amount" (no dollar sign, amount at end)
    match = re.match(r"^(.+?)\s+(\d+(?:\.\d{1,2})?)$", text)
    if match:
        item = match.group(1).strip()
        amount = float(match.group(2))
        return ParsedExpense(item=item, amount=amount, transaction_date=transaction_date)

    return None
