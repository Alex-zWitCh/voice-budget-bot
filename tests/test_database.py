import csv
import gzip
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from database import Database
from schemas import ParsedScheduledEvent, ParsedTransaction
from services.reports import build_previous_month_expense_chart, export_transactions_csv_gz
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
    config = SimpleNamespace(groq_stt_model="whisper-large-v3", deepseek_model="deepseek-v4-flash", processing_version="1.0")
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
        groq_stt_model="whisper-large-v3",
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
        groq_stt_model="whisper-large-v3",
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
    config = SimpleNamespace(groq_stt_model="whisper-large-v3", deepseek_model="deepseek-v4-flash", processing_version="1.0")
    message = _message(message_id=50)
    message.date = int(datetime.now(timezone.utc).timestamp())
    parsed = ParsedTransaction("EXPENSE", 99800, "RUB", "ALCOHOL", "пиво с закусками", 0.95)

    db.upsert_user_and_chat(message)
    db.save_transaction(message, parsed, "девятьсот девяносто восемь рублей пиво с закусками", config)

    path = export_transactions_csv_gz(db, 20, "Europe/Moscow", tmp_path)

    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 1
    assert rows[0]["category_code"] == "ALCOHOL"
    assert rows[0]["category_title"] == "Алкоголь"
    assert rows[0]["transcript"] == "девятьсот девяносто восемь рублей пиво с закусками"


def test_previous_month_expense_chart_is_created(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    config = SimpleNamespace(groq_stt_model="whisper-large-v3", deepseek_model="deepseek-v4-flash", processing_version="1.0")
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
