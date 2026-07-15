"""
M2R Newsletter Sender
=====================
Sends the monthly M2 Reporter newsletter via Resend API.

Send list:
  - All active accounts (is_retired=0) that have not explicitly unsubscribed
  - Accounts retired/lapsed within the last 12 months (based on paid_through_date)
  Accounts with no email address across all three email fields are skipped.

Email fields: email_ap, email_user, and email_it are all combined and
deduplicated per account.  A separate email is sent to each unique address.
Fields that are blank or null are silently skipped.

Usage:
    python send_newsletter.py newsletter-2026-07.html
    python send_newsletter.py newsletter-2026-07.html --dry-run
    python send_newsletter.py newsletter-2026-07.html --limit 5

Requirements:
    pip install requests
    Set RESEND_API_KEY environment variable before running.
"""

import argparse
import csv
import os
import re
import sqlite3
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests")
    sys.exit(1)

from m2r_crm_paths import APP_DIR


# ---------------------------------------------------------------------------
# Configuration — edit these before first use
# ---------------------------------------------------------------------------
FROM_EMAIL = "newsletter@m2reporter.com"   # Must be a verified Resend sender address
FROM_NAME  = "M2 Reporter"

# Set to a URL prefix (e.g. "https://m2reporter.com/unsubscribe?email=") when
# an unsubscribe page exists.  Leave blank to fall back to a mailto: link.
UNSUBSCRIBE_BASE_URL = ""

DB_PATH    = os.path.join(str(APP_DIR), "m2r_crm.db")
RESEND_URL = "https://api.resend.com/emails"

# Matches standard email addresses; used to extract addresses from multi-email fields.
_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
# ---------------------------------------------------------------------------


def get_send_list(db_path: str, audience: str = "all") -> List[Dict]:
    """
    Query accounts that have at least one email address.

    audience:
      "all"     — active + recently retired (default, monthly newsletter)
      "active"  — active accounts only (is_retired=0, not Unsubscribed)
      "retired" — recently retired only (paid_through_date within 12 months)

    Returns a list of dicts with a synthetic 'send_status' key:
      'active' or 'recently_retired'
    """
    _email_filter = """
          AND (
              (email_ap IS NOT NULL AND email_ap != '')
              OR (email IS NOT NULL AND email != '')
              OR (email_user IS NOT NULL AND email_user != '')
              OR (email_it IS NOT NULL AND email_it != '')
          )
    """
    active_sql = f"""
        SELECT
            account_number, company_name, contact_name,
            email_ap, email, email_user, email_it,
            paid_through_date, subscription_status,
            'active' AS send_status
        FROM customers
        WHERE is_retired = 0
          AND subscription_status != 'Unsubscribed'
          {_email_filter}
    """
    retired_sql = f"""
        SELECT
            account_number, company_name, contact_name,
            email_ap, email, email_user, email_it,
            paid_through_date, subscription_status,
            'recently_retired' AS send_status
        FROM customers
        WHERE is_retired = 1
          AND paid_through_date IS NOT NULL
          AND paid_through_date >= date('now', '-12 months')
          {_email_filter}
    """
    if audience == "active":
        sql = active_sql + " ORDER BY company_name"
    elif audience == "retired":
        sql = retired_sql + " ORDER BY company_name"
    else:
        sql = active_sql + " UNION ALL " + retired_sql + " ORDER BY company_name"

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(sql)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def extract_emails(field_value: str) -> List[str]:
    """Extract all valid email addresses from a space-separated (or single) email field."""
    if not field_value:
        return []
    return _EMAIL_RE.findall(field_value)


def get_primary_email_field(record: Dict) -> str:
    """Return the email_ap value, falling back to the legacy email field."""
    return (record.get("email_ap") or record.get("email") or "").strip()


def get_all_emails(record: Dict) -> List[str]:
    """
    Extract, combine, and deduplicate all valid email addresses from all three
    email fields (plus the legacy email column).  Blank/null fields are skipped.
    Deduplication is case-insensitive; first-seen casing is preserved.
    """
    seen, seen_lower = [], set()
    for field in ("email_ap", "email", "email_user", "email_it"):
        for addr in extract_emails(record.get(field) or ""):
            if addr.lower() not in seen_lower:
                seen_lower.add(addr.lower())
                seen.append(addr)
    return seen


