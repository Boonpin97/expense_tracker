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

from routers import dashboard
from routers.webhook import webhook

SGT = timezone(timedelta(hours=8))


def _future_iso() -> str:
    return (datetime.now(SGT) + timedelta(seconds=120)).isoformat()


def _request_for_text(text: str, chat_id: int = 123):
    payload = {"message": {"chat": {"id": chat_id}, "text": text}}

    class DummyRequest:
        async def json(self_nonlocal):
            return payload

    return DummyRequest()


def _request_for_callback(data: str, chat_id: int = 123):
    payload = {
        "callback_query": {
            "id": "cbq-1",
            "data": data,
            "message": {"chat": {"id": chat_id}},
        }
    }

    class DummyRequest:
        async def json(self_nonlocal):
            return payload

    return DummyRequest()


class GoalsCommandTests(unittest.TestCase):
    def test_goals_lists_progress(self):
        goals = [
            {"id": "g1", "name": "Vacation", "target_amount": 3000.0},
            {"id": "g2", "name": "Emergency", "target_amount": 1000.0},
        ]
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_goals", return_value=goals),
            patch("routers.webhook.sum_inflows_by_goal", return_value={"g1": 1500.0}),
            patch("routers.webhook.telegram.send_message", new=AsyncMock()) as mock_send,
        ):
            result = asyncio.run(webhook(_request_for_text("/goals")))

        self.assertEqual(result, {"ok": True})
        body = mock_send.call_args.args[1]
        self.assertIn("Vacation", body)
        self.assertIn("$1,500.00 / $3,000.00 (50%)", body)
        self.assertIn("$0.00 / $1,000.00 (0%)", body)

    def test_goals_empty_state(self):
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_goals", return_value=[]),
            patch("routers.webhook.telegram.send_message", new=AsyncMock()) as mock_send,
        ):
            asyncio.run(webhook(_request_for_text("/goals")))

        self.assertIn("/new_goal", mock_send.call_args.args[1])


