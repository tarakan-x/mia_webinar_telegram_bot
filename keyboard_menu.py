#!/usr/bin/env python
# -*- coding: utf-8 -*-

def handle_keyboard_button(text):
    """Map keyboard button text to command"""
    button_map = {
        "ℹ️ Info": "/info",
        "📋 Meniu": "/menu",
        "❓ Ajutor": "/help",
        "📊 Export CSV": "/exportcsv",
        "✉️ Setare mesaje": "/setmessage",
        "🔔 Reminder": "/sendreminder",
        "📢 Broadcast": "/broadcast",
        "👤 Admini": "/adminmenu",
        "➕ Add Admin": "/addadmin",
        "➖ Del Admin": "/deladmin",
        "👥 List Admins": "/listadmins"
    }
    return button_map.get(text)