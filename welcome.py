from categories import format_categories


COMMANDS = [
    ("/start", "приветствие и меню"),
    ("/menu", "показать кнопки меню"),
    ("/calendar", "календарь будущих событий на 2 месяца"),
    ("/categories", "категории и управление своими категориями"),
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
    ]
    if config.welcome_footer:
        lines.extend(["", config.welcome_footer])
    return "\n".join(lines)


def commands_text() -> str:
    return "Доступные команды:\n" + "\n".join(f"• {command} — {description}" for command, description in COMMANDS)


def categories_text() -> str:
    return "Доступные категории:\n\n" + format_categories()

