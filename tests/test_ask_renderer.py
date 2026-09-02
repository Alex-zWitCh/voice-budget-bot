from services.analytics_calculator import CalculationResult, SeriesPoint
from services.ask_renderer import (
    AskRenderer,
    period_description,
    transaction_type_label,
)


def _result(group_by, metric="SUM"):
    return CalculationResult(
        series=[
            SeriesPoint("август 2026", 120000, 2),
            SeriesPoint("сентябрь 2026", 180000, 3),
        ],
        total_minor=300000,
        total_count=5,
        currency="RUB",
        unconverted={"USD": 1},
        group_by=group_by,
        metric=metric,
    )


def test_renderer_chart_kind_selection(tmp_path):
    renderer = AskRenderer(tmp_path, "Europe/Moscow")
    assert renderer.chart_kind(_result("MONTH")) in {"line", "bar"}
    assert renderer.chart_kind(_result("DAY")) == "bar"
    assert renderer.chart_kind(_result("CATEGORY")) == "pie"


def test_renderer_creates_pie_for_categories(tmp_path):
    renderer = AskRenderer(tmp_path, "Europe/Moscow")
    path = renderer.render_chart(_result("CATEGORY"), title="Расходы", subtitle="")
    assert path.exists()
    assert path.stat().st_size > 0
    with open(path, "rb") as image:
        assert image.read(8).startswith(b"\x89PNG")
    path.unlink(missing_ok=True)


def test_render_text_answer_lists_total(tmp_path):
    text = AskRenderer.build_text_answer(
        _result("NONE"),
        title="Расходы на «Кафе»",
        subtitle="за август 2026",
        scope_note="личные записи",
        has_data_in_base_currency=True,
    )
    assert "3 000,00" in text
    assert "личные записи" in text


def test_render_text_answer_mentions_unconverted(tmp_path):
    text = AskRenderer.build_text_answer(
        _result("NONE"),
        title="Расходы",
        subtitle="за всё время",
        scope_note="личные записи",
        has_data_in_base_currency=True,
    )
    assert "не приведена к RUB" in text


def test_period_and_type_labels():
    assert transaction_type_label("EXPENSE") == "Расходы"
    assert transaction_type_label(None) == "Расходы и доходы"
    assert period_description(None, None, "Europe/Moscow") == "за всё время"
