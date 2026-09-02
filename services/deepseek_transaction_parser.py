import json
from typing import Optional

import requests

from categories import EXPENSE_CATEGORIES, INCOME_CATEGORIES


class DeepSeekParserError(Exception):
    pass


SYSTEM_PROMPT_TEMPLATE = """Ты выполняешь строгое извлечение намерения из русского текста.
Намерение может быть:
- IMMEDIATE_TRANSACTION: обычный доход или расход сейчас;
- DEFERRED_EXPENSE: расход, который нужно автоматически зафиксировать в будущем;
- REMINDER: напоминание с текстом;
- EXCHANGE: конвертация денег из одной валюты в другую.

Верни только валидный JSON без Markdown и пояснений.

Формат конвертации валюты (курс назван):
{{
  "action_type": "EXCHANGE",
  "is_financial_record": true,
  "is_multiple": false,
  "from_amount": "2000.00",
  "from_currency": "USD",
  "to_currency": "RUB",
  "rate": 92.0,
  "description": "перевод долларов в рубли",
  "confidence": 0.95
}}

Формат конвертации валюты (обе суммы названы, курс не назван):
{{
  "action_type": "EXCHANGE",
  "is_financial_record": true,
  "is_multiple": false,
  "from_amount": "2000.00",
  "from_currency": "USD",
  "to_currency": "AMD",
  "to_amount": "100000.00",
  "description": "поменял доллары на драмы",
  "confidence": 0.95
}}

Формат обычной операции:
{{
  "action_type": "IMMEDIATE_TRANSACTION",
  "is_financial_record": true,
  "is_multiple": false,
  "transaction_type": "EXPENSE",
  "amount": "1200.00",
  "currency": "RUB",
  "category": "PRODUCTS",
  "description": "молоко, хлеб",
  "confidence": 0.95
}}

Формат отложенного списания:
{{
  "action_type": "DEFERRED_EXPENSE",
  "is_financial_record": true,
  "is_multiple": false,
  "transaction_type": "EXPENSE",
  "amount": "1000.00",
  "currency": "RUB",
  "category": "SUBSCRIPTIONS",
  "description": "интернет",
  "title": "списание за интернет",
  "event_at": "2026-12-20T09:00:00",
  "notify_at": "2026-12-20T09:00:00",
  "recurrence": "none",
  "confidence": 0.95
}}

Формат напоминания:
{{
  "action_type": "REMINDER",
  "title": "сходить в туалет",
  "event_at": "2026-07-25T15:00:00",
  "notify_at": "2026-07-25T14:30:00",
  "recurrence": "none",
  "confidence": 0.95
}}

Правила:
- текущая дата и время: {now_local};
- таймзона: {app_timezone};
- одна фраза должна содержать ровно одно намерение;
- если сказано "напомни", "напомнить", "поздравь", "не забыть" — это REMINDER;
- если сказано что расход будет/спишется/нужно списать в будущем — это DEFERRED_EXPENSE;
- если деньги переводятся из одной валюты в другую ("перевёл/конвертировал/обменял/поменял N <валюта> в/на <валюта>") — это EXCHANGE;
- для EXCHANGE укажи from_amount, from_currency, to_currency; если курс назван ("по курсу R") — укажи rate числом;
  если названы обе суммы и курс не назван — укажи to_amount (сколько получилось в целевой валюте) и оставь rate = null;
  если не названы ни курс, ни сумма в целевой валюте — и rate, и to_amount = null;
- сумма в целевой валюте считается известной только вместе с её валютой: «на 140 драм» — это to_amount="140", to_currency="AMD";
  если валюта суммы не названа («на 140») — to_amount определить нельзя, верни is_financial_record=false;
- если валюты совпадают, это не конвертация, а IMMEDIATE_TRANSACTION с категорией TRANSFERS;
- названия валют: рубли/рубль/руб/₽/RUB — RUB, доллары/баксы/$/USD — USD, евро/€/EUR — EUR,
  фунты/GBP — GBP, юани/CNY — CNY, сумы/UZS — UZS, тенге/KZT — KZT, драм/драмы/драммах/AMD — AMD;
- при распознавании речи «драм» часто звучит как «грамм», «грам», «драмм» — в контексте конвертации
  («поменял/перевёл X рублей на Y грамм») считай это драм (AMD);
- EXCHANGE выполняет правило курса: 1 единица from_currency = rate единиц to_currency;
- если дата указана без года, выбери ближайшую будущую дату;
- если указано "через N дней", прибавь N дней к текущей дате;
- если для напоминания указано время события, notify_at ставь за 30 минут до event_at;
- если для напоминания время события не указано, используй текущее время суток и notify_at = event_at;
- если для отложенного списания время не указано, используй 09:00;
- recurrence может быть только none, daily, weekly, monthly, yearly;
- "ежедневно" => daily, "еженедельно" => weekly, "ежемесячно" => monthly, "ежегодно/каждый год" => yearly;
- для IMMEDIATE_TRANSACTION и DEFERRED_EXPENSE определи transaction_type: EXPENSE или INCOME;
- не придумывай сумму;
- если сумма отсутствует или неоднозначна в финансовой операции, is_financial_record=false;
- если невозможно надёжно определить доход это или расход,
  transaction_type=UNKNOWN и is_financial_record=false;
- если найдено несколько независимых операций, is_multiple=true;
- если валюта не названа, используй RUB;
- категория должна соответствовать transaction_type и быть только из списка;
- если тип понятен, но категория неясна, используй OTHER;
- покупки алкоголя, выпивки, пива, вина, крепкого алкоголя и сопутствующих
  закусок для употребления с алкоголем классифицируй как EXPENSE/ALCOHOL;
- денежные переводы другому члену семьи классифицируй как EXPENSE/TRANSFERS;
- полученные денежные переводы от члена семьи классифицируй как INCOME/TRANSFERS;
- description должен кратко описывать назначение операции;
- каждый запрос независим от предыдущих.

Категории расходов в формате CODE — название:
{expense_categories}.

Категории доходов в формате CODE — название:
{income_categories}."""


