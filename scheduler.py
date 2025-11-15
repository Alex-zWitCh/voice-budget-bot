"""
Scheduler for reminder notifications using APScheduler.
"""

import logging
from datetime import datetime, timezone, time as dt_time
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
import pytz
import telebot
from database import Database
from translations import get_translation

logger = logging.getLogger(__name__)


class ReminderScheduler:
    """Scheduler for sending reminder notifications."""
    
    def __init__(self, bot: telebot.TeleBot, db: Database):
        self.bot = bot
        self.db = db
        # Configure scheduler to use UTC timezone
        self.scheduler = BackgroundScheduler(timezone=timezone.utc)
        self.scheduler.start()
        self._schedule_pending_reminders()
        self._schedule_daily_expense_reminders()
    
    def _schedule_pending_reminders(self):
        """Schedule all pending reminders."""
        from datetime import timedelta
        pending = self.db.get_pending_reminders(datetime.utcnow() + timedelta(days=30))
        
        for reminder in pending:
            self.schedule_reminder(reminder)
    
    def schedule_reminder(self, reminder):
        """Schedule a single reminder with two notifications: 10 min before and at exact time."""
        try:
            from database import User
            from datetime import timedelta
            
            user = self.db.session.query(User).filter_by(id=reminder.user_id).first()
            if not user:
                return
            
            language = user.language or "en"
            
            # Calculate 10 minutes before reminder time
            warning_time = reminder.reminder_time - timedelta(minutes=10)
            exact_time = reminder.reminder_time
            
            # Only schedule if times are in the future
            now = datetime.utcnow()
            
            logger.info(f"Scheduling reminder {reminder.id}: reminder_time={reminder.reminder_time}, warning_time={warning_time}, exact_time={exact_time}, now={now}")
            
            # Convert naive UTC datetimes to timezone-aware UTC for scheduler
            # Database stores naive UTC, but scheduler needs timezone-aware
            warning_time_aware = warning_time.replace(tzinfo=timezone.utc) if warning_time.tzinfo is None else warning_time
            exact_time_aware = exact_time.replace(tzinfo=timezone.utc) if exact_time.tzinfo is None else exact_time
            
            # Schedule warning notification (10 minutes before) if it's in the future
            if warning_time > now:
                warning_message = get_translation(language, "reminder_warning", message=reminder.message)
                self.scheduler.add_job(
                    self._send_reminder_warning,
                    trigger=DateTrigger(run_date=warning_time_aware),
                    args=[reminder.id, user.telegram_id, warning_message],
                    id=f"reminder_warning_{reminder.id}",
                    replace_existing=True
                )
                logger.info(f"Scheduled warning notification for reminder {reminder.id} at {warning_time_aware}")
            
            # Schedule exact time notification
            if exact_time > now:
                exact_message = get_translation(language, "reminder_triggered", message=reminder.message)
                self.scheduler.add_job(
                    self._send_reminder_exact,
                    trigger=DateTrigger(run_date=exact_time_aware),
                    args=[reminder.id, user.telegram_id, exact_message],
                    id=f"reminder_exact_{reminder.id}",
                    replace_existing=True
                )
                logger.info(f"Scheduled exact notification for reminder {reminder.id} at {exact_time_aware}")
            
            logger.info(f"Scheduled reminder {reminder.id} for user {user.telegram_id}")
        except Exception as e:
            logger.error(f"Error scheduling reminder {reminder.id}: {e}")
    
    def _send_reminder_warning(self, reminder_id: int, telegram_id: int, message_text: str):
        """Send warning notification 10 minutes before reminder time."""
        try:
            self.bot.send_message(telegram_id, message_text)
            logger.info(f"Sent warning notification for reminder {reminder_id} to user {telegram_id}")
        except Exception as e:
            logger.error(f"Error sending warning notification for reminder {reminder_id}: {e}")
    
    def _send_reminder_exact(self, reminder_id: int, telegram_id: int, message_text: str):
        """Send reminder notification at exact reminder time and mark as sent."""
        try:
            self.bot.send_message(telegram_id, message_text)
            self.db.mark_reminder_sent(reminder_id)
            logger.info(f"Sent exact notification for reminder {reminder_id} to user {telegram_id} and marked as sent")
        except Exception as e:
            logger.error(f"Error sending exact notification for reminder {reminder_id}: {e}")
    
    def _schedule_daily_expense_reminders(self):
        """Schedule daily expense reminders at 20:00 for each user in their timezone."""
        try:
            # Get all users with timezone set
            users = self.db.get_all_users_with_timezone()
            
            for user in users:
                try:
                    # Get user's timezone
                    user_tz = pytz.timezone(user.timezone)
                    language = user.language or "en"
                    
                    # Create a job that runs daily at 20:00 in user's timezone
                    # We use cron trigger with timezone support
                    self.scheduler.add_job(
                        self._send_daily_expense_reminder,
                        trigger=CronTrigger(hour=20, minute=0, timezone=user_tz),
                        args=[user.telegram_id, language],
                        id=f"daily_expense_reminder_{user.telegram_id}",
                        replace_existing=True,
                        name=f"Daily expense reminder for user {user.telegram_id}"
                    )
                    logger.info(f"Scheduled daily expense reminder for user {user.telegram_id} at 20:00 {user.timezone}")
                except Exception as e:
                    logger.error(f"Error scheduling daily reminder for user {user.telegram_id}: {e}", exc_info=True)
            
            logger.info(f"Scheduled daily expense reminders for {len(users)} users")
        except Exception as e:
            logger.error(f"Error scheduling daily expense reminders: {e}", exc_info=True)
    
    def _send_daily_expense_reminder(self, telegram_id: int, language: str):
        """Send daily expense reminder to user."""
        try:
            message = get_translation(language, "daily_expense_reminder")
            self.bot.send_message(telegram_id, message)
            logger.info(f"Sent daily expense reminder to user {telegram_id}")
        except Exception as e:
            logger.error(f"Error sending daily expense reminder to user {telegram_id}: {e}", exc_info=True)
    
    def reschedule_user_daily_reminder(self, telegram_id: int, user_timezone: str, user_language: str):
        """Reschedule daily expense reminder for a specific user (e.g., when timezone changes)."""
        try:
            user_tz = pytz.timezone(user_timezone)
            
            # Remove old job if exists
            job_id = f"daily_expense_reminder_{telegram_id}"
            try:
                self.scheduler.remove_job(job_id)
            except:
                pass  # Job might not exist
            
            # Schedule new job
            self.scheduler.add_job(
                self._send_daily_expense_reminder,
                trigger=CronTrigger(hour=20, minute=0, timezone=user_tz),
                args=[telegram_id, user_language],
                id=job_id,
                replace_existing=True,
                name=f"Daily expense reminder for user {telegram_id}"
            )
            logger.info(f"Rescheduled daily expense reminder for user {telegram_id} at 20:00 {user_timezone}")
        except Exception as e:
            logger.error(f"Error rescheduling daily reminder for user {telegram_id}: {e}", exc_info=True)
    
    def shutdown(self):
        """Shutdown the scheduler."""
        self.scheduler.shutdown()

