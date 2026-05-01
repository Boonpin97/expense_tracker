import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if "pydantic" not in sys.modules:
    pydantic_stub = types.ModuleType("pydantic")

    class BaseModel:
        def __init__(self, **kwargs):
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

from services.payment_plans import clamp_day, compute_split_amounts, compute_next_due_date
from services.plan_manager import process_due_plans

SGT = timezone(timedelta(hours=8))


class PaymentPlanHelperTests(unittest.TestCase):
    def test_clamp_day_uses_month_end(self):
        self.assertEqual(clamp_day(2026, 2, 31), 28)
        self.assertEqual(clamp_day(2024, 2, 31), 29)
        self.assertEqual(clamp_day(2026, 4, 31), 30)

    def test_split_amounts_put_remainder_in_last_installment(self):
        base, final_amount = compute_split_amounts(100.0, 3)
        self.assertEqual(base, 33.33)
        self.assertEqual(final_amount, 33.34)

    def test_next_due_date_completes_split_plan(self):
        plan = {
            "plan_type": "split_payment",
            "start_year": 2026,
            "start_month": 5,
            "day_of_month": 31,
            "installment_count": 4,
            "current_installment_number": 4,
            "base_installment_amount": 25.0,
            "final_installment_amount": 25.0,
        }
        self.assertIsNone(compute_next_due_date(plan))


class ProcessDuePlansTests(unittest.IsolatedAsyncioTestCase):
    async def test_process_due_plans_posts_once(self):
        due_at = datetime(2026, 6, 30, 0, 0, 0, tzinfo=SGT)
        plan = {
            "id": "plan-1",
            "chat_id": 123,
            "plan_type": "recurring",
            "item": "Netflix",
            "category": "Entertainment",
            "day_of_month": 31,
            "status": "active",
            "start_year": 2026,
            "start_month": 5,
            "next_due_date": due_at.isoformat(),
            "created_at": due_at.isoformat(),
            "amount": 25.0,
            "current_installment_number": 1,
        }
        with patch("services.plan_manager.firestore.list_due_payment_plans", return_value=[plan]), \
             patch("services.plan_manager.firestore.find_transaction_by_plan_occurrence", return_value=None), \
             patch("services.plan_manager.firestore.save_transaction"), \
             patch("services.plan_manager.firestore.update_payment_plan"), \
             patch("services.plan_manager.telegram.send_transaction_confirmation", new=AsyncMock()), \
             patch("services.plan_manager._check_budget_exceeded", new=AsyncMock()):
            processed = await process_due_plans(due_at)
        self.assertEqual(processed, 1)

    async def test_process_due_plans_skips_duplicate_occurrence(self):
        due_at = datetime(2026, 6, 30, 0, 0, 0, tzinfo=SGT)
        plan = {
            "id": "plan-1",
            "chat_id": 123,
            "plan_type": "recurring",
            "item": "Netflix",
            "category": "Entertainment",
            "day_of_month": 31,
            "status": "active",
            "start_year": 2026,
            "start_month": 5,
            "next_due_date": due_at.isoformat(),
            "created_at": due_at.isoformat(),
            "amount": 25.0,
            "current_installment_number": 1,
        }
        with patch("services.plan_manager.firestore.list_due_payment_plans", return_value=[plan]), \
             patch("services.plan_manager.firestore.find_transaction_by_plan_occurrence", return_value={"_doc_id": "tx-1"}), \
             patch("services.plan_manager.firestore.save_transaction"), \
             patch("services.plan_manager.firestore.update_payment_plan"), \
             patch("services.plan_manager.telegram.send_transaction_confirmation", new=AsyncMock()), \
             patch("services.plan_manager._check_budget_exceeded", new=AsyncMock()):
            processed = await process_due_plans(due_at)
        self.assertEqual(processed, 0)


if __name__ == "__main__":
    unittest.main()
