from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Numeric, String, Text, UniqueConstraint, create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from categories import CATEGORY_BY_TYPE


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255))
    first_name: Mapped[Optional[str]] = mapped_column(String(255))
    last_name: Mapped[Optional[str]] = mapped_column(String(255))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    chat_type: Mapped[str] = mapped_column(String(32))
    title: Mapped[Optional[str]] = mapped_column(String(255))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (UniqueConstraint("telegram_chat_id", "telegram_message_id", name="uq_transactions_telegram_message"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    telegram_message_id: Mapped[int] = mapped_column(BigInteger)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    transaction_type: Mapped[str] = mapped_column(String(16), index=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    category: Mapped[str] = mapped_column(String(64), index=True)
    description: Mapped[str] = mapped_column(Text)
    transcript: Mapped[str] = mapped_column(Text)
    message_date_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    voice_duration_sec: Mapped[int] = mapped_column(Integer)
    groq_model: Mapped[str] = mapped_column(String(64))
    deepseek_model: Mapped[str] = mapped_column(String(64))
    deepseek_confidence: Mapped[float] = mapped_column(Numeric(4, 3))
    processing_version: Mapped[str] = mapped_column(String(32))


class ProcessingEvent(Base):
    __tablename__ = "processing_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    telegram_message_id: Mapped[int] = mapped_column(BigInteger, index=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    status: Mapped[str] = mapped_column(String(64), index=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(64))
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)


class UserCategory(Base):
    __tablename__ = "user_categories"
    __table_args__ = (UniqueConstraint("telegram_user_id", "transaction_type", "code", name="uq_user_categories_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    transaction_type: Mapped[str] = mapped_column(String(16), index=True)
    code: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Database:
    def __init__(self, sqlite_path: Path):
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            f"sqlite:///{sqlite_path}",
            connect_args={"check_same_thread": False, "timeout": 10},
            pool_pre_ping=True,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)

    def upsert_user_and_chat(self, message) -> None:
        now = datetime.now(timezone.utc)
        with self.Session.begin() as session:
            user = session.query(User).filter_by(telegram_user_id=message.from_user.id).first()
            if user:
                user.username = message.from_user.username
                user.first_name = message.from_user.first_name
                user.last_name = message.from_user.last_name
                user.last_seen_at = now
            else:
                session.add(
                    User(
                        telegram_user_id=message.from_user.id,
                        username=message.from_user.username,
                        first_name=message.from_user.first_name,
                        last_name=message.from_user.last_name,
                        first_seen_at=now,
                        last_seen_at=now,
                    )
                )

            chat = session.query(Chat).filter_by(telegram_chat_id=message.chat.id).first()
            if not chat:
                session.add(
                    Chat(
                        telegram_chat_id=message.chat.id,
                        chat_type=message.chat.type,
                        title=getattr(message.chat, "title", None),
                        is_enabled=True,
                    )
                )

    def transaction_exists(self, chat_id: int, message_id: int) -> bool:
        with self.Session() as session:
            return session.query(Transaction).filter_by(telegram_chat_id=chat_id, telegram_message_id=message_id).first() is not None

    def save_transaction(self, message, parsed, transcript: str, config) -> Optional[int]:
        tx = Transaction(
            telegram_chat_id=message.chat.id,
            telegram_message_id=message.message_id,
            telegram_user_id=message.from_user.id,
            transaction_type=parsed.transaction_type,
            amount_minor=parsed.amount_minor,
            currency=parsed.currency,
            category=parsed.category,
            description=parsed.description,
            transcript=transcript,
            message_date_utc=datetime.fromtimestamp(message.date, timezone.utc),
            voice_duration_sec=message.voice.duration,
            groq_model=config.groq_stt_model,
            deepseek_model=config.deepseek_model,
            deepseek_confidence=parsed.confidence,
            processing_version=config.processing_version,
        )
        try:
            with self.Session.begin() as session:
                session.add(tx)
                session.flush()
                transaction_id = tx.id
        except IntegrityError:
            return None
        return transaction_id

    def record_event(self, message, status: str, error_code: Optional[str] = None, duration_ms: Optional[int] = None) -> None:
        with self.Session.begin() as session:
            session.add(
                ProcessingEvent(
                    telegram_chat_id=message.chat.id,
                    telegram_message_id=message.message_id,
                    telegram_user_id=message.from_user.id if message.from_user else 0,
                    status=status,
                    error_code=error_code,
                    duration_ms=duration_ms,
                )
            )

    def get_category_catalog(self, telegram_user_id: int) -> dict:
        catalog = {key: value.copy() for key, value in CATEGORY_BY_TYPE.items()}
        with self.Session() as session:
            rows = (
                session.query(UserCategory)
                .filter_by(telegram_user_id=telegram_user_id, is_active=True)
                .order_by(UserCategory.title.asc())
                .all()
            )
            for row in rows:
                catalog.setdefault(row.transaction_type, {})[row.code] = row.title
        return catalog

    def add_user_category(self, telegram_user_id: int, transaction_type: str, title: str) -> str:
        code = _category_code(title)
        with self.Session.begin() as session:
            existing = (
                session.query(UserCategory)
                .filter_by(telegram_user_id=telegram_user_id, transaction_type=transaction_type, code=code)
                .first()
            )
            if existing:
                existing.title = title
                existing.is_active = True
            else:
                session.add(UserCategory(telegram_user_id=telegram_user_id, transaction_type=transaction_type, code=code, title=title))
        return code

    def list_user_categories(self, telegram_user_id: int) -> list[UserCategory]:
        with self.Session() as session:
            return (
                session.query(UserCategory)
                .filter_by(telegram_user_id=telegram_user_id, is_active=True)
                .order_by(UserCategory.transaction_type.asc(), UserCategory.title.asc())
                .all()
            )

    def deactivate_user_category(self, telegram_user_id: int, category_id: int) -> bool:
        with self.Session.begin() as session:
            row = session.query(UserCategory).filter_by(id=category_id, telegram_user_id=telegram_user_id, is_active=True).first()
            if not row:
                return False
            row.is_active = False
            return True

    def delete_transaction(self, transaction_id: int, telegram_user_id: int, telegram_chat_id: int) -> bool:
        with self.Session.begin() as session:
            row = (
                session.query(Transaction)
                .filter_by(id=transaction_id, telegram_user_id=telegram_user_id, telegram_chat_id=telegram_chat_id)
                .first()
            )
            if not row:
                return False
            session.delete(row)
            return True


def _category_code(title: str) -> str:
    result = []
    previous_underscore = False
    translit = {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "e",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "c",
        "ч": "ch",
        "ш": "sh",
        "щ": "sch",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
    }
    for char in title.lower():
        chunk = translit.get(char, char)
        for item in chunk:
            if item.isalnum():
                result.append(item.upper())
                previous_underscore = False
            elif not previous_underscore:
                result.append("_")
                previous_underscore = True
    code = "".join(result).strip("_")[:48] or "CUSTOM"
    return f"CUSTOM_{code}"
