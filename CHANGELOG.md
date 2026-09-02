# Changelog

All notable changes to Voice Budget Bot will be documented in this file.

## [Unreleased]

### Added
- `/ask`: read-only natural-language analytics over personal and family records.
  Text or voice question → text or PNG-infographic answer. Includes:
  - `AnalyticsRepository` with a separate SQLite read-only connection
    (`mode=ro` + `PRAGMA query_only=ON`) and enforced visibility predicates
    (personal scope and family scope), no write methods.
  - Deterministic policy classifier that rejects write requests, out-of-scope and
    prompt-injection/security attempts before any query.
  - Query planner (optional LLM via DeepSeek or a dedicated `ASK_*` endpoint,
    with deterministic fallback), server-side `AnalyticsCalculator` for all
    arithmetic in integer minor units, and `AskRenderer` producing text or PNG
    (bar/line/pie) output.
  - In-memory `/ask` sessions with `/cancel` and `ASK_SESSION_TTL_SEC`,
    `ASK_MAX_ROWS`, `ASK_MAX_QUESTION_LENGTH` and rate limiting.
  - Shared currency-conversion helpers extracted to
    `services/currency_conversion.py` (used by both reports and /ask).
- Security tests for family isolation, SQLite read-only enforcement and policy
  classification.
- Pending exchange-rate dialogs are persisted in a new `pending_exchanges` table
  and survive container restarts; expired dialogs are cleaned by the scheduler.
- Report charts now warn (caption + log) when transactions are skipped because no
  exchange rate to the user's main currency is known.
- Monthly report bundle catch-up: if the 1st of the month is missed, the report is
  retried on the 2nd and 3rd day (deduplicated via `report_deliveries`).
- ffmpeg conversion errors now carry and log the stderr tail for diagnosis.
- Centralized access checks in `services/access.py` shared by `bot.py` and the
  voice/text handler.

### Changed
- `STT_VERIFY_SSL` defaults to `true` (secure by default); set explicitly to
  `false` in `.env` only for a trusted network/self-signed gateway.
- Concurrent currency conversions allocate unique `exchange_pair_id` values
  (single IMMEDIATE transaction instead of a racy `MAX()+1` read).
- `requirements.txt` pins `SQLAlchemy==2.0.52`.
- Default voice limit documented as 20 seconds in `.env.example` and docs.

## [2.1.0] - 2026-09-02

### Added
- Multi-currency tracking: transactions keep their own currency and amounts in
  integer minor units; new `EXCHANGE` intent converts money between currencies at a
  user-specified rate.
- Currency conversion: "перевёл 2000 долларов в рубли по курсу 92" creates two
  mirror records (expense in the source currency and income in the target currency,
  category `TRANSFERS`) linked by `exchange_pair_id`, both storing the applied
  `exchange_rate` and `from_currency`/`from_amount_minor` for future analysis.
- Two ways to declare a conversion: with an explicit rate, or with both amounts
  ("поменял 2000 долларов на 100 000 армянских драм") — the bot computes the rate
  itself. New currency `AMD` (Armenian dram) is supported.
- If neither the rate nor the resulting amount is mentioned, the bot asks for the
  rate in a short dialog (the pending conversion is completed when the user replies
  with a number).
- `/balance` — running balance per currency (`INCOME - EXPENSE`, conversions move
  money between currencies automatically).
- `/currency [CODE]` — show or change the user's main currency (stored on `users.main_currency`).
- Reports in a main currency: expense/income pie charts convert every operation to
  the user's main currency using stored exchange rates (mirror records and the most
  recent rate for the pair). Detailed CSV export now includes the original amount
  and currency plus `amount_main`/`main_currency`, `from_currency`, `from_amount`,
  `exchange_rate`, `exchange_pair_id`.
- Family layer: `families` and `family_members` tables, `/family` (create/status),
  `/family create <name>`, `/family invite` (invite code), `/join <code>`.
- Transaction scope: `scope = personal | family`, `family_id`, `paid_by` columns on
  `transactions` and `scheduled_events`. Inline buttons `Семейное` / `Личное` after
  saving a transaction let the author switch scope.
- Transparent schema migration: `_run_schema_migrations` (idempotent `ALTER TABLE`
  for existing DBs) and `_backfill_legacy_rows` (`paid_by = author` for existing rows).
  Existing data is preserved and defaults to `personal` scope.
- Primary STT is now the local OpenAI-compatible gateway (`STT_BASE_URL`, default `https://stt.example.com:7443/v1`, model `Systran/faster-whisper-large-v3`).
- Groq became an optional fallback STT channel (`GROQ_FALLBACK_ENABLED`), used when the primary STT fails or returns an empty transcript.
- Added direct text input for transactions, reminders, and deferred expenses through the same parser path as voice transcripts.
- Added `/report` and a Telegram menu button for last-30-days expense and income pie charts.
- Added automatic previous-calendar-month report bundle delivery on the 1st day of each month: expense chart, income chart, and CSV.gz with all records for the period.
- Added the default `ALCOHOL` expense category for alcohol purchases.
- Detailed configurable application logs with 2 MiB file rotation and two retained backups.
- Docker JSON log rotation capped at three files of 2 MiB.
- Applied the existing optional `ALLOWED_USER_IDS`/`ALLOWED_CHAT_IDS` access primitive consistently to commands and inline buttons.

### Changed
- Fixed: voice normalization no longer truncates recordings to 8 seconds (`-t 8` in
  the ffmpeg command was silently cutting every message); the full voice message is
  now re-encoded and recognized. Long recordings kept losing their tail (e.g. the
  target "… на 140 000 драм" in a currency conversion).
- Default maximum voice-message duration is now 20 seconds.
- Removed the manual `/export` command; detailed CSV export is now included in the automatic monthly report bundle.

## [1.0.0] - 2026-07-22

### Added
- Added a root-friendly interactive VPS installer.
- Documented one-line installation and configuration locations.
- Added a permanent fork author GitHub link to the bot welcome message.

## [0.1.0] - 2026-07-21

### Added
- Rebuilt SmartExpenseBot fork as a voice-only budget MVP.
- Added Groq STT, DeepSeek transaction extraction and strict server validation.
- Added SQLite schema for users, chats, transactions and processing events.
- Added Docker Compose deployment with isolated `voice-budget-bot` service.

## [0.2.0] - 2026-07-21

### Added
- Added `TRANSFERS` category for family money transfers in expenses and income.
- Added delete button to successful transaction messages.
- Added Telegram controls for creating and deleting user categories.
- Added SmartExpense 2.0 welcome text with available categories.

## [0.3.0] - 2026-07-21

### Added
- Added deferred expenses with automatic future transaction creation.
- Added one-time and recurring voice reminders.
- Added `/calendar` command with upcoming events for the next 2 months.
- Added scheduler loop for due reminders and deferred expenses.

## [0.4.0] - 2026-07-22

### Added
- Added configurable welcome message and welcome image settings.
- Added Telegram command menu and reply keyboard menu.
- Added delete button for scheduled reminders and deferred expenses.
- Added README command list and collapsible category list.

### Changed
- Replaced README overview image with the new `desc3` asset.
- Removed the `/kalendar` alias; `/calendar` remains the only calendar command.
