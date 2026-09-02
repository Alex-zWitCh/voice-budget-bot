import json
from typing import Optional

import requests

from services.deepseek_transaction_parser import _strip_json


class AskLLMError(Exception):
    pass


class AskLLMClient:
    def __init__(self, api_key: str, api_url: str, model: str, timeout_sec: int):
        self.api_key = api_key
        self.api_url = api_url
        self.model = model
        self.timeout_sec = timeout_sec

    def chat_json(self, system: str, user: str, temperature: float = 0.0) -> dict:
        content = self._chat(system, user, temperature, json_mode=True)
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise AskLLMError("invalid_json") from exc
        if not isinstance(parsed, dict):
            raise AskLLMError("invalid_json")
        return parsed

    def _chat(self, system: str, user: str, temperature: float, json_mode: bool) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        last_error: Optional[str] = None
        for attempt in range(3):
            try:
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout_sec,
                )
                if response.status_code in {429, 500, 502, 503, 504}:
                    last_error = f"http_{response.status_code}"
                    continue
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"].strip()
                return _strip_json(content)
            except (
                requests.RequestException,
                KeyError,
                IndexError,
                ValueError,
                json.JSONDecodeError,
            ) as exc:
                last_error = str(exc)
                if attempt < 2:
                    payload["messages"].append(
                        {
                            "role": "user",
                            "content": "Повтори ответ. Только валидный JSON без пояснений.",
                        }
                    )
                    continue
        raise AskLLMError(last_error or "ask_llm_failed")
