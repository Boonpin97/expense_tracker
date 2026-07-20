# Finance Bot Feature Test Cases

This document maps the current backend feature set to concrete test cases. It is intended to answer "what should we test to cover every feature in this codebase?" rather than only "what is already tested?".

## Existing automated coverage

The current suite already covers parts of these areas:

- Parsing dates and freeform expenses: `test_transaction_dates.py`
- Budget command helpers and the interactive set-budget flow: `test_budget_commands.py`
- Dashboard auth/session basics and selected dashboard mutations: `test_dashboard_auth.py`, `test_dashboard_router_sessions.py`
- Monthly-report helpers and Telegram callback payload sizing: `test_monthly_reports.py`, `test_payment_plans.py`
- Interaction session storage behavior: `test_interaction_sessions.py`
- Category storage partitioning, migration, rename, reassignment, and budget cleanup: `test_category_partitioning.py`

The gaps are mostly:

- Full Telegram webhook command coverage
- Scheduler endpoint authorization and reporting behavior
- Categoriser behavior around known/unknown items and budget warnings
- Dashboard CRUD error paths and authorization boundaries
- Plan edit/delete flows in the webhook
- App startup and middleware behavior

## Test strategy

Use three layers:

- Unit tests for pure helpers and formatting/parsing logic
- Service tests with Firestore/Telegram mocked
- Router tests for webhook and dashboard endpoint behavior

## Test Cases

### 1. App startup, middleware, and health

| ID | Feature | Scenario | Expected result |
|---|---|---|---|
| APP-001 | `/health` | GET `/health` | Returns `200` and `{"status":"ok"}` |
| APP-002 | lifespan startup | `CLOUD_RUN_URL` and `TELEGRAM_WEBHOOK_SECRET` are set | `telegram.set_webhook()` called with `<cloud_run_url>/webhook` |
| APP-003 | lifespan startup | webhook env vars missing | Startup skips `set_webhook()` without failing |
| APP-004 | lifespan startup | `telegram.set_my_commands()` raises | Startup swallows exception and app still starts |
| APP-005 | auth listener startup | app lifespan starts | `start_authorized_chats_listener()` invoked once |
| APP-006 | CORS config | default origins only | middleware contains local/dev/prod dashboard origins |
| APP-007 | CORS config | `DASHBOARD_WEB_ORIGINS` contains duplicates and whitespace | origins are trimmed, deduplicated, and merged |
| APP-008 | crash middleware | downstream request succeeds | response passes through unchanged |
| APP-009 | crash middleware | downstream raises and `DEV_MODE=false` | exception re-raised, no Telegram notification |
| APP-010 | crash middleware | downstream raises and `DEV_MODE=true` | sends crash report to each allowed chat ID |
| APP-011 | crash middleware | crash traceback exceeds Telegram length | crash message is truncated to safe size |
| APP-012 | crash middleware | Telegram send fails for one chat | middleware continues attempting remaining chats |

### 2. Expense parsing and date parsing

| ID | Feature | Scenario | Expected result |
|---|---|---|---|
| PAR-001 | item-first parsing | `Coffee $10` | item=`Coffee`, amount=`10.0` |
| PAR-002 | amount-first parsing with dollar | `$10 Food` | item=`Food`, amount=`10.0` |
| PAR-003 | amount-first parsing without dollar | `10.4 Drinks` | item=`Drinks`, amount=`10.4` |
| PAR-004 | numeric item names | `10.44 711` | item=`711`, amount=`10.44` |
| PAR-005 | hyphenated numeric item names | `5 7-11` | item=`7-11`, amount=`5.0` |
| PAR-006 | math expressions | `Drinks 10+20*2` | amount evaluates to `50.0` |
| PAR-007 | math expressions amount-first | `$10+20*2 Drinks` | amount evaluates to `50.0` |
| PAR-008 | parentheses | `Snacks (10+20)*2` | amount evaluates to `60.0` |
| PAR-009 | `x` multiplication alias | `Taxi 10+20x2` | amount evaluates to `50.0` |
| PAR-010 | trailing transaction date | `Coffee $10 130126` | transaction date parsed as `2026-01-13` |
| PAR-011 | invalid trailing transaction date | `Coffee $10 310226` | returns `None` |
| PAR-012 | invalid expression syntax | `Drinks 10++` | returns `None` |
| PAR-013 | unmatched parentheses | `Drinks (10+20` | returns `None` |
| PAR-014 | division by zero | `Drinks 10/0` | returns `None` |
| PAR-015 | negative result | expression evaluates below zero | returns `None` |
| PAR-016 | blank input | empty or whitespace-only string | returns `None` |
| PAR-017 | date parser format | `130126` | returns `2026-01-13` |
| PAR-018 | date parser invalid format | `03-05-2026` | returns `None` |
| PAR-019 | amount lexer hardening | alphabetic characters in amount segment | returns `None` |
| PAR-020 | unary operators | `Refund -10` or `+-10` style input | rejected if final amount negative |

