from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal, Optional, Union
from zoneinfo import ZoneInfo

from categories import CATEGORY_BY_TYPE, SUPPORTED_CURRENCIES


class ValidationError(Exception):
    def __init__(self, code: str, user_message: str):
        super().__init__(code)
        self.code = code
        self.user_message = user_message


@dataclass(frozen=True)
class ParsedTransaction:
    transaction_type: str
    amount_minor: int
    currency: str
    category: str
    description: str
    confidence: float


@dataclass(frozen=True)
class ParsedScheduledEvent:
    event_type: str
    title: str
    notify_at_utc: datetime
    event_at_utc: datetime
    recurrence: str
    confidence: float
    transaction: Optional[ParsedTransaction] = None


@dataclass(frozen=True)
class ParsedExchange:
    from_amount_minor: int
    from_currency: str
    to_currency: str
    to_amount_minor: Optional[int]
    rate: Optional[Decimal]
    description: str
    confidence: float

    def with_rate(self, rate: Decimal) -> "ParsedExchange":
        to_amount_minor = int(round(self.from_amount_minor * rate)) if rate else None
        return replace(self, rate=rate, to_amount_minor=to_amount_minor)


def _parse_rate(value: object) -> Optional[Decimal]:
    if value is None:
        return None
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    try:
        rate = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if rate <= 0:
        return None
    return rate


def amount_to_minor(amount: Union[str, int, float, Decimal], currency: str = "RUB") -> int:
    try:
        normalized = str(amount).replace(" ", "").replace("\u00a0", "").replace(",", ".")
        decimal_amount = Decimal(normalized).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError("parse_failed", "⚠️ Не удалось определить сумму операции.") from exc
    if decimal_amount <= 0:
        raise ValidationError("parse_failed", "⚠️ Не удалось определить сумму операции.")
    return int(decimal_amount * 100)


def validate_deepseek_payload(
    payload: dict,
    transcript: str,
    min_confidence: float,
    category_catalog: Optional[dict] = None,
) -> ParsedTransaction:
    category_catalog = category_catalog or CATEGORY_BY_TYPE
    if not transcript.strip():
        raise ValidationError("transcription_failed", "⚠️ Речь не распознана.\nПовторите сообщение немного громче и короче.")
    if not payload.get("is_financial_record"):
        raise ValidationError(
            "rejected_not_financial",
            "⚠️ Не удалось определить сумму операции.\n"
            "Примеры: «тысяча двести продукты» или «получил зарплату сто тысяч».\n"
            "Если это конвертация валюты, называйте обе валюты и суммы: «поменял 35 000 рублей на 150 000 армянских драм».",
        )
    if payload.get("is_multiple"):
        raise ValidationError(
            "rejected_multiple",
            "⚠️ В сообщении обнаружено несколько финансовых операций.\nОтправляйте каждую операцию отдельным голосовым сообщением.",
        )

    transaction_type = str(payload.get("transaction_type", "UNKNOWN")).upper()
    if transaction_type not in {"EXPENSE", "INCOME"}:
        raise ValidationError(
            "rejected_unknown_type",
            "⚠️ Не удалось понять, это доход или расход.\nСформулируйте действие явно: «заплатил», «купил», «получил» или «вернули».",
        )

    try:
        confidence = float(payload.get("confidence", 0))
    except (TypeError, ValueError) as exc:
        raise ValidationError("parse_failed", "⚠️ Не удалось разобрать ответ сервиса распознавания.") from exc
    if confidence < min_confidence:
        raise ValidationError("rejected_low_confidence", "⚠️ Не удалось уверенно распознать операцию.\nПовторите запись чуть яснее.")

    currency = str(payload.get("currency") or "RUB").upper()
    if currency not in SUPPORTED_CURRENCIES:
        currency = "RUB"

    category = str(payload.get("category") or "OTHER").upper()
    if category not in category_catalog[transaction_type]:
        category = "OTHER"

    description = str(payload.get("description") or "").strip()
    amount_minor = amount_to_minor(payload.get("amount", ""), currency)

    return ParsedTransaction(
        transaction_type=transaction_type,
        amount_minor=amount_minor,
        currency=currency,
        category=category,
        description=description[:500],
        confidence=confidence,
    )


