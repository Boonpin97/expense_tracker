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


def _future_iso():
    return (datetime.now(SGT) + timedelta(minutes=10)).isoformat()


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


class ProjectFirestoreTests(unittest.TestCase):
    def test_sum_inflows_by_project_is_all_time(self):
        from services import firestore

        docs = [
            _FakeDoc("a", {"chat_id": 123, "amount": 100.0, "project_id": "p1", "timestamp": "2026-01-05T00:00:00+08:00"}),
            _FakeDoc("b", {"chat_id": 123, "amount": 50.0, "project_id": "p1", "timestamp": "2026-06-30T00:00:00+08:00"}),
            _FakeDoc("c", {"chat_id": 123, "amount": 25.0, "goal_id": "g1"}),  # goal-tagged, not a project
            _FakeDoc("d", {"chat_id": 999, "amount": 500.0, "project_id": "p1"}),
        ]
        with patch.object(firestore, "get_db", return_value=_FakeDB(docs)):
            sums = firestore.sum_inflows_by_project(123)

        # All-time across months; other users and goal-tagged inflows excluded.
        self.assertEqual(sums, {"p1": 150.0})


class ProjectCommandTests(unittest.TestCase):
    def test_projects_lists_initial_plus_inflows(self):
        projects = [
            {
                "id": "p1",
                "name": "House",
                "target_amount": 50000.0,
                "initial_amount": 1000.0,
                "deadline": "2027-01-01",
            }
        ]
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_projects", return_value=projects),
            patch("routers.webhook.sum_inflows_by_project", return_value={"p1": 500.0}),
            patch("routers.webhook.telegram.send_message", new=AsyncMock()) as mock_send,
        ):
            result = asyncio.run(webhook(_request_for_text("/projects")))

        self.assertEqual(result, {"ok": True})
        body = mock_send.call_args.args[1]
        self.assertIn("House", body)
        self.assertIn("$1,500.00 / $50,000.00", body)


class NewProjectFlowTests(unittest.TestCase):
    def test_new_projects_command_starts_session(self):
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.start_session") as mock_start,
            patch("routers.webhook.telegram.send_message", new=AsyncMock()),
        ):
            asyncio.run(webhook(_request_for_text("/new_projects")))

        mock_start.assert_called_once_with(123, "new_project", "awaiting_name")

    def test_new_project_flow_saves_all_fields(self):
        session = {
            "flow_type": "new_project",
            "step": "awaiting_deadline",
            "payload": {
                "name": "House",
                "emoji": "🏠",
                "target_amount": 50000.0,
                "initial_amount": 1000.0,
            },
            "expires_at": _future_iso(),
        }
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_session", return_value=session),
            patch("routers.webhook.session_expired", return_value=False),
            patch("routers.webhook.save_project", return_value="p1") as mock_save,
            patch("routers.webhook.clear_session") as mock_clear,
            patch("routers.webhook.telegram.send_message", new=AsyncMock()) as mock_send,
        ):
            asyncio.run(webhook(_request_for_text("010127")))

        saved = mock_save.call_args.args[0]
        self.assertEqual(saved.name, "House")
        self.assertEqual(saved.target_amount, 50000.0)
        self.assertEqual(saved.initial_amount, 1000.0)
        self.assertEqual(saved.deadline, "2027-01-01")
        self.assertEqual(saved.emoji, "🏠")
        mock_clear.assert_called_once_with(123)
        self.assertIn("House", mock_send.call_args.args[1])

    def test_invalid_initial_amount_keeps_session(self):
        session = {
            "flow_type": "new_project",
            "step": "awaiting_initial",
            "payload": {"name": "House", "emoji": "🏠", "target_amount": 50000.0},
            "expires_at": _future_iso(),
        }
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_session", return_value=session),
            patch("routers.webhook.session_expired", return_value=False),
            patch("routers.webhook.update_session") as mock_update,
            patch("routers.webhook.telegram.send_message", new=AsyncMock()) as mock_send,
        ):
            asyncio.run(webhook(_request_for_text("-1")))

        mock_update.assert_not_called()
        self.assertIn("zero or more", mock_send.call_args.args[1])


