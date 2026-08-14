# Changelog

All notable changes to Voice Budget Bot will be documented in this file.

## [Unreleased]

### Added
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
- Default maximum voice-message duration is 16 seconds.
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