class NewGoalFlowTests(unittest.TestCase):
    def test_new_goal_command_starts_session(self):
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.start_session") as mock_start,
            patch("routers.webhook.telegram.send_message", new=AsyncMock()),
        ):
            asyncio.run(webhook(_request_for_text("/new_goal")))

        mock_start.assert_called_once_with(123, "new_goal", "awaiting_name")

    def test_name_step_advances_to_target(self):
        session = {"flow_type": "new_goal", "step": "awaiting_name", "payload": {}, "expires_at": _future_iso()}
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_session", return_value=session),
            patch("routers.webhook.session_expired", return_value=False),
            patch("routers.webhook.get_goals", return_value=[]),
            patch("routers.webhook.update_session") as mock_update,
            patch("routers.webhook.telegram.send_message", new=AsyncMock()) as mock_send,
        ):
            result = asyncio.run(webhook(_request_for_text("Vacation")))

        self.assertEqual(result, {"ok": True})
        mock_update.assert_called_once_with(123, step="awaiting_target", payload_updates={"name": "Vacation"})
        self.assertIn("target amount", mock_send.call_args.args[1].lower())

    def test_duplicate_name_keeps_session(self):
        session = {"flow_type": "new_goal", "step": "awaiting_name", "payload": {}, "expires_at": _future_iso()}
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_session", return_value=session),
            patch("routers.webhook.session_expired", return_value=False),
            patch("routers.webhook.get_goals", return_value=[{"id": "g1", "name": "Vacation"}]),
            patch("routers.webhook.update_session") as mock_update,
            patch("routers.webhook.clear_session") as mock_clear,
            patch("routers.webhook.telegram.send_message", new=AsyncMock()) as mock_send,
        ):
            asyncio.run(webhook(_request_for_text("vacation")))

        mock_update.assert_not_called()
        mock_clear.assert_not_called()
        self.assertIn("already exists", mock_send.call_args.args[1])

    def test_target_step_saves_goal_and_clears(self):
        session = {
            "flow_type": "new_goal",
            "step": "awaiting_target",
            "payload": {"name": "Vacation"},
            "expires_at": _future_iso(),
        }
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_session", return_value=session),
            patch("routers.webhook.session_expired", return_value=False),
            patch("routers.webhook.save_goal", return_value="goal-1") as mock_save,
            patch("routers.webhook.update_inflow_goal") as mock_tag,
            patch("routers.webhook.clear_session") as mock_clear,
            patch("routers.webhook.telegram.send_message", new=AsyncMock()) as mock_send,
        ):
            result = asyncio.run(webhook(_request_for_text("3000")))

        self.assertEqual(result, {"ok": True})
        mock_save.assert_called_once()
        goal = mock_save.call_args.args[0]
        self.assertEqual(goal.name, "Vacation")
        self.assertEqual(goal.target_amount, 3000.0)
        self.assertEqual(goal.chat_id, 123)
        mock_tag.assert_not_called()
        mock_clear.assert_called_once_with(123)
        self.assertIn("Vacation", mock_send.call_args.args[1])

    def test_invalid_target_keeps_session(self):
        session = {
            "flow_type": "new_goal",
            "step": "awaiting_target",
            "payload": {"name": "Vacation"},
            "expires_at": _future_iso(),
        }
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_session", return_value=session),
            patch("routers.webhook.session_expired", return_value=False),
            patch("routers.webhook.save_goal") as mock_save,
            patch("routers.webhook.clear_session") as mock_clear,
            patch("routers.webhook.telegram.send_message", new=AsyncMock()) as mock_send,
        ):
            asyncio.run(webhook(_request_for_text("abc")))

        mock_save.assert_not_called()
        mock_clear.assert_not_called()
        self.assertIn("positive number", mock_send.call_args.args[1].lower())

    def test_expired_session_notifies_without_saving(self):
        session = {
            "flow_type": "new_goal",
            "step": "awaiting_target",
            "payload": {"name": "Vacation"},
            "expires_at": "2000-01-01T00:00:00+08:00",
        }
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_session", return_value=session),
            patch("routers.webhook.session_expired", return_value=True),
            patch("routers.webhook.clear_session") as mock_clear,
            patch("routers.webhook.clear_user_state"),
            patch("routers.webhook.save_goal") as mock_save,
            patch("routers.webhook.telegram.send_message", new=AsyncMock()) as mock_send,
        ):
            result = asyncio.run(webhook(_request_for_text("3000")))

        self.assertEqual(result, {"ok": True})
        mock_save.assert_not_called()
        mock_clear.assert_called_once_with(123)
        self.assertIn("expired", mock_send.call_args.args[1].lower())

    def test_completion_from_income_prompt_tags_inflow(self):
        session = {
            "flow_type": "new_goal",
            "step": "awaiting_target",
            "payload": {"name": "Vacation", "inflow_id": "inflow-doc-1", "item": "Salary", "amount": 2000.0},
            "expires_at": _future_iso(),
        }
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_session", return_value=session),
            patch("routers.webhook.session_expired", return_value=False),
            patch("routers.webhook.save_goal", return_value="goal-1") as mock_save,
            patch("routers.webhook.update_inflow_goal") as mock_tag,
            patch("routers.webhook.clear_session") as mock_clear,
            patch("routers.webhook.telegram.send_message", new=AsyncMock()) as mock_send,
        ):
            asyncio.run(webhook(_request_for_text("3000")))

        mock_save.assert_called_once()
        mock_tag.assert_called_once_with("inflow-doc-1", "goal-1")
        mock_clear.assert_called_once_with(123)
        self.assertIn("Salary", mock_send.call_args.args[1])

    def test_expiry_from_income_prompt_leaves_inflow_untagged(self):
        session = {
            "flow_type": "new_goal",
            "step": "awaiting_target",
            "payload": {"name": "Vacation", "inflow_id": "inflow-doc-1"},
            "expires_at": "2000-01-01T00:00:00+08:00",
        }
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_session", return_value=session),
            patch("routers.webhook.session_expired", return_value=True),
            patch("routers.webhook.clear_session"),
            patch("routers.webhook.clear_user_state"),
            patch("routers.webhook.save_goal") as mock_save,
            patch("routers.webhook.update_inflow_goal") as mock_tag,
            patch("routers.webhook.telegram.send_message", new=AsyncMock()),
        ):
            asyncio.run(webhook(_request_for_text("3000")))

        mock_save.assert_not_called()
        mock_tag.assert_not_called()


