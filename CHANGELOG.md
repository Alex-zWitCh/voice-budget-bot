# Changelog

All notable changes to Voice Budget Bot will be documented in this file.

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
