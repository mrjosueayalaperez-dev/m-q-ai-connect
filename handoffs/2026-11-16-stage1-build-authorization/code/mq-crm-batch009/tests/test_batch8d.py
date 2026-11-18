"""Batch 008d — suppression-key continuity (review acceptance item, relayed
Nov 17, 3:05 PM ET).
- backup -> wipe -> restore of DB + key keeps retained suppressions blocking
  send AND dispatch for the same contact;
- a missing key is never regenerated once the DB uses one; a wrong key is
  refused — both fail LOUDLY (startup refuses; send/dispatch/delete refuse);
- env var takes precedence over the key file;
- no error, log, audit row or delivery record contains the key or its
  check value.
Synthetic data only; keys are random per test and never printed."""
import glob
import logging
import os
import secrets
import shutil
import sqlite3
import stat
import subprocess
import sys

import pytest

from app import db as dbmod
from app.services import customers, data_rights, delivery, messages, policy
from tests.conftest import auth_headers  # noqa: E402

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHONE = "3215557701"


@pytest.fixture(autouse=True)
def _no_env_key(monkeypatch):
    monkeypatch.delenv("MQ_CRM_SUPPRESSION_KEY", raising=False)


def _seed(path, phone=PHONE):
    """A file DB holding one retained SMS + marketing suppression for
    `phone` (customer opted out, then was deleted)."""
    c = dbmod.connect(path)
    cust, _ = customers.create_customer(c, "Synthetic B8d", phone=phone,
                                        consent_marketing=True, consent_source="b8d")
    policy.record_channel_opt_out(c, cust["id"], "sms", "STOP", "op", "owner")
    customers.set_consent(c, cust["id"], False, "withdrawn")
    assert data_rights.delete_customer(c, cust["id"])["suppressions_retained"] == 2
    return c


def _key_text(path):
    with open(os.path.join(os.path.dirname(path), "suppression.key"), "rb") as f:
        return f.read().strip().decode()


def _check_value(c):
    return c.execute("SELECT check_value FROM suppression_key_check").fetchone()[0]


def _blocked_everywhere(c, phone=PHONE):
    """A re-created customer with the same contact: send AND dispatch refused."""
    cust, _ = customers.create_customer(c, "Synthetic B8d again", phone=phone,
                                        consent_marketing=True, consent_source="b8d")
    m = messages.compose_free_text(c, cust["id"], "Your part arrived.", "en",
                                   purpose="transactional")
    messages.approve(c, m["id"], "op", "owner")
    with pytest.raises(PermissionError) as e_send:
        messages.send(c, m["id"])
    c.execute("UPDATE messages SET status = 'sent' WHERE id = ?", (m["id"],))
    c.commit()
    with pytest.raises(PermissionError) as e_disp:
        delivery.dispatch(c, m["id"])
    assert delivery.get_delivery(c, m["id"])["status"] == "failed"
    return str(e_send.value), str(e_disp.value), m["id"]


def _wipe(path):
    for f in glob.glob(path + "*") + [os.path.join(os.path.dirname(path), "suppression.key")]:
        if os.path.exists(f):
            os.remove(f)


# --------------------------------------------------------------- restore

def test_b8d_backup_wipe_restore_keeps_suppressions_blocking(tmp_path):
    live = tmp_path / "live"; live.mkdir()
    db_bak = tmp_path / "backup-db"; db_bak.mkdir()      # stored separately
    key_bak = tmp_path / "backup-key"; key_bak.mkdir()
    path = str(live / "crm.db")
    c = _seed(path)
    # 1. Back up: consistent DB snapshot (SQLite online backup) + key, apart.
    dst = sqlite3.connect(str(db_bak / "crm.db"))
    c.backup(dst)
    dst.close()
    shutil.copy2(live / "suppression.key", key_bak / "suppression.key")
    os.chmod(key_bak / "suppression.key", 0o600)
    c.close()
    # 2. Wipe both.
    _wipe(path)
    assert not os.listdir(live)
    # 3. Restore both (key back with 0600).
    shutil.copy2(db_bak / "crm.db", path)
    shutil.copy2(key_bak / "suppression.key", live / "suppression.key")
    os.chmod(live / "suppression.key", 0o600)
    c = dbmod.connect(path)
    assert policy.verify_suppression_key(c)["state"] == "verified"
    assert c.execute("SELECT COUNT(*) FROM suppressions").fetchone()[0] == 2
    # 4. The retained suppression still blocks the same contact.
    send_err, disp_err, _ = _blocked_everywhere(c, phone="+1 (321) 555-7701")
    assert "do-not-message" in send_err and "do-not-message" in disp_err
    assert stat.S_IMODE(os.stat(live / "suppression.key").st_mode) == 0o600
    c.close()


