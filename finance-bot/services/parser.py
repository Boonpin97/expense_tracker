import ast
import re
from datetime import datetime
from typing import Optional

from models.transaction import ParsedExpense

DATE_PATTERN = r"\d{6}"
AMOUNT_TOKEN_PATTERN = r"[\d\.\+\-\*\/\(\)xX\s]+"


def _evaluate_amount_expression(text: str) -> Optional[float]:
    normalized = text.strip().replace("X", "*").replace("x", "*")
    if not normalized or not re.fullmatch(AMOUNT_TOKEN_PATTERN, normalized):
        return None

    try:
        expression = ast.parse(normalized, mode="eval")
    except SyntaxError:
        return None

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = _eval(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left = _eval(node.left)
            right = _eval(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if right == 0:
                raise ZeroDivisionError
            return left / right
        raise ValueError("Unsupported expression")

    try:
        value = _eval(expression)
    except (ValueError, ZeroDivisionError):
        return None

    if value < 0:
        return None
    return float(value)


def _whitespace_boundaries(text: str) -> list[int]:
    return [match.start() for match in re.finditer(r"\s+", text)]


def _parse_item_then_amount(text: str, amount_prefix: str = "") -> Optional[tuple[str, float]]:
    for boundary in _whitespace_boundaries(text):
        item = text[:boundary].strip()
        amount_text = text[boundary:].strip()
        if not item or not amount_text.startswith(amount_prefix):
            continue
        amount = _evaluate_amount_expression(amount_text[len(amount_prefix):])
        if amount is not None:
            return item, amount
    return None


def _parse_amount_then_item(text: str, amount_prefix: str = "") -> Optional[tuple[str, float]]:
    if amount_prefix and not text.startswith(amount_prefix):
        return None

    stripped = text[len(amount_prefix):].strip() if amount_prefix else text
    for boundary in reversed(_whitespace_boundaries(stripped)):
        amount_text = stripped[:boundary].strip()
        item = stripped[boundary:].strip()
        if not amount_text or not item:
            continue
        amount = _evaluate_amount_expression(amount_text)
        if amount is not None:
            return item, amount
    return None


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
    """Parse freeform text like 'Coffee $10', 'Grab $15.50', 'Coffee 10+20*2 130126'.

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

    parsed = _parse_item_then_amount(text, amount_prefix="$")
    if parsed:
        item, amount = parsed
        return ParsedExpense(item=item, amount=amount, transaction_date=transaction_date)

    parsed = _parse_amount_then_item(text, amount_prefix="$")
    if parsed:
        item, amount = parsed
        return ParsedExpense(item=item, amount=amount, transaction_date=transaction_date)

    parsed = _parse_item_then_amount(text)
    if parsed:
        item, amount = parsed
        return ParsedExpense(item=item, amount=amount, transaction_date=transaction_date)

    return None
