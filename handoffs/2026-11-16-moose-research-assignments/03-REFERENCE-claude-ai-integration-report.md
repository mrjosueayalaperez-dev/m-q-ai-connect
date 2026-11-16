# M&Q AI INTEGRATION RESEARCH — Parts A–E Deliverable
**Date:** November 16, 2026 · **Prepared by:** Muse (Chief of Staff) · **Status of this document:** RESEARCH REPORT — nothing in it is built, bought, enabled, or deployed. Implementation requires the founder's separate approval.
**Inputs:** (1) Founder's Parts A–E directive, Nov 16, 2026. (2) Zelator's AI integration research, filed verbatim as `ZELATOR-AI-INTEGRATION-RESEARCH-AS-RECEIVED-2026-11-16.md`. (3) Internal inventory — read-only code audit of both applications, `~/workspace/ai-integration-research/INVENTORY.md`, SHA-256 `02a5fa464e8ff00caafded1a43a78ffb302db70f94f1fd4817a0819364224ec0`. (4) External technology/cost research with vendor sources (Nov 2026); prices quoted below are from the vendors' own pricing/documentation pages unless a line says "reported" — those come from secondary readings of official pages and must be re-checked on the live page before any purchase.

**Direction (founder-adopted):** M&Q University becomes an intelligent **teacher**. The Command Center becomes an intelligent **analyst**. One permission-controlled intelligence layer (M&Q AI CONNECT) serves both — the applications are never merged, and private data never crosses between them.

**Cost basis for all figures:** one AI request ≈ 1,500 input + 500 output tokens. Prototype scale = 200 requests/month. Early production = 5,000 requests/month. At these volumes, token cost is nearly irrelevant — the real costs are one fixed fee (Supabase Pro, if needed) and the discipline around grounding and model churn.

---

## E1. Current implementation inventory

### Command Center / Dashboard — an analyst chassis already exists
- **M&Q AI Copilot: IMPLEMENTED, hardened, switched OFF, never live-tested.** Real code (`backend/copilot.py`, read in full during the audit): login-gated streaming chat, per-user sessions, 30-day retention with user delete, per-call usage accounting (provider/model/language/latency/tokens).
- **Two providers wired:** OpenAI through a local litellm shim (allow-list includes the gpt-5.6 family, 5.5, 5.4, 5.4-mini; default gpt-5.4) and xAI Grok (`grok-4.6`). A `ProviderRegistry` dispatches both behind one signature — its own docstring calls it a "shared intelligence layer." It has exactly one consumer today.
- **The teaching brain exists:** bilingual EN/ES method prompts teach **Strategy A — Six Gates** gate-by-gate and **Strategy B — Outer Range Extremes** rule-by-rule, with HOLD vs WAIT definitions, data-label discipline (REAL-TIME / DELAYED / PAPER-SIM-TEST), a fixed five-section answer format, and the futures risk disclaimer appended server-side in both languages.
- **Safety by construction:** an EN+ES execution-request screen refuses order language *before* any provider call. The Copilot has **no execution path at all** — it can only stream text. Legacy `/ai/analyze` was hardened in PR #22 (login-required).
- **Grounding exists:** every chat receives live desk context (position, daily P&L vs the −$100 limit, trades vs the 20 cap, kill switch, active signal, last 5 resolved) labeled PAPER/SIM/TEST.
- **Stage 2 gives an analyst clean data:** persisted fail-closed operator state; journal entries with `origin` (MANUAL/AUTO/ENGINE), `source_alert`, `journal_ok`/`degraded` on every execution; hard ceilings (max 10 contracts, max 400 bracket ticks); the provenance rule `KPI_EXCLUDED_SOURCES` in code (E1: 30 test rows vs 18 genuine, genuine-only **+68.0 pts**).
- **Missing:** no reconciliation engine (detection today = tests + one-off audits); no daily-report generator; no session object in the backend; **0 completed automatic PAPER sessions** (one synthetic demo trade) — Part B items 4/6/7 have almost no real data until the 20-session PAPER block runs.
- **Blockers (founder decisions pending since Nov 14):** no OpenAI key exists; Copilot is OFF on every surface; the target host (Render) is staged, not serving. **Every provider call in every test is mocked — no live round-trip has ever been evidenced.** Real latency, cost per conversation, generated-Spanish quality, and live refusal behavior are **UNKNOWN**.

