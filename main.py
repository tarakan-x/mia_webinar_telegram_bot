#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import json
import os
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from handlers import (start_command, info_command, export_csv_command, 
                     set_message_command, send_reminder_command, message_handler,
                     broadcast_command, menu_command, admin_menu_command, button_callback_handler,
                     add_admin_command, remove_admin_command, list_admins_command,
                     set_reminder_schedule_command, view_schedule_command, set_webinar_command,
                     help_command, sync_sheet_command)
from scheduler import setup_scheduler
from keyboard_menu import handle_keyboard_button

# Load environment variables from .env file
load_dotenv()

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='bot.log'
)
logger = logging.getLogger(__name__)

def load_config():
    """Load configuration from config.json"""
    try:
        with open('config.json', 'r', encoding='utf-8') as file:
            config = json.load(file)
        return config
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        raise

def main():
    """Main function to start the bot"""
    # Initialize database.json if it doesn't exist
    if not os.path.exists('database.json'):
        with open('database.json', 'w', encoding='utf-8') as file:
            json.dump({"participants": {}, "settings": {"last_modified": None}}, file, indent=4)
    
    # Load configuration
    config = load_config()
    
    # Get token from environment variable, if not present, use the one from config.json
    token = os.environ.get('TELEGRAM_BOT_TOKEN') or config.get('token')
    
    if not token or token == "YOUR_BOT_TOKEN":
        logger.error("Please set your bot token in .env file or config.json")
        print("Please set your bot token in .env file or config.json")
        return
    
    # Create the Application
    application = ApplicationBuilder().token(token).build()
    
    # Add command handlers
    application.add_handler(CommandHandler('start', start_command))
    application.add_handler(CommandHandler('info', info_command))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('exportcsv', export_csv_command))
    application.add_handler(CommandHandler('syncsheet', sync_sheet_command))
    application.add_handler(CommandHandler('setmessage', set_message_command))
    application.add_handler(CommandHandler('sendreminder', send_reminder_command))
    application.add_handler(CommandHandler('broadcast', broadcast_command))
    application.add_handler(CommandHandler('menu', menu_command))
    application.add_handler(CommandHandler('adminmenu', admin_menu_command))
    # removed /setkeyboard
    
    # Admin management commands
    application.add_handler(CommandHandler('addadmin', add_admin_command))
    application.add_handler(CommandHandler('deladmin', remove_admin_command))
    application.add_handler(CommandHandler('listadmins', list_admins_command))
    application.add_handler(CommandHandler('setreminder', set_reminder_schedule_command))
    application.add_handler(CommandHandler('viewschedule', view_schedule_command))
    application.add_handler(CommandHandler('setwebinar', set_webinar_command))
    
    # Add callback handler for menu buttons
    application.add_handler(CallbackQueryHandler(button_callback_handler))
    
    # Add message handler for text messages (used for formatted messages after /setmessage)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    # Setup scheduler for automatic reminders
    setup_scheduler(application.bot)
    
    # Start the Bot
    logger.info("Bot started")
    application.run_polling()

if __name__ == '__main__':
    main()