class IncomeGoalCallbackTests(unittest.TestCase):
    def _session(self):
        return {
            "flow_type": "income_goal",
            "step": "choosing_goal",
            "payload": {"inflow_id": "inflow-doc-1", "item": "Salary", "amount": 2000.0},
            "expires_at": _future_iso(),
        }

    def test_pick_goal_tags_inflow_and_clears(self):
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_session", return_value=self._session()),
            patch("routers.webhook.session_expired", return_value=False),
            patch("routers.webhook.get_goal_by_id", return_value={"id": "g1", "name": "Vacation"}),
            patch("routers.webhook.update_inflow_goal") as mock_tag,
            patch("routers.webhook.clear_session") as mock_clear,
            patch("routers.webhook.telegram.answer_callback_query", new=AsyncMock()),
            patch("routers.webhook.telegram.send_message", new=AsyncMock()) as mock_send,
        ):
            result = asyncio.run(webhook(_request_for_callback("inflowgoal:g1")))

        self.assertEqual(result, {"ok": True})
        mock_tag.assert_called_once_with("inflow-doc-1", "g1")
        mock_clear.assert_called_once_with(123)
        self.assertIn("Vacation", mock_send.call_args.args[1])

    def test_no_goal_clears_without_tagging(self):
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_session", return_value=self._session()),
            patch("routers.webhook.session_expired", return_value=False),
            patch("routers.webhook.update_inflow_goal") as mock_tag,
            patch("routers.webhook.clear_session") as mock_clear,
            patch("routers.webhook.telegram.answer_callback_query", new=AsyncMock()),
            patch("routers.webhook.telegram.send_message", new=AsyncMock()),
        ):
            asyncio.run(webhook(_request_for_callback("inflowgoal:__none__")))

        mock_tag.assert_not_called()
        mock_clear.assert_called_once_with(123)

    def test_add_new_goal_chains_session_with_inflow_id(self):
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_session", return_value=self._session()),
            patch("routers.webhook.session_expired", return_value=False),
            patch("routers.webhook.start_session") as mock_start,
            patch("routers.webhook.telegram.answer_callback_query", new=AsyncMock()),
            patch("routers.webhook.telegram.send_message", new=AsyncMock()),
        ):
            asyncio.run(webhook(_request_for_callback("inflowgoal:__new__")))

        mock_start.assert_called_once_with(
            123,
            "new_goal",
            "awaiting_name",
            payload={"inflow_id": "inflow-doc-1", "item": "Salary", "amount": 2000.0},
        )

    def test_expired_session_rejects_without_tagging(self):
        session = self._session()
        session["expires_at"] = "2000-01-01T00:00:00+08:00"
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_session", return_value=session),
            patch("routers.webhook.session_expired", return_value=True),
            patch("routers.webhook.clear_session"),
            patch("routers.webhook.clear_user_state"),
            patch("routers.webhook.update_inflow_goal") as mock_tag,
            patch("routers.webhook.telegram.answer_callback_query", new=AsyncMock()) as mock_answer,
            patch("routers.webhook.telegram.send_message", new=AsyncMock()) as mock_send,
        ):
            asyncio.run(webhook(_request_for_callback("inflowgoal:g1")))

        mock_tag.assert_not_called()
        self.assertIn("Expired", mock_answer.call_args.args[1])
        self.assertIn("expired", mock_send.call_args.args[1].lower())


