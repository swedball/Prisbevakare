import json
import os
import re
import smtplib
import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from email.message import EmailMessage
from typing import Optional

try:
    import requests
except ImportError:
    requests = None


def _normalize_price_text(raw_text: str) -> Decimal:
    """Normalize price text to Decimal, e.g. '1 234,56' -> Decimal('1234.56')."""
    txt = raw_text.strip()
    txt = txt.replace("\u00A0", " ").replace(" ", "")
    txt = txt.replace("$", "").replace("€", "").replace("kr", "").replace("SEK", "")
    txt = txt.replace("EUR", "").replace("USD", "")

    if "," in txt and "." in txt:
        # be cautious: 1.234,56 -> svensk format
        if txt.rfind(",") > txt.rfind("."):
            txt = txt.replace(".", "").replace(",", ".")
        else:
            txt = txt.replace(",", "")
    elif "," in txt:
        txt = txt.replace(",", ".")

    try:
        return Decimal(txt)
    except Exception as exc:
        raise ValueError(f"Could not parse price '{raw_text}': {exc}") from exc


def get_price_from_url(url: str) -> Decimal:
    """Fetch the webpage and extract the first price in SEK/EUR/USD direction."""
    if requests is None:
        raise RuntimeError("The requests package is missing. Install it with 'pip install requests'.")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }

    response = requests.get(url, timeout=12, headers=headers)
    response.raise_for_status()
    content = response.text

    # Matches common formats: 1 234 kr, 1234,56 SEK, €1,234.00, $12.99
    pattern = re.compile(
        r"(?P<price>(?:\d{1,3}(?:[ \u00A0\.,]\d{3})*|\d+)(?:[\.,]\d{1,2})?)\s*(?:kr|sek|eur|usd|€|\$)",
        re.IGNORECASE,
    )

    match = pattern.search(content)
    if not match:
        raise ValueError(f"Ingen prisinformation hittades på sidan: {url}")

    price_str = match.group("price")
    return _normalize_price_text(price_str)


def get_price_from_url_text(content: str) -> Optional[Decimal]:
    """Helper for tests: extract the first matched price from HTML/text."""
    pattern = re.compile(
        r"(?P<price>(?:\d{1,3}(?:[ \u00A0\.,]\d{3})*|\d+)(?:[\.,]\d{1,2})?)\s*(?:kr|sek|eur|usd|€|\$)",
        re.IGNORECASE,
    )

    match = pattern.search(content)
    if not match:
        return None

    return _normalize_price_text(match.group("price"))


def load_urls_config(config_path: str) -> list[dict]:
    """Load list of URL configs from JSON file."""
    if not os.path.exists(config_path):
        return []
    
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_urls_config(config_path: str, configs: list[dict]) -> None:
    """Save list of URL configs to JSON file."""
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(configs, f, indent=2, ensure_ascii=False)


