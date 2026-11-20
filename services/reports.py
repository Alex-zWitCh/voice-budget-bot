from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from categories import CURRENCY_SYMBOLS
from services.currency_conversion import (
    build_rate_map as _build_rate_map,
    to_base_minor as _to_base_minor,
)

logger = logging.getLogger(__name__)

_TYPE_TITLES = {"EXPENSE": "Расход", "INCOME": "Доход"}
_XLSX_HEADERS = [
    "Дата",
    "Тип",
    "Категория",
    "Сумма",
    "Валюта",
    "Сумма (осн. валюта)",
    "Осн. валюта",
    "Из валюты",
    "Из суммы",
    "Курс",
    "Описание",
    "Транскрипция",
]


def export_transactions_xlsx(
    db,
    telegram_user_id: int,
    app_timezone: str,
    output_dir: Path,
    start_local: datetime,
    end_local: datetime,
    filename_suffix: str,
) -> Path:
    tz = ZoneInfo(app_timezone)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    rows = db.list_transactions_for_user(telegram_user_id, start_utc, end_utc)
    category_catalog = db.get_category_catalog(telegram_user_id, active_only=False)
    main_currency = db.get_main_currency(telegram_user_id)
    rates = _build_rate_map(db.get_exchange_rates(telegram_user_id))

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"transactions-{telegram_user_id}-{filename_suffix}.xlsx"

    wb = Workbook()
    ws = wb.active
    ws.title = "Операции"
    ws.append(_XLSX_HEADERS)
    for row in rows:
        base_minor = _to_base_minor(row, main_currency, rates)
        date_local = _as_utc(row.message_date_utc).astimezone(tz)
        ws.append(
            [
                date_local.strftime("%Y-%m-%d %H:%M"),
                _TYPE_TITLES.get(row.transaction_type, row.transaction_type),
                category_catalog.get(row.transaction_type, {}).get(row.category, row.category),
                round(row.amount_minor / 100, 2),
                row.currency,
                round(base_minor / 100, 2) if base_minor is not None else "",
                main_currency,
                row.from_currency or "",
                round(row.from_amount_minor / 100, 2) if row.from_amount_minor is not None else "",
                float(row.exchange_rate) if row.exchange_rate is not None else "",
                row.description,
                row.transcript,
            ]
        )
    _style_worksheet(ws)
    wb.save(path)
    return path


def _style_worksheet(ws) -> None:
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="4472C4")
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            if isinstance(cell.value, float):
                cell.number_format = "0.00"
    widths = [16, 9, 18, 12, 9, 18, 11, 11, 11, 10, 32, 44]
    for index, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(index)].width = width
    ws.freeze_panes = "A2"


def build_previous_month_expense_chart(db, telegram_user_id: int, app_timezone: str, output_dir: Path) -> tuple[Path | None, str]:
    tz = ZoneInfo(app_timezone)
    start_local, end_local = _previous_month_range(datetime.now(tz))
    period = start_local.strftime("%m.%Y")
    filename_suffix = start_local.strftime("%Y-%m")
    return build_category_chart(
        db=db,
        telegram_user_id=telegram_user_id,
        app_timezone=app_timezone,
        output_dir=output_dir,
        transaction_type="EXPENSE",
        start_local=start_local,
        end_local=end_local,
        period_title=period,
        empty_text=f"За прошлый календарный месяц ({period}) расходов не найдено.",
        caption=f"Расходы по категориям за {period}",
        filename_suffix=filename_suffix,
    )


def build_previous_month_income_chart(db, telegram_user_id: int, app_timezone: str, output_dir: Path) -> tuple[Path | None, str]:
    tz = ZoneInfo(app_timezone)
    start_local, end_local = _previous_month_range(datetime.now(tz))
    period = start_local.strftime("%m.%Y")
    filename_suffix = start_local.strftime("%Y-%m")
    return build_category_chart(
        db=db,
        telegram_user_id=telegram_user_id,
        app_timezone=app_timezone,
        output_dir=output_dir,
        transaction_type="INCOME",
        start_local=start_local,
        end_local=end_local,
        period_title=period,
        empty_text=f"За прошлый календарный месяц ({period}) доходов не найдено.",
        caption=f"Доходы по категориям за {period}",
        filename_suffix=filename_suffix,
    )


