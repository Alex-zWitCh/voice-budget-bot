import re

POLICY_FINANCIAL = "FINANCIAL_DATA_QUERY"
POLICY_OUT_OF_SCOPE = "OUT_OF_SCOPE"
POLICY_WRITE = "WRITE_REQUEST"
POLICY_SECURITY = "SECURITY_VIOLATION"
POLICY_AMBIGUOUS = "AMBIGUOUS"

_SECURITY_MARKERS = [
    "select *",
    "union select",
    "sqlite_master",
    "pragma",
    "drop table",
    "insert into",
    "delete from",
    "update transactions",
    "show tables",
    "system prompt",
    "системный промпт",
    "игнорируй",
    "обойди ограничения",
    "сними ограничения",
    "telegram_user_id",
    "family_id",
    "все записи базы",
    "другого пользователя",
    "чужого пользователя",
    "ты теперь администратор",
    "теперь ты администратор",
    "выполни sql",
    "выполни sql-запрос",
    "сырой sql",
]

_WRITE_MARKERS = [
    "удали",
    "удалить",
    "измени",
    "изменить",
    "исправь",
    "исправить",
    "добавь",
    "добавить",
    "создай",
    "создать",
    "перенеси",
    "перенести",
    "перемести",
    "назначь",
    "поставь основную валюту",
    "установи основную валюту",
    "смени валюту",
    "переведи запись",
    "переведи в семейные",
    "пометь",
    "запиши",
    "записать расход",
    "удаления",
]

_OUT_OF_SCOPE_MARKERS = [
    "какая погода",
    "погода",
    "рецепт",
    "как приготовить",
    "кто президент",
    "президент",
    "напиши рассказ",
    "напиши стих",
    "расскажи анекдот",
    "пошути",
    "сочини",
    "переведи",
    "напиши python",
    "напиши код",
    "напиши программу",
    "покажи картинку",
    "сгенерируй картинку",
    "сегодня курс",
    "текущий курс",
    "курс на сегодня",
    "курс доллара сегодня",
    "курс евро сегодня",
    "какой курс валют",
    "что такое",
    "объясни физику",
    "спой",
]

_OUT_OF_SCOPE_VERB_RE = re.compile(r"\b(расскажи|рассказать|опиши)\b")


def _contains_marker(text: str, markers: list[str]) -> bool:
    for marker in markers:
        if marker in text:
            return True
    return False


class AskPolicy:
    def classify(self, question: str) -> str:
        text = (question or "").lower().strip()
        if not text:
            return POLICY_AMBIGUOUS
        if _contains_marker(text, _SECURITY_MARKERS):
            return POLICY_SECURITY
        if _contains_marker(text, _WRITE_MARKERS):
            return POLICY_WRITE
        if _contains_marker(text, _OUT_OF_SCOPE_MARKERS):
            return POLICY_OUT_OF_SCOPE
        if _OUT_OF_SCOPE_VERB_RE.search(text):
            if _contains_marker(text, _FINANCIAL_CONTEXT):
                return POLICY_FINANCIAL
            return POLICY_OUT_OF_SCOPE
        return POLICY_FINANCIAL


_FINANCIAL_CONTEXT = [
    "расход",
    "расходы",
    "трат",
    "тратил",
    "тратила",
    "доход",
    "зарплат",
    "бюджет",
    "деньг",
    "купил",
    "купила",
    "покупк",
    "кафе",
    "продукт",
    "жиль",
    "семь",
    "потратил",
    "потратила",
    "записа",
]