### 3. Categoriser and pending-expense flow

| ID | Feature | Scenario | Expected result |
|---|---|---|---|
| CAT-001 | item normalization | item contains punctuation/case variation | category lookup uses normalized key |
| CAT-002 | known item mapping | category exists for normalized item | transaction saved immediately |
| CAT-003 | known item confirmation | known item saved | confirmation sent with tx id and item key |
| CAT-004 | explicit date confirmation | transaction had explicit date | confirmation omits "change date" action |
| CAT-005 | implicit date confirmation | transaction had no explicit date | confirmation includes "change date" action |
| CAT-006 | unknown item flow | no category mapping exists | pending transaction saved and category keyboard sent |
| CAT-007 | pending expiry | pending `created_at` older than expiry | expired pending is rejected |
| CAT-008 | pending fallback field | pending has no `created_at` but has `timestamp` | expiry still computed |
| CAT-009 | budget warning | category spending exceeds prorated budget after save | warning message sent |
| CAT-010 | no budget warning | budget absent or spending below prorated budget | no warning message sent |
| CAT-011 | category selection existing category | pending expense is active | saves transaction, stores category mapping, deletes pending |
| CAT-012 | category selection expired pending | category button clicked after expiry | pending deleted and user told to resend expense |
| CAT-013 | category selection with no pending | callback arrives with no pending doc | callback answered with "No pending expense found." |
| CAT-014 | change-category callback | pending change exists and is active | transaction category updated and mapping saved |
| CAT-015 | change-category callback expired | pending change expired | pending change cleared and user told to retry |
| CAT-016 | choose new category from expense flow | callback category is `__new__` | user state set to `awaiting_inline_cat_name` |
| CAT-017 | choose new category from change flow | callback category is `__new__` during change flow | user state set to `awaiting_change_new_name:<tx_id>:<item_key>` |
| CAT-018 | custom category input | active pending expense and custom category name | transaction saved, category list updated, pending deleted |
| CAT-019 | custom category input with no pending | user sends custom category after flow lost | user receives "No pending expense found" |
| CAT-020 | custom category input expired | pending expense expired before emoji/name completion | pending deleted and user told to resend |

### 4. Webhook authorization and top-level update routing

| ID | Feature | Scenario | Expected result |
|---|---|---|---|
| WEB-001 | chat authorization | inbound message chat id not in Firestore `authorized_chats` | update ignored with `{"ok": True}` |
| WEB-002 | message update routing | inbound `message.text` event | command/text flow executed |
| WEB-003 | callback update routing | inbound `callback_query.data` event | callback flow executed |
| WEB-004 | unsupported update shape | payload lacks supported message/callback fields | returns `{"ok": True}` without crashing |
| WEB-005 | malformed callback data | unknown callback prefix | ignored safely |

### 5. Telegram commands: reports and deletion