def build_last_30_days_expense_chart(db, telegram_user_id: int, app_timezone: str, output_dir: Path) -> tuple[Path | None, str]:
    tz = ZoneInfo(app_timezone)
    end_local = datetime.now(tz)
    start_local = end_local - timedelta(days=30)
    period = f"{start_local:%d.%m.%Y} - {end_local:%d.%m.%Y}"
    return build_category_chart(
        db=db,
        telegram_user_id=telegram_user_id,
        app_timezone=app_timezone,
        output_dir=output_dir,
        transaction_type="EXPENSE",
        start_local=start_local,
        end_local=end_local,
        period_title="последние 30 дней",
        empty_text="За последние 30 дней расходов не найдено.",
        caption=f"Расходы по категориям за 30 дней ({period})",
        filename_suffix=f"last-30-days-{end_local:%Y-%m-%d}",
    )


def build_last_30_days_income_chart(db, telegram_user_id: int, app_timezone: str, output_dir: Path) -> tuple[Path | None, str]:
    tz = ZoneInfo(app_timezone)
    end_local = datetime.now(tz)
    start_local = end_local - timedelta(days=30)
    period = f"{start_local:%d.%m.%Y} - {end_local:%d.%m.%Y}"
    return build_category_chart(
        db=db,
        telegram_user_id=telegram_user_id,
        app_timezone=app_timezone,
        output_dir=output_dir,
        transaction_type="INCOME",
        start_local=start_local,
        end_local=end_local,
        period_title="последние 30 дней",
        empty_text="За последние 30 дней доходов не найдено.",
        caption=f"Доходы по категориям за 30 дней ({period})",
        filename_suffix=f"last-30-days-{end_local:%Y-%m-%d}",
    )


def _resolve_family_id(db, telegram_user_id: int) -> int | None:
    family = db.get_family_for_user(telegram_user_id)
    return family.id if family is not None else None


def _scoped_expense_chart(
    db,
    telegram_user_id: int,
    app_timezone: str,
    output_dir: Path,
    scope_filter: str,
    scope_title: str,
    scope_tag: str,
    start_local: datetime,
    end_local: datetime,
    period_title: str,
    empty_text: str,
    caption: str,
    filename_suffix: str,
) -> tuple[Path | None, str]:
    family_id = _resolve_family_id(db, telegram_user_id) if scope_filter != SCOPE_PERSONAL else None
    if scope_filter != SCOPE_PERSONAL and family_id is None:
        return None, "Нет семьи — семейные диаграммы недоступны. Создайте семью: /family create <имя>."
    return build_category_chart(
        db=db,
        telegram_user_id=telegram_user_id,
        app_timezone=app_timezone,
        output_dir=output_dir,
        transaction_type="EXPENSE",
        start_local=start_local,
        end_local=end_local,
        period_title=period_title,
        empty_text=empty_text,
        caption=caption,
        filename_suffix=f"{filename_suffix}-{scope_tag}",
        scope_filter=scope_filter,
        family_id=family_id,
    )


def build_last_30_days_personal_expense_chart(db, telegram_user_id: int, app_timezone: str, output_dir: Path) -> tuple[Path | None, str]:
    tz = ZoneInfo(app_timezone)
    end_local = datetime.now(tz)
    start_local = end_local - timedelta(days=30)
    period = f"{start_local:%d.%m.%Y} - {end_local:%d.%m.%Y}"
    return _scoped_expense_chart(
        db, telegram_user_id, app_timezone, output_dir,
        SCOPE_PERSONAL, "личные", "personal",
        start_local, end_local, "последние 30 дней",
        "За последние 30 дней личных расходов не найдено.",
        f"Расходы личные за 30 дней ({period})",
        f"last-30-days-{end_local:%Y-%m-%d}",
    )


def build_last_30_days_family_mine_expense_chart(db, telegram_user_id: int, app_timezone: str, output_dir: Path) -> tuple[Path | None, str]:
    tz = ZoneInfo(app_timezone)
    end_local = datetime.now(tz)
    start_local = end_local - timedelta(days=30)
    period = f"{start_local:%d.%m.%Y} - {end_local:%d.%m.%Y}"
    return _scoped_expense_chart(
        db, telegram_user_id, app_timezone, output_dir,
        SCOPE_FAMILY_MINE, "семейные мои", "family-mine",
        start_local, end_local, "последние 30 дней",
        "За последние 30 дней ваших семейных расходов не найдено.",
        f"Расходы семейные (мои) за 30 дней ({period})",
        f"last-30-days-{end_local:%Y-%m-%d}",
    )