class EditProjectFlowTests(unittest.TestCase):
    def test_command_starts_session_with_keyboard(self):
        projects = [{"id": "p1", "name": "House", "target_amount": 50000.0}]
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_projects", return_value=projects),
            patch("routers.webhook.start_session") as mock_start,
            patch("routers.webhook.telegram.send_project_keyboard", new=AsyncMock()) as mock_keyboard,
        ):
            asyncio.run(webhook(_request_for_text("/edit_projects")))

        mock_start.assert_called_once_with(123, "edit_project", "choosing_project")
        self.assertEqual(mock_keyboard.call_args.args[2], "projectedit")

    def test_callback_field_selection_advances_to_initial_step(self):
        session = {
            "flow_type": "edit_project",
            "step": "choosing_field",
            "payload": {"project_id": "p1", "project_name": "House"},
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
            asyncio.run(webhook(_request_for_callback("projectfield:initial")))

        mock_update.assert_called_once_with(123, step="awaiting_new_initial")

    def test_new_initial_updates_project(self):
        session = {
            "flow_type": "edit_project",
            "step": "awaiting_new_initial",
            "payload": {"project_id": "p1", "project_name": "House"},
            "expires_at": _future_iso(),
        }
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_session", return_value=session),
            patch("routers.webhook.session_expired", return_value=False),
            patch("routers.webhook.update_project", return_value=True) as mock_update,
            patch("routers.webhook.clear_session") as mock_clear,
            patch("routers.webhook.telegram.send_message", new=AsyncMock()),
        ):
            asyncio.run(webhook(_request_for_text("1500")))

        mock_update.assert_called_once_with(123, "p1", initial_amount=1500.0)
        mock_clear.assert_called_once_with(123)

    def test_new_deadline_updates_project(self):
        session = {
            "flow_type": "edit_project",
            "step": "awaiting_new_deadline",
            "payload": {"project_id": "p1", "project_name": "House"},
            "expires_at": _future_iso(),
        }
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_session", return_value=session),
            patch("routers.webhook.session_expired", return_value=False),
            patch("routers.webhook.update_project", return_value=True) as mock_update,
            patch("routers.webhook.clear_session") as mock_clear,
            patch("routers.webhook.telegram.send_message", new=AsyncMock()),
        ):
            asyncio.run(webhook(_request_for_text("010127")))

        mock_update.assert_called_once_with(123, "p1", deadline="2027-01-01")
        mock_clear.assert_called_once_with(123)


class DeleteProjectFlowTests(unittest.TestCase):
    def test_pick_project_advances_to_confirmation(self):
        session = {
            "flow_type": "delete_project",
            "step": "choosing_project",
            "payload": {},
            "expires_at": _future_iso(),
        }
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_session", return_value=session),
            patch("routers.webhook.session_expired", return_value=False),
            patch("routers.webhook.get_project_by_id", return_value={"id": "p1", "name": "House"}),
            patch("routers.webhook.update_session") as mock_update,
            patch("routers.webhook.telegram.answer_callback_query", new=AsyncMock()),
            patch("routers.webhook.telegram.send_project_delete_confirm_keyboard", new=AsyncMock()) as mock_keyboard,
        ):
            asyncio.run(webhook(_request_for_callback("projectdel:p1")))

        mock_update.assert_called_once_with(
            123, step="confirming", payload_updates={"project_id": "p1", "project_name": "House"}
        )
        mock_keyboard.assert_awaited_once()

    def test_confirm_yes_deletes_project_only(self):
        session = {
            "flow_type": "delete_project",
            "step": "confirming",
            "payload": {"project_id": "p1", "project_name": "House"},
            "expires_at": _future_iso(),
        }
        with (
            patch("routers.webhook._get_allowed_chat_ids", return_value={123}),
            patch("routers.webhook.get_session", return_value=session),
            patch("routers.webhook.session_expired", return_value=False),
            patch("routers.webhook.delete_project", return_value=True) as mock_delete,
            patch("routers.webhook.clear_session") as mock_clear,
            patch("routers.webhook.telegram.answer_callback_query", new=AsyncMock()),
            patch("routers.webhook.telegram.send_message", new=AsyncMock()) as mock_send,
        ):
            asyncio.run(webhook(_request_for_callback("projectdelconfirm:yes")))

        mock_delete.assert_called_once_with(123, "p1")
        mock_clear.assert_called_once_with(123)
        self.assertIn("unchanged", mock_send.call_args.args[1])


