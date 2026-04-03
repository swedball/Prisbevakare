# Prisbevakare

A simple price monitoring tool that checks prices on web pages and sends daily email alerts.

## Features

- Monitor multiple URLs for price changes
- Store price history in JSONL format
- Send daily email reports
- Web UI for managing monitored URLs

## Setup

1. Install dependencies: `pip install requests`

2. **Configure SMTP** for email notifications (see [Email Setup](#email-setup) below)

3. Create `urls.json` with your configurations:
   ```json
   [
     {
       "url": "https://example.com/product",
       "email": "user@example.com",
       "history_path": "history/example.jsonl"
     }
   ]
   ```

## Email Setup

The script sends reports via email. You need to configure an SMTP server using environment variables.

### Option 1: Gmail (Recommended for Testing)

1. **Create a Gmail App Password:**
   - Go to: https://myaccount.google.com/apppasswords
   - Select "Mail" and "Windows Computer"
   - Copy the 16-character password

2. **Run the script with these environment variables:**
   ```bash
   export SMTP_SERVER="smtp.gmail.com"
   export SMTP_PORT="587"
   export SMTP_USERNAME="your-email@gmail.com"
   export SMTP_PASSWORD="your-16-char-app-password"
   export SMTP_USE_TLS="true"
   export SMTP_FROM="your-email@gmail.com"
   
   python price_checker.py send-report urls.json
   ```

### Option 2: Other Email Providers

Update the environment variables accordingly:

| Provider | Server | Port | TLS |
|----------|--------|------|-----|
| Gmail | smtp.gmail.com | 587 | true |
| Outlook | smtp.office365.com | 587 | true |
| SendGrid | smtp.sendgrid.net | 587 | true |
| Your Server | your-server.com | 25 or 587 | true/false |

### Environment Variables Reference

- `SMTP_SERVER` - SMTP server address (required)
- `SMTP_PORT` - SMTP port (default: 25)
- `SMTP_USERNAME` - Login username (optional if no auth)
- `SMTP_PASSWORD` - Login password (optional if no auth)
- `SMTP_USE_TLS` - Use TLS encryption: true/false (default: false)
- `SMTP_FROM` - Sender email address (default: price-checker@example.com)

## Usage

- Check price for a single URL: `python price_checker.py <url>`
- Start monitoring: `python price_checker.py monitor urls.json`
- Send immediate report: `python price_checker.py send-report urls.json`

### Scheduling Reports with Cron

To send reports automatically every day at 9 AM:

1. Set up your SMTP environment variables in a `.env` file or export them
2. Add to crontab (`crontab -e`):
   ```bash
   0 9 * * * cd /path/to/Prisbevakare && export SMTP_SERVER="smtp.gmail.com" && export SMTP_PORT="587" && export SMTP_USERNAME="your-email@gmail.com" && export SMTP_PASSWORD="your-app-password" && export SMTP_USE_TLS="true" && export SMTP_FROM="your-email@gmail.com" && python price_checker.py send-report urls.json
   ```

Or use a shell script wrapper for cleaner cron entries:
   ```bash
   #!/bin/bash
   export SMTP_SERVER="smtp.gmail.com"
   export SMTP_PORT="587"
   export SMTP_USERNAME="your-email@gmail.com"
   export SMTP_PASSWORD="your-app-password"
   export SMTP_USE_TLS="true"
   export SMTP_FROM="your-email@gmail.com"
   cd /path/to/Prisbevakare
   python price_checker.py send-report urls.json
   ```
   Then add to crontab: `0 9 * * * /path/to/script.sh`

## Web UI

The web UI allows you to manage URLs via a browser.

1. Enable GitHub Pages in your repo settings (source: main branch).
2. Access the UI at `https://<username>.github.io/<repo>/`
3. Enter your GitHub personal access token (with repo permissions) to load/save configurations.

Note: The "Send Report Now" button shows the command to run locally, as static sites cannot send emails directly.