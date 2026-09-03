import logging
import uuid
from pathlib import Path

from services.ask_service import AskService
from services.access import is_allowed_message
from services.audio_converter import AudioConversionError, normalize_voice
from services.stt_transcriber import TranscriptionError
from schemas import AskResult

logger = logging.getLogger(__name__)


def send_ask_result(bot, chat_id: int, result: AskResult) -> None:
    if result.output_type == "INFOGRAPHIC":
        image_path = result.image_path
        try:
            with open(image_path, "rb") as image:
                bot.send_photo(chat_id, image, caption=result.caption)
        finally:
            image_path.unlink(missing_ok=True)
        return
    bot.send_message(chat_id, result.text)


class AskVoiceHandler:
    def __init__(self, bot, config, transcriber, ask_service: AskService, semaphore):
        self.bot = bot
        self.config = config
        self.transcriber = transcriber
        self.ask_service = ask_service
        self.semaphore = semaphore

    def handle(self, message) -> None:
        if not is_allowed_message(self.config, message):
            return
        if message.voice.duration > self.config.ask_max_voice_duration_sec:
            self.bot.reply_to(
                message,
                f"⚠️ Голосовой вопрос слишком длинный: {message.voice.duration} сек "
                f"(лимит — {self.config.ask_max_voice_duration_sec} сек).\nЗадайте вопрос короче.",
            )
            return
        acquired = self.semaphore.acquire(blocking=False)
        if not acquired:
            self.bot.reply_to(
                message,
                "Сейчас обрабатывается другой аналитический вопрос. Повторите через несколько секунд.",
            )
            return
        original_path = normalized_path = None
        try:
            self.bot.reply_to(message, "🎙️ Распознаю ваш вопрос…")
            original_path = self._download_voice(message)
            audio_path = original_path
            if self.config.reencode_voice:
                normalized_path = original_path.with_name(
                    f"{original_path.stem}_normalized.ogg"
                )
                audio_path = normalize_voice(
                    original_path,
                    normalized_path,
                    self.config.voice_sample_rate,
                    self.config.voice_bitrate,
                )
            transcript = self.transcriber.transcribe(audio_path)
            if not transcript.strip():
                self.bot.reply_to(
                    message,
                    "⚠️ Речь не распознана.\nПовторите вопрос немного громче и короче.",
                )
                return
            self.bot.reply_to(message, "🤖 Анализирую ваши данные…")
            result = self.ask_service.ask(message.from_user.id, transcript, source="voice")
            send_ask_result(self.bot, message.chat.id, result)
        except AudioConversionError:
            logger.warning(
                "ffmpeg ask conversion failed user_id=%s",
                message.from_user.id,
                exc_info=True,
            )
            self.bot.reply_to(
                message,
                "⚠️ Не удалось подготовить голосовой вопрос.\nПовторите запись ещё раз.",
            )
        except TranscriptionError:
            logger.warning(
                "ask transcription failed user_id=%s",
                message.from_user.id,
                exc_info=True,
            )
            self.bot.reply_to(
                message,
                "⚠️ Речь не распознана.\nПовторите вопрос немного громче и короче.",
            )
        except Exception:
            logger.exception(
                "Unhandled ask voice error user_id=%s", message.from_user.id
            )
            self.bot.reply_to(
                message, "⚠️ Не удалось выполнить запрос. Попробуйте ещё раз."
            )
        finally:
            for path in (original_path, normalized_path):
                if path:
                    path.unlink(missing_ok=True)
            self.semaphore.release()

    def _download_voice(self, message) -> Path:
        base_dir = self.config.ask_temp_dir / "voice"
        base_dir.mkdir(parents=True, exist_ok=True)
        path = base_dir / f"{message.from_user.id}_{uuid.uuid4().hex}.ogg"
        file_info = self.bot.get_file(message.voice.file_id)
        downloaded = self.bot.download_file(file_info.file_path)
        with open(path, "wb") as output:
            output.write(downloaded)
        return path
