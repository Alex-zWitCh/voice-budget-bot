from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional, Union
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


def amount_to_minor(amount: Union[str, int, float, Decimal], currency: str = "RUB") -> int:
    try:
        decimal_amount = Decimal(str(amount).replace(",", ".")).quantize(Decimal("0.01"))
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
            "⚠️ Не удалось определить сумму операции.\nПримеры: «тысяча двести продукты» или «получил зарплату сто тысяч».",
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


def validate_voice_intent(
    payload: dict,
    transcript: str,
    min_confidence: float,
    category_catalog: Optional[dict],
    app_timezone: str,
) -> Union[ParsedTransaction, ParsedScheduledEvent]:
    action_type = str(payload.get("action_type") or "IMMEDIATE_TRANSACTION").upper()
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
