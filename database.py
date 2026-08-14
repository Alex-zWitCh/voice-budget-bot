from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Numeric, String, Text, UniqueConstraint, create_engine
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from categories import CATEGORY_BY_TYPE

INVITE_CODE_TTL = timedelta(hours=24)


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
    scope: Mapped[str] = mapped_column(String(16), default="personal", index=True)
    family_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    paid_by: Mapped[Optional[int]] = mapped_column(BigInteger, index=True)


class Family(Base):
    __tablename__ = "families"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    owner_telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    invite_code: Mapped[Optional[str]] = mapped_column(String(32), unique=True)
    invite_code_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class FamilyMember(Base):
    __tablename__ = "family_members"
    __table_args__ = (
        UniqueConstraint("family_id", "telegram_user_id", name="uq_family_members_family_user"),
        UniqueConstraint("telegram_user_id", name="uq_family_members_one_family_per_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    family_id: Mapped[int] = mapped_column(Integer, index=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    role: Mapped[str] = mapped_column(String(16), default="member")
    joined_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ScheduledEvent(Base):
    __tablename__ = "scheduled_events"
    __table_args__ = (UniqueConstraint("telegram_chat_id", "telegram_message_id", name="uq_scheduled_events_telegram_message"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    telegram_message_id: Mapped[int] = mapped_column(BigInteger)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    notify_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    event_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    recurrence: Mapped[str] = mapped_column(String(16), default="none", index=True)
    title: Mapped[str] = mapped_column(Text)
    transcript: Mapped[str] = mapped_column(Text)
    transaction_type: Mapped[Optional[str]] = mapped_column(String(16))
    amount_minor: Mapped[Optional[int]] = mapped_column(BigInteger)
    currency: Mapped[Optional[str]] = mapped_column(String(3))
    category: Mapped[Optional[str]] = mapped_column(String(64))
    description: Mapped[Optional[str]] = mapped_column(Text)
    groq_model: Mapped[str] = mapped_column(String(64))
    deepseek_model: Mapped[str] = mapped_column(String(64))
    deepseek_confidence: Mapped[float] = mapped_column(Numeric(4, 3))
    processing_version: Mapped[str] = mapped_column(String(32))
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_fired_at_utc: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    scope: Mapped[str] = mapped_column(String(16), default="personal", index=True)
    family_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)


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


class ReportDelivery(Base):
    __tablename__ = "report_deliveries"
    __table_args__ = (UniqueConstraint("telegram_user_id", "report_type", "period_key", name="uq_report_deliveries_period"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger)
    report_type: Mapped[str] = mapped_column(String(64), index=True)
    period_key: Mapped[str] = mapped_column(String(32), index=True)
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
        self._run_schema_migrations()
        self._backfill_legacy_rows()
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)

    def _run_schema_migrations(self) -> None:
        with self.engine.begin() as connection:
            migrations = {
                "transactions": {
                    "scope": "VARCHAR(16) NOT NULL DEFAULT 'personal'",
                    "family_id": "INTEGER",
                    "paid_by": "BIGINT",
                },
                "scheduled_events": {
                    "scope": "VARCHAR(16) NOT NULL DEFAULT 'personal'",
                    "family_id": "INTEGER",
                },
            }
            for table, columns in migrations.items():
                existing = {row[1] for row in connection.exec_driver_sql(f"PRAGMA table_info({table})")}
                for column, definition in columns.items():
                    if column in existing:
                        continue
                    connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _backfill_legacy_rows(self) -> None:
        with self.engine.begin() as connection:
            connection.exec_driver_sql(
                "UPDATE transactions SET paid_by = telegram_user_id WHERE paid_by IS NULL"
            )

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

    def scheduled_event_exists(self, chat_id: int, message_id: int) -> bool:
        with self.Session() as session:
            return session.query(ScheduledEvent).filter_by(telegram_chat_id=chat_id, telegram_message_id=message_id).first() is not None

    def save_transaction(self, message, parsed, transcript: str, config) -> Optional[int]:
        voice = getattr(message, "voice", None)
        return self.create_transaction(
            telegram_chat_id=message.chat.id,
            telegram_message_id=message.message_id,
            telegram_user_id=message.from_user.id,
            parsed=parsed,
            transcript=transcript,
            message_date_utc=datetime.fromtimestamp(message.date, timezone.utc),
            voice_duration_sec=voice.duration if voice else 0,
            config=config,
        )

    def create_transaction(
        self,
        telegram_chat_id: int,
        telegram_message_id: int,
        telegram_user_id: int,
        parsed,
        transcript: str,
        message_date_utc: datetime,
        voice_duration_sec: int,
        config,
        scope: str = "personal",
        family_id: Optional[int] = None,
        paid_by: Optional[int] = None,
    ) -> Optional[int]:
        tx = Transaction(
            telegram_chat_id=telegram_chat_id,
            telegram_message_id=telegram_message_id,
            telegram_user_id=telegram_user_id,
            transaction_type=parsed.transaction_type,
            amount_minor=parsed.amount_minor,
            currency=parsed.currency,
            category=parsed.category,
            description=parsed.description,
            transcript=transcript,
            message_date_utc=message_date_utc,
            voice_duration_sec=voice_duration_sec,
            groq_model=config.stt_model,
            deepseek_model=config.deepseek_model,
            deepseek_confidence=parsed.confidence,
            processing_version=config.processing_version,
            scope=scope,
            family_id=family_id,
            paid_by=paid_by or telegram_user_id,
        )
        try:
            with self.Session.begin() as session:
                session.add(tx)
                session.flush()
                transaction_id = tx.id
        except IntegrityError:
            return None
        return transaction_id

    def create_scheduled_event(self, message, event, transcript: str, config) -> Optional[int]:
        scheduled = ScheduledEvent(
            telegram_chat_id=message.chat.id,
            telegram_message_id=message.message_id,
            telegram_user_id=message.from_user.id,
            event_type=event.event_type,
            notify_at_utc=event.notify_at_utc,
            event_at_utc=event.event_at_utc,
            recurrence=event.recurrence,
            title=event.title,
            transcript=transcript,
            transaction_type=event.transaction.transaction_type if event.transaction else None,
            amount_minor=event.transaction.amount_minor if event.transaction else None,
            currency=event.transaction.currency if event.transaction else None,
            category=event.transaction.category if event.transaction else None,
            description=event.transaction.description if event.transaction else None,
            groq_model=config.stt_model,
            deepseek_model=config.deepseek_model,
            deepseek_confidence=event.confidence,
            processing_version=config.processing_version,
        )
        try:
            with self.Session.begin() as session:
                session.add(scheduled)
                session.flush()
                event_id = scheduled.id
        except IntegrityError:
            return None
        return event_id

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

    def get_category_catalog(self, telegram_user_id: int, active_only: bool = True) -> dict:
        catalog = {key: value.copy() for key, value in CATEGORY_BY_TYPE.items()}
        with self.Session() as session:
            query = session.query(UserCategory).filter_by(telegram_user_id=telegram_user_id)
            if active_only:
                query = query.filter_by(is_active=True)
            rows = query.order_by(UserCategory.title.asc()).all()
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

    def delete_scheduled_event(self, event_id: int, telegram_user_id: int, telegram_chat_id: int) -> bool:
        with self.Session.begin() as session:
            row = (
                session.query(ScheduledEvent)
                .filter_by(id=event_id, telegram_user_id=telegram_user_id, telegram_chat_id=telegram_chat_id, status="active")
                .first()
            )
            if not row:
                return False
            row.status = "deleted"
            return True

    def get_due_scheduled_events(self, now_utc: datetime) -> list[ScheduledEvent]:
        with self.Session() as session:
            return (
                session.query(ScheduledEvent)
                .filter(ScheduledEvent.status == "active", ScheduledEvent.notify_at_utc <= now_utc)
                .order_by(ScheduledEvent.notify_at_utc.asc())
                .limit(20)
                .all()
            )

    def complete_scheduled_event(self, event_id: int, fired_at_utc: datetime) -> None:
        with self.Session.begin() as session:
            row = session.query(ScheduledEvent).filter_by(id=event_id).first()
            if row:
                row.status = "done"
                row.last_fired_at_utc = fired_at_utc

    def reschedule_event(self, event_id: int, notify_at_utc: datetime, event_at_utc: datetime, fired_at_utc: datetime) -> None:
        with self.Session.begin() as session:
            row = session.query(ScheduledEvent).filter_by(id=event_id).first()
            if row:
                row.notify_at_utc = notify_at_utc
                row.event_at_utc = event_at_utc
                row.last_fired_at_utc = fired_at_utc

    def list_calendar_events(self, telegram_user_id: int, start_utc: datetime, end_utc: datetime) -> list[dict]:
        with self.Session() as session:
            rows = (
                session.query(ScheduledEvent)
                .filter(
                    ScheduledEvent.telegram_user_id == telegram_user_id,
                    ScheduledEvent.status == "active",
                    ScheduledEvent.event_at_utc <= end_utc,
                )
                .order_by(ScheduledEvent.event_at_utc.asc())
                .all()
            )
        events = []
        for row in rows:
            notify_at = _as_utc(row.notify_at_utc)
            event_at = _as_utc(row.event_at_utc)
            while event_at < start_utc and row.recurrence != "none":
                notify_at = add_recurrence(notify_at, row.recurrence)
                event_at = add_recurrence(event_at, row.recurrence)
            if start_utc <= event_at <= end_utc:
                events.append(
                    {
                        "id": row.id,
                        "event_type": row.event_type,
                        "title": row.title,
                        "event_at_utc": event_at,
                        "notify_at_utc": notify_at,
                        "recurrence": row.recurrence,
                        "amount_minor": row.amount_minor,
                        "currency": row.currency,
                    }
                )
            while row.recurrence != "none":
                notify_at = add_recurrence(notify_at, row.recurrence)
                event_at = add_recurrence(event_at, row.recurrence)
                if event_at > end_utc:
                    break
                events.append(
                    {
                        "id": row.id,
                        "event_type": row.event_type,
                        "title": row.title,
                        "event_at_utc": event_at,
                        "notify_at_utc": notify_at,
                        "recurrence": row.recurrence,
                        "amount_minor": row.amount_minor,
                        "currency": row.currency,
                    }
                )
        return sorted(events, key=lambda item: item["event_at_utc"])

    def list_transactions_for_user(self, telegram_user_id: int, start_utc: datetime, end_utc: datetime) -> list[Transaction]:
        with self.Session() as session:
            return (
                session.query(Transaction)
                .filter(
                    Transaction.telegram_user_id == telegram_user_id,
                    Transaction.message_date_utc >= start_utc,
                    Transaction.message_date_utc < end_utc,
                )
                .order_by(Transaction.message_date_utc.asc(), Transaction.id.asc())
                .all()
            )

    def list_previous_month_report_targets(self, start_utc: datetime, end_utc: datetime) -> list[dict]:
        with self.Session() as session:
            rows = (
                session.query(Transaction, Chat)
                .outerjoin(Chat, Chat.telegram_chat_id == Transaction.telegram_chat_id)
                .filter(
                    Transaction.message_date_utc >= start_utc,
                    Transaction.message_date_utc < end_utc,
                )
                .order_by(Transaction.telegram_user_id.asc(), Transaction.message_date_utc.desc(), Transaction.id.desc())
                .all()
            )
        targets = {}
        for transaction, chat in rows:
            user_id = transaction.telegram_user_id
            chat_type = chat.chat_type if chat else ""
            existing = targets.get(user_id)
            if existing and existing["chat_type"] == "private":
                continue
            if not existing or chat_type == "private":
                targets[user_id] = {
                    "telegram_user_id": user_id,
                    "telegram_chat_id": transaction.telegram_chat_id,
                    "chat_type": chat_type,
                }
        return list(targets.values())

    def report_delivery_exists(self, telegram_user_id: int, report_type: str, period_key: str) -> bool:
        with self.Session() as session:
            return (
                session.query(ReportDelivery)
                .filter_by(telegram_user_id=telegram_user_id, report_type=report_type, period_key=period_key)
                .first()
                is not None
            )

    def record_report_delivery(self, telegram_user_id: int, telegram_chat_id: int, report_type: str, period_key: str) -> bool:
        try:
            with self.Session.begin() as session:
                session.add(
                    ReportDelivery(
                        telegram_user_id=telegram_user_id,
                        telegram_chat_id=telegram_chat_id,
                        report_type=report_type,
                        period_key=period_key,
                    )
                )
        except IntegrityError:
            return False
        return True

    # ---- Families ----

    def create_family(self, name: str, owner_telegram_user_id: int) -> Optional[int]:
        with self.Session.begin() as session:
            existing = session.query(FamilyMember).filter_by(telegram_user_id=owner_telegram_user_id).first()
            if existing:
                return None
            family = Family(name=name, owner_telegram_user_id=owner_telegram_user_id)
            session.add(family)
            session.flush()
            session.add(
                FamilyMember(
                    family_id=family.id,
                    telegram_user_id=owner_telegram_user_id,
                    role="owner",
                    joined_at_utc=datetime.now(timezone.utc),
                )
            )
            return family.id

    def get_family_for_user(self, telegram_user_id: int) -> Optional[Family]:
        with self.Session() as session:
            member = session.query(FamilyMember).filter_by(telegram_user_id=telegram_user_id).first()
            if not member:
                return None
            return session.query(Family).filter_by(id=member.family_id).first()

    def generate_invite_code(self, telegram_user_id: int) -> Optional[str]:
        family = self.get_family_for_user(telegram_user_id)
        if not family:
            return None
        code = _invite_code()
        with self.Session.begin() as session:
            row = session.query(Family).filter_by(id=family.id).first()
            row.invite_code = code
            row.invite_code_expires_at = datetime.now(timezone.utc) + INVITE_CODE_TTL
        return code

    def join_family_by_code(self, telegram_user_id: int, code: str) -> tuple[bool, str]:
        code = code.strip().upper()
        with self.Session.begin() as session:
            family = session.query(Family).filter_by(invite_code=code).first()
            if not family:
                return False, "invite_code_not_found"
            expires_at = family.invite_code_expires_at
            if expires_at and _as_utc(expires_at) < datetime.now(timezone.utc):
                return False, "invite_code_expired"
            existing = session.query(FamilyMember).filter_by(telegram_user_id=telegram_user_id).first()
            if existing:
                return False, "already_in_family"
            session.add(
                FamilyMember(
                    family_id=family.id,
                    telegram_user_id=telegram_user_id,
                    role="member",
                    joined_at_utc=datetime.now(timezone.utc),
                )
            )
            return True, family.name

    def list_family_members(self, family_id: int) -> list[FamilyMember]:
        with self.Session() as session:
            return (
                session.query(FamilyMember)
                .filter_by(family_id=family_id)
                .order_by(FamilyMember.joined_at_utc.asc())
                .all()
            )

    def set_transaction_scope(
        self,
        transaction_id: int,
        telegram_user_id: int,
        scope: str,
        family_id: Optional[int] = None,
        paid_by: Optional[int] = None,
    ) -> bool:
        with self.Session.begin() as session:
            tx = session.query(Transaction).filter_by(id=transaction_id).first()
            if not tx:
                return False
            if tx.telegram_user_id != telegram_user_id:
                return False
            tx.scope = scope
            tx.family_id = family_id if scope == "family" else None
            tx.paid_by = paid_by or telegram_user_id
            return True


def _invite_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(8))


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


def add_recurrence(value: datetime, recurrence: str) -> datetime:
    value = _as_utc(value)
    if recurrence == "daily":
        return value + timedelta(days=1)
    if recurrence == "weekly":
        return value + timedelta(days=7)
    if recurrence == "monthly":
        return _add_months(value, 1)
    if recurrence == "yearly":
        return _add_months(value, 12)
    return value


def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, _days_in_month(year, month))
    return value.replace(year=year, month=month, day=day)


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        next_month = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        next_month = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return (next_month - timedelta(days=1)).day


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
