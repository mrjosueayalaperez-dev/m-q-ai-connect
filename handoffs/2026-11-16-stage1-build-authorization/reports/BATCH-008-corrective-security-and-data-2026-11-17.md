# BATCH 008 (+008b, +008c) — Corrective batch: deletion, deny-by-default, XSS, concurrency, consent, approval audit, endpoint-bound privacy gate, Batch 006 gaps
**Date:** November 17, 2026 · **Builder:** MNQ Eng (Grok Bot) · **Authorization:** founder approval relayed by Chief of Staff (Nov 17, 1:08 PM ET): fix the defects found by the Nov 17 read-only audit on a NEW draft branch cut from `handoff/moose-crm-package-2026-11-16` @ `3c03375`; draft PR only.
**Status: IMPLEMENTED + TESTED (builder-side) · NOT INDEPENDENTLY VERIFIED · NOT MERGED · NOT DEPLOYED.** Moose's Batch 004/005 reconciliation is untouched. Delivered Batch 001–007 folders are untouched (addenda discipline): every changed file is a full copy under `code/mq-crm-batch008/`, overlaid last.

## How to assemble and run
`code/mq-crm` → overlay `mq-crm-batch004` → `005` → `006` → `007` → `008`, then `pip install -r requirements.txt && pytest -q`.

## What was fixed (one line per item; details in the code docstrings)
1. **Customer deletion after a dispatch (500 since Batch 005).** `data_rights.delete_customer` is ONE `BEGIN IMMEDIATE` transaction: deliveries are deleted first (they reference messages), then items/payments, children, the customer, and the `delete_customer` audit row (written with `commit=False`, counts only). Any error rolls everything back. A delivery still `sending` blocks deletion (409) instead of racing it. Unknown customer → 404. Export now includes `deliveries`. API requests also run on their own connection that is rolled back if left open, so a partial write can never be committed by a later unrelated request.
2. **Deny by default.** A global dependency on every route: `X-Role` must be `owner|staff|viewer` or the request is 401 (no more silent `owner`), and every write must carry a non-empty `X-Actor`. All 30 `Header("owner")` defaults are gone; every GET calls `require_read`; `/api/export` stays owner-only. `/api/health` stays open (liveness only, returns no data). The UI now has Operator + Role controls (default **viewer**) and sends both headers. Authentication in front of the header is still a deployment concern (unchanged, stated).
3. **Stored XSS.** New `web/safe_html.js`: an `html` tagged template escapes every interpolated value; `setHTML()` is the only innerHTML sink and refuses non-`html` strings. All 9 renderers in `app.js` use it; `app.js` contains no `innerHTML`.
4. **Shared SQLite connection.** Per-request connections (ASGI middleware + contextvar) and per-thread connections elsewhere; WAL mode. The module-level `conn` is now a proxy, never one shared connection. Dispatch claims the delivery row with ONE conditional UPDATE (`queued|failed → sending` + claim token; unique index on `deliveries.message_id`), so concurrent dispatches give exactly one transport call; losers get 409 / `DispatchInProgress`. Webhook requests carry `Idempotency-Key: mq-crm-message-<id>`. A `sending` claim older than 300 s may be retried.
5. **Consent bypass.** Messages carry `purpose`. Consent and channel opt-out are re-read at send AND at dispatch for every message type (template, free text, AI draft). A refusal is recorded on the delivery (`consent gate`) and audited (`dispatch_denied`). *Superseded in part by Batch 008b below:* free text no longer defaults to marketing; a message with no clear purpose is **held**.
6. **Approval audit.** `approve_message` audit row (actor, role, approved content hash, timestamp, purpose) plus `approved_by / approved_role / approved_at` on the message.
7. **Privacy gate matched the literal name 'webhook'.** The gate now matches the configured `MQ_CRM_WEBHOOK_URL` against the register row's `endpoint` (scheme, host, port, and path prefix if given). The provider name is a label only. Endpoints are stored without userinfo/query (where credentials hide), and refusals name the host only.
8. **Batch 006 gaps.** (a) Register fields `terms_reference` (required to record a review), `reviewed_at`, `reviewed_by`, `withdrawn_at`, `endpoint`. (b) Withdrawal vs in-flight dispatch: dispatch re-checks the gate under a shared lock right before the transport call, and changing a review takes the lock exclusively (`app/gate_lock.py`). A claimed-but-not-yet-sent dispatch is refused after a withdrawal. A POST already on the wire when the withdrawal arrives completes first, and the withdrawal commits right after it (≤5 s), so nothing passes the gate after the withdrawal commits. Scope: in-process lock (Stage 1 is single-process).

