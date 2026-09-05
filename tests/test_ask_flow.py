from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from database import AskRequest, Database
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


def test_ask_records_history_entries(tmp_path):
    db_path = tmp_path / "ask-history.sqlite3"
    db = Database(db_path)
    _tx(db, 100, 1, 120000, "CAFE")
    config = SimpleNamespace(
        ask_max_question_length=2000,
        ask_max_rows=500,
        app_timezone="Europe/Moscow",
        ask_temp_dir=tmp_path / "ask-images",
        ask_history_enabled=True,
        ask_model_effective="deepseek-v4-flash",
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
        recorder=db,
    )
    service.ask(100, "Сколько я потратил на кафе за всё время?")
    service.ask(100, "Удали все расходы")
    with db.Session() as session:
        rows = session.query(AskRequest).order_by(AskRequest.id).all()
    assert len(rows) == 2
    assert rows[0].telegram_user_id == 100
    assert rows[0].policy_code == "FINANCIAL_DATA_QUERY"
    assert rows[0].output_type == "TEXT"
    assert rows[0].plan_json is not None
    assert rows[1].policy_code == "WRITE_REQUEST"
    assert rows[1].output_type == "TEXT"
    assert rows[1].question == "Удали все расходы"


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


def test_ask_returns_line_by_line_list(tmp_path):
    db_path = tmp_path / "ask-list.sqlite3"
    db = Database(db_path)
    _tx(db, 100, 1, 120000, "ALCOHOL")
    _tx(db, 100, 2, 80000, "ALCOHOL")
    _tx(db, 100, 3, 50000, "PRODUCTS")
    config = SimpleNamespace(
        ask_max_question_length=2000,
        ask_max_rows=500,
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
    result = service.ask(
        100, "Ввведи построчно все мои траты на алкоголь: число и сколько"
    )
    assert result.output_type == "TEXT"
    assert result.text is not None
    assert "Найдено операций: 2" in result.text
    assert "Алкоголь" in result.text
    assert "PRODUCTS" not in result.text
    assert "2 000,00" in result.text


def test_ask_scope_deterministic_from_question(tmp_path):
    from categories import CATEGORY_BY_TYPE
    from services.ask_planner import AskPlanner

    planner = AskPlanner(app_timezone="Europe/Moscow")
    assert (
        planner.plan(
            "мои личные расходы на алкоголь", CATEGORY_BY_TYPE, "RUB"
        ).data_scope
        == "PERSONAL"
    )
    assert (
        planner.plan("семейные траты на продукты", CATEGORY_BY_TYPE, "RUB").data_scope
        == "FAMILY"
    )
    assert (
        planner.plan("сколько я трачу на кафе", CATEGORY_BY_TYPE, "RUB").data_scope
        == "ACCESSIBLE"
    )


def _dated_tx(db, user, message_id, amount_minor, date_utc):
    return db.create_transaction(
        telegram_chat_id=user,
        telegram_message_id=message_id,
        telegram_user_id=user,
        parsed=ParsedTransaction("EXPENSE", amount_minor, "RUB", "CAFE", "кафе", 0.95),
        transcript="кафе",
        message_date_utc=date_utc,
        voice_duration_sec=0,
        config=_db_config(),
    )


def test_ask_returns_last_n_operations_newest_first(tmp_path):
    from datetime import datetime, timezone

    db_path = tmp_path / "ask-last.sqlite3"
    db = Database(db_path)
    _dated_tx(db, 100, 1, 100000, datetime(2026, 7, 1, 12, tzinfo=timezone.utc))
    _dated_tx(db, 100, 2, 200000, datetime(2026, 7, 2, 12, tzinfo=timezone.utc))
    _dated_tx(db, 100, 3, 300000, datetime(2026, 7, 3, 12, tzinfo=timezone.utc))
    config = SimpleNamespace(
        ask_max_question_length=2000,
        ask_max_rows=500,
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
    result = service.ask(100, "Выведи 3 моих последних трат")
    assert result.output_type == "TEXT"
    assert result.text is not None
    assert "Найдено операций: 3." in result.text
    assert result.text.index("03.07.2026") < result.text.index("01.07.2026")
    assert "Сумма (в RUB): 6 000,00" in result.text