def get_first_name(contact_name: Optional[str], company_name: Optional[str]) -> str:
    """Return first word of contact_name, falling back to company_name, then 'Friend'."""
    if contact_name and contact_name.strip():
        return contact_name.strip().split()[0]
    if company_name and company_name.strip():
        return company_name.strip()
    return "Friend"


def build_unsubscribe_link(email: str) -> str:
    """Build an unsubscribe URL (or mailto: fallback) for the given address."""
    encoded = urllib.parse.quote(email)
    if UNSUBSCRIBE_BASE_URL:
        return UNSUBSCRIBE_BASE_URL + encoded
    subject = urllib.parse.quote("Unsubscribe from M2 Reporter Newsletter")
    body    = urllib.parse.quote(
        f"Please remove {email} from the M2 Reporter newsletter list."
    )
    return f"mailto:{FROM_EMAIL}?subject={subject}&body={body}"


def merge_template(html: str, first_name: str, unsubscribe_link: str,
                   company_name: str = "") -> str:
    """Replace merge placeholders: {{first_name}}, {{company_name}}, {{unsubscribe_link}}."""
    html = html.replace("{{first_name}}", first_name)
    html = html.replace("{{company_name}}", company_name)
    html = html.replace("{{unsubscribe_link}}", unsubscribe_link)
    return html


def get_subject_from_html(html: str, fallback: str = "M2 Reporter Newsletter") -> str:
    """Extract the <title> tag content to use as the email subject line."""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if m:
        subject = m.group(1).strip()
        if subject:
            return subject
    return fallback


def send_email(
    to_email: str, subject: str, html_body: str, api_key: str
) -> Tuple[bool, str]:
    """
    Send a single email via Resend API.

    Returns (success, error_detail).  error_detail is empty on success.
    """
    payload = {
        "from":    f"{FROM_NAME} <{FROM_EMAIL}>",
        "to":      [to_email],
        "subject": subject,
        "html":    html_body,
    }
    try:
        resp = requests.post(
            RESEND_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type":  "application/json",
            },
            json=payload,
            timeout=30,
        )
        if resp.status_code in (200, 201):
            return True, ""
        return False, f"HTTP {resp.status_code}: {resp.text[:300]}"
    except requests.RequestException as exc:
        return False, str(exc)


def open_log_file(newsletter_path: str) -> Tuple[object, csv.writer, str]:
    """
    Create a timestamped CSV log file for this send run.

    Returns (file_handle, csv_writer, log_path).
    """
    stem        = Path(newsletter_path).stem
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_name    = f"newsletter_log_{stem}_{timestamp}.csv"
    reports_dir = os.path.join(str(APP_DIR), "Reports")
    os.makedirs(reports_dir, exist_ok=True)
    log_path    = os.path.join(reports_dir, log_name)

    f = open(log_path, "w", newline="", encoding="utf-8")
    writer = csv.writer(f)
    writer.writerow([
        "timestamp", "account_number", "company_name",
        "email", "send_status", "result", "error",
    ])
    return f, writer, log_path


