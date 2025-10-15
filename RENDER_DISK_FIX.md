# 🔧 FIX: Render.com Disk Configuration Error

## ❌ The Problem

When trying to add a disk with mount path `/opt/render/project/src`, you get:
```
⚠️ Path cannot be a reserved path
```

## ✅ The Solution

Use `/data` as the mount path instead!

---

## 📝 Corrected Disk Configuration for Render

### In Render Dashboard:

1. Go to your service settings
2. Scroll to **"Advanced"** section
3. Find **"Disk"** section
4. Click **"Add Disk"**
5. Fill in:

| Field | Value |
|-------|-------|
| **Name** | `bot-data` |
| **Mount Path** | `/data` ⚠️ **Use this, NOT /opt/render/project/src** |
| **Size** | `1 GB` |

6. Click **Save**

---

## ✅ Code Already Updated!

The code has been updated to automatically use the `/data` directory when available. It will:

- ✅ Store `config.json` in `/data/config.json`
- ✅ Store `database.json` in `/data/database.json`
- ✅ Store `bot.log` in `/data/bot.log`
- ✅ Fall back to current directory when running locally

---

## 🧪 How to Verify It Works

After deploying to Render:

1. Check the logs for:
   ```
   INFO - Using data directory: /data
   INFO - Created /data/config.json from environment variables
   INFO - Created /data/database.json
   ```

2. Use Render Shell to verify:
   ```bash
   ls -la /data/
   ```
   
   You should see:
   ```
   -rw-r--r-- 1 render render config.json
   -rw-r--r-- 1 render render database.json
   -rw-r--r-- 1 render render bot.log
   ```

3. Test persistence:
   - Change a setting via Telegram: `/setwebinar Wednesday 18:00`
   - Restart the service
   - Check if the setting persisted: `/viewschedule`

---

## 📋 Alternative Mount Paths (if /data doesn't work)

If `/data` is also reserved, try these alternatives:

- `/persist`
- `/storage`
- `/app-data`
- `/bot-storage`

Then update the code in `main.py` and `handlers.py`:
```python
DATA_DIR = '/persist'  # Change to your chosen path
```

---

## 🔄 Already Deployed? How to Update

If you already deployed without the disk:

1. **In Render Dashboard:**
   - Go to your service
   - Click "Environment" tab
   - Scroll to "Disk" section
   - Add disk with mount path `/data`
   - Save

2. **Manual Deploy:**
   - Click "Manual Deploy" button
   - Select "Clear build cache & deploy"
   - Wait for new deployment

3. **Verify:**
   - Check logs show `/data` directory in use
   - Test bot still responds
   - Make a config change and verify it persists

---

## 💾 Why This Matters

Without persistent disk:
- ❌ User registrations lost on restart
- ❌ Config changes reset on restart
- ❌ Bot forgets everything each deploy

With persistent disk:
- ✅ Data survives restarts
- ✅ Config changes permanent
- ✅ Production-ready setup

---

**Your bot is now configured correctly!** 🎉
