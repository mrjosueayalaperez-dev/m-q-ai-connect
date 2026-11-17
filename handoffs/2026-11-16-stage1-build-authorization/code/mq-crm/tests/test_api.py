import os
import tempfile

os.environ["MQ_CRM_DB"] = os.path.join(tempfile.mkdtemp(), "api-test.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["product"] == "M&Q CRM"


def test_customer_flow_and_rbac():
    r = client.post("/api/customers", json={
        "name": "API Ana", "phone": "3215550300", "language": "es",
        "consent_marketing": True, "consent_source": "api test"})
    assert r.status_code == 200
    cust = r.json()["customer"]
    assert cust["language"] == "es"
    # viewer role may not write
    r = client.post("/api/customers", json={"name": "Nope"},
                    headers={"X-Role": "viewer"})
    assert r.status_code == 403
    # deletion requires owner; staff is refused
    r = client.delete(f"/api/customers/{cust['id']}", headers={"X-Role": "staff"})
    assert r.status_code == 403


def test_import_endpoint_reports_outcome():
    csv_text = ("name,phone,email,language,last_service_date\n"
                "Csv Carmen,321-555-0301,carmen@example.com,es,2025-06-01\n"
                ",321-555-0302,x@example.com,en,2025-06-01\n")
    r = client.post("/api/comeback/import", content=csv_text,
                    headers={"Content-Type": "text/csv"})
    assert r.status_code == 200
    body = r.json()
    assert body["received"] == 2 and body["imported"] == 1
    assert len(body["rejected"]) == 1
    r = client.get("/api/reports/summary")
    assert r.json()["customers"] >= 1
