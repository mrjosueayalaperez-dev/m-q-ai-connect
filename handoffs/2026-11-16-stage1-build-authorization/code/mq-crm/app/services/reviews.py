"""Reviews & Referrals: ask at the right moment, make sharing one step."""
from __future__ import annotations

import secrets
import sqlite3

from ..db import now_utc, row_to_dict


def request_review(conn: sqlite3.Connection, customer_id: int) -> dict:
    cur = conn.execute(
        "INSERT INTO reviews (customer_id, created_at) VALUES (?, ?)",
        (customer_id, now_utc()))
    conn.commit()
    return row_to_dict(conn.execute("SELECT * FROM reviews WHERE id = ?",
                                    (cur.lastrowid,)).fetchone())


def record_review(conn: sqlite3.Connection, review_id: int, rating: int,
                  text: str = "") -> dict:
    if not 1 <= rating <= 5:
        raise ValueError("rating must be 1..5")
    conn.execute("UPDATE reviews SET status = 'received', rating = ?, text = ?"
                 " WHERE id = ?", (rating, text, review_id))
    conn.commit()
    return row_to_dict(conn.execute("SELECT * FROM reviews WHERE id = ?",
                                    (review_id,)).fetchone())


def create_referral_code(conn: sqlite3.Connection, customer_id: int) -> dict:
    code = "MQ-" + secrets.token_hex(3).upper()
    cur = conn.execute(
        "INSERT INTO referrals (from_customer_id, code, created_at) VALUES (?, ?, ?)",
        (customer_id, code, now_utc()))
    conn.commit()
    return row_to_dict(conn.execute("SELECT * FROM referrals WHERE id = ?",
                                    (cur.lastrowid,)).fetchone())


def redeem_referral(conn: sqlite3.Connection, code: str, new_customer_id: int) -> dict:
    ref = row_to_dict(conn.execute("SELECT * FROM referrals WHERE code = ?",
                                   (code,)).fetchone())
    if ref is None:
        raise ValueError("referral code not found")
    conn.execute("UPDATE referrals SET referred_customer_id = ?, status = 'redeemed'"
                 " WHERE id = ?", (new_customer_id, ref["id"]))
    conn.commit()
    return row_to_dict(conn.execute("SELECT * FROM referrals WHERE id = ?",
                                    (ref["id"],)).fetchone())
