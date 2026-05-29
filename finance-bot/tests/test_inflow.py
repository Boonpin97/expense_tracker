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

if "fastapi" not in sys.modules:
    fastapi_stub = types.ModuleType("fastapi")

    class APIRouter:
        def __init__(self, *args, **kwargs):
            pass

        def get(self, *_args, **_kwargs):
            return lambda fn: fn

        def post(self, *_args, **_kwargs):
            return lambda fn: fn

        def patch(self, *_args, **_kwargs):
            return lambda fn: fn

        def delete(self, *_args, **_kwargs):
            return lambda fn: fn

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    def Header(default=None, alias=None):
        return default

    def Query(default=None, **_kwargs):
        return default

    class Request:
        pass

    class Response:
        pass

    fastapi_stub.APIRouter = APIRouter
    fastapi_stub.HTTPException = HTTPException
    fastapi_stub.Header = Header
    fastapi_stub.Query = Query
    fastapi_stub.Request = Request
    fastapi_stub.Response = Response
    sys.modules["fastapi"] = fastapi_stub

from fastapi import HTTPException

from routers import dashboard, reports
from routers.webhook import webhook

SGT = timezone(timedelta(hours=8))


def _future_iso() -> str:
    return (datetime.now(SGT) + timedelta(seconds=120)).isoformat()


class InflowCommandTests(unittest.TestCase):
    def _request_for_text(self, text: str, chat_id: int = 123):
        payload = {"message": {"chat": {"id": chat_id}, "text": text}}

        class DummyRequest:
            async def json(self_nonlocal):
                return payload

        return DummyRequest()

    def test_inflow_command_with_args_records_inflow(self):
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.save_inflow") as mock_save,
            patch("routers.webhook.telegram.send_message", new=AsyncMock()) as mock_send,
        ):
            result = asyncio.run(webhook(self._request_for_text("/inflow Salary 2000")))

        self.assertEqual(result, {"ok": True})
        mock_save.assert_called_once()
        inflow = mock_save.call_args.args[0]
        self.assertEqual(inflow.item, "Salary")
        self.assertEqual(inflow.amount, 2000.0)
        self.assertEqual(inflow.chat_id, 123)
        self.assertIn("Income", mock_send.call_args.args[1])

    def test_inflow_command_with_dollar_and_date(self):
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.save_inflow") as mock_save,
            patch("routers.webhook.telegram.send_message", new=AsyncMock()),
        ):
            asyncio.run(webhook(self._request_for_text("/inflow Cashback $50 130126")))

        inflow = mock_save.call_args.args[0]
        self.assertEqual(inflow.item, "Cashback")
        self.assertEqual(inflow.amount, 50.0)
        self.assertTrue(inflow.timestamp.startswith("2026-01-13"))

    def test_inflow_command_without_args_starts_session(self):
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.start_session") as mock_start,
            patch("routers.webhook.telegram.send_message", new=AsyncMock()) as mock_send,
        ):
            result = asyncio.run(webhook(self._request_for_text("/inflow")))

        self.assertEqual(result, {"ok": True})
        mock_start.assert_called_once_with(123, "inflow", "awaiting_entry")
        self.assertIn("item", mock_send.call_args.args[1].lower())

    def test_inflow_command_invalid_args_sends_guidance(self):
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.save_inflow") as mock_save,
            patch("routers.webhook.telegram.send_message", new=AsyncMock()) as mock_send,
        ):
            asyncio.run(webhook(self._request_for_text("/inflow ??? ++")))

        mock_save.assert_not_called()
        self.assertIn("couldn't read", mock_send.call_args.args[1].lower())