## Batch 008b — messaging policies (founder approval relayed by Chief of Staff, Nov 17, 1:33 PM ET)
Same branch, new commit. Same status: IMPLEMENTED + TESTED (builder-side), NOT MERGED, NOT DEPLOYED. New module `app/services/policy.py` holds the policy. `messages.enforce_policy()` is the single check run at send and at dispatch.

**Rule 1: classify by purpose, not by free text vs template.**
- Purposes: `marketing` (promotional, sales, solicitation, advertising), which needs marketing consent; and `transactional` (service updates, customer-requested replies, account messages). `opt_out_confirmation` is system-only; operators cannot set it.
- Templates carry their purpose: `comeback` and `review_request` are marketing; the others are transactional.
- Free text with no purpose, or any unclear purpose, is **held** (`status=held`, `hold_reason=purpose_unclear`). It is never defaulted to either purpose. A held message cannot be approved, sent, or dispatched until an operator classifies it (`POST /api/messages/{id}/classify`, or the Classify buttons in the Messages tab).
- Classifying resets the message to draft and clears any approval, so it must be re-approved. It is refused for delivered, sending, inbound, and system messages.
- Migration: legacy template rows get their template's purpose. Legacy free-text rows with no purpose that are not yet delivered become `held` / `purpose_unclear`.
- Audit: `classify_message` records actor, role, time, purpose from→to, status from→to, and hold reason from→to. `compose_free_text` records the purpose and any hold.

**Rule 2: a marketing opt-out is not a channel opt-out.**
- Marketing opt-out (`consent_marketing` withdrawn) blocks marketing only. Transactional messages are still allowed.
- Channel opt-out (SMS STOP) is recorded as an event in the new table `channel_opt_outs`. It comes from `POST /api/customers/{id}/channel-opt-out`, or automatically when an inbound message is a STOP keyword (*superseded by 008c:* EN/ES/PT/HT keywords and opt-out phrases, whole-message match). The confirmation text exists in EN/ES/PT/HT. It blocks **everything** on that channel at send and at dispatch, with one exception: an opt-out confirmation.
- Each event drafts one `opt_out_confirmation` message in the customer's language. A human still approves it, as with every outbound message. A partial unique index on `messages(opt_out_event_id)` enforces one confirmation per event in the database. A confirmation for an event that has since been revoked (`/channel-opt-in`) is refused. A new opt-out event gets its own confirmation.
- Opt-outs are per channel. Opt-out records are exported and deleted with the customer.
- **Promo-content guard:** a deterministic keyword check runs over accent-folded, lowercased text: sale, % off, discount, promo, coupon, limited time, buy now, offer, deal, free gift, clearance, plus ES/PT/HT equivalents. It runs at compose, at classify, at translation, at send, and at dispatch, on the original text and the translation. A hit on a transactional or confirmation message holds it (`hold_reason=promotional_content_in_transactional`) and is audited as `message_held_for_review` with the matched words and the stage. Relabelling it transactional again does not release it. Only reclassifying it as marketing (which then requires consent), rewriting it, or, since 008c, an audited human release of a false positive frees it.

**Tests: 153/153 passed (113 prior + 40 new in `tests/test_batch8b.py`: 21 test functions, 2 of them parametrized).** Run 3× consecutively, green each time. `test_batch8b.py` against the previous commit (`3551fa4`) fails at import: `app.services.policy` does not exist there.

