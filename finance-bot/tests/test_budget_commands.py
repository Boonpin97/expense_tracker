import sys
import types
import unittest
import asyncio
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

from routers.webhook import (
    _format_budget_list,
    _parse_budget_command_or_none,
    _parse_remove_budget_command_or_none,
    webhook,
)


class BudgetCommandTests(unittest.TestCase):
    def test_parse_budget_command_accepts_category_with_spaces(self):
        self.assertEqual(
            _parse_budget_command_or_none("/set_budget Food & Drink 300"),
            ("Food & Drink", 300.0),
        )
        self.assertEqual(
            _parse_budget_command_or_none("/set_budget Transport $45.50"),
            ("Transport", 45.50),
        )

    def test_parse_budget_command_rejects_invalid_input(self):
        self.assertIsNone(_parse_budget_command_or_none("/set_budget"))
        self.assertIsNone(_parse_budget_command_or_none("/set_budget Food nope"))
        self.assertIsNone(_parse_budget_command_or_none("/set_budget Food 0"))

    def test_parse_remove_budget_command(self):
        self.assertEqual(
            _parse_remove_budget_command_or_none("/remove_budget Food & Drink"),
            "Food & Drink",
        )
        self.assertIsNone(_parse_remove_budget_command_or_none("/remove_budget"))

    def test_format_budget_list(self):
        with patch("routers.webhook.get_budgets", return_value={"Food & Drink": 300.0, "Transport": 50.0}), patch(
            "routers.webhook.get_category_list",
            return_value=[
                {"name": "Food & Drink", "emoji": "🍔"},
                {"name": "Transport", "emoji": "🚗"},
            ],
        ):
            message = _format_budget_list(123)

        self.assertIn("<b>Monthly Budgets</b>", message)
        self.assertIn("🍔 Food & Drink: <b>$300.00</b>", message)
        self.assertIn("🚗 Transport: <b>$50.00</b>", message)

    def test_remove_budget_deletes_only_requested_category(self):
        class DummyDoc:
            def __init__(self):
                self._data = {"Food & Drink": 300.0, "Transport": 50.0}
                self.exists = True
                self.deleted = False

            def get(self):
                return self

            def to_dict(self):
                return dict(self._data)

            def set(self, data):
                self._data = dict(data)

            def delete(self):
                self.deleted = True

        class DummyCollection:
            def __init__(self, doc):
                self._doc = doc

            def document(self, _doc_id):
                return self._doc

        class DummyDB:
            def __init__(self, doc):
                self._doc = doc

            def collection(self, _name):
                return DummyCollection(self._doc)

        from services.firestore import remove_budget

        dummy_doc = DummyDoc()
        with patch("services.firestore.get_db", return_value=DummyDB(dummy_doc)):
            removed = remove_budget(123, "Food & Drink")

        self.assertTrue(removed)
        self.assertEqual(dummy_doc._data, {"Transport": 50.0})
        self.assertFalse(dummy_doc.deleted)

    def test_remove_budget_deletes_document_when_last_budget_removed(self):
        class DummyDoc:
            def __init__(self):
                self._data = {"Food & Drink": 300.0}
                self.exists = True
                self.deleted = False

            def get(self):
                return self

            def to_dict(self):
                return dict(self._data)

            def set(self, data):
                self._data = dict(data)

            def delete(self):
                self.deleted = True

        class DummyCollection:
            def __init__(self, doc):
                self._doc = doc

            def document(self, _doc_id):
                return self._doc

        class DummyDB:
            def __init__(self, doc):
                self._doc = doc

            def collection(self, _name):
                return DummyCollection(self._doc)

        from services.firestore import remove_budget

        dummy_doc = DummyDoc()
        with patch("services.firestore.get_db", return_value=DummyDB(dummy_doc)):
            removed = remove_budget(123, "Food & Drink")

        self.assertTrue(removed)
        self.assertTrue(dummy_doc.deleted)

    def test_budget_report_command_sends_formatted_report(self):
        payload = {"message": {"chat": {"id": 123}, "text": "/budget_report"}}

        class DummyRequest:
            async def json(self):
                return payload

        with patch("routers.webhook._get_allowed_chat_ids", return_value={123}), patch(
            "routers.webhook._format_budget_report",
            return_value="Budget body",
        ), patch(
            "routers.webhook.telegram.send_message",
            new=AsyncMock(),
        ) as send_message:
            asyncio.run(webhook(DummyRequest()))

        send_message.assert_awaited_once_with(123, "<pre>Budget body</pre>")

    def test_set_budget_command_starts_interactive_flow(self):
        payload = {"message": {"chat": {"id": 123}, "text": "/set_budget"}}

        class DummyRequest:
            async def json(self):
                return payload

        with patch("routers.webhook._get_allowed_chat_ids", return_value={123}), patch(
            "routers.webhook.start_session",
        ) as start_session, patch(
            "routers.webhook.telegram.send_budget_category_keyboard",
            new=AsyncMock(),
        ) as send_budget_category_keyboard:
            asyncio.run(webhook(DummyRequest()))

        start_session.assert_called_once_with(123, "set_budget", "choosing_category")
        send_budget_category_keyboard.assert_awaited_once()

    def test_set_budget_category_callback_prompts_for_amount(self):
        payload = {
            "callback_query": {
                "id": "cb-1",
                "data": "budgetcat:Food & Drink",
                "message": {"chat": {"id": 123}},
            }
        }

        class DummyRequest:
            async def json(self):
                return payload

        with patch("routers.webhook._get_allowed_chat_ids", return_value={123}), patch(
            "routers.webhook.get_session",
            return_value={"flow_type": "set_budget", "step": "choosing_category", "payload": {}, "expires_at": "2999-01-01T00:00:00+08:00"},
        ), patch(
            "routers.webhook.get_category_list",
            return_value=[{"name": "Food & Drink"}],
        ), patch(
            "routers.webhook.update_session",
        ) as update_session, patch(
            "routers.webhook.telegram.answer_callback_query",
            new=AsyncMock(),
        ) as answer_callback_query, patch(
            "routers.webhook.telegram.send_message",
            new=AsyncMock(),
        ) as send_message:
            asyncio.run(webhook(DummyRequest()))

        update_session.assert_called_once_with(
            123,
            step="awaiting_amount",
            payload_updates={"selected_category": "Food & Drink"},
        )
        answer_callback_query.assert_awaited_once_with("cb-1", "")
        send_message.assert_awaited_once_with(
            123,
            "Send the monthly budget for <b>Food & Drink</b>, for example <code>300</code>.",
        )

    def test_set_budget_amount_entry_saves_budget_and_reprompts(self):
        payload = {"message": {"chat": {"id": 123}, "text": "300"}}

        class DummyRequest:
            async def json(self):
                return payload

        session = {
            "flow_type": "set_budget",
            "step": "awaiting_amount",
            "payload": {"selected_category": "Food & Drink"},
            "expires_at": "2999-01-01T00:00:00+08:00",
        }

        with patch("routers.webhook._get_allowed_chat_ids", return_value={123}), patch(
            "routers.webhook.get_session",
            return_value=session,
        ), patch(
            "routers.webhook.set_budget",
        ) as set_budget, patch(
            "routers.webhook.update_session",
        ) as update_session, patch(
            "routers.webhook.telegram.send_message",
            new=AsyncMock(),
        ) as send_message, patch(
            "routers.webhook.telegram.send_budget_category_keyboard",
            new=AsyncMock(),
        ) as send_budget_category_keyboard:
            asyncio.run(webhook(DummyRequest()))

        set_budget.assert_called_once_with(123, "Food & Drink", 300.0)
        update_session.assert_called_once_with(
            123,
            step="choosing_category",
            payload_updates={"selected_category": ""},
        )
        self.assertEqual(send_message.await_count, 1)
        send_message.assert_awaited_once_with(
            123,
            "✅ Monthly budget for <b>Food & Drink</b> set to <b>$300.00</b>.",
        )
        send_budget_category_keyboard.assert_awaited_once_with(
            123,
            "Choose another category to set a monthly budget for, or tap Done.",
        )


if __name__ == "__main__":
    unittest.main()
