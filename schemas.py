from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional, Union

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
