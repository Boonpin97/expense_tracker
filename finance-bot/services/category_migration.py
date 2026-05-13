from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from google.cloud import firestore

from services.firestore import (
    _category_doc_id,
    _category_list_path,
    _item_map_doc_id,
    _category_map_path,
    get_db,
)


@dataclass
class CategoryMigrationSummary:
    migrated_category_list: int = 0
    migrated_category_map: int = 0
    deleted_source_category_list: int = 0
    deleted_source_category_map: int = 0
    source_shape: str = "none"


@dataclass
class CategoryCloneSummary:
    cloned_category_list: int = 0
    cloned_category_map: int = 0


def _is_legacy_doc(snapshot) -> bool:
    data = snapshot.to_dict() or {}
    return "chat_id" not in data or data.get("chat_id") in (None, "")


def _assert_target_is_clear(db: firestore.Client, chat_id: int) -> None:
    has_category_list = any(db.collection(_category_list_path(chat_id)).limit(1).stream())
    has_category_map = any(db.collection(_category_map_path(chat_id)).limit(1).stream())
    if has_category_list or has_category_map:
        raise ValueError(
            f"Target chat_id {chat_id} already has category data in user subcollections. "
            "Refusing to merge source docs automatically."
        )


def _commit_batch(db: firestore.Client, batch: firestore.WriteBatch) -> firestore.WriteBatch:
    batch.commit()
    return db.batch()


def _get_source_docs(db: firestore.Client, chat_id: int) -> tuple[str, list, list]:
    legacy_category_list = [doc for doc in db.collection("category_list").stream() if _is_legacy_doc(doc)]
    legacy_category_map = [doc for doc in db.collection("category_map").stream() if _is_legacy_doc(doc)]
    scoped_category_list = list(db.collection("category_list").where("chat_id", "==", chat_id).stream())
    scoped_category_map = list(db.collection("category_map").where("chat_id", "==", chat_id).stream())

    has_legacy = bool(legacy_category_list or legacy_category_map)
    has_scoped = bool(scoped_category_list or scoped_category_map)

    if has_legacy and has_scoped:
        raise ValueError(
            f"Found both legacy global docs and top-level user-scoped docs for chat_id {chat_id}. "
            "Refusing ambiguous migration."
        )
    if has_scoped:
        return "top-level user-scoped", scoped_category_list, scoped_category_map
    if has_legacy:
        return "legacy global", legacy_category_list, legacy_category_map
    return "none", [], []


def migrate_categories_to_user_subcollections(
    chat_id: int,
    *,
    db: Optional[firestore.Client] = None,
    delete_source: bool = True,
    dry_run: bool = False,
) -> CategoryMigrationSummary:
    db = db or get_db()
    _assert_target_is_clear(db, chat_id)

    source_shape, source_category_list, source_category_map = _get_source_docs(db, chat_id)
    summary = CategoryMigrationSummary(source_shape=source_shape)
    if source_shape == "none":
        return summary

    batch = None if dry_run else db.batch()
    ops_in_batch = 0
    category_list_target = db.collection(_category_list_path(chat_id))
    category_map_target = db.collection(_category_map_path(chat_id))

    for doc in source_category_list:
        data = doc.to_dict() or {}
        name = str(data.get("name") or doc.id).strip()
        if not name:
            continue

        payload = dict(data)
        payload["name"] = name
        payload.pop("chat_id", None)
        if not dry_run:
            batch.set(category_list_target.document(_category_doc_id(name)), payload)
            ops_in_batch += 1
        summary.migrated_category_list += 1

        if delete_source:
            if not dry_run:
                batch.delete(doc.reference)
                ops_in_batch += 1
            summary.deleted_source_category_list += 1

        if not dry_run and ops_in_batch >= 400:
            batch = _commit_batch(db, batch)
            ops_in_batch = 0

    for doc in source_category_map:
        data = doc.to_dict() or {}
        item_key = str(data.get("item_key") or doc.id).strip()
        if not item_key:
            continue

        payload = dict(data)
        payload["item_key"] = item_key
        payload.pop("chat_id", None)
        if not dry_run:
            batch.set(category_map_target.document(_item_map_doc_id(item_key)), payload)
            ops_in_batch += 1
        summary.migrated_category_map += 1

        if delete_source:
            if not dry_run:
                batch.delete(doc.reference)
                ops_in_batch += 1
            summary.deleted_source_category_map += 1

        if not dry_run and ops_in_batch >= 400:
            batch = _commit_batch(db, batch)
            ops_in_batch = 0

    if not dry_run and ops_in_batch > 0:
        batch.commit()

    return summary


def clone_user_categories(
    source_chat_id: int,
    target_chat_id: int,
    *,
    db: Optional[firestore.Client] = None,
    dry_run: bool = False,
) -> CategoryCloneSummary:
    db = db or get_db()
    if source_chat_id == target_chat_id:
        raise ValueError("Source and target chat_id must be different.")

    _assert_target_is_clear(db, target_chat_id)

    source_category_list = list(db.collection(_category_list_path(source_chat_id)).stream())
    source_category_map = list(db.collection(_category_map_path(source_chat_id)).stream())

    summary = CategoryCloneSummary()
    batch = None if dry_run else db.batch()
    ops_in_batch = 0
    target_category_list = db.collection(_category_list_path(target_chat_id))
    target_category_map = db.collection(_category_map_path(target_chat_id))

    for doc in source_category_list:
        data = doc.to_dict() or {}
        name = str(data.get("name") or doc.id).strip()
        if not name:
            continue
        if not dry_run:
            batch.set(target_category_list.document(_category_doc_id(name)), dict(data))
            ops_in_batch += 1
        summary.cloned_category_list += 1
        if not dry_run and ops_in_batch >= 400:
            batch = _commit_batch(db, batch)
            ops_in_batch = 0

    for doc in source_category_map:
        data = doc.to_dict() or {}
        item_key = str(data.get("item_key") or doc.id).strip()
        if not item_key:
            continue
        if not dry_run:
            batch.set(target_category_map.document(_item_map_doc_id(item_key)), dict(data))
            ops_in_batch += 1
        summary.cloned_category_map += 1
        if not dry_run and ops_in_batch >= 400:
            batch = _commit_batch(db, batch)
            ops_in_batch = 0

    if not dry_run and ops_in_batch > 0:
        batch.commit()

    return summary
