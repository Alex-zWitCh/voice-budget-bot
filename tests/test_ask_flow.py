from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from database import Database
from schemas import AskResult, ParsedTransaction
from services.analytics_calculator import AnalyticsCalculator
from services.analytics_repository import AnalyticsRepository
from services.ask_planner import AskPlanner
from services.ask_policy import AskPolicy
from services.ask_renderer import AskRenderer
from services.ask_service import AskService


def _db_config():
    return SimpleNamespace(
        stt_model="whisper-large-v3",
        deepseek_model="deepseek-v4-flash",
        processing_version="1.0",
    )


def _tx(db, user_id, message_id, amount_minor, category, transaction_type="EXPENSE"):
    return db.create_transaction(
        telegram_chat_id=user_id,
        telegram_message_id=message_id,
        telegram_user_id=user_id,
        parsed=ParsedTransaction(
            transaction_type, amount_minor, "RUB", category, "запись", 0.95
        ),
        transcript="запись",
        message_date_utc=datetime(2026, 8, 15, tzinfo=timezone.utc),
        voice_duration_sec=0,
        config=_db_config(),
    )


def _service(tmp_path: Path) -> tuple[AskService, Path]:
    db_path = tmp_path / "ask.sqlite3"
    db = Database(db_path)
    _tx(db, 100, 1, 120000, "CAFE")
    _tx(db, 100, 2, 50000, "PRODUCTS")
    _tx(db, 100, 3, 90000, "CAFE")
    config = SimpleNamespace(
        ask_max_question_length=2000,
        ask_max_rows=500,
        ask_session_ttl_sec=600,
        app_timezone="Europe/Moscow",
        ask_temp_dir=tmp_path / "ask-images",
    )
    repository = AnalyticsRepository(db_path)
    planner = AskPlanner(app_timezone="Europe/Moscow")
    service = AskService(
        config=config,
        repository=repository,
        policy=AskPolicy(),
        planner=planner,
        calculator=AnalyticsCalculator(),
        renderer=AskRenderer(config.ask_temp_dir, config.app_timezone),
    )
    return service, db_path


def test_ask_returns_text_total_for_cafe(tmp_path):
    service, _db_path = _service(tmp_path)
    result = service.ask(100, "Сколько я потратил на кафе за всё время?")
    assert result.output_type == "TEXT"
    assert result.text
    assert "2 100,00" in result.text
    assert result.validate() is None


def test_ask_rejects_write_request_and_keeps_db_unchanged(tmp_path):
    service, db_path = _service(tmp_path)
    result = service.ask(100, "Удали все расходы")
    assert result.output_type == "TEXT"
    assert "анализировать" in result.text
    repository = AnalyticsRepository(db_path)
    rows = repository.fetch_transactions(repository.make_scope(100))
    assert len(rows) == 3


def test_ask_rejects_out_of_scope(tmp_path):
    service, _db_path = _service(tmp_path)
    result = service.ask(100, "Напиши рассказ")
    assert result.output_type == "TEXT"
    assert "финансовыми данными" in result.text


def test_ask_returns_no_data_message(tmp_path):
    service, _db_path = _service(tmp_path)
    result = service.ask(100, "Сколько я потратил на одежду за всё время?")
    assert result.output_type == "TEXT"
    assert "не найдено" in result.text


def test_ask_rejects_oversized_question(tmp_path):
    service, _db_path = _service(tmp_path)
    result = service.ask(100, "А" * 5000)
    assert result.output_type == "TEXT"
    assert "слишком длинный" in result.text


def test_ask_returns_infographic_for_category_structure(tmp_path):
    service, _db_path = _service(tmp_path)
    result = service.ask(100, "На что я потратил больше всего за всё время?")
    assert result.output_type == "INFOGRAPHIC"
    assert result.image_path is not None
    assert result.image_path.exists()
    assert result.image_path.stat().st_size > 0
    assert "Итого" in (result.caption or "")
    assert result.validate() is None
    result.image_path.unlink(missing_ok=True)


def test_ask_result_validation_rules():
    good_text = AskResult(output_type="TEXT", text="ok")
    good_text.validate()
    bad_text = AskResult(output_type="TEXT", text=None)
    try:
        bad_text.validate()
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    bad_both = AskResult(output_type="TEXT", text="ok", image_path=Path("x.png"))
    try:
        bad_both.validate()
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
    bad_image = AskResult(output_type="INFOGRAPHIC", image_path=None)
    try:
        bad_image.validate()
        raise AssertionError("expected ValueError")
    except ValueError:
        pass