| ID | Feature | Scenario | Expected result |
|---|---|---|---|
| CMD-001 | `/start` | authorized user sends `/start` | onboarding/help message sent |
| CMD-002 | `/weekly` | weekly command | fetches current week window and sends formatted report |
| CMD-003 | `/daily` immediate | `/daily` without arguments | sends daily report keyboard |
| CMD-004 | `/daily` with valid date | `/daily 130126` | sends formatted report for that date |
| CMD-005 | `/daily` with invalid date | `/daily nope` | sends DDMMYY validation message |
| CMD-006 | `/monthly` immediate | `/monthly` without args | sends monthly report keyboard |
| CMD-007 | `/monthly` with valid month | `/monthly 0126` | sends formatted report for Jan 2026 |
| CMD-008 | `/monthly` with invalid month | `/monthly 1326` | sends MMYY validation message |
| CMD-009 | daily callback today | callback `dailyrep:today|...` active | sends today report |
| CMD-010 | daily callback past | callback `dailyrep:past|...` active | prompts for DDMMYY input and stores state |
| CMD-011 | daily callback expired | callback timestamp expired | user told `/daily` expired |
| CMD-012 | monthly callback current month | callback `monthrep:YYYYMM|...` active | sends that month report |
| CMD-013 | monthly callback earlier | callback `monthrep:earlier|...` active | prompts for MMYY input and stores state |
| CMD-014 | monthly callback expired | callback timestamp expired | user told `/monthly` expired |
| CMD-015 | stateful daily date entry valid | `awaiting_daily_report_date` and valid DDMMYY text | sends chosen daily report and clears state |
| CMD-016 | stateful daily date entry invalid | same state but invalid date | validation message, state retained |
| CMD-017 | stateful monthly entry valid | `awaiting_monthly_report_month` and valid MMYY | sends chosen monthly report and clears state |
| CMD-018 | stateful monthly entry invalid | same state but invalid input | validation message, state retained |
| CMD-019 | `/delete_last` with transaction | last transaction exists | transaction deleted and details sent |
| CMD-020 | `/delete_last` empty | no transactions found | "No transactions found." |
| CMD-021 | `/delete_today` with transactions | transactions exist for today | transaction keyboard sent |
| CMD-022 | `/delete_today` empty | no transactions today | "No transactions today." |
| CMD-023 | `/delete_past` missing date | command without argument | usage message sent |
| CMD-024 | `/delete_past` invalid date | bad DDMMYY input | validation message sent |
| CMD-025 | `/delete_past` valid with matches | date has transactions | transaction keyboard sent |
| CMD-026 | `/delete_past` valid without matches | date has no transactions | "No transactions on <date>." |
| CMD-027 | transaction delete callback | callback selects a transaction to delete | transaction removed and details echoed |
| CMD-028 | delete callback missing tx | selected transaction was already deleted | user told transaction no longer exists |

### 6. Telegram commands: budgets

| ID | Feature | Scenario | Expected result |
|---|---|---|---|
| BUD-001 | `/set_budget` interactive start | bare `/set_budget` | session `set_budget/choosing_category` created |
| BUD-002 | `/set_budget` inline command parse | `/set_budget Food 300` | budget saved immediately |
| BUD-003 | `/set_budget` invalid inline parse | malformed command | usage or validation response |
| BUD-004 | budget category callback valid | active session and valid category | prompts for amount and updates session payload |
| BUD-005 | budget category callback missing category | category no longer exists | warns and asks to restart |
| BUD-006 | budget category callback expired session | session expired | informs user `/set_budget` expired |
| BUD-007 | budget amount entry positive | active awaiting amount state with positive number | budget saved and category chooser re-shown |
| BUD-008 | budget amount entry zero | amount `0` | budget removed and category chooser re-shown |
| BUD-009 | budget amount entry negative | negative number | validation message, state retained |
| BUD-010 | budget amount entry non-numeric | text input | validation message, state retained |
| BUD-011 | budget flow done callback | user taps Done | session cleared and completion message sent |
| BUD-012 | `/list_budget` | budgets exist | formatted budget list sent |
| BUD-013 | `/list_budget` empty | no budgets exist | empty-state guidance sent |
| BUD-014 | `/budget_report` with budgets | budgets exist | formatted budget report sent |
| BUD-015 | `/budget_report` without budgets | no budgets exist | helper guidance sent |
| BUD-016 | `/remove_budget` valid category | category exists and budget exists | budget removed |
| BUD-017 | `/remove_budget` missing arg | no category provided | usage message sent |
| BUD-018 | `/remove_budget` unknown category | category not in category list | user warned category does not exist |
| BUD-019 | `/remove_budget` category with no budget | category exists but no budget stored | user told no budget found |

### 7. Telegram commands: category management

| ID | Feature | Scenario | Expected result |
|---|---|---|---|
| CCG-001 | `/new_category` start | command received | state set to `awaiting_new_cat_name` |
| CCG-002 | new category name valid | non-duplicate name entered before expiry | prompts for emoji |
| CCG-003 | new category name duplicate | existing category name entered | warns already exists |
| CCG-004 | new category flow expired | name or emoji entered after expiry | tells user `/new_category` expired |
| CCG-005 | new category emoji | valid emoji entered | category added to list and success message sent |
| CCG-006 | `/remove_category` start | categories exist | removal keyboard sent |
| CCG-007 | remove category callback valid | selected category exists | category mappings deleted, tx reassigned to Other, category removed |
| CCG-008 | remove category callback missing | category already missing | not-found message sent |
| CCG-009 | remove category callback expired | callback timestamp expired | tells user `/remove_category` expired |
| CCG-010 | `/edit_category` start | categories exist | edit keyboard sent |
| CCG-011 | edit category choose emoji | callback action `emoji` | prompts for new emoji |
| CCG-012 | edit category choose name | callback action `name` | prompts for new name |
| CCG-013 | edit category choose order | callback action `order` | prompts for new order |
| CCG-014 | edit category callback expired | expired callback timestamp | tells user `/edit_category` expired |
| CCG-015 | edit emoji valid | emoji submitted for existing category | updates category emoji |
| CCG-016 | edit emoji missing category | category no longer exists | not-found message |
| CCG-017 | rename category valid | new unique name | rename succeeds and tx/map counts shown |
| CCG-018 | rename category duplicate | name already exists | warning shown |
| CCG-019 | rename Other | current category is `Other` | rejected |
| CCG-020 | rename empty | whitespace-only new name | rejected |
| CCG-021 | rename missing category | backend rename returns false | not-found message |
| CCG-022 | reorder category valid | order inside valid range | order updated |
| CCG-023 | reorder category invalid low | order `0` | rejected |
| CCG-024 | reorder category invalid high | order greater than category count | rejected |
| CCG-025 | reorder Other | category is `Other` | rejected |
| CCG-026 | reorder missing category | backend update returns false | not-found message |

