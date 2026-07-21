import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from categories import CURRENCY_SYMBOLS
from database import add_recurrence
from schemas import ParsedTransaction

logger = logging.getLogger(__name__)


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

