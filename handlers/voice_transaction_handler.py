import logging
import pprint
import re
import time
import uuid
from datetime import datetime
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from categories import CURRENCY_SYMBOLS, category_title
from schemas import ParsedExchange, ParsedScheduledEvent, ValidationError, validate_voice_intent
from services.access import is_allowed_message
from services.audio_converter import AudioConversionError, normalize_voice
from services.deepseek_transaction_parser import DeepSeekParserError
from services.stt_transcriber import TranscriptionError

logger = logging.getLogger(__name__)


class VoiceTransactionHandler:
    def __init__(self, bot, db, config, transcriber, parser, semaphore):
        self.bot = bot
        self.db = db
        self.config = config
        self.transcriber = transcriber
        self.parser = parser
        self.semaphore = semaphore

    def handle(self, message) -> None:
        started = time.monotonic()
        if not is_allowed_message(self.config, message):
            return

        if self.pending_exchange(message.from_user.id):
            self.bot.reply_to(message, "Сначала укажите курс конвертации числом (например: 92).")
            return

        self.db.upsert_user_and_chat(message)

        if self._already_processed(message):
            self.db.record_event(message, "duplicate", "duplicate")
            return

        if message.voice.duration > self.config.max_voice_duration_sec:
            self.db.record_event(message, "rejected_too_long", "too_long")
            self.bot.reply_to(
                message,
                f"⚠️ Сообщение слишком длинное: {message.voice.duration} сек (лимит — {self.config.max_voice_duration_sec} сек).\n"
                "Запишите короче и отправьте ещё раз.",
            )
            return

        acquired = self.semaphore.acquire(blocking=False)
        if not acquired:
            self.bot.reply_to(message, "Сейчас обрабатываю другие записи. Повторите через несколько секунд.")
            return

        original_path = normalized_path = None
        transcript = ""
        payload = None
        try:
            self.bot.reply_to(message, "🎙️ Распознаю речь…")
            original_path = self._download_voice(message)
            audio_path = original_path
            if self.config.reencode_voice:
                normalized_path = original_path.with_name(f"{original_path.stem}_normalized.ogg")
                audio_path = normalize_voice(original_path, normalized_path, self.config.voice_sample_rate, self.config.voice_bitrate)

            category_catalog = self.db.get_category_catalog(message.from_user.id)
            transcript = self.transcriber.transcribe(audio_path)
            self._process_transcript(message, started, transcript, category_catalog)
        except AudioConversionError as exc:
            logger.warning(
                "ffmpeg conversion failed chat_id=%s message_id=%s user_id=%s stderr=%r",
                message.chat.id,
                message.message_id,
                message.from_user.id,
                _truncate(exc.stderr, 2000),
            )
            self._fail(message, "transcription_failed", "ffmpeg_failed", "⚠️ Не удалось подготовить голосовое сообщение.\nПовторите запись ещё раз.")
        except TranscriptionError:
            self._fail(message, "transcription_failed", "groq_failed", "⚠️ Речь не распознана.\nПовторите сообщение немного громче и короче.")
        except DeepSeekParserError as exc:
            self._log_processing_diagnostics(message, started, "deepseek_failed", transcript, payload, str(exc))
            self._fail(message, "parse_failed", "deepseek_failed", "⚠️ Сервис распознавания временно недоступен.\nПопробуйте отправить сообщение позже.")
        except ValidationError as exc:
            self._log_processing_diagnostics(message, started, exc.code, transcript, payload, exc.user_message)
            self._fail(message, exc.code, exc.code, exc.user_message)
        except Exception:
            logger.exception(
                "Unhandled processing error chat_id=%s message_id=%s user_id=%s",
                message.chat.id,
                message.message_id,
                message.from_user.id,
            )
            self._fail(message, "parse_failed", "unexpected", "⚠️ Не удалось обработать голосовое сообщение.")
        finally:
            for path in (original_path, normalized_path):
                if path:
                    path.unlink(missing_ok=True)
            self.semaphore.release()

    def handle_text(self, message) -> None:
        """Process a plain text message through the same parser path as STT output."""
        started = time.monotonic()
        if not is_allowed_message(self.config, message):
            return

        transcript = (message.text or "").strip()
        if not transcript:
            return

        self.db.upsert_user_and_chat(message)
        if self._already_processed(message):
            self.db.record_event(message, "duplicate", "duplicate")
            return

        acquired = self.semaphore.acquire(blocking=False)
        if not acquired:
            self.bot.reply_to(message, "Сейчас обрабатываю другие записи. Повторите через несколько секунд.")
            return

        payload = None
        try:
            category_catalog = self.db.get_category_catalog(message.from_user.id)
            payload = self._process_transcript(message, started, transcript, category_catalog)
        except DeepSeekParserError as exc:
            self._log_processing_diagnostics(message, started, "deepseek_failed", transcript, payload, str(exc))
            self._fail(message, "parse_failed", "deepseek_failed", "⚠️ Сервис распознавания временно недоступен.\nПопробуйте отправить сообщение позже.")
        except ValidationError as exc:
            self._log_processing_diagnostics(message, started, exc.code, transcript, payload, exc.user_message)
            self._fail(message, exc.code, exc.code, exc.user_message)
        except Exception:
            logger.exception(
                "Unhandled text processing error chat_id=%s message_id=%s user_id=%s",
                message.chat.id,
                message.message_id,
                message.from_user.id,
            )
            self._fail(message, "parse_failed", "unexpected", "⚠️ Не удалось обработать текстовое сообщение.")
        finally:
            self.semaphore.release()

    def _process_transcript(self, message, started: float, transcript: str, category_catalog: dict):
        now_local = datetime.now(ZoneInfo(self.config.app_timezone)).isoformat(timespec="seconds")
        payload = self.parser.parse_voice_intent(transcript, category_catalog, now_local, self.config.app_timezone)
        parsed = validate_voice_intent(payload, transcript, self.config.min_deepseek_confidence, category_catalog, self.config.app_timezone)
        if isinstance(parsed, ParsedExchange):
            self._handle_exchange(message, started, parsed, transcript)
            return payload
        if isinstance(parsed, ParsedScheduledEvent):
            event_id = self.db.create_scheduled_event(message, parsed, transcript, self.config)
            self.db.record_event(message, "scheduled" if event_id else "duplicate", duration_ms=int((time.monotonic() - started) * 1000))
            if event_id:
                self.bot.reply_to(message, self._scheduled_text(parsed), reply_markup=_delete_event_keyboard(event_id))
            return payload
        transaction_id = self.db.save_transaction(message, parsed, transcript, self.config)
        status = f"saved_{parsed.transaction_type.lower()}" if transaction_id else "duplicate"
        self.db.record_event(message, status, duration_ms=int((time.monotonic() - started) * 1000))
        if transaction_id:
            self.bot.reply_to(
                message,
                self._success_text(message, parsed, category_catalog),
                reply_markup=_success_keyboard(transaction_id, self.db.get_family_for_user(message.from_user.id) is not None),
            )
        return payload

    def pending_exchange(self, telegram_user_id: int) -> bool:
        return self.db.load_pending_exchange(telegram_user_id) is not None

    def handle_rate_reply(self, message) -> bool:
        state = self.db.load_pending_exchange(message.from_user.id)
        if not state:
            return False
        if (message.text or "").lstrip().startswith("/"):
            self.db.drop_pending_exchange(message.from_user.id)
            self.bot.reply_to(message, "Конвертация отменена.")
            return True
        rate = _extract_rate(message.text or "")
        parsed = state["parsed"]
        if rate is None:
            self.db.save_pending_exchange(
                message.from_user.id,
                parsed,
                state["transcript"],
                state.get("chat_id"),
            )
            self.bot.reply_to(
                message,
                f"Не понял курс. Ответьте числом, например: {_format_amount(parsed.from_amount_minor, parsed.from_currency)} → {parsed.to_currency}",
            )
            return True
        self.db.drop_pending_exchange(message.from_user.id)
        parsed = parsed.with_rate(rate)
        self._save_exchange(message, state["transcript"], parsed)
        return True

    def _handle_exchange(self, message, started: float, parsed: ParsedExchange, transcript: str) -> None:
        if parsed.rate is None:
            self.db.save_pending_exchange(message.from_user.id, parsed, transcript, message.chat.id)
            self.db.record_event(message, "rate_required", "rate_required", duration_ms=int((time.monotonic() - started) * 1000))
            from_amount = _format_amount(parsed.from_amount_minor, parsed.from_currency)
            self.bot.reply_to(
                message,
                f"📤 Конвертация: {from_amount} → {parsed.to_currency}\n"
                "Укажите курс, по которому вы перевели деньги. Ответьте числом, например: 92",
            )
            return
        self._save_exchange(message, transcript, parsed)

    def _save_exchange(self, message, transcript: str, parsed: ParsedExchange) -> None:
        expense_id = self.db.create_exchange(message, parsed, transcript, self.config)
        self.db.record_event(message, "saved_exchange" if expense_id else "duplicate")
        if expense_id:
            from_amount = _format_amount(parsed.from_amount_minor, parsed.from_currency)
            to_amount = _format_amount(parsed.to_amount_minor or 0, parsed.to_currency)
            rate_text = f"курс {_format_rate(parsed.rate)}"
            self.bot.reply_to(
                message,
                f"✅ Конвертация\n\n{from_amount} → {to_amount}\n{rate_text}\n"
                "Созданы два перевода: расход в исходной валюте и доход в целевой.",
                reply_markup=_delete_exchange_keyboard(expense_id),
            )

    def _already_processed(self, message) -> bool:
        return self.db.transaction_exists(message.chat.id, message.message_id) or self.db.scheduled_event_exists(message.chat.id, message.message_id)

    def _download_voice(self, message):
        base_dir = self.config.temp_audio_dir / str(message.chat.id) / str(message.from_user.id)
        base_dir.mkdir(parents=True, exist_ok=True)
        path = base_dir / f"{message.message_id}_{uuid.uuid4().hex}.ogg"
        file_info = self.bot.get_file(message.voice.file_id)
        downloaded = self.bot.download_file(file_info.file_path)
        with open(path, "wb") as output:
            output.write(downloaded)
        return path

    def _success_text(self, message, parsed, category_catalog: dict) -> str:
        amount = _format_amount(parsed.amount_minor, parsed.currency)
        category = category_catalog.get(parsed.transaction_type, {}).get(parsed.category) or category_title(parsed.transaction_type, parsed.category)
        noun = "расход" if parsed.transaction_type == "EXPENSE" else "доход"
        if message.chat.type in {"group", "supergroup"}:
            name = message.from_user.first_name or message.from_user.username or "Пользователь"
            return f"✅ {name}: записан {noun} {amount}\n{category} — {parsed.description or category.lower()}"
        return f"✅ Записан {noun}\n\n{amount}\nКатегория: {category}\nОписание: {parsed.description or category.lower()}"

    def _fail(self, message, status: str, error_code: str, text: str) -> None:
        self.db.record_event(message, status, error_code)
        self.bot.reply_to(message, text)

    def _log_processing_diagnostics(self, message, started: float, reason: str, transcript: str, payload, details: str) -> None:
        logger.warning(
            "Voice transaction rejected chat_id=%s message_id=%s user_id=%s reason=%s duration_ms=%s transcript=%r payload=%s details=%r",
            message.chat.id,
            message.message_id,
            message.from_user.id if message.from_user else 0,
            reason,
            int((time.monotonic() - started) * 1000),
            _truncate(transcript, 2000),
            _truncate(pprint.pformat(payload, sort_dicts=True, compact=True), 4000),
            _truncate(details, 1000),
        )

    def _scheduled_text(self, event: ParsedScheduledEvent) -> str:
        event_at = event.event_at_utc.astimezone(ZoneInfo(self.config.app_timezone)).strftime("%d.%m.%Y %H:%M")
        recurrence = {
            "none": "",
            "daily": "\nПовтор: ежедневно",
            "weekly": "\nПовтор: еженедельно",
            "monthly": "\nПовтор: ежемесячно",
            "yearly": "\nПовтор: ежегодно",
        }.get(event.recurrence, "")
        if event.event_type == "DEFERRED_EXPENSE" and event.transaction:
            amount = _format_amount(event.transaction.amount_minor, event.transaction.currency)
            return f"✅ Отложенное списание запланировано\n\n{event_at}\n{amount}\n{event.title}{recurrence}"
        return f"✅ Напоминание запланировано\n\n{event_at}\n{event.title}{recurrence}"