class DeepSeekTransactionParser:
    def __init__(self, api_key: str, api_url: str, model: str, timeout_sec: int):
        self.api_key = api_key
        self.api_url = api_url
        self.model = model
        self.timeout_sec = timeout_sec

    def parse(self, transcript: str, category_catalog: Optional[dict] = None) -> dict:
        return self.parse_voice_intent(transcript, category_catalog)

    def parse_voice_intent(
        self,
        transcript: str,
        category_catalog: Optional[dict] = None,
        now_local: Optional[str] = None,
        app_timezone: str = "Europe/Moscow",
    ) -> dict:
        category_catalog = category_catalog or {"EXPENSE": EXPENSE_CATEGORIES, "INCOME": INCOME_CATEGORIES}
        now_local = now_local or ""
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            expense_categories=_format_category_prompt(category_catalog.get("EXPENSE", EXPENSE_CATEGORIES)),
            income_categories=_format_category_prompt(category_catalog.get("INCOME", INCOME_CATEGORIES)),
            now_local=now_local,
            app_timezone=app_timezone,
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Распознанный текст: {transcript}"},
        ]
        payload = {"model": self.model, "messages": messages, "temperature": 0, "response_format": {"type": "json_object"}}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        last_error = None
        required_keys = {
            "is_financial_record",
            "is_multiple",
            "transaction_type",
            "amount",
            "currency",
            "category",
            "description",
            "confidence",
        }
        reminder_keys = {"action_type", "title", "event_at", "notify_at", "recurrence", "confidence"}
        deferred_keys = required_keys | {"action_type", "event_at", "notify_at", "recurrence", "title"}
        exchange_keys = {
            "action_type",
            "is_financial_record",
            "is_multiple",
            "from_amount",
            "from_currency",
            "to_currency",
            "confidence",
        }
        for attempt in range(3):
            try:
                response = requests.post(self.api_url, headers=headers, json=payload, timeout=self.timeout_sec)
                if response.status_code in {429, 500, 502, 503, 504}:
                    last_error = f"http_{response.status_code}"
                    continue
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"].strip()
                parsed = json.loads(_strip_json(content))
                action_type = str(parsed.get("action_type") or "IMMEDIATE_TRANSACTION").upper()
                if action_type == "EXCHANGE" and exchange_keys.issubset(parsed):
                    return parsed
                if action_type == "REMINDER" and reminder_keys.issubset(parsed):
                    return parsed
                if action_type == "DEFERRED_EXPENSE" and deferred_keys.issubset(parsed):
                    return parsed
                if action_type == "IMMEDIATE_TRANSACTION" and required_keys.issubset(parsed):
                    return parsed
                last_error = "missing_required_json_fields"
                payload["messages"].append(
                    {
                        "role": "user",
                        "content": "В JSON отсутствуют обязательные поля. Верни все поля для выбранного action_type, включая confidence числом от 0 до 1.",
                    }
                )
            except (requests.RequestException, KeyError, IndexError, ValueError, json.JSONDecodeError) as exc:
                last_error = str(exc)
                if attempt < 2:
                    payload["messages"].append({"role": "user", "content": "Повтори ответ. Верни только валидный JSON."})
                    continue
        raise DeepSeekParserError(last_error or "deepseek_parse_failed")


def _strip_json(content: str) -> str:
    if content.startswith("```"):
        content = content.strip("`")
        if content.startswith("json"):
            content = content[4:]
    return content.strip()


def _format_category_prompt(categories: dict) -> str:
    return "\n".join(f"- {code} — {title}" for code, title in categories.items())