def build_last_30_days_family_total_expense_chart(db, telegram_user_id: int, app_timezone: str, output_dir: Path) -> tuple[Path | None, str]:
    tz = ZoneInfo(app_timezone)
    end_local = datetime.now(tz)
    start_local = end_local - timedelta(days=30)
    period = f"{start_local:%d.%m.%Y} - {end_local:%d.%m.%Y}"
    return _scoped_expense_chart(
        db, telegram_user_id, app_timezone, output_dir,
        SCOPE_FAMILY_ALL, "семейные общие", "family-total",
        start_local, end_local, "последние 30 дней",
        "За последние 30 дней семейных расходов не найдено.",
        f"Расходы семейные (все) за 30 дней ({period})",
        f"last-30-days-{end_local:%Y-%m-%d}",
    )


def build_previous_month_personal_expense_chart(db, telegram_user_id: int, app_timezone: str, output_dir: Path) -> tuple[Path | None, str]:
    tz = ZoneInfo(app_timezone)
    start_local, end_local = _previous_month_range(datetime.now(tz))
    period = start_local.strftime("%m.%Y")
    filename_suffix = start_local.strftime("%Y-%m")
    return _scoped_expense_chart(
        db, telegram_user_id, app_timezone, output_dir,
        SCOPE_PERSONAL, "личные", "personal",
        start_local, end_local, period,
        f"За прошлый календарный месяц ({period}) личных расходов не найдено.",
        f"Расходы личные по категориям за {period}",
        filename_suffix,
    )


def build_previous_month_family_mine_expense_chart(db, telegram_user_id: int, app_timezone: str, output_dir: Path) -> tuple[Path | None, str]:
    tz = ZoneInfo(app_timezone)
    start_local, end_local = _previous_month_range(datetime.now(tz))
    period = start_local.strftime("%m.%Y")
    filename_suffix = start_local.strftime("%Y-%m")
    return _scoped_expense_chart(
        db, telegram_user_id, app_timezone, output_dir,
        SCOPE_FAMILY_MINE, "семейные мои", "family-mine",
        start_local, end_local, period,
        f"За прошлый календарный месяц ({period}) ваших семейных расходов не найдено.",
        f"Расходы семейные (мои) по категориям за {period}",
        filename_suffix,
    )


def build_previous_month_family_total_expense_chart(db, telegram_user_id: int, app_timezone: str, output_dir: Path) -> tuple[Path | None, str]:
    tz = ZoneInfo(app_timezone)
    start_local, end_local = _previous_month_range(datetime.now(tz))
    period = start_local.strftime("%m.%Y")
    filename_suffix = start_local.strftime("%Y-%m")
    return _scoped_expense_chart(
        db, telegram_user_id, app_timezone, output_dir,
        SCOPE_FAMILY_ALL, "семейные общие", "family-total",
        start_local, end_local, period,
        f"За прошлый календарный месяц ({period}) семейных расходов не найдено.",
        f"Расходы семейные (все) по категориям за {period}",
        filename_suffix,
    )


#: Сколько завершённых календарных месяцев охватывает диаграмма динамики.
DYNAMICS_MONTHS = 4
#: Минимальное относительное изменение последнего месяца к предыдущему, %.
DYNAMICS_MIN_PCT = 20.0
#: Минимальное абсолютное изменение в minor units основной валюты.
#: 300000 minor units = 3000.00 (калибруется по реальным данным).
DYNAMICS_MIN_ABS_MINOR = 300000
#: Максимум категорий на одной композитной диаграмме динамики.
DYNAMICS_MAX_CATEGORIES = 12

#: Фильтры области видимости для круговых диаграмм расходов.
SCOPE_PERSONAL = "personal"
SCOPE_FAMILY_MINE = "family_mine"
SCOPE_FAMILY_ALL = "family_all"


