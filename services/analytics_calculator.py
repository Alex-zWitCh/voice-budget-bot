from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from schemas import (
    ASK_GROUP_BY_CATEGORY,
    ASK_GROUP_BY_CURRENCY,
    ASK_GROUP_BY_DAY,
    ASK_GROUP_BY_MONTH,
    ASK_GROUP_BY_NONE,
    ASK_GROUP_BY_SCOPE,
    ASK_GROUP_BY_WEEK,
    ASK_METRIC_CHANGE_PERCENT,
    ASK_METRIC_SUM,
    AnalyticsTransaction,
    AskQueryPlan,
)
from services.currency_conversion import build_rate_map, symbol_for, to_base_minor

RUSSIAN_MONTHS = {
    1: "январь",
    2: "февраль",
    3: "март",
    4: "апрель",
    5: "май",
    6: "июнь",
    7: "июль",
    8: "август",
    9: "сентябрь",
    10: "октябрь",
    11: "ноябрь",
    12: "декабрь",
}

SORTED_DESC_GROUP_BY = {
    ASK_GROUP_BY_CATEGORY,
    ASK_GROUP_BY_CURRENCY,
    ASK_GROUP_BY_SCOPE,
}


@dataclass(frozen=True)
class SeriesPoint:
    label: str
    total_minor: int
    count: int

    @property
    def avg_minor(self) -> int:
        if self.count <= 0:
            return 0
        return int(round(self.total_minor / self.count))


@dataclass(frozen=True)
class ChangeSummary:
    first_total_minor: int
    second_total_minor: int
    change_percent: Optional[Decimal]


@dataclass(frozen=True)
class CalculationResult:
    series: list[SeriesPoint]
    total_minor: int
    total_count: int
    currency: str
    unconverted: dict[str, int]
    group_by: str
    metric: str
    min_transaction: Optional[tuple[int, str, str]] = None
    max_transaction: Optional[tuple[int, str, str]] = None
    change: Optional[ChangeSummary] = None

    def bucket_avg_minor(self) -> Optional[int]:
        if not self.series:
            return None
        return int(
            round(sum(point.total_minor for point in self.series) / len(self.series))
        )

    def sorted_desc(self) -> list[SeriesPoint]:
        return sorted(self.series, key=lambda point: point.total_minor, reverse=True)

    def top_share(self) -> Optional[tuple[SeriesPoint, float]]:
        if self.total_minor <= 0 or not self.series:
            return None
        top = max(self.series, key=lambda point: point.total_minor)
        return top, top.total_minor / self.total_minor * 100


@dataclass
class _Bucket:
    label: str
    values: list[int]
    reference_date: datetime


