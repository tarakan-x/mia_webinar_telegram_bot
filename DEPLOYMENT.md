# Deployment Guide for Render.com

## 🔄 How Configuration Works

### Initial Setup (First Deployment)
1. **Environment variables** are read from Render dashboard
2. Bot creates `config.json` from these variables on first run
3. Bot saves `config.json` to **persistent disk**

### Runtime Changes (Using Telegram Commands)
When you change settings via Telegram commands like:
- `/setwebinar Tuesday 16:00`
- `/setreminder Tuesday 10:00`
- `/setmessage welcome`

**What happens:**
- ✅ Changes are saved to `config.json`
- ✅ Changes persist across restarts (thanks to Render disk)
- ✅ Bot reads from `config.json` on restart
- ⚠️ Environment variables are ONLY used if `config.json` doesn't exist

### Priority Order
```
1. config.json (if exists) ← Telegram command changes saved here
2. Environment variables (if no config.json) ← Initial deployment only
```

---

## 📦 Render.com Deployment Steps

### Step 1: Create Persistent Disk (IMPORTANT!)

In Render dashboard, when creating/editing your service:

1. Scroll to **"Disks"** section
2. Click **"Add Disk"**
3. Configure:
   - **Name**: `bot-data`
   - **Mount Path**: `/opt/render/project/src`
   - **Size**: `1 GB` (free tier)
4. Save

**Without this disk, all changes via Telegram will be lost on restart!**

---

### Step 2: Set Environment Variables

These are ONLY used for initial setup. Add in Render dashboard:

#### Required Variables:

| Variable | Example Value | Description |
|----------|---------------|-------------|
| `TELEGRAM_BOT_TOKEN` | `123456:ABC-DEF...` | Get from @BotFather |
| `ADMIN_IDS` | `592460481,1016953420` | Comma-separated user IDs |
| `WEBINAR_DAY` | `Tuesday` | Day of webinar |
| `WEBINAR_TIME` | `15:00` | Time in HH:MM format |
| `WEBINAR_TIMEZONE` | `Europe/Bucharest` | Timezone |
| `REMINDER_DAY_DAY` | `Tuesday` | Day for reminder |
| `REMINDER_DAY_TIME` | `09:00` | Time for reminder |

#### Optional Variables (Google Sheets):

| Variable | Example Value |
|----------|---------------|
| `GOOGLE_SHEETS_ENABLED` | `true` or `false` |
| `GOOGLE_SHEETS_SPREADSHEET_ID` | Your spreadsheet ID |
| `GOOGLE_SHEETS_WORKSHEET_NAME` | `participants` |

---

### Step 3: Deploy

1. Connect GitHub repository
2. Set build command: `pip install -r requirements.txt`
3. Set start command: `python main.py`
4. Click **Deploy**

---

## 🔧 Making Changes After Deployment

### Option A: Via Telegram (Recommended)
Use bot commands to change settings. Changes persist!

```
/setwebinar Wednesday 18:00
/setreminder Monday 08:00
/setmessage welcome Your new welcome message
```

### Option B: Via Environment Variables
1. Update variables in Render dashboard
2. **Delete config.json** from the disk (via Render shell)
3. Restart the service
4. Bot will recreate config.json from new env vars

---

## 🐛 Troubleshooting

### Changes Lost After Restart?
❌ **Problem**: Persistent disk not configured
✅ **Solution**: Add persistent disk as described in Step 1

### Bot Not Reading My Changes?
❌ **Problem**: `config.json` exists and overrides env vars
✅ **Solution**: Either:
- Use Telegram commands to update
- Or delete `config.json` and restart

### How to Reset to Defaults?
1. Go to Render Shell
2. Run: `rm config.json database.json`
3. Restart service
4. Bot recreates from environment variables

---

## 📊 File Persistence

| File | Persists? | Purpose |
|------|-----------|---------|
| `config.json` | ✅ Yes (with disk) | Bot configuration |
| `database.json` | ✅ Yes (with disk) | Participant data |
| `bot.log` | ✅ Yes (with disk) | Logs |
| Code files | ❌ No (read-only) | From Git repo |

---

## 💡 Best Practices

1. **Set initial values via environment variables** (one-time setup)
2. **Change values via Telegram commands** (daily operation)
3. **Enable persistent disk** (crucial for data retention)
4. **Use Google Sheets** for extra backup of participant data
5. **Monitor logs** in Render dashboard for issues

---

## 🚀 Quick Start Checklist

- [ ] Persistent disk configured (1 GB)
- [ ] All environment variables set
- [ ] Bot deployed successfully
- [ ] Test with `/start` command
- [ ] Change settings via `/setwebinar`
- [ ] Verify changes persist after manual restart

---

## 📞 Support Commands

```bash
# View current settings
/viewschedule

# Test reminder
/sendreminder test

# Check admin list
/listadmins
```
