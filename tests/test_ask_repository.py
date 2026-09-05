from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy import text

from database import Database
from schemas import ParsedExchange, ParsedTransaction
from services.analytics_repository import AnalyticsRepository


def _config():
    return SimpleNamespace(
        stt_model="whisper-large-v3",
        deepseek_model="deepseek-v4-flash",
        processing_version="1.0",
    )


def _tx(
    db,
    config,
    user_id,
    message_id,
    amount_minor,
    category="PRODUCTS",
    scope="personal",
    family_id=None,
    paid_by=None,
):
    return db.create_transaction(
        telegram_chat_id=user_id,
        telegram_message_id=message_id,
        telegram_user_id=user_id,
        parsed=ParsedTransaction(
            "EXPENSE", amount_minor, "RUB", category, "запись", 0.95
        ),
        transcript="запись",
        message_date_utc=datetime.now(timezone.utc),
        voice_duration_sec=0,
        config=config,
        scope=scope,
        family_id=family_id,
        paid_by=paid_by or user_id,
    )


def _setup(db):
    config = _config()
    a, b, c = 100, 200, 300
    family1 = db.create_family("F1", a)
    code = db.generate_invite_code(a)
    db.join_family_by_code(b, code)
    family2 = db.create_family("F2", c)
    assert family1 is not None and family2 is not None

    _tx(db, config, a, 1, 10000)
    _tx(db, config, a, 2, 20000, scope="family", family_id=family1, paid_by=a)
    _tx(db, config, b, 1, 30000)
    _tx(db, config, b, 2, 40000, scope="family", family_id=family1, paid_by=b)
    _tx(db, config, c, 1, 50000)
    _tx(db, config, c, 2, 60000, scope="family", family_id=family2, paid_by=c)
    return a, b, c, family1, family2


def _total(rows):
    return sum(row.amount_minor for row in rows)


def test_family_isolation_for_user_a(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    a, _b, _c, _family1, _family2 = _setup(db)
    repository = AnalyticsRepository(tmp_path / "test.sqlite3")
    scope = repository.make_scope(a)
    rows = repository.fetch_transactions(scope)
    assert _total(rows) == 10000 + 20000 + 40000
    assert {row.amount_minor for row in rows} == {10000, 20000, 40000}


def test_family_isolation_for_user_c(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    _a, _b, c, _family1, _family2 = _setup(db)
    repository = AnalyticsRepository(tmp_path / "test.sqlite3")
    rows = repository.fetch_transactions(repository.make_scope(c))
    assert {row.amount_minor for row in rows} == {50000, 60000}


def test_user_b_cannot_see_a_personal(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    _a, b, _c, _family1, _family2 = _setup(db)
    repository = AnalyticsRepository(tmp_path / "test.sqlite3")
    rows = repository.fetch_transactions(repository.make_scope(b))
    assert 10000 not in {row.amount_minor for row in rows}
    assert 20000 in {row.amount_minor for row in rows}
    assert 40000 in {row.amount_minor for row in rows}


def test_data_scope_personal_and_my_payments(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    a, _b, _c, family1, _family2 = _setup(db)
    repository = AnalyticsRepository(tmp_path / "test.sqlite3")
    scope = repository.make_scope(a)
    assert scope.family_id == family1

    personal = repository.fetch_transactions(scope, data_scope="PERSONAL")
    assert {row.amount_minor for row in personal} == {10000}

    my_payments = repository.fetch_transactions(scope, data_scope="MY_PAYMENTS")
    assert {row.amount_minor for row in my_payments} == {20000}

    family = repository.fetch_transactions(scope, data_scope="FAMILY")
    assert _total(family) == 20000 + 40000


def test_repository_is_read_only_sqlite(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    _a, _b, _c, _family1, _family2 = _setup(db)
    repository = AnalyticsRepository(tmp_path / "test.sqlite3")
    with repository.engine.connect() as connection:
        with pytest.raises(OperationalError):
            connection.execute(text("UPDATE transactions SET amount_minor = 0"))
        with pytest.raises(OperationalError):
            connection.execute(text("DELETE FROM transactions"))
        with pytest.raises(OperationalError):
            connection.execute(text("CREATE TABLE should_not_exist (id INTEGER)"))
        with pytest.raises(OperationalError):
            connection.execute(text("DROP TABLE transactions"))
    with db.Session() as session:
        after = session.execute(text("SELECT COUNT(*) FROM transactions")).scalar()
    assert after == 6


def test_repository_fetch_applies_text_and_category_filters(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    a, _b, _c, _family1, _family2 = _setup(db)
    repository = AnalyticsRepository(tmp_path / "test.sqlite3")
    scope = repository.make_scope(a)
    rows = repository.fetch_transactions(scope, categories=("PRODUCTS",))
    assert len(rows) == 3
    rows = repository.fetch_transactions(scope, transaction_type="EXPENSE")
    assert len(rows) == 3


def test_accesssible_filters_categories_for_personal_rows(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    config = _config()
    user = 900
    db.upsert_user_and_chat(
        SimpleNamespace(
            chat=SimpleNamespace(id=user, type="private", title=None),
            from_user=SimpleNamespace(
                id=user, username="u", first_name="U", last_name=None
            ),
            message_id=1,
            date=1,
        )
    )
    _tx(db, config, user, 1, 10000, category="ALCOHOL")
    _tx(db, config, user, 2, 50000, category="PRODUCTS")
    _tx(db, config, user, 3, 70000, category="CAFE")
    repository = AnalyticsRepository(tmp_path / "test.sqlite3")
    scope = repository.make_scope(user)
    rows = repository.fetch_transactions(
        scope, transaction_type="EXPENSE", categories=("ALCOHOL",)
    )
    assert [row.category for row in rows] == ["ALCOHOL"]
    rows = repository.fetch_transactions(
        scope, transaction_type="INCOME", categories=("ALCOHOL",)
    )
    assert rows == []


def test_fetch_can_exclude_exchange_legs(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    user = 700
    message = SimpleNamespace(
        chat=SimpleNamespace(id=user, type="private", title=None),
        from_user=SimpleNamespace(
            id=user, username="u", first_name="U", last_name=None
        ),
        message_id=10,
        date=int(datetime(2026, 8, 30, tzinfo=timezone.utc).timestamp()),
        voice=None,
    )
    config = SimpleNamespace(
        stt_model="w", deepseek_model="d", processing_version="1.0"
    )
    parsed = ParsedExchange(
        from_amount_minor=6000000,
        from_currency="RUB",
        to_currency="AMD",
        to_amount_minor=24180000,
        rate=Decimal("4.03"),
        description="обмен",
        confidence=0.95,
    )
    db.create_exchange(message, parsed, "поменял 60000 рублей на 241800 драм", config)

    repository = AnalyticsRepository(tmp_path / "test.sqlite3")
    scope = repository.make_scope(user)
    with_legs = repository.fetch_transactions(scope, transaction_type="EXPENSE")
    assert len(with_legs) == 1
    no_legs = repository.fetch_transactions(
        scope, transaction_type="EXPENSE", exclude_exchange_legs=True
    )
    assert no_legs == []
