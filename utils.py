#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import datetime
from datetime import timedelta
import calendar
import pytz

logger = logging.getLogger(__name__)

def get_next_webinar_date(config):
    """Calculate the date of the next webinar based on the config"""
    try:
        # Get day and time from config
        day_name = config['webinar'].get('day', 'Tuesday')
        time_str = config['webinar'].get('time', '19:00')
        timezone_str = config['webinar'].get('timezone', 'Europe/Bucharest')
        
        # Convert day name to day number (0 = Monday, 6 = Sunday)
        day_map = {
            'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 
            'Thursday': 3, 'Friday': 4, 'Saturday': 5, 'Sunday': 6
        }
        target_day = day_map.get(day_name, 1)  # Default to Tuesday (1) if invalid
        
        # Romanian day names for display
        romanian_days = {
            'Monday': 'luni', 'Tuesday': 'marți', 'Wednesday': 'miercuri',
            'Thursday': 'joi', 'Friday': 'vineri', 'Saturday': 'sâmbătă', 'Sunday': 'duminică'
        }
        day_name_ro = romanian_days.get(day_name, day_name.lower())
        
        # Get current date and time in the specified timezone
        tz = pytz.timezone(timezone_str)
        now = datetime.datetime.now(tz)
        
        # Calculate days until next webinar
        current_day = now.weekday()
        days_ahead = target_day - current_day
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        
        # Calculate the next webinar date
        next_webinar_date = now.date() + timedelta(days=days_ahead)
        
        # Format the date as needed
        day = next_webinar_date.day
        
        # Romanian month names
        romanian_months = {
            1: "ianuarie", 2: "februarie", 3: "martie", 4: "aprilie",
            5: "mai", 6: "iunie", 7: "iulie", 8: "august",
            9: "septembrie", 10: "octombrie", 11: "noiembrie", 12: "decembrie"
        }
        
        month_ro = romanian_months[next_webinar_date.month]
        year = next_webinar_date.year
        
        # Return formatted date and raw date
        return {
            'formatted': f"{day} {month_ro} {year}",
            'formatted_ro': f"{day} {month_ro} {year}",
            'date_obj': next_webinar_date,
            'day_name': day_name_ro,  # Romanian day name
            'time': time_str
        }
    except Exception as e:
        logger.error(f"Error calculating next webinar date: {e}")
        # Default Romanian format for error fallback
        now = datetime.datetime.now()
        fallback_date = now.date() + timedelta(days=7)
        romanian_months = {
            1: "ianuarie", 2: "februarie", 3: "martie", 4: "aprilie",
            5: "mai", 6: "iunie", 7: "iulie", 8: "august",
            9: "septembrie", 10: "octombrie", 11: "noiembrie", 12: "decembrie"
        }
        fallback_month = romanian_months[fallback_date.month]
        
        return {
            'formatted': f"{fallback_date.day} {fallback_month} {fallback_date.year}",
            'formatted_ro': f"{fallback_date.day} {fallback_month} {fallback_date.year}",
            'date_obj': fallback_date,
            'day_name': 'marți',  # Romanian day name for Tuesday
            'time': '19:00'
        }