class EditGoalFlowTests(unittest.TestCase):
    def test_command_starts_session_with_keyboard(self):
        goals = [{"id": "g1", "name": "Vacation", "target_amount": 3000.0}]
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_goals", return_value=goals),
            patch("routers.webhook.start_session") as mock_start,
            patch("routers.webhook.telegram.send_goal_keyboard", new=AsyncMock()) as mock_keyboard,
        ):
            asyncio.run(webhook(_request_for_text("/edit_goal")))

        mock_start.assert_called_once_with(123, "edit_goal", "choosing_goal")
        self.assertEqual(mock_keyboard.call_args.args[2], "goaledit")

    def test_pick_goal_then_field_then_rename(self):
        session = {
            "flow_type": "edit_goal",
            "step": "awaiting_new_name",
            "payload": {"goal_id": "g1", "goal_name": "Vacation"},
            "expires_at": _future_iso(),
        }
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_session", return_value=session),
            patch("routers.webhook.session_expired", return_value=False),
            patch("routers.webhook.get_goals", return_value=[]),
            patch("routers.webhook.update_goal", return_value=True) as mock_update,
            patch("routers.webhook.update_inflow_goal") as mock_tag,
            patch("routers.webhook.clear_session") as mock_clear,
            patch("routers.webhook.telegram.send_message", new=AsyncMock()) as mock_send,
        ):
            asyncio.run(webhook(_request_for_text("Holiday")))

        mock_update.assert_called_once_with(123, "g1", name="Holiday")
        mock_tag.assert_not_called()
        mock_clear.assert_called_once_with(123)
        self.assertIn("Holiday", mock_send.call_args.args[1])

    def test_new_target_updates_goal(self):
        session = {
            "flow_type": "edit_goal",
            "step": "awaiting_new_target",
            "payload": {"goal_id": "g1", "goal_name": "Vacation"},
            "expires_at": _future_iso(),
        }
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_session", return_value=session),
            patch("routers.webhook.session_expired", return_value=False),
            patch("routers.webhook.update_goal", return_value=True) as mock_update,
            patch("routers.webhook.clear_session") as mock_clear,
            patch("routers.webhook.telegram.send_message", new=AsyncMock()),
        ):
            asyncio.run(webhook(_request_for_text("5000")))

        mock_update.assert_called_once_with(123, "g1", target_amount=5000.0)
        mock_clear.assert_called_once_with(123)

    def test_callback_field_selection_advances_step(self):
        session = {
            "flow_type": "edit_goal",
            "step": "choosing_field",
            "payload": {"goal_id": "g1", "goal_name": "Vacation"},
            "expires_at": _future_iso(),
        }
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_session", return_value=session),
            patch("routers.webhook.session_expired", return_value=False),
            patch("routers.webhook.update_session") as mock_update,
            patch("routers.webhook.telegram.answer_callback_query", new=AsyncMock()),
            patch("routers.webhook.telegram.send_message", new=AsyncMock()),
        ):
            asyncio.run(webhook(_request_for_callback("goalfield:target")))

        mock_update.assert_called_once_with(123, step="awaiting_new_target")

    def test_expired_callback_rejected(self):
        session = {
            "flow_type": "edit_goal",
            "step": "choosing_goal",
            "payload": {},
            "expires_at": "2000-01-01T00:00:00+08:00",
        }
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_session", return_value=session),
            patch("routers.webhook.session_expired", return_value=True),
            patch("routers.webhook.clear_session"),
            patch("routers.webhook.clear_user_state"),
            patch("routers.webhook.update_session") as mock_update,
            patch("routers.webhook.telegram.answer_callback_query", new=AsyncMock()) as mock_answer,
            patch("routers.webhook.telegram.send_message", new=AsyncMock()) as mock_send,
        ):
            asyncio.run(webhook(_request_for_callback("goaledit:g1")))

        mock_update.assert_not_called()
        self.assertIn("Expired", mock_answer.call_args.args[1])
        self.assertIn("expired", mock_send.call_args.args[1].lower())


