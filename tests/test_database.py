import csv
import gzip
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from sqlalchemy import text

from database import Database, Transaction
from schemas import ParsedExchange, ParsedScheduledEvent, ParsedTransaction
from decimal import Decimal
from services.reports import (
    build_category_chart,
    build_last_30_days_expense_chart,
    build_last_30_days_income_chart,
    build_previous_month_expense_chart,
    build_previous_month_income_chart,
    export_transactions_csv_gz,
)
from services.scheduler import ScheduledEventRunner, calendar_text


def _message(chat_id=1, message_id=10, user_id=20):
    return SimpleNamespace(
        chat=SimpleNamespace(id=chat_id, type="private", title=None),
        from_user=SimpleNamespace(id=user_id, username="alex", first_name="Alex", last_name=None),
        message_id=message_id,
        date=int(datetime(2026, 7, 21, tzinfo=timezone.utc).timestamp()),
        voice=SimpleNamespace(duration=3),
    )


def _previous_month_datetime(app_timezone="Europe/Moscow"):
    tz = ZoneInfo(app_timezone)
    current_month = datetime.now(tz).replace(day=1, hour=12, minute=0, second=0, microsecond=0)
    previous_month = current_month - timedelta(days=1)
    return previous_month.replace(day=min(previous_month.day, 15))