def _load_price_history(history_path: str) -> list[dict]:
    """Load price history from JSONL file."""
    if not os.path.exists(history_path):
        return []

    with open(history_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    history = []
    for line in lines:
        try:
            history.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return history


def _save_price_entry(history_path: str, entry: dict) -> None:
    """Append a price entry to the JSONL history file."""
    directory = os.path.dirname(history_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(history_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def send_price_alert(email_to: str, price: Decimal, change_status: str, old_price: Optional[Decimal] = None) -> None:
    """Send email alert for price status."""
    smtp_server = os.getenv("SMTP_SERVER", "localhost")
    smtp_port = int(os.getenv("SMTP_PORT", "25"))
    smtp_user = os.getenv("SMTP_USERNAME")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    use_tls = os.getenv("SMTP_USE_TLS", "false").lower() in ("1", "true", "yes")

    message = EmailMessage()
    subject = "Price status update"
    if change_status == "unchanged":
        subject = f"Price is still the same: {price}"
        body = f"Price is still the same: {price}."
    elif change_status == "no_history":
        subject = "No price history yet"
        body = "No price history available yet."
    elif change_status == "immediate_report":
        subject = f"Current price: {price}"
        body = f"Current price: {price}."
    else:
        subject = f"Price changed to {price}"
        body = f"Price changed to {price}."
        if old_price is not None:
            body += f" Previous price was {old_price}."

    message["Subject"] = subject
    message["From"] = os.getenv("SMTP_FROM", "price-checker@example.com")
    message["To"] = email_to
    message.set_content(body)

    if not smtp_server:
        print("SMTP_SERVER is not configured; skipping email notification.")
        return

    try:
        smtp = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
        if use_tls:
            smtp.starttls()

        with smtp:
            if smtp_user and smtp_pass:
                smtp.login(smtp_user, smtp_pass)
            smtp.send_message(message)
    except Exception as exc:
        print(f"Warning: Failed to send email alert ({exc}). Continuing without email.")


def check_price_daily(config: dict) -> None:
    """Check price for a single URL configuration."""
    url = config["url"]
    history_path = config["history_path"]
    email_to = config["email"]
    today = date.today().isoformat()
    price = get_price_from_url(url)

    history = _load_price_history(history_path)
    last_entry = history[-1] if history else None

    if last_entry and last_entry.get("date") == today:
        # Already logged today; send status email anyway
        current_price = Decimal(str(last_entry.get("price")))
        send_price_alert(email_to, current_price, "unchanged" if current_price == price else "changed", current_price)
        return

    if last_entry:
        previous_price = Decimal(str(last_entry.get("price")))
        if price == previous_price:
            send_price_alert(email_to, price, "unchanged", previous_price)
        else:
            send_price_alert(email_to, price, "changed", previous_price)
    else:
        send_price_alert(email_to, price, "changed", None)

    entry = {"date": today, "price": str(price), "url": url}
    _save_price_entry(history_path, entry)


def send_immediate_report(configs: list[dict]) -> None:
    """Send immediate status report for all URLs."""
    for config in configs:
        url = config["url"]
        history_path = config["history_path"]
        email_to = config["email"]
        try:
            history = _load_price_history(history_path)
            if not history:
                send_price_alert(email_to, Decimal("0"), "no_history", None)
                continue
            last_entry = history[-1]
            price = Decimal(str(last_entry.get("price")))
            send_price_alert(email_to, price, "immediate_report", None)
        except Exception as exc:
            print(f"Failed to send report for {url}: {exc}")


def run_daemon(configs: list[dict]) -> None:
    """Continuously monitor prices and send daily reports."""
    while True:
        for config in configs:
            try:
                check_price_daily(config)
            except Exception as exc:
                print(f"Daily check failed for {config['url']}: {exc}")

        now = datetime.now()
        next_run = (now + timedelta(days=1)).replace(hour=0, minute=1, second=0, microsecond=0)
        wait_seconds = (next_run - now).total_seconds()
        if wait_seconds <= 0:
            wait_seconds = 24 * 60 * 60

        print(f"Next check in {wait_seconds/3600:.1f} hours")
        time.sleep(wait_seconds)


if __name__ == "__main__":
    import sys

    def print_usage() -> None:
        print("Usage:")
        print("  python price_checker.py <url>")
        print("  python price_checker.py monitor <config_file>")
        print("  python price_checker.py send-report <config_file>")
        print("Example:")
        print("  python price_checker.py monitor urls.json")
        print("  python price_checker.py send-report urls.json")
        sys.exit(1)

    if len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help"):
        print_usage()

    if len(sys.argv) == 2:
        url = sys.argv[1]
        try:
            price = get_price_from_url(url)
            print(f"Price: {price} (Decimal)")
        except Exception as exc:
            print(f"Error while fetching price: {exc}")
            sys.exit(2)
    elif len(sys.argv) == 3 and sys.argv[1] == "monitor":
        _, command, config_file = sys.argv
        try:
            configs = load_urls_config(config_file)
            if not configs:
                print(f"No configurations found in {config_file}")
                sys.exit(1)
            print(f"Starting monitor for {len(configs)} URLs")
            run_daemon(configs)
        except KeyboardInterrupt:
            print("Stopped by user")
            sys.exit(0)
        except Exception as exc:
            print(f"Monitor failed: {exc}")
            sys.exit(3)
    elif len(sys.argv) == 3 and sys.argv[1] == "send-report":
        _, command, config_file = sys.argv
        try:
            configs = load_urls_config(config_file)
            if not configs:
                print(f"No configurations found in {config_file}")
                sys.exit(1)
            send_immediate_report(configs)
            print("Immediate reports sent.")
        except Exception as exc:
            print(f"Send report failed: {exc}")
            sys.exit(3)
    else:
        print_usage()
