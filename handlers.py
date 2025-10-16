#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import logging
import csv
import datetime
import os
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, MessageHandler, filters, CallbackQueryHandler
from scheduler import send_reminder_to_all, refresh_scheduler, get_schedule_preview
from utils import get_next_webinar_date
from sheets import get_sheets_client
try:
    from keyboard_menu import handle_keyboard_button
except ImportError:
    def handle_keyboard_button(text):
        return None

# Setup logging
logger = logging.getLogger(__name__)

# Use same data directory as main.py
DATA_DIR = '/data' if os.path.exists('/data') and os.access('/data', os.W_OK) else '.'
CONFIG_FILE = os.path.join(DATA_DIR, 'config.json')
DATABASE_FILE = os.path.join(DATA_DIR, 'database.json')

# Debug logging
logger.info(f"[HANDLERS] Using DATA_DIR: {DATA_DIR}")
logger.info(f"[HANDLERS] CONFIG_FILE: {CONFIG_FILE}")
logger.info(f"/data exists: {os.path.exists('/data')}, writable: {os.access('/data', os.W_OK)}")

def load_config():
    """Load configuration from config.json"""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as file:
            config = json.load(file)
        return config
    except Exception as e:
        logger.error(f"Error loading config from {CONFIG_FILE}: {e}")
        return None

def save_config(config):
    """Persist configuration to config.json"""
    try:
        logger.info(f"[SAVE_CONFIG] Attempting to save to: {CONFIG_FILE}")
        logger.info(f"[SAVE_CONFIG] Current working directory: {os.getcwd()}")
        with open(CONFIG_FILE, 'w', encoding='utf-8') as file:
            json.dump(config, file, indent=4, ensure_ascii=False)
        logger.info(f"[SAVE_CONFIG] Successfully saved to: {CONFIG_FILE}")
        return True
    except Exception as e:
        logger.error(f"Error saving config to {CONFIG_FILE}: {e}")
        return False

def load_database():
    """Load database from database.json"""
    try:
        with open(DATABASE_FILE, 'r', encoding='utf-8') as file:
            database = json.load(file)
        return database
    except Exception as e:
        logger.error(f"Error loading database from {DATABASE_FILE}: {e}")
        return {"participants": {}, "settings": {"last_modified": None}}

def save_database(database):
    """Save database to database.json"""
    try:
        with open(DATABASE_FILE, 'w', encoding='utf-8') as file:
            json.dump(database, file, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error saving database to {DATABASE_FILE}: {e}")
        return False

def is_admin(user_id):
    """Check if user is admin"""
    config = load_config()
    if not config:
        return False
    
    admin_ids = config.get('admin_ids', [])
    return user_id in admin_ids

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all commands and how they work (admin-aware)"""
    try:
        uid = update.effective_user.id
        admin = is_admin(uid)
        common = [
            "Comenzi pentru toți utilizatorii:",
            "- /start — Înregistrare și mesaj de bun venit",
            "- /info — Informații despre următorul webinar",
            "- /menu — Deschide meniul principal",
            "- /help — Afișează acest ajutor",
            "",
        ]
        if admin:
            admin_cmds = [
                "Comenzi pentru administratori:",
                "- /exportcsv — Exportă participanții în format CSV",
                "- /syncsheet — Sincronizează toți participanții către Google Sheets",
                "- /setmessage [welcome|info|reminder_day|reminder_15min] — Actualizează mesajele botului",
                "- /sendreminder [day|15min] — Trimite manual reminderul către toți participanții activi",
                "- /broadcast — Trimite un mesaj către toți participanții (cu confirmare)",
                "- /addadmin <id> — Adaugă un administrator",
                "- /deladmin <id> — Elimină un administrator",
                "- /listadmins — Listează administratorii",
                "- /setreminder day <Zi> <HH:MM> — Programează reminderul din ziua aleasă (ex: Tuesday 09:00)",
                "- /viewschedule — Afișează programarea curentă și cât timp a rămas până la următoarele evenimente",
                "- /setwebinar <Zi> <HH:MM> — Setează ziua și ora webinarului (ex: Tuesday 15:00)",
                "  Alte forme: /setwebinar day <Zi> | time <HH:MM> | timezone <Continent/City> | link <URL>",
                "",
                "Note:",
                "- Toate orele sunt interpretate în timezone-ul din config.json (webinar.timezone)",
                "- Reminderul 'pre15' se trimite automat cu 15 minute înainte de ora webinarului",
            ]
            text = "\n".join(common + admin_cmds)
        else:
            text = "\n".join(common)

        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
    except Exception as e:
        logger.error(f"Error in help_command: {e}")
        try:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Nu s-a putut afișa ajutorul acum.")
        except:
            pass

async def list_admins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all admin IDs"""
    try:
        # Only admins can list admins
        if not is_admin(update.effective_user.id):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⛔ Doar administratorii pot folosi această comandă."
            )
            return

        config = load_config() or {}
        admin_ids = config.get('admin_ids', [])
        if not admin_ids:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Nu există administratori configurați."
            )
            return

        ids_str = "\n".join(str(a) for a in admin_ids)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"👤 Lista adminilor:\n{ids_str}"
        )
    except Exception as e:
        logger.error(f"Error in list_admins_command: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="A apărut o eroare la listarea administratorilor."
        )