def build_category_chart(
    db,
    telegram_user_id: int,
    app_timezone: str,
    output_dir: Path,
    transaction_type: str,
    start_local: datetime,
    end_local: datetime,
    period_title: str,
    empty_text: str,
    caption: str,
    filename_suffix: str,
    scope_filter: str | None = None,
    family_id: int | None = None,
) -> tuple[Path | None, str]:
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    if scope_filter == SCOPE_FAMILY_ALL and family_id is not None:
        rows = db.list_family_transactions(family_id, start_utc, end_utc)
    else:
        rows = db.list_transactions_for_user(telegram_user_id, start_utc, end_utc)
    category_catalog = db.get_category_catalog(telegram_user_id, active_only=False)
    main_currency = db.get_main_currency(telegram_user_id)
    rates = _build_rate_map(db.get_exchange_rates(telegram_user_id))

    totals: dict[tuple[str, str], int] = defaultdict(int)
    skipped: list[str] = []
    for row in rows:
        if row.transaction_type != transaction_type:
            continue
        if row.exchange_pair_id is not None:
            continue
        if scope_filter == SCOPE_PERSONAL and row.scope != "personal":
            continue
        if scope_filter == SCOPE_FAMILY_MINE and not (
            row.scope == "family" and row.paid_by == telegram_user_id
        ):
            continue
        base_minor = _to_base_minor(row, main_currency, rates)
        base_minor = _to_base_minor(row, main_currency, rates)
        if base_minor is None:
            skipped.append(f"{row.amount_minor / 100:.2f} {row.currency}")
            continue
        title = category_catalog.get(transaction_type, {}).get(row.category, row.category)
        totals[(row.category, title)] += base_minor

    if skipped:
        logger.warning(
            "Report skipped %d transactions without a rate to %s (user=%s type=%s)",
            len(skipped),
            main_currency,
            telegram_user_id,
            transaction_type,
        )

    if not totals:
        suffix = ""
        if skipped:
            suffix = f" Пропущено {len(skipped)} записей без курса в {main_currency} (например, {skipped[0]})."
        return None, f"{empty_text} В основной валюте {main_currency} операций не найдено.{suffix}"

    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = "expenses" if transaction_type == "EXPENSE" else "income"
    title = "Расходы" if transaction_type == "EXPENSE" else "Доходы"
    path = output_dir / f"{prefix}-{telegram_user_id}-{filename_suffix}.png"
    _render_pie_chart(path, totals, main_currency, period_title, title)
    caption_extra = ""
    if skipped:
        caption_extra = f"\n\n⚠️ Пропущено {len(skipped)} записей без курса в {main_currency} (например, {skipped[0]})."
    return path, caption + caption_extra


_RU_MONTH_SHORT = ("", "янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек")


def _completed_month_ranges(app_timezone: str, months: int = DYNAMICS_MONTHS, now_local: datetime | None = None) -> list[tuple[datetime, datetime]]:
    """Последние `months` завершённых календарных месяцев (текущий неполный исключается)."""
    tz = ZoneInfo(app_timezone)
    now_local = now_local or datetime.now(tz)
    first_of_current = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    ranges = []
    for i in range(months, 0, -1):
        end = _add_months(first_of_current, -(i - 1))
        start = _add_months(first_of_current, -i)
        ranges.append((start, end))
    return ranges


def monthly_category_totals(
    db,
    telegram_user_id: int,
    app_timezone: str,
    months: int = DYNAMICS_MONTHS,
    now_local: datetime | None = None,
) -> dict:
    """Помесячные итоги расходов по категориям в основной валюте.

    Возвращает dict: months (подписи), main_currency, symbol,
    categories {code: {title, personal: [...], family: [...]}},
    где personal — scope='personal', family — scope='family' всей семьи.
    Зеркальные ноги конвертаций исключаются (не расход).
    """
    month_ranges = _completed_month_ranges(app_timezone, months, now_local)
    main_currency = db.get_main_currency(telegram_user_id)
    symbol = CURRENCY_SYMBOLS.get(main_currency, main_currency)
    rates = _build_rate_map(db.get_exchange_rates(telegram_user_id))
    category_catalog = db.get_category_catalog(telegram_user_id, active_only=False)
    family = db.get_family_for_user(telegram_user_id)
    family_id = family.id if family is not None else None

    categories: dict[str, dict] = {}
    skipped = 0
    month_labels = []
    for start_local, end_local in month_ranges:
        month_labels.append(f"{_RU_MONTH_SHORT[start_local.month]} {start_local.strftime('%y')}")
        start_utc, end_utc = start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)
        own_rows = db.list_transactions_for_user(telegram_user_id, start_utc, end_utc)
        family_rows = (
            db.list_family_transactions(family_id, start_utc, end_utc)
            if family_id is not None
            else []
        )
        seen_ids: set[int] = set()
        for row in list(own_rows) + list(family_rows):
            if getattr(row, "id", None) in seen_ids:
                continue
            seen_ids.add(row.id)
            if row.transaction_type != "EXPENSE":
                continue
            if row.exchange_pair_id is not None:
                continue
            base_minor = _to_base_minor(row, main_currency, rates)
            if base_minor is None:
                skipped += 1
                continue
            bucket = "personal" if row.scope == "personal" else "family"
            entry = categories.setdefault(
                row.category,
                {
                    "title": category_catalog.get("EXPENSE", {}).get(row.category, row.category),
                    "personal": [0] * len(month_ranges),
                    "family": [0] * len(month_ranges),
                },
            )
            entry[bucket][len(month_labels) - 1] += base_minor

    if skipped:
        logger.warning(
            "Dynamics skipped %d transactions without a rate to %s (user=%s)",
            skipped,
            main_currency,
            telegram_user_id,
        )
    return {
        "months": month_labels,
        "main_currency": main_currency,
        "symbol": symbol,
        "categories": categories,
        "skipped": skipped,
    }


