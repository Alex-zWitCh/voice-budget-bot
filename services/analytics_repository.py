from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, event, text

from schemas import (
    ASK_SCOPE_ACCESSIBLE,
    ASK_SCOPE_FAMILY,
    ASK_SCOPE_MY_PAYMENTS,
    ASK_SCOPE_PERSONAL,
    AnalyticsTransaction,
    AskAccessScope,
)


class AnalyticsReadOnlyError(Exception):
    pass


def _as_utc(value: datetime) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class AnalyticsRepository:
    """Read-only доступ к финансовым записям для /ask.

    Открывает тот же SQLite-файл в режиме mode=ro и дополнительно
    выставляет PRAGMA query_only=ON. Запись в этом объекте отсутствует.
    """

    _COLUMNS = (
        "id",
        "transaction_type",
        "amount_minor",
        "currency",
        "category",
        "description",
        "transcript",
        "message_date_utc",
        "scope",
        "paid_by",
        "exchange_rate",
        "from_currency",
        "from_amount_minor",
    )

    def __init__(self, sqlite_path: Path):
        self.sqlite_path = sqlite_path
        db_uri = f"sqlite:///file:{sqlite_path.resolve()}?mode=ro&uri=true"
        self.engine = create_engine(
            db_uri,
            connect_args={"check_same_thread": False, "timeout": 10},
            pool_pre_ping=True,
        )

        @event.listens_for(self.engine, "connect")
        def _set_query_only(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA query_only = ON")
            finally:
                cursor.close()

    def close(self) -> None:
        self.engine.dispose()

    def get_family_id_for_user(self, telegram_user_id: int) -> Optional[int]:
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT family_id FROM family_members WHERE telegram_user_id = :user_id ORDER BY id LIMIT 1"
                ),
                {"user_id": telegram_user_id},
            ).first()
        return int(row[0]) if row else None

    def get_main_currency(self, telegram_user_id: int) -> str:
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT main_currency FROM users WHERE telegram_user_id = :user_id"
                ),
                {"user_id": telegram_user_id},
            ).first()
        return row[0] if row and row[0] else "RUB"

    def get_user_categories(
        self, telegram_user_id: int, active_only: bool = True
    ) -> list[tuple[str, str, str]]:
        clause = " AND is_active = 1" if active_only else ""
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT transaction_type, code, title FROM user_categories "
                    "WHERE telegram_user_id = :user_id"
                    + clause
                    + " ORDER BY transaction_type, title"
                ),
                {"user_id": telegram_user_id},
            ).all()
        return [(row[0], row[1], row[2]) for row in rows]

    def get_exchange_rates(
        self, telegram_user_id: int
    ) -> list[tuple[str, str, Decimal]]:
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT from_currency, currency, exchange_rate FROM transactions "
                    "WHERE telegram_user_id = :user_id AND transaction_type = 'INCOME' "
                    "AND exchange_pair_id IS NOT NULL AND exchange_rate IS NOT NULL "
                    "ORDER BY created_at_utc ASC"
                ),
                {"user_id": telegram_user_id},
            ).all()
        return [(row[0], row[1], Decimal(str(row[2]))) for row in rows]

    def make_scope(self, telegram_user_id: int) -> AskAccessScope:
        return AskAccessScope(
            telegram_user_id=telegram_user_id,
            family_id=self.get_family_id_for_user(telegram_user_id),
        )

    def _visibility(
        self, access_scope: AskAccessScope, data_scope: str
    ) -> tuple[str, dict]:
        user_id = access_scope.telegram_user_id
        params: dict = {"user_id": user_id}
        personal = "telegram_user_id = :user_id AND scope = 'personal'"
        if data_scope == ASK_SCOPE_PERSONAL:
            return personal, params
        family_id = access_scope.family_id
        if family_id is None:
            if data_scope in {ASK_SCOPE_FAMILY, ASK_SCOPE_MY_PAYMENTS}:
                return "1 = 0", params
            return personal, params
        params["family_id"] = family_id
        if data_scope == ASK_SCOPE_MY_PAYMENTS:
            return (
                "scope = 'family' AND family_id = :family_id AND paid_by = :user_id",
                params,
            )
        if data_scope == ASK_SCOPE_FAMILY:
            return "scope = 'family' AND family_id = :family_id", params
        if data_scope == ASK_SCOPE_PERSONAL:
            return personal, params
        return (
            "(telegram_user_id = :user_id AND scope = 'personal') "
            "OR (scope = 'family' AND family_id = :family_id)",
            params,
        )

    @staticmethod
    def _in_clause(
        values: tuple[str, ...], column: str, prefix: str
    ) -> tuple[str, dict]:
        if not values:
            return "", {}
        placeholders = ", ".join(f":{prefix}{index}" for index in range(len(values)))
        params = {f"{prefix}{index}": value for index, value in enumerate(values)}
        return f"{column} IN ({placeholders})", params

    def fetch_transactions(
        self,
        access_scope: AskAccessScope,
        *,
        data_scope: str = ASK_SCOPE_ACCESSIBLE,
        transaction_type: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        categories: tuple[str, ...] = (),
        currencies: tuple[str, ...] = (),
        text_terms: tuple[str, ...] = (),
        limit: Optional[int] = None,
    ) -> list[AnalyticsTransaction]:
        condition, params = self._visibility(access_scope, data_scope)
        conditions = [condition]
        if transaction_type is not None:
            conditions.append("transaction_type = :transaction_type")
            params["transaction_type"] = transaction_type
        if date_from is not None:
            conditions.append("message_date_utc >= :date_from")
            params["date_from"] = date_from
        if date_to is not None:
            conditions.append("message_date_utc < :date_to")
            params["date_to"] = date_to
        if categories:
            clause, category_params = self._in_clause(
                tuple(categories), "category", "category_"
            )
            conditions.append(clause)
            params.update(category_params)
        if currencies:
            clause, currency_params = self._in_clause(
                tuple(currencies), "currency", "currency_"
            )
            conditions.append(clause)
            params.update(currency_params)
        if text_terms:
            term_parts = []
            for index, term in enumerate(text_terms):
                term_parts.append(
                    f"(description LIKE :term_{index} OR transcript LIKE :term_{index})"
                )
                params[f"term_{index}"] = f"%{term}%"
            conditions.append("(" + " OR ".join(term_parts) + ")")

        sql = (
            "SELECT "
            + ", ".join(self._COLUMNS)
            + " FROM transactions WHERE "
            + " AND ".join(conditions)
            + " ORDER BY message_date_utc ASC, id ASC"
        )
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        with self.engine.connect() as connection:
            rows = connection.execute(text(sql), params).all()
        return [self._to_read_model(access_scope, row) for row in rows]

    @staticmethod
    def _to_read_model(access_scope: AskAccessScope, row) -> AnalyticsTransaction:
        return AnalyticsTransaction(
            id=int(row.id),
            transaction_type=str(row.transaction_type),
            amount_minor=int(row.amount_minor),
            currency=str(row.currency),
            category=str(row.category),
            description=str(row.description or ""),
            transcript=str(row.transcript or ""),
            message_date_utc=_as_utc(row.message_date_utc),
            scope=str(row.scope),
            paid_by_current_user=bool(row.paid_by)
            and int(row.paid_by) == access_scope.telegram_user_id,
            exchange_rate=Decimal(str(row.exchange_rate))
            if row.exchange_rate is not None
            else None,
            from_currency=str(row.from_currency)
            if row.from_currency is not None
            else None,
            from_amount_minor=int(row.from_amount_minor)
            if row.from_amount_minor is not None
            else None,
        )

    def get_visible_date_range(
        self,
        access_scope: AskAccessScope,
        *,
        data_scope: str = ASK_SCOPE_ACCESSIBLE,
        transaction_type: Optional[str] = None,
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        condition, params = self._visibility(access_scope, data_scope)
        conditions = [condition]
        if transaction_type is not None:
            conditions.append("transaction_type = :transaction_type")
            params["transaction_type"] = transaction_type
        sql = (
            "SELECT MIN(message_date_utc), MAX(message_date_utc) FROM transactions WHERE "
            + " AND ".join(conditions)
        )
        with self.engine.connect() as connection:
            row = connection.execute(text(sql), params).first()
        if not row or row[0] is None:
            return None, None
        return _as_utc(row[0]), _as_utc(row[1])
