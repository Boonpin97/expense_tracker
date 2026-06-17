import os
from datetime import datetime, timedelta, timezone

import httpx

SGT = timezone(timedelta(hours=8))

TELEGRAM_API = "https://api.telegram.org/bot{token}"
_TIMEOUT = httpx.Timeout(10.0)


def _api_url(method: str) -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    return f"{TELEGRAM_API.format(token=token)}/{method}"


async def send_message(chat_id: int, text: str, parse_mode: str = "HTML") -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
            },
        )
        return resp.json()


async def send_message_with_transaction_actions(
    chat_id: int,
    text: str,
    tx_id: str,
    item_key: str,
    include_change_date: bool = False,
) -> dict:
    keyboard = [[{"text": "🔄 Change category", "callback_data": f"chgcat:{tx_id}:{item_key}"}]]
    if include_change_date:
        keyboard[0].append({"text": "🗓 Change date", "callback_data": f"chgdate:{tx_id}"})

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def send_transaction_confirmation(
    chat_id: int,
    item: str,
    amount: float,
    category: str,
    tx_id: str | None = None,
    item_key: str | None = None,
    note: str | None = None,
    include_change_date: bool = False,
) -> dict:
    text = f"✅ <b>{item}</b> — ${amount:.2f} → {category}"
    if note:
        text += f"\n<i>{note}</i>"
    if tx_id and item_key:
        return await send_message_with_transaction_actions(
            chat_id,
            text,
            tx_id,
            item_key,
            include_change_date=include_change_date,
        )
    return await send_message(chat_id, text)


