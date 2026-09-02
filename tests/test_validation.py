import pytest
from decimal import Decimal

from schemas import ValidationError, amount_to_minor, validate_deepseek_payload, validate_exchange_payload, validate_voice_intent


def test_amount_to_minor_uses_decimal_not_float():
    assert amount_to_minor("1250.50") == 125050
    assert amount_to_minor("1250,50") == 125050


@pytest.mark.parametrize("amount", ["0", "-1", "abc"])
def test_amount_to_minor_rejects_invalid(amount):
    with pytest.raises(ValidationError):
        amount_to_minor(amount)


def test_validate_expense_payload():
    parsed = validate_deepseek_payload(
        {
            "is_financial_record": True,
            "is_multiple": False,
            "transaction_type": "EXPENSE",
            "amount": "500",
            "currency": "RUB",
            "category": "PRODUCTS",
            "description": "молоко",
            "confidence": 0.9,
        },
        "пятьсот продукты молоко",
        0.7,
    )
    assert parsed.amount_minor == 50000
    assert parsed.transaction_type == "EXPENSE"
    assert parsed.category == "PRODUCTS"


def test_validate_transfers_category():
    parsed = validate_deepseek_payload(
        {
            "is_financial_record": True,
            "is_multiple": False,
            "transaction_type": "EXPENSE",
            "amount": "5000",
            "currency": "RUB",
            "category": "TRANSFERS",
            "description": "перевод жене",
            "confidence": 0.9,
        },
        "перевел жене пять тысяч",
        0.7,
    )
    assert parsed.category == "TRANSFERS"


def test_validate_alcohol_category():
    parsed = validate_deepseek_payload(
        {
            "is_financial_record": True,
            "is_multiple": False,
            "transaction_type": "EXPENSE",
            "amount": "998",
            "currency": "RUB",
            "category": "ALCOHOL",
            "description": "пиво с закусками",
            "confidence": 0.9,
        },
        "девятьсот девяносто восемь рублей пиво с закусками",
        0.7,
    )
    assert parsed.category == "ALCOHOL"


def test_validate_custom_category():
    catalog = {
        "EXPENSE": {"OTHER": "Прочее", "CUSTOM_FAMILY": "Семья"},
        "INCOME": {"OTHER": "Прочее"},
    }
    parsed = validate_deepseek_payload(
        {
            "is_financial_record": True,
            "is_multiple": False,
            "transaction_type": "EXPENSE",
            "amount": "1000",
            "currency": "RUB",
            "category": "CUSTOM_FAMILY",
            "description": "семья",
            "confidence": 0.9,
        },
        "тысяча семья",
        0.7,
        catalog,
    )
    assert parsed.category == "CUSTOM_FAMILY"


def test_wrong_category_becomes_other():
    parsed = validate_deepseek_payload(
        {
            "is_financial_record": True,
            "is_multiple": False,
            "transaction_type": "EXPENSE",
            "amount": "1000",
            "currency": "RUB",
            "category": "SALARY",
            "description": "что-то",
            "confidence": 0.9,
        },
        "тысяча что-то",
        0.7,
    )
    assert parsed.category == "OTHER"


@pytest.mark.parametrize(
    "payload,error_code",
    [
        ({"is_financial_record": False}, "rejected_not_financial"),
        ({"is_financial_record": True, "is_multiple": True}, "rejected_multiple"),
        ({"is_financial_record": True, "is_multiple": False, "transaction_type": "UNKNOWN"}, "rejected_unknown_type"),
    ],
)
def test_rejections(payload, error_code):
    with pytest.raises(ValidationError) as exc:
        validate_deepseek_payload(payload, "текст", 0.7)
    assert exc.value.code == error_code


EXCHANGE_PAYLOAD = {
    "action_type": "EXCHANGE",
    "is_financial_record": True,
    "is_multiple": False,
    "from_amount": "2000",
    "from_currency": "USD",
    "to_currency": "RUB",
    "rate": 92,
    "description": "перевод долларов в рубли",
    "confidence": 0.95,
}