class DashboardProjectCrudTests(unittest.TestCase):
    def _req(self):
        return SimpleNamespace(cookies={}, headers={})

    def test_list_projects_merges_accumulated(self):
        projects = [
            {
                "id": "p1",
                "name": "House",
                "target_amount": 50000.0,
                "initial_amount": 300.0,
                "deadline": "2027-01-01",
            },
            {"id": "p2", "name": "Wedding", "target_amount": 20000.0, "deadline": "2026-12-01"},
        ]
        with (
            patch.object(dashboard, "_require_session", return_value={"chat_id": 123}),
            patch.object(dashboard, "get_projects", return_value=projects),
            patch.object(dashboard, "sum_inflows_by_project", return_value={"p1": 1200.0}),
        ):
            result = asyncio.run(dashboard.list_dashboard_projects(self._req()))

        self.assertEqual(result["projects"][0]["accumulated"], 1500.0)
        self.assertEqual(result["projects"][0]["initial_amount"], 300.0)
        self.assertEqual(result["projects"][1]["accumulated"], 0.0)
        self.assertEqual(result["projects"][1]["initial_amount"], 0.0)
        self.assertEqual(result["projects"][0]["deadline"], "2027-01-01")

    def test_create_project_saves_with_deadline(self):
        with (
            patch.object(dashboard, "_require_session", return_value={"chat_id": 123}),
            patch.object(dashboard, "save_project", return_value="p-new") as mock_save,
        ):
            payload = dashboard.ProjectCreateRequest(
                name="House",
                target_amount=50000.0,
                initial_amount=1000.0,
                deadline="2027-01-01",
                emoji="🏠",
            )
            result = asyncio.run(dashboard.create_dashboard_project(payload, self._req()))

        self.assertEqual(result, {"ok": True, "id": "p-new"})
        saved = mock_save.call_args.args[0]
        self.assertEqual(
            (saved.name, saved.target_amount, saved.initial_amount, saved.deadline),
            ("House", 50000.0, 1000.0, "2027-01-01"),
        )

    def test_create_project_rejects_negative_initial_amount(self):
        with patch.object(dashboard, "_require_session", return_value={"chat_id": 123}):
            payload = dashboard.ProjectCreateRequest(
                name="House", target_amount=50000.0, initial_amount=-1.0, deadline="2027-01-01"
            )
            with self.assertRaises(Exception):
                asyncio.run(dashboard.create_dashboard_project(payload, self._req()))

    def test_create_project_requires_deadline(self):
        with patch.object(dashboard, "_require_session", return_value={"chat_id": 123}):
            payload = dashboard.ProjectCreateRequest(name="House", target_amount=50000.0, deadline="")
            with self.assertRaises(Exception):
                asyncio.run(dashboard.create_dashboard_project(payload, self._req()))

    def test_update_project(self):
        with (
            patch.object(dashboard, "_require_session", return_value={"chat_id": 123}),
            patch.object(dashboard, "update_project", return_value=True) as mock_update,
        ):
            payload = dashboard.ProjectUpdateRequest(target_amount=60000.0, initial_amount=500.0)
            result = asyncio.run(dashboard.update_dashboard_project("p1", payload, self._req()))

        self.assertEqual(result, {"ok": True})
        mock_update.assert_called_once_with(123, "p1", target_amount=60000.0, initial_amount=500.0)

    def test_update_project_rejects_negative_initial_amount(self):
        with patch.object(dashboard, "_require_session", return_value={"chat_id": 123}):
            payload = dashboard.ProjectUpdateRequest(initial_amount=-1.0)
            with self.assertRaises(Exception):
                asyncio.run(dashboard.update_dashboard_project("p1", payload, self._req()))

    def test_delete_project(self):
        with (
            patch.object(dashboard, "_require_session", return_value={"chat_id": 123}),
            patch.object(dashboard, "delete_project", return_value=True) as mock_del,
        ):
            result = asyncio.run(dashboard.delete_dashboard_project("p1", self._req()))

        self.assertEqual(result, {"ok": True})
        mock_del.assert_called_once_with(123, "p1")

    def test_move_project(self):
        with (
            patch.object(dashboard, "_require_session", return_value={"chat_id": 123}),
            patch.object(dashboard, "move_project", return_value=True) as mock_move,
        ):
            payload = dashboard.MoveRequest(direction=1)
            result = asyncio.run(dashboard.move_dashboard_project("p1", payload, self._req()))

        self.assertEqual(result, {"ok": True})
        mock_move.assert_called_once_with(123, "p1", 1)


