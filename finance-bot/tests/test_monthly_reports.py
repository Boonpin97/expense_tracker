import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
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

if "fastapi" not in sys.modules:
    fastapi_stub = types.ModuleType("fastapi")

    class APIRouter:
        def post(self, *_args, **_kwargs):
            def decorator(fn):
                return fn
            return decorator

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

    fastapi_stub.APIRouter = APIRouter
    fastapi_stub.HTTPException = HTTPException
    fastapi_stub.Header = Header
    fastapi_stub.Query = Query
    fastapi_stub.Request = Request
    sys.modules["fastapi"] = fastapi_stub

from routers.webhook import _build_monthly_report_buttons, _get_month_window, _parse_month_input_or_none
from services import telegram

SGT = timezone(timedelta(hours=8))


class MonthlyReportHelpersTests(unittest.TestCase):
    def test_parse_month_input_accepts_mmyy(self):
        self.assertEqual(_parse_month_input_or_none("0126"), (2026, 1))
        self.assertIsNone(_parse_month_input_or_none("1326"))
        self.assertIsNone(_parse_month_input_or_none("01-26"))

    def test_get_month_window_returns_calendar_month_range(self):
        start, end, label = _get_month_window(2026, 1)
        self.assertEqual(start, datetime(2026, 1, 1, tzinfo=SGT))
        self.assertEqual(end, datetime(2026, 2, 1, tzinfo=SGT))
        self.assertEqual(label, "Monthly Report (Jan 2026)")

    def test_build_monthly_report_buttons_uses_earlier_then_past_three_then_current(self):
        now = datetime(2026, 5, 3, tzinfo=SGT)
        buttons = _build_monthly_report_buttons(now)
        self.assertEqual(
            buttons,
            [
                ("Earlier months", "monthrep:earlier"),
                ("Apr 2026", "monthrep:202604"),
                ("Mar 2026", "monthrep:202603"),
                ("Feb 2026", "monthrep:202602"),
                ("Current month", "monthrep:202605"),
            ],
        )

    def test_monthly_report_keyboard_adds_expiry_timestamp(self):
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
                telegram.send_monthly_report_keyboard(
                    123,
                    [("Current month", "monthrep:202605"), ("Earlier months", "monthrep:earlier")],
                    "Choose a month:",
                )
            )
        finally:
            telegram.httpx.AsyncClient = original_client

        keyboard = captured["reply_markup"]["inline_keyboard"]
        self.assertRegex(keyboard[0][0]["callback_data"], r"^monthrep:202605\|")
        self.assertRegex(keyboard[0][1]["callback_data"], r"^monthrep:earlier\|")

    def test_daily_report_keyboard_adds_expiry_timestamp(self):
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

            asyncio.run(telegram.send_daily_report_keyboard(123, "Choose a daily report:"))
        finally:
            telegram.httpx.AsyncClient = original_client

        keyboard = captured["reply_markup"]["inline_keyboard"][0]
        self.assertRegex(keyboard[0]["callback_data"], r"^dailyrep:today\|")
        self.assertRegex(keyboard[1]["callback_data"], r"^dailyrep:past\|")


if __name__ == "__main__":
    unittest.main()
