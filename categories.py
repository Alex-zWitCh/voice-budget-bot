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
    "TRANSFERS": "Переводы",
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
    "TRANSFERS": "Переводы",
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


def format_categories() -> str:
    expense = "\n".join(f"- {title}" for title in EXPENSE_CATEGORIES.values())
    income = "\n".join(f"- {title}" for title in INCOME_CATEGORIES.values())
    return f"Расходы:\n{expense}\n\nДоходы:\n{income}"