def detect_significant_moves(
    monthly: dict,
    min_pct: float = DYNAMICS_MIN_PCT,
    min_abs_minor: int = DYNAMICS_MIN_ABS_MINOR,
) -> list[dict]:
    """Значимые изменения последнего месяца к предыдущему.

    Категория попадает в результат, если: присутствует минимум в 2 месяцах,
    |Δ%| >= min_pct И |Δ| >= min_abs_minor. Дополнительно определяется тренд
    за последние 3 месяца: рост N-й месяц / снижение после роста / снижение.
    """
    moves = []
    for code, data in monthly["categories"].items():
        totals = [p + f for p, f in zip(data["personal"], data["family"])]
        present = sum(1 for t in totals if t > 0)
        if present < 2 or len(totals) < 2:
            continue
        last, prev = totals[-1], totals[-2]
        if prev <= 0:
            if last < min_abs_minor:
                continue
            moves.append(
                {
                    "code": code,
                    "title": data["title"],
                    "personal": data["personal"],
                    "family": data["family"],
                    "last": last,
                    "prev": prev,
                    "pct": None,
                    "delta": last,
                    "trend": "новые траты",
                }
            )
            continue
        delta = last - prev
        pct = delta / prev * 100
        if abs(pct) < min_pct or abs(delta) < min_abs_minor:
            continue
        moves.append(
            {
                "code": code,
                "title": data["title"],
                "personal": data["personal"],
                "family": data["family"],
                "last": last,
                "prev": prev,
                "pct": pct,
                "delta": delta,
                "trend": _trend_label(totals),
            }
        )
    moves.sort(key=lambda m: abs(m["delta"]), reverse=True)
    return moves


def _trend_label(totals: list[int]) -> str:
    """Направление изменения за последние до 3 месяцев."""
    steps = [totals[i] - totals[i - 1] for i in range(max(1, len(totals) - 3), len(totals))]
    if not steps:
        return "без изменений"
    if all(s > 0 for s in steps):
        n = len(steps) + 1
        return f"рост {n}-й месяц"
    if steps[-1] < 0 and len(steps) >= 2 and steps[-2] > 0:
        return "снижение после роста"
    if all(s < 0 for s in steps):
        return f"снижение {len(steps) + 1}-й месяц"
    return "изменение"


