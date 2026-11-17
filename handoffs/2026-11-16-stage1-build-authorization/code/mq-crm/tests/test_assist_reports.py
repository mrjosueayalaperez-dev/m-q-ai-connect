import pytest

from app.services import ai_assist, customers, messages, reports, reviews


def test_ai_draft_is_draft_and_cannot_send(conn):
    cust, _ = customers.create_customer(
        conn, "Draftee", phone="3215550230", consent_marketing=True,
        consent_source="verbal")
    draft = ai_assist.draft_comeback(conn, cust["id"])
    assert draft["created_by"] == "ai_draft" and draft["status"] == "draft"
    with pytest.raises(PermissionError):
        messages.send(conn, draft["id"])


def test_reviews_and_referrals(conn):
    cust, _ = customers.create_customer(conn, "Fan", phone="3215550231")
    req = reviews.request_review(conn, cust["id"])
    done = reviews.record_review(conn, req["id"], 5, "Great")
    assert done["status"] == "received" and done["rating"] == 5
    with pytest.raises(ValueError):
        reviews.record_review(conn, req["id"], 9)
    ref = reviews.create_referral_code(conn, cust["id"])
    new_cust, _ = customers.create_customer(conn, "Referred", phone="3215550232")
    redeemed = reviews.redeem_referral(conn, ref["code"], new_cust["id"])
    assert redeemed["status"] == "redeemed"


def test_reports_summary(conn):
    cust, _ = customers.create_customer(
        conn, "Counted", phone="3215550233", last_service_at="2025-01-01T00:00:00Z")
    s = reports.summary(conn)
    assert s["customers"] == 1 and s["lapsed_customers"] == 1
    assert s["average_rating"] is None
