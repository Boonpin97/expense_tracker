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

    class DummyQuery:
        DESCENDING = "DESCENDING"

    firestore_mod.Client = DummyClient
    firestore_mod.Query = DummyQuery
    cloud_mod.firestore = firestore_mod
    google_mod.cloud = cloud_mod
    sys.modules["google"] = google_mod
    sys.modules["google.cloud"] = cloud_mod
    sys.modules["google.cloud.firestore"] = firestore_mod

from services import firestore
from services.category_migration import migrate_categories_to_user_subcollections


class _FakeSnapshot:
    def __init__(self, ref, data: dict | None):
        self.reference = ref
        self.exists = data is not None
        self._data = dict(data or {})
        self.id = ref.doc_id

    def to_dict(self):
        return dict(self._data)


class _FakeDocumentRef:
    def __init__(self, db, collection_name: str, doc_id: str):
        self._db = db
        self.collection_name = collection_name
        self.doc_id = doc_id

    def get(self):
        data = self._db.store.get((self.collection_name, self.doc_id))
        return _FakeSnapshot(self, data)

    def set(self, data: dict, merge: bool = False):
        key = (self.collection_name, self.doc_id)
        if merge and key in self._db.store:
            current = dict(self._db.store[key])
            current.update(data)
            self._db.store[key] = current
        else:
            self._db.store[key] = dict(data)

    def update(self, fields: dict):
        key = (self.collection_name, self.doc_id)
        current = dict(self._db.store.get(key, {}))
        current.update(fields)
        self._db.store[key] = current

    def delete(self):
        self._db.store.pop((self.collection_name, self.doc_id), None)


class _FakeQuery:
    def __init__(self, db, collection_name: str, filters=None, limit_count=None):
        self._db = db
        self.collection_name = collection_name
        self._filters = list(filters or [])
        self._limit_count = limit_count

    def where(self, field: str, op: str, value):
        assert op == "=="
        return _FakeQuery(self._db, self.collection_name, [*self._filters, (field, value)], self._limit_count)

    def limit(self, count: int):
        return _FakeQuery(self._db, self.collection_name, self._filters, count)

    def order_by(self, *_args, **_kwargs):
        return self

    def document(self, doc_id: str = ""):
        if not doc_id:
            doc_id = f"generated-{len(self._db.store) + 1}"
        return _FakeDocumentRef(self._db, self.collection_name, doc_id)

    def stream(self):
        rows = []
        for (collection_name, doc_id), data in self._db.store.items():
            if collection_name != self.collection_name:
                continue
            if all(data.get(field) == expected for field, expected in self._filters):
                rows.append(_FakeSnapshot(_FakeDocumentRef(self._db, collection_name, doc_id), data))
        if self._limit_count is not None:
            rows = rows[: self._limit_count]
        return rows


class _FakeBatch:
    def __init__(self):
        self._ops = []

    def set(self, ref, data: dict, merge: bool = False):
        self._ops.append(("set", ref, dict(data), merge))

    def delete(self, ref):
        self._ops.append(("delete", ref, None, False))

    def update(self, ref, fields: dict):
        self._ops.append(("update", ref, dict(fields), False))

    def commit(self):
        for op, ref, payload, merge in self._ops:
            if op == "set":
                ref.set(payload, merge=merge)
            elif op == "delete":
                ref.delete()
            else:
                ref.update(payload)


class _FakeDb:
    def __init__(self, store: dict):
        self.store = store

    def collection(self, collection_name: str):
        return _FakeQuery(self, collection_name)

    def batch(self):
        return _FakeBatch()


