#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import json
import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone
from utils import get_next_webinar_date

# Setup logging
logger = logging.getLogger(__name__)

# Global scheduler
scheduler = None

def load_config():
    """Load configuration from config.json"""
    try:
        with open('config.json', 'r', encoding='utf-8') as file:
            config = json.load(file)
        return config
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return None

def load_database():
    """Load database from database.json"""
    try:
        with open('database.json', 'r', encoding='utf-8') as file:
            database = json.load(file)
        return database
    except Exception as e:
        logger.error(f"Error loading database: {e}")
        return {"participants": {}, "settings": {"last_modified": None}}

async def send_reminder_to_all(bot, reminder_type):
    """Send reminder to all active participants"""
    try:
        # Load database and config
        database = load_database()
        config = load_config()
        
        if not config or not database:
            logger.error("Failed to load configuration or database")
            return
        
        # Get participants
        participants = database.get('participants', {})
        
        # Get message based on reminder type
        if reminder_type == 'day':
            message = config['messages']['reminder_day']
        elif reminder_type == '15min':
            message = config['messages']['reminder_15min']
        else:
            logger.error(f"Invalid reminder type: {reminder_type}")
            return
        
        # Get next webinar date
        next_webinar = get_next_webinar_date(config)
        
        # Replace placeholders with webinar date
        message = message.replace("{next_webinar_date}", next_webinar['formatted']) \
                         .replace("{webinar_day}", next_webinar['day_name']) \
                         .replace("{webinar_time}", next_webinar['time'])
        
        # Send message to all active participants
        for chat_id, participant in participants.items():
            if participant.get('active', False):
                try:
                    await bot.send_message(chat_id=int(chat_id), text=message)
                    logger.info(f"Sent {reminder_type} reminder to {chat_id}")
                except Exception as e:
                    logger.error(f"Failed to send reminder to {chat_id}: {e}")
        
    except Exception as e:
        logger.error(f"Error in send_reminder_to_all: {e}")

def setup_scheduler(bot):
    """Setup scheduler for automatic reminders"""
    global scheduler
    
    try:
        # Load config
        config = load_config()
        if not config:
            logger.error("Failed to load configuration")
            return
        
        # Get timezone
        tz = timezone(config['webinar'].get('timezone', 'Europe/Bucharest'))
        
        # Create scheduler (or reuse existing)
        if scheduler is None:
            scheduler = AsyncIOScheduler(timezone=tz)
        else:
            # Update timezone if needed
            scheduler.configure(timezone=tz)
        
        # Get day of week and time for webinar
        day_of_week = config['webinar'].get('day', 'Tuesday')
        time = config['webinar'].get('time', '15:00')
        hour, minute = map(int, time.split(':'))
        
        # Map day of week to integer (0 = Monday, 6 = Sunday)
        days = {
            'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 
            'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6
        }
        day_num = days.get(day_of_week, 2)  # Default to Wednesday if invalid
        
        # Read custom reminders configuration for 'day' only
        reminders_cfg = config.get('reminders', {})
        day_reminder_cfg = reminders_cfg.get('day', {})
        day_reminder_day = day_reminder_cfg.get('day')  # e.g., 'Tuesday'
        day_reminder_time = day_reminder_cfg.get('time')  # 'HH:MM'
        if day_reminder_day and day_reminder_time:
            dr_hour, dr_minute = map(int, day_reminder_time.split(':'))
            day_num_for_day_rem = days.get(day_reminder_day, day_num)
            cron_day = CronTrigger(day_of_week=day_num_for_day_rem, hour=dr_hour, minute=dr_minute)
        else:
            # Default: webinar day at 09:00
            cron_day = CronTrigger(day_of_week=day_num, hour=9, minute=0)

        scheduler.add_job(
            send_reminder_to_all,
            cron_day,
            id='day_reminder',
            replace_existing=True,
            args=[bot, 'day']
        )

        # 15-minute reminder scheduling: always 15 minutes before webinar
        rel_hour = hour
        rel_minute = minute - 15
        rel_day_num = day_num
        if rel_minute < 0:
            rel_minute += 60
            rel_hour -= 1
            if rel_hour < 0:
                rel_hour = 23
                rel_day_num = (day_num - 1) % 7
        cron_15 = CronTrigger(day_of_week=rel_day_num, hour=rel_hour, minute=rel_minute)

        scheduler.add_job(
            send_reminder_to_all,
            cron_15,
            id='15min_reminder',
            replace_existing=True,
            args=[bot, '15min']
        )
        
        # Heartbeat: log every 10 minutes to verify liveness on Render
        try:
            scheduler.add_job(
                lambda: logger.info("[heartbeat] Bot worker alive"),
                CronTrigger(minute='*/10')
            )
        except Exception:
            pass

        # Start scheduler
        if not scheduler.running:
            scheduler.start()
        logger.info("Scheduler started")
        
    except Exception as e:
        logger.error(f"Error in setup_scheduler: {e}")

