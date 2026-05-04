import sys
import types
import unittest
from pathlib import Path
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

    firestore_mod.Client = DummyClient
    cloud_mod.firestore = firestore_mod
    google_mod.cloud = cloud_mod
    sys.modules["google"] = google_mod
    sys.modules["google.cloud"] = cloud_mod
    sys.modules["google.cloud.firestore"] = firestore_mod

from services import firestore


class _FakeDocument:
    def __init__(self, exists: bool, data: dict | None):
        self.exists = exists
        self._data = data or {}

    def to_dict(self):
        return dict(self._data)


class _FakeDocumentRef:
    def __init__(self, collection_name: str, doc_id: str, store: dict):
        self.collection_name = collection_name
        self.doc_id = doc_id
        self.store = store

    def get(self):
        data = self.store.get((self.collection_name, self.doc_id))
        return _FakeDocument(data is not None, data)


class _FakeCollection:
    def __init__(self, collection_name: str, store: dict):
        self.collection_name = collection_name
        self.store = store

    def document(self, doc_id: str):
        return _FakeDocumentRef(self.collection_name, doc_id, self.store)


class _FakeDb:
    def __init__(self, store: dict):
        self.store = store

    def collection(self, collection_name: str):
        return _FakeCollection(collection_name, self.store)


class FirestoreWebAccountLookupTests(unittest.TestCase):
    def test_get_account_by_username_returns_account(self):
        store = {
            ("web_usernames", "alice"): {"chat_id": "123"},
            ("web_accounts", "123"): {"username": "Alice", "password_hash": "hash"},
        }
        with patch.object(firestore, "get_db", return_value=_FakeDb(store)):
            account = firestore.get_account_by_username("alice")

        self.assertIsNotNone(account)
        self.assertEqual(account["chat_id"], 123)
        self.assertEqual(account["username"], "Alice")

    def test_get_account_by_username_ignores_invalid_username_mapping(self):
        store = {
            ("web_usernames", "broken"): {"chat_id": None},
        }
        with patch.object(firestore, "get_db", return_value=_FakeDb(store)):
            account = firestore.get_account_by_username("broken")

        self.assertIsNone(account)


if __name__ == "__main__":
    unittest.main()
