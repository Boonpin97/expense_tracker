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
from services.plan_manager import (
    create_plan_and_post_first_charge,
    process_due_plans,
    rewrite_plan_history,
    post_next_occurrence,
)
from services import telegram, firestore

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

    def test_plan_keyboards_add_expiry_timestamp(self):
        captured = {}

        class FakeResponse:
            def json(self):
                return {}

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, *_args, **kwargs):
                captured.update(kwargs["json"])
                return FakeResponse()

        original_client = telegram.httpx.AsyncClient
        telegram.httpx.AsyncClient = FakeAsyncClient
        try:
            import asyncio

            asyncio.run(
                telegram.send_plan_keyboard(
                    123,
                    [{"id": "plan-1", "plan_type": "recurring", "item": "Netflix"}],
                    "editrecurring",
                    "Select a plan:",
                )
            )
            callback_data = captured["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
            self.assertRegex(callback_data, r"^editrecurring:plan-1\|")

            asyncio.run(
                telegram.send_plan_keyboard(
                    123,
                    [{"id": "plan-2", "plan_type": "split_payment", "item": "Sofa"}],
                    "editsplit",
                    "Select a plan:",
                )
            )
            split_callback = captured["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
            self.assertRegex(split_callback, r"^editsplit:plan-2\|")

            asyncio.run(telegram.send_plan_delete_mode_keyboard(123, "plan-1", "Delete?"))
            delete_buttons = captured["reply_markup"]["inline_keyboard"][0]
            self.assertEqual(delete_buttons[0]["callback_data"], "plandelmode:future:plan-1")
            self.assertEqual(delete_buttons[1]["callback_data"], "plandelmode:all:plan-1")

            # Confirm callback_data fits Telegram's 64-byte limit with a real 20-char Firestore ID.
            firestore_id = "a" * 20
            asyncio.run(telegram.send_plan_delete_mode_keyboard(123, firestore_id, "Delete?"))
            for button in captured["reply_markup"]["inline_keyboard"][0]:
                self.assertLessEqual(len(button["callback_data"].encode("utf-8")), 64)
            asyncio.run(telegram.send_split_plan_delete_confirm_keyboard(123, firestore_id, "Delete?"))
            confirm_button = captured["reply_markup"]["inline_keyboard"][0][0]
            self.assertLessEqual(len(confirm_button["callback_data"].encode("utf-8")), 64)
            self.assertEqual(confirm_button["callback_data"], f"plandelmode:all:{firestore_id}")

            # Plan-listing keyboards (with timestamp suffix) must also stay under 64 bytes
            # for the longest prefix variant ("editrecurring:" = 14 chars).
            for action in ("editrecurring", "delrecurring", "editsplit", "delsplit"):
                asyncio.run(
                    telegram.send_plan_keyboard(
                        123,
                        [{"id": firestore_id, "plan_type": "recurring", "item": "Netflix"}],
                        action,
                        "Select a plan:",
                    )
                )
                cb = captured["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
                self.assertLessEqual(
                    len(cb.encode("utf-8")), 64,
                    msg=f"{action} callback_data too long: {cb!r} ({len(cb)} bytes)",
                )
        finally:
            telegram.httpx.AsyncClient = original_client


class ProcessDuePlansTests(unittest.IsolatedAsyncioTestCase):
    async def test_post_next_occurrence_marks_final_split_installment_completed(self):
        due_at = datetime(2026, 6, 30, 0, 0, 0, tzinfo=SGT)
        plan = {
            "id": "plan-1",
            "chat_id": 123,
            "plan_type": "split_payment",
            "item": "Phone",
            "category": "Shopping",
            "day_of_month": 30,
            "status": "active",
            "start_year": 2026,
            "start_month": 5,
            "next_due_date": due_at.isoformat(),
            "created_at": due_at.isoformat(),
            "total_amount": 100.0,
            "installment_count": 2,
            "current_installment_number": 1,
            "base_installment_amount": 50.0,
            "final_installment_amount": 50.0,
        }
        with patch("services.plan_manager.firestore.find_transaction_by_plan_occurrence", return_value=None), \
             patch("services.plan_manager.firestore.save_transaction") as mock_save_tx, \
             patch("services.plan_manager.firestore.update_payment_plan") as mock_update_plan, \
             patch("services.plan_manager.telegram.send_transaction_confirmation", new=AsyncMock()) as mock_confirm, \
             patch("services.plan_manager._check_budget_exceeded", new=AsyncMock()):
            posted = await post_next_occurrence(plan, timestamp=due_at)

        self.assertTrue(posted)
        self.assertEqual(mock_save_tx.call_args.args[0].occurrence_key, "2026-06")
        mock_update_plan.assert_called_once_with(
            "plan-1",
            current_installment_number=2,
            next_due_date="",
            status="completed",
        )
        self.assertIn("installment 2/2", mock_confirm.call_args.kwargs["note"])

    async def test_post_next_occurrence_reconciles_when_charge_already_exists(self):
        # Inconsistent state: the occurrence's transaction exists but the plan
        # counter was never advanced. post_next_occurrence must advance the plan
        # forward (not re-charge, not bail), so it stops being perpetually "due".
        due_at = datetime(2026, 6, 1, 0, 0, 0, tzinfo=SGT)
        plan = {
            "id": "plan-1",
            "chat_id": 123,
            "plan_type": "recurring",
            "item": "Phone Bill",
            "category": "Other",
            "day_of_month": 1,
            "status": "active",
            "start_year": 2026,
            "start_month": 5,
            "next_due_date": due_at.isoformat(),
            "created_at": "2026-05-01T00:00:00+08:00",
            "amount": 18.33,
            "current_installment_number": 1,
        }
        with patch("services.plan_manager.firestore.find_transaction_by_plan_occurrence", return_value={"_doc_id": "tx-existing"}), \
             patch("services.plan_manager.firestore.save_transaction") as mock_save_tx, \
             patch("services.plan_manager.firestore.update_payment_plan") as mock_update_plan, \
             patch("services.plan_manager.telegram.send_transaction_confirmation", new=AsyncMock()) as mock_confirm, \
             patch("services.plan_manager._check_budget_exceeded", new=AsyncMock()):
            posted = await post_next_occurrence(plan, timestamp=due_at)

        self.assertFalse(posted)
        mock_save_tx.assert_not_called()
        mock_confirm.assert_not_called()
        mock_update_plan.assert_called_once_with(
            "plan-1",
            current_installment_number=2,
            next_due_date="2026-07-01T00:00:00+08:00",
            status="active",
        )

    async def test_post_next_occurrence_skips_inactive_plan(self):
        plan = {"id": "plan-1", "status": "completed"}
        with patch("services.plan_manager.firestore.save_transaction") as mock_save_tx:
            posted = await post_next_occurrence(plan)
        self.assertFalse(posted)
        mock_save_tx.assert_not_called()

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

    async def test_rewrite_split_plan_after_shortening_months_amends_past(self):
        # User edits a $90/3-month split to $90/2-month with rewrite.
        # Past $30 charge becomes $45; subsequent due date is now the final installment.
        edited_plan = {
            "id": "plan-1",
            "chat_id": 123,
            "plan_type": "split_payment",
            "item": "Sofa",
            "category": "Home",
            "day_of_month": 15,
            "status": "active",
            "start_year": 2026,
            "start_month": 5,
            "next_due_date": datetime(2026, 6, 15, tzinfo=SGT).isoformat(),
            "created_at": datetime(2026, 5, 15, tzinfo=SGT).isoformat(),
            "total_amount": 90.0,
            "installment_count": 2,
            "current_installment_number": 1,
            "base_installment_amount": 45.0,
            "final_installment_amount": 45.0,
        }
        saved_transactions = []
        update_kwargs = {}

        def capture_save_tx(tx):
            saved_transactions.append(tx)

        def capture_update(_plan_id, **kwargs):
            update_kwargs.update(kwargs)

        class FakeDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 5, 20, 12, 0, 0, tzinfo=tz or SGT)

        with patch("services.plan_manager.firestore.get_payment_plan", return_value=edited_plan), \
             patch("services.plan_manager.firestore.delete_transactions_for_plan", return_value=1), \
             patch("services.plan_manager.firestore.save_transaction", side_effect=capture_save_tx), \
             patch("services.plan_manager.firestore.update_payment_plan", side_effect=capture_update), \
             patch("services.plan_manager.datetime", FakeDateTime):
            rewritten = await rewrite_plan_history("plan-1")

        self.assertEqual(rewritten, 1)
        self.assertEqual(len(saved_transactions), 1)
        self.assertAlmostEqual(saved_transactions[0].amount, 45.0)
        self.assertEqual(saved_transactions[0].occurrence_key, "2026-05")
        self.assertEqual(update_kwargs["current_installment_number"], 1)
        # Next due date should be the second (final) installment in June 2026.
        next_due = datetime.fromisoformat(update_kwargs["next_due_date"])
        self.assertEqual((next_due.year, next_due.month, next_due.day), (2026, 6, 15))
        self.assertEqual(update_kwargs["status"], "active")

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

    async def test_rewrite_recurring_plan_history_rebuilds_past_months_and_next_due(self):
        recurring_plan = {
            "id": "plan-1",
            "chat_id": 123,
            "plan_type": "recurring",
            "item": "Netflix",
            "category": "Entertainment",
            "day_of_month": 15,
            "status": "active",
            "start_year": 2026,
            "start_month": 3,
            "next_due_date": datetime(2026, 5, 15, tzinfo=SGT).isoformat(),
            "created_at": datetime(2026, 3, 15, tzinfo=SGT).isoformat(),
            "amount": 20.0,
            "current_installment_number": 0,
        }
        saved_transactions = []
        update_kwargs = {}

        def capture_save_tx(tx):
            saved_transactions.append(tx)

        def capture_update(_plan_id, **kwargs):
            update_kwargs.update(kwargs)

        class FakeDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 5, 20, 12, 0, 0, tzinfo=tz or SGT)

        with patch("services.plan_manager.firestore.get_payment_plan", return_value=recurring_plan), \
             patch("services.plan_manager.firestore.delete_transactions_for_plan", return_value=0), \
             patch("services.plan_manager.firestore.save_transaction", side_effect=capture_save_tx), \
             patch("services.plan_manager.firestore.update_payment_plan", side_effect=capture_update), \
             patch("services.plan_manager.datetime", FakeDateTime):
            rewritten = await rewrite_plan_history("plan-1")

        self.assertEqual(rewritten, 3)
        self.assertEqual([tx.occurrence_key for tx in saved_transactions], ["2026-03", "2026-04", "2026-05"])
        self.assertEqual(update_kwargs["current_installment_number"], 3)
        self.assertEqual(update_kwargs["next_due_date"], "2026-06-15T00:00:00+08:00")
        self.assertEqual(update_kwargs["status"], "active")


class _FakeDueDoc:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data

    def to_dict(self):
        return dict(self._data)


class _FakeDueQuery:
    def __init__(self, docs):
        self._docs = docs

    def where(self, *args, **kwargs):
        return self

    def stream(self):
        return iter(self._docs)


class _FakeDueDb:
    def __init__(self, docs):
        self._docs = docs

    def collection(self, _name):
        return _FakeDueQuery(self._docs)


class ListDuePaymentPlansTests(unittest.TestCase):
    def test_includes_due_and_overdue_excludes_future_and_undated(self):
        today = datetime(2026, 6, 16, tzinfo=SGT)
        docs = [
            _FakeDueDoc("overdue", {"next_due_date": "2026-06-01T00:00:00+08:00"}),
            _FakeDueDoc("due-today", {"next_due_date": "2026-06-16T00:00:00+08:00"}),
            _FakeDueDoc("future", {"next_due_date": "2026-07-01T00:00:00+08:00"}),
            _FakeDueDoc("undated", {"next_due_date": ""}),
        ]
        with patch("services.firestore.get_db", return_value=_FakeDueDb(docs)):
            due = firestore.list_due_payment_plans(today)
        self.assertEqual({plan["id"] for plan in due}, {"overdue", "due-today"})


class CatchUpAndIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def test_overdue_charge_is_dated_to_its_due_month_not_run_date(self):
        # Plan was due 2026-06-01 but is only processed on 2026-06-16 (a missed run).
        # The caught-up charge must be recorded for June, not dated to the run date.
        run_date = datetime(2026, 6, 16, 0, 0, 0, tzinfo=SGT)
        plan = {
            "id": "plan-1",
            "chat_id": 123,
            "plan_type": "recurring",
            "item": "Phone Bill",
            "category": "Other",
            "day_of_month": 1,
            "status": "active",
            "start_year": 2026,
            "start_month": 5,
            "next_due_date": "2026-06-01T00:00:00+08:00",
            "created_at": "2026-05-01T00:00:00+08:00",
            "amount": 18.33,
            "current_installment_number": 1,
        }
        saved = []
        with patch("services.plan_manager.firestore.list_due_payment_plans", return_value=[plan]), \
             patch("services.plan_manager.firestore.find_transaction_by_plan_occurrence", return_value=None), \
             patch("services.plan_manager.firestore.save_transaction", side_effect=saved.append), \
             patch("services.plan_manager.firestore.update_payment_plan"), \
             patch("services.plan_manager.telegram.send_transaction_confirmation", new=AsyncMock()), \
             patch("services.plan_manager._check_budget_exceeded", new=AsyncMock()):
            processed = await process_due_plans(run_date)

        self.assertEqual(processed, 1)
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].occurrence_key, "2026-06")
        self.assertTrue(saved[0].timestamp.startswith("2026-06-01"), saved[0].timestamp)

    async def test_failing_plan_does_not_block_remaining_plans(self):
        run_date = datetime(2026, 6, 16, 0, 0, 0, tzinfo=SGT)

        def make_plan(plan_id, item):
            return {
                "id": plan_id,
                "chat_id": 123,
                "plan_type": "recurring",
                "item": item,
                "category": "Other",
                "day_of_month": 1,
                "status": "active",
                "start_year": 2026,
                "start_month": 5,
                "next_due_date": "2026-06-01T00:00:00+08:00",
                "created_at": "2026-05-01T00:00:00+08:00",
                "amount": 9.99,
                "current_installment_number": 1,
            }

        bad = make_plan("plan-bad", "Boom")
        good = make_plan("plan-good", "Survivor")
        saved = []

        def save_side_effect(tx):
            if tx.source_plan_id == "plan-bad":
                raise RuntimeError("simulated Firestore failure")
            saved.append(tx)

        with patch("services.plan_manager.firestore.list_due_payment_plans", return_value=[bad, good]), \
             patch("services.plan_manager.firestore.find_transaction_by_plan_occurrence", return_value=None), \
             patch("services.plan_manager.firestore.save_transaction", side_effect=save_side_effect), \
             patch("services.plan_manager.firestore.update_payment_plan"), \
             patch("services.plan_manager.telegram.send_transaction_confirmation", new=AsyncMock()), \
             patch("services.plan_manager._check_budget_exceeded", new=AsyncMock()):
            processed = await process_due_plans(run_date)

        self.assertEqual(processed, 1)
        self.assertEqual([tx.source_plan_id for tx in saved], ["plan-good"])


