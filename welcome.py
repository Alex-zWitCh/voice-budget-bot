from categories import format_categories


AUTHOR_GITHUB_URL = "https://github.com/Alex-zWitCh"

COMMANDS = [
    ("/start", "приветствие и меню"),
    ("/menu", "показать кнопки меню"),
    ("/calendar", "календарь будущих событий на 2 месяца"),
    ("/categories", "категории и управление своими категориями"),
    ("/report", "графические отчеты расходов и доходов за последние 30 дней"),
    ("/balance", "баланс по каждой валюте"),
    ("/currency", "показать или сменить основную валюту"),
    ("/family", "статус семьи, создание и приглашение"),
    ("/join", "вступить в семью по коду"),
]

COMMANDS_EXTRA = [
    ("/family create <имя>", "создать семью"),
    ("/family invite", "показать код приглашения"),
]


FEATURES = [
    "• голосовые и текстовые записи доходов и расходов",
    "• доход и траты в разных валютах (RUB, USD, EUR, GBP, CNY, UZS, KZT, AMD)",
    "• конвертация валюты: по курсу «перевёл 2000 $ в рубли по курсу 92»",
    "  или по обеим суммам «поменял 2000 $ на 100 000 армянских драм» — курс бот вычислит сам",
    "  обязательно называйте обе валюты и суммы: «поменял 35 000 рублей на 150 000 армянских драм»",
    "• если курс не назван — бот спросит его в диалоге",
    "• баланс по каждой валюте: /balance",
    "• основная валюта для отчётов: /currency",
    "• графические отчёты за 30 дней и автоматические месячные пакеты в основной валюте",
    "• отложенные списания, напоминания и календарь: /calendar",
    "• семейный учёт: /family, /join",
]

EXAMPLES = [
    "«пятьсот продукты молоко»",
    "«получил зарплату 2000 долларов»",
    "«перевёл 2000 долларов в рубли по курсу 92»",
    "«поменял 35 000 рублей на 150 000 армянских драм»",
    "«20 декабря спишется тысяча за интернет»",
    "«напомни через 4 дня в 15:00 сходить в туалет»",
]


def welcome_text(config) -> str:
    lines = [
        f"{config.welcome_title}",
        "",
        config.welcome_intro,
        "",
        "Возможности:",
        *FEATURES,
        "",
        "Примеры:",
        *[f"• {example}" for example in EXAMPLES],
        "",
        "Команды:",
        *[f"• {command} — {description}" for command, description in COMMANDS],
        *[f"• {command} — {description}" for command, description in COMMANDS_EXTRA],
    ]
    if config.welcome_footer:
        lines.extend(["", config.welcome_footer])
    lines.extend(["", f"Автор форка: {AUTHOR_GITHUB_URL}"])
    return "\n".join(lines)


def commands_text() -> str:
    lines = [
        "Доступные команды:",
        *[f"• {command} — {description}" for command, description in COMMANDS],
        *[f"• {command} — {description}" for command, description in COMMANDS_EXTRA],
        "",
        "Возможности:",
        *FEATURES,
    ]
    return "\n".join(lines)


def categories_text() -> str:
    return "Доступные категории:\n\n" + format_categories()