class DashboardInflowTargetTests(unittest.TestCase):
    def _req(self):
        return SimpleNamespace(cookies={}, headers={})

    def test_create_inflow_with_goal(self):
        with (
            patch.object(dashboard, "_require_session", return_value={"chat_id": 123}),
            patch.object(dashboard, "get_goal_by_id", return_value={"id": "g1"}),
            patch.object(dashboard, "save_inflow") as mock_save,
        ):
            payload = dashboard.InflowCreateRequest(
                item="Salary", amount=2000.0, timestamp="2026-06-01T00:00:00+08:00", goal_id="g1"
            )
            result = asyncio.run(dashboard.create_dashboard_inflow(payload, self._req()))

        self.assertEqual(result, {"ok": True})
        saved = mock_save.call_args.args[0]
        self.assertEqual(saved.goal_id, "g1")
        self.assertIsNone(saved.project_id)

    def test_create_inflow_with_project(self):
        with (
            patch.object(dashboard, "_require_session", return_value={"chat_id": 123}),
            patch.object(dashboard, "get_project_by_id", return_value={"id": "p1"}),
            patch.object(dashboard, "save_inflow") as mock_save,
        ):
            payload = dashboard.InflowCreateRequest(
                item="Bonus", amount=500.0, timestamp="2026-06-01T00:00:00+08:00", project_id="p1"
            )
            asyncio.run(dashboard.create_dashboard_inflow(payload, self._req()))

        saved = mock_save.call_args.args[0]
        self.assertEqual(saved.project_id, "p1")
        self.assertIsNone(saved.goal_id)

    def test_create_inflow_accepts_goal_and_project(self):
        with (
            patch.object(dashboard, "_require_session", return_value={"chat_id": 123}),
            patch.object(dashboard, "get_goal_by_id", return_value={"id": "g1"}),
            patch.object(dashboard, "get_project_by_id", return_value={"id": "p1"}),
            patch.object(dashboard, "save_inflow") as mock_save,
        ):
            payload = dashboard.InflowCreateRequest(
                item="X", amount=10.0, timestamp="2026-06-01T00:00:00+08:00", goal_id="g1", project_id="p1"
            )
            asyncio.run(dashboard.create_dashboard_inflow(payload, self._req()))

        saved = mock_save.call_args.args[0]
        self.assertEqual(saved.goal_id, "g1")
        self.assertEqual(saved.project_id, "p1")

    def test_create_inflow_rejects_missing_goal(self):
        with (
            patch.object(dashboard, "_require_session", return_value={"chat_id": 123}),
            patch.object(dashboard, "get_goal_by_id", return_value=None),
        ):
            payload = dashboard.InflowCreateRequest(
                item="X", amount=10.0, timestamp="2026-06-01T00:00:00+08:00", goal_id="ghost"
            )
            with self.assertRaises(Exception):
                asyncio.run(dashboard.create_dashboard_inflow(payload, self._req()))


if __name__ == "__main__":
    unittest.main()
