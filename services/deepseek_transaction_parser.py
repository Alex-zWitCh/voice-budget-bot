import json

import requests

from categories import EXPENSE_CATEGORIES, INCOME_CATEGORIES


class DeepSeekParserError(Exception):
    pass


SYSTEM_PROMPT = f"""Ты выполняешь строгое извлечение одной финансовой операции из русского текста.
Операция может быть доходом или расходом.

Верни только валидный JSON без Markdown и пояснений.

Обязательный формат:
{{
  "is_financial_record": true,
  "is_multiple": false,
  "transaction_type": "EXPENSE",
  "amount": "1200.00",
  "currency": "RUB",
  "category": "PRODUCTS",
  "description": "молоко, хлеб",
  "confidence": 0.95
}}

Правила:
- одна фраза должна содержать ровно одну финансовую операцию;
- определи transaction_type: EXPENSE или INCOME;
- не придумывай сумму;
- если сумма отсутствует или неоднозначна, is_financial_record=false;
- если невозможно надёжно определить доход это или расход,
  transaction_type=UNKNOWN и is_financial_record=false;
- если найдено несколько независимых операций, is_multiple=true;
- если валюта не названа, используй RUB;
- категория должна соответствовать transaction_type и быть только из списка;
- если тип понятен, но категория неясна, используй OTHER;
- description должен кратко описывать назначение операции;
- каждый запрос независим от предыдущих.

Категории расходов:
{", ".join(EXPENSE_CATEGORIES)}.

Категории доходов:
{", ".join(INCOME_CATEGORIES)}."""


class DeepSeekTransactionParser:
    def __init__(self, api_key: str, api_url: str, model: str, timeout_sec: int):
        self.api_key = api_key
        self.api_url = api_url
        self.model = model
        self.timeout_sec = timeout_sec

    def parse(self, transcript: str) -> dict:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
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
        for attempt in range(3):
            try:
                response = requests.post(self.api_url, headers=headers, json=payload, timeout=self.timeout_sec)
                if response.status_code in {429, 500, 502, 503, 504}:
                    last_error = f"http_{response.status_code}"
                    continue
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"].strip()
                parsed = json.loads(_strip_json(content))
                if required_keys.issubset(parsed):
                    return parsed
                last_error = "missing_required_json_fields"
                payload["messages"].append(
                    {
                        "role": "user",
                        "content": "В JSON отсутствуют обязательные поля. Верни все поля, включая confidence числом от 0 до 1.",
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