def validate_exchange_payload(
    payload: dict,
    transcript: str,
    min_confidence: float,
    category_catalog: Optional[dict] = None,
) -> ParsedExchange:
    if not transcript.strip():
        raise ValidationError("transcription_failed", "⚠️ Речь не распознана.\nПовторите сообщение немного громче и короче.")
    if not payload.get("is_financial_record"):
        raise ValidationError(
            "rejected_not_financial",
            "⚠️ Не удалось определить конвертацию: назовите обе валюты и сумму в целевой валюте.\n"
            "Пример: «поменял 35 000 рублей на 150 000 армянских драм» или «перевёл 2000 долларов в рубли по курсу 92».",
        )
    if payload.get("is_multiple"):
        raise ValidationError(
            "rejected_multiple",
            "⚠️ В сообщении обнаружено несколько операций.\nОтправляйте каждую операцию отдельным сообщением.",
        )

    try:
        confidence = float(payload.get("confidence", 0))
    except (TypeError, ValueError) as exc:
        raise ValidationError("parse_failed", "⚠️ Не удалось разобрать ответ сервиса распознавания.") from exc
    if confidence < min_confidence:
        raise ValidationError("rejected_low_confidence", "⚠️ Не удалось уверенно распознать операцию.\nПовторите запись чуть яснее.")

    from_currency = str(payload.get("from_currency") or "").upper()
    to_currency = str(payload.get("to_currency") or "").upper()
    if from_currency not in SUPPORTED_CURRENCIES or to_currency not in SUPPORTED_CURRENCIES:
        raise ValidationError("parse_failed", "⚠️ Не удалось определить валюты конвертации.")
    if from_currency == to_currency:
        raise ValidationError("rejected_same_currency", "⚠️ Валюты должны отличаться.\nЭто не конвертация, а перевод.")

    from_amount_minor = amount_to_minor(payload.get("from_amount", ""), from_currency)
    rate = _parse_rate(payload.get("rate"))
    to_amount_minor = None
    if rate is not None:
        to_amount_minor = int(round(from_amount_minor * rate))
    else:
        to_amount_text = payload.get("to_amount")
        if to_amount_text not in (None, ""):
            to_amount_minor = amount_to_minor(to_amount_text, to_currency)
            rate = Decimal(to_amount_minor) / Decimal(from_amount_minor)
    description = str(payload.get("description") or "").strip()

    return ParsedExchange(
        from_amount_minor=from_amount_minor,
        from_currency=from_currency,
        to_currency=to_currency,
        to_amount_minor=to_amount_minor,
        rate=rate,
        description=description[:500],
        confidence=confidence,
    )


def validate_voice_intent(
    payload: dict,
    transcript: str,
    min_confidence: float,
    category_catalog: Optional[dict],
    app_timezone: str,
) -> Union[ParsedTransaction, ParsedScheduledEvent]:
    action_type = str(payload.get("action_type") or "IMMEDIATE_TRANSACTION").upper()
    if action_type == "EXCHANGE":
        return validate_exchange_payload(payload, transcript, min_confidence, category_catalog)
    if action_type == "IMMEDIATE_TRANSACTION":
        return validate_deepseek_payload(payload, transcript, min_confidence, category_catalog)
    if action_type == "DEFERRED_EXPENSE":
        transaction = validate_deepseek_payload(_transaction_payload(payload), transcript, min_confidence, category_catalog)
        if transaction.transaction_type != "EXPENSE":
            raise ValidationError("parse_failed", "⚠️ Отложенным списанием может быть только расход.")
        event_at = _parse_local_datetime(payload.get("event_at"), app_timezone)
        notify_at = _parse_local_datetime(payload.get("notify_at") or payload.get("event_at"), app_timezone)
        return ParsedScheduledEvent(
            event_type="DEFERRED_EXPENSE",
            title=str(payload.get("title") or transaction.description or "отложенное списание")[:500],
            notify_at_utc=notify_at,
            event_at_utc=event_at,
            recurrence=_normalize_recurrence(payload.get("recurrence")),
            confidence=transaction.confidence,
            transaction=transaction,
        )
    if action_type == "REMINDER":
        confidence = _confidence(payload)
        if confidence < min_confidence:
            raise ValidationError("rejected_low_confidence", "⚠️ Не удалось уверенно распознать напоминание.\nПовторите запись чуть яснее.")
        event_at = _parse_local_datetime(payload.get("event_at"), app_timezone)
        notify_at = _parse_local_datetime(payload.get("notify_at") or payload.get("event_at"), app_timezone)
        title = str(payload.get("title") or payload.get("description") or "").strip()
        if not title:
            raise ValidationError("parse_failed", "⚠️ Не удалось определить текст напоминания.")
        return ParsedScheduledEvent(
            event_type="REMINDER",
            title=title[:500],
            notify_at_utc=notify_at,
            event_at_utc=event_at,
            recurrence=_normalize_recurrence(payload.get("recurrence")),
            confidence=confidence,
        )
    raise ValidationError("parse_failed", "⚠️ Не удалось понять: это операция, отложенное списание или напоминание.")


def _transaction_payload(payload: dict) -> dict:
    return {
        "is_financial_record": payload.get("is_financial_record", True),
        "is_multiple": payload.get("is_multiple", False),
        "transaction_type": payload.get("transaction_type", "EXPENSE"),
        "amount": payload.get("amount"),
        "currency": payload.get("currency"),
        "category": payload.get("category"),
        "description": payload.get("description") or payload.get("title"),
        "confidence": payload.get("confidence"),
    }


def _confidence(payload: dict) -> float:
    try:
        return float(payload.get("confidence", 0))
    except (TypeError, ValueError) as exc:
        raise ValidationError("parse_failed", "⚠️ Не удалось разобрать ответ сервиса распознавания.") from exc