async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a new admin by Telegram user ID. Usage: /addadmin <user_id> or use the menu to be prompted."""
    try:
        if not is_admin(update.effective_user.id):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⛔ Doar administratorii pot folosi această comandă."
            )
            return

        if context.args and len(context.args) >= 1:
            candidate = context.args[0]
        else:
            # Prompt flow handled by message_handler when 'waiting_for_admin_add' is set
            context.user_data['waiting_for_admin_add'] = True
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Introduceți ID-ul numeric al utilizatorului pe care doriți să-l adăugați ca admin:"
            )
            return

        try:
            new_admin_id = int(candidate)
        except Exception:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="ID invalid. Vă rugăm să furnizați un număr întreg valid."
            )
            return

        cfg = load_config() or {}
        admin_ids = cfg.get('admin_ids', [])
        if new_admin_id in admin_ids:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"ID {new_admin_id} este deja administrator."
            )
            return

        admin_ids.append(new_admin_id)
        cfg['admin_ids'] = admin_ids
        if save_config(cfg):
            logger.info(f"Admin added: {new_admin_id} by {update.effective_user.id}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"✅ ID {new_admin_id} a fost adăugat ca administrator."
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Eroare la salvarea configurației. Încercați din nou."
            )
    except Exception as e:
        logger.error(f"Error in add_admin_command: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="A apărut o eroare la adăugarea administratorului."
        )

async def remove_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove an admin by Telegram user ID. Usage: /deladmin <user_id> or use the menu to be prompted."""
    try:
        if not is_admin(update.effective_user.id):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⛔ Doar administratorii pot folosi această comandă."
            )
            return

        if context.args and len(context.args) >= 1:
            candidate = context.args[0]
        else:
            # Prompt flow handled by message_handler when 'waiting_for_admin_remove' is set
            context.user_data['waiting_for_admin_remove'] = True
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Introduceți ID-ul numeric al utilizatorului pe care doriți să-l eliminați din admini:"
            )
            return

        try:
            admin_id_to_remove = int(candidate)
        except Exception:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="ID invalid. Vă rugăm să furnizați un număr întreg valid."
            )
            return

        cfg = load_config() or {}
        admin_ids = cfg.get('admin_ids', [])
        if admin_id_to_remove not in admin_ids:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"ID {admin_id_to_remove} nu se află în lista de administratori."
            )
            return

        admin_ids = [a for a in admin_ids if a != admin_id_to_remove]
        cfg['admin_ids'] = admin_ids
        if save_config(cfg):
            logger.info(f"Admin removed: {admin_id_to_remove} by {update.effective_user.id}")
            note = " Atenție: v-ați eliminat propriul ID." if admin_id_to_remove == update.effective_user.id else ""
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"✅ ID {admin_id_to_remove} a fost eliminat din administratori.{note}"
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Eroare la salvarea configurației. Încercați din nou."
            )
    except Exception as e:
        logger.error(f"Error in remove_admin_command: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="A apărut o eroare la eliminarea administratorului."
        )

def _normalize_day_name(name: str):
    days_map = {
        'monday': 'Monday', 'tuesday': 'Tuesday', 'wednesday': 'Wednesday',
        'thursday': 'Thursday', 'friday': 'Friday', 'saturday': 'Saturday', 'sunday': 'Sunday',
        # Romanian common names
        'luni': 'Monday', 'marți': 'Tuesday', 'marti': 'Tuesday', 'miercuri': 'Wednesday',
        'joi': 'Thursday', 'vineri': 'Friday', 'sâmbătă': 'Saturday', 'sambata': 'Saturday', 'duminică': 'Sunday', 'duminica': 'Sunday'
    }
    return days_map.get(name.strip().lower())

def _parse_time_hhmm(value: str):
    parts = value.strip().split(':')
    if len(parts) != 2:
        return None
    try:
        h = int(parts[0]); m = int(parts[1])
        if 0 <= h <= 23 and 0 <= m <= 59:
            return f"{h:02d}:{m:02d}"
    except Exception:
        return None
    return None

