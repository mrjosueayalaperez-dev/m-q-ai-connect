# Hosted HTTPS test server: PLAN ONLY (Batch 010c)

**Status: PLAN. Nothing has been signed up for, created, deployed or hosted.**
Every step below needs **Josue's explicit approval** before anyone runs it. This includes
creating any account, and any step that puts the CRM on the internet. Cost target: **$0**.
Data: **synthetic only**.

Scope: the web CRM from PR #3 (real login, sessions, TOTP) plus Batch 010
(branch `feat/crm-web-login-premium-2026-11-17`), as one test instance for a few
invited testers. Not production, and no real customer data.

Provider facts were checked on 2026-11-17 against the providers' own docs. Free tiers
change, so re-check on the day.

## 1. $0 options, with honest caveats

The CRM keeps everything in **SQLite on local disk**. It also keeps two key files next
to the database, unless their env vars are set. So the deciding question is: **does the
disk survive restarts?**

| Option | $0? | HTTPS | Disk for SQLite | Sleep / idle | Card needed | Fit |
|---|---|---|---|---|---|---|
| **A. Cloudflare Quick Tunnel** in front of a machine we already run (the agent box or Josue's PC) | Yes. No account, no domain | Yes, a random `*.trycloudflare.com` URL | **Persistent** (the machine's own disk) | None, but the URL lives only while `cloudflared` runs, and **changes every start** | No | **Best for a supervised demo window (hours)** |
| **B. Oracle Cloud Always Free VM** (Ampere A1 or AMD micro) + Caddy for HTTPS | Yes, if we stay inside Always Free limits | Yes (Let's Encrypt via Caddy). Needs a hostname: a free DNS name, or use option A's tunnel on the VM | **Persistent** block volume (200 GB free total, 5 free backups) | Oracle may **reclaim an idle instance** (CPU, network and A1 memory below 20% for 7 days). Accounts idle 30+ days may be closed | **Yes**, for identity checks (temporary authorisation hold, no charge) | **Best for a multi-day test** |
| **C. Render free web service** | Yes | Yes (`*.onrender.com`) | **Ephemeral**: SQLite is **lost** on every spin-down, restart and redeploy. Free services cannot attach a persistent disk | Spins down after **15 min** idle; about 1 min to wake | No | Only a reset-every-time demo (reseed on boot). **Not recommended** |
| **D. Koyeb free instance** | Yes (1 per organisation) | Yes (`*.koyeb.app`) | **Ephemeral**: free instances cannot use Volumes | Scales to zero after **1 h** idle (cannot be disabled) | Yes, at signup | Same problem as C. **Not recommended** |
| ~~Fly.io~~ | **No free tier** for new accounts ($1 / 7-day trial; bills under $5 are waived only after adding a card) | Yes | Volumes are paid | n/a | Yes | Excluded: not guaranteed $0 |

Not considered: anything that needs a paid domain, a paid disk, or moving off SQLite (for
example Render Postgres). That is a code change, and free Postgres expires after 30 days.

**Recommendation:** use **A** for a short, supervised test with Josue present. If a
standing multi-day instance is wanted, use **B**. Avoid C and D, because the database would
silently reset.

## 2. Secrets: env vars, never committed

| Variable | What | Where it lives |
|---|---|---|
| `MQ_CRM_DB` | SQLite path (for example `/srv/mqcrm/data/crm.db`) | Host config (not secret) |
| `MQ_CRM_SUPPRESSION_KEY` | HMAC key for do-not-message records | Host secret store / a 0600 env file **outside the repo**, plus an owner-only copy in the password manager |
| `MQ_CRM_TOTP_KEY` | Encrypts the stored TOTP secrets | Same as above. Back up separately from the DB |
| `MQ_CRM_SESSION_IDLE_MINUTES` / `MQ_CRM_SESSION_MAX_HOURS` | 30 / 12 (Josue's decision) | Host config |
| `MQ_CRM_TRANSPORT` | Leave as `outbox`. **No real message sending** on the test server | Host config |
| `MQ_CRM_WEBHOOK_URL` | **Not set** on the test server | — |

Rules:
- Josue sets and rotates the values himself. Agents never see, print or paste them.
- Never put them in git, chat, tickets, logs or reports.
- Generate fresh values **for this test instance only**. Never reuse a value from anywhere else.
- `.gitignore` already excludes `data/`, `*.db*` and `suppression.key`. Add `totp.key` too if that
  file mode is used. Prefer env vars on hosted machines.
- The app reads the env var before any key file. Startup **refuses to run** with a missing or wrong
  suppression key or TOTP key for an existing database. This is fail-closed and intended.

## 3. Database and key backup / restore

Follow `../../mq-crm-batch008/docs/SUPPRESSION-KEY-BACKUP-RESTORE.md` (Batch 008d). Summary:

1. **Back up the DB with SQLite's online backup**, never a raw copy of a live file:
   `sqlite3 "$MQ_CRM_DB" ".backup '/srv/mqcrm/backup/crm-$(date +%Y%m%d).db'"`
   Encrypt the backup at rest.
2. **Back up both keys at the same time, stored apart** from the DB backups, owner-only (the
   password manager). Losing a key makes the matching data unreadable: retained opt-outs or TOTP factors.
3. **Prove the backup** before testers arrive. Restore it into a scratch directory, start the app,
   and check that `GET /api/admin/suppression-key/status` (owner) returns `"state": "verified"`.
4. Option B: also take one Oracle block-volume backup (5 are free). Option A: the machine's normal
   backups, plus step 1.
5. Restore: stop the app, put back the DB (delete stale `-wal`/`-shm`) and both keys, then start.
   Startup verifies the keys.

## 4. Before ANY exposure (the server is bound to 127.0.0.1 until every box is ticked)

1. Install from the branch at a **pinned commit**, in a venv with `requirements.txt`, under its own
   unprivileged user.
2. Set the env vars (section 2). Start uvicorn on **127.0.0.1 only**.
3. **Create the owner with the CLI, on the server shell:**
   `python -m app.auth_cli create-owner --username <owner>`. The password is typed at the prompt,
   never on the command line or in shell history.
4. **Enroll TOTP for the owner BEFORE exposure.** Over localhost, sign in (token mode):
   `POST /api/auth/totp/enroll`, scan in the authenticator app, then `POST /api/auth/totp/confirm`.
   Store the recovery codes in the password manager.
   - Check `GET /api/auth/me` shows `"two_step": {"enabled": true}` and no
     `owner_two_step_not_enrolled` warning.
   - The startup log must no longer warn about it.
5. Create the testers' **staff / viewer** accounts as the owner (strong unique passwords, shared out of band).
6. Load **synthetic data only** (the seed script). The "Test data" label stays on.
7. **Proxy / client IP (required behind a tunnel or platform proxy):** the app deliberately does
   not trust `X-Forwarded-For`.
   - Behind a proxy, every visitor would share the proxy's address, so 20 failures from anyone
     would lock **everyone** out (the per-IP lock).
   - Run uvicorn with `--proxy-headers --forwarded-allow-ips <the proxy's address only>`.
     For option A that is `127.0.0.1`, since cloudflared runs on the same machine.
   - Test the lockout once from two addresses.
8. **HTTPS, cookies and CSRF:** HTTPS is terminated by Cloudflare / Caddy / the platform. The
   app already sets `mq_session` as `HttpOnly; Secure; SameSite=Strict; Path=/api`, so the cookie
   only works over HTTPS. That is intended. Then verify over the public URL:
   - sign-in;
   - a write, which proves the Origin/Host check passes (if the proxy rewrites `Host`, configure
     it to pass the public host, e.g. cloudflared `--http-host-header`);
   - a write without `X-CSRF-Token` returns 403;
   - `X-Role` is ignored (401).
9. **Lock the door:**
   - Option A: start the tunnel with `--allowed-mail <invited emails>`, so only invited testers
     get past Cloudflare's one-time PIN, in front of the CRM's own login.
   - Option B: only ports 80/443 are open; SSH is by key only and from Josue's IP.
10. Run the security battery (`pytest tests/test_security_battery.py tests/test_batch9*.py tests/test_batch10b.py`)
    on the server's checkout. Record the commit SHA and the result.
11. Josue gives the explicit go. Only then is the public URL started or opened.

## 5. While it runs

- Synthetic data only. Real customer names, numbers or emails are **not allowed**.
- Outbound messaging stays on `outbox`. Nothing is sent to real phones or emails.
- Watch the log for repeated lockouts. One owner-run DB backup per day (section 3).
- Label everything **TEST**, in line with the "Test data" chip. Never call it live or production.

## 6. Teardown (same day for A; at the end of the test window for B/C/D)

1. Announce the end to testers. Stop the tunnel / close the firewall, so the public URL dies first.
2. Take a final DB backup only if Josue wants the synthetic test record kept. Otherwise skip it.
3. Stop the app. Delete the DB, the `-wal`/`-shm` files, the key files, any backups on the host,
   and the env file.
4. Revoke every tester account (the DB deletion covers this) and the owner's authenticator entry.
   Destroy the test-only key values in the secret store.
5. Provider:
   - **A:** nothing to delete. The quick-tunnel URL ended with the process.
   - **B:** terminate the instance, delete its boot and block volumes **and volume backups**,
     delete DNS records, and remove SSH keys. Optionally close the account.
   - **C/D:** delete the service and its env vars.
6. Record what was deleted, and when (America/New_York), in the batch report. Confirm the URL no
   longer answers.

## 7. Decisions for Josue

1. Approve hosting at all. Then choose **A** (supervised demo window) or **B** (standing
   multi-day instance; needs an Oracle account and a card check, $0 if we stay in Always Free).
2. Who the testers are: their email addresses (for the option A allow-list) and their roles.
3. The test window, and the teardown date and time.
4. Who holds the password-manager entries for the keys and recovery codes (Josue only is the default).
