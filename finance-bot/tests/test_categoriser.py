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

from services import categoriser

SGT = timezone(timedelta(hours=8))


class CategoriserTests(unittest.IsolatedAsyncioTestCase):
    async def test_handle_expense_saves_known_item_immediately(self):
        with (
            patch.object(categoriser.firestore, "get_category", return_value="Food"),
            patch.object(categoriser.firestore, "save_transaction", return_value="tx-1") as mock_save_tx,
            patch.object(categoriser.telegram, "send_transaction_confirmation", new=AsyncMock()) as mock_confirm,
            patch.object(categoriser, "_check_budget_exceeded", new=AsyncMock()) as mock_budget,
        ):
            await categoriser.handle_expense(123, "Coffee!", 4.5)

        saved_tx = mock_save_tx.call_args.args[0]
        self.assertEqual(saved_tx.item, "Coffee!")
        self.assertEqual(saved_tx.amount, 4.5)
        self.assertEqual(saved_tx.category, "Food")
        self.assertEqual(saved_tx.chat_id, 123)
        mock_confirm.assert_awaited_once_with(
            123,
            "Coffee!",
            4.5,
            "Food",
            tx_id="tx-1",
            item_key="coffee",
            include_change_date=True,
        )
        mock_budget.assert_awaited_once_with(123, "Food")

    async def test_handle_expense_with_explicit_date_omits_change_date_action(self):
        with (
            patch.object(categoriser.firestore, "get_category", return_value="Transport"),
            patch.object(categoriser.firestore, "save_transaction", return_value="tx-2"),
            patch.object(categoriser.telegram, "send_transaction_confirmation", new=AsyncMock()) as mock_confirm,
            patch.object(categoriser, "_check_budget_exceeded", new=AsyncMock()),
        ):
            await categoriser.handle_expense(123, "Grab", 10.0, transaction_date="2026-05-20")

        self.assertFalse(mock_confirm.call_args.kwargs["include_change_date"])

    async def test_handle_expense_saves_pending_for_unknown_item(self):
        with (
            patch.object(categoriser.firestore, "get_category", return_value=None),
            patch.object(categoriser.firestore, "save_pending") as mock_save_pending,
            patch.object(categoriser.telegram, "send_category_keyboard", new=AsyncMock()) as mock_keyboard,
        ):
            await categoriser.handle_expense(123, "Mystery Shop", 12.3)

        self.assertEqual(mock_save_pending.call_args.args[:3], (123, "Mystery Shop", 12.3))
        self.assertIn("timestamp", mock_save_pending.call_args.kwargs)
        mock_keyboard.assert_awaited_once_with(123, "Mystery Shop", 12.3)

    async def test_handle_category_selection_saves_pending_transaction(self):
        pending = {
            "item": "Mystery Shop",
            "amount": 12.3,
            "timestamp": "2026-05-20T09:00:00+08:00",
            "created_at": datetime.now(SGT).isoformat(),
            "date_was_explicit": False,
        }
        with (
            patch.object(categoriser.firestore, "get_pending_change", return_value=None),
            patch.object(categoriser.firestore, "get_pending", return_value=pending),
            patch.object(categoriser.firestore, "save_transaction", return_value="tx-3") as mock_save_tx,
            patch.object(categoriser.firestore, "save_category") as mock_save_category,
            patch.object(categoriser.firestore, "delete_pending") as mock_delete_pending,
            patch.object(categoriser.telegram, "answer_callback_query", new=AsyncMock()) as mock_answer,
            patch.object(categoriser.telegram, "send_transaction_confirmation", new=AsyncMock()) as mock_confirm,
            patch.object(categoriser, "_check_budget_exceeded", new=AsyncMock()) as mock_budget,
        ):
            await categoriser.handle_category_selection(123, "Shopping", "cb-1")

        saved_tx = mock_save_tx.call_args.args[0]
        self.assertEqual(saved_tx.category, "Shopping")
        mock_save_category.assert_called_once_with(123, "mystery shop", "Shopping", confirmed_by_user=True)
        mock_delete_pending.assert_called_once_with(123)
        mock_answer.assert_awaited_once_with("cb-1", "Saved as Shopping")
        self.assertTrue(mock_confirm.call_args.kwargs["include_change_date"])
        mock_budget.assert_awaited_once_with(123, "Shopping")

    async def test_handle_category_selection_rejects_expired_pending(self):
        expired_pending = {
            "item": "Old Expense",
            "amount": 7.0,
            "timestamp": "2026-05-20T09:00:00+08:00",
            "created_at": (datetime.now(SGT) - timedelta(minutes=10)).isoformat(),
        }
        with (
            patch.object(categoriser.firestore, "get_pending_change", return_value=None),
            patch.object(categoriser.firestore, "get_pending", return_value=expired_pending),
            patch.object(categoriser.firestore, "delete_pending") as mock_delete_pending,
            patch.object(categoriser.telegram, "answer_callback_query", new=AsyncMock()) as mock_answer,
            patch.object(categoriser.telegram, "send_message", new=AsyncMock()) as mock_send,
        ):
            await categoriser.handle_category_selection(123, "Food", "cb-2")

        mock_delete_pending.assert_called_once_with(123)
        mock_answer.assert_awaited_once_with("cb-2", "⏰ This selection has expired.")
        self.assertIn("expired", mock_send.call_args.args[1].lower())

    async def test_handle_custom_category_input_saves_category_and_transaction(self):
        pending = {
            "item": "Pop-up Store",
            "amount": 9.5,
            "timestamp": "2026-05-20T09:00:00+08:00",
            "created_at": datetime.now(SGT).isoformat(),
            "date_was_explicit": True,
        }
        with (
            patch.object(categoriser.firestore, "get_pending", return_value=pending),
            patch.object(categoriser.firestore, "save_transaction", return_value="tx-4") as mock_save_tx,
            patch.object(categoriser.firestore, "save_category") as mock_save_category,
            patch.object(categoriser.firestore, "add_category_to_list") as mock_add_category,
            patch.object(categoriser.firestore, "delete_pending") as mock_delete_pending,
            patch.object(categoriser.telegram, "send_transaction_confirmation", new=AsyncMock()) as mock_confirm,
            patch.object(categoriser, "_check_budget_exceeded", new=AsyncMock()) as mock_budget,
        ):
            await categoriser.handle_custom_category_input(123, "Fun Stuff", "🎉")

        saved_tx = mock_save_tx.call_args.args[0]
        self.assertEqual(saved_tx.category, "Fun Stuff")
        mock_save_category.assert_called_once_with(123, "popup store", "Fun Stuff", confirmed_by_user=True)
        mock_add_category.assert_called_once_with(123, "Fun Stuff", "🎉")
        mock_delete_pending.assert_called_once_with(123)
        self.assertEqual(mock_confirm.call_args.kwargs["note"], "New category saved")
        self.assertFalse(mock_confirm.call_args.kwargs["include_change_date"])
        mock_budget.assert_awaited_once_with(123, "Fun Stuff")

    async def test_handle_custom_category_input_without_pending_warns_user(self):
        with (
            patch.object(categoriser.firestore, "get_pending", return_value=None),
            patch.object(categoriser.telegram, "send_message", new=AsyncMock()) as mock_send,
        ):
            await categoriser.handle_custom_category_input(123, "Fun Stuff", "🎉")

        mock_send.assert_awaited_once()
        self.assertIn("no pending expense", mock_send.call_args.args[1].lower())

    async def test_handle_category_selection_updates_existing_transaction_in_change_flow(self):
        pending_change = {
            "tx_id": "tx-99",
            "item_key": "coffee",
            "timestamp": datetime.now(SGT).isoformat(),
        }
        with (
            patch.object(categoriser.firestore, "get_pending_change", return_value=pending_change),
            patch.object(categoriser.firestore, "update_transaction_category") as mock_update_tx,
            patch.object(categoriser.firestore, "save_category") as mock_save_category,
            patch.object(categoriser.firestore, "delete_pending_change") as mock_delete_pending_change,
            patch.object(categoriser.telegram, "answer_callback_query", new=AsyncMock()) as mock_answer,
            patch.object(categoriser.telegram, "send_message", new=AsyncMock()) as mock_send,
        ):
            await categoriser.handle_category_selection(123, "Food", "cb-3")

        mock_update_tx.assert_called_once_with("tx-99", "Food")
        mock_save_category.assert_called_once_with(123, "coffee", "Food", confirmed_by_user=True)
        mock_delete_pending_change.assert_called_once_with(123)
        mock_answer.assert_awaited_once_with("cb-3", "Changed to Food")
        self.assertIn("recategorised", mock_send.call_args.args[1].lower())

    async def test_handle_category_selection_new_category_from_expense_flow_sets_inline_name_state(self):
        pending = {
            "item": "Mystery Shop",
            "amount": 12.3,
            "timestamp": "2026-05-20T09:00:00+08:00",
            "created_at": datetime.now(SGT).isoformat(),
        }
        with (
            patch.object(categoriser.firestore, "get_pending_change", return_value=None),
            patch.object(categoriser.firestore, "get_pending", return_value=pending),
            patch.object(categoriser.firestore, "set_user_state") as mock_set_state,
            patch.object(categoriser.telegram, "answer_callback_query", new=AsyncMock()) as mock_answer,
            patch.object(categoriser.telegram, "send_message", new=AsyncMock()) as mock_send,
        ):
            await categoriser.handle_category_selection(123, "__new__", "cb-4")

        mock_set_state.assert_called_once_with(123, "awaiting_inline_cat_name")
        mock_answer.assert_awaited_once_with("cb-4", "")
        self.assertIn("type the name of the new category", mock_send.call_args.args[1].lower())

    async def test_check_budget_exceeded_sends_warning_when_over_prorated_limit(self):
        now = datetime(2026, 5, 20, 12, 0, tzinfo=SGT)

        class FakeDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return now.astimezone(tz or SGT)

        txs = [
            {"category": "Food", "amount": 120.0},
            {"category": "Food", "amount": 10.0},
        ]
        with (
            patch.object(categoriser.firestore, "get_budgets", return_value={"Food": 100.0}),
            patch.object(categoriser.firestore, "get_transactions", return_value=txs),
            patch.object(categoriser.telegram, "send_message", new=AsyncMock()) as mock_send,
            patch.object(categoriser, "datetime", FakeDateTime),
        ):
            await categoriser._check_budget_exceeded(123, "Food")

        self.assertIn("budget exceeded", mock_send.call_args.args[1].lower())

    async def test_check_budget_exceeded_skips_when_under_limit(self):
        now = datetime(2026, 5, 20, 12, 0, tzinfo=SGT)

        class FakeDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return now.astimezone(tz or SGT)

        with (
            patch.object(categoriser.firestore, "get_budgets", return_value={"Food": 1000.0}),
            patch.object(categoriser.firestore, "get_transactions", return_value=[{"category": "Food", "amount": 100.0}]),
            patch.object(categoriser.telegram, "send_message", new=AsyncMock()) as mock_send,
            patch.object(categoriser, "datetime", FakeDateTime),
        ):
            await categoriser._check_budget_exceeded(123, "Food")

        mock_send.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
