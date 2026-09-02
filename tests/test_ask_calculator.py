from datetime import datetime, timezone
from decimal import Decimal

from schemas import (
    ASK_GROUP_BY_CATEGORY,
    ASK_GROUP_BY_MONTH,
    ASK_METRIC_SUM,
    AnalyticsTransaction,
    AskQueryPlan,
)
from services.analytics_calculator import AnalyticsCalculator


def _row(tx_type, amount_minor, currency, category, date, scope="personal"):
    return AnalyticsTransaction(
        id=0,
        transaction_type=tx_type,
        amount_minor=amount_minor,
        currency=currency,
        category=category,
        description="",
        transcript="",
        message_date_utc=date,
        scope=scope,
        paid_by_current_user=True,
    )


def test_calculator_groups_by_month_and_converts_currency(tmp_path):
    calculator = AnalyticsCalculator()
    august = datetime(2026, 8, 15, tzinfo=timezone.utc)
    september = datetime(2026, 9, 15, tzinfo=timezone.utc)
    rows = [
        _row("EXPENSE", 100000, "RUB", "PRODUCTS", august),
        _row("EXPENSE", 50000, "RUB", "PRODUCTS", august),
        _row("EXPENSE", 300000, "RUB", "PRODUCTS", september),
        _row("EXPENSE", 70000, "USD", "PRODUCTS", september),
    ]
    plan = AskQueryPlan(
        transaction_type="EXPENSE",
        date_from_utc=datetime(2026, 8, 1, tzinfo=timezone.utc),
        date_to_utc=datetime(2026, 10, 1, tzinfo=timezone.utc),
        group_by=ASK_GROUP_BY_MONTH,
        metrics=(ASK_METRIC_SUM,),
    )
    result = calculator.calculate(rows, plan, "RUB", [], {"PRODUCTS": "Продукты"})
    assert result.currency == "RUB"
    assert result.total_count == 3
    assert result.total_minor == 100000 + 50000 + 300000
    assert {point.label for point in result.series} == {"август 2026", "сентябрь 2026"}
    assert result.unconverted == {"USD": 1}


def test_calculator_groups_by_category_with_share(tmp_path):
    calculator = AnalyticsCalculator()
    date = datetime(2026, 8, 10, tzinfo=timezone.utc)
    rows = [
        _row("EXPENSE", 40000, "RUB", "CAFE", date),
        _row("EXPENSE", 20000, "RUB", "CAFE", date),
        _row("EXPENSE", 10000, "RUB", "PRODUCTS", date),
        _row("EXPENSE", 10000, "RUB", "PRODUCTS", date),
    ]
    plan = AskQueryPlan(
        transaction_type="EXPENSE",
        date_from_utc=datetime(2026, 8, 1, tzinfo=timezone.utc),
        date_to_utc=datetime(2026, 9, 1, tzinfo=timezone.utc),
        group_by=ASK_GROUP_BY_CATEGORY,
        metrics=(ASK_METRIC_SUM,),
    )
    result = calculator.calculate(
        rows, plan, "RUB", [], {"CAFE": "Кафе", "PRODUCTS": "Продукты"}
    )
    assert result.total_minor == 80000
    top, share = result.top_share()
    assert top.label == "Кафе"
    assert abs(share - 75.0) < 0.01


def test_calculator_converts_income_anchor_using_rate(tmp_path):
    calculator = AnalyticsCalculator()
    date = datetime(2026, 8, 10, tzinfo=timezone.utc)
    income = AnalyticsTransaction(
        id=1,
        transaction_type="INCOME",
        amount_minor=9200000,
        currency="RUB",
        category="SALARY",
        description="",
        transcript="",
        message_date_utc=date,
        scope="personal",
        paid_by_current_user=True,
        exchange_rate=Decimal("92"),
        from_currency="USD",
        from_amount_minor=100000,
    )
    plan = AskQueryPlan(
        transaction_type="INCOME",
        date_from_utc=datetime(2026, 8, 1, tzinfo=timezone.utc),
        date_to_utc=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    result = calculator.calculate(
        [income], plan, "RUB", [("USD", "RUB", Decimal("92"))], {}
    )
    assert result.total_minor == 100000 * 92


def test_calculator_empty_rows(tmp_path):
    calculator = AnalyticsCalculator()
    plan = AskQueryPlan(transaction_type="EXPENSE")
    result = calculator.calculate([], plan, "RUB", [], {})
    assert result.total_count == 0
    assert result.total_minor == 0
    assert result.series == []
