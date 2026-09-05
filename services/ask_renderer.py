from __future__ import annotations

import calendar
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt

from categories import CURRENCY_SYMBOLS
from schemas import (
    ASK_GROUP_BY_CATEGORY,
    ASK_GROUP_BY_CURRENCY,
    ASK_GROUP_BY_DAY,
    ASK_GROUP_BY_MONTH,
    ASK_GROUP_BY_NONE,
    ASK_GROUP_BY_SCOPE,
    ASK_GROUP_BY_WEEK,
    ASK_METRIC_AVG,
    ASK_METRIC_COUNT,
)
from services.analytics_calculator import CalculationResult, RUSSIAN_MONTHS
from services.currency_conversion import symbol_for

RUSSIAN_MONTHS_GENITIVE = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}


def format_minor(amount_minor: int, currency: str) -> str:
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    amount = f"{amount_minor / 100:,.2f}".replace(",", " ").replace(".", ",")
    return f"{amount} {symbol}"


def format_minor_short(amount_minor: int, currency: str) -> str:
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    amount = f"{amount_minor / 100:,.0f}".replace(",", " ")
    return f"{amount} {symbol}"


def period_description(
    date_from_utc: Optional[datetime],
    date_to_utc: Optional[datetime],
    app_timezone: str,
) -> str:
    tz = ZoneInfo(app_timezone)
    if date_from_utc is None and date_to_utc is None:
        return "за всё время"
    if date_from_utc is not None and date_to_utc is not None:
        local_from = date_from_utc.astimezone(tz)
        local_to = (date_to_utc - timedelta(seconds=1)).astimezone(tz)
        if (
            local_from.day == 1
            and local_to.day == _last_day(local_to)
            and local_from.hour == 0
        ):
            if _same_month(local_from, local_to):
                return f"за {RUSSIAN_MONTHS[local_from.month]} {local_from.year}"
            return f"с {RUSSIAN_MONTHS_GENITIVE[local_from.month]} {local_from.year} по {RUSSIAN_MONTHS_GENITIVE[local_to.month]} {local_to.year}"
        return f"с {local_from:%d.%m.%Y} по {local_to:%d.%m.%Y}"
    if date_from_utc is not None:
        local_from = date_from_utc.astimezone(tz)
        return f"с {local_from:%d.%m.%Y}"
    local_to = (date_to_utc - timedelta(seconds=1)).astimezone(tz)
    return f"по {local_to:%d.%m.%Y}"


def _last_day(value: datetime) -> int:
    return calendar.monthrange(value.year, value.month)[1]


def _same_month(left: datetime, right: datetime) -> bool:
    return left.year == right.year and left.month == right.month


def scope_description(data_scope: str, has_family: bool) -> str:
    if not has_family:
        return "личные записи"
    if data_scope == "PERSONAL":
        return "личные записи"
    if data_scope == "FAMILY":
        return "семейные записи"
    if data_scope == "MY_PAYMENTS":
        return "семейные записи, оплаченные вами"
    return "личные и семейные записи"


def transaction_type_label(transaction_type: Optional[str]) -> str:
    if transaction_type == "EXPENSE":
        return "Расходы"
    if transaction_type == "INCOME":
        return "Доходы"
    return "Расходы и доходы"