Legacy test changes for 008b (minimal; each listed):
- `tests/test_batch3.py::test_content_change_after_approval_invalidates`: the free-text compose now passes `purpose="transactional"`.
- `tests/test_messages.py::test_free_text_other_language_waits_for_translation`: same.
- `tests/test_batch8.py::test_b8_5_free_text_promo_to_non_consenting_never_sends`: now declares `purpose: "marketing"`.
- `tests/test_batch8.py::test_b8_5_declared_transactional_free_text_goes_out_and_bad_purpose_refused`: now asserts only the audited purpose.
- `tests/test_batch8.py::test_b8_5_legacy_free_text_without_purpose_is_treated_as_marketing` is renamed `..._is_held_not_defaulted` and asserts `held`. It encoded the default-to-marketing rule that 008b replaces.

Known limits: keyword matching can false-positive. For example, Spanish "sale" means "leaves" and "deal" can appear in service text. A false positive only holds the message for a human; nothing is sent or deleted. STOP detection is an exact match on the inbound text the operator enters, since no provider is connected. *Superseded by 008c:* deletion now keeps a minimal suppression record.

## Batch 008c: founder corrections (Nov 17, 2:01 PM ET; supersede the 2:00 PM decisions)
Same branch, new commit. Same status: IMPLEMENTED + TESTED (builder-side), NOT MERGED, NOT DEPLOYED. The 2:00 PM "auto-send the confirmation" decision was never implemented or pushed.

**1. Suppression (do-not-message) record kept after deletion: retention policy**
- **Purpose:** keep honouring an opt-out after the customer record is deleted, including when the same person is re-created later.
- **When it is written:** inside the same deletion transaction, before the customer's rows are removed. It is written only if the customer had an active channel opt-out (STOP) or had withdrawn marketing consent. A customer who never opted out leaves nothing. If the deletion fails, the suppression row rolls back with it.
- **Fields (table `suppressions`):**
  - `contact_hmac`: HMAC-SHA256 under a server key, over `phone:<digits>` or `email:<lowercase>`.
  - `contact_type`: phone or email.
  - `channel`: `sms` or `email`, or `all` for marketing.
  - `scope`: `channel` (full opt-out) or `marketing`.
  - `suppressed_at`: when the row was written.
  - **Not stored:** name, customer id, message content or the raw contact.
- **The keyed hash is treated as personal data.** The key comes from `MQ_CRM_SUPPRESSION_KEY`. If that is unset, a random key is generated once at `<db dir>/suppression.key` (mode 0600). A new `.gitignore` keeps the key and the database out of git.
- **Access:** owner-only `GET /api/admin/suppressions`, which never returns the identifier. Staff and viewers get 403; anonymous requests get 401. Suppression rows are not in customer export, `/api/export` or any list view. The deletion audit row records only the count (`suppressions_retained`).
- **Enforcement:** checked at send AND at dispatch for every customer whose normalized phone/email matches. That includes a customer re-created with the same contact, in different formatting, even if consent is ticked at creation. A channel-scope row blocks every purpose on that channel except the opt-out confirmation for a new opt-out event. A marketing-scope row blocks marketing on any channel.
- **How long it is kept:** until an explicit re-opt-in; otherwise indefinitely while the CRM sends messages. A maximum retention period, if any, is a founder/legal decision.
- **How a re-opt-in clears it:** for a channel, `POST /api/customers/{id}/channel-opt-in`; for marketing, `POST /api/customers/{id}/consent` with `granted: true`. Either one, made on a customer holding that contact, deletes the matching rows and audits `suppression_cleared` (ids, scope, channel, actor; never the hash). Creating a customer does not clear anything.
- **Risk:** if the key is lost, the rows can no longer be matched. Back the key up with the database.

