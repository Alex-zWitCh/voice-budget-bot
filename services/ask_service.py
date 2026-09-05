from __future__ import annotations

import json
import logging
import re
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Optional

from categories import CATEGORY_BY_TYPE
from schemas import (
    ASK_GROUP_BY_NONE,
    ASK_METRIC_SUM,
    ASK_OUTPUT_INFOGRAPHIC,
    ASK_OUTPUT_TEXT,
    AnalyticsTransaction,
    AskQueryPlan,
    AskResult,
)
from services.analytics_calculator import AnalyticsCalculator, CalculationResult
from services.analytics_repository import AnalyticsRepository
from services.ask_llm import AskLLMClient
from services.ask_planner import AskPlanner
from services.ask_policy import (
    POLICY_AMBIGUOUS,
    POLICY_FINANCIAL,
    POLICY_OUT_OF_SCOPE,
    POLICY_SECURITY,
    POLICY_WRITE,
    AskPolicy,
)
from services.ask_renderer import (
    AskRenderer,
    build_list_text,
    format_minor,
    period_description,
    scope_description,
    transaction_type_label,
)
from services.currency_conversion import symbol_for

logger = logging.getLogger(__name__)

RATE_LIMIT_PER_MINUTE = 10
RATE_LIMIT_WINDOW_SEC = 60

_LIST_MARKERS = (
    "построчно",
    "перечисли",
    "списком",
    "перечень",
    "все операции",
    "покажи все",
    "покажи операции",
    "каждую запись",
    "по каждой операции",
    "какие были",
)

_NEWEST_RE = re.compile(
    r"(?:(\d{1,3})\s+)?(?:моих\s+)?последн\w*\s+"
    r"(?:личных\s+и\s+семейных\s+|личных\s+|семейных\s+)?"
    r"(трат|операци|запис|расход|покуп|списан|транзакц|конвертац)"
)

_EXCHANGE_MARKERS = (
    "конвертац",
    "обмен",
    "поменял",
    "поменяла",
    "менял",
    "перевод валют",
)

POLICY_MESSAGES = {
    POLICY_WRITE: "Я могу только анализировать данные.\nИзменение, создание и удаление записей через /ask запрещено.",
    POLICY_OUT_OF_SCOPE: "Через /ask я работаю только с вашими финансовыми данными SmartExpense.",
    POLICY_SECURITY: "Я могу анализировать только финансовые данные, доступные вашему аккаунту.",
    POLICY_AMBIGUOUS: "Задайте вопрос о ваших расходах или доходах — текстом или голосом.",
}

NO_DATA_TEXT = "В доступных вам записях данных по этому запросу не найдено."
TOO_BROAD_TEXT = (
    "Запрос охватывает слишком много операций.\nУточните период или категорию."
)


