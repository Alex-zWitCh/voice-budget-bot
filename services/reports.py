from __future__ import annotations

import csv
import gzip
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt

from categories import CURRENCY_SYMBOLS
from services.currency_conversion import (
    build_rate_map as _build_rate_map,
    format_exchange_rate as _format_exchange_rate,
    to_base_minor as _to_base_minor,
)

logger = logging.getLogger(__name__)


def export_transactions_csv_gz(
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
    path = output_dir / f"transactions-{telegram_user_id}-{filename_suffix}.csv.gz"
    with gzip.open(path, "wt", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "id",
                "date_local",
                "date_utc",
                "created_at_utc",
                "telegram_chat_id",
                "telegram_message_id",
                "telegram_user_id",
                "transaction_type",
                "amount",
                "amount_minor",
                "currency",
                "amount_main",
                "amount_main_minor",
                "main_currency",
                "from_currency",
                "from_amount",
                "exchange_rate",
                "exchange_pair_id",
                "category_code",
                "category_title",
                "description",
                "transcript",
                "voice_duration_sec",
                "groq_model",
                "deepseek_model",
                "deepseek_confidence",
                "processing_version",
            ]
        )
        for row in rows:
            category_title = category_catalog.get(row.transaction_type, {}).get(row.category, row.category)
            date_utc = _as_utc(row.message_date_utc)
            created_utc = _as_utc(row.created_at_utc)
            base_minor = _to_base_minor(row, main_currency, rates)
            writer.writerow(
                [
                    row.id,
                    date_utc.astimezone(tz).isoformat(timespec="seconds"),
                    date_utc.isoformat(timespec="seconds"),
                    created_utc.isoformat(timespec="seconds"),
                    row.telegram_chat_id,
                    row.telegram_message_id,
                    row.telegram_user_id,
                    row.transaction_type,
                    f"{row.amount_minor / 100:.2f}",
                    row.amount_minor,
                    row.currency,
                    f"{base_minor / 100:.2f}" if base_minor is not None else "",
                    base_minor if base_minor is not None else "",
                    main_currency,
                    row.from_currency or "",
                    f"{row.from_amount_minor / 100:.2f}" if row.from_amount_minor is not None else "",
                    _format_exchange_rate(row.exchange_rate),
                    row.exchange_pair_id if row.exchange_pair_id is not None else "",
                    row.category,
                    category_title,
                    row.description,
                    row.transcript,
                    row.voice_duration_sec,
                    row.groq_model,
                    row.deepseek_model,
                    float(row.deepseek_confidence),
                    row.processing_version,
                ]
            )
    return path


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
) -> tuple[Path | None, str]:
    rows = db.list_transactions_for_user(telegram_user_id, start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc))
    category_catalog = db.get_category_catalog(telegram_user_id, active_only=False)
    main_currency = db.get_main_currency(telegram_user_id)
    rates = _build_rate_map(db.get_exchange_rates(telegram_user_id))

    totals: dict[tuple[str, str], int] = defaultdict(int)
    skipped: list[str] = []
    for row in rows:
        if row.transaction_type != transaction_type:
            continue
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