def log_row(
    writer: csv.writer,
    record: Dict,
    email: str,
    result: str,
    error: str = "",
) -> None:
    """Write one send-attempt row to the CSV log."""
    writer.writerow([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        record.get("account_number", ""),
        record.get("company_name", ""),
        email,
        record.get("send_status", ""),
        result,
        error,
    ])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send M2R Reporter newsletter via Resend API"
    )
    parser.add_argument(
        "newsletter_html",
        help="Path to the finished newsletter HTML file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the first 10 recipients without sending anything",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Only process the first N accounts (useful for a small live test)",
    )
    parser.add_argument(
        "--subject",
        default=None,
        help="Override email subject (default: read from <title> tag)",
    )
    args = parser.parse_args()

    # --- Load newsletter HTML --------------------------------------------------
    if not os.path.isfile(args.newsletter_html):
        print(f"ERROR: Newsletter file not found: {args.newsletter_html}")
        sys.exit(1)

    with open(args.newsletter_html, "r", encoding="utf-8") as f:
        html_template = f.read()

    subject = args.subject or get_subject_from_html(html_template)

    # --- Load send list -------------------------------------------------------
    if not os.path.isfile(DB_PATH):
        print(f"ERROR: Database not found: {DB_PATH}")
        sys.exit(1)

    print("Loading send list from database...")
    records = get_send_list(DB_PATH)

    active_total  = sum(1 for r in records if r["send_status"] == "active")
    retired_total = sum(1 for r in records if r["send_status"] == "recently_retired")
    print(
        f"Found {len(records)} accounts: "
        f"{active_total} active, "
        f"{retired_total} recently retired (paid through within 12 months)"
    )
    print(f"Subject: {subject}")

    if args.limit:
        records = records[: args.limit]
        print(f"Limiting to first {args.limit} accounts.")

    # --- Dry run --------------------------------------------------------------
    if args.dry_run:
        preview = records[:10]
        print(f"\nDRY RUN — first {len(preview)} of {len(records)} accounts (no emails sent):\n")
        print(f"  {'STATUS':<18} {'COMPANY':<32} {'FIRST NAME':<16} EMAIL")
        print(f"  {'-'*18} {'-'*32} {'-'*16} {'-'*35}")
        for r in preview:
            emails     = get_all_emails(r)
            first      = get_first_name(r.get("contact_name"), r.get("company_name"))
            company    = (r.get("company_name") or "")[:31]
            status_lbl = "active" if r["send_status"] == "active" else "recently retired"
            addr_str   = ", ".join(emails) if emails else "(no valid email)"
            print(f"  {status_lbl:<18} {company:<32} {first:<16} {addr_str}")
        print()
        return

    # --- Real send ------------------------------------------------------------
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        print("ERROR: RESEND_API_KEY environment variable is not set.")
        sys.exit(1)

    active_in_batch  = sum(1 for r in records if r["send_status"] == "active")
    retired_in_batch = sum(1 for r in records if r["send_status"] == "recently_retired")
    total_addresses  = sum(len(get_all_emails(r)) for r in records)

    print(f"\nReady to send:")
    print(f"  Active accounts:            {active_in_batch}")
    print(f"  Recently-retired accounts:  {retired_in_batch}")
    print(f"  Total accounts:             {len(records)}")
    print(f"  Total email addresses:      {total_addresses}")
    print(f"  Subject:                    {subject}")
    print(f"  From:                       {FROM_NAME} <{FROM_EMAIL}>")
    print()

    confirm = input("Type YES to send, or anything else to cancel: ").strip()
    if confirm != "YES":
        print("Cancelled.")
        return

    log_file, log_writer, log_path = open_log_file(args.newsletter_html)
    print(f"\nLogging to: {log_path}\n")

    sent_ok   = 0
    sent_fail = 0
    skipped   = 0

    for i, record in enumerate(records, 1):
        emails     = get_all_emails(record)
        company    = (record.get("company_name") or "")[:35]
        status_lbl = "active " if record["send_status"] == "active" else "retired"

        if not emails:
            skipped += 1
            log_row(log_writer, record, "(all fields empty)", "skipped", "no valid email address")
            print(f"[{i:3}/{len(records)}] [SKIP] [{status_lbl}] {company} — no valid email")
            continue

        first_name = get_first_name(record.get("contact_name"), record.get("company_name"))

        for email in emails:
            unsub_link  = build_unsubscribe_link(email)
            merged_html = merge_template(html_template, first_name, unsub_link,
                                         record.get("company_name") or "")
            success, error = send_email(email, subject, merged_html, api_key)

            result_label = "sent" if success else "failed"
            log_row(log_writer, record, email, result_label, error)

            icon = "OK  " if success else "FAIL"
            print(f"[{i:3}/{len(records)}] [{icon}] [{status_lbl}] {company:<35} -> {email}")
            if not success:
                print(f"           ERROR: {error}")
                sent_fail += 1
            else:
                sent_ok += 1

    log_file.close()

    print(f"\nDone.")
    print(f"  Sent OK:  {sent_ok}")
    print(f"  Failed:   {sent_fail}")
    print(f"  Skipped:  {skipped}  (no valid email address)")
    print(f"  Log:      {log_path}")


if __name__ == "__main__":
    main()
