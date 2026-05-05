import asyncio
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
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


if __name__ == "__main__":
    unittest.main()