async def send_category_keyboard(chat_id: int, item: str, amount: float) -> dict:
    from services.firestore import get_category_list

    categories = []
    for cat in get_category_list(chat_id):
        emoji = cat.get("emoji", "🏷️")
        name = cat["name"]
        categories.append((f"{emoji} {name}", f"cat:{name}"))

    categories.append(("✏️ New category", "cat:__new__"))

    keyboard = []
    row = []
    for label, callback in categories:
        row.append({"text": label, "callback_data": callback})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": f"What category is <b>{item}</b> (${amount:.2f})?",
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def send_budget_category_keyboard(chat_id: int, prompt: str) -> dict:
    from services.firestore import get_category_list

    keyboard = []
    row = []
    for cat in get_category_list(chat_id):
        emoji = cat.get("emoji", "🏷️")
        name = cat["name"]
        row.append({"text": f"{emoji} {name}", "callback_data": f"budgetcat:{name}"})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([{"text": "Done", "callback_data": "budgetcat:__done__"}])

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": prompt,
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def send_income_goal_keyboard(chat_id: int, goals: list[dict], item: str, amount: float) -> dict:
    """Ask which goal a just-recorded income belongs to. Expiry comes from the
    interaction session, so callback_data carries no timestamps."""
    keyboard = [
        [{"text": f"{goal.get('emoji', '🎯')} {goal['name']}", "callback_data": f"inflowgoal:{goal['id']}"}]
        for goal in goals
    ]
    keyboard.append([{"text": "➕ Add new goal", "callback_data": "inflowgoal:__new__"}])
    keyboard.append([{"text": "🚫 No goal", "callback_data": "inflowgoal:__none__"}])

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": f"Tag <b>{item}</b> +${amount:.2f} to a goal?",
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def send_goal_keyboard(chat_id: int, goals: list[dict], action: str, prompt: str) -> dict:
    """Generic goal picker; callback_data is `{action}:{goal_id}`."""
    keyboard = [
        [{"text": f"{goal.get('emoji', '🎯')} {goal['name']}", "callback_data": f"{action}:{goal['id']}"}]
        for goal in goals
    ]

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": prompt,
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def send_goal_field_keyboard(chat_id: int, goal_name: str) -> dict:
    keyboard = [
        [
            {"text": "📝 Name", "callback_data": "goalfield:name"},
            {"text": "😀 Emoji", "callback_data": "goalfield:emoji"},
            {"text": "🎯 Target", "callback_data": "goalfield:target"},
        ],
        [{"text": "🔄 Reorder", "callback_data": "goalfield:reorder"}],
    ]

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": f"What do you want to change on <b>{goal_name}</b>?",
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def send_goal_reorder_keyboard(chat_id: int, goals: list[dict], goal_id: str) -> dict:
    """Show the goal's position with ⬆️/⬇️ buttons to move it, plus Done.
    Callback data is `goalmove:up`/`goalmove:down`/`goalmove:done`."""
    lines = ["Reordering goals — tap ⬆️/⬇️ to move the selected goal:"]
    for index, goal in enumerate(goals, start=1):
        marker = "👉 " if goal["id"] == goal_id else ""
        lines.append(f"{marker}{index}. {goal.get('emoji', '🎯')} {goal['name']}")
    keyboard = [
        [
            {"text": "⬆️ Up", "callback_data": "goalmove:up"},
            {"text": "⬇️ Down", "callback_data": "goalmove:down"},
        ],
        [{"text": "✅ Done", "callback_data": "goalmove:done"}],
    ]
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": "\n".join(lines),
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def send_goal_delete_confirm_keyboard(chat_id: int, goal_name: str) -> dict:
    keyboard = [[
        {"text": "🗑️ Delete", "callback_data": "goaldelconfirm:yes"},
        {"text": "Cancel", "callback_data": "goaldelconfirm:no"},
    ]]

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": f"Delete goal <b>{goal_name}</b>? Income entries tagged to it stay recorded.",
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def send_project_keyboard(chat_id: int, projects: list[dict], action: str, prompt: str) -> dict:
    """Generic project picker; callback_data is `{action}:{project_id}`."""
    keyboard = [
        [{"text": f"{project.get('emoji', '🚀')} {project['name']}", "callback_data": f"{action}:{project['id']}"}]
        for project in projects
    ]

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": prompt,
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def send_project_field_keyboard(chat_id: int, project_name: str) -> dict:
    keyboard = [
        [
            {"text": "📝 Name", "callback_data": "projectfield:name"},
            {"text": "😀 Emoji", "callback_data": "projectfield:emoji"},
        ],
        [
            {"text": "🎯 Target", "callback_data": "projectfield:target"},
            {"text": "💰 Initial", "callback_data": "projectfield:initial"},
        ],
        [
            {"text": "📅 Deadline", "callback_data": "projectfield:deadline"},
            {"text": "🔄 Reorder", "callback_data": "projectfield:reorder"},
        ],
    ]

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": f"What do you want to change on <b>{project_name}</b>?",
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def send_project_reorder_keyboard(chat_id: int, projects: list[dict], project_id: str) -> dict:
    """Show the project's position with ⬆️/⬇️ buttons to move it, plus Done."""
    lines = ["Reordering long-term projects — tap ⬆️/⬇️ to move the selected project:"]
    for index, project in enumerate(projects, start=1):
        marker = "👉 " if project["id"] == project_id else ""
        lines.append(f"{marker}{index}. {project.get('emoji', '🚀')} {project['name']}")
    keyboard = [
        [
            {"text": "⬆️ Up", "callback_data": "projectmove:up"},
            {"text": "⬇️ Down", "callback_data": "projectmove:down"},
        ],
        [{"text": "✅ Done", "callback_data": "projectmove:done"}],
    ]
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": "\n".join(lines),
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def send_project_delete_confirm_keyboard(chat_id: int, project_name: str) -> dict:
    keyboard = [[
        {"text": "🗑️ Delete", "callback_data": "projectdelconfirm:yes"},
        {"text": "Cancel", "callback_data": "projectdelconfirm:no"},
    ]]

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": f"Delete long-term project <b>{project_name}</b>? Income entries tagged to it stay recorded.",
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def send_transaction_keyboard(chat_id: int, transactions: list[dict], prompt: str) -> dict:
    """Send an inline keyboard where each button is a transaction to delete."""
    ts = datetime.now(SGT).isoformat(timespec="seconds")
    keyboard = []
    for tx in transactions:
        label = f"❌ {tx['item']} — ${tx['amount']:.2f} ({tx['category']})"
        callback_data = f"del:{tx['_doc_id']}:{ts}"
        keyboard.append([{"text": label, "callback_data": callback_data}])

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": prompt,
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def send_monthly_report_keyboard(chat_id: int, buttons: list[tuple[str, str]], prompt: str) -> dict:
    ts = datetime.now(SGT).isoformat(timespec="seconds")
    keyboard = []
    row = []
    for label, callback_data in buttons:
        row.append({"text": label, "callback_data": f"{callback_data}|{ts}"})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": prompt,
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def send_daily_report_keyboard(chat_id: int, prompt: str) -> dict:
    ts = datetime.now(SGT).isoformat(timespec="seconds")
    keyboard = [[
        {"text": "Today", "callback_data": f"dailyrep:today|{ts}"},
        {"text": "Past report", "callback_data": f"dailyrep:past|{ts}"},
    ]]

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": prompt,
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def send_remove_category_keyboard(chat_id: int, categories: list[dict]) -> dict:
    """Send an inline keyboard for removing a category."""
    ts = datetime.now(SGT).isoformat(timespec="seconds")
    keyboard = []
    for cat in categories:
        label = f"❌ {cat['emoji']} {cat['name']}"
        keyboard.append([{"text": label, "callback_data": f"rmcat:{cat['name']}|{ts}"}])

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": "🗂 Tap a category to remove it:",
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def send_edit_category_keyboard(chat_id: int, categories: list[dict]) -> dict:
    """Send an inline keyboard for picking which category to edit."""
    ts = datetime.now(SGT).isoformat(timespec="seconds")
    keyboard = []
    row = []
    for cat in categories:
        label = f"{cat['emoji']} {cat['name']}"
        row.append({"text": label, "callback_data": f"editcat:{cat['name']}|{ts}"})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": "✏️ Tap a category to edit:",
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def send_edit_category_field_keyboard(chat_id: int, category_name: str, emoji: str) -> dict:
    """Send an inline keyboard with 3 fields: emoji, name, order."""
    ts = datetime.now(SGT).isoformat(timespec="seconds")
    keyboard = [[
        {"text": "😀 Emoji", "callback_data": f"editfield:emoji:{category_name}|{ts}"},
        {"text": "📝 Name", "callback_data": f"editfield:name:{category_name}|{ts}"},
        {"text": "🔢 Order", "callback_data": f"editfield:order:{category_name}|{ts}"},
    ]]
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": f"Editing {emoji} <b>{category_name}</b> — what do you want to change?",
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def send_plan_keyboard(chat_id: int, plans: list[dict], action: str, prompt: str) -> dict:
    ts = datetime.now(SGT).isoformat(timespec="seconds")
    keyboard = []
    for plan in plans:
        plan_type = "Recurring" if plan["plan_type"] == "recurring" else "Split"
        label = f"{plan_type}: {plan['item']}"
        keyboard.append([{"text": label, "callback_data": f"{action}:{plan['id']}|{ts}"}])
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": prompt,
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def send_plan_edit_field_keyboard(chat_id: int, plan_id: str, plan_type: str) -> dict:
    keyboard = [
        [
            {"text": "Name", "callback_data": f"editplanfield:item:{plan_id}"},
            {"text": "Category", "callback_data": f"editplanfield:category:{plan_id}"},
        ],
        [
            {"text": "Amount", "callback_data": f"editplanfield:amount:{plan_id}"},
            {"text": "Day", "callback_data": f"editplanfield:day:{plan_id}"},
        ],
    ]
    if plan_type == "split_payment":
        keyboard.append([
            {"text": "Months", "callback_data": f"editplanfield:months:{plan_id}"},
        ])
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": "Choose what to edit:",
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def send_plan_delete_mode_keyboard(chat_id: int, plan_id: str, prompt: str) -> dict:
    keyboard = [[
        {"text": "Stop future only", "callback_data": f"plandelmode:future:{plan_id}"},
        {"text": "Stop future + remove past", "callback_data": f"plandelmode:all:{plan_id}"},
    ]]
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": prompt,
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def send_split_plan_delete_confirm_keyboard(chat_id: int, plan_id: str, prompt: str) -> dict:
    keyboard = [[
        {"text": "Stop + remove past charges", "callback_data": f"plandelmode:all:{plan_id}"},
    ]]
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": prompt,
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def send_plan_rewrite_keyboard(chat_id: int, prompt: str | None = None) -> dict:
    keyboard = [[
        {"text": "Future only", "callback_data": "planrewrite:future"},
        {"text": "Rewrite past auto charges", "callback_data": "planrewrite:rewrite"},
    ]]
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": prompt or "Should this edit affect only future charges, or also rewrite past auto-generated charges for this plan?",
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def set_webhook(url: str, secret_token: str) -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("setWebhook"),
            json={
                "url": url,
                "secret_token": secret_token,
            },
        )
        return resp.json()


