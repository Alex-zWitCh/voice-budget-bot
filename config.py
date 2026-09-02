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
    stt_base_url: str
    stt_api_key: str
    stt_model: str
    stt_timeout_sec: int
    stt_verify_ssl: bool
    groq_fallback_enabled: bool
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
    log_file: Path
    log_max_bytes: int
    log_backup_count: int
    processing_version: str
    max_concurrent_processing: int
    welcome_title: str
    welcome_intro: str
    welcome_footer: str
    welcome_image_path: Path
    ask_enabled: bool
    ask_model: str
    ask_api_url: str
    ask_api_key: str
    ask_timeout_sec: int
    ask_session_ttl_sec: int
    ask_max_rows: int
    ask_max_question_length: int
    ask_max_voice_duration_sec: int
    ask_max_concurrent_processing: int
    ask_temp_dir: Path

    @property
    def ask_api_key_effective(self) -> str:
        return self.ask_api_key or self.deepseek_api_key

    @property
    def ask_api_url_effective(self) -> str:
        return self.ask_api_url or self.deepseek_api_url

    @property
    def ask_model_effective(self) -> str:
        return self.ask_model or self.deepseek_model

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            bot_token=os.getenv("BOT_TOKEN", ""),
            allowed_chat_ids=_csv_ints(os.getenv("ALLOWED_CHAT_IDS", "")),
            allowed_user_ids=_csv_ints(os.getenv("ALLOWED_USER_IDS", "")),
            max_voice_duration_sec=int(os.getenv("MAX_VOICE_DURATION_SEC", "20")),
            stt_base_url=os.getenv("STT_BASE_URL", "https://stt.example.com:7443/v1"),
            stt_api_key=os.getenv("STT_API_KEY", ""),
            stt_model=os.getenv("STT_MODEL", "Systran/faster-whisper-large-v3"),
            stt_timeout_sec=int(os.getenv("STT_TIMEOUT_SEC", "120")),
            stt_verify_ssl=os.getenv("STT_VERIFY_SSL", "true").lower() in {"1", "true", "yes", "on"},
            groq_fallback_enabled=os.getenv("GROQ_FALLBACK_ENABLED", "false").lower() in {"1", "true", "yes", "on"},
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
            log_file=Path(os.getenv("LOG_FILE", "/data/logs/voice-budget-bot.log")),
            log_max_bytes=int(os.getenv("LOG_MAX_BYTES", str(2 * 1024 * 1024))),
            log_backup_count=int(os.getenv("LOG_BACKUP_COUNT", "2")),
            processing_version=os.getenv("PROCESSING_VERSION", "1.0"),
            max_concurrent_processing=int(os.getenv("MAX_CONCURRENT_PROCESSING", "2")),
            welcome_title=os.getenv("WELCOME_TITLE", "SmartExpense 2.0"),
            welcome_intro=os.getenv(
                "WELCOME_INTRO",
                "Отправьте короткое голосовое или текстовое сообщение, чтобы записать доход, расход, напоминание или отложенное списание.",
            ),
            welcome_footer=os.getenv("WELCOME_FOOTER", ""),
            welcome_image_path=Path(os.getenv("WELCOME_IMAGE_PATH", "assets/readme-description.png")),
            ask_enabled=os.getenv("ASK_ENABLED", "true").lower() in {"1", "true", "yes", "on"},
            ask_model=os.getenv("ASK_MODEL", ""),
            ask_api_url=os.getenv("ASK_API_URL", ""),
            ask_api_key=os.getenv("ASK_API_KEY", ""),
            ask_timeout_sec=int(os.getenv("ASK_TIMEOUT_SEC", "30")),
            ask_session_ttl_sec=int(os.getenv("ASK_SESSION_TTL_SEC", "600")),
            ask_max_rows=int(os.getenv("ASK_MAX_ROWS", "500")),
            ask_max_question_length=int(os.getenv("ASK_MAX_QUESTION_LENGTH", "2000")),
            ask_max_voice_duration_sec=int(os.getenv("ASK_MAX_VOICE_DURATION_SEC", "60")),
            ask_max_concurrent_processing=int(os.getenv("ASK_MAX_CONCURRENT_PROCESSING", "1")),
            ask_temp_dir=Path(os.getenv("ASK_TEMP_DIR", "/tmp/voice-budget-bot/ask")),
        )

    def validate(self) -> None:
        missing = []
        if not self.bot_token:
            missing.append("BOT_TOKEN")
        if not self.stt_api_key:
            missing.append("STT_API_KEY")
        if not self.deepseek_api_key:
            missing.append("DEEPSEEK_API_KEY")
        if self.groq_fallback_enabled and not self.groq_api_key:
            missing.append("GROQ_API_KEY")
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")
        if self.max_voice_duration_sec <= 0:
            raise ValueError("MAX_VOICE_DURATION_SEC must be positive")
        if self.max_concurrent_processing <= 0:
            raise ValueError("MAX_CONCURRENT_PROCESSING must be positive")
        if self.ask_session_ttl_sec <= 0:
            raise ValueError("ASK_SESSION_TTL_SEC must be positive")
        if self.ask_max_rows <= 0:
            raise ValueError("ASK_MAX_ROWS must be positive")
        if self.ask_max_question_length <= 0:
            raise ValueError("ASK_MAX_QUESTION_LENGTH must be positive")
        if self.ask_max_voice_duration_sec <= 0:
            raise ValueError("ASK_MAX_VOICE_DURATION_SEC must be positive")
        if self.ask_max_concurrent_processing <= 0:
            raise ValueError("ASK_MAX_CONCURRENT_PROCESSING must be positive")