class InflowSessionTests(unittest.TestCase):
    def _request_for_text(self, text: str, chat_id: int = 123):
        payload = {"message": {"chat": {"id": chat_id}, "text": text}}

        class DummyRequest:
            async def json(self_nonlocal):
                return payload

        return DummyRequest()

    def _common_patches(self):
        return (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook._handle_dashboard_account_session", new=AsyncMock(return_value=False)),
            patch("routers.webhook._handle_set_budget_session", new=AsyncMock(return_value=False)),
        )

    def test_active_session_records_inflow_and_clears(self):
        session = {"flow_type": "inflow", "step": "awaiting_entry", "expires_at": _future_iso()}
        a, b, c = self._common_patches()
        with (
            a, b, c,
            patch("routers.webhook.get_session", return_value=session),
            patch("routers.webhook.session_expired", return_value=False),
            patch("routers.webhook.clear_session") as mock_clear,
            patch("routers.webhook.save_inflow") as mock_save,
            patch("routers.webhook.telegram.send_message", new=AsyncMock()) as mock_send,
        ):
            result = asyncio.run(webhook(self._request_for_text("Cashback 50")))

        self.assertEqual(result, {"ok": True})
        mock_save.assert_called_once()
        inflow = mock_save.call_args.args[0]
        self.assertEqual(inflow.item, "Cashback")
        self.assertEqual(inflow.amount, 50.0)
        mock_clear.assert_called_once_with(123)
        self.assertIn("Income", mock_send.call_args.args[1])

    def test_expired_session_clears_and_notifies_without_recording(self):
        session = {"flow_type": "inflow", "step": "awaiting_entry", "expires_at": "2000-01-01T00:00:00+08:00"}
        a, b, c = self._common_patches()
        with (
            a, b, c,
            patch("routers.webhook.get_session", return_value=session),
            patch("routers.webhook.session_expired", return_value=True),
            patch("routers.webhook.clear_session") as mock_clear,
            patch("routers.webhook.save_inflow") as mock_save,
            patch("routers.webhook.telegram.send_message", new=AsyncMock()) as mock_send,
        ):
            result = asyncio.run(webhook(self._request_for_text("Cashback 50")))

        self.assertEqual(result, {"ok": True})
        mock_save.assert_not_called()
        mock_clear.assert_called_once_with(123)
        self.assertIn("expired", mock_send.call_args.args[1].lower())

    def test_invalid_entry_keeps_session_active(self):
        session = {"flow_type": "inflow", "step": "awaiting_entry", "expires_at": _future_iso()}
        a, b, c = self._common_patches()
        with (
            a, b, c,
            patch("routers.webhook.get_session", return_value=session),
            patch("routers.webhook.session_expired", return_value=False),
            patch("routers.webhook.clear_session") as mock_clear,
            patch("routers.webhook.save_inflow") as mock_save,
            patch("routers.webhook.telegram.send_message", new=AsyncMock()) as mock_send,
        ):
            result = asyncio.run(webhook(self._request_for_text("???")))

        self.assertEqual(result, {"ok": True})
        mock_save.assert_not_called()
        mock_clear.assert_not_called()
        self.assertIn("couldn't read", mock_send.call_args.args[1].lower())


class InflowReportTests(unittest.TestCase):
    def test_format_report_appends_income_and_net(self):
        transactions = [{"category": "Food", "amount": 40.0}]
        inflows = [{"amount": 100.0}]
        with patch.object(reports, "get_category_list", return_value=[{"name": "Food", "emoji": "🍔"}]):
            body = reports._format_report(123, "Weekly Report", transactions, inflows)

        self.assertIn("Income", body)
        self.assertIn("100.00", body)
        self.assertIn("Net", body)
        self.assertIn("60.00", body)

    def test_format_report_negative_net(self):
        transactions = [{"category": "Food", "amount": 100.0}]
        inflows = [{"amount": 30.0}]
        with patch.object(reports, "get_category_list", return_value=[{"name": "Food", "emoji": "🍔"}]):
            body = reports._format_report(123, "Weekly Report", transactions, inflows)

        self.assertIn("-$", body)
        self.assertIn("70.00", body)

    def test_format_report_income_without_expenses(self):
        with patch.object(reports, "get_category_list", return_value=[]):
            body = reports._format_report(123, "Weekly Report", [], [{"amount": 250.0}])

        self.assertIn("No expenses recorded.", body)
        self.assertIn("Income", body)
        self.assertIn("250.00", body)

    def test_format_report_without_inflows_unchanged(self):
        transactions = [{"category": "Food", "amount": 40.0}]
        with patch.object(reports, "get_category_list", return_value=[{"name": "Food", "emoji": "🍔"}]):
            body = reports._format_report(123, "Weekly Report", transactions)

        self.assertNotIn("Income", body)
        self.assertNotIn("Net", body)

    def test_format_daily_report_lists_inflows_with_times(self):
        transactions = [
            {"item": "Lunch", "amount": 12.0, "category": "Food", "timestamp": "2026-05-20T12:30:00+08:00"},
        ]
        inflows = [
            {"item": "Salary", "amount": 2000.0, "timestamp": "2026-05-20T09:00:00+08:00"},
        ]
        with patch.object(reports, "get_category_list", return_value=[{"name": "Food", "emoji": "🍔"}]):
            body = reports._format_daily_report(123, "Daily Report", transactions, inflows)

        self.assertIn("Salary", body)
        self.assertIn("2000.00", body)
        self.assertIn("Income", body)
        self.assertIn("Net", body)


class _FakeDoc:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data

    def to_dict(self):
        return dict(self._data)


class _FakeQuery:
    def __init__(self, docs):
        self._docs = docs

    def where(self, field, _op, value):
        return _FakeQuery([d for d in self._docs if d._data.get(field) == value])

    def stream(self):
        return iter(self._docs)


