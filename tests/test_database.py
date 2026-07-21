from datetime import datetime, timezone
from types import SimpleNamespace

from database import Database
from schemas import ParsedTransaction


def _message(chat_id=1, message_id=10, user_id=20):
    return SimpleNamespace(
        chat=SimpleNamespace(id=chat_id, type="private", title=None),
        from_user=SimpleNamespace(id=user_id, username="alex", first_name="Alex", last_name=None),
        message_id=message_id,
        date=int(datetime(2026, 7, 21, tzinfo=timezone.utc).timestamp()),
        voice=SimpleNamespace(duration=3),
    )


def test_save_transaction_is_idempotent(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    message = _message()
    config = SimpleNamespace(groq_stt_model="whisper-large-v3", deepseek_model="deepseek-chat", processing_version="1.0")
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