def test_b8d_restoring_the_db_without_its_key_fails_loudly_and_never_regenerates(tmp_path):
    path = str(tmp_path / "crm.db")
    c = _seed(path)
    c.close()
    os.remove(tmp_path / "suppression.key")              # DB restored, key lost
    c = dbmod.connect(path)
    with pytest.raises(policy.SuppressionKeyError) as ei:
        policy.verify_suppression_key(c)
    assert "suppression key missing" in str(ei.value)
    assert "Refusing to generate a new key" in str(ei.value)
    assert not os.path.exists(tmp_path / "suppression.key")   # NOT regenerated
    send_err, disp_err, mid = _blocked_everywhere(c)
    assert "suppression key missing" in send_err and "suppression key missing" in disp_err
    assert not os.path.exists(tmp_path / "suppression.key")
    # Deletion that would write a suppression is refused too (and rolls back).
    cust, _ = customers.create_customer(c, "Synthetic B8d del", phone="3215557702",
                                        consent_source="b8d")
    policy.record_channel_opt_out(c, cust["id"], "sms", "STOP", "op", "owner")
    with pytest.raises(policy.SuppressionKeyError):
        data_rights.delete_customer(c, cust["id"])
    assert customers.get_customer(c, cust["id"]) is not None
    c.close()


def test_b8d_key_check_alone_also_prevents_regeneration(tmp_path):
    """No suppression rows yet, but the DB already has a key check: a
    missing key is still refused (future suppressions must use the same key)."""
    path = str(tmp_path / "crm.db")
    c = dbmod.connect(path)
    policy.contact_hmac(c, "phone", PHONE)               # establishes key + check
    assert c.execute("SELECT COUNT(*) FROM suppressions").fetchone()[0] == 0
    os.remove(tmp_path / "suppression.key")
    with pytest.raises(policy.SuppressionKeyError):
        policy.contact_hmac(c, "phone", PHONE)
    assert not os.path.exists(tmp_path / "suppression.key")
    c.close()


def test_b8d_wrong_key_fails_loudly_at_send_dispatch_and_status(tmp_path):
    path = str(tmp_path / "crm.db")
    c = _seed(path)
    with open(tmp_path / "suppression.key", "wb") as f:  # someone else's key
        f.write(secrets.token_hex(32).encode())
    with pytest.raises(policy.SuppressionKeyError) as ei:
        policy.verify_suppression_key(c)
    assert "suppression key mismatch" in str(ei.value)
    send_err, disp_err, mid = _blocked_everywhere(c)
    assert "mismatch" in send_err and "mismatch" in disp_err
    assert "mismatch" in delivery.get_delivery(c, mid)["detail"]
    c.close()


def test_b8d_env_var_takes_precedence_over_the_key_file(tmp_path, monkeypatch):
    path = str(tmp_path / "crm.db")
    c = _seed(path)
    file_key = _key_text(path)
    h_file = policy.contact_hmac(c, "phone", PHONE)
    # Same key supplied by env -> accepted, identical identifiers.
    monkeypatch.setenv("MQ_CRM_SUPPRESSION_KEY", file_key)
    assert policy.verify_suppression_key(c)["source"] == "env"
    assert policy.contact_hmac(c, "phone", PHONE) == h_file
    # A different env key wins over the (correct) file -> refused.
    monkeypatch.setenv("MQ_CRM_SUPPRESSION_KEY", secrets.token_hex(32))
    with pytest.raises(policy.SuppressionKeyError) as ei:
        policy.contact_hmac(c, "phone", PHONE)
    assert "environment variable" in str(ei.value)
    # Env removed -> the file is used again.
    monkeypatch.delenv("MQ_CRM_SUPPRESSION_KEY")
    assert policy.verify_suppression_key(c)["source"] == "file"
    c.close()
    # Env-only deployment: a fresh DB never writes a key file.
    fresh = tmp_path / "envonly"; fresh.mkdir()
    monkeypatch.setenv("MQ_CRM_SUPPRESSION_KEY", secrets.token_hex(32))
    c2 = dbmod.connect(str(fresh / "crm.db"))
    policy.contact_hmac(c2, "phone", PHONE)
    assert not os.path.exists(fresh / "suppression.key")
    assert policy.verify_suppression_key(c2)["state"] == "verified"
    c2.close()


