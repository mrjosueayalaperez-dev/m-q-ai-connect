"""Comeback Engine: find the customers who drifted away — including the
ones sitting in an old list nobody ever imported.

Backlog import is demonstrated, not displayed: every run returns an outcome
report (received / imported / rejected with reasons / merged as duplicates),
proven by tests on synthetic records (tests/test_comeback_import.py).
"""
from __future__ import annotations

import csv
import io
import sqlite3
from datetime import datetime, timedelta, timezone

from ..db import now_utc
from . import customers as customers_svc

EXPECTED_COLUMNS = {"name", "phone", "email", "language", "last_service_date"}


def lapsed_customers(conn: sqlite3.Connection, inactive_days: int = 90,
                     now: str | None = None) -> list[dict]:
    """Customers whose last service is older than the threshold, plus
    imported customers who have never been served at all."""
    now_dt = datetime.strptime(now or now_utc(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    cutoff = (now_dt - timedelta(days=inactive_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = conn.execute(
        "SELECT * FROM customers WHERE merged_into IS NULL"
        " AND (last_service_at IS NULL OR last_service_at <= ?)"
        " ORDER BY COALESCE(last_service_at, '0000') ASC", (cutoff,))
    return [dict(r) for r in rows]


def _validate_row(row: dict, line_no: int) -> str | None:
    name = (row.get("name") or "").strip()
    phone = (row.get("phone") or "").strip()
    email = (row.get("email") or "").strip()
    if not name:
        return f"line {line_no}: missing name"
    if not phone and not email:
        return f"line {line_no}: missing both phone and email (no way to reach them)"
    if email and "@" not in email:
        return f"line {line_no}: email looks invalid"
    raw_date = (row.get("last_service_date") or "").strip()
    if raw_date:
        try:
            datetime.strptime(raw_date, "%Y-%m-%d")
        except ValueError:
            return f"line {line_no}: last_service_date must be YYYY-MM-DD"
    lang = (row.get("language") or "en").strip().lower()
    if lang not in ("en", "es", "pt", "ht"):
        return f"line {line_no}: unsupported language '{lang}'"
    return None


def import_backlog(conn: sqlite3.Connection, csv_text: str) -> dict:
    """Import a lapsed-customer list (CSV). Returns the outcome report.

    Columns: name, phone, email, language, last_service_date (YYYY-MM-DD).
    Duplicates — within the file or against the database — resolve to the
    one existing record under the One Record rule and count as 'merged'.
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None or not EXPECTED_COLUMNS.issubset(
            {f.strip() for f in reader.fieldnames}):
        raise ValueError(
            "CSV must have columns: name, phone, email, language, last_service_date")
    report = {"received": 0, "imported": 0, "merged": 0, "rejected": []}
    for i, raw in enumerate(reader, start=2):  # line 1 is the header
        row = {(k or "").strip(): (v or "") for k, v in raw.items()}
        if not any(v.strip() for v in row.values()):
            continue  # blank line: not received, not rejected
        report["received"] += 1
        problem = _validate_row(row, i)
        if problem:
            report["rejected"].append({"line": i, "reason": problem})
            continue
        last_service = None
        raw_date = (row.get("last_service_date") or "").strip()
        if raw_date:
            last_service = raw_date + "T00:00:00Z"
        _, merged = customers_svc.create_customer(
            conn,
            name=row["name"].strip(),
            phone=(row.get("phone") or "").strip() or None,
            email=(row.get("email") or "").strip() or None,
            language=(row.get("language") or "en").strip().lower(),
            source="backlog_import",
            last_service_at=last_service,
        )
        if merged:
            report["merged"] += 1
        else:
            report["imported"] += 1
    return report
