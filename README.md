# SmartExpenseBot

<p align="center">
  <strong>An intelligent personal finance assistant powered by AI</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-blue.svg" alt="Python 3.8+"/>
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License"/>
  <img src="https://img.shields.io/badge/Telegram-Bot-blue.svg" alt="Telegram Bot"/>
  <img src="https://img.shields.io/badge/code%20style-PEP%208-orange.svg" alt="PEP 8"/>
</p>

<p align="center">
  Track expenses and income, generate reports, and set reminders — all through natural language conversations in your preferred language.
</p>

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Technology Stack](#technology-stack)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Architecture](#architecture)
- [Contributing](#contributing)
- [License](#license)
- [Author](#author)

---

## Overview

**SmartExpenseBot** is a sophisticated Telegram bot that makes personal finance management effortless. Instead of filling out forms, users can simply chat with the bot — in text or voice — to record expenses, check balances, and receive intelligent financial reports.

Powered by **DeepSeek AI** and advanced NLP, the bot understands context across Uzbek, Russian, and English.

---

## Key Features

- **AI-Powered Intelligence** — Four specialized AI instances handle parsing, categorization, reporting, and reminders.
- **Universal Language Support** — Full support for English, Russian, and Uzbek with intelligent country detection.
- **Voice-First Design** — Record expenses and income via voice messages with automatic transcription.
- **Smart Automation** — Automated daily reminders at personalized times.
- **Intelligent Reporting** — Ask natural language questions for instant financial insights and balance summaries.
- **Income Tracking** — Track monthly and daily income alongside expenses.
- **Unified Currency System** — Single currency preference for all financial operations.
- **Privacy-Focused** — Local SQLite database by default, with optional PostgreSQL support.

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Bot Framework | python-telegram-bot |
| AI / NLP | DeepSeek AI |
| Database | SQLite (default) / PostgreSQL (optional) |
| Scheduling | APScheduler |
| Language | Python 3.8+ |

---

## Installation

### Prerequisites

- Python 3.8 or higher
- A Telegram Bot Token from [@BotFather](https://t.me/BotFather)
- DeepSeek AI API key

### Steps

```bash
# Clone the repository
git clone https://github.com/BotirBakhtiyarov/SmartExpenseBot.git
cd SmartExpenseBot

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your Telegram token and DeepSeek API key

# Run the bot
python main.py
```

---

## Configuration

Create a `.env` file with the following variables:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
DEEPSEEK_API_KEY=your_deepseek_api_key
DATABASE_URL=sqlite:///expenses.db
```

For PostgreSQL, set:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/smartexpense
```

---

## Usage

Start a conversation with your bot on Telegram and try:

- `I spent 50,000 UZS on lunch today`
- `Show my monthly report`
- `Remind me about rent every 1st day`
- `How much did I earn this month?`

---

## Project Structure

```
SmartExpenseBot/
├── bot/                # Telegram bot handlers and dialogs
├── ai/                 # DeepSeek AI integration modules
├── database/           # Database models and migrations
├── services/           # Business logic (reports, reminders, parsing)
├── config.py           # Configuration management
├── main.py             # Application entry point
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
└── README.md
```

---

## Architecture

SmartExpenseBot uses a modular pipeline architecture:

1. **Input Layer** — Receives text or voice messages from Telegram.
2. **AI Parsing Layer** — DeepSeek AI extracts amount, category, date, and type.
3. **Storage Layer** — Saves transactions to SQLite or PostgreSQL.
4. **Reporting Layer** — Generates summaries and answers natural language queries.
5. **Scheduler Layer** — Sends reminders at configured times.

---

## Contributing

Contributions are welcome!

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add your feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

Please follow PEP 8 style guidelines.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## Author

**Botir Bakhtiyarov**

- Email: hello@bbotir.xyz
- Website: https://bbotir.xyz
- Telegram: [@opensource_uz](https://t.me/opensource_uz)
