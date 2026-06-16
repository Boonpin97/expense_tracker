import asyncio
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

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

    def Field(default=None, **_kwargs):
        return default

    pydantic_stub.BaseModel = BaseModel
    pydantic_stub.Field = Field
    sys.modules["pydantic"] = pydantic_stub

if "fastapi" not in sys.modules:
    fastapi_stub = types.ModuleType("fastapi")

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class APIRouter:
        def __init__(self, *args, **kwargs):
            pass

        def get(self, *args, **kwargs):
            return lambda fn: fn

        def post(self, *args, **kwargs):
            return lambda fn: fn

        def patch(self, *args, **kwargs):
            return lambda fn: fn

        def delete(self, *args, **kwargs):
            return lambda fn: fn

    class Response:
        def __init__(self):
            self.headers = {}

        def set_cookie(self, key, value, **kwargs):
            self.headers["set-cookie"] = f"{key}={value}"

        def delete_cookie(self, key, **kwargs):
            self.headers["set-cookie"] = f"{key}="

    class Request:
        pass

    fastapi_stub.APIRouter = APIRouter
    fastapi_stub.HTTPException = HTTPException
    fastapi_stub.Request = Request
    fastapi_stub.Response = Response
    sys.modules["fastapi"] = fastapi_stub

if "google.cloud" not in sys.modules:
    google_mod = types.ModuleType("google")
    cloud_mod = types.ModuleType("google.cloud")
    firestore_mod = types.ModuleType("google.cloud.firestore")

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

    firestore_mod.Client = DummyClient
    cloud_mod.firestore = firestore_mod
    google_mod.cloud = cloud_mod
    sys.modules["google"] = google_mod
    sys.modules["google.cloud"] = cloud_mod
    sys.modules["google.cloud.firestore"] = firestore_mod

from fastapi import HTTPException, Response

from routers import dashboard