class AnalyticsCalculator:
    def calculate(
        self,
        rows: list[AnalyticsTransaction],
        plan: AskQueryPlan,
        main_currency: str,
        rate_rows: list[tuple[str, str, Decimal]],
        category_titles: dict[str, str],
    ) -> CalculationResult:
        rates = build_rate_map(rate_rows)
        converted = []
        unconverted: dict[str, int] = defaultdict(int)
        for row in rows:
            value = to_base_minor(row, main_currency, rates)
            if value is None:
                unconverted[row.currency] += 1
                continue
            converted.append(
                {
                    "minor": value,
                    "date_utc": row.message_date_utc,
                    "category": row.category,
                    "scope": row.scope,
                    "currency": row.currency,
                }
            )

        metric = plan.metrics[0] if plan.metrics else ASK_METRIC_SUM
        group_by = (
            plan.group_by
            if plan.group_by
            in {
                ASK_GROUP_BY_DAY,
                ASK_GROUP_BY_WEEK,
                ASK_GROUP_BY_MONTH,
                ASK_GROUP_BY_CATEGORY,
                ASK_GROUP_BY_CURRENCY,
                ASK_GROUP_BY_SCOPE,
            }
            else ASK_GROUP_BY_NONE
        )

        series = self._group_series(converted, group_by, category_titles)
        total_minor = sum(point.total_minor for point in series)
        total_count = sum(point.count for point in series)
        min_transaction = self._extremum(converted, minimum=True)
        max_transaction = self._extremum(converted, minimum=False)
        change = None
        if metric == ASK_METRIC_CHANGE_PERCENT:
            change = self._compare_halves(converted, plan)
        return CalculationResult(
            series=series,
            total_minor=total_minor,
            total_count=total_count,
            currency=main_currency,
            unconverted=dict(unconverted),
            group_by=group_by,
            metric=metric,
            min_transaction=min_transaction,
            max_transaction=max_transaction,
            change=change,
        )

    def _group_series(
        self, converted: list[dict], group_by: str, category_titles: dict[str, str]
    ) -> list[SeriesPoint]:
        if not converted:
            return []
        if group_by == ASK_GROUP_BY_NONE:
            total = sum(item["minor"] for item in converted)
            return [SeriesPoint(label="Всего", total_minor=total, count=len(converted))]

        buckets: dict[str, _Bucket] = {}
        for item in converted:
            key, label = self._bucket_key(item, group_by, category_titles)
            bucket = buckets.get(key)
            if bucket is None:
                bucket = _Bucket(
                    label=label, values=[], reference_date=item["date_utc"]
                )
                buckets[key] = bucket
            bucket.values.append(item["minor"])

        keys = self._sorted_keys(buckets, group_by)
        return [
            SeriesPoint(
                label=buckets[key].label,
                total_minor=sum(buckets[key].values),
                count=len(buckets[key].values),
            )
            for key in keys
            if buckets[key].values
        ]

    @staticmethod
    def _bucket_key(
        item: dict, group_by: str, category_titles: dict[str, str]
    ) -> tuple[str, str]:
        if group_by == ASK_GROUP_BY_MONTH:
            date_utc = item["date_utc"]
            return (
                f"{date_utc.year}-{date_utc.month:02d}",
                f"{RUSSIAN_MONTHS[date_utc.month]} {date_utc.year}",
            )
        if group_by == ASK_GROUP_BY_DAY:
            date_utc = item["date_utc"]
            return date_utc.date().isoformat(), date_utc.strftime("%d.%m.%Y")
        if group_by == ASK_GROUP_BY_WEEK:
            iso = item["date_utc"].isocalendar()
            key = f"{iso[0]}-W{iso[1]:02d}"
            return key, f"нед. {iso[1]:02d}"
        if group_by == ASK_GROUP_BY_CURRENCY:
            code = item["currency"]
            return code, f"{code} ({symbol_for(code)})"
        if group_by == ASK_GROUP_BY_SCOPE:
            scope = item["scope"]
            return scope, "Семейные" if scope == "family" else "Личные"
        code = item["category"]
        return code, category_titles.get(code, code)

    @staticmethod
    def _sorted_keys(buckets: dict[str, _Bucket], group_by: str) -> list[str]:
        if group_by in SORTED_DESC_GROUP_BY:
            return sorted(
                buckets, key=lambda key: sum(buckets[key].values), reverse=True
            )
        return sorted(buckets, key=lambda key: buckets[key].reference_date)

    @staticmethod
    def _extremum(
        converted: list[dict], minimum: bool
    ) -> Optional[tuple[int, str, str]]:
        if not converted:
            return None
        target = min if minimum else max
        best = target(converted, key=lambda item: item["minor"])
        return best["minor"], best["category"], best["date_utc"].date().isoformat()

    @staticmethod
    def _compare_halves(
        converted: list[dict], plan: AskQueryPlan
    ) -> Optional[ChangeSummary]:
        start = plan.date_from_utc
        end = plan.date_to_utc
        if start is None or end is None or end <= start:
            return None
        midpoint = start + (end - start) / 2
        first_total = sum(
            item["minor"] for item in converted if item["date_utc"] < midpoint
        )
        second_total = sum(
            item["minor"] for item in converted if item["date_utc"] >= midpoint
        )
        if first_total == 0:
            return ChangeSummary(first_total, second_total, None)
        change = (
            (Decimal(second_total) - Decimal(first_total)) / Decimal(first_total) * 100
        )
        return ChangeSummary(first_total, second_total, change)
