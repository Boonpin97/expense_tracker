import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services import interaction_sessions


SGT = timezone(timedelta(hours=8))


class InteractionSessionTests(unittest.TestCase):
    def setUp(self):
        self.store = {}

    def _save(self, session):
        self.store[session.chat_id] = session.model_dump()

    def _get(self, chat_id):
        return self.store.get(chat_id)

    def _update(self, chat_id, **fields):
        self.store[chat_id].update(fields)

    def _delete(self, chat_id):
        self.store.pop(chat_id, None)

    def _patch_firestore(self):
        return patch.multiple(
            interaction_sessions.firestore,
            save_interaction_session=self._save,
            get_interaction_session=self._get,
            update_interaction_session=self._update,
            delete_interaction_session=self._delete,
        )

    def test_start_session_sets_expiry(self):
        now = datetime(2026, 5, 4, 12, 0, tzinfo=SGT)
        with self._patch_firestore(), patch.object(interaction_sessions, "_now", return_value=now):
            session = interaction_sessions.start_session(
                123,
                "dashboard_account",
                "awaiting_username",
                expiry_seconds=180,
            )

        self.assertEqual(session["chat_id"], 123)
        self.assertEqual(session["flow_type"], "dashboard_account")
        self.assertEqual(session["step"], "awaiting_username")
        self.assertEqual(session["expires_at"], (now + timedelta(seconds=180)).isoformat())
        self.assertEqual(self.store[123], session)

    def test_expiry_detection(self):
        now = datetime(2026, 5, 4, 12, 0, tzinfo=SGT)
        active = {"expires_at": (now + timedelta(seconds=1)).isoformat()}
        expired = {"expires_at": (now - timedelta(seconds=1)).isoformat()}

        with patch.object(interaction_sessions, "_now", return_value=now):
            self.assertFalse(interaction_sessions.is_expired(active))
            self.assertTrue(interaction_sessions.is_expired(expired))
            self.assertTrue(interaction_sessions.is_expired(None))
            self.assertTrue(interaction_sessions.is_expired({}))

    def test_update_session_merges_payload(self):
        now = datetime(2026, 5, 4, 12, 0, tzinfo=SGT)
        with self._patch_firestore(), patch.object(interaction_sessions, "_now", return_value=now):
            interaction_sessions.start_session(
                123,
                "dashboard_account",
                "awaiting_username",
                payload={"attempts": 1},
            )
            updated = interaction_sessions.update_session(
                123,
                step="awaiting_password",
                payload_updates={"username": "alice"},
            )

        self.assertEqual(updated["step"], "awaiting_password")
        self.assertEqual(updated["payload"], {"attempts": 1, "username": "alice"})
        self.assertEqual(self.store[123]["payload"], {"attempts": 1, "username": "alice"})

    def test_clear_session_removes_record(self):
        now = datetime(2026, 5, 4, 12, 0, tzinfo=SGT)
        with self._patch_firestore(), patch.object(interaction_sessions, "_now", return_value=now):
            interaction_sessions.start_session(123, "dashboard_account", "awaiting_username")
            interaction_sessions.clear_session(123)

        self.assertNotIn(123, self.store)


if __name__ == "__main__":
    unittest.main()