async def set_webinar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Configure webinar settings.
    Usage:
      /setwebinar <DayName> <HH:MM>
      /setwebinar datetime <DayName> <HH:MM>
      /setwebinar day <DayName>
      /setwebinar time <HH:MM>
      /setwebinar timezone <Continent/City>
      /setwebinar link <URL>
    Examples:
      /setwebinar Tuesday 15:00
      /setwebinar datetime Wednesday 19:30
      /setwebinar day Thursday
      /setwebinar time 10:15
      /setwebinar timezone Europe/Bucharest
      /setwebinar link https://zoom.us/j/abc
    """
    try:
        if not is_admin(update.effective_user.id):
            await context.bot.send_message(chat_id=update.effective_chat.id, text="⛔ Doar administratorii pot folosi această comandă.")
            return

        cfg = load_config() or {}
        if 'webinar' not in cfg:
            cfg['webinar'] = {}
        w = cfg['webinar']

        if not context.args or len(context.args) == 0:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=("Utilizare:\n"
                      "• /setwebinar <Zi> <HH:MM>\n"
                      "• /setwebinar datetime <Zi> <HH:MM>\n"
                      "• /setwebinar day <Zi>\n"
                      "• /setwebinar time <HH:MM>\n"
                      "• /setwebinar timezone <Continent/City>\n"
                      "• /setwebinar link <URL>")
            )
            return

        sub = context.args[0].lower()

        # Helper imports for timezone validation
        from pytz import all_timezones

        updated = False

        # Form: /setwebinar <DayName> <HH:MM>
        if len(context.args) == 2 and _normalize_day_name(context.args[0]) and _parse_time_hhmm(context.args[1]):
            w['day'] = _normalize_day_name(context.args[0])
            w['time'] = _parse_time_hhmm(context.args[1])
            updated = True
        elif sub == 'datetime' and len(context.args) >= 3:
            day_norm = _normalize_day_name(context.args[1])
            time_norm = _parse_time_hhmm(context.args[2])
            if not day_norm or not time_norm:
                await context.bot.send_message(chat_id=update.effective_chat.id, text="Zi sau oră invalidă.")
                return
            w['day'] = day_norm
            w['time'] = time_norm
            updated = True
        elif sub == 'day' and len(context.args) >= 2:
            day_norm = _normalize_day_name(context.args[1])
            if not day_norm:
                await context.bot.send_message(chat_id=update.effective_chat.id, text="Zi invalidă.")
                return
            w['day'] = day_norm
            updated = True
        elif sub == 'time' and len(context.args) >= 2:
            time_norm = _parse_time_hhmm(context.args[1])
            if not time_norm:
                await context.bot.send_message(chat_id=update.effective_chat.id, text="Oră invalidă.")
                return
            w['time'] = time_norm
            updated = True
        elif sub == 'timezone' and len(context.args) >= 2:
            tz = context.args[1]
            if tz not in all_timezones:
                await context.bot.send_message(chat_id=update.effective_chat.id, text="Timezone invalid. Exemplu: Europe/Bucharest")
                return
            w['timezone'] = tz
            updated = True
        elif sub == 'link' and len(context.args) >= 2:
            link = " ".join(context.args[1:]).strip()
            if not link.startswith("http"):
                await context.bot.send_message(chat_id=update.effective_chat.id, text="URL invalid. Vă rugăm să furnizați un link complet (http/https).")
                return
            w['link'] = link
            updated = True
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=("Format invalid. Exemple:\n"
                      "• /setwebinar Tuesday 15:00\n"
                      "• /setwebinar datetime Wednesday 19:30\n"
                      "• /setwebinar day Thursday\n"
                      "• /setwebinar time 10:15\n"
                      "• /setwebinar timezone Europe/Bucharest\n"
                      "• /setwebinar link https://zoom.us/j/abc")
            )
            return

        if updated:
            cfg['webinar'] = w
            if not save_config(cfg):
                await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Eroare la salvarea configurației.")
                return
            try:
                refresh_scheduler(context.bot)
            except Exception as e:
                logger.error(f"Failed to refresh scheduler after setwebinar: {e}")
            await context.bot.send_message(chat_id=update.effective_chat.id, text="✅ Setările webinarului au fost actualizate.")
            return
    except Exception as e:
        logger.error(f"Error in set_webinar_command: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="A apărut o eroare la actualizarea setărilor webinarului.")

async def set_reminder_schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Configure 'day' reminder schedule.
    Usage: /setreminder day <DayName> <HH:MM>
    Example: /setreminder day Tuesday 09:00
    Note: 'pre15' is always 15 minutes before the webinar time.
    """
    try:
        if not is_admin(update.effective_user.id):
            await context.bot.send_message(chat_id=update.effective_chat.id, text="⛔ Doar administratorii pot folosi această comandă.")
            return

        if not context.args or len(context.args) < 2:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=("Utilizare: /setreminder day <Zi> <HH:MM>\n"
                      "Exemplu: /setreminder day Tuesday 09:00\n"
                      "Notă: 'pre15' se trimite automat cu 15 minute înainte de webinar.")
            )
            return

        rtype = context.args[0].lower()
        if rtype != 'day':
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Tip invalid. Folosiți doar 'day'. 'pre15' este automat.")
            return

        cfg = load_config() or {}
        reminders = cfg.get('reminders', {})

        if rtype == 'day':
            if len(context.args) < 3:
                await context.bot.send_message(chat_id=update.effective_chat.id, text="Utilizare: /setreminder day <Zi> <HH:MM>")
                return
            day_raw = context.args[1]
            time_raw = context.args[2]
            day_norm = _normalize_day_name(day_raw)
            time_norm = _parse_time_hhmm(time_raw)
            if not day_norm or not time_norm:
                await context.bot.send_message(chat_id=update.effective_chat.id, text="Zi sau oră invalidă.")
                return
            reminders['day'] = {'day': day_norm, 'time': time_norm}
        # No editable settings for 'pre15' anymore

        cfg['reminders'] = reminders
        if not save_config(cfg):
            await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Eroare la salvarea configurației.")
            return

        # Refresh scheduler
        try:
            refresh_scheduler(context.bot)
        except Exception as e:
            logger.error(f"Failed to refresh scheduler after setreminder: {e}")
        
        await context.bot.send_message(chat_id=update.effective_chat.id, text="✅ Programarea reminderelor a fost actualizată.")

    except Exception as e:
        logger.error(f"Error in set_reminder_schedule_command: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="A apărut o eroare la configurarea programării.")

async def view_schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show effective schedule and time remaining to next webinar and reminders"""
    try:
        if not is_admin(update.effective_user.id):
            await context.bot.send_message(chat_id=update.effective_chat.id, text="⛔ Doar administratorii pot folosi această comandă.")
            return
        config = load_config()
        if not config:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Nu s-a putut încărca configurația.")
            return
        preview = get_schedule_preview(config)
        from datetime import datetime as _dt
        from pytz import timezone as _tz
        tz = _tz(config['webinar'].get('timezone', 'Europe/Bucharest'))
        now = _dt.now(tz)

        def fmt_dt(d):
            # Show local time and relative delta
            delta = d - now
            total_seconds = int(delta.total_seconds())
            if total_seconds < 0:
                rel = "(în trecut)"
            else:
                days = total_seconds // 86400
                hours = (total_seconds % 86400) // 3600
                minutes = (total_seconds % 3600) // 60
                parts = []
                if days: parts.append(f"{days}d")
                if hours: parts.append(f"{hours}h")
                if minutes or not parts: parts.append(f"{minutes}m")
                rel = "în " + " ".join(parts)
            return d.strftime("%a, %d %b %Y %H:%M %Z") + f"  • {rel}"

        w = preview['webinar']
        d = preview['day']
        p = preview['pre15']
        msg = (
            "⏰ Programare curentă\n\n"
            f"• Webinar: {w['day']} la {w['time']} ({w['timezone']})\n"
            f"  Următorul: {fmt_dt(w['next'])}\n\n"
            f"• Reminder 'day': {d['day']} la {d['time']}\n"
            f"  Următorul: {fmt_dt(d['next'])}\n\n"
            f"• Reminder 'pre15': {p['day']} la {p['time']}\n"
            f"  Următorul: {fmt_dt(p['next'])}"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    except Exception as e:
        logger.error(f"Error in view_schedule_command: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="A apărut o eroare la afișarea programării.")
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - register user and send welcome message"""
    try:
        user = update.effective_user
        chat_id = update.effective_chat.id
        
        # Load database
        database = load_database()
        
        # Check if user already exists
        is_new = False
        if str(chat_id) not in database['participants']:
            # Register new user
            database['participants'][str(chat_id)] = {
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'chat_id': chat_id,
                'registration_date': datetime.datetime.now().isoformat(),
                'active': True
            }
            is_new = True
            
            # Save database
            save_database(database)
            logger.info(f"New user registered: {user.username} (ID: {chat_id})")
        
        # Load welcome message
        config = load_config()
        welcome_message = config['messages']['welcome']
        
        # Get next webinar date
        next_webinar = get_next_webinar_date(config)
        
        # Replace placeholders with user's actual name and webinar date
        first_name = user.first_name or ""
        last_name = user.last_name or ""
        personalized_welcome = welcome_message.replace("{first_name}", first_name) \
                                             .replace("{last_name}", last_name) \
                                             .replace("{next_webinar_date}", next_webinar['formatted']) \
                                             .replace("{webinar_day}", next_webinar['day_name']) \
                                             .replace("{webinar_time}", next_webinar['time'])
        
        # Upsert to Google Sheets (if enabled)
        try:
            cfg = load_config() or {}
            client = get_sheets_client(cfg)
            if client:
                client.upsert_user(database['participants'][str(chat_id)])
        except Exception as e:
            logger.warning(f"Sheets upsert failed: {e}")

        # Send welcome/info message
        await context.bot.send_message(chat_id=chat_id, text=personalized_welcome)
        
        # Afișăm un mesaj despre meniu cu un buton pentru acces rapid
        keyboard = [
            [InlineKeyboardButton("📋 Deschide Meniul", callback_data="cmd_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=chat_id,
            text="Pentru a accesa meniul de comenzi în orice moment, foloseși comanda /menu sau apasă butonul de mai jos:",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Error in start_command: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="A apărut o eroare la procesarea comenzii. Vă rugăm încercați din nou mai târziu."
        )

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /info command - send webinar information"""
    try:
        # Load info message
        config = load_config()
        info_message = config['messages']['info']
        
        # Get next webinar date
        next_webinar = get_next_webinar_date(config)
        
        # Replace placeholders with webinar date
        personalized_info = info_message.replace("{next_webinar_date}", next_webinar['formatted']) \
                                       .replace("{webinar_day}", next_webinar['day_name']) \
                                       .replace("{webinar_time}", next_webinar['time'])
        
        # Send info message
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=personalized_info
        )
        
    except Exception as e:
        logger.error(f"Error in info_command: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="A apărut o eroare la procesarea comenzii. Vă rugăm încercați din nou mai târziu."
        )

async def export_csv_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /exportcsv command - export participants to CSV file"""
    try:
        user_id = update.effective_user.id
        
        # Check if user is admin
        if not is_admin(user_id):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Nu aveți permisiunea de a executa această comandă."
            )
            return
        
        # Load database
        database = load_database()
        participants = database['participants']
        
        # Create CSV file
        filename = f"participants_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(filename, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            # Write header
            writer.writerow(['Chat ID', 'Username', 'First Name', 'Last Name', 'Registration Date', 'Active'])
            
            # Write participants
            for chat_id, participant in participants.items():
                writer.writerow([
                    chat_id,
                    participant.get('username', ''),
                    participant.get('first_name', ''),
                    participant.get('last_name', ''),
                    participant.get('registration_date', ''),
                    participant.get('active', False)
                ])
        
        # Send CSV file
        with open(filename, 'rb') as file:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=file,
                filename=filename
            )
        
        # Remove temporary file
        import os
        os.remove(filename)
        
    except Exception as e:
        logger.error(f"Error in export_csv_command: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="A apărut o eroare la procesarea comenzii. Vă rugăm încercați din nou mai târziu."
        )

async def sync_sheet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: Push entire participant list to Google Sheets"""
    try:
        if not is_admin(update.effective_user.id):
            await context.bot.send_message(chat_id=update.effective_chat.id, text="⛔ Acces interzis!")
            return
        cfg = load_config() or {}
        client = get_sheets_client(cfg)
        if not client:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Google Sheets nu este configurat sau nu s-a putut conecta.")
            return
        db = load_database()
        ok = client.bulk_export(db.get('participants', {}))
        if ok:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="✅ Sincronizare reușită către Google Sheets.")
        else:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="❌ Sincronizare eșuată.")
    except Exception as e:
        logger.error(f"Error in sync_sheet_command: {e}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="A apărut o eroare la sincronizare.")

async def set_message_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /setmessage command - set custom message"""
    try:
        user_id = update.effective_user.id
        
        # Check if user is admin
        if not is_admin(user_id):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Nu aveți permisiunea de a executa această comandă."
            )
            return
        
        # Check if message type is provided
        if not context.args or len(context.args) < 1:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Utilizare: /setmessage [welcome|info|reminder_day|reminder_15min] și apoi trimite mesajul formatat pe mai multe linii într-un mesaj separat"
            )
            return
        
        message_type = context.args[0]
        
        # Check if message type is valid
        valid_types = ['welcome', 'info', 'reminder_day', 'reminder_15min']
        if message_type not in valid_types:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Tip de mesaj invalid. Tipurile valide sunt: {', '.join(valid_types)}"
            )
            return
        
        # Ask for the formatted message
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Te rog trimite acum textul formatat pentru mesajul de tip '{message_type}':"
        )
        
        # Store the message type in user_data for the next step
        context.user_data['pending_message_type'] = message_type
        
    except Exception as e:
        logger.error(f"Error in set_message_command: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="A apărut o eroare la procesarea comenzii. Vă rugăm încercați din nou mai târziu."
        )

