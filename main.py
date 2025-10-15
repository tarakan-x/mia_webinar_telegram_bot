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

# Determine data directory (use /data for Render.com persistent disk, or current dir for local)
DATA_DIR = '/data' if os.path.exists('/data') and os.access('/data', os.W_OK) else '.'
CONFIG_FILE = os.path.join(DATA_DIR, 'config.json')
DATABASE_FILE = os.path.join(DATA_DIR, 'database.json')
LOG_FILE = os.path.join(DATA_DIR, 'bot.log')

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename=LOG_FILE
)
logger = logging.getLogger(__name__)

logger.info(f"Using data directory: {DATA_DIR}")

def load_config():
    """Load configuration from config.json or environment variables"""
    secret_config_file = '/etc/secrets/config.json'
    
    # Check if config exists in /data, if not, try to import from secrets
    if not os.path.exists(CONFIG_FILE) and os.path.exists(secret_config_file):
        try:
            import shutil
            shutil.copy(secret_config_file, CONFIG_FILE)
            logger.info(f"✅ Imported config from {secret_config_file} to {CONFIG_FILE}")
        except Exception as e:
            logger.error(f"Failed to import config from secrets: {e}")
    
    # Try to load from config.json first (for persistent changes)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as file:
                config = json.load(file)
            logger.info(f"Loaded configuration from {CONFIG_FILE}")
            return config
        except Exception as e:
            logger.warning(f"Error loading {CONFIG_FILE}: {e}, falling back to environment variables")
    
    # Fallback to environment variables (for initial Render.com deployment)
    # This will create config.json on first run
    logger.info(f"{CONFIG_FILE} not found, creating from environment variables")
    admin_ids_str = os.environ.get('ADMIN_IDS', '123456789')
    admin_ids = [int(id.strip()) for id in admin_ids_str.split(',') if id.strip()]
    
    config = {
        "token": os.environ.get('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN'),
        "admin_ids": admin_ids,
        "webinar": {
            "day": os.environ.get('WEBINAR_DAY', 'Tuesday'),
            "time": os.environ.get('WEBINAR_TIME', '15:00'),
            "timezone": os.environ.get('WEBINAR_TIMEZONE', 'Europe/Bucharest'),
            "link": os.environ.get('WEBINAR_LINK', 'https://meet.google.com/rws-ybdw-gfb')
        },
        "messages": {
            "welcome": "BINE AI VENIT! {first_name} {last_name} 👋\n\nTe-ai înregistrat cu succes la webinarul MIA pentru afaceri.\n📅 Când: Marți, ora 15:00\n🔗 Unde: https://meet.google.com/rws-ybdw-gfb\nLa acest webinar vei descoperi:\n✅ Cum să încasezi banii în câteva secunde, direct în cont\n✅ Care este cel mai mic comision de pe piață – max. 0,8%\n✅ Cum funcționează plățile prin cod QR – simplu și rapid\nℹ️ În ziua evenimentului vei primi un reminder cu toate detaliile.\nNe vedem curând! 🚀",
            "info": "Bună 👋\n\nUrmătorul webinar va avea loc:\n\n📅 Când: Marți, ora 15:00\n🔗 Unde: https://meet.google.com/rws-ybdw-gfb\nLa acest webinar vei descoperi:\n✅ Cum să încasezi banii în câteva secunde, direct în cont\n✅ Care este cel mai mic comision de pe piață – max. 0,8%\n✅ Cum funcționează plățile prin cod QR – simplu și rapid\nℹ️ În ziua evenimentului vei primi un reminder cu toate detaliile.\nNe vedem curând! 🚀",
            "reminder_day": "BUNĂ DIMINEAȚA!\nNu uita: azi, la ora 15:00, are loc webinarul gratuit MIA pentru afaceri, organizat de echipa FinTech a Băncii Naționale a Moldovei.\n👉 Conectează-te aici: https://meet.google.com/rws-ybdw-gfb\nCe vei învăța:\n⚡ Cum să încasezi banii în doar 10 secunde\n💡 Cum să reduci costurile la max. 0,8% comision\n📲 Cum să folosești plățile prin QR pentru afacerea ta\nTe așteptăm online! 🚀",
            "reminder_15min": "⏰ 15 minute până la start\n• Webinar: MIA pentru afaceri\n• Conectare: https://meet.google.com/rws-ybdw-gfb\n• Ora: 15:00 (Chișinău)\nTe așteptăm! 🙌\n💼 Vezi cum încasezi rapid, reduci costurile și simplifici plățile pentru clienți.\n📞 Ai nevoie de suport? Sună-ne: +373 (22) 82 81 25\n🚀 MIA – pentru afaceri în mișcare.\nCreat de Banca Națională a Moldovei"
        },
        "reminders": {
            "day": {
                "day": os.environ.get('REMINDER_DAY_DAY', 'Tuesday'),
                "time": os.environ.get('REMINDER_DAY_TIME', '09:00')
            }
        },
        "google_sheets": {
            "enabled": os.environ.get('GOOGLE_SHEETS_ENABLED', 'false').lower() == 'true',
            "credentials_json_path": "service_account.json",
            "spreadsheet_id": os.environ.get('GOOGLE_SHEETS_SPREADSHEET_ID', ''),
            "worksheet_name": os.environ.get('GOOGLE_SHEETS_WORKSHEET_NAME', 'participants')
        }
    }
    
    # Save this initial config to config.json for future edits
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as file:
            json.dump(config, file, indent=4, ensure_ascii=False)
        logger.info(f"Created {CONFIG_FILE} from environment variables")
    except Exception as e:
        logger.warning(f"Could not create {CONFIG_FILE}: {e}")
    
    return config

def main():
    """Main function to start the bot"""
    # Check if database exists in secret files location and import it
    secret_database_file = '/etc/secrets/database.json'
    if not os.path.exists(DATABASE_FILE) and os.path.exists(secret_database_file):
        try:
            import shutil
            shutil.copy(secret_database_file, DATABASE_FILE)
            logger.info(f"✅ Imported database from {secret_database_file} to {DATABASE_FILE}")
        except Exception as e:
            logger.error(f"Failed to import database from secrets: {e}")
    
    # Initialize database.json if it doesn't exist
    if not os.path.exists(DATABASE_FILE):
        with open(DATABASE_FILE, 'w', encoding='utf-8') as file:
            json.dump({"participants": {}, "settings": {"last_modified": None}}, file, indent=4)
        logger.info(f"Created {DATABASE_FILE}")
    
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