import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "pydantic" not in sys.modules:
    pydantic_stub = types.ModuleType("pydantic")

    class BaseModel:
        def __init__(self, **kwargs):
            annotations = getattr(self.__class__, "__annotations__", {})
            for key in annotations:
                if hasattr(self.__class__, key):
                    setattr(self, key, getattr(self.__class__, key))
            for key, value in kwargs.items():
                setattr(self, key, value)

        def model_dump(self, exclude_none: bool = False):
            data = dict(self.__dict__)
            if exclude_none:
                data = {k: v for k, v in data.items() if v is not None}
            return data

    def Field(default=None, **_kwargs):
        return default

    pydantic_stub.BaseModel = BaseModel
    pydantic_stub.Field = Field
    sys.modules["pydantic"] = pydantic_stub

if "google.cloud" not in sys.modules:
    google_mod = types.ModuleType("google")
    cloud_mod = types.ModuleType("google.cloud")
    firestore_mod = types.ModuleType("google.cloud.firestore")

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

    class DummyQuery:
        DESCENDING = "DESCENDING"

    firestore_mod.Client = DummyClient
    firestore_mod.Query = DummyQuery
    cloud_mod.firestore = firestore_mod
    google_mod.cloud = cloud_mod
    sys.modules["google"] = google_mod
    sys.modules["google.cloud"] = cloud_mod
    sys.modules["google.cloud.firestore"] = firestore_mod

if "httpx" not in sys.modules:
    httpx_stub = types.ModuleType("httpx")

    class Timeout:
        def __init__(self, *args, **kwargs):
            pass

    class AsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            class Response:
                def json(self):
                    return {}

            return Response()

    httpx_stub.Timeout = Timeout
    httpx_stub.AsyncClient = AsyncClient
    sys.modules["httpx"] = httpx_stub

from services.categoriser import build_transaction_timestamp
from services.parser import parse_expense, parse_transaction_date


class TransactionDateParsingTests(unittest.TestCase):
    def test_parse_expense_without_date(self):
        parsed = parse_expense("Coffee $10")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.item, "Coffee")
        self.assertEqual(parsed.amount, 10.0)
        self.assertIsNone(parsed.transaction_date)

    def test_parse_expense_with_trailing_date(self):
        parsed = parse_expense("Coffee $10 130126")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.item, "Coffee")
        self.assertEqual(parsed.amount, 10.0)
        self.assertEqual(parsed.transaction_date, "2026-01-13")

    def test_parse_expense_rejects_invalid_trailing_date(self):
        self.assertIsNone(parse_expense("Coffee $10 310226"))

    def test_parse_transaction_date_requires_ddmmyy_format(self):
        self.assertEqual(parse_transaction_date("130126"), "2026-01-13")
        self.assertIsNone(parse_transaction_date("03-05-2026"))


class TransactionTimestampBuilderTests(unittest.TestCase):
    def test_build_transaction_timestamp_uses_base_time_for_changed_date(self):
        base_timestamp = "2026-05-03T14:15:16+08:00"
        new_timestamp = build_transaction_timestamp("2026-05-01", base_timestamp)
        self.assertEqual(new_timestamp, "2026-05-01T14:15:16+08:00")


if __name__ == "__main__":
    unittest.main()