### 8. Telegram commands: dashboard account flow

| ID | Feature | Scenario | Expected result |
|---|---|---|---|
| ACC-001 | `/create_account` no account | user has no account | starts `dashboard_account` session at username step |
| ACC-002 | `/create_account` existing account | account already exists | presents choice keyboard to update/reuse |
| ACC-003 | account choice callback reuse | callback for existing account reuse | sends dashboard URL/login reminder |
| ACC-004 | account choice callback reset | callback chooses reset credentials | session restarts at username step |
| ACC-005 | account choice callback expired | callback timestamp expired | prompts user to rerun `/create_account` |
| ACC-006 | username entry valid | username passes validation and is available | session moves to password step |
| ACC-007 | username entry invalid pattern | contains spaces or too short | validation message |
| ACC-008 | username entry already taken | another account already uses username | validation message |
| ACC-009 | password entry too short | password below minimum length | validation message |
| ACC-010 | password entry valid | password acceptable | session moves to confirm step |
| ACC-011 | password confirmation mismatch | confirm text differs | user asked to re-enter password |
| ACC-012 | password confirmation success | confirmation matches | account upserted, previous sessions deleted, success message with dashboard link sent |
| ACC-013 | dashboard account flow expired | any step after expiry | user told setup expired |
| ACC-014 | `/change_password` with account | command sent by account owner | starts password reset flow |
| ACC-015 | `/change_password` without account | no account exists | told to use `/create_account` first |

### 9. Telegram commands: payment plan creation/listing

| ID | Feature | Scenario | Expected result |
|---|---|---|---|
| PLN-001 | `/set_recurring` start | command received | pending plan created and asks for item |
| PLN-002 | `/split_payment` start | command received | pending plan created and asks for item |
| PLN-003 | recurring item entry | awaiting recurring item | pending plan updated and category keyboard sent |
| PLN-004 | split item entry | awaiting split item | pending plan updated and category keyboard sent |
| PLN-005 | plan category existing | category selected from keyboard | next prompt depends on plan type |
| PLN-006 | plan category new | `__new__` selected | asks for new category name |
| PLN-007 | plan new category existing name | entered name already exists | skips emoji and continues flow |
| PLN-008 | plan new category brand-new name | entered unique name | asks for emoji |
| PLN-009 | plan new category emoji | emoji supplied | category added and continues flow |
| PLN-010 | recurring amount valid | positive amount | asks for start date |
| PLN-011 | recurring amount invalid | zero/negative/non-numeric | validation message |
| PLN-012 | recurring start date valid | valid DDMMYY date | plan created and first charge posted |
| PLN-013 | recurring start date invalid | invalid DDMMYY date | validation message |
| PLN-014 | split total valid | positive amount | asks for charge day |
| PLN-015 | split total invalid | zero/negative/non-numeric | validation message |
| PLN-016 | split day valid | day 1-31 | asks for month count |
| PLN-017 | split day invalid | invalid day | validation message |
| PLN-018 | split month count valid | positive integer | plan created and first charge posted |
| PLN-019 | split month count invalid | zero/negative/non-integer | validation message |
| PLN-020 | plan flow expired | any plan creation step after expiry | pending plan deleted and state cleared |
| PLN-021 | `/list_recurring` empty | no recurring plans | "No recurring payments found." |
| PLN-022 | `/list_recurring` non-empty | active/completed recurring plans | formatted plan list sent |
| PLN-023 | `/list_split_payment` empty | no split plans | "No split payments found." |
| PLN-024 | `/list_split_payment` non-empty | active/completed split plans | formatted plan list sent |

### 10. Telegram commands: payment plan edit/delete

