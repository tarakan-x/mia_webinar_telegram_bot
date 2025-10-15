#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import logging
from typing import Dict, Any, Optional

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.readonly'
]

class SheetsClient:
    def __init__(self, enabled: bool, creds_path: str, spreadsheet_id: str, worksheet_name: str):
        self.enabled = enabled
        self.creds_path = creds_path
        self.spreadsheet_id = spreadsheet_id
        self.worksheet_name = worksheet_name
        self.gc = None
        self.ws = None

    def _extract_id(self, value: str) -> str:
        # Accept either an ID or a full URL
        if not value:
            return ''
        if '/spreadsheets/d/' in value:
            try:
                part = value.split('/spreadsheets/d/')[1]
                return part.split('/', 1)[0]
            except Exception:
                return value
        return value

    def connect(self):
        if not self.enabled:
            return False
        try:
            creds = Credentials.from_service_account_file(self.creds_path, scopes=SCOPES)
            self.gc = gspread.authorize(creds)
            sheet_id = self._extract_id(self.spreadsheet_id)
            sh = self.gc.open_by_key(sheet_id)
            try:
                self.ws = sh.worksheet(self.worksheet_name)
            except gspread.WorksheetNotFound:
                self.ws = sh.add_worksheet(title=self.worksheet_name, rows=1000, cols=20)
            self.ensure_headers()
            logger.info("Connected to Google Sheet '%s' (%s)", self.worksheet_name, self.spreadsheet_id)
            return True
        except Exception as e:
            msg = str(e)
            if '404' in msg:
                logger.error("Failed to connect to Google Sheets (404). Check spreadsheet_id and that the Sheet exists. If you passed a URL, it's accepted; we're extracting the ID.")
            elif '403' in msg or 'PERMISSION' in msg.upper():
                logger.error("Failed to connect to Google Sheets (403). Share the sheet with the service account email as Editor and enable Sheets/Drive APIs.")
            else:
                logger.error("Failed to connect to Google Sheets: %s", e)
            return False

    def ensure_headers(self):
        if not self.ws:
            return
        headers = [
            'Chat ID', 'Username', 'First Name', 'Last Name', 'Registration Date', 'Active'
        ]
        try:
            current = self.ws.row_values(1)
            # Ensure at least header row exists
            self.ensure_capacity(min_rows=1, min_cols=6)
            if current != headers:
                self.ws.update('A1:F1', [headers])
        except Exception as e:
            logger.warning("Could not ensure headers: %s", e)

    def ensure_capacity(self, min_rows: int = 2, min_cols: int = 6):
        if not self.ws:
            return
        try:
            rows = self.ws.row_count
            cols = self.ws.col_count
            target_rows = max(rows, min_rows)
            target_cols = max(cols, min_cols)
            if target_rows != rows or target_cols != cols:
                self.ws.resize(rows=target_rows, cols=target_cols)
        except Exception as e:
            logger.warning("Could not ensure capacity (rows/cols): %s", e)

    def upsert_user(self, participant: Dict[str, Any]):
        if not self.enabled or not self.ws:
            return False
        try:
            chat_id = str(participant.get('chat_id', ''))
            # Find existing by Chat ID in column A
            cell = self.ws.find(chat_id) if chat_id else None
            row = None
            if cell and cell.col == 1:
                row = cell.row
            values = [
                chat_id,
                participant.get('username', ''),
                participant.get('first_name', ''),
                participant.get('last_name', ''),
                participant.get('registration_date', ''),
                'TRUE' if participant.get('active', False) else 'FALSE'
            ]
            if row:
                # Update existing row
                self.ws.update(f'A{row}:F{row}', [values])
            else:
                # Append new row
                self.ws.append_row(values)
            return True
        except Exception as e:
            logger.error("Failed to upsert user to Google Sheets: %s", e)
            return False

    def bulk_export(self, participants: Dict[str, Dict[str, Any]]):
        if not self.enabled or not self.ws:
            return False
        try:
            rows = []
            for chat_id, p in participants.items():
                rows.append([
                    chat_id,
                    p.get('username', ''),
                    p.get('first_name', ''),
                    p.get('last_name', ''),
                    p.get('registration_date', ''),
                    'TRUE' if p.get('active', False) else 'FALSE'
                ])
            self.ws.clear()
            # Make sure there is enough room for headers + all rows
            need_rows = max(1 + len(rows), 2)
            self.ensure_capacity(min_rows=need_rows, min_cols=6)
            # Restore headers after clear
            self.ensure_headers()
            if rows:
                end_row = len(rows) + 1
                self.ws.update(f'A2:F{end_row}', rows)
            return True
        except Exception as e:
            logger.error("Failed to bulk export to Google Sheets: %s", e)
            return False


def get_sheets_client(config: Dict[str, Any]) -> Optional[SheetsClient]:
    gs = config.get('google_sheets', {}) or {}
    enabled = bool(gs.get('enabled', False))
    creds_path = gs.get('credentials_json_path') or 'service_account.json'
    spreadsheet_id = gs.get('spreadsheet_id') or ''
    worksheet_name = gs.get('worksheet_name') or 'participants'
    client = SheetsClient(enabled, creds_path, spreadsheet_id, worksheet_name)
    ok = client.connect()
    return client if ok else None