class _FakeDB:
    def __init__(self, docs):
        self._docs = docs

    def collection(self, _name):
        return _FakeQuery(self._docs)


class InflowFirestoreQueryTests(unittest.TestCase):
    def test_get_inflows_filters_by_window_and_chat(self):
        from services import firestore

        docs = [
            _FakeDoc("a", {"chat_id": 123, "amount": 10.0, "timestamp": "2026-05-20T09:00:00+08:00"}),
            _FakeDoc("b", {"chat_id": 123, "amount": 20.0, "timestamp": "2026-05-25T09:00:00+08:00"}),
            _FakeDoc("c", {"chat_id": 999, "amount": 30.0, "timestamp": "2026-05-20T10:00:00+08:00"}),
        ]
        start = datetime(2026, 5, 20, tzinfo=SGT)
        end = datetime(2026, 5, 21, tzinfo=SGT)

        with patch.object(firestore, "get_db", return_value=_FakeDB(docs)):
            rows = firestore.get_inflows(123, start, end)
            with_ids = firestore.get_inflows_with_ids(123, start, end)

        self.assertEqual([row["amount"] for row in rows], [10.0])
        self.assertEqual([row["_doc_id"] for row in with_ids], ["a"])
        self.assertNotIn("_doc_id", rows[0])


class DashboardInflowTests(unittest.TestCase):
    def _request(self):
        return SimpleNamespace(cookies={}, headers={})

    def test_create_inflow_rejects_empty_item(self):
        payload = dashboard.InflowCreateRequest(item="   ", amount=10.0, timestamp="2026-05-20T09:30:00+08:00")
        with patch.object(dashboard, "_require_session", return_value={"chat_id": 123}):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(dashboard.create_dashboard_inflow(payload, self._request()))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_create_inflow_rejects_non_positive_amount(self):
        payload = dashboard.InflowCreateRequest(item="Salary", amount=0.0, timestamp="2026-05-20T09:30:00+08:00")
        with patch.object(dashboard, "_require_session", return_value={"chat_id": 123}):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(dashboard.create_dashboard_inflow(payload, self._request()))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_create_inflow_saves(self):
        payload = dashboard.InflowCreateRequest(item="Salary", amount=2000.0, timestamp="2026-05-20T09:30:00+08:00")
        with (
            patch.object(dashboard, "_require_session", return_value={"chat_id": 123}),
            patch.object(dashboard, "save_inflow") as mock_save,
        ):
            result = asyncio.run(dashboard.create_dashboard_inflow(payload, self._request()))

        self.assertEqual(result, {"ok": True})
        mock_save.assert_called_once()
        inflow = mock_save.call_args.args[0]
        self.assertEqual(inflow.item, "Salary")
        self.assertEqual(inflow.amount, 2000.0)
        self.assertEqual(inflow.chat_id, 123)

    def test_list_inflows_sorts_descending_by_timestamp(self):
        rows = [
            {"item": "Older", "amount": 1.0, "timestamp": "2026-05-19T09:00:00+08:00", "_doc_id": "a"},
            {"item": "Newer", "amount": 2.0, "timestamp": "2026-05-20T09:00:00+08:00", "_doc_id": "b"},
        ]
        with (
            patch.object(dashboard, "_require_session", return_value={"chat_id": 123}),
            patch.object(dashboard, "get_inflows_with_ids", return_value=list(rows)),
        ):
            result = asyncio.run(
                dashboard.list_dashboard_inflows(
                    self._request(),
                    "2026-05-01T00:00:00+08:00",
                    "2026-06-01T00:00:00+08:00",
                )
            )

        self.assertEqual([i["item"] for i in result["inflows"]], ["Newer", "Older"])

    def test_delete_inflow_rejects_cross_user(self):
        with (
            patch.object(dashboard, "_require_session", return_value={"chat_id": 123}),
            patch.object(dashboard, "get_inflow_by_id", return_value={"chat_id": 456}),
        ):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(dashboard.delete_dashboard_inflow("inflow-1", self._request()))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_delete_inflow_success(self):
        with (
            patch.object(dashboard, "_require_session", return_value={"chat_id": 123}),
            patch.object(dashboard, "get_inflow_by_id", return_value={"chat_id": 123}),
            patch.object(dashboard, "delete_inflow") as mock_delete,
        ):
            result = asyncio.run(dashboard.delete_dashboard_inflow("inflow-1", self._request()))

        self.assertEqual(result, {"ok": True})
        mock_delete.assert_called_once_with("inflow-1")


if __name__ == "__main__":
    unittest.main()