| ID | Feature | Scenario | Expected result |
|---|---|---|---|
| PED-001 | `/edit_recurring` | matching plans exist | keyboard sent |
| PED-002 | `/edit_split_payment` | matching plans exist | keyboard sent with split edit notice |
| PED-003 | edit command empty | no matching plans | "No matching plans found." |
| PED-004 | choose plan to edit | callback selects plan | prompts for editable fields |
| PED-005 | edit callback expired | old callback timestamp | asks user to rerun edit command |
| PED-006 | edit item valid | new item text | plan edit stored pending rewrite choice |
| PED-007 | edit amount recurring valid | positive amount | rewrite choice shown |
| PED-008 | edit amount recurring invalid | invalid amount | validation message |
| PED-009 | edit day valid | day 1-31 | rewrite choice shown |
| PED-010 | edit day invalid | invalid day | validation message |
| PED-011 | edit months valid split | month count >= posted installments | rewrite choice shown |
| PED-012 | edit months invalid split | month count < posted installments | rejected |
| PED-013 | edit category existing | category chosen from keyboard | rewrite choice shown |
| PED-014 | edit category new | new category entered through name/emoji flow | rewrite choice shown |
| PED-015 | rewrite prompt future mode | user picks future-only | plan updated but past auto tx untouched |
| PED-016 | rewrite prompt rewrite mode | user picks rewrite | `rewrite_plan_history()` called |
| PED-017 | rewrite prompt expired | pending edit expired | pending plan deleted and state cleared |
| PED-018 | split rewrite projection text | split plan edit pending | prompt explains future vs rewrite with projected months |
| PED-019 | split rewrite result text | split edit applied | response summarizes new schedule |
| PED-020 | `/delete_recurring` | matching recurring plans exist | delete keyboard sent |
| PED-021 | `/delete_split_payment` | matching split plans exist | delete keyboard sent |
| PED-022 | recurring delete mode future | choose stop future only | plan deleted, past charges kept |
| PED-023 | recurring delete mode all | choose stop future + remove past | plan deleted and plan tx removed |
| PED-024 | split delete | split plan delete confirmation | plan deleted and plan tx removed |
| PED-025 | delete callback expired | expired timestamp | asks user to rerun delete command |
| PED-026 | delete callback missing plan | plan no longer exists | not-found message |

### 11. Change-category and change-date actions from transaction confirmations

| ID | Feature | Scenario | Expected result |
|---|---|---|---|
| CHG-001 | change category action start | callback from transaction confirmation | pending change saved and category keyboard sent |
| CHG-002 | change category with existing category | category selected | transaction category updated and mapping saved |
| CHG-003 | change category with new category name | unique name entered | prompts for emoji |
| CHG-004 | change category with duplicate typed name | typed name matches existing category | reuses category without emoji prompt |
| CHG-005 | change category with emoji | emoji supplied | new category created and tx updated |
| CHG-006 | change category expired | pending change older than expiry | asks user to start change again |
| CHG-007 | change date action start | callback on eligible transaction | prompts for DDMMYY input |
| CHG-008 | change date valid | valid DDMMYY entered | timestamp updated preserving original time-of-day |
| CHG-009 | change date invalid | invalid DDMMYY entered | validation message |
| CHG-010 | change date missing tx | transaction already deleted | not-found message |
| CHG-011 | change date expired | pending change expired | asks user to tap change date again |

### 12. Reports router and scheduled endpoints

| ID | Feature | Scenario | Expected result |
|---|---|---|---|
| RPT-001 | daily report window | period `daily` | window is current SGT day 00:00 to next day 00:00 |
| RPT-002 | weekly report window | period `weekly` | window starts Monday 00:00 SGT and spans 7 days |
| RPT-003 | monthly report window mid-month | period `monthly` and now not day 1 | reports current month |
| RPT-004 | monthly report window on day 1 | period `monthly` and now is first day | reports previous month |
| RPT-005 | invalid period | period not daily/weekly/monthly | raises 400 |
| RPT-006 | formatted aggregate report empty | no transactions | returns "No expenses recorded." block |
| RPT-007 | formatted aggregate report populated | transactions across categories | totals grouped by category and sorted descending |
| RPT-008 | formatted daily report populated | multiple transactions same day | lines sorted by timestamp and include times |
| RPT-009 | budget report empty | no budgets | returns empty string |
| RPT-010 | budget report populated | budgets and spending exist | shows spent vs prorated per category and totals |
| RPT-011 | `/trigger-report` forbidden missing secret | no secret or wrong header | returns 403 |
| RPT-012 | `/trigger-report` no authorized chats | empty allowed chats | returns 500 |
| RPT-013 | `/trigger-report` daily | valid secret and chats | sends one daily report per chat and returns tx count |
| RPT-014 | `/trigger-report` weekly | valid secret | sends weekly aggregate report |
| RPT-015 | `/trigger-report` monthly | valid secret | sends monthly aggregate report |
| RPT-016 | `/trigger-budget-report` forbidden | wrong header | returns 403 |
| RPT-017 | `/trigger-budget-report` no budgets for a chat | valid secret but empty budgets | sends setup guidance |
| RPT-018 | `/trigger-budget-report` with budgets | valid secret and budgets | sends formatted budget report |
| RPT-019 | `/trigger-recurring-payments` forbidden | wrong header | returns 403 |
| RPT-020 | `/trigger-recurring-payments` success | valid secret | returns processed count from `process_due_plans()` |