class AskRenderer:
    def __init__(self, temp_dir: Path, app_timezone: str):
        self.temp_dir = temp_dir
        self.app_timezone = app_timezone

    def _new_path(self, extension: str) -> Path:
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        return self.temp_dir / f"ask-{uuid.uuid4().hex}.{extension}"

    def chart_kind(self, result: CalculationResult) -> str:
        if result.group_by == ASK_GROUP_BY_MONTH:
            return "line" if len(result.series) >= 3 else "bar"
        if result.group_by in {ASK_GROUP_BY_DAY, ASK_GROUP_BY_WEEK}:
            return "bar"
        if result.group_by in {
            ASK_GROUP_BY_CATEGORY,
            ASK_GROUP_BY_CURRENCY,
            ASK_GROUP_BY_SCOPE,
        }:
            return "pie" if len(result.series) <= 7 else "bar"
        return "bar"

    def render_chart(
        self, result: CalculationResult, title: str, subtitle: str, notes: str = ""
    ) -> Path:
        kind = self.chart_kind(result)
        path = self._new_path("png")
        labels = [point.label for point in result.series]
        values = [point.total_minor / 100 for point in result.series]
        currency = result.currency
        symbol = CURRENCY_SYMBOLS.get(currency, currency)
        total_text = f"{result.total_minor / 100:,.0f}".replace(",", " ")
        title_text = f"{title} {subtitle}"
        if kind == "pie":
            self._render_pie(
                path, labels, values, symbol, title_text, total_text, notes
            )
        elif kind == "line":
            self._render_line(
                path, labels, values, symbol, title_text, total_text, notes
            )
        else:
            self._render_bar(
                path, labels, values, symbol, title_text, total_text, notes
            )
        return path

    def render_summary_card(
        self,
        lines: list[tuple[str, str]],
        title: str,
        subtitle: str,
        notes: str = "",
    ) -> Path:
        path = self._new_path("png")
        fig, ax = plt.subplots(figsize=(9, max(3, 0.5 * len(lines) + 2)), dpi=160)
        ax.axis("off")
        header = f"{title} {subtitle}".strip()
        ax.text(
            0.05,
            0.96,
            header,
            transform=ax.transAxes,
            fontsize=17,
            fontweight="bold",
            va="top",
        )
        y = 0.86
        for label, value in lines:
            ax.text(0.06, y, label, transform=ax.transAxes, fontsize=13, va="center")
            ax.text(
                0.94,
                y,
                value,
                transform=ax.transAxes,
                fontsize=13,
                fontweight="bold",
                va="center",
                ha="right",
            )
            y -= 0.055
        if notes:
            ax.text(
                0.05,
                0.02,
                notes,
                transform=ax.transAxes,
                fontsize=10,
                va="bottom",
                color="#666666",
            )
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)
        return path

    @staticmethod
    def _render_pie(path, labels, values, symbol, title_text, total_text, notes):
        fig, ax = plt.subplots(figsize=(9, 7), dpi=160)
        colors = plt.get_cmap("tab20").colors
        total = sum(values) or 1
        wedges, _texts, autotexts = ax.pie(
            values,
            labels=labels,
            autopct=lambda pct: (
                f"{pct:.1f}%\n{total * pct / 100:,.0f}".replace(",", " ") + f" {symbol}"
                if pct >= 4
                else ""
            ),
            startangle=90,
            counterclock=False,
            colors=colors[: len(values)],
            pctdistance=0.72,
            labeldistance=1.08,
            wedgeprops={"linewidth": 1, "edgecolor": "white"},
        )
        for text in autotexts:
            text.set_fontsize(9)
            text.set_color("#222222")
        ax.legend(
            wedges, labels, loc="center left", bbox_to_anchor=(1, 0.5), fontsize=9
        )
        ax.set_title(f"{title_text}\nИтого: {total_text} {symbol}", fontsize=15, pad=18)
        ax.axis("equal")
        fig.tight_layout()
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)

    @staticmethod
    def _render_bar(path, labels, values, symbol, title_text, total_text, notes):
        fig, ax = plt.subplots(figsize=(max(8, len(labels) * 1.1), 7), dpi=160)
        colors = plt.get_cmap("tab10").colors[: len(values)]
        bars = ax.bar(labels, values, color=colors)
        ax.set_title(f"{title_text}\nИтого: {total_text} {symbol}", fontsize=14, pad=16)
        ax.set_ylabel(f"Сумма, {symbol}")
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        for bar, value in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                f"{value:,.0f}".replace(",", " "),
                ha="center",
                va="bottom",
                fontsize=9,
            )
        ax.tick_params(axis="x", rotation=30, labelsize=9)
        fig.tight_layout()
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)

    @staticmethod
    def _render_line(path, labels, values, symbol, title_text, total_text, notes):
        fig, ax = plt.subplots(figsize=(11, 6), dpi=160)
        x_positions = list(range(len(values)))
        ax.plot(x_positions, values, marker="o", linewidth=2)
        ax.set_title(f"{title_text}\nИтого: {total_text} {symbol}", fontsize=14, pad=16)
        ax.set_ylabel(f"Сумма, {symbol}")
        ax.set_xticks(x_positions)
        ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=9)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        for position, value in zip(x_positions, values):
            ax.text(
                position,
                value,
                f"{value:,.0f}".replace(",", " "),
                ha="center",
                va="bottom",
                fontsize=9,
            )
        fig.tight_layout()
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)

    @staticmethod
    def build_text_answer(
        result: CalculationResult,
        *,
        title: str,
        subtitle: str,
        scope_note: str,
        has_data_in_base_currency: bool,
    ) -> str:
        currency = result.currency
        lines: list[str] = []
        metric = result.metric
        if result.group_by == ASK_GROUP_BY_NONE:
            if metric == ASK_METRIC_COUNT:
                value = f"{result.total_count} операций"
                noun = f"{title.lower()} {subtitle}".strip()
                lines.append(f"Найдено {value} по запросу «{noun}».")
            elif metric == ASK_METRIC_AVG and result.total_count:
                avg = int(round(result.total_minor / result.total_count))
                lines.append(f"Средняя сумма операции: {format_minor(avg, currency)}")
                lines.append(
                    f"Всего за период: {format_minor(result.total_minor, currency)} ({result.total_count} операций)"
                )
            else:
                lines.append(
                    f"{title} {subtitle}: {format_minor(result.total_minor, currency)}"
                )
                if result.total_count:
                    lines.append(f"Всего операций: {result.total_count}")
            if result.change is not None:
                change = result.change.change_percent
                if change is None:
                    lines.append("Во второй половине периода расходов не обнаружено.")
                else:
                    direction = "выросли" if change > 0 else "снизились"
                    lines.append(
                        f"Изменение ко второй половине периода: {abs(change):.1f}% ({direction})."
                    )
        elif result.group_by in {
            ASK_GROUP_BY_CATEGORY,
            ASK_GROUP_BY_CURRENCY,
            ASK_GROUP_BY_SCOPE,
        }:
            lines.append(
                f"{title} {subtitle}: {format_minor(result.total_minor, currency)}"
            )
            top = result.sorted_desc()
            for point in top[:8]:
                share = (
                    (point.total_minor / result.total_minor * 100)
                    if result.total_minor
                    else 0
                )
                lines.append(
                    f"• {point.label} — {format_minor(point.total_minor, currency)} ({share:.1f}%)"
                )
        else:
            lines.append(
                f"{title} {subtitle}: {format_minor(result.total_minor, currency)}"
            )
            for point in result.series:
                lines.append(
                    f"• {point.label} — {format_minor(point.total_minor, currency)}"
                )
        if not has_data_in_base_currency and result.total_count == 0:
            lines = [f"{title} {subtitle}: нет данных в основной валюте {currency}."]
        elif result.total_count == 0:
            lines.append("Данные за период не найдены.")
        if result.unconverted:
            skipped = ", ".join(
                f"{count} в {code}" for code, count in result.unconverted.items()
            )
            lines.append(
                f"⚠️ Часть операций не приведена к {currency} из-за отсутствия сохранённого курса ({skipped})."
            )
        lines.append(f"\nУчтены {scope_note}.")
        return "\n".join(lines)