class DashboardRouterNegativePathTests(unittest.TestCase):
    def test_require_session_raises_when_missing(self):
        request = SimpleNamespace(cookies={}, headers={})
        with self.assertRaises(HTTPException) as ctx:
            dashboard._require_session(request)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_parse_dashboard_datetime_rejects_invalid_string(self):
        with self.assertRaises(HTTPException) as ctx:
            dashboard._parse_dashboard_datetime("not-a-date")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_scheduled_plan_start_stays_in_same_month_before_due_day(self):
        timestamp = dashboard._parse_dashboard_datetime("2026-05-10T09:30:00+08:00")
        self.assertEqual(dashboard._scheduled_plan_start(timestamp, 15), (2026, 5))

    def test_scheduled_plan_start_moves_to_next_month_after_due_day(self):
        timestamp = dashboard._parse_dashboard_datetime("2026-05-20T09:30:00+08:00")
        self.assertEqual(dashboard._scheduled_plan_start(timestamp, 15), (2026, 6))

    def test_login_dashboard_rejects_inactive_account(self):
        response = Response()
        request = dashboard.LoginRequest(username="alice", password="secret")
        with patch.object(dashboard, "get_account_by_username", return_value={"active": False}):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(dashboard.login_dashboard(request, response))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_create_dashboard_transaction_rejects_invalid_payment_type(self):
        request = SimpleNamespace(cookies={}, headers={})
        payload = dashboard.TransactionCreateRequest(
            item="Coffee",
            amount=4.5,
            category="Food",
            timestamp="2026-05-20T09:30:00+08:00",
            payment_type="crypto",
        )
        with patch.object(dashboard, "_require_session", return_value={"chat_id": 123}):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(dashboard.create_dashboard_transaction(payload, request))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_create_dashboard_transaction_rejects_invalid_split_months(self):
        request = SimpleNamespace(cookies={}, headers={})
        payload = dashboard.TransactionCreateRequest(
            item="Laptop",
            amount=120.0,
            category="Shopping",
            timestamp="2026-05-20T09:30:00+08:00",
            payment_type="split_payment",
            start_date="2026-06-15",
            number_of_months=0,
        )
        with patch.object(dashboard, "_require_session", return_value={"chat_id": 123}):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(dashboard.create_dashboard_transaction(payload, request))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_create_dashboard_split_requires_start_date(self):
        request = SimpleNamespace(cookies={}, headers={})
        payload = dashboard.TransactionCreateRequest(
            item="Laptop",
            amount=120.0,
            category="Shopping",
            timestamp="2026-05-20T09:30:00+08:00",
            payment_type="split_payment",
            number_of_months=3,
        )
        with patch.object(dashboard, "_require_session", return_value={"chat_id": 123}):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(dashboard.create_dashboard_transaction(payload, request))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_update_dashboard_transaction_rejects_cross_user_access(self):
        request = SimpleNamespace(cookies={}, headers={})
        payload = dashboard.TransactionUpdateRequest(
            item="Coffee",
            amount=5.0,
            category="Food",
            timestamp="2026-05-20T09:30:00+08:00",
        )
        with (
            patch.object(dashboard, "_require_session", return_value={"chat_id": 123}),
            patch.object(dashboard, "get_transaction_by_id", return_value={"chat_id": 456}),
        ):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(dashboard.update_dashboard_transaction("tx-1", payload, request))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_create_dashboard_category_rejects_duplicate(self):
        request = SimpleNamespace(cookies={}, headers={})
        payload = dashboard.CategoryCreateRequest(name="Food", emoji="🍔")
        with (
            patch.object(dashboard, "_require_session", return_value={"chat_id": 123}),
            patch.object(dashboard, "get_category_list", return_value=[{"name": "Food"}]),
        ):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(dashboard.create_dashboard_category(payload, request))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_update_dashboard_category_same_name_only_updates_emoji(self):
        request = SimpleNamespace(cookies={}, headers={})
        payload = dashboard.CategoryUpdateRequest(name="Food", emoji="🍟")
        with (
            patch.object(dashboard, "_require_session", return_value={"chat_id": 123}),
            patch.object(dashboard, "update_category_emoji", return_value=True) as mock_update_emoji,
        ):
            result = asyncio.run(dashboard.update_dashboard_category("Food", payload, request))

        self.assertEqual(result, {"ok": True})
        mock_update_emoji.assert_called_once_with(123, "Food", "🍟")

    def test_update_dashboard_category_rejects_renaming_other(self):
        request = SimpleNamespace(cookies={}, headers={})
        payload = dashboard.CategoryUpdateRequest(name="Misc", emoji="📦")
        with patch.object(dashboard, "_require_session", return_value={"chat_id": 123}):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(dashboard.update_dashboard_category("Other", payload, request))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_delete_dashboard_category_rejects_other(self):
        request = SimpleNamespace(cookies={}, headers={})
        with patch.object(dashboard, "_require_session", return_value={"chat_id": 123}):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(dashboard.delete_dashboard_category("Other", request))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_move_dashboard_category_rejects_invalid_direction(self):
        request = SimpleNamespace(cookies={}, headers={})
        payload = dashboard.CategoryMoveRequest(direction=2)
        with patch.object(dashboard, "_require_session", return_value={"chat_id": 123}):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(dashboard.move_dashboard_category("Food", payload, request))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_move_dashboard_category_out_of_bounds_is_noop(self):
        request = SimpleNamespace(cookies={}, headers={})
        payload = dashboard.CategoryMoveRequest(direction=-1)
        categories = [{"name": "Food", "order": 1}, {"name": "Other", "order": 9999}]
        with (
            patch.object(dashboard, "_require_session", return_value={"chat_id": 123}),
            patch.object(dashboard, "get_category_list", return_value=categories),
            patch.object(dashboard, "update_category_order") as mock_update_order,
        ):
            result = asyncio.run(dashboard.move_dashboard_category("Food", payload, request))

        self.assertEqual(result, {"ok": True})
        mock_update_order.assert_not_called()

    def test_update_dashboard_budget_rejects_negative_amount(self):
        request = SimpleNamespace(cookies={}, headers={})
        payload = dashboard.BudgetSetRequest(amount=-1.0)
        with patch.object(dashboard, "_require_session", return_value={"chat_id": 123}):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(dashboard.update_dashboard_budget("Food", payload, request))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_update_dashboard_plan_rejects_split_amount_field(self):
        request = SimpleNamespace(cookies={}, headers={})
        payload = dashboard.PlanUpdateRequest(amount=50.0)
        plan = {"id": "plan-1", "chat_id": 123, "plan_type": "split_payment"}
        with (
            patch.object(dashboard, "_require_session", return_value={"chat_id": 123}),
            patch.object(dashboard, "get_payment_plan", return_value=plan),
        ):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(dashboard.update_dashboard_plan("plan-1", payload, request))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_update_dashboard_plan_rejects_installment_count_below_posted(self):
        request = SimpleNamespace(cookies={}, headers={})
        payload = dashboard.PlanUpdateRequest(installment_count=1)
        plan = {
            "id": "plan-1",
            "chat_id": 123,
            "plan_type": "split_payment",
            "current_installment_number": 2,
        }
        with (
            patch.object(dashboard, "_require_session", return_value={"chat_id": 123}),
            patch.object(dashboard, "get_payment_plan", return_value=plan),
        ):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(dashboard.update_dashboard_plan("plan-1", payload, request))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_delete_dashboard_plan_rejects_cross_user_access(self):
        request = SimpleNamespace(cookies={}, headers={})
        plan = {"id": "plan-1", "chat_id": 456, "plan_type": "recurring"}
        with (
            patch.object(dashboard, "_require_session", return_value={"chat_id": 123}),
            patch.object(dashboard, "get_payment_plan", return_value=plan),
        ):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(dashboard.delete_dashboard_plan("plan-1", request))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_delete_dashboard_split_plan_removes_generated_transactions_by_default(self):
        request = SimpleNamespace(cookies={}, headers={})
        plan = {"id": "plan-1", "chat_id": 123, "plan_type": "split_payment"}
        with (
            patch.object(dashboard, "_require_session", return_value={"chat_id": 123}),
            patch.object(dashboard, "get_payment_plan", return_value=plan),
            patch.object(dashboard, "delete_payment_plan") as mock_delete_plan,
            patch.object(dashboard, "delete_transactions_for_plan", return_value=2) as mock_delete_txs,
        ):
            result = asyncio.run(dashboard.delete_dashboard_plan("plan-1", request))

        self.assertEqual(result, {"ok": True, "deleted": 2})
        mock_delete_plan.assert_called_once_with("plan-1")
        mock_delete_txs.assert_called_once_with("plan-1")


if __name__ == "__main__":
    unittest.main()
