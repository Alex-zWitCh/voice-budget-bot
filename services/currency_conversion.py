from decimal import Decimal

from categories import CURRENCY_SYMBOLS


def build_rate_map(rate_rows: list) -> dict[tuple[str, str], Decimal]:
    rates: dict[tuple[str, str], Decimal] = {}
    for from_currency, to_currency, rate in rate_rows:
        rates[(from_currency, to_currency)] = Decimal(str(rate))
    return rates


def rate_lookup(
    currency_from: str, currency_to: str, rates: dict[tuple[str, str], Decimal]
) -> Decimal | None:
    if currency_from == currency_to:
        return Decimal(1)
    direct = rates.get((currency_from, currency_to))
    if direct is not None:
        return direct
    reverse = rates.get((currency_to, currency_from))
    if reverse is not None:
        return Decimal(1) / reverse
    return None


def to_base_minor(
    row, main_currency: str, rates: dict[tuple[str, str], Decimal]
) -> int | None:
    """Переводит сумму записи в основную валюту через сохранённые курсы конвертаций."""
    if row.currency == main_currency and row.exchange_rate is None:
        return row.amount_minor
    if (
        row.exchange_rate is not None
        and row.from_currency
        and row.transaction_type == "INCOME"
    ):
        anchor_currency = row.from_currency
        anchor_minor = row.amount_minor / Decimal(str(row.exchange_rate))
    else:
        anchor_currency = row.currency
        anchor_minor = row.amount_minor
    factor = rate_lookup(anchor_currency, main_currency, rates)
    if factor is None:
        return None
    return int(round(anchor_minor * factor))


def format_exchange_rate(rate) -> str:
    if rate is None:
        return ""
    return format(Decimal(str(rate)).normalize(), "f")


def symbol_for(currency: str) -> str:
    return CURRENCY_SYMBOLS.get(currency, currency)


def format_amount_minor(amount_minor: int | float, currency: str) -> str:
    """Форматирует сумму в minor-единицах как человекочитаемую строку с символом валюты."""
    amount = Decimal(str(amount_minor)) / 100
    formatted = (
        format(amount.quantize(Decimal("0.01")), ",.2f")
        .replace(",", " ")
        .replace(".", ",")
    )
    return f"{formatted} {symbol_for(currency)}"
