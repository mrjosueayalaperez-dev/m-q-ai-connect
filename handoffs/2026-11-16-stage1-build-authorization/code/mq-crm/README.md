# M&Q CRM — Stage 1

**Built by Muse (Chief of Staff) on the founder's direct order, November 17, 2026** — the founder bypassed the pending Moose ACK gate ("he's waiting on you and you're waiting on him") and reassigned the Stage 1 build. The ACK precondition is recorded **waived, not met**. Stage 1 authorization terms (Nov 16) govern unchanged: isolated work, no production deployment, no protected-branch merge, no purchases, synthetic data only, no credentials anywhere in the code.

**Governing strategy (founder-adopted Nov 16, 2026): Better. Cheaper. Easier. More accessible. Multilingual.** — *We don't make people learn how to use technology. We make technology learn how to serve people.*

## What Stage 1 is

A working CRM for solo and small local service businesses — the entry segment from the verified research:

- **One Record** — a customer exists once; phone/email duplicates resolve to the existing record under a stated rule.
- **Book & Remind** — bookings in the customer's IANA timezone, stored as UTC instants; due-reminder query built in.
- **Quote → Invoice → Paid** — full chain; money is integer minor units + ISO currency; an invoice is *paid* only when payments sum to its total.
- **Comeback Engine** — lapsed-customer detection **plus backlog import of an existing lapsed list** with validation, duplicate resolution, and an outcome report (received / imported / merged / rejected-with-reasons) — the capability the research found no incumbent offering at this level.
- **Message Center EN/ES** — per-customer language preference; authored bilingual templates; **originals always preserved** next to translations; free text in the wrong language waits for a human translation; **nothing sends without human approval** (draft → approved → sent, enforced in code); marketing sends refuse without recorded consent.
- **Reviews & Referrals** — request/record flow and referral codes.
- **Simple Reports** — customers, lapsed, open invoices by currency, payments, upcoming bookings, average rating.
- **Your Data Is Yours** — full export (JSON) and deletion that propagates to every child record, audited.
- **AI Assistance** — draft generation from the authored templates, marked `ai_draft`, gated by the same human-approval rule. **No external AI provider is connected**: the standing privacy rule requires a provider's data-processing terms review first; none has been reviewed. Stated as a limitation, not hidden.

## Architecture notes (14-item checklist, Stage 1 subset)

Built: multi-currency + timezone-aware records (UTC instants, IANA zones) · extensible language architecture (a new language is a catalog entry; PT/HT designed-for, **not** shipped or claimed) · role-based access enforced server-side (viewer read-only, owner-only deletion/export) · audit log for consequential actions · processing register table started (empty — no provider processes customer data) · region/residency metadata: designed-for (fields land with the first hosted deployment; no hosted deployment exists yet). CONNECT boundary: this app exposes its own API only; no cross-product data flows exist.

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
MQ_CRM_DB=data/crm.db .venv/bin/uvicorn app.main:app --port 8300
# UI + API at http://localhost:8300/
```

## Test it

```bash
.venv/bin/python -m pytest tests/ -q
```

Synthetic data only, everywhere. No real customer data has ever touched this codebase.

## Honest status

IMPLEMENTED (all modules above) · TESTED (pytest suite — see the batch report for the run as it came out) · NOT independently verified (Zelator's inspection is the next loop step) · NOT deployed · NOT merged anywhere. Known limitations are listed in the batch report, not buried here.