class CreateSplitPlanFromStartDateTests(unittest.IsolatedAsyncioTestCase):
    async def test_split_plan_derives_schedule_from_start_date(self):
        pending = {
            "plan_type": "split_payment",
            "item": "Sofa",
            "category": "Home",
            "total_amount": 300.0,
            "start_date": "2026-07-15",
            "number_of_months": 3,
        }
        saved = {}

        def capture_plan(plan):
            saved.update(plan.__dict__)
            return "plan-1"

        with patch("services.plan_manager.firestore.save_payment_plan", side_effect=capture_plan), \
             patch("services.plan_manager.firestore.get_payment_plan", return_value={"id": "plan-1", **{}}), \
             patch("services.plan_manager.post_next_occurrence", new=AsyncMock()) as mock_post, \
             patch("services.plan_manager.firestore.delete_pending_plan"), \
             patch("services.plan_manager.firestore.clear_user_state"):
            await create_plan_and_post_first_charge(123, pending)

        # Schedule derives from the explicit start date, not "now".
        self.assertEqual(saved["day_of_month"], 15)
        self.assertEqual((saved["start_year"], saved["start_month"]), (2026, 7))
        self.assertEqual(saved["installment_count"], 3)
        self.assertEqual(saved["base_installment_amount"], 100.0)
        # First charge is dated at the start date.
        first_charge_time = mock_post.call_args.kwargs["timestamp"]
        self.assertEqual((first_charge_time.year, first_charge_time.month, first_charge_time.day), (2026, 7, 15))


if __name__ == "__main__":
    unittest.main()