### M&Q University — no AI, but an ideal grounding corpus
- **Zero LLM, zero backend: VERIFIED.** One static file on GitHub Pages; the page truthfully states it "sends nothing to any server of its own," and its instructor labels itself "not a live AI." The ask-box is a deterministic glossary lookup that refuses honestly when it has no verified answer.
- **The curriculum is a ready-made grounding corpus:** 9 lessons × 4 phases in one structured array — every lesson has intro, key points, example, and quiz, with **full EN/ES parity at the data level**, plus glossary answers that already carry lesson references.
- **Quizzes are fixed banks** with per-question explanations in both languages — no generation, no adaptivity.
- **Voice assets are real:** 160 recorded Helio clips (EN 80 / ES 80), byte-verified; device TTS/STT already wired with fallbacks. The recorded clips can only say what was pre-recorded; device voice is the accepted fallback, not the match.
- **Progress is device-local only** (localStorage): no accounts, nothing leaves the device. Registration is built but **Gate G1 is closed** — the `mq-university` Supabase project exists and is healthy, but nothing is wired to the site; its schema, pgvector availability, and RLS state are **UNKNOWN** from local evidence.
- **Consequence:** any server-side AI changes the University's stated privacy posture ("sends nothing to any server"). That is a **founder policy decision**, not a build detail — and the page's honesty line ("not a live AI") must be rewritten truthfully wherever AI answers appear, labeled as AI-generated.
- **Demand is unmeasured:** the ask-box keeps no logs by design, so its miss rate — the measurable case for semantic search and an AI Professor — is **UNKNOWN**.

### Shared layer — the law already exists, the runtime does not
- **CONNECT blueprint v1.0 (ADOPTED Nov 13, 2026)** already legislates the shape: the shared layer is a **library + registry + workflow patterns, never a central runtime holding project data**; projects call in; the layer never pulls project data; no monolithic cross-project model. The Capability Registry (owner, approved consumers, evidence, maturity ladder, scope-widening = new founder decision) and Integration Registry (what is / is not shared, with verification evidence) are ready-made governance for AI capabilities.
- **Hard boundaries already legislated:** private user information never crosses projects; CONNECT has no autonomous powers (no spending, no database access, no trade execution).
- **Gaps:** no shared runtime or API connects the apps; no embeddings/vector store anywhere; no cross-app identity (Dashboard has per-user JWT; University has no accounts); Langfuse is an **empty** Hobby account whose POC is assigned-but-unrun, under a standing **no-Copilot-connection** rule.
- **Doctrine drift risk (UNKNOWN):** the two strategies exist in three parallel renderings — University lessons, Copilot prompts, Dashboard strategy docs — never compared line-by-line. A shared knowledge layer should designate a single source of truth; today none is designated.

---

## E2. Proposed architecture — M&Q University (the Teacher)

All items **PROPOSED**. Foundation first: a **Lesson Knowledge Layer** — the approved corpus (lessons + glossary, EN + ES) chunked and embedded once into the University's own Supabase project (pgvector), with the corpus source-of-truth kept in exportable form (never only inside a vendor's vector store). Every AI feature below reads from that layer; none reads another student's data.

| Part A item | Design | Builds on |
| --- | --- | --- |
| A5 Semantic lesson search | pgvector similarity search over lesson chunks; results deep-link to lessons (the ask-box already returns lesson references). **No LLM generation** — pure retrieval. | Corpus structure; ask-box lesson-ref pattern |
| A1 AI Professor | Retrieval-grounded Q&A: retrieve top chunks → answer **only** from them → cite the lesson → **refuse when retrieval is weak** ("cite-or-refuse"). Labeled AI-generated. | Knowledge layer; Professor identity + greeting discipline; Copilot's prompt/refusal patterns as template |
| A2 Bilingual assistant | Same pipeline, grounded in the student's selected language (corpus parity makes this day-one); generated ES passes the same eval set as EN before release. | EN/ES corpus parity; Copilot's bilingual prompts |
| A4 Intelligent quizzes | Generation **only** from a completed lesson's chunks, with a deterministic answer-key verification pass before a question is ever shown (a wrong generated key is a correctness risk the fixed banks don't have). Fixed banks remain the default. | Fixed banks + `why` explanations; Quality Center deterministic-case discipline |
| A6 Progress explanations | Phase 1: narrate the student's **own on-device** record (lessons done, quiz bests, rule-adherence) — data leaves the device only inside the student's own question. No accounts required. Cross-device/accounts version waits on the Gate G1 decision. | Existing progress record + rule-based "next step" line |
| A3 Voice interaction | Phase last: record → transcribe → the same text pipeline → spoken answer. Student's choice of recorded Professor clips for fixed utterances stays; generated speech uses a clearly-labeled synthetic voice (an identity decision — it will not be the Professor's recorded voice). | 160 clips; existing device STT/TTS fallbacks |