### 13. Payment plan helper and manager services

| ID | Feature | Scenario | Expected result |
|---|---|---|---|
| PM-001 | `clamp_day` | day exceeds month length | clamped to month end |
| PM-002 | `month_due_date` | valid year/month/day | returns SGT datetime |
| PM-003 | `next_month` | December rollover | returns January of next year |
| PM-004 | `add_months` | positive delta across years | returns correct year/month |
| PM-005 | `compute_split_amounts` | amount not evenly divisible | remainder carried in final installment |
| PM-006 | `plan_occurrence_for_index` recurring | recurring plan index | amount is monthly amount, installment number fixed at 1 |
| PM-007 | `plan_occurrence_for_index` split | split plan last installment | final installment amount used |
| PM-008 | `occurrence_label` recurring | recurring plan occurrence | label is `Auto: recurring` |
| PM-009 | `occurrence_label` split | split occurrence | label includes installment progress |
| PM-010 | `compute_next_due_date` recurring | recurring with posted count N | returns occurrence at index N |
| PM-011 | `compute_next_due_date` split active | posted count < total | returns next installment due date |
| PM-012 | `compute_next_due_date` split complete | posted count >= total | returns `None` |
| PM-013 | `due_today` | next due same date as today | returns true |
| PM-014 | `plan_display_line` recurring | recurring plan | shows monthly amount and open-ended |
| PM-015 | `plan_display_line` split | split plan | shows total and installment progress |
| PM-016 | `start_pending_plan` | start recurring/split flow | pending plan persisted with timestamp |
| PM-017 | `create_plan_and_post_first_charge` recurring | complete pending data | plan saved, first occurrence posted, pending cleared |
| PM-018 | `create_plan_and_post_first_charge` split | complete pending data | split plan saved, base/final amounts calculated, first occurrence posted |
| PM-019 | `post_next_occurrence` inactive plan | status not active | returns false and does nothing |
| PM-020 | `post_next_occurrence` duplicate occurrence | matching tx already exists | returns false |
| PM-021 | `post_next_occurrence` recurring success | active recurring plan due | saves auto-generated tx, increments posted count, updates next due |
| PM-022 | `post_next_occurrence` final split installment | last occurrence posted | plan status becomes completed |
| PM-023 | `process_due_plans` with due plans | multiple due plans, some duplicates | only newly posted occurrences counted |
| PM-024 | `rewrite_plan_history` missing plan | plan id not found | returns 0 |
| PM-025 | `rewrite_plan_history` recurring | active recurring plan from past months | rebuilds past months up to current month |
| PM-026 | `rewrite_plan_history` split | split plan shortened/edited | rebuilds only applicable installments and updates next due |
| PM-027 | `pending_plan_expired` | no pending doc | returns true |
| PM-028 | `pending_plan_expired` | missing created_at | returns true |
| PM-029 | `pending_plan_expired` | within TTL | returns false |

### 14. Interaction sessions and dashboard auth helpers

| ID | Feature | Scenario | Expected result |
|---|---|---|---|
| SVC-001 | `start_session` | explicit expiry seconds | persisted session contains matching `expires_at` |
| SVC-002 | `is_expired` | active session | returns false |
| SVC-003 | `is_expired` | expired session | returns true |
| SVC-004 | `is_expired` | missing or malformed `expires_at` | returns true |
| SVC-005 | `get_active_session` | wrong flow type requested | returns `None` |
| SVC-006 | `update_session` | payload updates supplied | payload merged, not replaced |
| SVC-007 | `update_session` | no session exists | returns `None` |
| SVC-008 | `clear_session` | session exists | session deleted |
| SVC-009 | username normalization | mixed case and spaces | lowercased and trimmed |
| SVC-010 | username validation | allowed punctuation `_.-` | accepted |
| SVC-011 | username validation | too short or contains spaces | rejected |
| SVC-012 | password validation | length below minimum | returns message |
| SVC-013 | password validation | valid length | returns `None` |
| SVC-014 | hash/verify round trip | valid password | hash verifies true |
| SVC-015 | verify invalid hash format | malformed stored hash | returns false |
| SVC-016 | verify wrong algorithm label | non-`pbkdf2_sha256` hash | returns false |
| SVC-017 | session token | build token | token is non-empty and URL-safe |
| SVC-018 | session doc id | same token twice | deterministic SHA-256 hex |
| SVC-019 | session expiry | fixed input datetime | adds one day |

