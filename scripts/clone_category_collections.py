import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FINANCE_BOT_ROOT = ROOT / "finance-bot"
if str(FINANCE_BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(FINANCE_BOT_ROOT))

from services.category_migration import clone_user_categories


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Clone category docs from users/{source_chat_id}/... to "
            "users/{target_chat_id}/... subcollections."
        )
    )
    parser.add_argument("--source-chat-id", type=int, required=True, help="Source Telegram chat_id.")
    parser.add_argument("--target-chat-id", type=int, required=True, help="Target Telegram chat_id.")
    parser.add_argument(
        "--database",
        required=True,
        help="Target Firestore database ID inside the configured GCP project, for example '(default)', 'developer', or 'prod'.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview how many documents would be cloned without writing anything.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_id = os.getenv("FIRESTORE_PROJECT_ID")
    if not project_id:
        raise SystemExit("FIRESTORE_PROJECT_ID is not set.")

    os.environ["FIRESTORE_DATABASE"] = args.database

    summary = clone_user_categories(
        args.source_chat_id,
        args.target_chat_id,
        dry_run=args.dry_run,
    )

    print(f"Mode: {'dry-run' if args.dry_run else 'apply'}")
    print(f"Target project: {project_id}")
    print(f"Target database: {args.database}")
    print(f"Source chat_id: {args.source_chat_id}")
    print(f"Target chat_id: {args.target_chat_id}")
    print(f"Cloned category_list docs: {summary.cloned_category_list}")
    print(f"Cloned category_map docs: {summary.cloned_category_map}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
