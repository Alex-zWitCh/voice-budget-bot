from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from categories import SUPPORTED_CURRENCIES
from schemas import (
    ASK_GROUP_BY_CATEGORY,
    ASK_GROUP_BY_DAY,
    ASK_GROUP_BY_MONTH,
    ASK_GROUP_BY_NONE,
    ASK_GROUP_BY_VALUES,
    ASK_GROUP_BY_WEEK,
    ASK_METRIC_AVG,
    ASK_METRIC_COUNT,
    ASK_METRIC_SUM,
    ASK_METRIC_VALUES,
    ASK_OUTPUT_AUTO,
    ASK_OUTPUT_INFOGRAPHIC,
    ASK_OUTPUT_TEXT,
    ASK_OUTPUT_PREFERENCE_VALUES,
    ASK_SCOPE_ACCESSIBLE,
    AskQueryPlan,
)
from services.ask_llm import AskLLMClient, AskLLMError

RUSSIAN_MONTH_RE = re.compile(
    r"(январ\w*|феврал\w*|март\w*|апрел\w*|ма[йя]\b|июн\w*|июл\w*|август\w*|сентябр\w*|октябр\w*|ноябр\w*|декабр\w*)"
)

RUSSIAN_MONTH_PREFIXES = [
    ("январ", 1),
    ("феврал", 2),
    ("март", 3),
    ("апрел", 4),
    ("ма", 5),
    ("июн", 6),
    ("июл", 7),
    ("август", 8),
    ("сентябр", 9),
    ("октябр", 10),
    ("ноябр", 11),
    ("декабр", 12),
]

_NUMBER_WORDS = {
    "один": 1,
    "одна": 1,
    "одну": 1,
    "два": 2,
    "две": 2,
    "три": 3,
    "четыре": 4,
    "пять": 5,
    "шесть": 6,
    "семь": 7,
    "восемь": 8,
    "девять": 9,
    "десять": 10,
    "одиннадцать": 11,
    "двенадцать": 12,
}

_CURRENCY_ALIASES = {
    "rub": "RUB",
    "руб": "RUB",
    "рубл": "RUB",
    "₽": "RUB",
    "usd": "USD",
    "доллар": "USD",
    "бакс": "USD",
    "$": "USD",
    "eur": "EUR",
    "евро": "EUR",
    "€": "EUR",
    "gbp": "GBP",
    "фунт": "GBP",
    "£": "GBP",
    "cny": "CNY",
    "юан": "CNY",
    "¥": "CNY",
    "uzs": "UZS",
    "сум": "UZS",
    "kzt": "KZT",
    "тенге": "KZT",
    "₸": "KZT",
    "amd": "AMD",
    "драм": "AMD",
    "֏": "AMD",
}

_CATEGORY_KEYWORDS = {
    "CAFE": ["кафе", "ресторан", "кофейн", "бар", "столов"],
    "PRODUCTS": [
        "продукт",
        "продуктов",
        "супермаркет",
        "бакале",
        "рынок",
        "магазин продукт",
        "продовольств",
    ],
    "ALCOHOL": ["алкогол", "пиво", "вино", "водк", "коньяк", "виски", "коктейл"],
    "TRANSPORT": [
        "транспорт",
        "метро",
        "автобус",
        "проезд",
        "трамвай",
        "такси",
        "электричк",
    ],
    "CAR": [
        "бензин",
        "топлив",
        "заправк",
        "авто",
        "машина",
        "автосервис",
        "гараж",
        "стоянк",
    ],
    "HOUSING": [
        "жиль",
        "аренд",
        "квартплат",
        "коммунал",
        "ремонт квартир",
        "ипотек",
        "коммунальн",
    ],
    "HEALTH": [
        "здоров",
        "лекарств",
        "аптек",
        "больниц",
        "врач",
        "стоматолог",
        "анализ",
    ],
    "CLOTHING": ["одежд", "обув", "куртк", "пальто", "плать", "рубашк", "костюм"],
    "CHILDREN": ["дети", "ребенк", "ребёнк", "детск", "игрушк", "подгузник"],
    "ENTERTAINMENT": [
        "развлечен",
        "кино",
        "концерт",
        "клуб",
        "хобби",
        "музе",
        "театр",
        "спортзал",
    ],
    "SUBSCRIPTIONS": [
        "подписк",
        "интернет",
        "связь",
        "тариф",
        "мобильн",
        "оператор",
        "подписки",
    ],
    "ELECTRONICS": [
        "техник",
        "электрон",
        "ноутбук",
        "телефон",
        "компьютер",
        "гаджет",
        "планшет",
        "наушник",
    ],
    "EDUCATION": ["образован", "курс", "университет", "обучен", "репетитор", "школ"],
    "GIFTS": ["подарк", "цветы", "поздравлен"],
    "TRANSFERS": ["перевод", "перевёл", "перевел", "перевести"],
    "TRAVEL": [
        "путешеств",
        "отель",
        "гостиниц",
        "авиабилет",
        "самолет",
        "билет",
        "отпуск",
        "поездк",
        "виза",
        "перелет",
    ],
    "SALARY": ["зарплат", "оклад", "аванс"],
    "FREELANCE": ["фриланс", "подработк", "заказ"],
    "BUSINESS": ["бизнес", "продажи", "выручк"],
    "BENEFITS": ["пособи"],
    "PENSION": ["пенси"],
    "REFUND": ["возврат", "вернули", "возмещен"],
    "GIFTS_RECEIVED": ["подарок получил", "подарили", "презент"],
    "SALE": ["продаж", "продал", "продала"],
    "INVESTMENT_INCOME": ["инвестиц", "дивиденд", "акци", "купон"],
}