### 15. Dashboard API: authentication and bootstrap

| ID | Feature | Scenario | Expected result |
|---|---|---|---|
| DSH-001 | session source precedence | cookie and header both present | cookie token used first |
| DSH-002 | session source fallback | no cookie, header present | header token used |
| DSH-003 | session source fallback | no cookie/header, bearer present | bearer token used |
| DSH-004 | session source absent | no token anywhere | returns unauthenticated or 401 depending on endpoint |
| DSH-005 | `/dashboard/auth/session` unauthenticated | no session token | returns `authenticated=false` |
| DSH-006 | `/dashboard/auth/session` authenticated | valid session token | returns username and chat id |
| DSH-007 | `/dashboard/auth/login` valid | active account and valid password | session saved, cookie set, token returned |
| DSH-008 | `/dashboard/auth/login` unknown username | no account found | 401 |
| DSH-009 | `/dashboard/auth/login` inactive account | account `active=false` | 401 |
| DSH-010 | `/dashboard/auth/login` wrong password | verification fails | 401 |
| DSH-011 | `/dashboard/auth/logout` with cookie | cookie token present | session deleted and cookie cleared |
| DSH-012 | `/dashboard/auth/logout` without cookie | no cookie token | still returns `{"ok": true}` |
| DSH-013 | `/dashboard/bootstrap` authenticated | valid session | returns account, categories, budgets, preferences |
| DSH-014 | `/dashboard/bootstrap` unauthorized | no session | 401 |

### 16. Dashboard API: transactions

| ID | Feature | Scenario | Expected result |
|---|---|---|---|
| DTX-001 | list transactions | valid start/end | returns current user's transactions sorted newest first |
| DTX-002 | list transactions filter | category query provided | filters to that category |
| DTX-003 | list transactions invalid datetime | bad `start` or `end` | 400 |
| DTX-004 | create one-time tx valid | valid payload | manual transaction saved |
| DTX-005 | create tx empty item | whitespace item | 400 |
| DTX-006 | create tx empty category | whitespace category | 400 |
| DTX-007 | create tx non-positive amount | amount `<= 0` | 400 |
| DTX-008 | create tx invalid payment type | unknown `payment_type` | 400 |
| DTX-009 | create recurring valid immediate | valid payload and `create_first_transaction_now=true` | plan saved and first occurrence posted |
| DTX-010 | create recurring valid scheduled | `create_first_transaction_now=false` | plan saved with future start month if past day-of-month |
| DTX-011 | create split valid immediate | valid split payload | plan saved, base/final amounts computed, first occurrence posted |
| DTX-012 | create split valid scheduled | scheduled split | no immediate tx and next due set correctly |
| DTX-013 | create recurring missing start date | no `start_date` | 400 |
| DTX-014 | create recurring invalid start date | invalid `start_date` | 400 |
| DTX-015 | create split missing installment count | no months provided | 400 |
| DTX-016 | create split invalid installment count | months < 1 | 400 |
| DTX-017 | update transaction valid | owned transaction and valid payload | tx doc updated |
| DTX-018 | update transaction missing | tx not found or owned by another chat | 404 |
| DTX-019 | update transaction invalid datetime | bad timestamp | 400 |
| DTX-020 | update transaction invalid fields | empty item/category or amount <= 0 | 400 |
| DTX-021 | delete transaction valid | owned transaction exists | tx deleted |
| DTX-022 | delete transaction missing | tx not found or wrong chat id | 404 |

### 17. Dashboard API: categories, budgets, preferences, plans