def test_save_transaction_is_idempotent(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    message = _message()
    config = SimpleNamespace(stt_model="whisper-large-v3", deepseek_model="deepseek-v4-flash", processing_version="1.0")
    parsed = ParsedTransaction("EXPENSE", 50000, "RUB", "PRODUCTS", "молоко", 0.95)

    db.upsert_user_and_chat(message)

    transaction_id = db.save_transaction(message, parsed, "пятьсот продукты молоко", config)
    assert transaction_id
    assert db.save_transaction(message, parsed, "пятьсот продукты молоко", config) is None
    assert db.transaction_exists(1, 10) is True
    assert db.delete_transaction(transaction_id, 20, 1) is True
    assert db.transaction_exists(1, 10) is False


def test_user_categories(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    code = db.add_user_category(20, "EXPENSE", "Семья")
    assert code == "CUSTOM_SEMYA"
    catalog = db.get_category_catalog(20)
    assert catalog["EXPENSE"][code] == "Семья"
    rows = db.list_user_categories(20)
    assert len(rows) == 1
    assert db.deactivate_user_category(20, rows[0].id) is True
    assert db.list_user_categories(20) == []


def test_scheduled_events_calendar_and_deferred_expense(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    message = _message()
    config = SimpleNamespace(
        stt_model="whisper-large-v3",
        deepseek_model="deepseek-v4-flash",
        processing_version="1.0",
        app_timezone="Europe/Moscow",
    )
    transaction = ParsedTransaction("EXPENSE", 100000, "RUB", "SUBSCRIPTIONS", "интернет", 0.95)
    event = ParsedScheduledEvent(
        event_type="DEFERRED_EXPENSE",
        title="интернет",
        notify_at_utc=datetime.now(timezone.utc) - timedelta(minutes=1),
        event_at_utc=datetime.now(timezone.utc),
        recurrence="monthly",
        confidence=0.95,
        transaction=transaction,
    )
    event_id = db.create_scheduled_event(message, event, "20 декабря интернет тысяча", config)
    assert event_id
    assert db.scheduled_event_exists(1, 10) is True

    text = calendar_text(db, 20, "Europe/Moscow")
    assert "интернет" in text
    assert "ежемесячно" in text

    bot = SimpleNamespace(messages=[])
    bot.send_message = lambda chat_id, text: bot.messages.append((chat_id, text))
    runner = ScheduledEventRunner(bot, db, config)
    runner.process_due_events()
    assert bot.messages
    assert db.transaction_exists(1, -(event_id * 10_000_000_000 + int(event.event_at_utc.timestamp()) % 10_000_000_000))


def test_delete_scheduled_event(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    message = _message()
    config = SimpleNamespace(
        stt_model="whisper-large-v3",
        deepseek_model="deepseek-v4-flash",
        processing_version="1.0",
        app_timezone="Europe/Moscow",
    )
    event = ParsedScheduledEvent(
        event_type="REMINDER",
        title="проверить меню",
        notify_at_utc=datetime.now(timezone.utc) + timedelta(days=1),
        event_at_utc=datetime.now(timezone.utc) + timedelta(days=1),
        recurrence="none",
        confidence=0.95,
    )
    event_id = db.create_scheduled_event(message, event, "напомни проверить меню", config)
    assert event_id
    assert db.delete_scheduled_event(event_id, 20, 1) is True
    assert db.get_due_scheduled_events(datetime.now(timezone.utc) + timedelta(days=2)) == []


def test_export_transactions_csv_gz_contains_full_transcript(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    config = SimpleNamespace(stt_model="whisper-large-v3", deepseek_model="deepseek-v4-flash", processing_version="1.0")
    message = _message(message_id=50)
    message.date = int(datetime.now(timezone.utc).timestamp())
    parsed = ParsedTransaction("EXPENSE", 99800, "RUB", "ALCOHOL", "пиво с закусками", 0.95)

    db.upsert_user_and_chat(message)
    db.save_transaction(message, parsed, "девятьсот девяносто восемь рублей пиво с закусками", config)

    tz = ZoneInfo("Europe/Moscow")
    end_local = datetime.now(tz)
    start_local = end_local - timedelta(days=1)
    path = export_transactions_csv_gz(db, 20, "Europe/Moscow", tmp_path, start_local, end_local, "test-period")

    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 1
    assert rows[0]["category_code"] == "ALCOHOL"
    assert rows[0]["category_title"] == "Алкоголь"
    assert rows[0]["transcript"] == "девятьсот девяносто восемь рублей пиво с закусками"


def test_previous_month_expense_chart_is_created(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    config = SimpleNamespace(stt_model="whisper-large-v3", deepseek_model="deepseek-v4-flash", processing_version="1.0")
    message = _message(message_id=60)
    message.date = int(_previous_month_datetime().astimezone(timezone.utc).timestamp())
    parsed = ParsedTransaction("EXPENSE", 140000, "RUB", "PRODUCTS", "продукты", 0.95)

    db.upsert_user_and_chat(message)
    db.save_transaction(message, parsed, "тысяча четыреста продукты", config)

    path, caption = build_previous_month_expense_chart(db, 20, "Europe/Moscow", tmp_path)

    assert path is not None
    assert path.exists()
    assert path.suffix == ".png"
    assert "Расходы по категориям" in caption


def test_previous_month_income_chart_is_created(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    config = SimpleNamespace(stt_model="whisper-large-v3", deepseek_model="deepseek-v4-flash", processing_version="1.0")
    message = _message(message_id=63)
    message.date = int(_previous_month_datetime().astimezone(timezone.utc).timestamp())
    parsed = ParsedTransaction("INCOME", 10000000, "RUB", "SALARY", "зарплата", 0.95)

    db.upsert_user_and_chat(message)
    db.save_transaction(message, parsed, "получил зарплату сто тысяч", config)

    path, caption = build_previous_month_income_chart(db, 20, "Europe/Moscow", tmp_path)

    assert path is not None
    assert path.exists()
    assert path.suffix == ".png"
    assert "Доходы по категориям" in caption


def test_last_30_days_expense_chart_is_created(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    config = SimpleNamespace(stt_model="whisper-large-v3", deepseek_model="deepseek-v4-flash", processing_version="1.0")
    message = _message(message_id=61)
    message.date = int((datetime.now(timezone.utc) - timedelta(days=3)).timestamp())
    parsed = ParsedTransaction("EXPENSE", 140000, "RUB", "PRODUCTS", "продукты", 0.95)

    db.upsert_user_and_chat(message)
    db.save_transaction(message, parsed, "тысяча четыреста продукты", config)

    path, caption = build_last_30_days_expense_chart(db, 20, "Europe/Moscow", tmp_path)

    assert path is not None
    assert path.exists()
    assert "30 дней" in caption


def test_last_30_days_income_chart_is_created(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    config = SimpleNamespace(stt_model="whisper-large-v3", deepseek_model="deepseek-v4-flash", processing_version="1.0")
    message = _message(message_id=64)
    message.date = int((datetime.now(timezone.utc) - timedelta(days=3)).timestamp())
    parsed = ParsedTransaction("INCOME", 10000000, "RUB", "SALARY", "зарплата", 0.95)

    db.upsert_user_and_chat(message)
    db.save_transaction(message, parsed, "получил зарплату сто тысяч", config)

    path, caption = build_last_30_days_income_chart(db, 20, "Europe/Moscow", tmp_path)

    assert path is not None
    assert path.exists()
    assert "30 дней" in caption


def test_monthly_report_is_sent_once_on_first_day(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    config = SimpleNamespace(
        stt_model="whisper-large-v3",
        deepseek_model="deepseek-v4-flash",
        processing_version="1.0",
        app_timezone="Europe/Moscow",
        temp_audio_dir=tmp_path,
    )
    message = _message(message_id=62)
    previous_month = _previous_month_datetime()
    message.date = int(previous_month.astimezone(timezone.utc).timestamp())
    parsed = ParsedTransaction("EXPENSE", 140000, "RUB", "PRODUCTS", "продукты", 0.95)

    db.upsert_user_and_chat(message)
    db.save_transaction(message, parsed, "тысяча четыреста продукты", config)
    income_message = _message(message_id=63)
    income_message.date = message.date
    income_parsed = ParsedTransaction("INCOME", 10000000, "RUB", "SALARY", "зарплата", 0.95)
    db.save_transaction(income_message, income_parsed, "получил зарплату сто тысяч", config)

    bot = SimpleNamespace(photos=[], documents=[], messages=[])

    def send_photo(chat_id, image, caption):
        bot.photos.append((chat_id, caption, image.read(4)))

    def send_document(chat_id, file, visible_file_name, caption):
        bot.documents.append((chat_id, visible_file_name, caption, file.read(2)))

    bot.send_photo = send_photo
    bot.send_document = send_document
    bot.send_message = lambda chat_id, text: bot.messages.append((chat_id, text))
    runner = ScheduledEventRunner(bot, db, config)
    first_day = previous_month.replace(day=1) + timedelta(days=40)
    first_day = first_day.replace(day=1, hour=9, minute=0, second=0, microsecond=0)

    runner._process_monthly_reports(first_day.astimezone(timezone.utc))
    runner._process_monthly_reports(first_day.astimezone(timezone.utc))

    assert len(bot.photos) == 2
    assert bot.photos[0][0] == 1
    assert "Автоматический отчет" in bot.photos[0][1]
    assert bot.photos[1][0] == 1
    assert "Автоматический отчет" in bot.photos[1][1]
    assert len(bot.documents) == 1
    assert bot.documents[0][0] == 1
    assert bot.documents[0][1].endswith(".csv.gz")


def test_monthly_report_catch_up_on_second_day(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    config = SimpleNamespace(
        stt_model="whisper-large-v3",
        deepseek_model="deepseek-v4-flash",
        processing_version="1.0",
        app_timezone="Europe/Moscow",
        temp_audio_dir=tmp_path,
    )
    message = _message(message_id=72)
    previous_month = _previous_month_datetime()
    message.date = int(previous_month.astimezone(timezone.utc).timestamp())
    parsed = ParsedTransaction("EXPENSE", 140000, "RUB", "PRODUCTS", "продукты", 0.95)
    db.upsert_user_and_chat(message)
    db.save_transaction(message, parsed, "тысяча четыреста продукты", config)

    bot = SimpleNamespace(photos=[], documents=[], messages=[])
    bot.send_photo = lambda chat_id, image, caption: bot.photos.append((chat_id, caption, image.read(4)))
    bot.send_document = lambda chat_id, file, visible_file_name, caption: bot.documents.append(
        (chat_id, visible_file_name, caption, file.read(2))
    )
    bot.send_message = lambda chat_id, text: bot.messages.append((chat_id, text))
    runner = ScheduledEventRunner(bot, db, config)

    tz = ZoneInfo("Europe/Moscow")
    now_local = datetime.now(tz)
    second_day = now_local.replace(day=2, hour=9, minute=0, second=0, microsecond=0)

    runner._process_monthly_reports(second_day.astimezone(timezone.utc))
    runner._process_monthly_reports(second_day.astimezone(timezone.utc))

    assert len(bot.photos) == 1
    assert len(bot.documents) == 1
    assert bot.documents[0][1].endswith(".csv.gz")


def _create_legacy_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            telegram_user_id BIGINT UNIQUE,
            username VARCHAR(255),
            first_name VARCHAR(255),
            last_name VARCHAR(255),
            first_seen_at DATETIME,
            last_seen_at DATETIME
        );
        CREATE TABLE chats (
            id INTEGER PRIMARY KEY,
            telegram_chat_id BIGINT UNIQUE,
            chat_type VARCHAR(32),
            title VARCHAR(255),
            is_enabled BOOLEAN,
            created_at DATETIME
        );
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY,
            telegram_chat_id BIGINT,
            telegram_message_id BIGINT,
            telegram_user_id BIGINT,
            transaction_type VARCHAR(16),
            amount_minor BIGINT,
            currency VARCHAR(3),
            category VARCHAR(64),
            description TEXT,
            transcript TEXT,
            message_date_utc DATETIME,
            created_at_utc DATETIME,
            voice_duration_sec INTEGER,
            groq_model VARCHAR(64),
            deepseek_model VARCHAR(64),
            deepseek_confidence NUMERIC,
            processing_version VARCHAR(32),
            UNIQUE(telegram_chat_id, telegram_message_id)
        );
        CREATE TABLE scheduled_events (
            id INTEGER PRIMARY KEY,
            telegram_chat_id BIGINT,
            telegram_message_id BIGINT,
            telegram_user_id BIGINT,
            event_type VARCHAR(32),
            status VARCHAR(32),
            notify_at_utc DATETIME,
            event_at_utc DATETIME,
            recurrence VARCHAR(16),
            title TEXT,
            transcript TEXT,
            transaction_type VARCHAR(16),
            amount_minor BIGINT,
            currency VARCHAR(3),
            category VARCHAR(64),
            description TEXT,
            groq_model VARCHAR(64),
            deepseek_model VARCHAR(64),
            deepseek_confidence NUMERIC,
            processing_version VARCHAR(32),
            created_at_utc DATETIME,
            last_fired_at_utc DATETIME,
            UNIQUE(telegram_chat_id, telegram_message_id)
        );
        INSERT INTO users (telegram_user_id, first_name) VALUES (20, 'Alex');
        INSERT INTO chats (telegram_chat_id, chat_type) VALUES (1, 'private');
        INSERT INTO transactions (
            telegram_chat_id, telegram_message_id, telegram_user_id, transaction_type,
            amount_minor, currency, category, description, transcript, message_date_utc,
            voice_duration_sec, groq_model, deepseek_model, deepseek_confidence, processing_version
        ) VALUES (1, 10, 20, 'EXPENSE', 50000, 'RUB', 'PRODUCTS', 'молоко', 'пятьсот продукты молоко',
                  '2026-07-21 10:00:00', 3, 'whisper', 'deepseek', 0.95, '1.0');
        """
    )
    conn.commit()
    conn.close()


def test_schema_migration_preserves_legacy_data_and_adds_columns(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    _create_legacy_db(path)
    db = Database(path)

    with db.Session() as session:
        rows = session.execute(text("SELECT * FROM transactions")).fetchall()
    assert len(rows) == 1
    row = rows[0]
    assert row.scope == "personal"
    assert row.family_id is None
    assert row.paid_by == 20

    cols = {row[1] for row in __import__("sqlite3").connect(path).execute("PRAGMA table_info(transactions)")}
    assert {"scope", "family_id", "paid_by", "from_currency", "from_amount_minor", "exchange_rate", "exchange_pair_id"} <= cols
    event_cols = {row[1] for row in __import__("sqlite3").connect(path).execute("PRAGMA table_info(scheduled_events)")}
    assert {"scope", "family_id"} <= event_cols
    user_cols = {row[1] for row in __import__("sqlite3").connect(path).execute("PRAGMA table_info(users)")}
    assert "main_currency" in user_cols
    with db.Session() as session:
        user = session.execute(text("SELECT main_currency FROM users WHERE telegram_user_id=:id"), {"id": 20}).fetchone()
    assert user.main_currency == "RUB"


def test_schema_migration_is_idempotent(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    _create_legacy_db(path)
    Database(path)
    Database(path)


def test_create_family_and_invite_and_join(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    family_id = db.create_family("Наша семья", 20)
    assert family_id is not None
    assert db.create_family("Другая", 20) is None

    family = db.get_family_for_user(20)
    assert family is not None
    assert family.name == "Наша семья"

    code = db.generate_invite_code(20)
    assert code

    ok, name = db.join_family_by_code(30, code)
    assert ok is True
    assert name == "Наша семья"

    ok, reason = db.join_family_by_code(40, "WRONG123")
    assert ok is False
    assert reason == "invite_code_not_found"

    ok, reason = db.join_family_by_code(30, code)
    assert ok is False
    assert reason == "already_in_family"

    members = db.list_family_members(family_id)
    assert {m.telegram_user_id for m in members} == {20, 30}


def test_join_without_family_returns_not_found(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    ok, reason = db.join_family_by_code(20, "ABC12345")
    assert ok is False
    assert reason == "invite_code_not_found"


def test_set_transaction_scope(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    message = _message()
    config = SimpleNamespace(stt_model="whisper-large-v3", deepseek_model="deepseek-v4-flash", processing_version="1.0")
    parsed = ParsedTransaction("EXPENSE", 50000, "RUB", "PRODUCTS", "молоко", 0.95)
    db.upsert_user_and_chat(message)
    transaction_id = db.save_transaction(message, parsed, "пятьсот продукты молоко", config)
    assert transaction_id

    family_id = db.create_family("Наша семья", 20)

    assert db.set_transaction_scope(transaction_id, 20, "family", family_id) is True
    with db.Session() as session:
        row = session.execute(text("SELECT scope, family_id, paid_by FROM transactions WHERE id=:id"), {"id": transaction_id}).fetchone()
    assert row.scope == "family"
    assert row.family_id == family_id
    assert row.paid_by == 20

    assert db.set_transaction_scope(transaction_id, 20, "personal") is True
    with db.Session() as session:
        row = session.execute(text("SELECT scope, family_id FROM transactions WHERE id=:id"), {"id": transaction_id}).fetchone()
    assert row.scope == "personal"
    assert row.family_id is None

    assert db.set_transaction_scope(transaction_id, 999, "family", family_id) is False


def _exchange_message(message_id=12, days_ago=3):
    return SimpleNamespace(
        chat=SimpleNamespace(id=1, type="private", title=None),
        from_user=SimpleNamespace(id=20, username="alex", first_name="Alex", last_name=None),
        message_id=message_id,
        date=int((datetime.now(timezone.utc) - timedelta(days=days_ago)).timestamp()),
        voice=None,
    )


def _parsed_exchange():
    return ParsedExchange(
        from_amount_minor=200000,
        from_currency="USD",
        to_currency="RUB",
        to_amount_minor=18400000,
        rate=Decimal("92"),
        description="перевод долларов в рубли",
        confidence=0.95,
    )


def test_create_exchange_creates_two_mirror_records_and_balances(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    config = SimpleNamespace(stt_model="whisper-large-v3", deepseek_model="deepseek-v4-flash", processing_version="1.0")
    message = _exchange_message(message_id=10)
    db.upsert_user_and_chat(message)

    salary = ParsedTransaction("INCOME", 200000, "USD", "SALARY", "зарплата", 0.95)
    db.save_transaction(message, salary, "получил зарплату две тысячи долларов", config)

    exchange_message = _exchange_message(message_id=12)
    expense_id = db.create_exchange(exchange_message, _parsed_exchange(), "перевёл 2000 долларов в рубли по курсу 92", config)
    assert expense_id is not None

    balances = db.get_balances(20)
    assert balances["USD"] == 0
    assert balances["RUB"] == 18400000

    with db.Session() as session:
        rows = session.query(Transaction).filter(Transaction.exchange_pair_id.is_not(None)).all()
    assert len(rows) == 2
    assert rows[0].exchange_pair_id == rows[1].exchange_pair_id
    assert {row.transaction_type for row in rows} == {"EXPENSE", "INCOME"}
    assert all(row.exchange_rate == Decimal("92") for row in rows)
    assert all(row.from_currency == "USD" for row in rows)
    assert all(row.from_amount_minor == 200000 for row in rows)


def test_delete_exchange_deletes_both_mirrors(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    config = SimpleNamespace(stt_model="whisper-large-v3", deepseek_model="deepseek-v4-flash", processing_version="1.0")
    message = _exchange_message(message_id=12)
    db.upsert_user_and_chat(message)
    expense_id = db.create_exchange(message, _parsed_exchange(), "перевёл 2000 долларов в рубли по курсу 92", config)

    assert db.delete_transaction(expense_id, 20, 1) is True
    assert db.get_balances(20) == {}
    assert db.transaction_exists(1, 12) is False
    assert db.transaction_exists(1, -12) is False


def test_main_currency_default_and_set(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    message = _exchange_message()
    db.upsert_user_and_chat(message)
    assert db.get_main_currency(20) == "RUB"
    assert db.set_main_currency(20, "USD") is True
    assert db.get_main_currency(20) == "USD"


def test_get_exchange_rates(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    config = SimpleNamespace(stt_model="whisper-large-v3", deepseek_model="deepseek-v4-flash", processing_version="1.0")
    message = _exchange_message()
    db.upsert_user_and_chat(message)
    db.create_exchange(message, _parsed_exchange(), "перевёл 2000 долларов в рубли по курсу 92", config)

    rates = db.get_exchange_rates(20)
    assert rates == [("USD", "RUB", Decimal("92"))]


def test_exchange_chart_converts_to_main_currency(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    config = SimpleNamespace(stt_model="whisper-large-v3", deepseek_model="deepseek-v4-flash", processing_version="1.0")
    message = _exchange_message()
    db.upsert_user_and_chat(message)
    db.set_main_currency(20, "RUB")

    expense_message = _exchange_message()
    expense_message.message_id = 11
    expense_message.date = int((datetime.now(timezone.utc) - timedelta(days=3)).timestamp())
    db.save_transaction(
        expense_message,
        ParsedTransaction("EXPENSE", 500000, "RUB", "PRODUCTS", "продукты", 0.95),
        "пять тысяч продукты",
        config,
    )
    db.create_exchange(message, _parsed_exchange(), "перевёл 2000 долларов в рубли по курсу 92", config)

    path, _caption = build_last_30_days_expense_chart(db, 20, "Europe/Moscow", tmp_path)
    assert path is not None
    assert path.exists()


def test_csv_export_includes_main_and_exchange_columns(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    config = SimpleNamespace(stt_model="whisper-large-v3", deepseek_model="deepseek-v4-flash", processing_version="1.0")
    message = _exchange_message(days_ago=0)
    db.upsert_user_and_chat(message)
    db.set_main_currency(20, "RUB")
    db.create_exchange(message, _parsed_exchange(), "перевёл 2000 долларов в рубли по курсу 92", config)

    tz = ZoneInfo("Europe/Moscow")
    end_local = datetime.now(tz)
    start_local = end_local - timedelta(days=1)
    path = export_transactions_csv_gz(db, 20, "Europe/Moscow", tmp_path, start_local, end_local, "test-period")

    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 2
    income = next(row for row in rows if row["transaction_type"] == "INCOME")
    assert income["currency"] == "RUB"
    assert income["from_currency"] == "USD"
    assert income["from_amount"] == "2000.00"
    assert income["exchange_rate"] == "92"
    assert income["main_currency"] == "RUB"
    assert income["amount_main_minor"] == "18400000"


def test_concurrent_exchanges_get_unique_pair_ids(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    config = SimpleNamespace(stt_model="whisper-large-v3", deepseek_model="deepseek-v4-flash", processing_version="1.0")
    for user_id in (1, 2, 3, 4):
        db.upsert_user_and_chat(SimpleNamespace(
            chat=SimpleNamespace(id=user_id, type="private", title=None),
            from_user=SimpleNamespace(id=user_id, username=f"u{user_id}", first_name=f"U{user_id}", last_name=None),
            message_id=1,
            date=int(datetime.now(timezone.utc).timestamp()),
            voice=None,
        ))

    barrier = threading.Barrier(4)

    def _run(user_id, message_id):
        msg = SimpleNamespace(
            chat=SimpleNamespace(id=user_id, type="private", title=None),
            from_user=SimpleNamespace(id=user_id, username=f"u{user_id}", first_name=f"U{user_id}", last_name=None),
            message_id=message_id,
            date=int(datetime.now(timezone.utc).timestamp()),
            voice=None,
        )
        barrier.wait()
        return db.create_exchange(msg, _parsed_exchange(), f"перевёл 2000 долларов в рубли по курсу 92 u{user_id}", config)

    with ThreadPoolExecutor(max_workers=4) as pool:
        expense_ids = list(pool.map(_run, (1, 2, 3, 4), (101, 102, 103, 104)))

    assert all(eid is not None for eid in expense_ids)

    with db.Session() as session:
        rows = session.query(Transaction).filter(Transaction.exchange_pair_id.is_not(None)).all()
    pair_ids = sorted({row.exchange_pair_id for row in rows})
    assert len(rows) == 8
    assert len(pair_ids) == 4, f"ожидали 4 уникальных pair_id, получили {pair_ids}"
    from collections import Counter
    counts = Counter(row.exchange_pair_id for row in rows)
    assert all(count == 2 for count in counts.values())


def test_pending_exchange_persists_across_db_reopen(tmp_path):
    path = tmp_path / "test.sqlite3"
    db = Database(path)
    parsed = _parsed_exchange().with_rate(None)
    db.save_pending_exchange(20, parsed, "перевёл 2000 долларов в рубли", chat_id=1)

    assert db.load_pending_exchange(20) is not None

    db2 = Database(path)
    state = db2.load_pending_exchange(20)
    assert state is not None
    assert state["parsed"].from_amount_minor == 200000
    assert state["parsed"].from_currency == "USD"
    assert state["parsed"].to_currency == "RUB"
    assert state["parsed"].rate is None
    assert state["chat_id"] == 1

    db2.drop_pending_exchange(20)
    assert db2.load_pending_exchange(20) is None


def test_pending_exchange_expires_after_ttl(tmp_path):
    from database import PendingExchange, PENDING_EXCHANGE_TTL
    db = Database(tmp_path / "test.sqlite3")
    parsed = _parsed_exchange().with_rate(None)
    db.save_pending_exchange(20, parsed, "перевёл 2000 долларов в рубли", chat_id=1)

    with db.Session.begin() as session:
        row = session.query(PendingExchange).filter_by(telegram_user_id=20).first()
        row.created_at_utc = datetime.now(timezone.utc) - PENDING_EXCHANGE_TTL - timedelta(seconds=1)

    removed = db.clean_expired_pending()
    assert removed == 1
    assert db.load_pending_exchange(20) is None


def test_chart_warns_when_rate_missing(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    config = SimpleNamespace(stt_model="whisper-large-v3", deepseek_model="deepseek-v4-flash", processing_version="1.0")
    message = _message(chat_id=1, message_id=200, user_id=20)
    db.upsert_user_and_chat(message)
    db.set_main_currency(20, "RUB")

    from datetime import datetime as _dt
    msg_usd = _message(chat_id=1, message_id=201, user_id=20)
    msg_usd.date = int((datetime.now(timezone.utc)).timestamp())
    db.save_transaction(
        msg_usd,
        ParsedTransaction("EXPENSE", 100000, "USD", "PRODUCTS", "импортные продукты", 0.95),
        "импортные продукты доллары",
        config,
    )

    tz = ZoneInfo("Europe/Moscow")
    end_local = datetime.now(tz)
    start_local = end_local - timedelta(days=1)
    path, caption = build_category_chart(
        db=db, telegram_user_id=20, app_timezone="Europe/Moscow", output_dir=tmp_path,
        transaction_type="EXPENSE", start_local=start_local, end_local=end_local,
        period_title="тест", empty_text="Расходов не найдено.", caption="Расходы",
        filename_suffix="test",
    )
    assert path is None
    assert "Пропущено" in caption
    assert "USD" in caption