def refresh_scheduler(bot):
    """Refresh (reschedule) reminder jobs based on current config"""
    global scheduler
    try:
        if scheduler is None:
            setup_scheduler(bot)
            return
        # Remove existing jobs if present
        try:
            scheduler.remove_job('day_reminder')
        except Exception:
            pass
        try:
            scheduler.remove_job('15min_reminder')
        except Exception:
            pass
        # Re-add with current config
        setup_scheduler(bot)
        logger.info("Scheduler refreshed with new configuration")
    except Exception as e:
        logger.error(f"Error refreshing scheduler: {e}")

def get_schedule_preview(config):
    """Return effective schedule configuration and next fire times for webinar, day reminder, and pre15 reminder.
    Output dict structure:
      {
        'webinar': {'day': str, 'time': 'HH:MM', 'timezone': str, 'next': datetime},
        'day': {'day': str, 'time': 'HH:MM', 'next': datetime},
        'pre15': {'day': str, 'time': 'HH:MM', 'next': datetime}
      }
    """
    from datetime import datetime as _dt, timedelta as _td, time as _time
    tzname = config['webinar'].get('timezone', 'Europe/Bucharest')
    tz = timezone(tzname)
    now = _dt.now(tz)

    # Map day names
    days = {
        'Monday': 0, 'Tuesday': 1, 'Wednesday': 2,
        'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6
    }
    rev_days = {v: k for k, v in days.items()}

    w_day = config['webinar'].get('day', 'Wednesday')
    w_time = config['webinar'].get('time', '19:00')
    w_hour, w_min = map(int, w_time.split(':'))
    w_day_num = days.get(w_day, 2)

    # Compute next webinar datetime
    current_day = now.weekday()
    days_ahead = (w_day_num - current_day) % 7
    # If same day but time already passed, schedule for next week
    if days_ahead == 0 and (now.hour, now.minute) >= (w_hour, w_min):
        days_ahead = 7
    base_date = now.date() + _td(days=days_ahead)
    w_next = tz.localize(_dt.combine(base_date, _time(hour=w_hour, minute=w_min)))

    # Build reminder triggers
    reminders_cfg = config.get('reminders', {})

    # Day reminder
    day_cfg = reminders_cfg.get('day', {})
    if day_cfg.get('day') and day_cfg.get('time'):
        d_day = day_cfg['day']
        d_time = day_cfg['time']
        d_hour, d_min = map(int, d_time.split(':'))
        d_day_num = days.get(d_day, w_day_num)
    else:
        d_day = w_day
        d_day_num = w_day_num
        d_hour, d_min = 9, 0
        d_time = f"{d_hour:02d}:{d_min:02d}"
    cron_day = CronTrigger(day_of_week=d_day_num, hour=d_hour, minute=d_min, timezone=tz)
    d_next = cron_day.get_next_fire_time(None, now)

    # Pre15 reminder: always 15 minutes before webinar
    p_hour = w_hour
    p_min = w_min - 15
    p_day_num = w_day_num
    if p_min < 0:
        p_min += 60
        p_hour -= 1
        if p_hour < 0:
            p_hour = 23
            p_day_num = (w_day_num - 1) % 7
    p_time = f"{p_hour:02d}:{p_min:02d}"
    p_day = rev_days[p_day_num]

    cron_15 = CronTrigger(day_of_week=p_day_num, hour=p_hour, minute=p_min, timezone=tz)
    p_next = cron_15.get_next_fire_time(None, now)

    return {
        'webinar': {'day': w_day, 'time': w_time, 'timezone': tzname, 'next': w_next},
        'day': {'day': d_day, 'time': d_time, 'next': d_next},
        'pre15': {'day': p_day, 'time': p_time, 'next': p_next}
    }