**2. STOP in EN/ES/PT/HT: keywords and opt-out phrases. PENDING NATIVE-SPEAKER REVIEW**
- **Matching:** the WHOLE inbound message must equal a listed phrase after normalization: accents folded, lowercased, apostrophes removed, hyphens turned into spaces, surrounding punctuation trimmed, whitespace collapsed. It is never a substring match: "Stop by tomorrow?" and "Cancelar la cita del martes" do not opt out. Matching does not depend on the customer's language: a phrase from any list counts. The response names the matching language(s).
- **Exact lists** (stored in matched form, in `policy.STOP_PHRASES`):
- **English (30):** `stop`, `stopall`, `unsubscribe`, `cancel`, `end`, `quit`, `revoke`, `optout`, `opt out`, `stop texting`, `stop texting me`, `stop messaging me`, `stop sending messages`, `stop sending me messages`, `no more messages`, `no more texts`, `please stop`, `stop please`, `unsubscribe me`, `remove me`, `remove me from your list`, `remove me from the list`, `take me off your list`, `take me off the list`, `do not text me`, `dont text me`, `do not message me`, `dont message me`, `do not contact me`, `dont contact me`
- **Spanish (20):** `parar`, `alto`, `baja`, `cancelar`, `darme de baja`, `dar de baja`, `deme de baja`, `no mas mensajes`, `no mas textos`, `no quiero mas mensajes`, `no me envien mas mensajes`, `no me manden mas mensajes`, `no me escriban mas`, `deja de enviarme mensajes`, `dejen de enviarme mensajes`, `quitenme de la lista`, `sacame de la lista`, `saquenme de la lista`, `eliminenme de la lista`, `cancelar suscripcion`
- **Portuguese (18):** `pare`, `parar`, `sair`, `cancelar`, `descadastrar`, `nao quero mais mensagens`, `nao quero mais receber mensagens`, `nao me envie mais mensagens`, `nao me mande mais mensagens`, `pare de enviar mensagens`, `pare de me enviar mensagens`, `parem de enviar mensagens`, `parem de me enviar mensagens`, `chega de mensagens`, `me tire da lista`, `me tirem da lista`, `quero sair da lista`, `cancelar inscricao`
- **Haitian Creole (14):** `sispann`, `kanpe`, `sispann voye mesaj`, `sispann voye m mesaj`, `sispann ekri m`, `pa voye m mesaj anko`, `pa voye mesaj anko`, `pa voye mwen mesaj anko`, `m pa vle mesaj anko`, `mwen pa vle mesaj anko`, `mwen pa vle resevwa mesaj anko`, `retire m nan lis la`, `retire mwen nan lis la`, `pa ekri m anko`
- **Deliberately not listed (too ambiguous as a whole message):**
  - `para` (ES/PT "for")
  - `basta` (ES "enough")
  - `fin` (ES)
  - `chega` (PT "arrives"/"enough")
  - `rete` (HT "stay")
  - `anile` (HT "cancel", which would catch "cancel my appointment")
  - `no` / `nao` / `non` on their own
- **Kept but flagged for review:**
  - `cancel` / `cancelar`: standard carrier keywords, but a customer may mean an appointment.
  - `alto` (ES, also "tall/high").
  - `baja` (ES, also "low").
  - `end`.

**3. Confirmation stays HUMAN-APPROVED**
- On a valid STOP, the event row is written and blocks the channel at send and dispatch from that commit onward, before anyone approves anything.
- The one confirmation (DB-unique per event) is a draft in the approval queue (`GET /api/opt-out-confirmations`). It needs the normal approve step: anonymous gets 401, viewer gets 403, and the approval is audited.
- Approving, sending or withdrawing (rejecting) it never revokes the opt-out and never creates a second confirmation. A repeated STOP during the same event returns the same event.

**4. The promo list is a screen, not a verdict**
- A hit HOLDS the message (`hold_reason=promotional_content_in_transactional`). It never withdraws or rejects the message and never changes its purpose.
- A human (owner or staff) can release a false positive: `POST /api/messages/{id}/release-hold` with a required reason, or the "Release (not promotional)" button in the UI. The message returns to draft with the same purpose and still needs normal approval.
- The release is audited as `promo_hold_released` (actor, role, time, reason, matched words, content hash). It is bound to that exact content: any later change is screened again.
- The list itself is unchanged and stays a STARTING list pending native-speaker review.

**Tests: 308/308 passed on 3 consecutive runs** (153 prior + 155 new in `tests/test_batch8c.py`: 21 functions, of which 3 are parametrized over every listed phrase (82), 26 case/accent/punctuation variants, and 29 non-matches).
- **No legacy test was changed.**
- **Mutation checks:**
  - Disabling the suppression check fails 2 tests.
  - Switching to substring STOP matching fails 16.
  - Removing the human release fails 2.

