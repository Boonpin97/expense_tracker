import asyncio
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    def Header(default=None, alias=None):
        return default

    def Query(default=None, **_kwargs):
        return default

    fastapi_stub.APIRouter = APIRouter
    fastapi_stub.HTTPException = HTTPException
    fastapi_stub.Header = Header
    fastapi_stub.Query = Query
    sys.modules["fastapi"] = fastapi_stub

from fastapi import HTTPException

from routers import reports

SGT = timezone(timedelta(hours=8))


class ReportsRouterTests(unittest.TestCase):
    def test_get_period_window_monthly_on_first_day_uses_previous_month(self):
        now = datetime(2026, 6, 1, 9, 0, tzinfo=SGT)

        class FakeDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return now.astimezone(tz or SGT)

        with patch.object(reports, "datetime", FakeDateTime):
            start, end, label = reports._get_period_window("monthly")

        self.assertEqual(start, datetime(2026, 5, 1, tzinfo=SGT))
        self.assertEqual(end, datetime(2026, 6, 1, tzinfo=SGT))
        self.assertEqual(label, "Monthly Report (May 2026)")

    def test_get_period_window_invalid_period_raises(self):
        with self.assertRaises(HTTPException) as ctx:
            reports._get_period_window("yearly")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_format_report_sorts_categories_by_total_descending_with_fallback_emoji(self):
        transactions = [
            {"category": "Food", "amount": 15.0},
            {"category": "Transport", "amount": 5.0},
            {"category": "Food", "amount": 10.0},
            {"category": "Other", "amount": 30.0},
        ]
        with patch.object(reports, "get_category_list", return_value=[{"name": "Food", "emoji": "🍔"}]):
            body = reports._format_report(123, "Weekly Report", transactions)

        self.assertLess(body.index("📦 Other"), body.index("🍔 Food"))
        self.assertLess(body.index("🍔 Food"), body.index("📦 Transport"))
        self.assertIn("100.0%", body)

    def test_format_daily_report_sorts_by_timestamp_and_formats_times(self):
        transactions = [
            {"item": "Dinner", "amount": 12.0, "category": "Food", "timestamp": "2026-05-20T19:30:00+08:00"},
            {"item": "Breakfast", "amount": 5.0, "category": "Food", "timestamp": "2026-05-20T08:15:00+08:00"},
        ]
        with patch.object(reports, "get_category_list", return_value=[{"name": "Food", "emoji": "🍔"}]):
            body = reports._format_daily_report(123, "Daily Report", transactions)

        self.assertLess(body.index("Breakfast"), body.index("Dinner"))
        self.assertIn("08:15 AM", body)
        self.assertIn("07:30 PM", body)

    def test_trigger_report_rejects_invalid_scheduler_secret(self):
        with patch("os.getenv", return_value="expected-secret"):
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(reports.trigger_report("daily", x_scheduler_token="wrong-secret"))
        self.assertEqual(ctx.exception.status_code, 403)

    def test_trigger_report_rejects_when_no_chat_ids_configured(self):
        def fake_getenv(key, default=""):
            if key == "SCHEDULER_SECRET":
                return "expected-secret"
            return default

        with patch("os.getenv", side_effect=fake_getenv):
            with patch("services.firestore.get_allowed_chat_ids", return_value=set()):
                with self.assertRaises(HTTPException) as ctx:
                    asyncio.run(reports.trigger_report("daily", x_scheduler_token="expected-secret"))
        self.assertEqual(ctx.exception.status_code, 500)

    def test_trigger_report_sends_daily_report_for_each_chat(self):
        start = datetime(2026, 5, 20, 0, 0, tzinfo=SGT)
        end = start + timedelta(days=1)

        def fake_getenv(key, default=""):
            if key == "SCHEDULER_SECRET":
                return "expected-secret"
            return default

        with (
            patch("os.getenv", side_effect=fake_getenv),
            patch("services.firestore.get_allowed_chat_ids", return_value={123, 456}),
            patch.object(reports, "_get_period_window", return_value=(start, end, "Daily Report (20/05/26)")),
            patch.object(reports, "get_transactions", return_value=[{"item": "Coffee", "amount": 4.5, "category": "Food", "timestamp": start.isoformat()}]) as mock_get_transactions,
            patch.object(reports, "_format_daily_report", return_value="daily-body"),
            patch.object(reports, "send_message", new=AsyncMock()) as mock_send,
        ):
            result = asyncio.run(reports.trigger_report("daily", x_scheduler_token="expected-secret"))

        self.assertEqual(result, {"ok": True, "period": "daily", "transactions_count": 2})
        self.assertEqual(mock_get_transactions.call_count, 2)
        self.assertEqual(mock_send.await_count, 2)
        mock_send.assert_any_await(123, "<pre>daily-body</pre>")
        mock_send.assert_any_await(456, "<pre>daily-body</pre>")

    def test_trigger_budget_report_sends_setup_guidance_when_no_budgets(self):
        def fake_getenv(key, default=""):
            if key == "SCHEDULER_SECRET":
                return "expected-secret"
            return default

        with (
            patch("os.getenv", side_effect=fake_getenv),
            patch("services.firestore.get_allowed_chat_ids", return_value={123}),
            patch.object(reports, "_format_budget_report", return_value=""),
            patch.object(reports, "send_message", new=AsyncMock()) as mock_send,
        ):
            result = asyncio.run(reports.trigger_budget_report(x_scheduler_token="expected-secret"))

        self.assertEqual(result, {"ok": True})
        self.assertIn("/set_budget", mock_send.call_args.args[1])

    def test_trigger_recurring_payments_returns_processed_count(self):
        def fake_getenv(key, default=""):
            if key == "SCHEDULER_SECRET":
                return "expected-secret"
            return default

        with (
            patch("os.getenv", side_effect=fake_getenv),
            patch.object(reports, "process_due_plans", new=AsyncMock(return_value=3)) as mock_process,
        ):
            result = asyncio.run(reports.trigger_recurring_payments(x_scheduler_token="expected-secret"))

        self.assertEqual(result, {"ok": True, "processed": 3})
        mock_process.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