def test_b8d_fresh_database_generates_one_key_and_a_non_secret_check(tmp_path):
    path = str(tmp_path / "crm.db")
    c = dbmod.connect(path)
    assert policy.verify_suppression_key(c)["state"] == "not_initialized"
    h = policy.contact_hmac(c, "phone", PHONE)
    key = _key_text(path)
    assert stat.S_IMODE(os.stat(tmp_path / "suppression.key").st_mode) == 0o600
    chk = _check_value(c)
    assert chk != key and key not in chk and len(chk) == 64
    c.close()
    c = dbmod.connect(path)                               # reconnect: same key
    assert policy.contact_hmac(c, "phone", PHONE) == h
    assert _key_text(path) == key
    c.close()


def _startup(path, env_key=None):
    env = dict(os.environ, MQ_CRM_DB=path)
    env.pop("MQ_CRM_SUPPRESSION_KEY", None)
    if env_key:
        env["MQ_CRM_SUPPRESSION_KEY"] = env_key
    return subprocess.run([sys.executable, "-c", "import app.main"], cwd=WORK,
                          env=env, capture_output=True, text=True, timeout=60)


def test_b8d_app_refuses_to_start_with_a_missing_or_wrong_key(tmp_path):
    path = str(tmp_path / "crm.db")
    c = _seed(path)
    key, chk = _key_text(path), _check_value(c)
    c.close()
    ok = _startup(path)
    assert ok.returncode == 0, "starts with the right key"
    shutil.move(str(tmp_path / "suppression.key"), str(tmp_path / "moved.key"))
    missing = _startup(path)
    assert missing.returncode != 0
    assert "SuppressionKeyError" in missing.stderr
    assert "suppression key missing" in missing.stderr
    assert not os.path.exists(tmp_path / "suppression.key")
    wrong_env = secrets.token_hex(32)
    wrong = _startup(path, env_key=wrong_env)
    assert wrong.returncode != 0 and "suppression key mismatch" in wrong.stderr
    shutil.move(str(tmp_path / "moved.key"), str(tmp_path / "suppression.key"))
    assert _startup(path).returncode == 0                 # restored -> starts
    for out in (ok, missing, wrong):
        text = out.stdout + out.stderr
        assert key not in text and chk not in text and wrong_env not in text


def test_b8d_no_error_log_audit_or_delivery_record_contains_the_key(tmp_path, caplog):
    caplog.set_level(logging.DEBUG)
    path = str(tmp_path / "crm.db")
    c = _seed(path)
    key, chk = _key_text(path), _check_value(c)
    errors = []
    with open(tmp_path / "suppression.key", "wb") as f:
        f.write(secrets.token_hex(32).encode())
    wrong = _key_text(path)
    for fn in (lambda: policy.verify_suppression_key(c),
               lambda: _blocked_everywhere(c)):
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            errors.append(str(e))
    os.remove(tmp_path / "suppression.key")
    try:
        policy.verify_suppression_key(c)
    except policy.SuppressionKeyError as e:
        errors.append(str(e))
    assert len(errors) >= 2
    dump = "\n".join(errors) + caplog.text
    dump += "\n".join(str(tuple(r)) for r in c.execute("SELECT * FROM audit_log"))
    dump += "\n".join(str(tuple(r)) for r in c.execute("SELECT * FROM deliveries"))
    for secret in (key, wrong, chk):
        assert secret not in dump
    c.close()


def test_b8d_status_route_is_owner_only_and_never_returns_the_key():
    from fastapi.testclient import TestClient
    from app import main as main_mod
    client = TestClient(main_mod.app)
    r = client.get("/api/admin/suppression-key/status")
    assert r.status_code == 200 and r.json()["state"] in ("verified", "not_initialized")
    assert set(r.json()) <= {"state", "source", "suppressions"}
    assert client.get("/api/admin/suppression-key/status",
                      headers=auth_headers("staff")).status_code == 403
