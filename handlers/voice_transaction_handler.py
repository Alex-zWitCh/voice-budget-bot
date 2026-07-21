import logging
import time
import uuid

from categories import CURRENCY_SYMBOLS, category_title
from schemas import ValidationError, validate_deepseek_payload
from services.audio_converter import AudioConversionError, normalize_voice
from services.deepseek_transaction_parser import DeepSeekParserError
from services.groq_transcriber import TranscriptionError

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
        if not self._is_allowed(message):
            return

        self.db.upsert_user_and_chat(message)

        if self.db.transaction_exists(message.chat.id, message.message_id):
            self.db.record_event(message, "duplicate", "duplicate")
            return

        if message.voice.duration > self.config.max_voice_duration_sec:
            self.db.record_event(message, "rejected_too_long", "too_long")
            self.bot.reply_to(
                message,
                "⚠️ Голосовое сообщение длиннее 8 секунд и не обработано.\n"
                "Отправьте одну короткую запись дохода или расхода.",
            )
            return

        acquired = self.semaphore.acquire(blocking=False)
        if not acquired:
            self.bot.reply_to(message, "Сейчас обрабатываю другие записи. Повторите через несколько секунд.")
            return

        original_path = normalized_path = None
        try:
            original_path = self._download_voice(message)
            audio_path = original_path
            if self.config.reencode_voice:
                normalized_path = original_path.with_name(f"{original_path.stem}_normalized.ogg")
                audio_path = normalize_voice(original_path, normalized_path, self.config.voice_sample_rate, self.config.voice_bitrate)

            category_catalog = self.db.get_category_catalog(message.from_user.id)
            transcript = self.transcriber.transcribe(audio_path)
            payload = self.parser.parse(transcript, category_catalog)
            parsed = validate_deepseek_payload(payload, transcript, self.config.min_deepseek_confidence, category_catalog)
            transaction_id = self.db.save_transaction(message, parsed, transcript, self.config)
            status = f"saved_{parsed.transaction_type.lower()}" if transaction_id else "duplicate"
            self.db.record_event(message, status, duration_ms=int((time.monotonic() - started) * 1000))
            if transaction_id:
                self.bot.reply_to(message, self._success_text(message, parsed, category_catalog), reply_markup=_delete_keyboard(transaction_id))
        except AudioConversionError:
            self._fail(message, "transcription_failed", "ffmpeg_failed", "⚠️ Не удалось подготовить голосовое сообщение.\nПовторите запись ещё раз.")
        except TranscriptionError:
            self._fail(message, "transcription_failed", "groq_failed", "⚠️ Речь не распознана.\nПовторите сообщение немного громче и короче.")
        except DeepSeekParserError:
            self._fail(message, "parse_failed", "deepseek_failed", "⚠️ Сервис распознавания временно недоступен.\nПопробуйте отправить сообщение позже.")
        except ValidationError as exc:
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

    def _is_allowed(self, message) -> bool:
        chat_id = message.chat.id
        user_id = message.from_user.id if message.from_user else 0
        if self.config.allowed_user_ids and user_id not in self.config.allowed_user_ids:
            return False
        if message.chat.type in {"group", "supergroup"}:
            return chat_id in self.config.allowed_chat_ids
        if self.config.allowed_chat_ids:
            return chat_id in self.config.allowed_chat_ids
        return message.chat.type == "private"

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


def _format_amount(amount_minor: int, currency: str) -> str:
    major = amount_minor // 100
    minor = amount_minor % 100
    amount = f"{major:,}".replace(",", " ")
    if minor:
        amount = f"{amount},{minor:02d}"
    return f"{amount} {CURRENCY_SYMBOLS.get(currency, currency)}"


def _delete_keyboard(transaction_id: int):
    from telebot import types

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("Удалить запись", callback_data=f"delete_tx:{transaction_id}"))
    return keyboard
