# Suppression key: backup and recovery (Batch 008d)

**Applies to:** M&Q CRM with Batch 008c+ (retained do-not-message records).
**Status:** procedure for Stage 1. This document contains no key values; every value below is a placeholder.

## 1. What the key does and why it matters
When a customer who opted out is deleted, the CRM keeps a minimal suppression record. It holds an **HMAC-SHA256 of their normalized phone/email under the suppression key**, plus the contact type, channel, scope and a timestamp. When a message is sent or dispatched, the CRM hashes the recipient's contact with the same key and compares it.

**Without the same key, retained records cannot be matched.** A previously opted-out person who is re-created would no longer be recognised. For that reason, the key must be backed up and restored **together with** the database, but **stored separately** from it.

The keyed hash is still personal data. Back up and protect the database with the same care as customer data.

## 2. Where the key lives (precedence)
1. **`MQ_CRM_SUPPRESSION_KEY` environment variable**, if set and non-empty. It always wins, even when a key file exists. Recommended for hosted deployments: keep the value in the host's secret manager.
2. **Otherwise, the key file `<db dir>/suppression.key`**, in the same directory as the SQLite database (`MQ_CRM_DB`; default `data/crm.db`, so `data/suppression.key`). It is created once, on first use, with random 32 bytes (hex) and mode **0600** (owner read/write only).

The database also stores a **non-secret check value**, `HMAC-SHA256(key, "mq-crm/suppression-key-check/v1")`, in table `suppression_key_check`. It lets the app prove that the key it has is the right one. It is not the key, and the key cannot be recovered from it.

`.gitignore` excludes `data/`, `*.db*` and `suppression.key`. Never commit either file.

## 3. Back up (DB and key together, stored apart)
Do both steps at the same time. Losing either one breaks the other.

1. **Database:** take a consistent online snapshot. Don't copy a live file mid-write.
   ```
   sqlite3 <db dir>/crm.db ".backup '<db-backup-location>/crm-<YYYYMMDD>.db'"
   ```
   Encrypt it at rest, like any customer-data backup.
2. **Key:**
   - **Key-file deployments:** encrypt the file to the owner (for example `age -r <OWNER-PUBLIC-KEY>` or `gpg --encrypt -r <OWNER-ID>`). Store the encrypted copy in a **different place** from the DB backups, such as the owner's password manager or a separate encrypted vault, with access limited to the owner.
   - **Env-var deployments:** the value lives in the host secret manager. Keep an owner-only copy in the password manager as `<KEY-FROM-PASSWORD-MANAGER>`.
3. **Never** paste the key into chat, tickets, email, docs, commit messages, logs or reports. The app never prints it; the test `test_b8d_no_error_log_audit_or_delivery_record_contains_the_key` checks this.
4. **Prove the backup works.** Restore both into a scratch directory (section 4) and confirm the status is `verified`.

## 4. Restore
1. Stop the app.
2. Put the database back: copy `crm-<YYYYMMDD>.db` to `<db dir>/crm.db`, and delete any stale `crm.db-wal` / `crm.db-shm` left from the old file.
3. Put the key back, using one of these:
   - **Key file:** decrypt to `<db dir>/suppression.key`, then `chmod 600 <db dir>/suppression.key`, owned by the service user. Make sure `MQ_CRM_SUPPRESSION_KEY` is **unset**, or set to the same value.
   - **Env var:** set `MQ_CRM_SUPPRESSION_KEY=<KEY-FROM-PASSWORD-MANAGER>` in the host secret manager.
4. Start the app. **Startup verifies the key against the stored check value** and refuses to start if it's missing or wrong (section 5).
5. As owner, check `GET /api/admin/suppression-key/status`. It should return `{"state": "verified", "source": "file"|"env", "suppressions": <n>}`. It never returns the key or the check value. Compare `<n>` with the count expected from the backup.

The test `test_b8d_backup_wipe_restore_keeps_suppressions_blocking` runs this full cycle (back up, wipe, restore) and asserts that a re-created customer with the same contact is still refused at send **and** dispatch.

## 5. If the key is missing or doesn't match
The app **fails closed and loudly**. It never silently lets a suppressed contact through, and it never generates a new key for a database that already uses one.

| Situation | What happens |
| --- | --- |
| DB has a key check or suppression rows, env var unset, key file missing | Startup fails with `SuppressionKeyError: suppression key missing … Refusing to generate a new key`. If the key disappears while running, every send, dispatch and opt-out-retaining deletion is refused with the same error (403 / 503 on the API). No new key file is written. |
| Key present but different (wrong file, or a stale env var, which takes precedence) | Startup fails with `SuppressionKeyError: suppression key mismatch: the key from <source> does not match …`. Sends, dispatches and deletions are refused. The error names the **source** (env var or file path), never the value. |
| Key file empty | Refused: "suppression key file … is empty". |
| Brand-new DB (no check value, no suppression rows) | A key is generated once (file mode 0600), unless the env var is set, and its check value is stored. |

**What to do:**
- Restore the matching key from its backup (section 4).
- With a mismatch, first check whether a stale `MQ_CRM_SUPPRESSION_KEY` is overriding a correct key file.
- The app has **no automatic reset or re-key**, on purpose.
- If the key is truly lost, the retained records can no longer be matched. Clearing them would mean previously opted-out, deleted contacts are no longer blocked. That is a founder and legal decision: get Josue's explicit approval before any manual change, and audit it. No tool for this is provided.

## 6. Not covered in this batch
- **Key rotation.** The raw contacts aren't retained, so rows can't be re-hashed under a new key. Rotation would need a dual-key period. Not implemented.
- **Multi-instance deployments.** Every instance must use the same key (use the env var).