_INCOME_MARKERS = [
    "доход",
    "зарплат",
    "получил",
    "получила",
    "пришло",
    "заработал",
    "заработала",
    "премия",
    "выручк",
    "продал",
    "продала",
]
_EXPENSE_MARKERS = [
    "расход",
    "трат",
    "потратил",
    "потратила",
    "купил",
    "купила",
    "заплатил",
    "заплатила",
    "оплат",
    "списал",
    "счет",
]

_GROUP_TIME_WORDS = [
    "динамик",
    "по месяцам",
    "помесячн",
    "по неделям",
    "еженедельн",
    "по дням",
    "ежедневн",
    "тренд",
    "график по",
]
_GROUP_CATEGORY_WORDS = [
    "по категори",
    "по категориям",
    "на что",
    "структур",
    "распределен",
    "категориям",
    "категориями",
]
_GROUP_CURRENCY_WORDS = ["по валютам", "по валюте", "по курсам", "в валютах"]

_RELATIVE_NUMERIC_RE = re.compile(
    r"(\d+)\s*(дн\w*|недел\w*|месяц\w*|год\w*|лет\w*|мес\w*)"
)
_RELATIVE_WORD_RE = re.compile(
    r"(?:за\s+)?(?:последни\w+|прошл\w+)?\s*(одн\w*|дв\w*|три|четыр\w*|пять|шесть|семь|восемь|девять|десять|одиннадцать|двенадцать)\s*(дн\w*|недел\w*|месяц\w*|год\w*|лет\w*)"
)


def _month_number(text: str) -> Optional[int]:
    match = RUSSIAN_MONTH_RE.search(text)
    if not match:
        return None
    word = match.group(0)
    for prefix, number in RUSSIAN_MONTH_PREFIXES:
        if word.startswith(prefix):
            return number
    return None


def _add_months_local(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, _month_days(year, month))
    return value.replace(year=year, month=month, day=day)


def _month_days(year: int, month: int) -> int:
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)
    return (next_month - datetime(year, month, 1)).days


def _start_of_next_month(value: datetime) -> datetime:
    return _add_months_local(value.replace(day=1), 1)


def _detect_type(text: str) -> Optional[str]:
    income_hits = sum(1 for marker in _INCOME_MARKERS if marker in text)
    expense_hits = sum(1 for marker in _EXPENSE_MARKERS if marker in text)
    if expense_hits and not income_hits:
        return "EXPENSE"
    if income_hits and not expense_hits:
        return "INCOME"
    if income_hits and expense_hits:
        return None
    return None


def _detect_currencies(text: str) -> list[str]:
    found = []
    lowered = text.lower()
    for alias, code in _CURRENCY_ALIASES.items():
        if alias in lowered and code not in found:
            found.append(code)
    return found