**Preserved:** curriculum and lesson structure unchanged; Professor identity unchanged; two-door principle (every voice feature keeps a first-class typed twin); accessibility requirements unchanged. **Changed — founder decision required:** the "sends nothing to any server" posture, and only for the features the student actively uses.

## E3. Proposed architecture — Command Center (the Analyst)

All items **PROPOSED** as extensions of the existing Copilot chassis — this is an extension, not a greenfield build. **Hard rule, by construction: the AI is registered with NO write or execution tools.** Deterministic code computes every number; the AI only narrates a typed digest of records, with mandatory record IDs, validated programmatically before display.

| Part B item | Design | Builds on |
| --- | --- | --- |
| B1 AI trading analyst | Activate the Copilot on the migration host (credential + flag decisions) with an analyst persona beside the teaching persona; same ProviderRegistry, same refusal screen. | Copilot (IMPLEMENTED, OFF) |
| B2 Strategy A/B explanations | Feed a specific `evaluate_strategy_a/b` verdict (including its named WAIT reason) into the analyst prompt — the engine already produces structured verdicts with reasons. | `strategy_engine.py` verdicts; method prompts |
| B3 Signal validation explanations | Assemble the validation trace (freshness, alignment, gate results, provenance classification) into the digest the analyst narrates — "why this signal passed/failed gate X." | Signal fields; fail-closed pipeline semantics |
| B5 Risk monitoring explanations | Event hooks narrate *why* a lockout/ceiling/persistence-halt fired, at the moment it fires — the state is already explicit and persisted. | Operator state; ceilings; fail-closed persistence |
| B4 PAPER journal summaries | Session digest (entries/exits/P&L by origin, journal_ok flags) → one structured analyst call per session. **Meaningful only after the 20-session PAPER block produces data.** | Stage 2 journal; `pnl_journal` |
| B6 Reconciliation & discrepancies | **Detection is deterministic code, built first** (signals ↔ executions ↔ journal ↔ Discord, provenance filter applied). The AI explains queued discrepancies; it never detects by impression. | `KPI_EXCLUDED_SOURCES`; E1 method; journal==state design |
| B7 Daily intelligence reports | Scheduled digest → analyst narration → Discord delivery; Batch API pricing (−50% at all three major vendors, reported) fits a once-daily job. Every performance figure passes `KPI_SIGNAL_FILTER` first — never the blended number E1 corrected. | Discord plumbing; five-section format |

**Preserved:** SIM/PAPER/TEST labels on every surface; fail-closed persistence; hard ceilings; human approval for any state change; AI cannot execute trades or modify risk settings — enforced by giving it no tools that can, not by asking it nicely.

## E4. Shared intelligence architecture (through M&Q AI CONNECT)

**PROPOSED**, and deliberately shaped to the adopted blueprint:

1. **One model-access door:** Vercel AI Gateway in front of all providers — zero markup including bring-your-own-key, automatic cross-provider retry and model fallbacks, per-key/project budgets with alerts, no prompt content retained by the Gateway. Model swaps become configuration, not code — the direct defense against the model-churn risk in E6. (Caveats: Gateway budgets are **soft caps** and exclude BYOK spend, so they are paired with the provider's own hard project limit — OpenAI's hard limit returns 429 at the cap, with slight enforcement lag. The Gateway's $5/month free credit is reported from secondary readings; the live page confirms a monthly free credit exists.)
2. **One retrieval system, lessons only:** Supabase pgvector holds the University's knowledge layer. The Command Center does **not** use vectors — its records are structured; deterministic digests beat embeddings there.
3. **Shared assets, not shared data:** the approved corpus, method prompts, and glossaries are packaged as versioned, scope-tagged CONNECT Capability Registry entries (owner, approved consumers, evidence, verification date). Each app consumes them inside its own boundary. Student data and trading data never enter the shared layer.
4. **Governance inherited, not invented:** CONNECT's rules bind the layer — no autonomous powers, scope-widening is a founder decision, every connection documented in the Integration Registry with what is explicitly NOT shared.
5. **Observability:** per-call usage accounting already exists in the Copilot pattern and is replicated University-side. Langfuse remains **disconnected** under the standing rule until the founder rules otherwise; its synthetic-data POC (Moose's lane) informs a later decision.

## E5. The three lowest-cost prototypes

**Prototype 1 — Semantic lesson search (University). PROPOSED.**
pgvector on the existing Supabase project (Free tier, $0) + `text-embedding-3-small` embeddings ($0.02 per 1M tokens, reported from official pricing readings — indexing the whole corpus, ~500k tokens, costs about **$0.01 one time**). No LLM at all. Running cost ≈ **$0/month**. (The free in-database embedder, gte-small, is English-only — disqualified as the sole embedder for a bilingual corpus.) *Proves:* the knowledge layer, real student demand (search logs answer the UNKNOWN miss-rate question), and the G1 wiring — with zero generation risk.

**Prototype 2 — AI Professor grounded Q&A (University). PROPOSED.**
Prototype 1's index + one small model through the Gateway with threshold-gated cite-or-refuse: **gpt-6-luna at $0.10 input / $0.50 output per 1M tokens (OpenAI's pricing page)** ≈ **$0.08/month at 200 requests, $2.00/month at 5,000**. Claude Haiku 5.5 is priced identically ($0.10/$0.50 for prompts ≤100k tokens, Anthropic's page) — a genuine co-equal, swappable through the Gateway. *Faster disposable spike (not the foundation):* OpenAI file_search ≈ $0.58/month at 200 requests (its calls cost $2.50 per 1,000, OpenAI's page; first 1 GB storage free) — but its embeddings are non-exportable, so the corpus must never live only there.

**Prototype 3 — PAPER journal analyst (Command Center). PROPOSED.**
Deterministic MongoDB digest of one session → one structured-output model call (mandatory record IDs) → explanation text. No vector store. Same model economics as Prototype 2 ≈ **$0.08/month at 200 requests**. *Proves:* the analyst pattern on the app's own data, behind the existing login, with the Copilot's refusal screen and accounting reused.

**Fixed-cost reality check:** the largest single line item in the whole program is Supabase Pro at **$25/month** (Supabase pricing page) — needed only if the Free tier's limits bite (500 MB database; projects pause after 1 week idle). Everything else at prototype scale is under a dollar a month. Gemini's free tier is real but its terms say free-tier content is used to improve Google's products (Google's pricing page) — acceptable for the public lesson corpus only, **never** for student progress or trading journals.

## E6. Technical dependencies and risks

**Dependencies (in order of hardness):**
1. **Founder Phase-0 decisions** — provider lead + API credential; activation host (the migration must finish: Atlas user → Render serving); University privacy posture + Gate G1 wiring; spending caps set **before** any key is enabled. Every build sequences behind these.
2. Supabase `mq-university` internals (schema, pgvector, RLS) — **UNKNOWN** until inspected under the G1 decision.
3. The 20-session PAPER block — Part B items 4/6/7 are data-starved until it runs.
4. Zelator's re-review of PR #24 — outstanding for the Dashboard lane.
5. A live provider round-trip — never yet evidenced; it is an acceptance item, not an assumption.