def _compact_money(amount_minor: int, currency: str) -> str:
    symbol = CURRENCY_SYMBOLS.get(currency, currency)
    whole, fraction = divmod(amount_minor, 100)
    text = f"{whole:,}".replace(",", " ")
    if fraction:
        text = f"{text},{fraction:02d}"
    return f"{text} {symbol}"


def build_list_text(
    rows,
    category_titles: dict[str, str],
    currency: str,
    total_minor: Optional[int],
    unconverted: dict[str, int],
    app_timezone: str,
    limit: int = 60,
    total: Optional[int] = None,
) -> str:
    tz = ZoneInfo(app_timezone)
    count = total if total is not None else len(rows)
    shown = rows[:limit]
    lines = [f"Найдено операций: {count}."]
    for row in shown:
        local_date = row.message_date_utc.astimezone(tz).strftime("%d.%m.%Y")
        category = category_titles.get(row.category, row.category)
        scope_label = "Семейное" if row.scope == "family" else "Личное"
        description = (row.description or "").strip()
        detail = f" — {description}" if description else ""
        lines.append(
            f"{local_date}  {_compact_money(row.amount_minor, row.currency)} · {category}{detail} · {scope_label}"
        )
    if count > len(shown):
        lines.append(f"…и ещё {count - len(shown)} операций.")
    if total_minor is not None and len(shown):
        lines.append(f"Сумма (в {currency}): {format_minor(total_minor, currency)}")
    if unconverted:
        skipped = ", ".join(
            f"{count} в {symbol_for(code)}" for code, count in unconverted.items()
        )
        lines.append(
            f"⚠️ Часть операций не приведена к {currency} из-за отсутствия сохранённого курса ({skipped})."
        )
    return "\n".join(lines)