## Tests (Batch 008) — 113/113 passed (88 prior + 25 new, `tests/test_batch8.py`)
- Baseline before any change (assembled 001–007): **88 passed**.
- After: **113 passed** (`--ignore=tests/test_batch8.py`: 88 passed). Run 3× consecutively, green each time.
- The 25 new tests were also run against the UNFIXED 001–007 build: **25 failed**, as expected.
- **Legacy test changes, stated plainly** (no assertion line was changed):
  - `tests/conftest.py`: the harness now authenticates every TestClient as an explicit owner (`X-Role: owner`, `X-Actor: test-operator`). Per-request role headers in the old tests still override it.
  - `tests/test_batch5.py::_register_terms` and three setup calls in `tests/test_batch6.py` now bind the register row to the stub endpoint and pass a synthetic `terms_reference`. Those 5 tests encoded the exact behaviour item 7/8 removes (a nameless 'webhook' row with no terms reference authorizing any URL).

## Gates intact
No provider connected · no deployment · no secrets · synthetic data only · $0 spent. PT/HT native review still outstanding.

## Changed / new files (SHA-256, copies under `code/mq-crm-batch008/`, as of the 008c commit)
| File | SHA-256 |
| --- | --- |
| .gitignore | `2c8b6677713b0418c3d3fa7303dc2d867fee9286876b68576527d0832a729480` |
| app/db.py | `f9d49e7c5c31018d29c7d2434e4163a2df2d179252d9bef11bd494fefa1fc7a0` |
| app/gate_lock.py | `33790b81a6548588803f1d3be2560260b2203cbdc074c0f2e71573d4daadd91f` |
| app/main.py | `57fb63bedb717eb7c46592de29973661631f6c68281cd33a0275c8214f8cc1ff` |
| app/services/customers.py | `0bf8120f14bd7cbded1d20048fddbf46614cd790e4fff662691ceed624db99e0` |
| app/services/data_rights.py | `9a46937289b5bc5c398df9f5693849d9a51d8f1f8a85a5bab0880ec8afccd601` |
| app/services/delivery.py | `1933276d87e038df89afad8df9daba01399334032a9efdb7c5b6a64af18924d5` |
| app/services/messages.py | `ffc68f6956c4a68a236d7f0be0d8b5b524d629e336eb302330045f8e6a54d4d1` |
| app/services/policy.py | `f18ac8e7fe4e8cc328e445b7139c632c154df481c194be42e4e564c5153a8515` |
| app/services/register.py | `5f5286a5d5c69de1e71701559f98c20b5dbb4a1e94431b67c8719e7ffba39b87` |
| tests/conftest.py | `6af3276662c1e00c911b72363652c8ce1cb5969d80001bdacd42b1fb45dc712b` |
| tests/test_batch3.py | `4dba627f8ed499bbef4008c9307875e27bf6800dbc4f6a1761a84182b5d41840` |
| tests/test_batch5.py | `fff200a68b0ad61999dc4d9dd1d0501bfa16aca1853ee82cb37f55c7bdb5a539` |
| tests/test_batch6.py | `78481632c6f7f5d0f7ac19bc65174298496cd240d831404fe96633eb33f4ebd6` |
| tests/test_batch8.py | `ec80269831dd6956a95523c975efaa2246b92157b5d0cdec66407368ad5f7f6a` |
| tests/test_batch8b.py | `6892578f5a3b7d36c0ceb250dfada5e84ece0fd2e78b91f5bff21aeb38dab72a` |
| tests/test_batch8c.py | `5f6663ddf6cc07f94614ca18c301f7441d61874fc8d40fecffdac98329fd571a` |
| tests/test_messages.py | `3ae09d17f02bc96d611d4f9bb108a3e6e376ec8bb44864e0aa3553d1207a35c4` |
| web/app.js | `9f20fb0f0ca17774eaaa3e09f22293bb86a56f1685d0330fd05a07b1255d4b0a` |
| web/index.html | `d580f46501b685cb181e20bb82023963d67fa74e56efe89f8c18b23a530e1e7d` |
| web/safe_html.js | `8b4a53f7b1ece2dd4f01d7eed3daca9d0eaaf00c09d16970d93a175389c2c40b` |
| web/styles.css | `e7ea9271b07a25b4d610f854cada94fab7111a8f2aec722a68a306e9b16f4618` |

*KNOWLEDGE IS THE LEGACY.*
