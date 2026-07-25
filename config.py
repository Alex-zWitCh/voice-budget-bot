import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


def _csv_ints(value: str) -> set[int]:
    if not value.strip():
        return set()
    return {int(part.strip()) for part in value.split(",") if part.strip()}


@dataclass(frozen=True)
class Config:
    bot_token: str
    allowed_chat_ids: set[int]
    allowed_user_ids: set[int]
    max_voice_duration_sec: int
    groq_api_key: str
    groq_base_url: str
    groq_stt_model: str
    groq_timeout_sec: int
    deepseek_api_key: str
    deepseek_api_url: str
    deepseek_model: str
    deepseek_timeout_sec: int
    min_deepseek_confidence: float
    reencode_voice: bool
    voice_sample_rate: int
    voice_bitrate: str
    temp_audio_dir: Path
    sqlite_db_path: Path
    app_timezone: str
    log_level: str
    processing_version: str
    max_concurrent_processing: int
    welcome_title: str
    welcome_intro: str
    welcome_footer: str
    welcome_image_path: Path

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            bot_token=os.getenv("BOT_TOKEN", ""),
            allowed_chat_ids=_csv_ints(os.getenv("ALLOWED_CHAT_IDS", "")),
            allowed_user_ids=_csv_ints(os.getenv("ALLOWED_USER_IDS", "")),
            max_voice_duration_sec=int(os.getenv("MAX_VOICE_DURATION_SEC", "8")),
            groq_api_key=os.getenv("GROQ_API_KEY", ""),
            groq_base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
            groq_stt_model=os.getenv("GROQ_STT_MODEL", "whisper-large-v3"),
            groq_timeout_sec=int(os.getenv("GROQ_TIMEOUT_SEC", "30")),
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            deepseek_api_url=os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions"),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
            deepseek_timeout_sec=int(os.getenv("DEEPSEEK_TIMEOUT_SEC", "30")),
            min_deepseek_confidence=float(os.getenv("MIN_DEEPSEEK_CONFIDENCE", "0.70")),
            reencode_voice=os.getenv("REENCODE_VOICE", "true").lower() in {"1", "true", "yes", "on"},
            voice_sample_rate=int(os.getenv("VOICE_SAMPLE_RATE", "16000")),
            voice_bitrate=os.getenv("VOICE_BITRATE", "16k"),
            temp_audio_dir=Path(os.getenv("TEMP_AUDIO_DIR", "/tmp/voice-budget-bot")),
            sqlite_db_path=Path(os.getenv("SQLITE_DB_PATH", "/data/voice_budget_bot.db")),
            app_timezone=os.getenv("APP_TIMEZONE", "Europe/Moscow"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            processing_version=os.getenv("PROCESSING_VERSION", "1.0"),
            max_concurrent_processing=int(os.getenv("MAX_CONCURRENT_PROCESSING", "2")),
            welcome_title=os.getenv("WELCOME_TITLE", "SmartExpense 2.0"),
            welcome_intro=os.getenv(
                "WELCOME_INTRO",
                "Отправьте короткое голосовое сообщение, чтобы записать доход, расход, напоминание или отложенное списание.",
            ),
            welcome_footer=os.getenv("WELCOME_FOOTER", ""),
            welcome_image_path=Path(os.getenv("WELCOME_IMAGE_PATH", "assets/readme-description.png")),
        )

    def validate(self) -> None:
        missing = []
        if not self.bot_token:
            missing.append("BOT_TOKEN")
        if not self.groq_api_key:
            missing.append("GROQ_API_KEY")
        if not self.deepseek_api_key:
            missing.append("DEEPSEEK_API_KEY")
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")
        if self.max_voice_duration_sec <= 0:
            raise ValueError("MAX_VOICE_DURATION_SEC must be positive")
        if self.max_concurrent_processing <= 0:
            raise ValueError("MAX_CONCURRENT_PROCESSING must be positive")
