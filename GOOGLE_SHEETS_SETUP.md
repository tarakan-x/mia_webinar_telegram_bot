# 🔐 Google Sheets Setup for Render Deployment

## 📋 Overview

The `service_account.json` file contains sensitive Google Cloud credentials and is **NOT** included in your GitHub repository (correctly listed in `.gitignore`). 

When deploying to Render, you need to provide this file separately.

---

## ✅ Your Code Now Supports 4 Methods!

The bot will automatically try to load credentials in this order:

1. **Environment Variable** (`GOOGLE_SERVICE_ACCOUNT_JSON`)
2. **Render Secret Files** (`/etc/secrets/service_account.json`)
3. **Persistent Disk** (`/data/service_account.json`)
4. **Local Path** (`service_account.json` - for development)

---

## 🚀 Recommended Methods for Render

### **Method 1: Render Secret Files** ⭐ (Easiest)

This is the recommended approach for Render.

#### Steps:

1. **In Render Dashboard:**
   - Go to your service
   - Click **"Environment"** tab
   - Scroll to **"Secret Files"** section
   - Click **"Add Secret File"**

2. **Configure the secret file:**
   - **Filename**: `service_account.json`
   - **Contents**: Copy and paste your entire `service_account.json` content
   
3. **Save and Deploy**
   - Render automatically places it at `/etc/secrets/service_account.json`
   - Your bot will find it automatically!

**Pros:**
- ✅ Secure (encrypted by Render)
- ✅ Easy to update
- ✅ Automatically available on deploy
- ✅ No code changes needed

---

### **Method 2: Environment Variable** (Alternative)

Good if your service account JSON is small.

#### Steps:

1. **Get your service_account.json as single line:**
   ```bash
   cat service_account.json | jq -c
   ```
   Or manually copy the content and remove line breaks.

2. **In Render Dashboard:**
   - Add environment variable: `GOOGLE_SERVICE_ACCOUNT_JSON`
   - Value: Paste the entire JSON (one line, with quotes escaped)
   
   Example value:
   ```json
   {"type":"service_account","project_id":"your-project","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n","client_email":"...@....iam.gserviceaccount.com","client_id":"...","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_x509_cert_url":"..."}
   ```

3. **Save and Deploy**

**Pros:**
- ✅ Simple to set up
- ✅ Works immediately

**Cons:**
- ⚠️ Environment variable size limits
- ⚠️ Harder to read/update

---

### **Method 3: Upload to Persistent Disk** (Manual)

If you prefer to manage the file directly.

#### Steps:

1. **Deploy your bot first** (without Google Sheets working)

2. **Access Render Shell:**
   - In Render dashboard, go to **"Shell"** tab
   - Wait for shell to connect

3. **Create the file:**
   ```bash
   nano /data/service_account.json
   ```
   
4. **Paste your JSON content** and save (Ctrl+X, Y, Enter)

5. **Verify:**
   ```bash
   cat /data/service_account.json
   ls -la /data/
   ```

6. **Restart your service**

**Pros:**
- ✅ Full control
- ✅ Stored on persistent disk

**Cons:**
- ⚠️ Manual process
- ⚠️ Need to redo if disk is recreated

---

## 🧪 How to Verify It Works

After setting up the credentials:

### 1. Check Logs

Look for one of these messages in Render logs:

```
✅ Loading Google credentials from GOOGLE_SERVICE_ACCOUNT_JSON environment variable
✅ Loading Google credentials from /etc/secrets/service_account.json
✅ Loading Google credentials from /data/service_account.json
✅ Loading Google credentials from service_account.json
```

And then:

```
✅ Connected to Google Sheet 'participants' (1-ipmnZDO8jwNGiRqJlI7do5a_5CpuWCc5ym4ML59YTk)
```

### 2. Test in Telegram

Send to your bot:
```
/syncsheet
```

You should see:
```
✅ Google Sheets sync completed
```

### 3. Check Your Spreadsheet

Open your Google Sheet and verify participant data appears!

---

## 🔧 Troubleshooting

### Error: "Google service account credentials not found"

**Solution:**
- Verify you added the secret file or env var correctly
- Check the filename is exactly `service_account.json`
- Ensure the JSON is valid (use jsonlint.com)

### Error: "403 Permission denied"

**Solution:**
- Share your Google Sheet with the service account email
- Find the email in your `service_account.json`: `"client_email": "...@....iam.gserviceaccount.com"`
- In Google Sheets, click "Share" and add that email as "Editor"

### Error: "404 Not found"

**Solution:**
- Check `GOOGLE_SHEETS_SPREADSHEET_ID` is correct
- You can use either the ID or full URL
- Verify the spreadsheet exists and isn't deleted

### Error: "API not enabled"

**Solution:**
- In Google Cloud Console, enable:
  - Google Sheets API
  - Google Drive API
- Wait a few minutes for APIs to activate

---

## 📝 Quick Setup Checklist

For Render deployment with Google Sheets:

- [ ] `service_account.json` is in `.gitignore` ✅
- [ ] Choose a method (Secret Files recommended)
- [ ] Add credentials to Render
- [ ] Set `GOOGLE_SHEETS_ENABLED=true`
- [ ] Set `GOOGLE_SHEETS_SPREADSHEET_ID`
- [ ] Share Sheet with service account email
- [ ] Deploy and check logs
- [ ] Test `/syncsheet` command
- [ ] Verify data appears in Sheet

---

## 🎯 Recommended Configuration

**Environment Variables to set:**

```bash
GOOGLE_SHEETS_ENABLED=true
GOOGLE_SHEETS_SPREADSHEET_ID=1-ipmnZDO8jwNGiRqJlI7do5a_5CpuWCc5ym4ML59YTk
GOOGLE_SHEETS_WORKSHEET_NAME=participants
```

**Secret File to add:**
- Filename: `service_account.json`
- Content: Your full service account JSON

**Share your Google Sheet with:**
- The email from `"client_email"` in your service_account.json
- Permission level: Editor

---

## 🔒 Security Best Practices

✅ **DO:**
- Keep `service_account.json` in `.gitignore`
- Use Render Secret Files
- Rotate credentials periodically
- Grant minimum required permissions

❌ **DON'T:**
- Commit `service_account.json` to Git
- Share credentials in chat/email
- Use production credentials for testing
- Give "Owner" permissions (Editor is enough)

---

## 💡 Local Development

For local development, just keep your `service_account.json` in the project root:

```
mia_webinar_telegram_bot/
├── service_account.json  ← Here (gitignored)
├── config.json
├── main.py
└── ...
```

The bot will find it automatically!

---

**Your Google Sheets integration is now ready for production!** 🎉
