# SmartExpenseBot

<div align="center">

**An intelligent personal finance assistant Telegram bot powered by AI**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-blue.svg)](https://telegram.org/)
[![Code Style](https://img.shields.io/badge/code%20style-PEP%208-orange.svg)](https://www.python.org/dev/peps/pep-0008/)

**Track expenses, generate reports, set reminders - all through natural language conversations in your preferred language**

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Technology Stack](#-technology-stack)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage Guide](#-usage-guide)
- [Architecture](#-architecture)
- [Project Structure](#-project-structure)
- [API Documentation](#-api-documentation)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)
- [Author & Support](#-author--support)

## 🎯 Overview

**SmartExpenseBot** is a sophisticated Telegram bot designed to help users manage their personal finances effortlessly. Leveraging the power of **DeepSeek AI** and advanced natural language processing, it transforms expense tracking from a tedious task into an intuitive conversation.

### Core Philosophy

The bot understands that managing finances shouldn't be complicated. Whether you're on-the-go, prefer voice messages, or speak different languages, SmartExpenseBot adapts to your needs and helps you maintain better financial awareness.

### Key Highlights

- **🤖 AI-Powered Intelligence**: Three specialized AI instances handle different aspects of financial management
- **🌍 Universal Language Support**: Full support for English, Russian, and Uzbek with intelligent country detection
- **🎤 Voice-First Design**: Record expenses via voice messages with automatic transcription
- **⏰ Smart Automation**: Automated daily reminders at personalized times
- **📊 Intelligent Reporting**: Natural language queries for instant financial insights
- **🔒 Privacy-Focused**: Local database storage with optional PostgreSQL support

## ✨ Key Features

### 💸 Intelligent Expense Management

**Multi-Modal Input**
- Text messages: `"Spent 50 yuan on lunch"`
- Voice messages: Speak naturally about your expenses
- Support for multiple expenses in a single message

**AI-Powered Categorization**
- Automatic expense extraction (amount, currency, description)
- Smart category assignment (Food, Transport, Entertainment, etc.)
- Currency detection and normalization
- Intelligent fallback for edge cases

**Multiple Currency Support**
- Automatic currency detection (USD, EUR, CNY, RUB, UZS, etc.)
- User-defined default currency preference
- Cross-currency expense tracking

**Confirmation Workflow**
- Review AI-extracted information before saving
- Batch confirmation for multiple expenses
- Easy cancellation and modification

### 📊 Advanced Reporting & Analytics

**Natural Language Queries**
- Ask questions in plain language: `"Show my food expenses this month"`
- Conversational report generation
- Context-aware responses based on your expense history

**Flexible Time Filtering**
- Daily, weekly, monthly reports
- Custom date range selection
- Historical data analysis

**Comprehensive Insights**
- Category-based breakdowns
- Spending trends and patterns
- Total expense calculations
- Visual summaries

### ⏰ Smart Reminder System

**Intelligent Time Parsing**
- Natural language time expressions: `"Remind me tomorrow at 3 PM"`
- Relative time handling: `"Remind me in 2 hours"`
- Timezone-aware scheduling

**Dual Notification System**
- Warning notification 10 minutes before scheduled time
- Exact time reminder notification
- Automatic reminder tracking

**Daily Expense Reminders**
- Personalized daily notifications at 20:00 (user's local time)
- Automatic scheduling based on user timezone
- Multi-language reminder messages

### 🌍 Internationalization & Localization

**Language Support**
- **English**: Full feature support
- **Russian (Русский)**: Complete localization
- **Uzbek (O'zbek)**: Full native language support

**Smart Country Detection**
- AI-powered country name recognition in any supported language
- Automatic timezone detection from country input
- Location-based timezone detection via GPS coordinates
- Manual timezone configuration option

**Localized User Experience**
- Language-specific date/time formatting
- Cultural context awareness
- Native currency suggestions

### 🎤 Voice Transcription

**Multi-Language Voice Support**
- Voice message transcription using Vosk
- Support for Uzbek, Russian, and English
- Automatic language detection and model selection

**Optimized Performance**
- Shared model cache (loads once, used by all instances)
- Thread-safe model initialization
- Efficient memory management

**Audio Processing**
- Automatic format conversion (OGG, MP3 → WAV)
- Sample rate normalization (16kHz mono)
- Clean temporary file management

### 🛡️ Robust Architecture

**Thread-Safe Operations**
- Concurrent user request handling
- Safe database session management
- Atomic operations for data integrity

**Database Flexibility**
- SQLite for development and small deployments
- PostgreSQL for production scalability
- Automatic schema migration
- Connection pooling

**Error Handling**
- Comprehensive exception catching
- Graceful degradation
- Detailed logging for debugging
- User-friendly error messages

## 🛠 Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| **Language** | Python | 3.8+ |
| **Bot Framework** | pyTelegramBotAPI | 4.14.0 |
| **ORM & Database** | SQLAlchemy | ≥2.0.36 |
| **Database Drivers** | SQLite3 (built-in), psycopg2-binary | 2.9.10 |
| **AI Integration** | DeepSeek API | Latest |
| **Speech Recognition** | Vosk | 0.3.45 |
| **Task Scheduling** | APScheduler | 3.10.4 |
| **Audio Processing** | FFmpeg, pydub | 0.25.1 |
| **Timezone Handling** | pytz, timezonefinderL | 2024.1, 0.1.0 |
| **HTTP Requests** | requests | 2.32.4 |
| **Date Parsing** | python-dateutil | 2.8.2 |
| **Configuration** | python-dotenv | 1.0.0 |

## 📦 Prerequisites

Before installing SmartExpenseBot, ensure you have:

- **Python 3.8 or higher** (Python 3.10+ recommended)
- **FFmpeg** installed and accessible in PATH
- **Telegram Bot Token** (obtain from [@BotFather](https://t.me/BotFather))
- **DeepSeek API Key** (obtain from [DeepSeek Platform](https://platform.deepseek.com/))
- **Vosk Models** (optional, for voice transcription)

### System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install ffmpeg python3-pip python3-venv
```

**macOS:**
```bash
brew install ffmpeg python3
```

**Windows:**
- Download Python from [python.org](https://www.python.org/downloads/)
- Download FFmpeg from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH

## 🚀 Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/botirbakhtiyarov/SmartExpenseBot.git
cd SmartExpenseBot
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### Step 3: Install Python Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Download Vosk Models (Optional but Recommended)

For voice transcription support, download language models from [Vosk Models](https://alphacephei.com/vosk/models):

**Recommended Models:**
- `vosk-model-small-uz-0.22` (Uzbek - ~45MB)
- `vosk-model-small-ru-0.22` (Russian - ~45MB)
- `vosk-model-small-en-us-0.22` (English - ~45MB)

**Installation Steps:**

1. Download the models:
```bash
# Create models directory
mkdir -p models

# Download and extract (example for Uzbek)
cd models
wget https://alphacephei.com/vosk/models/vosk-model-small-uz-0.22.zip
unzip vosk-model-small-uz-0.22.zip
mv vosk-model-small-uz-0.22 vosk-model-uz

# Repeat for other languages
cd ..
```

2. Verify structure:
```
models/
├── vosk-model-uz/
│   ├── am/
│   ├── conf/
│   └── ...
├── vosk-model-ru/
│   └── ...
└── vosk-model-en/
    └── ...
```

## ⚙️ Configuration

### Step 1: Create Environment File

Create a `.env` file in the project root:

```bash
cp .env.example .env  # If example exists
# Or create manually
touch .env
```

### Step 2: Configure Environment Variables

Edit `.env` with your configuration:

```env
# ============================================
# REQUIRED CONFIGURATION
# ============================================

# Telegram Bot Token (from @BotFather)
BOT_TOKEN=your_telegram_bot_token_here

# DeepSeek API Configuration
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_API_URL=https://api.deepseek.com/v1/chat/completions

# ============================================
# OPTIONAL CONFIGURATION
# ============================================

# Developer ID (for receiving feedback)
DEVELOPER_ID=your_telegram_user_id

# Database Configuration
# Options: 'sqlite' or 'postgresql'
DB_TYPE=sqlite

# SQLite Configuration (if DB_TYPE=sqlite)
SQLITE_DB_PATH=smart_expense_bot.db

# PostgreSQL Configuration (if DB_TYPE=postgresql)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=smart_expense_bot
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# Vosk Model Paths (optional)
VOSK_MODEL_PATH_UZ=./models/vosk-model-uz
VOSK_MODEL_PATH_RU=./models/vosk-model-ru
VOSK_MODEL_PATH_EN=./models/vosk-model-en

# Proxy Configuration (optional)
# PROXY_URL=socks5://127.0.0.1:10808
# PROXY_URL=http://proxy.example.com:8080
```

### Step 3: Verify Configuration

Test your configuration:

```bash
python bot.py
```

You should see:
- Configuration validation messages
- Database initialization confirmation
- Scheduler startup notification
- Bot polling status

If errors occur, check:
- Environment variables are set correctly
- API keys are valid
- Database connection (if using PostgreSQL)
- Required dependencies are installed

## 📖 Usage Guide

### Starting the Bot

```bash
python bot.py
```

The bot will:
1. Validate configuration
2. Initialize database (create tables if needed)
3. Load Vosk models (if available)
4. Start the reminder scheduler
5. Begin polling for Telegram messages

### First-Time Setup

When a user first interacts with the bot:

1. **Language Selection**: User chooses their preferred language (English, Russian, or Uzbek)
2. **Timezone Setup**: 
   - Option A: Share location (GPS coordinates)
   - Option B: Enter country name in any language
   - Option C: Skip (defaults to UTC)
3. **Currency Selection**: Choose default currency preference
4. **Ready to Use**: Main menu appears

### Using Expense Tracking

#### Adding Single Expense

**Via Text:**
```
User: "I spent 25 dollars on lunch at McDonald's"
Bot: [Shows categorized expense for confirmation]
     Amount: $25.00
     Category: Food
     Description: lunch at McDonald's
     [Yes] [No]
```

**Via Voice:**
1. Tap microphone icon
2. Speak: "Spent 50 yuan on taxi ride"
3. Bot transcribes and categorizes
4. Confirm to save

#### Adding Multiple Expenses

**Example:**
```
User: "I spent 30 dollars on groceries, 15 on gas, and 20 on movie tickets"
Bot: [Shows 3 separate expenses]
     1. $30 - Food - groceries
     2. $15 - Transport - gas
     3. $20 - Entertainment - movie tickets
     [Save All] [Cancel]
```

### Generating Reports

#### Natural Language Queries

**Time-Based Queries:**
```
"Show my expenses this month"
"What did I spend last week?"
"Total expenses in December"
```

**Category-Based Queries:**
```
"Show my food expenses"
"How much did I spend on transport?"
"Entertainment expenses this year"
```

**Complex Queries:**
```
"Compare my spending this month vs last month"
"Show my top spending categories"
"What's my average daily expense?"
```

### Setting Reminders

#### Simple Reminders

```
"Remind me to pay bills tomorrow at 3 PM"
"Remind me in 2 hours to call mom"
"Set reminder for next Friday at 10 AM"
```

#### Reminder Notifications

1. **Warning Notification**: Sent 10 minutes before scheduled time
2. **Exact Time Notification**: Sent at the scheduled time

### Managing Settings

Access settings via the ⚙️ Settings button:

- **Change Language**: Switch between English, Russian, Uzbek
- **Edit Profile**: Update your display name
- **Change Timezone**: Update timezone (location or country name)

### Daily Expense Reminders

Every day at 20:00 (8 PM) in your local timezone, you'll automatically receive:

**English:**
> 💰 Daily Reminder: Don't forget to input your expenses today! Recording your expenses helps you control your financial situation.

**Russian:**
> 💰 Ежедневное напоминание: Не забудьте внести сегодняшние расходы! Запись ваших расходов поможет вам контролировать свое финансовое положение.

**Uzbek:**
> 💰 Kunlik eslatma: Bugungi xarajatlaringizni kiritishni unutmang! Xarajatlaringizni yozib olish sizga moliyaviy holatingizni nazorat qilishda yordam beradi.

## 🏗 Architecture

### System Design

```
┌─────────────────┐
│  Telegram API   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   bot.py        │  ← Main Entry Point
│  (Message Loop) │
└────────┬────────┘
         │
    ┌────┴────┬────────────┬────────────┬─────────────┐
    │         │            │            │             │
    ▼         ▼            ▼            ▼             ▼
┌────────┐ ┌────────┐ ┌─────────┐ ┌──────────┐ ┌─────────┐
│Expense │ │Report  │ │Reminder │ │Settings  │ │ About   │
│Handler │ │Handler │ │ Handler │ │ Handler  │ │ Handler │
└───┬────┘ └───┬────┘ └────┬────┘ └────┬─────┘ └────┬────┘
    │          │           │           │            │
    └──────────┴───────────┴───────────┴────────────┘
                    │
        ┌───────────┼───────────┬──────────────┐
        │           │           │              │
        ▼           ▼           ▼              ▼
  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌──────────┐
  │   AI    │ │Database │ │Scheduler │ │  Vosk    │
  │Functions│ │ (ORM)   │ │(APSched) │ │ Models   │
  └─────────┘ └─────────┘ └──────────┘ └──────────┘
```

### AI Architecture

The bot uses **three specialized AI instances** from DeepSeek:

#### 1. DeepSeek_AI_1: Expense Extraction
- **Purpose**: Extract expense information from natural language
- **Input**: User's expense description (text or transcribed voice)
- **Output**: Structured expense data (amount, currency, category, description)
- **Specialization**: Currency detection, category assignment

#### 2. DeepSeek_AI_2: Time Parsing
- **Purpose**: Extract time/date information from reminder messages
- **Input**: User's reminder text with time reference
- **Output**: ISO format datetime string
- **Specialization**: Relative time parsing, timezone awareness

#### 3. DeepSeek_AI_Country: Country Detection
- **Purpose**: Detect country names in any language and return timezone
- **Input**: Country name in any language
- **Output**: IANA timezone name
- **Specialization**: Multi-language country recognition

#### 4. DeepSeek_AI_data: Report Generation
- **Purpose**: Generate comprehensive expense reports
- **Input**: User's report query + expense data from database
- **Output**: Natural language report with insights
- **Specialization**: Data analysis, pattern recognition

### Database Schema

```python
User
├── id (PK)
├── telegram_id (Unique, Indexed)
├── name
├── language (default: 'en')
├── timezone (default: 'UTC')
├── currency (default: 'USD')
├── created_at
├── expenses (1-to-Many)
└── reminders (1-to-Many)

Expense
├── id (PK)
├── user_id (FK → User.id)
├── amount
├── currency
├── category
├── description
├── date (Indexed)
└── created_at

Reminder
├── id (PK)
├── user_id (FK → User.id)
├── message
├── reminder_time (Indexed)
├── created_at
└── sent (0 or 1)
```

### Thread Safety

- **Database Sessions**: Uses SQLAlchemy `scoped_session` for thread-local sessions
- **Model Loading**: Singleton pattern for Vosk models (shared cache)
- **Scheduler**: Thread-safe APScheduler with UTC timezone
- **Concurrent Users**: Each request handled in isolated context

## 📁 Project Structure

```
SmartExpenseBot/
│
├── handlers/                      # Command handlers (MVC pattern)
│   ├── __init__.py
│   ├── expense_handler.py         # Expense tracking logic
│   │   └── ExpenseHandler class
│   ├── report_handler.py          # Report generation logic
│   │   └── ReportHandler class
│   ├── reminder_handler.py        # Reminder management
│   │   ├── ReminderHandler class
│   │   └── Helper functions (timezone detection)
│   ├── settings_handler.py        # User settings management
│   │   └── SettingsHandler class
│   └── about_handler.py           # About page & feedback
│       └── AboutHandler class
│
├── ai_functions.py                # DeepSeek AI integration
│   ├── deepseek_ai_expense()      # Expense extraction
│   ├── deepseek_ai_expense_multiple()  # Multiple expense extraction
│   ├── deepseek_ai_reminder()     # Time parsing
│   ├── deepseek_ai_country()      # Country detection
│   ├── deepseek_ai_report()       # Report generation
│   └── _extract_expense_manually() # Fallback extraction
│
├── bot.py                         # Main application entry point
│   ├── Message handlers
│   ├── Callback handlers
│   └── Bot initialization
│
├── config.py                      # Configuration management
│   └── Config class (environment variables)
│
├── database.py                    # Database layer
│   ├── User model
│   ├── Expense model
│   ├── Reminder model
│   └── Database class (CRUD operations)
│
├── keyboards.py                   # UI keyboard utilities
│   ├── create_main_keyboard()
│   ├── create_language_keyboard()
│   ├── create_currency_keyboard()
│   └── create_report_keyboard()
│
├── translations.py                # Internationalization
│   ├── TRANSLATIONS dict
│   ├── get_translation()
│   └── get_language_name()
│
├── voice_transcriber.py           # Voice transcription
│   └── VoiceTranscriber class (singleton pattern)
│
├── scheduler.py                   # Task scheduling
│   └── ReminderScheduler class
│       ├── Reminder scheduling
│       └── Daily expense reminders
│
├── models/                        # Vosk model files (git-ignored)
│   ├── vosk-model-uz/
│   ├── vosk-model-ru/
│   └── vosk-model-en/
│
├── requirements.txt               # Python dependencies
├── .env                           # Environment variables (git-ignored)
├── .env.example                   # Environment template
├── LICENSE                        # MIT License
└── README.md                      # This file
```

## 🔌 API Documentation

### Environment Variables

| Variable | Description | Required | Default | Example |
|----------|-------------|----------|---------|---------|
| `BOT_TOKEN` | Telegram bot token from @BotFather | ✅ Yes | - | `123456789:ABCdef...` |
| `DEEPSEEK_API_KEY` | DeepSeek API authentication key | ✅ Yes | - | `sk-...` |
| `DEEPSEEK_API_URL` | DeepSeek API endpoint URL | ✅ Yes | `https://api.deepseek.com/v1/chat/completions` | - |
| `DEVELOPER_ID` | Telegram user ID for receiving feedback | ❌ No | `0` | `123456789` |
| `DB_TYPE` | Database type: `sqlite` or `postgresql` | ✅ Yes | `sqlite` | `postgresql` |
| `SQLITE_DB_PATH` | SQLite database file path | If SQLite | `smart_expense_bot.db` | `./data/bot.db` |
| `POSTGRES_HOST` | PostgreSQL server host | If PostgreSQL | `localhost` | `db.example.com` |
| `POSTGRES_PORT` | PostgreSQL server port | If PostgreSQL | `5432` | `5432` |
| `POSTGRES_DB` | PostgreSQL database name | If PostgreSQL | `smart_expense_bot` | `expense_bot` |
| `POSTGRES_USER` | PostgreSQL username | If PostgreSQL | `postgres` | `bot_user` |
| `POSTGRES_PASSWORD` | PostgreSQL password | If PostgreSQL | `postgres` | `secure_password` |
| `PROXY_URL` | Proxy server URL (optional) | ❌ No | - | `socks5://127.0.0.1:10808` |
| `VOSK_MODEL_PATH_UZ` | Path to Uzbek Vosk model | ❌ No | `./models/vosk-model-uz` | `/path/to/model` |
| `VOSK_MODEL_PATH_RU` | Path to Russian Vosk model | ❌ No | `./models/vosk-model-ru` | `/path/to/model` |
| `VOSK_MODEL_PATH_EN` | Path to English Vosk model | ❌ No | `./models/vosk-model-en` | `/path/to/model` |

### Database Methods

#### User Management

```python
# Get or create user
user = db.get_or_create_user(telegram_id: int, name: str) -> User

# Update user settings
db.update_user_language(telegram_id: int, language: str)
db.update_user_name(telegram_id: int, name: str)
db.update_user_timezone(telegram_id: int, timezone: str)
db.update_user_currency(telegram_id: int, currency: str)

# Get all users with timezone set
users = db.get_all_users_with_timezone() -> List[User]
```

#### Expense Management

```python
# Add expense
expense = db.add_expense(
    telegram_id: int,
    amount: float,
    currency: str,
    category: str,
    description: str = None
) -> Expense

# Get expenses with filters
expenses = db.get_expenses(
    telegram_id: int,
    start_date: datetime = None,
    end_date: datetime = None,
    category: str = None,
    limit: int = 100
) -> List[Expense]
```

#### Reminder Management

```python
# Add reminder
reminder = db.add_reminder(
    telegram_id: int,
    message: str,
    reminder_time: datetime
) -> Reminder

# Get pending reminders
reminders = db.get_pending_reminders(before_time: datetime) -> List[Reminder]

# Mark reminder as sent
db.mark_reminder_sent(reminder_id: int)
```

### AI Functions

#### Expense Extraction

```python
from ai_functions import deepseek_ai_expense, deepseek_ai_expense_multiple

# Single expense
result = deepseek_ai_expense(
    text: str,
    lang: str = "en"
) -> Dict[str, Any]
# Returns: {"amount": float, "currency": str, "category": str, 
#           "description": str, "advice": str}

# Multiple expenses
expenses = deepseek_ai_expense_multiple(
    text: str,
    lang: str = "en",
    default_currency: str = "USD"
) -> List[Dict[str, Any]]
```

#### Time Parsing

```python
from ai_functions import deepseek_ai_reminder

time_str = deepseek_ai_reminder(
    text: str,
    lang: str = "en",
    user_timezone: str = "UTC",
    current_time: datetime = None
) -> Optional[str]  # ISO format datetime string
```

#### Country Detection

```python
from ai_functions import deepseek_ai_country

timezone = deepseek_ai_country(
    country_text: str,
    lang: str = "en"
) -> Optional[str]  # IANA timezone name
```

#### Report Generation

```python
from ai_functions import deepseek_ai_report

report = deepseek_ai_report(
    text: str,
    lang: str = "en",
    expenses_data: List[Expense] = None
) -> str  # Natural language report
```

## 🔧 Troubleshooting

### Common Issues

#### Bot Not Responding

**Symptoms**: Bot doesn't respond to any messages

**Diagnosis Steps**:
1. Check if bot process is running: `ps aux | grep bot.py`
2. Review application logs for errors
3. Verify bot token is correct: Check `.env` file

**Solutions**:
- Verify `BOT_TOKEN` is correct and active
- Ensure bot has necessary permissions in Telegram
- Check network connectivity
- Review logs for specific error messages
- Restart the bot process

#### Database Connection Errors

**Symptoms**: Database-related errors in logs

**Solutions**:

*For SQLite:*
- Verify write permissions in database directory
- Check disk space availability
- Ensure database file path is correct

*For PostgreSQL:*
- Verify connection credentials
- Check PostgreSQL service is running: `sudo systemctl status postgresql`
- Test connection: `psql -h host -U user -d database`
- Verify network connectivity
- Check firewall rules

#### Voice Transcription Not Working

**Symptoms**: Voice messages not transcribed

**Diagnosis**:
1. Check if Vosk models are downloaded
2. Verify model paths in environment variables
3. Check FFmpeg installation: `ffmpeg -version`
4. Review logs for transcription errors

**Solutions**:
- Download missing Vosk models
- Verify model paths match actual directories
- Install FFmpeg: `sudo apt-get install ffmpeg` (Ubuntu) or `brew install ffmpeg` (macOS)
- Check available disk space for temporary files
- Verify audio format is supported (OGG, MP3, WAV)

#### AI Categorization Errors

**Symptoms**: Expenses not categorized correctly or API errors

**Solutions**:
- Verify `DEEPSEEK_API_KEY` is valid and active
- Check API endpoint URL is correct
- Review API rate limits and quotas
- Check network connectivity to DeepSeek API
- Review API response logs for detailed errors
- Check API account balance/credits

#### Timezone Detection Issues

**Symptoms**: Reminders scheduled at wrong times or timezone not detected

**Solutions**:
- For location-based: Ensure user shared GPS location
- For country-based: Try different country name formats
- Verify `timezonefinderL` is installed: `pip install timezonefinderL`
- Manually set timezone in settings
- Check timezone string format (must be valid IANA timezone)

#### Concurrent User Errors

**Symptoms**: Errors when multiple users use bot simultaneously

**Solutions**:
- Ensure using latest version with thread-safe session management
- For SQLite: Bot configured with proper thread settings
- For PostgreSQL: Connection pooling enabled automatically
- Check database connection limits
- Review error logs for specific thread-safety issues

#### Model Loading Issues

**Symptoms**: Vosk models loading multiple times or memory errors

**Solutions**:
- Models use singleton pattern (should load once)
- Check available system memory
- Verify model files are complete (not corrupted)
- Review logs for model loading errors

### Debug Mode

Enable detailed logging:

```python
# In bot.py, change log level:
logging.basicConfig(
    level=logging.DEBUG,  # Change from INFO to DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Getting Help

If issues persist:
1. Check [GitHub Issues](https://github.com/botirbakhtiyarov/SmartExpenseBot/issues)
2. Enable debug logging and review logs
3. Create detailed issue report with:
   - Error messages
   - Steps to reproduce
   - System information
   - Relevant log excerpts

## 🤝 Contributing

We welcome contributions! Here's how you can help:

### Contribution Guidelines

1. **Fork the Repository**
   ```bash
   git clone https://github.com/botirbakhtiyarov/SmartExpenseBot.git
   ```

2. **Create Feature Branch**
   ```bash
   git checkout -b feature/AmazingFeature
   ```

3. **Make Changes**
   - Follow PEP 8 style guidelines
   - Add comments for complex logic
   - Update documentation as needed
   - Write/update tests if applicable

4. **Commit Changes**
   ```bash
   git commit -m 'Add some AmazingFeature'
   ```

5. **Push to Branch**
   ```bash
   git push origin feature/AmazingFeature
   ```

6. **Open Pull Request**
   - Provide clear description of changes
   - Reference any related issues
   - Ensure all tests pass

### Code Style

- Follow **PEP 8** Python style guide
- Use **type hints** for function signatures
- Add **docstrings** for all functions and classes
- Keep functions focused and modular
- Use descriptive variable names

### Testing

- Test your changes thoroughly
- Test with multiple languages
- Test edge cases
- Ensure backward compatibility

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

### License Summary

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files, to deal in the software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the software.

## 👤 Author & Support

### Author

**Botir Bakhtiyarov**

- 🌐 **GitHub**: [@botirbakhtiyarov](https://github.com/botirbakhtiyarov)
- 💬 **Telegram**: [@bakhtiyarovbotir](https://t.me/bakhtiyarovbotir)
- 📧 **Email**: botirbakhtiyarovb@gmail.com

### Support Channels

- **GitHub Issues**: [Report Bugs or Request Features](https://github.com/botirbakhtiyarov/SmartExpenseBot/issues)
- **Telegram**: Use the bot's "About Us" → "Feedback" feature
- **Email**: botirbakhtiyarovb@gmail.com

### Acknowledgments

This project uses the following excellent libraries and services:

- **[pyTelegramBotAPI](https://github.com/eternnoir/pyTelegramBotAPI)** - Elegant Telegram Bot API wrapper
- **[DeepSeek](https://www.deepseek.com/)** - Powerful AI API for natural language processing
- **[Vosk](https://alphacephei.com/vosk/)** - Offline speech recognition toolkit
- **[SQLAlchemy](https://www.sqlalchemy.org/)** - Python SQL toolkit and ORM
- **[APScheduler](https://apscheduler.readthedocs.io/)** - Advanced Python Scheduler
- **[TimezoneFinderL](https://github.com/MrMinimal64/timezonefinderL)** - Fast timezone lookup library

---

<div align="center">

**Made with ❤️ by Botir Bakhtiyarov**

⭐ **Star this repo if you find it helpful!**

[⬆ Back to Top](#smartexpensebot)

</div>
