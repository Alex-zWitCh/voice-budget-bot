EXPENSE_CATEGORIES = {
    "PRODUCTS": "Продукты",
    "CAFE": "Кафе",
    "TRANSPORT": "Транспорт",
    "CAR": "Автомобиль",
    "HOUSING": "Жильё",
    "HEALTH": "Здоровье",
    "CLOTHING": "Одежда",
    "CHILDREN": "Дети",
    "ENTERTAINMENT": "Развлечения",
    "SUBSCRIPTIONS": "Подписки и связь",
    "ELECTRONICS": "Техника",
    "EDUCATION": "Образование",
    "GIFTS": "Подарки",
    "TRAVEL": "Путешествия",
    "OTHER": "Прочее",
}

INCOME_CATEGORIES = {
    "SALARY": "Зарплата",
    "FREELANCE": "Подработка",
    "BUSINESS": "Бизнес",
    "BENEFITS": "Пособия",
    "PENSION": "Пенсия",
    "REFUND": "Возврат",
    "GIFTS_RECEIVED": "Подарок",
    "SALE": "Продажа",
    "INVESTMENT_INCOME": "Инвестиции",
    "OTHER": "Прочее",
}

CATEGORY_BY_TYPE = {
    "EXPENSE": EXPENSE_CATEGORIES,
    "INCOME": INCOME_CATEGORIES,
}

SUPPORTED_CURRENCIES = {"RUB", "USD", "EUR", "GBP", "CNY", "UZS", "KZT"}
CURRENCY_SYMBOLS = {"RUB": "₽", "USD": "$", "EUR": "€", "GBP": "£", "CNY": "¥", "UZS": "UZS", "KZT": "₸"}


def category_title(transaction_type: str, category: str) -> str:
    return CATEGORY_BY_TYPE.get(transaction_type, {}).get(category, "Прочее")

