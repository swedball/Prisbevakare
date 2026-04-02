# Prisbevakare

A simple price monitoring tool that checks prices on web pages and sends daily email alerts.

## Features

- Monitor multiple URLs for price changes
- Store price history in JSONL format
- Send daily email reports
- Web UI for managing monitored URLs

## Setup

1. Install dependencies: `pip install requests`

2. Configure SMTP environment variables:
   - `SMTP_SERVER`
   - `SMTP_PORT` (default 25)
   - `SMTP_USERNAME`
   - `SMTP_PASSWORD`
   - `SMTP_USE_TLS` (true/false)
   - `SMTP_FROM` (sender email)

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

## Usage

- Check price for a single URL: `python price_checker.py <url>`
- Start monitoring: `python price_checker.py monitor urls.json`
- Send immediate report: `python price_checker.py send-report urls.json`

## Web UI

The web UI allows you to manage URLs via a browser.

1. Enable GitHub Pages in your repo settings (source: main branch).
2. Access the UI at `https://<username>.github.io/<repo>/`
3. Enter your GitHub personal access token (with repo permissions) to load/save configurations.

Note: The "Send Report Now" button shows the command to run locally, as static sites cannot send emails directly.