| ID | Feature | Scenario | Expected result |
|---|---|---|---|
| DCT-001 | list categories | authenticated | returns current user's categories |
| DCT-002 | create category valid | unique name, emoji optional | category added |
| DCT-003 | create category empty | blank name | 400 |
| DCT-004 | create category duplicate | name already exists | 400 |
| DCT-005 | update category emoji only | same name, new emoji | emoji updated |
| DCT-006 | update category rename valid | unique new name | rename succeeds and emoji updated |
| DCT-007 | update category rename duplicate | target already exists | 400 |
| DCT-008 | update category rename Other | rename `Other` to something else | 400 |
| DCT-009 | update category missing | backend cannot find category | 404 |
| DCT-010 | delete category valid | non-Other category exists | tx reassigned to Other and category removed |
| DCT-011 | delete category Other | path category is `Other` | 400 |
| DCT-012 | delete category missing | category list removal returns false | 404 |
| DCT-013 | move category up/down valid | direction `-1` or `1` in bounds | order updated |
| DCT-014 | move category invalid direction | direction not `-1` or `1` | 400 |
| DCT-015 | move category Other | reorder Other | 400 |
| DCT-016 | move category beyond bounds | move first up or last down | returns ok without change |
| DCT-017 | move category missing | category not found | 404 |
| DBT-001 | list budgets | authenticated | returns budgets map |
| DBT-002 | patch budget positive | amount > 0 | budget set |
| DBT-003 | patch budget zero | amount == 0 | budget removed |
| DBT-004 | patch budget negative | amount < 0 | 400 |
| DBT-005 | delete budget | authenticated | budget removed |
| DPR-001 | get preferences | authenticated | returns preferences |
| DPR-002 | patch preferences | visible cards list provided | preferences updated |
| DPL-001 | list plans | authenticated | returns all current user's plans |
| DPL-002 | patch recurring plan item/category/day | valid fields | plan updated and next due recomputed |
| DPL-003 | patch recurring plan amount | positive amount | amount updated |
| DPL-004 | patch recurring plan total_amount | recurring plan with split-only field | 400 |
| DPL-005 | patch split plan total/months | valid values | base/final recalculated and rewrite triggered |
| DPL-006 | patch split plan amount field | split plan with recurring-only field | 400 |
| DPL-007 | patch split months below posted | installment count less than posted | 400 |
| DPL-008 | patch plan empty item/category | blank string | 400 |
| DPL-009 | patch plan invalid day | day outside 1..31 | 400 |
| DPL-010 | patch plan missing/foreign | plan not found or wrong chat id | 404 |
| DPL-011 | delete recurring plan future mode | `mode=future` | plan deleted, past tx retained |
| DPL-012 | delete recurring plan all mode | `mode=all` | plan deleted and plan tx removed |
| DPL-013 | delete split plan default mode | split plan deleted | plan tx removed even with default mode |
| DPL-014 | delete plan missing/foreign | plan not found or wrong chat id | 404 |

### 18. Firestore-backed category and budget data management

| ID | Feature | Scenario | Expected result |
|---|---|---|---|
| FDB-001 | per-user category isolation | two chat ids use same item key | mappings remain isolated |
| FDB-002 | remove category also removes budget | category removed from list | matching budget key removed |
| FDB-003 | rename category moves budget key | renamed category has budget | budget key renamed too |
| FDB-004 | get budgets cleanup | orphaned, zero, or negative budget entries exist | only active positive budgets returned and stored |
| FDB-005 | migration legacy global shape | legacy top-level docs exist | moved into `users/<chat_id>/...` subcollections |
| FDB-006 | migration top-level user-scoped shape | `123:<id>` docs exist | moved into user subcollections |
| FDB-007 | migration dry-run | dry-run enabled | reports counts without writes |
| FDB-008 | migration ambiguous source | mixed source shapes exist | raises error |
| FDB-009 | migration existing target data | target subcollections already populated | raises error |
| FDB-010 | clone user categories | empty target user | category list and map cloned |
| FDB-011 | clone user categories target exists | target already has data | raises error |

## Highest-value missing tests to implement first

If you want to turn this into code incrementally, start here:

1. Webhook command matrix: `/start`, `/daily`, `/weekly`, `/monthly`, `/delete_*`, `/new_category`, `/remove_category`, `/edit_category`, `/create_account`, `/change_password`, `/set_recurring`, `/split_payment`
2. Categoriser tests: known-item save, unknown-item pending, category selection, custom category creation, budget warning
3. Scheduler endpoint authorization tests: `/trigger-report`, `/trigger-budget-report`, `/trigger-recurring-payments`
4. Dashboard negative-path tests: unauthorized access, invalid payloads, cross-user access rejection
5. Payment-plan edit/delete webhook flows, especially split-plan rewrite behavior

## Suggested test-file expansion

- `test_webhook_reports_and_delete.py`
- `test_webhook_categories.py`
- `test_webhook_dashboard_account.py`
- `test_webhook_payment_plans.py`
- `test_categoriser.py`
- `test_reports_router.py`
- `test_dashboard_router_negative_paths.py`
- `test_payment_plan_webhook_edits.py`

