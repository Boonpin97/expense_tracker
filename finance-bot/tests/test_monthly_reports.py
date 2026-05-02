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

    def test_build_monthly_report_buttons_uses_current_and_last_three_months(self):
        now = datetime(2026, 5, 3, tzinfo=SGT)
        buttons = _build_monthly_report_buttons(now)
        self.assertEqual(
            buttons,
            [
                ("Current month", "monthrep:202605"),
                ("April", "monthrep:202604"),
                ("March", "monthrep:202603"),
                ("February", "monthrep:202602"),
                ("Earlier months", "monthrep:earlier"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
