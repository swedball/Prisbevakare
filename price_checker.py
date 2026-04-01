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


def _load_price_history(history_path: str) -> list[dict]:
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
    directory = os.path.dirname(history_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(history_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def send_price_alert(email_to: str, price: Decimal, change_status: str, old_price: Optional[Decimal] = None) -> None:
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
    else:
        subject = f"Price changed to {price}"
        body = f"Price changed to {price}."
        if old_price is not None:
            body += f" Previous price was {old_price}."

    message["Subject"] = subject
    message["From"] = os.getenv("SMTP_FROM", "price-checker@example.com")
    message["To"] = email_to
    message.set_content(body)

    if use_tls:
        smtp = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
        smtp.starttls()
    else:
        smtp = smtplib.SMTP(smtp_server, smtp_port, timeout=30)

    with smtp:
        if smtp_user and smtp_pass:
            smtp.login(smtp_user, smtp_pass)
        smtp.send_message(message)


def check_price_daily(url: str, history_path: str, email_to: str) -> None:
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


def run_daemon(url: str, history_path: str, email_to: str) -> None:
    while True:
        try:
            check_price_daily(url, history_path, email_to)
        except Exception as exc:
            print(f"Daily check failed: {exc}")

        now = datetime.now()
        next_run = (now + timedelta(days=1)).replace(hour=0, minute=1, second=0, microsecond=0)
        wait_seconds = (next_run - now).total_seconds()
        if wait_seconds <= 0:
            wait_seconds = 24 * 60 * 60

        time.sleep(wait_seconds)


if __name__ == "__main__":
    import sys

    def print_usage() -> None:
        print("Usage:")
        print("  python price_checker.py <url>")
        print("  python price_checker.py monitor <url> <history_file> <email_to>")
        print("Example:")
        print("  python price_checker.py monitor https://... /tmp/price_history.jsonl henrikadolfsson@gmail.com")
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
    elif len(sys.argv) == 5 and sys.argv[1] == "monitor":
        _, _, url, history_file, email_to = sys.argv
        try:
            print(f"Starting monitor for {url}, history {history_file}, alert {email_to}")
            run_daemon(url, history_file, email_to)
        except KeyboardInterrupt:
            print("Stopped by user")
            sys.exit(0)
        except Exception as exc:
            print(f"Monitor failed: {exc}")
            sys.exit(3)
    elif len(sys.argv) == 5 and sys.argv[1] == "check":
        _, _, url, history_file, email_to = sys.argv
        try:
            check_price_daily(url, history_file, email_to)
            print("Checked price for today and stored history.")
        except Exception as exc:
            print(f"Check failed: {exc}")
            sys.exit(3)
    else:
        print_usage()
