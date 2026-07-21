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

    assert db.save_transaction(message, parsed, "пятьсот продукты молоко", config) is True
    assert db.save_transaction(message, parsed, "пятьсот продукты молоко", config) is False
    assert db.transaction_exists(1, 10) is True