def build_dynamics_chart(
    db,
    telegram_user_id: int,
    app_timezone: str,
    output_dir: Path,
    filename_suffix: str,
    months: int = DYNAMICS_MONTHS,
    now_local: datetime | None = None,
) -> tuple[Path | None, str]:
    """Композитная диаграмма динамики: только значимые изменения категорий.

    Возвращает (path|None, caption). Пустой результат — текст без картинки.
    """
    monthly = monthly_category_totals(db, telegram_user_id, app_timezone, months, now_local)
    moves = detect_significant_moves(monthly)
    main_currency = monthly["main_currency"]
    symbol = monthly["symbol"]

    if not moves:
        return None, (
            "Существенных изменений трат за последние "
            f"{months} мес. нет: все категории изменились "
            f"менее чем на {DYNAMICS_MIN_PCT:.0f}%."
        )

    shown = moves[:DYNAMICS_MAX_CATEGORIES]
    n = len(shown)
    fig, axes = plt.subplots(n, 1, figsize=(10, 2.6 * n), dpi=160, squeeze=False)
    fig.suptitle(f"Динамика трат ({', '.join(monthly['months'])})", fontsize=15, y=0.995)
    for ax, move in zip(axes.flat, shown):
        personal = [v / 100 for v in move["personal"]]
        family = [v / 100 for v in move["family"]]
        xs = range(len(monthly["months"]))
        ax.bar(list(xs), personal, label="Личные", color="#4C78A8")
        ax.bar(list(xs), family, bottom=personal, label="Семейные", color="#F58518")
        ax.set_xticks(list(xs), monthly["months"], fontsize=9)
        ax.set_ylabel(symbol, fontsize=9)
        if move["pct"] is None:
            note = "новые траты"
        else:
            sign = "+" if move["pct"] > 0 else ""
            note = f"{sign}{move['pct']:.0f}%"
        ax.set_title(f"{move['title']}: {note} ({move['trend']})", fontsize=11, loc="left")
        ax.ticklabel_format(style="plain", axis="y")
    handles, labels_ = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels_, loc="upper right", fontsize=9)
    fig.tight_layout()
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"dynamics-{telegram_user_id}-{filename_suffix}.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)

    lines = [f"Динамика трат ({', '.join(monthly['months'])}):"]
    for move in shown[:8]:
        if move["pct"] is None:
            change = "новые траты"
        else:
            sign = "+" if move["pct"] > 0 else ""
            change = f"{sign}{move['pct']:.0f}%"
        lines.append(
            f"• {move['title']}: {change} ({_format_money(move['last'] / 100, symbol)}; {move['trend']})"
        )
    if len(moves) > 8:
        lines.append(f"…и ещё {len(moves) - 8}.")
    return path, "\n".join(lines)


def previous_month_period(app_timezone: str, now_local: datetime | None = None) -> tuple[datetime, datetime, str]:
    tz = ZoneInfo(app_timezone)
    now_local = now_local or datetime.now(tz)
    start_local, end_local = _previous_month_range(now_local)
    return start_local, end_local, start_local.strftime("%Y-%m")


def _render_pie_chart(path: Path, totals: dict[tuple[str, str], int], currency: str, period: str, title: str) -> None:
    sorted_items = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    labels = [title for (_code, title), _amount in sorted_items]
    values = [amount / 100 for _key, amount in sorted_items]
    total = sum(values)
    symbol = CURRENCY_SYMBOLS.get(currency, currency)

    fig, ax = plt.subplots(figsize=(9, 7), dpi=160)
    colors = plt.get_cmap("tab20").colors
    wedges, _texts, autotexts = ax.pie(
        values,
        labels=None,
        autopct=lambda pct: _autopct(pct, total, symbol),
        startangle=90,
        counterclock=False,
        colors=colors[: len(values)],
        pctdistance=0.72,
        wedgeprops={"linewidth": 1, "edgecolor": "white"},
    )
    for text in autotexts:
        text.set_fontsize(9)
        text.set_color("#222222")
    legend_labels = [
        f"{name} — {_format_percent(value, total, symbol)}"
        for name, value in zip(labels, values)
    ]
    ax.legend(wedges, legend_labels, title="Категории", loc="center left", bbox_to_anchor=(1, 0.5), fontsize=9)
    ax.set_title(f"{title} за {period}\nИтого: {_format_money(total, symbol)}", fontsize=15, pad=18)
    ax.axis("equal")
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def _autopct(pct: float, total: float, symbol: str) -> str:
    if pct < 4:
        return ""
    amount = total * pct / 100
    return f"{pct:.1f}%\n{_format_money(amount, symbol)}"


def _format_percent(value: float, total: float, symbol: str) -> str:
    percent = (value / total) * 100 if total else 0.0
    return f"{percent:.1f}%"


def _format_money(amount: float, symbol: str) -> str:
    return f"{amount:,.0f}".replace(",", " ") + f" {symbol}"


def _previous_month_range(now_local: datetime) -> tuple[datetime, datetime]:
    current_month = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start = _add_months(current_month, -1)
    return start, current_month


def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    max_day = _month_days(year, month)
    return value.replace(year=year, month=month, day=min(value.day, max_day))


def _month_days(year: int, month: int) -> int:
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)
    return (next_month - datetime(year, month, 1)).days


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