class AskService:
    def __init__(
        self,
        config,
        repository: AnalyticsRepository,
        policy: AskPolicy,
        planner: AskPlanner,
        calculator: AnalyticsCalculator,
        renderer: AskRenderer,
        llm_client: Optional[AskLLMClient] = None,
        recorder: Optional = None,
    ):
        self.config = config
        self.repository = repository
        self.policy = policy
        self.planner = planner
        self.calculator = calculator
        self.renderer = renderer
        self.llm_client = llm_client
        self.recorder = recorder
        self._history: dict[int, deque[float]] = defaultdict(deque)

    def ask(
        self, telegram_user_id: int, question: str, source: str = "text"
    ) -> AskResult:
        started = time.monotonic()
        trace = {
            "telegram_user_id": telegram_user_id,
            "source": source,
            "question": (question or "").strip(),
            "policy_code": "FINANCIAL",
            "plan_json": None,
            "rows_fetched": None,
            "was_narrowed": None,
            "output_type": None,
            "duration_ms": None,
            "error_code": None,
        }
        try:
            result = self._ask(telegram_user_id, trace)
            trace["output_type"] = result.output_type
            return result
        except Exception:
            trace.setdefault("error_code", "exception")
            trace.setdefault("output_type", None)
            logger.exception(
                "ask_failed user_id=%s question_len=%s",
                telegram_user_id,
                len(trace["question"]),
            )
            raise
        finally:
            trace["duration_ms"] = int((time.monotonic() - started) * 1000)
            logger.info(
                "ask_finished user_id=%s outcome=%s duration_ms=%s error=%s",
                telegram_user_id,
                trace["output_type"] or "error",
                trace["duration_ms"],
                trace.get("error_code"),
            )
            self._persist(trace)

    def _persist(self, trace: dict) -> None:
        if not self.recorder or not getattr(self.config, "ask_history_enabled", True):
            return
        try:
            self.recorder.record_ask(
                telegram_user_id=trace["telegram_user_id"],
                source=trace["source"],
                question=trace["question"],
                policy_code=trace["policy_code"],
                plan_json=trace.get("plan_json"),
                rows_fetched=trace.get("rows_fetched"),
                was_narrowed=trace.get("was_narrowed"),
                output_type=trace.get("output_type"),
                duration_ms=trace.get("duration_ms"),
                model=self.config.ask_model_effective,
                error_code=trace.get("error_code"),
            )
        except Exception:
            logger.exception(
                "ask_history_write_failed user_id=%s", trace.get("telegram_user_id")
            )

    @staticmethod
    def _plan_payload(plan: Optional[AskQueryPlan]) -> Optional[str]:
        if plan is None:
            return None
        payload = {
            "transaction_type": plan.transaction_type,
            "data_scope": plan.data_scope,
            "date_from_utc": plan.date_from_utc.isoformat()
            if plan.date_from_utc
            else None,
            "date_to_utc": plan.date_to_utc.isoformat() if plan.date_to_utc else None,
            "categories": list(plan.categories),
            "currencies": list(plan.currencies),
            "text_terms": list(plan.text_terms),
            "group_by": plan.group_by,
            "metrics": list(plan.metrics),
            "semantic_filter_required": plan.semantic_filter_required,
            "output_preference": plan.output_preference,
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    def _ask(self, telegram_user_id: int, trace: dict) -> AskResult:
        question = trace["question"]
        if not question:
            trace["error_code"] = "empty"
            return self._text("Задайте вопрос о ваших финансовых данных.")
        if len(question) > self.config.ask_max_question_length:
            trace["error_code"] = "too_long"
            return self._text(
                f"Вопрос слишком длинный (лимит {self.config.ask_max_question_length} символов).\nСформулируйте короче."
            )
        if not self._allow_request(telegram_user_id):
            trace["error_code"] = "rate_limited"
            return self._text(
                "Слишком много запросов в минуту. Подождите немного и повторите."
            )

        policy_code = self.policy.classify(question)
        trace["policy_code"] = policy_code
        if policy_code != POLICY_FINANCIAL:
            logger.info(
                "ask_rejected user_id=%s policy=%s", telegram_user_id, policy_code
            )
            trace["output_type"] = "TEXT"
            return self._text(
                POLICY_MESSAGES.get(policy_code, POLICY_MESSAGES[POLICY_AMBIGUOUS])
            )

        access_scope = self.repository.make_scope(telegram_user_id)
        main_currency = self.repository.get_main_currency(telegram_user_id)
        category_catalog = self._category_catalog(telegram_user_id)

        try:
            plan = self.planner.plan(question, category_catalog, main_currency)
        except Exception:
            logger.exception("ask_plan_failed user_id=%s", telegram_user_id)
            trace["error_code"] = "plan_failed"
            trace["output_type"] = "TEXT"
            return self._text(
                "Не удалось понять вопрос. Переформулируйте его, пожалуйста."
            )
        trace["plan_json"] = self._plan_payload(plan)

        rows = self._fetch_rows(
            access_scope,
            plan,
            trace,
            exclude_exchange_legs=not self._wants_exchange(question),
        )
        if rows is None:
            trace["error_code"] = "too_broad"
            trace["output_type"] = "TEXT"
            return self._text(TOO_BROAD_TEXT)
        if not rows:
            trace["error_code"] = "no_data"
            trace["output_type"] = "TEXT"
            return self._text(NO_DATA_TEXT)

        if plan.semantic_filter_required and self.llm_client is not None:
            rows = self._semantic_filter(question, rows)
            if not rows:
                trace["error_code"] = "no_data"
                trace["output_type"] = "TEXT"
                return self._text(NO_DATA_TEXT)

        category_titles = self._category_titles(category_catalog)
        target_currency = self._target_currency(plan, main_currency)
        rate_rows = self.repository.get_exchange_rates(telegram_user_id)
        result = self.calculator.calculate(
            rows, plan, target_currency, rate_rows, category_titles
        )

        if result.total_count == 0:
            trace["error_code"] = "unconverted_only"
            trace["output_type"] = "TEXT"
            note = self._unconverted_note(result)
            return self._text(f"{NO_DATA_TEXT}\n{note}" if note else NO_DATA_TEXT)

        if self._wants_list(question):
            trace["output_type"] = "TEXT"
            return self._build_list_answer(question, result, rows, category_titles)

        output_preference = self._output_preference(plan, result)
        if output_preference == ASK_OUTPUT_TEXT:
            return self._build_text_answer(plan, result, access_scope, main_currency)
        return self._build_infographic(plan, result, access_scope)

    # ---- data ----

    def _fetch_rows(
        self,
        access_scope,
        plan: AskQueryPlan,
        trace: dict,
        exclude_exchange_legs: bool = True,
    ) -> Optional[list[AnalyticsTransaction]]:
        limit = self.config.ask_max_rows + 1
        rows = self.repository.fetch_transactions(
            access_scope,
            data_scope=plan.data_scope,
            transaction_type=plan.transaction_type,
            date_from=plan.date_from_utc,
            date_to=plan.date_to_utc,
            categories=plan.categories,
            currencies=plan.currencies,
            text_terms=plan.text_terms,
            limit=limit,
            exclude_exchange_legs=exclude_exchange_legs,
        )
        trace["rows_fetched"] = len(rows)
        if len(rows) <= self.config.ask_max_rows:
            return rows
        if (
            plan.date_from_utc is None
            and plan.date_to_utc is None
            and not plan.text_terms
            and not plan.semantic_filter_required
        ):
            now = datetime.now(timezone.utc)
            narrowed = self.repository.fetch_transactions(
                access_scope,
                data_scope=plan.data_scope,
                transaction_type=plan.transaction_type,
                date_from=now - timedelta(days=365),
                date_to=None,
                categories=plan.categories,
                currencies=plan.currencies,
                text_terms=plan.text_terms,
                limit=limit,
                exclude_exchange_legs=exclude_exchange_legs,
            )
            trace["was_narrowed"] = True
            trace["rows_fetched"] = len(narrowed)
            if len(narrowed) <= self.config.ask_max_rows:
                return narrowed
        return None

    def _semantic_filter(
        self, question: str, rows: list[AnalyticsTransaction]
    ) -> list[AnalyticsTransaction]:
        try:
            payload_lines = []
            for index, row in enumerate(rows[: self.config.ask_max_rows]):
                payload_lines.append(
                    f"ref={index} date={row.message_date_utc:%Y-%m-%d} category={row.category} "
                    f"description={row.description[:120]!r} transcript={row.transcript[:120]!r}"
                )
            system = (
                "Ты выбираешь из списка финансовых записей те, что релевантны вопросу пользователя.\n"
                'Верни только JSON: {"relevant_refs": [числа], "reason": "коротко"}.\n'
                "Не возвращай идентификаторы пользователей, telegram_user_id, family_id и SQL."
            )
            user = f"Вопрос: {question}\n\nЗаписи:\n{chr(10).join(payload_lines)}"
            payload = self.llm_client.chat_json(system, user)
            refs = payload.get("relevant_refs") or []
            allowed = {
                int(ref)
                for ref in refs
                if str(ref).isdigit() and 0 <= int(ref) < len(rows)
            }
            if not allowed:
                return rows
            return [row for index, row in enumerate(rows) if index in allowed]
        except Exception:
            logger.exception("ask_semantic_filter_failed")
            return rows

    # ---- helpers ----

    def _category_catalog(self, telegram_user_id: int) -> dict[str, dict[str, str]]:
        catalog = {
            transaction_type: values.copy()
            for transaction_type, values in CATEGORY_BY_TYPE.items()
        }
        for transaction_type, code, title in self.repository.get_user_categories(
            telegram_user_id
        ):
            catalog.setdefault(transaction_type, {})[code] = title
        return catalog

    @staticmethod
    def _category_titles(category_catalog: dict[str, dict[str, str]]) -> dict[str, str]:
        titles: dict[str, str] = {}
        for entries in category_catalog.values():
            for code, title in entries.items():
                titles.setdefault(code, title)
        return titles

    @staticmethod
    def _target_currency(plan: AskQueryPlan, main_currency: str) -> str:
        if len(plan.currencies) == 1:
            return plan.currencies[0]
        return main_currency

    @staticmethod
    def _unconverted_note(result: CalculationResult) -> str:
        if not result.unconverted:
            return ""
        detail = ", ".join(
            f"{count} {symbol_for(currency)}"
            for currency, count in result.unconverted.items()
        )
        return f"Часть операций не приведена к {result.currency} из-за отсутствия сохранённого курса ({detail})."

    @staticmethod
    def _wants_list(question: str) -> bool:
        lowered = (question or "").lower()
        return any(marker in lowered for marker in _LIST_MARKERS) or bool(
            _NEWEST_RE.search(lowered)
        )

    @staticmethod
    def _wants_exchange(question: str) -> bool:
        lowered = (question or "").lower()
        return any(marker in lowered for marker in _EXCHANGE_MARKERS)

    @staticmethod
    def _number_in_question(question: str) -> Optional[int]:
        match = re.search(r"\b(\d{1,3})\b", question or "")
        return int(match.group(1)) if match else None

    def _build_list_answer(self, question, result, rows, category_titles) -> AskResult:
        total_count = len(rows)
        newest_first = bool(_NEWEST_RE.search((question or "").lower()))
        requested = self._number_in_question(question)
        if newest_first:
            shown = list(reversed(rows))
            cap = requested if requested is not None and 1 <= requested <= 60 else 60
            shown = shown[:cap]
        else:
            cap = requested if requested is not None and 1 <= requested <= 60 else None
            shown = rows[:cap] if cap else rows
        total_minor = result.total_minor if result.total_count else None
        text = build_list_text(
            shown,
            category_titles,
            result.currency,
            total_minor,
            result.unconverted,
            self.config.app_timezone,
            total=total_count,
        )
        return self._text(text)

    def _headline_parts(
        self, plan: AskQueryPlan, category_catalog: dict[str, dict[str, str]]
    ) -> tuple[str, str]:
        titles = self._category_titles(category_catalog)
        type_label = transaction_type_label(plan.transaction_type)
        category_names = [titles.get(code, code) for code in plan.categories]
        title = type_label
        if len(category_names) == 1:
            title = f"{type_label} на «{category_names[0]}»"
        elif len(category_names) > 1:
            title = f"{type_label} по категориям: {', '.join(category_names)}"
        currency_hint = (
            f"в валюте {symbol_for(plan.currencies[0])}"
            if len(plan.currencies) == 1
            else ""
        )
        return title, currency_hint

    def _output_preference(self, plan: AskQueryPlan, result: CalculationResult) -> str:
        if plan.output_preference == ASK_OUTPUT_TEXT:
            return ASK_OUTPUT_TEXT
        if plan.output_preference == ASK_OUTPUT_INFOGRAPHIC:
            return ASK_OUTPUT_INFOGRAPHIC
        if (
            result.group_by != ASK_GROUP_BY_NONE
            and result.metric == ASK_METRIC_SUM
            and len(result.series) >= 2
        ):
            return ASK_OUTPUT_INFOGRAPHIC
        return ASK_OUTPUT_TEXT

    def _build_text_answer(
        self, plan: AskQueryPlan, result: CalculationResult, access_scope, main_currency
    ) -> AskResult:
        category_catalog = self._category_catalog(access_scope.telegram_user_id)
        title, currency_hint = self._headline_parts(plan, category_catalog)
        subtitle = period_description(
            plan.date_from_utc, plan.date_to_utc, self.config.app_timezone
        )
        scope_note = scope_description(
            plan.data_scope, access_scope.family_id is not None
        )
        full_title = f"{title} {currency_hint}".strip()
        text = self.renderer.build_text_answer(
            result,
            title=full_title,
            subtitle=subtitle,
            scope_note=scope_note,
            has_data_in_base_currency=result.total_count > 0,
        )
        return self._text(text)

    def _build_infographic(
        self, plan: AskQueryPlan, result: CalculationResult, access_scope
    ) -> AskResult:
        category_catalog = self._category_catalog(access_scope.telegram_user_id)
        title, currency_hint = self._headline_parts(plan, category_catalog)
        subtitle = period_description(
            plan.date_from_utc, plan.date_to_utc, self.config.app_timezone
        )
        scope_note = scope_description(
            plan.data_scope, access_scope.family_id is not None
        )
        notes = self._unconverted_note(result)
        image_path = self.renderer.render_chart(
            result,
            title=f"{title} {currency_hint}".strip(),
            subtitle=subtitle,
            notes=notes,
        )
        caption = f"{title} {subtitle}.\nИтого: {format_minor(result.total_minor, result.currency)}"
        if notes:
            caption += f"\n{notes}"
        caption += f"\nУчтены {scope_note}."
        result_object = AskResult(
            output_type=ASK_OUTPUT_INFOGRAPHIC, image_path=image_path, caption=caption
        )
        try:
            result_object.validate()
        except ValueError:
            return self._text("Не удалось сформировать ответ.")
        return result_object

    def _text(self, message: str) -> AskResult:
        return AskResult(output_type=ASK_OUTPUT_TEXT, text=message)

    def _allow_request(self, telegram_user_id: int) -> bool:
        now = time.monotonic()
        window_start = now - RATE_LIMIT_WINDOW_SEC
        history = self._history[telegram_user_id]
        while history and history[0] < window_start:
            history.popleft()
        if len(history) >= RATE_LIMIT_PER_MINUTE:
            return False
        history.append(now)
        return True
