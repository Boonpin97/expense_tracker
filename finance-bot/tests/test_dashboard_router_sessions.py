import asyncio
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
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

from fastapi import Response

from routers import dashboard


class DashboardRouterSessionTests(unittest.TestCase):
    def test_session_payload_uses_cookie_token_first(self):
        request = SimpleNamespace(
            cookies={dashboard.COOKIE_NAME: "cookie-token"},
            headers={dashboard.SESSION_HEADER: "header-token"},
        )

        with patch.object(dashboard, "get_web_session", return_value={"chat_id": 123}) as mock_get:
            payload = dashboard._session_payload(request)

        self.assertEqual(payload, {"chat_id": 123})
        mock_get.assert_called_once_with("cookie-token")

    def test_session_payload_falls_back_to_header_token(self):
        request = SimpleNamespace(cookies={}, headers={dashboard.SESSION_HEADER: "header-token"})

        with patch.object(dashboard, "get_web_session", return_value={"chat_id": 456}) as mock_get:
            payload = dashboard._session_payload(request)

        self.assertEqual(payload, {"chat_id": 456})
        mock_get.assert_called_once_with("header-token")

    def test_session_payload_falls_back_to_bearer_token(self):
        request = SimpleNamespace(cookies={}, headers={"authorization": "Bearer api-token"})

        with patch.object(dashboard, "get_web_session", return_value={"chat_id": 789}) as mock_get:
            payload = dashboard._session_payload(request)

        self.assertEqual(payload, {"chat_id": 789})
        mock_get.assert_called_once_with("api-token")

    def test_login_dashboard_returns_session_token(self):
        response = Response()
        expires_at = datetime(2026, 5, 7, 12, 0, tzinfo=timezone(timedelta(hours=8)))
        request = dashboard.LoginRequest(username="alice", password="correct-password")
        account = {
            "username": "alice",
            "chat_id": 123,
            "password_hash": "stored-hash",
            "active": True,
        }

        with (
            patch.object(dashboard, "get_account_by_username", return_value=account),
            patch.object(dashboard, "verify_password", return_value=True),
            patch.object(dashboard, "build_session_token", return_value="session-token"),
            patch.object(dashboard, "session_expiry", return_value=expires_at),
            patch.object(dashboard, "save_web_session") as mock_save,
        ):
            result = asyncio.run(dashboard.login_dashboard(request, response))

        self.assertTrue(result.authenticated)
        self.assertEqual(result.username, "alice")
        self.assertEqual(result.chat_id, 123)
        self.assertEqual(result.session_token, "session-token")
        self.assertIn("dashboard_session=session-token", response.headers.get("set-cookie", ""))
        mock_save.assert_called_once_with(
            token="session-token",
            chat_id=123,
            username="alice",
            expires_at=expires_at,
        )

    def test_update_dashboard_split_plan_recomputes_schedule_and_rewrites_history(self):
        request = SimpleNamespace(cookies={}, headers={})
        session = {"chat_id": 123}
        plan = {
            "id": "plan-1",
            "chat_id": 123,
            "plan_type": "split_payment",
            "item": "Laptop",
            "category": "Shopping",
            "day_of_month": 12,
            "status": "active",
            "start_year": 2026,
            "start_month": 5,
            "next_due_date": "2026-06-12T00:00:00+08:00",
            "created_at": "2026-05-12T00:00:00+08:00",
            "total_amount": 120.0,
            "installment_count": 4,
            "current_installment_number": 1,
            "base_installment_amount": 30.0,
            "final_installment_amount": 30.0,
        }
        payload = dashboard.PlanUpdateRequest(total_amount=150.0, installment_count=3)

        with (
            patch.object(dashboard, "_require_session", return_value=session),
            patch.object(dashboard, "get_payment_plan", return_value=plan),
            patch.object(dashboard, "compute_split_amounts", return_value=(50.0, 50.0)),
            patch.object(
                dashboard,
                "compute_next_due_date",
                return_value=datetime(2026, 6, 12, tzinfo=timezone(timedelta(hours=8))),
            ),
            patch.object(dashboard, "update_payment_plan") as mock_update,
            patch.object(dashboard, "rewrite_plan_history", new_callable=AsyncMock) as mock_rewrite,
        ):
            result = asyncio.run(dashboard.update_dashboard_plan("plan-1", payload, request))

        self.assertEqual(result, {"ok": True})
        mock_update.assert_called_once_with(
            "plan-1",
            total_amount=150.0,
            installment_count=3,
            base_installment_amount=50.0,
            final_installment_amount=50.0,
            next_due_date="2026-06-12T00:00:00+08:00",
            status="active",
        )
        mock_rewrite.assert_awaited_once_with("plan-1")

    def test_delete_dashboard_plan_removes_plan_document(self):
        request = SimpleNamespace(cookies={}, headers={})
        session = {"chat_id": 123}
        plan = {
            "id": "plan-1",
            "chat_id": 123,
            "plan_type": "recurring",
        }

        with (
            patch.object(dashboard, "_require_session", return_value=session),
            patch.object(dashboard, "get_payment_plan", return_value=plan),
            patch.object(dashboard, "delete_payment_plan") as mock_delete_plan,
            patch.object(dashboard, "delete_transactions_for_plan", return_value=0) as mock_delete_tx,
        ):
            result = asyncio.run(dashboard.delete_dashboard_plan("plan-1", request, mode="future"))

        self.assertEqual(result, {"ok": True, "deleted": 0})
        mock_delete_plan.assert_called_once_with("plan-1")
        mock_delete_tx.assert_not_called()

    def test_update_dashboard_preferences_persists_overview_cards(self):
        request = SimpleNamespace(cookies={}, headers={})
        session = {"chat_id": 123}
        payload = dashboard.DashboardPreferencesUpdateRequest(
            overview_visible_cards=["today", "month"],
        )

        with (
            patch.object(dashboard, "_require_session", return_value=session),
            patch.object(dashboard, "update_dashboard_preferences") as mock_update,
        ):
            result = asyncio.run(dashboard.update_dashboard_user_preferences(payload, request))

        self.assertEqual(result, {"ok": True})
        mock_update.assert_called_once_with(123, overview_visible_cards=["today", "month"])

    def test_create_dashboard_one_time_transaction_saves_manual_transaction(self):
        request = SimpleNamespace(cookies={}, headers={})
        session = {"chat_id": 123}
        payload = dashboard.TransactionCreateRequest(
            item="Coffee",
            amount=4.5,
            category="Food",
            timestamp="2026-05-12T09:30:00+08:00",
            payment_type="one_time",
        )

        with (
            patch.object(dashboard, "_require_session", return_value=session),
            patch.object(dashboard, "save_transaction") as mock_save,
        ):
            result = asyncio.run(dashboard.create_dashboard_transaction(payload, request))

        self.assertEqual(result, {"ok": True})
        saved_tx = mock_save.call_args.args[0]
        self.assertEqual(saved_tx.item, "Coffee")
        self.assertEqual(saved_tx.amount, 4.5)
        self.assertEqual(saved_tx.category, "Food")
        self.assertEqual(saved_tx.chat_id, 123)
        self.assertEqual(saved_tx.source_type, "manual")
        self.assertFalse(saved_tx.auto_generated)

    def test_create_dashboard_split_plan_without_immediate_charge_schedules_first_due(self):
        request = SimpleNamespace(cookies={}, headers={})
        session = {"chat_id": 123}
        payload = dashboard.TransactionCreateRequest(
            item="Laptop",
            amount=120.0,
            category="Shopping",
            timestamp="2026-05-20T09:30:00+08:00",
            payment_type="split_payment",
            start_date="2026-06-15",
            number_of_months=3,
            create_first_transaction_now=False,
        )
        saved_plan = {}

        def capture_plan(plan):
            saved_plan.update(plan.__dict__)
            return "plan-1"

        with (
            patch.object(dashboard, "_require_session", return_value=session),
            patch.object(dashboard, "save_payment_plan", side_effect=capture_plan),
            patch.object(
                dashboard,
                "get_payment_plan",
                return_value={
                    "id": "plan-1",
                    **{
                        "chat_id": 123,
                        "plan_type": "split_payment",
                        "item": "Laptop",
                        "category": "Shopping",
                        "day_of_month": 15,
                        "start_year": 2026,
                        "start_month": 6,
                        "next_due_date": "2026-05-20T09:30:00+08:00",
                        "created_at": "2026-05-12T00:00:00+08:00",
                        "total_amount": 120.0,
                        "installment_count": 3,
                        "current_installment_number": 0,
                        "base_installment_amount": 40.0,
                        "final_installment_amount": 40.0,
                    },
                },
            ),
            patch.object(dashboard, "update_payment_plan") as mock_update,
            patch.object(dashboard, "save_transaction") as mock_save_tx,
        ):
            result = asyncio.run(dashboard.create_dashboard_transaction(payload, request))

        self.assertEqual(result, {"ok": True})
        self.assertEqual((saved_plan["start_year"], saved_plan["start_month"]), (2026, 6))
        mock_save_tx.assert_not_called()
        mock_update.assert_called_once_with(
            "plan-1",
            current_installment_number=0,
            next_due_date="2026-06-15T00:00:00+08:00",
            status="active",
        )


if __name__ == "__main__":
    unittest.main()
