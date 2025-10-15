# Webinar Telegram Bot

Telegram bot for managing webinar registrations and reminders. Includes admin tools, flexible scheduling, and optional Google Sheets sync.

## Features

- Register participants with `/start` and store them in `database.json`
- Info and welcome messages with dynamic placeholders (next webinar day/time)
- Automated reminders via APScheduler:
	- Day reminder at a configured day/time (e.g., Tuesday 09:00)
	- 15-minute reminder automatically before the webinar time
- Admin controls:
	- Add/Remove/List admins
	- Set webinar day/time/timezone/link
	- Configure reminder day/time
	- View schedule and next run times
	- Broadcast messages to all participants
	- Export participants to CSV
	- Optional: Sync participants to Google Sheets

## Project structure

```
main.py                # Entrypoint
handlers.py            # Bot command handlers and menus
scheduler.py           # APScheduler jobs and schedule preview
utils.py               # Date/time utils (next webinar calculation)
keyboard_menu.py       # Keyboard button mapper
config.json            # Bot configuration
database.json          # Participants store
requirements.txt       # Dependencies
botfather_commands.txt # Suggested command list for BotFather
sheets.py              # (Optional) Google Sheets integration
```

## Requirements

- Python 3.11+ (3.13 tested)
- A Telegram bot token (via @BotFather)

## Setup

1) Clone and create a virtual environment

```zsh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Configure your token and settings

- Option A: Create a `.env` file with `TELEGRAM_BOT_TOKEN=...`
- Option B: Put the token into `config.json` under `token` (not recommended for commits)

Edit `config.json` to set:
- `admin_ids`: array of Telegram user IDs allowed admin actions
- `webinar`: day, time, timezone (IANA, e.g., Europe/Bucharest)
- `messages`: welcome/info/reminder templates
- `reminders.day`: day + time for the day-of reminder

3) Run the bot

```zsh
"$(pwd)/.venv/bin/python" main.py
```

Keep it running to allow scheduled reminders to fire.

## Commands

User commands:
- `/start` — Register and receive a welcome message
- `/info` — See details about the next webinar
- `/menu` — Open the inline menu
- `/help` — Show this help

Admin commands:
- `/exportcsv` — Export participants to CSV
- `/syncsheet` — Sync all participants to Google Sheets (optional)
- `/setmessage [welcome|info|reminder_day|reminder_15min]` — Update bot texts
- `/sendreminder [day|15min]` — Manually send reminders
- `/broadcast` — Send a message to all participants (with confirmation)
- `/addadmin <id>` — Add an admin
- `/deladmin <id>` — Remove an admin
- `/listadmins` — List admin IDs
- `/setreminder day <Day> <HH:MM>` — Configure the day reminder
- `/viewschedule` — Show current schedule and next run times
- `/setwebinar <Day> <HH:MM>` or subcommands `day|time|timezone|link`

Inline menus give quick access to these actions. Admins see additional options.

## Scheduling details

- Timezone is taken from `config.webinar.timezone`
- Reminder “day”: configurable via `/setreminder day <Day> <HH:MM>`
- Reminder “pre15”: always scheduled at webinar time minus 15 minutes
- Use `/viewschedule` to preview the next execution times and how long remains

## Google Sheets (optional)

1) Enable APIs in Google Cloud:
	 - Google Sheets API
	 - Google Drive API
2) Create a Service Account and download the JSON key
3) Share your spreadsheet with the service account email (Editor)
4) Configure `config.json`:

```
"google_sheets": {
	"enabled": true,
	"credentials_json_path": "service_account.json",
	"spreadsheet_id": "<ID or full URL>",
	"worksheet_name": "participants"
}
```

Notes:
- You can paste a full spreadsheet URL; the bot extracts the ID automatically.
- On `/start`, the user is upserted to the sheet; admins can run `/syncsheet` for a full refresh.

## Troubleshooting

- Bot doesn’t start: ensure `TELEGRAM_BOT_TOKEN` is set or `config.json` has a valid `token`.
- Scheduled reminders didn’t fire: the process must be running at the scheduled times and timezone must be correct.
- Google Sheets 403: share the sheet with the service account and enable APIs.
- Google Sheets 404: check the spreadsheet ID/URL; ensure it wasn’t moved or deleted.
- Range exceeds grid: fixed; the bot resizes the worksheet before bulk updates.
- Missing packages: activate venv and `pip install -r requirements.txt`.

## License

Private project. All rights reserved.

## Deploy to Render

1) Push to GitHub

- Initialize git and commit this project (ensure `.gitignore` excludes secrets and local files):

```zsh
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<your-user>/<your-repo>.git
git push -u origin main
```

2) Create a Render Worker service

- Dashboard → New → Background Worker
- Connect your GitHub repo
- Environment: Python
- Build Command: `pip install -r requirements.txt`
- Start Command: `python main.py`
- Add Environment Variable:
	- `TELEGRAM_BOT_TOKEN`: your token (Secret)
- Create service

3) (Optional) Google Sheets on Render

- Upload your `service_account.json` as a Render Secret File and mount it.
- Update `config.json` to point `google_sheets.credentials_json_path` to the mounted path (e.g., `/opt/render/project/src/service_account.json`).
- Set `google_sheets.enabled: true` and fill `spreadsheet_id`.

4) Deploy & Logs

- Render will build and start the worker automatically on push.
- Use the Logs tab to watch the bot startup and scheduler logs.

