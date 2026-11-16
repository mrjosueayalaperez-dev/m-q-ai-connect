# M&Q CRM — Stage 1 Review Criteria & Acceptance Checklist
**Prepared by Muse, November 16, 2026, while Moose's ACK is still pending — so the standard exists before the first batch arrives, and the builder is judged by the same list he can read.** Applied jointly: Muse verifies the evidence; Zelator inspects independently; a cycle closes only when both pass on evidence. The founder approves anything that reaches production. Statuses throughout: implemented ≠ tested ≠ verified ≠ deployed.

## A. Every batch report must carry (batch acceptance)
- [ ] Work sits on an isolated branch; nothing merged into a protected/production branch.
- [ ] Changed files are listed and inspectable in GitHub — claims point at code, not summaries.
- [ ] Tests were executed and the **actual results** are reported as they came out (counts, failures included).
- [ ] Implemented / tested / deployed are stated separately; nothing is called deployed that is not.
- [ ] Known limitations and incomplete items are listed in the batch, not discovered later.
- [ ] No credentials, database identifiers, secrets, or customer/customer-like data anywhere in the repo or the report.
- [ ] Any delivered artifact carries its SHA-256; verifiers hash their own copies.

## B. Functional acceptance (Stage 1 scope — entry segment)
- [ ] **One Record** — a customer exists once; jobs, messages, and payments attach to that record.
- [ ] **Book & Remind** — booking with reminders a solo operator can run unaided.
- [ ] **Quote → Invoice → Paid** — the full chain works end to end under test, amounts in integer minor units with ISO currency code.
- [ ] **Comeback Engine** — lapsed-customer identification works, **including import of an existing lapsed list (the backlog)** — the capability no incumbent offers at this level; forward-only logic alone does not pass.
- [ ] **Backlog import — demonstrated, not displayed** *(safeguard added Nov 16, 2026)*: the import must be proven by a real test run on **synthetic records**, showing all three: **(1) validation** — malformed or incomplete rows are rejected, each with its reason; **(2) duplicate handling** — the same customer appearing more than once resolves to one record under a stated rule; **(3) an outcome report** — counts of records received / imported / rejected / merged, with reasons. A button, an import screen, or a code path nobody has run earns nothing: the test output is the evidence.
- [ ] **Message Center EN/ES** — two-way messaging with the customer's language preference stored per customer.
- [ ] **Reviews & Referrals** — request flow present and testable.
- [ ] **Simple Reports** — the few numbers a solo operator actually checks, readable at a glance.
- [ ] **Your Data Is Yours** — full export and deletion both work under test, deletion propagating as designed.
- [ ] **AI Assistance** — drafts and suggestions only; **a human approves every customer-facing send**; no AI path silently makes a consequential customer decision.

## C. Language acceptance
- [ ] Shipped surfaces are EN/ES complete — parity, not a translated skin over an English-only admin (the Jobber failure mode is the named anti-pattern).
- [ ] Originals are preserved alongside every translation, with prices, dates, addresses, and commitments verifiable against the original.
- [ ] Machine translation is disclosed where the evidence rules require it, in the customer's preferred language.
- [ ] **No HT spoken-output claim anywhere** — no provider exists; HT text paths, if claimed, carry a measured quality result, not an adjective.
- [ ] Per-customer language preference drives outbound language; interface language, two-way messaging, and voice are never conflated in claims.

## D. Privacy & safety acceptance
- [ ] **Privacy rule honored:** no customer message routes through any AI/translation provider before that provider's data-processing terms are reviewed and required opt-outs configured — the review is evidenced, per provider, per service (the Lane 11/13 standard).
- [ ] Consent and communication preferences are recorded per customer and respected by every send path.
- [ ] Retention/deletion controls cover originals and translations alike.
- [ ] Synthetic data only in every test, demo, and POC artifact.
- [ ] Security basics evidenced: role-based access enforced server-side, audit trail for consequential actions, no secrets in code or history.

## E. Architecture — design-in items (Stage 1 applicable subset)
For each: state **built / designed-for / not addressed**, with evidence — designed-for is an honest pass at Stage 1; silently absent is not.
- [ ] Multi-currency + time-zone-aware records (UTC instants, IANA zones) in the data model.
- [ ] Region/data-residency metadata fields present.
- [ ] Extensible language architecture (a fifth language is a configuration, not a rewrite).
- [ ] Role-based access/permissions model.
- [ ] Processing register started (what data, which provider, what terms).
- [ ] Integration & data-portability boundaries defined (CONNECT touches only task-authorized data).

## F. Claims & economics honesty
- [ ] No "SSO included" promise in product copy or docs without the verified per-customer cost model behind it (WorkOS benchmark: $250/mo per SSO+SCIM customer).
- [ ] The $19–$29 band is labeled PROPOSED wherever it appears until Stage 0 evidence (H2) returns; no willingness-to-pay claim before then.
- [ ] No capability is described with a status stronger than its evidence (this checklist's own rule, applied to the product).

## G. How a cycle closes
1. Moose's batch report lands under `reports/` in this folder.
2. Muse verifies: fingerprints, test evidence, claim-by-claim against the register and this checklist.
3. Zelator inspects independently and adds his findings.
4. One consolidated corrections list is issued under `corrections/` — disagreements between verifiers are reported as disagreements.
5. Moose implements; the next batch answers the list item by item.
6. A cycle closes only when both verifications pass. Production remains a separate founder decision, always.

*Prepared November 16, 2026. This checklist is the review standard — it authorizes nothing and completes nothing. It exists so that when the work arrives, judgment is fast, identical on both sides, and based on evidence.*