def _parse_local_datetime(value: object, app_timezone: str) -> datetime:
    if not value:
        raise ValidationError("parse_failed", "⚠️ Не удалось определить дату события.")
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValidationError("parse_failed", "⚠️ Не удалось разобрать дату события.") from exc
    tz = ZoneInfo(app_timezone)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    else:
        parsed = parsed.astimezone(tz)
    return parsed.astimezone(timezone.utc)


def _normalize_recurrence(value: object) -> str:
    recurrence = str(value or "none").lower()
    if recurrence in {"daily", "weekly", "monthly", "yearly"}:
        return recurrence
    return "none"


def default_notify_at(event_at_utc: datetime, time_was_specified: bool) -> datetime:
    if time_was_specified:
        return event_at_utc - timedelta(minutes=30)
    return event_at_utc


# ---- /ask read-only analytics ----

ASK_SCOPE_PERSONAL = "PERSONAL"
ASK_SCOPE_FAMILY = "FAMILY"
ASK_SCOPE_ACCESSIBLE = "ACCESSIBLE"
ASK_SCOPE_MY_PAYMENTS = "MY_PAYMENTS"
ASK_SCOPES = (ASK_SCOPE_PERSONAL, ASK_SCOPE_FAMILY, ASK_SCOPE_ACCESSIBLE, ASK_SCOPE_MY_PAYMENTS)

ASK_GROUP_BY_NONE = "NONE"
ASK_GROUP_BY_DAY = "DAY"
ASK_GROUP_BY_WEEK = "WEEK"
ASK_GROUP_BY_MONTH = "MONTH"
ASK_GROUP_BY_CATEGORY = "CATEGORY"
ASK_GROUP_BY_CURRENCY = "CURRENCY"
ASK_GROUP_BY_SCOPE = "SCOPE"
ASK_GROUP_BY_VALUES = (ASK_GROUP_BY_NONE, ASK_GROUP_BY_DAY, ASK_GROUP_BY_WEEK, ASK_GROUP_BY_MONTH, ASK_GROUP_BY_CATEGORY, ASK_GROUP_BY_CURRENCY, ASK_GROUP_BY_SCOPE)

ASK_METRIC_SUM = "SUM"
ASK_METRIC_AVG = "AVG"
ASK_METRIC_COUNT = "COUNT"
ASK_METRIC_MIN = "MIN"
ASK_METRIC_MAX = "MAX"
ASK_METRIC_SHARE = "SHARE"
ASK_METRIC_CHANGE_PERCENT = "CHANGE_PERCENT"
ASK_METRIC_VALUES = (ASK_METRIC_SUM, ASK_METRIC_AVG, ASK_METRIC_COUNT, ASK_METRIC_MIN, ASK_METRIC_MAX, ASK_METRIC_SHARE, ASK_METRIC_CHANGE_PERCENT)

ASK_OUTPUT_AUTO = "AUTO"
ASK_OUTPUT_TEXT = "TEXT"
ASK_OUTPUT_INFOGRAPHIC = "INFOGRAPHIC"
ASK_OUTPUT_PREFERENCE_VALUES = (ASK_OUTPUT_AUTO, ASK_OUTPUT_TEXT, ASK_OUTPUT_INFOGRAPHIC)


@dataclass(frozen=True)
class AskAccessScope:
    telegram_user_id: int
    family_id: Optional[int] = None


@dataclass(frozen=True)
class AnalyticsTransaction:
    id: int
    transaction_type: str
    amount_minor: int
    currency: str
    category: str
    description: str
    transcript: str
    message_date_utc: datetime
    scope: str
    paid_by_current_user: bool
    exchange_rate: Optional[Decimal] = None
    from_currency: Optional[str] = None
    from_amount_minor: Optional[int] = None


@dataclass(frozen=True)
class AskQueryPlan:
    transaction_type: Optional[str] = None
    data_scope: str = ASK_SCOPE_ACCESSIBLE
    date_from_utc: Optional[datetime] = None
    date_to_utc: Optional[datetime] = None
    categories: tuple[str, ...] = ()
    currencies: tuple[str, ...] = ()
    text_terms: tuple[str, ...] = ()
    group_by: str = ASK_GROUP_BY_NONE
    metrics: tuple[str, ...] = (ASK_METRIC_SUM,)
    semantic_filter_required: bool = False
    output_preference: str = ASK_OUTPUT_AUTO


@dataclass(frozen=True)
class AskResult:
    output_type: Literal["TEXT", "INFOGRAPHIC"]
    text: Optional[str] = None
    image_path: Optional[Path] = None
    caption: Optional[str] = None

    def validate(self) -> None:
        if self.output_type == "TEXT":
            if self.text is None or self.image_path is not None:
                raise ValueError("Invalid AskResult: TEXT must have text and no image_path")
        elif self.output_type == "INFOGRAPHIC":
            if self.image_path is None:
                raise ValueError("Invalid AskResult: INFOGRAPHIC must have image_path")
        else:
            raise ValueError(f"Invalid AskResult output_type: {self.output_type!r}")
