from categories import format_categories


AUTHOR_GITHUB_URL = "https://github.com/Alex-zWitCh"

COMMANDS = [
    ("/start", "приветствие и меню"),
    ("/menu", "показать кнопки меню"),
    ("/calendar", "календарь будущих событий на 2 месяца"),
    ("/categories", "категории и управление своими категориями"),
    ("/report", "графические отчеты расходов и доходов за последние 30 дней"),
    ("/family", "статус семьи, создание и приглашение"),
    ("/join", "вступить в семью по коду"),
]

COMMANDS_EXTRA = [
    ("/family create <имя>", "создать семью"),
    ("/family invite", "показать код приглашения"),
]


def welcome_text(config) -> str:
    lines = [
        f"{config.welcome_title}",
        "",
        config.welcome_intro,
        "",
        "Примеры:",
        "• «пятьсот продукты молоко»",
        "• «получил зарплату сто тысяч»",
        "• «20 декабря спишется тысяча за интернет»",
        "• «напомни через 4 дня в 15:00 сходить в туалет»",
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
    lines = [f"• {command} — {description}" for command, description in COMMANDS]
    lines.extend(f"• {command} — {description}" for command, description in COMMANDS_EXTRA)
    return "Доступные команды:\n" + "\n".join(lines)


def categories_text() -> str:
    return "Доступные категории:\n\n" + format_categories()