**Risks:**
- **Model churn (VERIFIED pattern, current examples):** gpt-5-mini and gpt-5-nano **shut down December 11, 2026** (reported consistently; do not build on them); a mid-tier Gemini model's price doubles January 1, 2027 (reported); the whisper-1 and tts-1 audio families retire in early 2027 (reported). Even a model's *named replacement* changed mid-November. Mitigation: Gateway routing, no model name hard-coded in product logic, eval re-run on every swap. The Copilot's existing allow-list must be checked against shutdown dates before any activation.
- **Grounding failures:** retrieval miss, the model answering from general knowledge instead of the corpus, invented citations, EN/ES quality asymmetry, and prompt injection inside lesson questions. Mitigation: cite-or-refuse with a retrieval threshold, citations checked programmatically, per-language eval sets. Worst case by construction is a *wrong explanation* — never an action, because the AI holds no write tools.
- **Privacy:** OpenAI API data is not used for training; abuse-monitoring logs may retain prompts/responses up to 30 days, and the Responses API's `store` defaults to 30-day retention — **set `store: false`** (data-controls details reported from secondary readings of OpenAI's official page; re-verify at build time). Credentials live server-side only; the static University page can never hold a key — a small serverless proxy is required there (the Dashboard backend calls directly).
- **Budget enforcement is imperfect at every layer** (Gateway soft caps; OpenAI hard-limit lag) — pair both, and alert at 50%.
- **Doctrine drift** across the three strategy renderings — designate the shared corpus as source of truth during Phase 1, and diff the three renderings as part of that phase.
- **Vendor lock-in:** low if the corpus stays exportable (Supabase) and access stays behind the Gateway; high only if file_search becomes the foundation — it is approved here as a spike, never the base.
- **Self-hosting is not the cheaper door** at this scale (reported: a CPU VPS at $15–80/month generating 2–5 tokens/second loses to API pricing by an order of magnitude); self-hosted embeddings remain a sane escape hatch only.

## E7. Testing and acceptance criteria

Following the Quality Center's on-file discipline (deterministic cases + founder review, dual-record) and the Copilot's existing test patterns:
1. **Grounding eval set:** 50–100 golden questions **per language** with expected lesson chunks — measure retrieval recall@5 separately for EN and ES; a release gate, not a report.
2. **Refusal tests:** ≥20 out-of-corpus questions per language must refuse, in the student's language, without inventing an answer.
3. **Citation precision:** sampled answers' citations must point at chunks that actually support the claim; failures block release.
4. **Safety screens:** execution-request refusals (EN + ES) fire **without** a provider call — the Copilot's existing test pattern, extended to the University assistant (no trading instructions beyond the approved curriculum, ever).
5. **Analyst integrity:** every number in an analyst output must trace to a record ID in its digest; a programmatic check rejects outputs citing absent IDs. Discrepancy *detection* is accepted only on deterministic tests, never on AI judgment.
6. **Live round-trip evidence:** the first activation of any surface requires a recorded live call (latency, tokens, cost) — mocked tests alone never mark anything TESTED again.
7. **Privacy checks:** `store: false` verified; caps and alerts verified by a deliberate small overage test; no key material in any client bundle (static-page proxy inspected).
8. **Founder phone test** on each student/operator surface, per standing practice — device-specific, item by item.
9. **Re-run the full eval set on every model or embedding change** — churn is expected; the eval is the constant.

## E8. Recommended implementation order

Zelator's order (Professor → lesson Q&A → journal intelligence → signal explanations → shared retrieval → voice) and this evidence agree on the destination and on voice last. One reordering is recommended, transparently: **the retrieval layer he lists fifth is the foundation his first two items stand on** — so it is built first, *as* the search feature (Prototype 1), and the Professor follows on the same layer in the next phase. Journal intelligence moves after the PAPER data exists, for the same reason: there is currently almost nothing to summarize.

- **Phase 0 — Founder decisions** (no build): provider lead + credential · activation host (migration completion) · University privacy posture + Gate G1 · spending caps · Langfuse rule stands.
- **Phase 1 — Lesson Knowledge Layer + semantic search** (Prototype 1). Includes the three-rendering doctrine diff and designating the source of truth.
- **Phase 2 — AI Professor grounded Q&A** (Prototype 2), EN/ES eval-gated, labeled AI-generated. Quiz generation (A4) and progress explanations (A6, on-device data) follow inside this phase.
- **Phase 3 — Command Center analyst activation** (Prototype 3 + B1/B2/B3/B5): Copilot live on the migration host, verdict-fed explanations, risk-event narration. First live round-trip evidence in the ecosystem's history.
- **Phase 4 — Reconciliation engine (deterministic) → AI explanations + daily reports** (B6/B7), sequenced after the 20-session PAPER block.
- **Phase 5 — Voice** (A3 + Command Center voice queries), after the audio-model churn settles and with the Professor voice-identity decision made explicitly.

**The single decision asked of the founder:** approve this research direction and implementation order (Phases 0–5) so that a Phase 1 build proposal — scope, branch plan, and acceptance tests — can be drafted for separate approval. This report authorizes nothing by itself: no purchase, no key, no merge, no deploy.

*KNOWLEDGE IS THE LEGACY.*