async def send_dashboard_account_options_keyboard(chat_id: int, prompt: str) -> dict:
    keyboard = [[
        {"text": "Username", "callback_data": "acct:username"},
        {"text": "Password", "callback_data": "acct:password"},
        {"text": "Cancel", "callback_data": "acct:cancel"},
    ]]

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("sendMessage"),
            json={
                "chat_id": chat_id,
                "text": prompt,
                "parse_mode": "HTML",
                "reply_markup": {"inline_keyboard": keyboard},
            },
        )
        return resp.json()


async def answer_callback_query(callback_query_id: str, text: str = "") -> dict:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("answerCallbackQuery"),
            json={
                "callback_query_id": callback_query_id,
                "text": text,
            },
        )
        return resp.json()


async def set_my_commands() -> dict:
    commands = [
        {"command": "start", "description": "Welcome message"},
        {"command": "daily", "description": "Daily spending reports"},
        {"command": "weekly", "description": "This week's spending summary"},
        {"command": "income", "description": "Record income, e.g. /income Salary 2000"},
        {"command": "goals", "description": "List goals with progress"},
        {"command": "new_goal", "description": "Create a savings goal"},
        {"command": "edit_goal", "description": "Edit a goal's name or target"},
        {"command": "delete_goal", "description": "Delete a goal"},
        {"command": "projects", "description": "List long-term projects"},
        {"command": "new_projects", "description": "Create a long-term project"},
        {"command": "edit_projects", "description": "Edit a long-term project"},
        {"command": "delete_projects", "description": "Delete a long-term project"},
        {"command": "set_budget", "description": "Set a monthly budget for a category"},
        {"command": "list_budget", "description": "List monthly budgets"},
        {"command": "budget_report", "description": "Show this month's budget report"},
        {"command": "remove_budget", "description": "Remove a monthly budget"},
        {"command": "monthly", "description": "This month's spending summary"},
        {"command": "delete_last", "description": "Delete the last recorded transaction"},
        {"command": "delete_today", "description": "Delete a transactions from today"},
        {"command": "delete_past", "description": "Delete a transactions in a specific date"},
        {"command": "new_category", "description": "Add a new spending category"},
        {"command": "remove_category", "description": "Remove a spending category"},
        {"command": "edit_category", "description": "Edit a category's emoji, name, or order"},
        {"command": "create_account", "description": "Create a dashboard username and password"},
        {"command": "change_password", "description": "Change your dashboard password"},
        {"command": "set_recurring", "description": "Create a monthly recurring payment"},
        {"command": "list_recurring", "description": "List recurring payment plans"},
        {"command": "edit_recurring", "description": "Edit a recurring payment plan"},
        {"command": "delete_recurring", "description": "Delete a recurring payment plan"},
        {"command": "split_payment", "description": "Split one payment across monthly charges"},
        {"command": "list_split_payment", "description": "List split payment plans"},
        {"command": "edit_split_payment", "description": "Edit a split payment plan"},
        {"command": "delete_split_payment", "description": "Delete a split payment plan"},
    ]
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            _api_url("setMyCommands"),
            json={"commands": commands},
        )
        return resp.json()
