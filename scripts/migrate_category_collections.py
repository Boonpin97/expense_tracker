import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FINANCE_BOT_ROOT = ROOT / "finance-bot"
if str(FINANCE_BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(FINANCE_BOT_ROOT))

from services.category_migration import migrate_categories_to_user_subcollections


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Migrate category docs into users/{chat_id}/category_list and "
            "users/{chat_id}/category_map subcollections."
        )
    )
    parser.add_argument("--chat-id", type=int, required=True, help="Target Telegram chat_id.")
    parser.add_argument(
        "--database",
        required=True,
        help="Target Firestore database ID inside the configured GCP project, for example '(default)', 'developer', or 'prod'.",
    )
    parser.add_argument(
        "--keep-source",
        "--keep-legacy",
        dest="keep_source",
        action="store_true",
        help="Copy source docs without deleting the original top-level documents.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview how many documents would be migrated without writing or deleting anything.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_id = os.getenv("FIRESTORE_PROJECT_ID")
    if not project_id:
        raise SystemExit("FIRESTORE_PROJECT_ID is not set.")

    os.environ["FIRESTORE_DATABASE"] = args.database

    summary = migrate_categories_to_user_subcollections(
        args.chat_id,
        delete_source=not args.keep_source,
        dry_run=args.dry_run,
    )

    print(f"Mode: {'dry-run' if args.dry_run else 'apply'}")
    print(f"Target project: {project_id}")
    print(f"Target database: {args.database}")
    print(f"Target chat_id: {args.chat_id}")
    print(f"Source shape: {summary.source_shape}")
    print(f"Migrated category_list docs: {summary.migrated_category_list}")
    print(f"Migrated category_map docs: {summary.migrated_category_map}")
    print(f"Deleted source category_list docs: {summary.deleted_source_category_list}")
    print(f"Deleted source category_map docs: {summary.deleted_source_category_map}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