class DeleteGoalFlowTests(unittest.TestCase):
    def test_pick_goal_advances_to_confirmation(self):
        session = {
            "flow_type": "delete_goal",
            "step": "choosing_goal",
            "payload": {},
            "expires_at": _future_iso(),
        }
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_session", return_value=session),
            patch("routers.webhook.session_expired", return_value=False),
            patch("routers.webhook.get_goal_by_id", return_value={"id": "g1", "name": "Vacation"}),
            patch("routers.webhook.update_session") as mock_update,
            patch("routers.webhook.telegram.answer_callback_query", new=AsyncMock()),
            patch("routers.webhook.telegram.send_goal_delete_confirm_keyboard", new=AsyncMock()) as mock_keyboard,
        ):
            asyncio.run(webhook(_request_for_callback("goaldel:g1")))

        mock_update.assert_called_once_with(
            123, step="confirming", payload_updates={"goal_id": "g1", "goal_name": "Vacation"}
        )
        mock_keyboard.assert_awaited_once()

    def test_confirm_yes_deletes_goal_only(self):
        session = {
            "flow_type": "delete_goal",
            "step": "confirming",
            "payload": {"goal_id": "g1", "goal_name": "Vacation"},
            "expires_at": _future_iso(),
        }
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_session", return_value=session),
            patch("routers.webhook.session_expired", return_value=False),
            patch("routers.webhook.delete_goal", return_value=True) as mock_delete,
            patch("routers.webhook.update_inflow_goal") as mock_tag,
            patch("routers.webhook.clear_session") as mock_clear,
            patch("routers.webhook.telegram.answer_callback_query", new=AsyncMock()),
            patch("routers.webhook.telegram.send_message", new=AsyncMock()) as mock_send,
        ):
            asyncio.run(webhook(_request_for_callback("goaldelconfirm:yes")))

        mock_delete.assert_called_once_with(123, "g1")
        mock_tag.assert_not_called()
        mock_clear.assert_called_once_with(123)
        self.assertIn("unchanged", mock_send.call_args.args[1])

    def test_confirm_no_cancels(self):
        session = {
            "flow_type": "delete_goal",
            "step": "confirming",
            "payload": {"goal_id": "g1", "goal_name": "Vacation"},
            "expires_at": _future_iso(),
        }
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_session", return_value=session),
            patch("routers.webhook.session_expired", return_value=False),
            patch("routers.webhook.delete_goal") as mock_delete,
            patch("routers.webhook.clear_session") as mock_clear,
            patch("routers.webhook.telegram.answer_callback_query", new=AsyncMock()),
            patch("routers.webhook.telegram.send_message", new=AsyncMock()),
        ):
            asyncio.run(webhook(_request_for_callback("goaldelconfirm:no")))

        mock_delete.assert_not_called()
        mock_clear.assert_called_once_with(123)

    def test_expired_confirmation_rejected(self):
        session = {
            "flow_type": "delete_goal",
            "step": "confirming",
            "payload": {"goal_id": "g1", "goal_name": "Vacation"},
            "expires_at": "2000-01-01T00:00:00+08:00",
        }
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_session", return_value=session),
            patch("routers.webhook.session_expired", return_value=True),
            patch("routers.webhook.clear_session"),
            patch("routers.webhook.clear_user_state"),
            patch("routers.webhook.delete_goal") as mock_delete,
            patch("routers.webhook.telegram.answer_callback_query", new=AsyncMock()) as mock_answer,
            patch("routers.webhook.telegram.send_message", new=AsyncMock()),
        ):
            asyncio.run(webhook(_request_for_callback("goaldelconfirm:yes")))

        mock_delete.assert_not_called()
        self.assertIn("Expired", mock_answer.call_args.args[1])


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


class GoalFirestoreTests(unittest.TestCase):
    def test_sum_inflows_by_goal_groups_and_filters(self):
        from services import firestore

        docs = [
            _FakeDoc("a", {"chat_id": 123, "amount": 100.0, "goal_id": "g1"}),
            _FakeDoc("b", {"chat_id": 123, "amount": 50.0, "goal_id": "g1"}),
            _FakeDoc("c", {"chat_id": 123, "amount": 25.0, "goal_id": "g2"}),
            _FakeDoc("d", {"chat_id": 123, "amount": 75.0}),
            _FakeDoc("e", {"chat_id": 999, "amount": 500.0, "goal_id": "g1"}),
        ]
        with patch.object(firestore, "get_db", return_value=_FakeDB(docs)):
            sums = firestore.sum_inflows_by_goal(123)

        self.assertEqual(sums, {"g1": 150.0, "g2": 25.0})


class DashboardGoalsTests(unittest.TestCase):
    def test_list_goals_merges_accumulated(self):
        goals = [
            {"id": "g1", "name": "Vacation", "target_amount": 3000.0},
            {"id": "g2", "name": "Emergency", "target_amount": 1000.0},
        ]
        with (
            patch.object(dashboard, "_require_session", return_value={"chat_id": 123}),
            patch.object(dashboard, "get_goals", return_value=goals),
            patch.object(dashboard, "sum_inflows_by_goal", return_value={"g1": 1500.0}),
        ):
            result = asyncio.run(dashboard.list_dashboard_goals(SimpleNamespace(cookies={}, headers={})))

        self.assertEqual(result["goals"][0]["accumulated"], 1500.0)
        self.assertEqual(result["goals"][1]["accumulated"], 0.0)
        self.assertEqual(result["goals"][0]["name"], "Vacation")


if __name__ == "__main__":
    unittest.main()
