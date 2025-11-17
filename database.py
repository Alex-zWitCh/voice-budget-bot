"""
Database models and utilities using SQLAlchemy.
Supports both SQLite3 (development) and PostgreSQL (production).
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session, relationship
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from config import Config
import threading

Base = declarative_base()


class User(Base):
    """User model."""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    language = Column(String(10), default='en')
    timezone = Column(String(50), default='UTC')  # Timezone string like 'Asia/Tashkent', 'Europe/Moscow', 'UTC'
    currency = Column(String(10), default='USD')  # Default currency preference
    created_at = Column(DateTime, default=datetime.utcnow)
    
    expenses = relationship("Expense", back_populates="user", cascade="all, delete-orphan")
    reminders = relationship("Reminder", back_populates="user", cascade="all, delete-orphan")
    incomes = relationship("Income", back_populates="user", cascade="all, delete-orphan")


class Expense(Base):
    """Expense model."""
    __tablename__ = 'expenses'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String(100), nullable=False)
    description = Column(Text)
    date = Column(DateTime, default=datetime.utcnow, index=True)
    
    user = relationship("User", back_populates="expenses")


class Reminder(Base):
    """Reminder model."""
    __tablename__ = 'reminders'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    message = Column(Text, nullable=False)
    reminder_time = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    sent = Column(Integer, default=0)  # 0 = not sent, 1 = sent
    
    user = relationship("User", back_populates="reminders")


class Income(Base):
    """Income model."""
    __tablename__ = 'incomes'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), nullable=False)
    description = Column(Text)
    income_type = Column(String(20), default='monthly')  # 'monthly' or 'daily'
    date = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="incomes")


class Database:
    """Database manager supporting SQLite3 and PostgreSQL with thread-safe session management."""
    
    def __init__(self):
        self.db_type = Config.DB_TYPE
        
        if self.db_type == "sqlite":
            database_url = f"sqlite:///{Config.SQLITE_DB_PATH}"
            # Use pool_pre_ping to handle stale connections
            self.engine = create_engine(
                database_url, 
                connect_args={"check_same_thread": False},
                pool_pre_ping=True
            )
        elif self.db_type == "postgresql":
            database_url = f"postgresql://{Config.POSTGRES_USER}:{Config.POSTGRES_PASSWORD}@{Config.POSTGRES_HOST}:{Config.POSTGRES_PORT}/{Config.POSTGRES_DB}"
            # Use pool_pre_ping for PostgreSQL as well
            self.engine = create_engine(database_url, pool_pre_ping=True)
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")
        
        Base.metadata.create_all(self.engine)
        # Use scoped_session for thread-safe session management
        # This creates a session per thread, preventing conflicts between concurrent users
        session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(session_factory)
    
    @property
    def session(self):
        """Get thread-local session."""
        return self.Session()
    
    def get_or_create_user(self, telegram_id: int, name: str) -> User:
        """Get existing user or create new one. Thread-safe."""
        session = self.session
        try:
            # Use no_autoflush to prevent premature flushes during query
            with session.no_autoflush:
                user = session.query(User).filter_by(telegram_id=telegram_id).first()
            
            if not user:
                try:
                    user = User(telegram_id=telegram_id, name=name)
                    session.add(user)
                    session.commit()
                    session.refresh(user)
                except IntegrityError:
                    # User was created by another thread/process, rollback and fetch
                    session.rollback()
                    user = session.query(User).filter_by(telegram_id=telegram_id).first()
                    if not user:
                        raise  # Re-raise if still not found after rollback
            return user
        finally:
            # Close the session to return it to the pool
            session.close()
    
    def update_user_language(self, telegram_id: int, language: str):
        """Update user's language preference. Thread-safe."""
        session = self.session
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if user:
                user.language = language
                session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def update_user_name(self, telegram_id: int, name: str):
        """Update user's name. Thread-safe."""
        session = self.session
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if user:
                user.name = name
                session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def update_user_timezone(self, telegram_id: int, timezone: str):
        """Update user's timezone. Thread-safe."""
        session = self.session
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if user:
                user.timezone = timezone
                session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def update_user_currency(self, telegram_id: int, currency: str):
        """Update user's currency preference. Thread-safe."""
        session = self.session
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if user:
                user.currency = currency
                session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def add_expense(self, telegram_id: int, amount: float, category: str, description: str):
        """Add an expense for a user. Thread-safe."""
        session = self.session
        try:
            # Get or create user in the same session
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if not user:
                user = User(telegram_id=telegram_id, name="")
                session.add(user)
                session.flush()  # Flush to get user.id
            
            expense = Expense(
                user_id=user.id,
                amount=amount,
                category=category,
                description=description,
                date=datetime.utcnow()
            )
            session.add(expense)
            session.commit()
        except IntegrityError:
            # User might have been created by another thread, retry
            session.rollback()
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if not user:
                user = User(telegram_id=telegram_id, name="")
                session.add(user)
                session.flush()
            expense = Expense(
                user_id=user.id,
                amount=amount,
                category=category,
                description=description,
                date=datetime.utcnow()
            )
            session.add(expense)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_expenses(self, telegram_id: int, start_date=None, end_date=None, category=None, limit=100):
        """Get expenses for a user with optional filters. Thread-safe."""
        session = self.session
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if not user:
                return []
            
            query = session.query(Expense).filter_by(user_id=user.id)
            
            if start_date:
                query = query.filter(Expense.date >= start_date)
            if end_date:
                query = query.filter(Expense.date <= end_date)
            if category:
                query = query.filter(Expense.category == category)
            
            # Convert to list to detach from session before closing
            results = query.order_by(Expense.date.desc()).limit(limit).all()
            return results
        finally:
            session.close()
    
    def add_reminder(self, telegram_id: int, message: str, reminder_time: datetime):
        """Add a reminder for a user. Thread-safe."""
        session = self.session
        try:
            # Get or create user in the same session
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if not user:
                try:
                    user = User(telegram_id=telegram_id, name="")
                    session.add(user)
                    session.flush()  # Flush to get user.id
                except IntegrityError:
                    session.rollback()
                    user = session.query(User).filter_by(telegram_id=telegram_id).first()
                    if not user:
                        raise
            
            reminder = Reminder(
                user_id=user.id,
                message=message,
                reminder_time=reminder_time,
                sent=0
            )
            session.add(reminder)
            session.commit()
            session.refresh(reminder)
            return reminder
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_pending_reminders(self, before_time: datetime):
        """Get reminders that should be triggered before the given time. Thread-safe."""
        session = self.session
        try:
            results = session.query(Reminder).filter(
                Reminder.reminder_time <= before_time,
                Reminder.sent == 0
            ).all()
            return results
        finally:
            session.close()
    
    def get_all_users_with_timezone(self):
        """Get all users who have timezone set (not UTC). Thread-safe."""
        session = self.session
        try:
            results = session.query(User).filter(
                User.timezone.isnot(None),
                User.timezone != 'UTC'
            ).all()
            return results
        finally:
            session.close()
    
    def mark_reminder_sent(self, reminder_id: int):
        """Mark a reminder as sent. Thread-safe."""
        session = self.session
        try:
            reminder = session.query(Reminder).filter_by(id=reminder_id).first()
            if reminder:
                reminder.sent = 1
                session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def add_income(self, telegram_id: int, amount: float, currency: str = None, description: str = None, income_type: str = 'monthly'):
        """Add an income record for a user. Uses user's currency from User table. Thread-safe."""
        session = self.session
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if not user:
                user = User(telegram_id=telegram_id, name="")
                session.add(user)
                session.flush()
            
            # Always use user's currency from User table, not the passed currency parameter
            user_currency = user.currency or "USD"
            
            income = Income(
                user_id=user.id,
                amount=amount,
                currency=user_currency,  # Use user's currency from User table
                description=description or "",
                income_type=income_type,
                date=datetime.utcnow()
            )
            session.add(income)
            session.commit()
            session.refresh(income)
            return income
        except IntegrityError:
            session.rollback()
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if not user:
                user = User(telegram_id=telegram_id, name="")
                session.add(user)
                session.flush()
            
            # Always use user's currency from User table
            user_currency = user.currency or "USD"
            
            income = Income(
                user_id=user.id,
                amount=amount,
                currency=user_currency,  # Use user's currency from User table
                description=description or "",
                income_type=income_type,
                date=datetime.utcnow()
            )
            session.add(income)
            session.commit()
            session.refresh(income)
            return income
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def get_incomes(self, telegram_id: int, start_date=None, end_date=None, limit=100):
        """Get incomes for a user with optional filters. Thread-safe."""
        session = self.session
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if not user:
                return []
            
            query = session.query(Income).filter_by(user_id=user.id)
            
            if start_date:
                query = query.filter(Income.date >= start_date)
            if end_date:
                query = query.filter(Income.date <= end_date)
            
            results = query.order_by(Income.date.desc()).limit(limit).all()
            return results
        finally:
            session.close()
    
    def user_exists(self, telegram_id: int) -> bool:
        """Check if user exists in database. Thread-safe."""
        session = self.session
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            return user is not None
        except Exception:
            return False
        finally:
            session.close()
    
    def delete_user(self, telegram_id: int):
        """Delete user and all associated data. Thread-safe."""
        session = self.session
        try:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if user:
                # Cascade delete will handle expenses, reminders, and incomes
                session.delete(user)
                session.commit()
                return True
            return False
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def close(self):
        """Close all database sessions and cleanup."""
        self.Session.remove()

