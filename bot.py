import logging
import os
import signal
import sys
import threading

import telebot
from telebot import apihelper

from config import Config
from database import Database
from handlers.voice_transaction_handler import VoiceTransactionHandler
from services.deepseek_transaction_parser import DeepSeekTransactionParser
from services.groq_transcriber import GroqTranscriber


def build_bot(config: Config):
    if proxy_url := os.getenv("PROXY_URL", ""):
        apihelper.proxy = {"https": proxy_url}
    bot = telebot.TeleBot(config.bot_token)
    db = Database(config.sqlite_db_path)
    semaphore = threading.BoundedSemaphore(config.max_concurrent_processing)
    handler = VoiceTransactionHandler(
        bot=bot,
        db=db,
        config=config,
        transcriber=GroqTranscriber(config.groq_api_key, config.groq_base_url, config.groq_stt_model, config.groq_timeout_sec),
        parser=DeepSeekTransactionParser(config.deepseek_api_key, config.deepseek_api_url, config.deepseek_model, config.deepseek_timeout_sec),
        semaphore=semaphore,
    )

    @bot.message_handler(commands=["start", "help"])
    def start(message):
        bot.reply_to(
            message,
            "Voice Budget Bot готов.\n\n"
            "Отправьте короткое голосовое сообщение до 8 секунд с одной операцией: "
            "например, «пятьсот продукты молоко» или «получил зарплату сто тысяч».",
        )

    @bot.message_handler(content_types=["voice"])
    def voice(message):
        handler.handle(message)

    @bot.message_handler(content_types=["text", "audio", "video", "video_note", "document", "photo", "sticker", "contact", "location"])
    def unsupported(message):
        if message.chat.type == "private":
            bot.reply_to(message, "Первая версия бота принимает только голосовые сообщения до 8 секунд.")

    return bot


def main() -> int:
    config = Config.from_env()
    try:
        config.validate()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    bot = build_bot(config)

    def stop(_signum, _frame):
        logging.getLogger(__name__).info("Stopping bot polling")
        bot.stop_polling()
        sys.exit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    logging.getLogger(__name__).info("Voice Budget Bot polling is starting")
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