def _format_amount(amount_minor: int, currency: str) -> str:
    major = amount_minor // 100
    minor = amount_minor % 100
    amount = f"{major:,}".replace(",", " ")
    if minor:
        amount = f"{amount},{minor:02d}"
    return f"{amount} {CURRENCY_SYMBOLS.get(currency, currency)}"


def _success_keyboard(transaction_id: int, has_family: bool):
    from telebot import types

    keyboard = types.InlineKeyboardMarkup()
    if has_family:
        keyboard.add(
            types.InlineKeyboardButton("Семейное", callback_data=f"scope_tx:{transaction_id}:family"),
            types.InlineKeyboardButton("Личное", callback_data=f"scope_tx:{transaction_id}:personal"),
        )
    keyboard.add(types.InlineKeyboardButton("Удалить запись", callback_data=f"delete_tx:{transaction_id}"))
    return keyboard


def _delete_keyboard(transaction_id: int):
    from telebot import types

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Удалить запись", callback_data=f"delete_tx:{transaction_id}"))
    return keyboard


def _delete_event_keyboard(event_id: int):
    from telebot import types

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Удалить событие", callback_data=f"delete_event:{event_id}"))
    return keyboard


def _delete_exchange_keyboard(expense_id: int):
    from telebot import types

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Удалить запись", callback_data=f"delete_tx:{expense_id}"))
    return keyboard


_RATE_RE = re.compile(r"(\d{1,15}(?:[.,]\d{1,10})?)")


def _extract_rate(text: str) -> Decimal | None:
    match = _RATE_RE.search(text)
    if not match:
        return None
    try:
        rate = Decimal(match.group(1).replace(",", "."))
    except InvalidOperation:
        return None
    return rate if rate > 0 else None


def _format_rate(rate: Decimal | None) -> str:
    if rate is None:
        return "?"
    return f"{rate.normalize():f}"


def _truncate(value: str, limit: int) -> str:
    text = value or ""
    if len(text) <= limit:
        return text
    return text[:limit] + f"...<truncated {len(text) - limit} chars>"