async def send_reminder_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /sendreminder command - send manual reminder"""
    try:
        user_id = update.effective_user.id
        
        # Check if user is admin
        if not is_admin(user_id):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Nu aveți permisiunea de a executa această comandă."
            )
            return
        
        # Check if reminder type is provided
        if not context.args or context.args[0] not in ['day', '15min']:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Utilizare: /sendreminder [day|15min]"
            )
            return
        
        reminder_type = context.args[0]
        
        # Send reminder
        await send_reminder_to_all(context.bot, reminder_type)
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Reminder de tip '{reminder_type}' a fost trimis cu succes."
        )
        
    except Exception as e:
        logger.error(f"Error in send_reminder_command: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="A apărut o eroare la procesarea comenzii. Vă rugăm încercați din nou mai târziu."
        )

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages - used for setting formatted messages after /setmessage command
    and handling broadcast messages after /broadcast command, as well as keyboard buttons"""
    try:
        user_id = update.effective_user.id
        message_text = update.message.text
        
        # Verifică dacă mesajul este de la un buton de tastatură
        command = handle_keyboard_button(message_text)
        if command:
            # Simulăm comanda corespunzătoare
            if command == "/info":
                await info_command(update, context)
                return
            elif command == "/help":
                await help_command(update, context)
                return
            elif command == "/menu":
                await menu_command(update, context)
                return
            elif command == "/adminmenu" and is_admin(user_id):
                await admin_menu_command(update, context)
                return
            elif command == "/exportcsv" and is_admin(user_id):
                await export_csv_command(update, context)
                return
            elif command == "/setmessage" and is_admin(user_id):
                context.args = []  # Initialize empty args
                await set_message_command(update, context)
                return
            elif command == "/sendreminder" and is_admin(user_id):
                context.args = []  # Initialize empty args
                await send_reminder_command(update, context)
                return
            elif command == "/broadcast" and is_admin(user_id):
                await broadcast_command(update, context)
                return
            elif command == "/addadmin" and is_admin(user_id):
                context.args = []  # trigger interactive prompt
                await add_admin_command(update, context)
                return
            elif command == "/deladmin" and is_admin(user_id):
                context.args = []  # trigger interactive prompt
                await remove_admin_command(update, context)
                return
            elif command == "/listadmins" and is_admin(user_id):
                await list_admins_command(update, context)
                return
        
        # Admin management prompts (can only be used by admins)
        if context.user_data.get('waiting_for_admin_add'):
            if not is_admin(user_id):
                # Clear state and ignore
                del context.user_data['waiting_for_admin_add']
                return
            candidate = update.message.text.strip()
            context.args = [candidate]
            # Clear state before executing
            del context.user_data['waiting_for_admin_add']
            await add_admin_command(update, context)
            return

        if context.user_data.get('waiting_for_admin_remove'):
            if not is_admin(user_id):
                del context.user_data['waiting_for_admin_remove']
                return
            candidate = update.message.text.strip()
            context.args = [candidate]
            del context.user_data['waiting_for_admin_remove']
            await remove_admin_command(update, context)
            return

        # Pending webinar settings prompts
        if context.user_data.get('pending_setwebinar'):
            if not is_admin(user_id):
                del context.user_data['pending_setwebinar']
                return
            pending = context.user_data['pending_setwebinar']
            text = update.message.text.strip()
            if pending == 'day':
                context.args = ['day', text]
            elif pending == 'time':
                context.args = ['time', text]
            elif pending == 'timezone':
                context.args = ['timezone', text]
            elif pending == 'link':
                context.args = ['link'] + text.split()
            else:
                del context.user_data['pending_setwebinar']
                return
            del context.user_data['pending_setwebinar']
            await set_webinar_command(update, context)
            return

        # Pending set reminder flow from menu (day only)
        if context.user_data.get('pending_setrem_type'):
            if not is_admin(user_id):
                del context.user_data['pending_setrem_type']
                return
            rtype = context.user_data['pending_setrem_type']
            text = update.message.text.strip()
            parts = text.split()
            # Build args for the command and delegate
            if rtype == 'day':
                # Expect: <Zi> <HH:MM>
                if len(parts) != 2:
                    await context.bot.send_message(chat_id=update.effective_chat.id, text="Format invalid. Exemplu: Tuesday 09:00")
                    return
                context.args = ['day', parts[0], parts[1]]
            else:
                await context.bot.send_message(chat_id=update.effective_chat.id, text="Tip invalid. Folosiți doar 'day'.")
                del context.user_data['pending_setrem_type']
                return
            del context.user_data['pending_setrem_type']
            await set_reminder_schedule_command(update, context)
            return

        # Check if user is admin for remaining handlers
        if not is_admin(user_id):
            return
        
        # Check if we're waiting for a broadcast message
        if context.user_data.get('waiting_for_broadcast_message'):
            # Get the message text
            message_text = update.message.text
            
            # Clear the waiting state
            del context.user_data['waiting_for_broadcast_message']
            
            # Load database to get all users
            database = load_database()
            participants = database.get('participants', {})
            
            if not participants:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="Nu există participanți înregistrați pentru a trimite mesajul."
                )
                return
            
            # Send confirmation message before broadcasting
            confirmation_text = f"Sunteți pe cale să trimiteți următorul mesaj la {len(participants)} participanți:\n\n{message_text}\n\nConfirmați trimiterea? (Da/Nu)"
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=confirmation_text
            )
            
            # Store message and waiting state in user_data
            context.user_data['pending_broadcast'] = message_text
            context.user_data['waiting_for_broadcast_confirmation'] = True
            return
        
        # Check if we're waiting for broadcast confirmation
        if context.user_data.get('waiting_for_broadcast_confirmation'):
            user_response = update.message.text.strip().lower()
            
            if user_response == 'da':
                # Get the pending broadcast message
                message_text = context.user_data['pending_broadcast']
                
                # Load database
                database = load_database()
                participants = database.get('participants', {})
                
                # Count successful and failed sends
                success_count = 0
                failed_count = 0
                
                # Send message to all participants
                for chat_id, user_data in participants.items():
                    try:
                        # Replace placeholders if any
                        personalized_message = message_text.format(
                            first_name=user_data.get('first_name', ''),
                            last_name=user_data.get('last_name', '')
                        )
                        
                        await context.bot.send_message(
                            chat_id=int(chat_id),
                            text=personalized_message
                        )
                        success_count += 1
                    except Exception as e:
                        logger.error(f"Failed to send broadcast to {chat_id}: {e}")
                        failed_count += 1
                
                # Send summary to admin
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"✅ Broadcast finalizat!\n\n• Mesaje trimise cu succes: {success_count}\n• Mesaje eșuate: {failed_count}"
                )
                
                # Log the broadcast
                admin_name = update.effective_user.username or update.effective_user.first_name
                logger.info(f"Broadcast sent by admin {admin_name} (ID: {user_id}) to {success_count} users. Failed: {failed_count}")
                
            elif user_response == 'nu':
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="Broadcast anulat."
                )
            else:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="Răspuns nevalid. Vă rugăm să răspundeți cu 'Da' sau 'Nu'."
                )
                # Keep waiting for confirmation
                return
            
            # Clear pending state regardless of yes/no
            del context.user_data['pending_broadcast']
            del context.user_data['waiting_for_broadcast_confirmation']
            return
        
        # Check if we're waiting for a message after /setmessage
        if 'pending_message_type' in context.user_data:
            message_type = context.user_data['pending_message_type']
            message_text = update.message.text
            
            # Load config
            config = load_config()
            
            # Update message
            config['messages'][message_type] = message_text
            
            # Save config
            with open('config.json', 'w', encoding='utf-8') as file:
                json.dump(config, file, indent=4, ensure_ascii=False)
            
            # Clear pending state
            del context.user_data['pending_message_type']
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"Mesajul de tip '{message_type}' a fost actualizat cu succes."
            )
            
    except Exception as e:
        logger.error(f"Error in message_handler: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="A apărut o eroare la procesarea mesajului. Vă rugăm încercați din nou mai târziu."
        )

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /broadcast command - allow admins to send a message to all registered users
    The bot will ask for the message in a separate chat after the command is issued
    """
    try:
        user_id = update.effective_user.id
        
        # Check if user is admin
        if not is_admin(user_id):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⛔ Acces interzis! Doar administratorii pot folosi această comandă."
            )
            logger.warning(f"Non-admin user {user_id} tried to use /broadcast command")
            return
        
        # Always ask for the message in a separate chat, regardless of args
        # Ignore any text that might be after the command
        
        # Set state to wait for the broadcast message
        context.user_data['waiting_for_broadcast_message'] = True
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Vă rugăm să introduceți mesajul pe care doriți să îl transmiteți tuturor participanților:"
        )
        
    except Exception as e:
        logger.error(f"Error in broadcast_command: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="A apărut o eroare la procesarea comenzii. Vă rugăm încercați din nou mai târziu."
        )

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display the main menu with commands appropriate for the user's role"""
    try:
        user_id = update.effective_user.id
        is_user_admin = is_admin(user_id)
        
        if is_user_admin:
            # Admin menu
            keyboard = [
                [InlineKeyboardButton("ℹ️ Info", callback_data="cmd_info"), InlineKeyboardButton("❓ Ajutor", callback_data="cmd_help")],
                [InlineKeyboardButton("📊 Export CSV", callback_data="cmd_exportcsv")],
                [InlineKeyboardButton("🗂️ Sincronizează Sheet", callback_data="cmd_syncsheet")],
                [InlineKeyboardButton("✉️ Setare mesaje", callback_data="cmd_setmessage")],
                [InlineKeyboardButton("🔔 Trimitere reminder", callback_data="cmd_sendreminder")],
                [InlineKeyboardButton("👁️ Vezi programare", callback_data="cmd_viewschedule")],
                [InlineKeyboardButton("⏰ Programare reminder", callback_data="cmd_schedreminder")],
                [InlineKeyboardButton("� Setează webinar", callback_data="cmd_setwebinar")],
                [InlineKeyboardButton("�📢 Broadcast", callback_data="cmd_broadcast")],
                [InlineKeyboardButton("👤 Administratori", callback_data="cmd_admins")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="🛠️ *Meniu Administrator*\n\nSelectați o comandă:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            # Regular user menu
            keyboard = [
                [InlineKeyboardButton("ℹ️ Informații", callback_data="cmd_info"), InlineKeyboardButton("❓ Ajutor", callback_data="cmd_help")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="📋 *Meniu Participant*\n\nSelectați o comandă:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Error in menu_command: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="A apărut o eroare la afișarea meniului. Vă rugăm încercați din nou mai târziu."
        )

async def admin_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display admin menu (accessible only to admins)"""
    try:
        user_id = update.effective_user.id
        
        # Check if user is admin
        if not is_admin(user_id):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⛔ Acces interzis! Doar administratorii pot accesa acest meniu."
            )
            return
        
        # Admin menu
        keyboard = [
            [InlineKeyboardButton("ℹ️ Info", callback_data="cmd_info")],
            [InlineKeyboardButton("📊 Export CSV", callback_data="cmd_exportcsv")],
            [InlineKeyboardButton("✉️ Setare mesaje", callback_data="cmd_setmessage")],
            [InlineKeyboardButton("🔔 Trimitere reminder", callback_data="cmd_sendreminder")],
            [InlineKeyboardButton("👁️ Vezi programare", callback_data="cmd_viewschedule")],
            [InlineKeyboardButton("⏰ Programare reminder", callback_data="cmd_schedreminder")],
            [InlineKeyboardButton("📅 Setează webinar", callback_data="cmd_setwebinar")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="cmd_broadcast")],
            [InlineKeyboardButton("👤 Administratori", callback_data="cmd_admins")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🛠️ *Meniu Administrator*\n\nSelectați o comandă:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
            
    except Exception as e:
        logger.error(f"Error in admin_menu_command: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="A apărut o eroare la afișarea meniului de administrator. Vă rugăm încercați din nou mai târziu."
        )

async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button presses from inline keyboards"""
    try:
        query = update.callback_query
        await query.answer()  # Answer the callback query
        
        # Get the callback data
        callback_data = query.data
        
        # Execute the corresponding command based on callback data
        if callback_data == "cmd_info":
            await info_command(update, context)
        elif callback_data == "cmd_help":
            await help_command(update, context)
        elif callback_data == "cmd_menu":
            # Afișăm meniul corespunzător utilizatorului
            await menu_command(update, context)
        elif callback_data == "cmd_exportcsv":
            # Check if user is admin
            if not is_admin(update.effective_user.id):
                await query.edit_message_text(text="⛔ Acces interzis! Doar administratorii pot folosi această comandă.")
                return
            await export_csv_command(update, context)
        elif callback_data == "cmd_syncsheet":
            if not is_admin(update.effective_user.id):
                await query.edit_message_text(text="⛔ Acces interzis! Doar administratorii pot folosi această comandă.")
                return
            await sync_sheet_command(update, context)
        elif callback_data == "cmd_setmessage":
            # Check if user is admin
            if not is_admin(update.effective_user.id):
                await query.edit_message_text(text="⛔ Acces interzis! Doar administratorii pot folosi această comandă.")
                return
            
            # Pentru setmessage, în loc să apelăm direct funcția, trimitem un mesaj cu opțiunile
            keyboard = [
                [InlineKeyboardButton("Mesaj bun venit", callback_data="setmsg_welcome")],
                [InlineKeyboardButton("Mesaj info", callback_data="setmsg_info")],
                [InlineKeyboardButton("Reminder în ziua webinarului", callback_data="setmsg_reminder_day")],
                [InlineKeyboardButton("Reminder cu 15 minute înainte", callback_data="setmsg_reminder_15min")],
                [InlineKeyboardButton("❌ Anulare", callback_data="cancel_action")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text="Selectați tipul de mesaj pe care doriți să îl modificați:",
                reply_markup=reply_markup
            )
            return
            
        elif callback_data.startswith("setmsg_"):
            # Procesăm submeniul pentru setmessage
            if not is_admin(update.effective_user.id):
                await query.edit_message_text(text="⛔ Acces interzis! Doar administratorii pot folosi această comandă.")
                return
                
            # Extragem tipul de mesaj din callback_data
            message_type = callback_data[7:]  # eliminăm "setmsg_" de la început
            
            # Simulăm argumentele pentru set_message_command
            context.args = [message_type]
            
            # Eliminăm meniul inline și afișăm prompt-ul pentru noul mesaj
            await query.edit_message_text(
                text=f"Te rog trimite acum textul formatat pentru mesajul de tip '{message_type}':"
            )
            
            # Setăm starea în așteptarea mesajului
            context.user_data['pending_message_type'] = message_type
            return
            
        elif callback_data == "cmd_sendreminder":
            # Check if user is admin
            if not is_admin(update.effective_user.id):
                await query.edit_message_text(text="⛔ Acces interzis! Doar administratorii pot folosi această comandă.")
                return
                
            # Pentru sendreminder, afișăm un submeniu pentru a alege tipul de reminder
            keyboard = [
                [InlineKeyboardButton("Reminder în ziua webinarului", callback_data="sendrm_day")],
                [InlineKeyboardButton("Reminder cu 15 minute înainte", callback_data="sendrm_15min")],
                [InlineKeyboardButton("❌ Anulare", callback_data="cancel_action")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text="Selectați tipul de reminder pe care doriți să îl trimiteți:",
                reply_markup=reply_markup
            )
            return
        elif callback_data == "cmd_schedreminder":
            # Schedule configuration submenu
            if not is_admin(update.effective_user.id):
                await query.edit_message_text(text="⛔ Acces interzis! Doar administratorii pot folosi această comandă.")
                return
            keyboard = [
                [InlineKeyboardButton("Setează 'day' (Zi HH:MM)", callback_data="setrem_day")],
                [InlineKeyboardButton("❌ Anulare", callback_data="cancel_action")]
            ]
            await query.edit_message_text(
                text=("Configurați programarea pentru 'day'.\n"
                      "Exemplu: Tuesday 09:00\n"
                      "Notă: 'pre15' se trimite automat cu 15 minute înainte de webinar."),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        elif callback_data == "cmd_viewschedule":
            if not is_admin(update.effective_user.id):
                await query.edit_message_text(text="⛔ Acces interzis! Doar administratorii pot folosi această comandă.")
                return
            await view_schedule_command(update, context)
            return
        elif callback_data == "cmd_setwebinar":
            if not is_admin(update.effective_user.id):
                await query.edit_message_text(text="⛔ Acces interzis! Doar administratorii pot folosi această comandă.")
                return
            keyboard = [
                [InlineKeyboardButton("Setează ziua", callback_data="setwb_day")],
                [InlineKeyboardButton("Setează ora", callback_data="setwb_time")],
                [InlineKeyboardButton("Setează timezone", callback_data="setwb_timezone")],
                [InlineKeyboardButton("Setează link", callback_data="setwb_link")],
                [InlineKeyboardButton("❌ Anulare", callback_data="cancel_action")]
            ]
            await query.edit_message_text(
                text=("Setări webinar: alegeți ce modificați.\n"
                      "• Zi: ex. Tuesday\n"
                      "• Oră: ex. 15:00\n"
                      "• Timezone: ex. Europe/Bucharest\n"
                      "• Link: URL complet"),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        elif callback_data.startswith("setwb_"):
            if not is_admin(update.effective_user.id):
                await query.edit_message_text(text="⛔ Acces interzis! Doar administratorii pot folosi această comandă.")
                return
            field = callback_data.split('_', 1)[1]
            context.user_data['pending_setwebinar'] = field
            prompts = {
                'day': "Introduceți noua zi a webinarului (ex: Tuesday / marți):",
                'time': "Introduceți noua oră a webinarului (HH:MM):",
                'timezone': "Introduceți noul timezone (ex: Europe/Bucharest):",
                'link': "Introduceți noul link (URL complet):"
            }
            await query.edit_message_text(text=prompts.get(field, "Introduceți valoarea:"))
            return
        elif callback_data == "setrem_day":
            if not is_admin(update.effective_user.id):
                await query.edit_message_text(text="⛔ Acces interzis! Doar administratorii pot folosi această comandă.")
                return
            context.user_data['pending_setrem_type'] = 'day'
            await query.edit_message_text(text="Trimiteți acum: <Zi> <HH:MM> (ex: Tuesday 09:00)")
            return
        
            
        elif callback_data.startswith("sendrm_"):
            # Procesăm submeniul pentru sendreminder
            if not is_admin(update.effective_user.id):
                await query.edit_message_text(text="⛔ Acces interzis! Doar administratorii pot folosi această comandă.")
                return
                
            # Extragem tipul de reminder din callback_data
            reminder_type = callback_data[7:]  # eliminăm "sendrm_" de la început
            
            # Simulăm argumentele pentru send_reminder_command
            context.args = [reminder_type]
            
            # Apelăm funcția pentru trimiterea reminderului
            await send_reminder_to_all(context.bot, reminder_type)
            
            # Afișăm un mesaj de confirmare
            await query.edit_message_text(
                text=f"✅ Reminderul de tip '{reminder_type}' a fost trimis cu succes tuturor participanților."
            )
            return
            
        elif callback_data == "cmd_broadcast":
            # Check if user is admin
            if not is_admin(update.effective_user.id):
                await query.edit_message_text(text="⛔ Acces interzis! Doar administratorii pot folosi această comandă.")
                return
            await broadcast_command(update, context)
        elif callback_data == "cmd_admins":
            # Admin management submenu
            if not is_admin(update.effective_user.id):
                await query.edit_message_text(text="⛔ Acces interzis! Doar administratorii pot folosi această comandă.")
                return
            keyboard = [
                [InlineKeyboardButton("👥 Listează admini", callback_data="admins_list")],
                [InlineKeyboardButton("➕ Adaugă admin", callback_data="admins_add")],
                [InlineKeyboardButton("➖ Șterge admin", callback_data="admins_remove")],
                [InlineKeyboardButton("❌ Anulare", callback_data="cancel_action")]
            ]
            await query.edit_message_text(
                text="Gestionare administratori: alegeți o acțiune.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        elif callback_data == "admins_list":
            if not is_admin(update.effective_user.id):
                await query.edit_message_text(text="⛔ Acces interzis! Doar administratorii pot folosi această comandă.")
                return
            await list_admins_command(update, context)
            return
        elif callback_data == "admins_add":
            if not is_admin(update.effective_user.id):
                await query.edit_message_text(text="⛔ Acces interzis! Doar administratorii pot folosi această comandă.")
                return
            context.user_data['waiting_for_admin_add'] = True
            await query.edit_message_text(text="Introduceți ID-ul numeric al utilizatorului pentru a-l adăuga ca admin:")
            return
        elif callback_data == "admins_remove":
            if not is_admin(update.effective_user.id):
                await query.edit_message_text(text="⛔ Acces interzis! Doar administratorii pot folosi această comandă.")
                return
            context.user_data['waiting_for_admin_remove'] = True
            await query.edit_message_text(text="Introduceți ID-ul numeric al utilizatorului pentru a-l elimina din admini:")
            return
        elif callback_data == "cancel_action":
            # Anulare acțiune
            await query.edit_message_text(
                text="✅ Acțiune anulată. Folosiți /menu pentru a afișa din nou meniul principal."
            )
            
            # Curățăm orice stare în așteptare, dacă există
            if 'pending_message_type' in context.user_data:
                del context.user_data['pending_message_type']
            if 'waiting_for_broadcast_message' in context.user_data:
                del context.user_data['waiting_for_broadcast_message']
            if 'waiting_for_broadcast_confirmation' in context.user_data:
                del context.user_data['waiting_for_broadcast_confirmation']
            if 'pending_broadcast' in context.user_data:
                del context.user_data['pending_broadcast']
            
    except Exception as e:
        logger.error(f"Error in button_callback_handler: {e}")
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="A apărut o eroare la procesarea comenzii. Vă rugăm încercați din nou mai târziu."
            )
        except:
            pass