def _detect_categories(
    text: str, catalog: dict[str, dict[str, str]], detected_type: Optional[str]
) -> list[str]:
    lowered = text.lower()
    candidates: dict[str, str] = {}
    for transaction_type, entries in catalog.items():
        for code, title in entries.items():
            title_lower = title.lower()
            if len(title_lower) >= 4 and title_lower in lowered:
                candidates[code] = transaction_type
            for keyword in _CATEGORY_KEYWORDS.get(code, []):
                if keyword in lowered:
                    candidates[code] = transaction_type
    if not candidates:
        return []
    if detected_type == "EXPENSE":
        return [
            code
            for code, transaction_type in candidates.items()
            if transaction_type == "EXPENSE"
        ][:5]
    if detected_type == "INCOME":
        return [
            code
            for code, transaction_type in candidates.items()
            if transaction_type == "INCOME"
        ][:5]
    expense_codes = [
        code
        for code, transaction_type in candidates.items()
        if transaction_type == "EXPENSE"
    ]
    if expense_codes and len(expense_codes) == len(candidates):
        return expense_codes[:5]
    return list(candidates)[:5]


class AskPlanner:
    def __init__(
        self,
        llm_client: Optional[AskLLMClient] = None,
        app_timezone: str = "Europe/Moscow",
        now_provider=None,
    ):
        self.llm_client = llm_client
        self.app_timezone = app_timezone
        self._now_provider = now_provider

    def plan(
        self,
        question: str,
        category_catalog: dict[str, dict[str, str]],
        main_currency: str,
    ) -> AskQueryPlan:
        now_local = self._now()
        if self.llm_client is not None:
            try:
                raw = self._llm_raw_plan(
                    question, category_catalog, main_currency, now_local
                )
                return self._validate_plan(raw, category_catalog, now_local)
            except (AskLLMError, ValueError):
                pass
        return self._deterministic_plan(question, category_catalog, now_local)

    def _now(self) -> datetime:
        if self._now_provider is not None:
            return self._now_provider()
        return datetime.now(ZoneInfo(self.app_timezone))

    # ---- deterministic ----

    def _deterministic_plan(
        self,
        question: str,
        category_catalog: dict[str, dict[str, str]],
        now_local: datetime,
    ) -> AskQueryPlan:
        text = (question or "").lower().strip()
        transaction_type = _detect_type(text)
        currencies = _detect_currencies(text)
        categories = _detect_categories(text, category_catalog, transaction_type)
        date_from, date_to = self._detect_period(text, now_local)
        group_by = self._detect_group_by(text)
        if transaction_type is None and categories:
            type_of_categories = {
                entry_type
                for entry_type, entries in category_catalog.items()
                for code in categories
                if code in entries
            }
            if len(type_of_categories) == 1:
                transaction_type = next(iter(type_of_categories))
        metrics = self._detect_metrics(text)
        output_preference = self._detect_output(text)
        semantic_filter_required = (
            "включая" in text
            or "связанн" in text
            or "в ереван" in text
            or "ереване" in text
        )
        return AskQueryPlan(
            transaction_type=transaction_type,
            data_scope=ASK_SCOPE_ACCESSIBLE,
            date_from_utc=self._to_utc(date_from) if date_from else None,
            date_to_utc=self._to_utc(date_to) if date_to else None,
            categories=tuple(categories),
            currencies=tuple(currencies),
            group_by=group_by,
            metrics=tuple(metrics),
            semantic_filter_required=semantic_filter_required,
            output_preference=output_preference,
        )

    def _detect_period(
        self, text: str, now_local: datetime
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        today = now_local.date()
        if (
            "за всё время" in text
            or "за все время" in text
            or "всё время" in text
            or "за всю историю" in text
        ):
            return None, None
        if "этот месяц" in text or "в этом месяце" in text:
            start = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return start, _start_of_next_month(start)
        if "прошлый месяц" in text or "прошлом месяце" in text:
            start = _add_months_local(
                now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0), -1
            )
            return start, _start_of_next_month(start)
        if "вчера" in text:
            start = datetime.combine(today - timedelta(days=1), datetime.min.time())
            return start, start + timedelta(days=1)
        if "сегодня" in text or "сегодняшн" in text:
            start = datetime.combine(today, datetime.min.time())
            return start, start + timedelta(days=1)

        numeric = _RELATIVE_NUMERIC_RE.search(text)
        word_match = None
        if not numeric:
            word_match = _RELATIVE_WORD_RE.search(text)
        relative = numeric or word_match
        if relative:
            if numeric:
                count = int(numeric.group(1))
                unit = numeric.group(2)
            else:
                word = word_match.group(1)
                count = _NUMBER_WORDS.get(word, 1)
                unit = word_match.group(2)
            return self._relative_range(count, unit, now_local)

        month = _month_number(text)
        if month is not None:
            year = now_local.year if month <= now_local.month else now_local.year - 1
            start = datetime(year, month, 1)
            return start, _start_of_next_month(start)

        if re.search(r"\bгод\b", text) or " за год" in text or "за 12 месяцев" in text:
            current_start = now_local.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            start = _add_months_local(current_start, -11)
            return start, _start_of_next_month(current_start)
        return None, None

    @staticmethod
    def _relative_range(
        count: int, unit: str, now_local: datetime
    ) -> tuple[datetime, datetime]:
        today = now_local.date()
        if unit.startswith("недел"):
            start = datetime.combine(
                today - timedelta(days=count * 7 - 1), datetime.min.time()
            )
            return start, datetime.combine(
                today + timedelta(days=1), datetime.min.time()
            )
        if unit.startswith("дн"):
            start = datetime.combine(
                today - timedelta(days=count - 1), datetime.min.time()
            )
            return start, datetime.combine(
                today + timedelta(days=1), datetime.min.time()
            )
        if unit.startswith("месяц") or unit.startswith("мес"):
            current_start = now_local.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            start = _add_months_local(current_start, -(count - 1))
            return start, _start_of_next_month(current_start)
        if unit.startswith("год") or unit.startswith("лет"):
            current_start = now_local.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            start = _add_months_local(current_start, -(count * 12 - 1))
            return start, _start_of_next_month(current_start)
        return None, None

    @staticmethod
    def _detect_group_by(text: str) -> str:
        if any(word in text for word in _GROUP_CURRENCY_WORDS):
            return "CURRENCY"
        if any(word in text for word in _GROUP_CATEGORY_WORDS):
            return ASK_GROUP_BY_CATEGORY
        if "по неделям" in text or "еженедельн" in text:
            return ASK_GROUP_BY_WEEK
        if "по дням" in text or "ежедневн" in text or "по дням" in text:
            return ASK_GROUP_BY_DAY
        if any(word in text for word in _GROUP_TIME_WORDS):
            return ASK_GROUP_BY_MONTH
        return ASK_GROUP_BY_NONE

    @staticmethod
    def _detect_metrics(text: str) -> list[str]:
        if "в среднем" in text or "средне" in text or "средний чек" in text:
            return [ASK_METRIC_AVG]
        if (
            "сколько раз" in text
            or "количество операций" in text
            or "сколько операций" in text
        ):
            return [ASK_METRIC_COUNT]
        if "доля" in text or "какой процент" in text or "какая доля" in text:
            return [ASK_METRIC_SUM, "SHARE"]
        return [ASK_METRIC_SUM]

    @staticmethod
    def _detect_output(text: str) -> str:
        if any(
            word in text
            for word in (
                "график",
                "графиком",
                "наглядно",
                "инфографик",
                "диаграмм",
                "покажи динамик",
            )
        ):
            return ASK_OUTPUT_INFOGRAPHIC
        if any(
            word in text
            for word in ("текстом", "только текст", "кратко", "списком", "числом")
        ):
            return ASK_OUTPUT_TEXT
        return ASK_OUTPUT_AUTO

    def _to_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=ZoneInfo(self.app_timezone))
        return value.astimezone(timezone.utc)

    # ---- llm ----

    def _llm_raw_plan(
        self,
        question: str,
        category_catalog: dict[str, dict[str, str]],
        main_currency: str,
        now_local: datetime,
    ) -> dict:
        system = (
            "Ты строишь read-only аналитический запрос к финансовым записям бюджета.\n"
            "Пользователь задаёт вопрос про свои траты/доходы. Твоя задача — вернуть JSON-план выборки.\n\n"
            "Допустимые значения:\n"
            '- "transaction_type": "EXPENSE" | "INCOME" | null\n'
            '- "data_scope": "ACCESSIBLE" | "PERSONAL" | "FAMILY" | "MY_PAYMENTS"\n'
            '- "date_from": "YYYY-MM-DD" | null  (начало периода, включительно, в локальном времени)\n'
            '- "date_to": "YYYY-MM-DD" | null  (конец периода, включительно, в локальном времени)\n'
            '- "categories": [коды категорий] | []\n'
            '- "currencies": [валюты] | []\n'
            '- "text_terms": [слова для поиска в описании] | [] (до 3 коротких слов)\n'
            f'- "group_by": одно из {list(ASK_GROUP_BY_VALUES)}\n'
            f'- "metrics": массив из {list(ASK_METRIC_VALUES)} (обычно ["SUM"])\n'
            '- "semantic_filter_required": boolean (true, если ответ нельзя получить одним фильтром '
            "по категориям/периоду и нужна ручная выборка по смыслу, например «все расходы на сделку с недвижимостью»)\n"
            f'- "output_preference": одно из {list(ASK_OUTPUT_PREFERENCE_VALUES)}\n\n'
            "Запрещено возвращать: telegram_user_id, family_id, любые служебные идентификаторы, SQL.\n"
            "Считай локальную дату и время сам от текущего момента.\n"
            'Если вопрос не про анализ личных данных, верни план с пустыми полями и output_preference="TEXT".'
        )
        catalog_lines = []
        for transaction_type, entries in category_catalog.items():
            for code, title in entries.items():
                catalog_lines.append(f"{code} — {title} ({transaction_type})")
        user = (
            f"Текущее локальное время: {now_local:%Y-%m-%d %H:%M}, таймзона {self.app_timezone}.\n"
            f"Основная валюта: {main_currency}.\n"
            f"Доступные валюты: {', '.join(sorted(SUPPORTED_CURRENCIES))}.\n"
            f"Каталог категорий:\n{chr(10).join(catalog_lines)}\n\n"
            f"Вопрос пользователя:\n{question}\n\n"
            "Верни только JSON по схеме выше."
        )
        return self.llm_client.chat_json(system, user)

    def _validate_plan(
        self,
        raw: dict,
        category_catalog: dict[str, dict[str, str]],
        now_local: datetime,
    ) -> AskQueryPlan:
        transaction_type = str(raw.get("transaction_type") or "").upper() or None
        if transaction_type not in (None, "EXPENSE", "INCOME"):
            transaction_type = None
        allowed_codes = set()
        for entries in category_catalog.values():
            allowed_codes.update(entries)
        categories = []
        for code in raw.get("categories") or []:
            normalized = str(code).upper()
            if normalized in allowed_codes and normalized not in categories:
                categories.append(normalized)
        currencies = []
        for code in raw.get("currencies") or []:
            normalized = str(code).upper()
            if normalized in SUPPORTED_CURRENCIES and normalized not in currencies:
                currencies.append(normalized)
        date_from = self._validate_date(raw.get("date_from"))
        date_to = self._validate_date(raw.get("date_to"))
        group_by = str(raw.get("group_by") or ASK_GROUP_BY_NONE).upper()
        if group_by not in ASK_GROUP_BY_VALUES:
            group_by = ASK_GROUP_BY_NONE
        metrics = [
            str(metric).upper() for metric in (raw.get("metrics") or [ASK_METRIC_SUM])
        ]
        metrics = [metric for metric in metrics if metric in ASK_METRIC_VALUES] or [
            ASK_METRIC_SUM
        ]
        output_preference = str(raw.get("output_preference") or ASK_OUTPUT_AUTO).upper()
        if output_preference not in ASK_OUTPUT_PREFERENCE_VALUES:
            output_preference = ASK_OUTPUT_AUTO
        data_scope = str(raw.get("data_scope") or ASK_SCOPE_ACCESSIBLE).upper()
        if data_scope not in {"ACCESSIBLE", "PERSONAL", "FAMILY", "MY_PAYMENTS"}:
            data_scope = ASK_SCOPE_ACCESSIBLE
        text_terms = [
            str(term).strip()[:80]
            for term in (raw.get("text_terms") or [])
            if str(term).strip()
        ]
        return AskQueryPlan(
            transaction_type=transaction_type,
            data_scope=data_scope,
            date_from_utc=self._date_to_utc(date_from) if date_from else None,
            date_to_utc=self._date_to_utc(date_to, exclusive=True) if date_to else None,
            categories=tuple(categories),
            currencies=tuple(currencies),
            text_terms=tuple(text_terms[:3]),
            group_by=group_by,
            metrics=tuple(metrics[:3]),
            semantic_filter_required=bool(raw.get("semantic_filter_required")),
            output_preference=output_preference,
        )

    @staticmethod
    def _validate_date(value) -> Optional[datetime]:
        if not value:
            return None
        text = str(value).strip()
        match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
        if not match:
            return None
        year, month, day = (int(part) for part in match.groups())
        try:
            return datetime(year, month, day)
        except ValueError:
            return None

    def _date_to_utc(self, value: datetime, exclusive: bool = False) -> datetime:
        if exclusive:
            value = value + timedelta(days=1)
        return self._to_utc(value)
