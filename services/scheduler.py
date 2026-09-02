import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from categories import CURRENCY_SYMBOLS
from database import add_recurrence
from schemas import ParsedTransaction
from services.reports import (
    build_previous_month_expense_chart,
    build_previous_month_income_chart,
    export_transactions_csv_gz,
    previous_month_period,
)

logger = logging.getLogger(__name__)

MONTHLY_REPORT_CATCH_UP_DAYS = 3


class ScheduledEventRunner:
    def __init__(self, bot, db, config):
        self.bot = bot
        self.db = db
        self.config = config
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="scheduled-events", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.process_due_events()
            except Exception:
                logger.exception("Scheduled event processing failed")
            self._stop.wait(60)

    def process_due_events(self) -> None:
        now = datetime.now(timezone.utc)
        for event in self.db.get_due_scheduled_events(now):
            self._process_event(event, now)
        self._process_monthly_reports(now)
        self.db.clean_expired_pending()

    def _process_event(self, event, now: datetime) -> None:
        if event.event_type == "DEFERRED_EXPENSE":
            self._process_deferred_expense(event)
        else:
            self._send_reminder(event)

        if event.recurrence == "none":
            self.db.complete_scheduled_event(event.id, now)
        else:
            self.db.reschedule_event(
                event.id,
                add_recurrence(event.notify_at_utc, event.recurrence),
                add_recurrence(event.event_at_utc, event.recurrence),
                now,
            )

    def _process_deferred_expense(self, event) -> None:
        parsed = ParsedTransaction(
            transaction_type=event.transaction_type or "EXPENSE",
            amount_minor=event.amount_minor or 0,
            currency=event.currency or "RUB",
            category=event.category or "OTHER",
            description=event.description or event.title,
            confidence=float(event.deepseek_confidence or 1),
        )
        transaction_id = self.db.create_transaction(
            telegram_chat_id=event.telegram_chat_id,
            telegram_message_id=_scheduled_message_id(event.id, event.event_at_utc),
            telegram_user_id=event.telegram_user_id,
            parsed=parsed,
            transcript=event.transcript,
            message_date_utc=datetime.now(timezone.utc),
            voice_duration_sec=0,
            config=self.config,
        )
        amount = _format_amount(parsed.amount_minor, parsed.currency)
        if transaction_id:
            self.bot.send_message(event.telegram_chat_id, f"✅ Отложенное списание зафиксировано\n\n{amount}\n{event.title}")
        else:
            self.bot.send_message(event.telegram_chat_id, f"ℹ️ Отложенное списание уже было зафиксировано\n\n{amount}\n{event.title}")

    def _send_reminder(self, event) -> None:
        event_at = _format_local(event.event_at_utc, self.config.app_timezone)
        self.bot.send_message(event.telegram_chat_id, f"🔔 Напоминание\n\nВ {event_at}: {event.title}")

    def _process_monthly_reports(self, now_utc: datetime) -> None:
        now_local = now_utc.astimezone(ZoneInfo(self.config.app_timezone))
        if now_local.day > MONTHLY_REPORT_CATCH_UP_DAYS:
            return
        start_local, end_local, period_key = previous_month_period(self.config.app_timezone, now_local)
        start_utc = start_local.astimezone(timezone.utc)
        end_utc = end_local.astimezone(timezone.utc)
        for target in self.db.list_previous_month_report_targets(start_utc, end_utc):
            user_id = target["telegram_user_id"]
            chat_id = target["telegram_chat_id"]
            if self.db.report_delivery_exists(user_id, "monthly_report_bundle", period_key):
                continue
            paths = []
            try:
                report_dir = self.config.temp_audio_dir / "reports"
                for builder in (build_previous_month_expense_chart, build_previous_month_income_chart):
                    chart_path, caption = builder(self.db, user_id, self.config.app_timezone, report_dir)
                    if chart_path:
                        paths.append(chart_path)
                        with open(chart_path, "rb") as image:
                            self.bot.send_photo(chat_id, image, caption=f"Автоматический отчет за прошлый месяц\n\n{caption}")
                    else:
                        self.bot.send_message(chat_id, f"Автоматический отчет за прошлый месяц\n\n{caption}")

                csv_path = export_transactions_csv_gz(
                    self.db,
                    user_id,
                    self.config.app_timezone,
                    report_dir,
                    start_local,
                    end_local,
                    f"monthly-{period_key}",
                )
                paths.append(csv_path)
                with open(csv_path, "rb") as file:
                    self.bot.send_document(
                        chat_id,
                        file,
                        visible_file_name=csv_path.name,
                        caption=f"CSV-выгрузка всех записей за {start_local:%m.%Y}.",
                    )
                self.db.record_report_delivery(user_id, chat_id, "monthly_report_bundle", period_key)
            except Exception:
                logger.exception("Monthly report bundle failed user_id=%s period=%s", user_id, period_key)
            finally:
                for path in paths:
                    path.unlink(missing_ok=True)


def calendar_text(db, telegram_user_id: int, app_timezone: str, months: int = 2) -> str:
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=31 * months)
    rows = db.list_calendar_events(telegram_user_id, now, end)
    if not rows:
        return "Календарь на ближайшие 2 месяца пуст."

    lines = ["Календарь на ближайшие 2 месяца:"]
    for item in rows:
        moment = _format_local(item["event_at_utc"], app_timezone)
        kind = "Списание" if item["event_type"] == "DEFERRED_EXPENSE" else "Напоминание"
        recurrence = _recurrence_title(item["recurrence"])
        amount = ""
        if item["amount_minor"] is not None and item["currency"]:
            amount = f" {_format_amount(item['amount_minor'], item['currency'])}"
        lines.append(f"{moment} | {kind}{amount} | {item['title']}{recurrence}")
    return "\n".join(lines)


def _scheduled_message_id(event_id: int, event_at) -> int:
    event_at_utc = _as_utc(event_at)
    return -(event_id * 10_000_000_000 + int(event_at_utc.timestamp()) % 10_000_000_000)


def _format_amount(amount_minor: int, currency: str) -> str:
    major = amount_minor // 100
    minor = amount_minor % 100
    amount = f"{major:,}".replace(",", " ")
    if minor:
        amount = f"{amount},{minor:02d}"
    return f"{amount} {CURRENCY_SYMBOLS.get(currency, currency)}"


def _format_local(value, app_timezone: str) -> str:
    return _as_utc(value).astimezone(ZoneInfo(app_timezone)).strftime("%d.%m.%Y %H:%M")


def _recurrence_title(recurrence: str) -> str:
    return {
        "daily": " (ежедневно)",
        "weekly": " (еженедельно)",
        "monthly": " (ежемесячно)",
        "yearly": " (ежегодно)",
    }.get(recurrence, "")


def _as_utc(value) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