class CategoryPartitioningTests(unittest.TestCase):
    def test_new_users_start_empty_without_runtime_migration(self):
        store = {
            ("category_list", "Food & Drink"): {"name": "Food & Drink", "emoji": "🍔", "order": 1},
            ("category_list", "Transport"): {"name": "Transport", "emoji": "🚗", "order": 2},
            ("category_map", "coffee"): {
                "item_key": "coffee",
                "category": "Food & Drink",
                "confirmed_by_user": True,
                "created_at": "2026-05-01T00:00:00+08:00",
            },
        }

        with patch.object(firestore, "get_db", return_value=_FakeDb(store)):
            self.assertEqual(firestore.get_category_list(123), [])
            self.assertEqual(firestore.get_category(123, "coffee"), None)

    def test_migrate_legacy_global_docs_to_subcollections(self):
        store = {
            ("category_list", "Food & Drink"): {"name": "Food & Drink", "emoji": "🍔", "order": 1},
            ("category_list", "Transport"): {"name": "Transport", "emoji": "🚗", "order": 2},
            ("category_map", "coffee"): {
                "item_key": "coffee",
                "category": "Food & Drink",
                "confirmed_by_user": True,
                "created_at": "2026-05-01T00:00:00+08:00",
            },
        }

        summary = migrate_categories_to_user_subcollections(123, db=_FakeDb(store))

        self.assertEqual(summary.source_shape, "legacy global")
        self.assertEqual(summary.migrated_category_list, 2)
        self.assertEqual(summary.migrated_category_map, 1)
        self.assertEqual(summary.deleted_source_category_list, 2)
        self.assertEqual(summary.deleted_source_category_map, 1)
        self.assertNotIn(("category_list", "Food & Drink"), store)
        self.assertNotIn(("category_map", "coffee"), store)
        self.assertEqual(store[("users/123/category_list", "Food%20%26%20Drink")]["name"], "Food & Drink")
        self.assertEqual(store[("users/123/category_map", "coffee")]["item_key"], "coffee")
        self.assertNotIn("chat_id", store[("users/123/category_list", "Food%20%26%20Drink")])

    def test_migrate_top_level_user_scoped_docs_to_subcollections(self):
        store = {
            ("category_list", "123:Food%20%26%20Drink"): {
                "chat_id": 123,
                "name": "Food & Drink",
                "emoji": "🍔",
                "order": 1,
            },
            ("category_map", "123:coffee"): {
                "chat_id": 123,
                "item_key": "coffee",
                "category": "Food & Drink",
                "confirmed_by_user": True,
                "created_at": "2026-05-01T00:00:00+08:00",
            },
        }

        summary = migrate_categories_to_user_subcollections(123, db=_FakeDb(store))

        self.assertEqual(summary.source_shape, "top-level user-scoped")
        self.assertEqual(summary.migrated_category_list, 1)
        self.assertEqual(summary.migrated_category_map, 1)
        self.assertNotIn(("category_list", "123:Food%20%26%20Drink"), store)
        self.assertNotIn(("category_map", "123:coffee"), store)
        self.assertEqual(store[("users/123/category_list", "Food%20%26%20Drink")]["emoji"], "🍔")
        self.assertNotIn("chat_id", store[("users/123/category_map", "coffee")])

    def test_dry_run_reports_counts_without_writing(self):
        store = {
            ("category_list", "123:Food%20%26%20Drink"): {
                "chat_id": 123,
                "name": "Food & Drink",
                "emoji": "🍔",
                "order": 1,
            },
            ("category_map", "123:coffee"): {
                "chat_id": 123,
                "item_key": "coffee",
                "category": "Food & Drink",
                "confirmed_by_user": True,
                "created_at": "2026-05-01T00:00:00+08:00",
            },
        }

        summary = migrate_categories_to_user_subcollections(123, db=_FakeDb(store), dry_run=True)

        self.assertEqual(summary.source_shape, "top-level user-scoped")
        self.assertEqual(summary.migrated_category_list, 1)
        self.assertEqual(summary.migrated_category_map, 1)
        self.assertEqual(summary.deleted_source_category_list, 1)
        self.assertEqual(summary.deleted_source_category_map, 1)
        self.assertIn(("category_list", "123:Food%20%26%20Drink"), store)
        self.assertNotIn(("users/123/category_list", "Food%20%26%20Drink"), store)

    def test_migration_refuses_mixed_sources(self):
        store = {
            ("category_list", "Food & Drink"): {"name": "Food & Drink", "emoji": "🍔", "order": 1},
            ("category_list", "123:Existing"): {
                "chat_id": 123,
                "name": "Existing",
                "emoji": "📦",
                "order": 1,
            },
        }

        with self.assertRaisesRegex(ValueError, "ambiguous migration"):
            migrate_categories_to_user_subcollections(123, db=_FakeDb(store))

    def test_migration_refuses_existing_subcollection_data(self):
        store = {
            ("users/123/category_list", "Existing"): {"name": "Existing", "emoji": "📦", "order": 1},
            ("category_list", "Food & Drink"): {"name": "Food & Drink", "emoji": "🍔", "order": 1},
        }

        with self.assertRaisesRegex(ValueError, "already has category data"):
            migrate_categories_to_user_subcollections(123, db=_FakeDb(store))

    def test_categories_are_isolated_per_chat_id(self):
        store = {}

        with patch.object(firestore, "get_db", return_value=_FakeDb(store)):
            firestore.add_category_to_list(123, "Food & Drink", "🍔")
            firestore.add_category_to_list(456, "Food & Drink", "🥗")
            firestore.save_category(123, "coffee", "Food & Drink", confirmed_by_user=True)
            firestore.save_category(456, "coffee", "Transport", confirmed_by_user=True)

            self.assertEqual(firestore.get_category(123, "coffee"), "Food & Drink")
            self.assertEqual(firestore.get_category(456, "coffee"), "Transport")
            self.assertEqual(firestore.get_category_list(123)[0]["emoji"], "🍔")
            self.assertEqual(firestore.get_category_list(456)[0]["emoji"], "🥗")
            self.assertIn(("users/123/category_map", "coffee"), store)
            self.assertIn(("users/456/category_map", "coffee"), store)

    def test_rename_delete_and_reassign_are_scoped_to_chat_id(self):
        store = {}

        with patch.object(firestore, "get_db", return_value=_FakeDb(store)):
            firestore.add_category_to_list(123, "Food & Drink", "🍔")
            firestore.add_category_to_list(456, "Food & Drink", "🥗")
            firestore.save_category(123, "coffee", "Food & Drink", confirmed_by_user=True)
            firestore.save_category(456, "coffee", "Food & Drink", confirmed_by_user=True)
            store[("transactions", "tx-123")] = {
                "chat_id": 123,
                "item": "Coffee",
                "amount": 5.0,
                "category": "Food & Drink",
                "timestamp": "2026-05-01T10:00:00+08:00",
            }
            store[("transactions", "tx-456")] = {
                "chat_id": 456,
                "item": "Coffee",
                "amount": 7.0,
                "category": "Food & Drink",
                "timestamp": "2026-05-01T11:00:00+08:00",
            }

            ok, tx_count, map_count = firestore.rename_category(123, "Food & Drink", "Meals")
            reassigned = firestore.reassign_transactions_category(123, "Meals", "Other")
            deleted_map_count = firestore.delete_category(123, "Meals")
            removed = firestore.remove_category_from_list(123, "Meals")

        self.assertTrue(ok)
        self.assertEqual((tx_count, map_count), (1, 1))
        self.assertEqual(reassigned, 1)
        self.assertEqual(deleted_map_count, 1)
        self.assertTrue(removed)
        self.assertEqual(store[("transactions", "tx-123")]["category"], "Other")
        self.assertEqual(store[("transactions", "tx-456")]["category"], "Food & Drink")
        self.assertEqual(store[("users/456/category_map", "coffee")]["category"], "Food & Drink")
        self.assertNotIn(("users/123/category_map", "coffee"), store)


if __name__ == "__main__":
    unittest.main()
