import asyncio
import sys
import types
import unittest
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

from routers.webhook import webhook


class WebhookParserInputTests(unittest.TestCase):
    def _request_for_text(self, text: str, chat_id: int = 123):
        payload = {"message": {"chat": {"id": chat_id}, "text": text}}

        class DummyRequest:
            async def json(self_nonlocal):
                return payload

        return DummyRequest()

    def test_webhook_routes_amount_first_numeric_item_input_to_handle_expense(self):
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook._handle_dashboard_account_session", new=AsyncMock(return_value=False)),
            patch("routers.webhook._handle_set_budget_session", new=AsyncMock(return_value=False)),
            patch("routers.webhook._handle_inflow_session", new=AsyncMock(return_value=False)),
            patch("routers.webhook._handle_new_goal_session", new=AsyncMock(return_value=False)),
            patch("routers.webhook._handle_edit_goal_session", new=AsyncMock(return_value=False)),
            patch("routers.webhook._handle_new_project_session", new=AsyncMock(return_value=False)),
            patch("routers.webhook._handle_edit_project_session", new=AsyncMock(return_value=False)),
            patch("routers.webhook.get_user_state", return_value=None),
            patch("routers.webhook.handle_expense", new=AsyncMock()) as mock_handle,
        ):
            result = asyncio.run(webhook(self._request_for_text("10.44 711")))

        self.assertEqual(result, {"ok": True})
        mock_handle.assert_awaited_once_with(123, "711", 10.44, transaction_date=None)

    def test_webhook_routes_amount_first_hyphenated_item_with_date(self):
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook._handle_dashboard_account_session", new=AsyncMock(return_value=False)),
            patch("routers.webhook._handle_set_budget_session", new=AsyncMock(return_value=False)),
            patch("routers.webhook._handle_inflow_session", new=AsyncMock(return_value=False)),
            patch("routers.webhook._handle_new_goal_session", new=AsyncMock(return_value=False)),
            patch("routers.webhook._handle_edit_goal_session", new=AsyncMock(return_value=False)),
            patch("routers.webhook._handle_new_project_session", new=AsyncMock(return_value=False)),
            patch("routers.webhook._handle_edit_project_session", new=AsyncMock(return_value=False)),
            patch("routers.webhook.get_user_state", return_value=None),
            patch("routers.webhook.handle_expense", new=AsyncMock()) as mock_handle,
        ):
            asyncio.run(webhook(self._request_for_text("5 7-11 130126")))

        mock_handle.assert_awaited_once_with(123, "7-11", 5.0, transaction_date="2026-01-13")

    def test_webhook_invalid_freeform_input_returns_guidance(self):
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook._handle_dashboard_account_session", new=AsyncMock(return_value=False)),
            patch("routers.webhook._handle_set_budget_session", new=AsyncMock(return_value=False)),
            patch("routers.webhook._handle_inflow_session", new=AsyncMock(return_value=False)),
            patch("routers.webhook._handle_new_goal_session", new=AsyncMock(return_value=False)),
            patch("routers.webhook._handle_edit_goal_session", new=AsyncMock(return_value=False)),
            patch("routers.webhook._handle_new_project_session", new=AsyncMock(return_value=False)),
            patch("routers.webhook._handle_edit_project_session", new=AsyncMock(return_value=False)),
            patch("routers.webhook.get_user_state", return_value=None),
            patch("routers.webhook.telegram.send_message", new=AsyncMock()) as mock_send,
        ):
            result = asyncio.run(webhook(self._request_for_text("10++ ???")))

        self.assertEqual(result, {"ok": True})
        self.assertIn("couldn't understand", mock_send.call_args.args[1].lower())

    def test_webhook_ignores_unauthorized_chat(self):
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={999}),
            patch("routers.webhook._handle_dashboard_account_session", new=AsyncMock(return_value=False)),
            patch("routers.webhook._handle_set_budget_session", new=AsyncMock(return_value=False)),
            patch("routers.webhook._handle_inflow_session", new=AsyncMock(return_value=False)),
            patch("routers.webhook._handle_new_goal_session", new=AsyncMock(return_value=False)),
            patch("routers.webhook._handle_edit_goal_session", new=AsyncMock(return_value=False)),
            patch("routers.webhook._handle_new_project_session", new=AsyncMock(return_value=False)),
            patch("routers.webhook._handle_edit_project_session", new=AsyncMock(return_value=False)),
            patch("routers.webhook.get_user_state", return_value=None),
            patch("routers.webhook.handle_expense", new=AsyncMock()) as mock_handle,
        ):
            result = asyncio.run(webhook(self._request_for_text("Coffee 10", chat_id=123)))

        self.assertEqual(result, {"ok": True})
        mock_handle.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
