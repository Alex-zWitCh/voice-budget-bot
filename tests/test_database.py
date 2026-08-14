import csv
import gzip
import sqlite3
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from sqlalchemy import text

from database import Database
from schemas import ParsedScheduledEvent, ParsedTransaction
from services.reports import (
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
    assert {"scope", "family_id", "paid_by"} <= cols
    event_cols = {row[1] for row in __import__("sqlite3").connect(path).execute("PRAGMA table_info(scheduled_events)")}
    assert {"scope", "family_id"} <= event_cols


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