def test_validate_exchange_with_rate():
    parsed = validate_exchange_payload(EXCHANGE_PAYLOAD, "перевёл 2000 долларов в рубли по курсу 92", 0.7)
    assert parsed.from_amount_minor == 200000
    assert parsed.from_currency == "USD"
    assert parsed.to_currency == "RUB"
    assert parsed.to_amount_minor == 18400000
    assert str(parsed.rate) == "92"


def test_validate_exchange_without_rate_requests_dialog():
    payload = {**EXCHANGE_PAYLOAD, "rate": None}
    parsed = validate_exchange_payload(payload, "перевёл 2000 долларов в рубли", 0.7)
    assert parsed.rate is None
    assert parsed.to_amount_minor is None


def test_validate_exchange_with_to_amount_computes_rate():
    payload = {
        **EXCHANGE_PAYLOAD,
        "rate": None,
        "from_amount": "2000",
        "from_currency": "USD",
        "to_currency": "AMD",
        "to_amount": "100 000",
    }
    parsed = validate_exchange_payload(payload, "поменял 2000 долларов на 100 000 армянских драм", 0.7)
    assert parsed.from_amount_minor == 200000
    assert parsed.to_currency == "AMD"
    assert parsed.to_amount_minor == 10000000
    assert parsed.rate == Decimal("50")


def test_validate_exchange_neither_rate_nor_to_amount_requests_dialog():
    payload = {**EXCHANGE_PAYLOAD, "rate": None, "to_amount": None}
    parsed = validate_exchange_payload(payload, "перевёл 2000 долларов", 0.7)
    assert parsed.rate is None
    assert parsed.to_amount_minor is None


def test_validate_exchange_rate_takes_precedence_over_to_amount():
    payload = {**EXCHANGE_PAYLOAD, "rate": 92, "to_amount": "99999999"}
    parsed = validate_exchange_payload(payload, "перевёл 2000 долларов в рубли по курсу 92", 0.7)
    assert parsed.to_amount_minor == 18400000
    assert str(parsed.rate) == "92"


def test_amount_to_minor_accepts_spaces():
    assert amount_to_minor("100 000") == 10000000
    assert amount_to_minor("100 000,50") == 10000050


def test_validate_exchange_same_currency_rejected():
    payload = {**EXCHANGE_PAYLOAD, "to_currency": "USD"}
    with pytest.raises(ValidationError) as exc:
        validate_exchange_payload(payload, "перевёл доллары в доллары", 0.7)
    assert exc.value.code == "rejected_same_currency"


def test_validate_exchange_unsupported_currency_rejected():
    payload = {**EXCHANGE_PAYLOAD, "to_currency": "XYZ"}
    with pytest.raises(ValidationError) as exc:
        validate_exchange_payload(payload, "перевёл в XYZ", 0.7)
    assert exc.value.code == "parse_failed"


def test_validate_exchange_zero_rate_is_missing_rate():
    parsed = validate_exchange_payload({**EXCHANGE_PAYLOAD, "rate": 0}, "перевёл 2000 долларов в рубли", 0.7)
    assert parsed.rate is None


def test_validate_voice_intent_dispatches_exchange():
    from schemas import ParsedExchange

    parsed = validate_voice_intent(EXCHANGE_PAYLOAD, "перевёл 2000 долларов в рубли по курсу 92", 0.7, None, "Europe/Moscow")
    assert isinstance(parsed, ParsedExchange)
    assert parsed.from_amount_minor == 200000
    assert parsed.to_amount_minor == 18400000


def test_exchange_with_rate_computes_to_amount():
    from schemas import ParsedExchange

    parsed = validate_exchange_payload(EXCHANGE_PAYLOAD, "фраза", 0.7)
    assert isinstance(parsed, ParsedExchange)
    assert parsed.to_amount_minor == 18400000
