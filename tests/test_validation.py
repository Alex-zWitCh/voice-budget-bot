import pytest

from schemas import ValidationError, amount_to_minor, validate_deepseek_payload


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

