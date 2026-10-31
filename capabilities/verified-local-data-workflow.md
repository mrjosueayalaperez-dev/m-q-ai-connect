# Capability: Verified Local-Data Workflow

- **Registry ID:** C-LDW-001
- **Version:** 1.0
- **Registered:** October 31, 2026 (M&Q AI CONNECT founding registration)
- **Proven in:** Community Bridge (first use — data verified October 23, 2026; launched October 30, 2026)
- **Scope:** Any M&Q project that publishes local, real-world service information (food, housing, health, legal aid, community resources). The **pattern** is shared. The **data** never is — each project collects, verifies, and owns its own dataset under its own boundaries.

## Purpose

Give any project a trustworthy way to answer "where can I actually get help near me?" with real places — a name, a physical address, and directions — instead of plausible-sounding inventions. The workflow exists because local-service information on the open web is stale, conflicting, and sometimes wrong; sending a person in need to a closed pantry or a wrong address is a harm, not a bug.

## The workflow

### 1. Collect from authoritative sources only
- The organization's **own official pages** outrank everything.
- Next: official guides and registries (e.g., 211 reference guides, school-district community resource lists, state corporate filings).
- Aggregator directories are used only where they **agree** with an authoritative source — never as the sole authority, and never where they conflict with the organization's own current page.
- An older guide (however official) is treated as a lead, not as truth: its facts require agreement from a more recent source.

### 2. Verify every field that ships
- An entry ships only with **name + physical address + a fetched source**.
- Phone and hours appear only where a source states them.
- Anything time-sensitive (hours, schedules) requires the strongest available source; the organization's own current page governs over directories.

### 3. Hedge conflicts — never guess
- When sources agree on the days but conflict on the hours, ship the agreed part and mark the rest **"call to confirm."**
- When an organization's status is contested (e.g., a closure flag on an aggregator vs. the organization's own current announcements), ship the entry **with the conflict disclosed on the card itself**, or exclude it — never silently pick the convenient version.
- Every conflict, its sources, and its treatment are written into the project's provenance record.

### 4. Exclude what cannot be verified — and document the exclusions
- Out-of-area, conflicting, stale, or mislabeled candidates are **excluded, not guessed into place**.
- The exclusion list, with the reason for each exclusion, is part of the deliverable. An honest "we could not verify this" protects the people the product serves.

### 5. Date-stamp everything
- Every shipped entry carries its verification date (**"Verified YYYY-MM-DD"**), shown in the product itself.
- The provenance record keeps, per entry: sources fetched, what each source stated, conflicts found, and the treatment chosen.

### 6. Publish with provenance, and keep a pull rule
- The dataset ships together with its provenance record — anyone reviewing the product can answer *"show me the exact boundary and the evidence it was respected."*
- **Re-verification triggers:** if the organization's own channels go silent, a closure is confirmed, or a fresher authoritative source contradicts a shipped fact, the entry is corrected on re-check or pulled to UNVERIFIED — EXCLUDED.
- A phone-only answer fails the standard: the person must be able to **go there** — address and directions are part of the answer.

## Boundary (what this capability does and does not share)

- **Shared:** this procedure, its standards, and its lessons — the know-how.
- **Never shared:** any project's actual dataset, listings, or provenance records. Those belong to the project that collected them and stay inside that project's boundary.
- A second project adopting this capability starts its **own** collection for its **own** area and audience. It inherits the standard, not the data.

## Evidence of first use — Community Bridge

- Dataset: **9 verified food-resource entries** shipped (Fellsmere / Sebastian / Vero Beach, FL), every one with name, street address, and fetched authoritative sources; **7 candidates documented as UNVERIFIED — EXCLUDED**, each with its reason.
- All shipped entries carry the stamp **"Verified 2026-10-23."**
- Conflicts handled under Step 3 in production: contested hours hedged as "call to confirm"; one organization's disputed open/closed status disclosed on its card with a call-first note; a 2017 guide's stale phone and hours identified and **not** shipped.
- Product verification: 82/82 build checks passed; release audit passed; launched October 30, 2026; founder phone test passed in English and Spanish ("fully operating") — typed and voice questions returned real local places with street addresses, directions, and tap-to-call.
- Live product: https://mrjosueayalaperez-dev.github.io/Community-Bridge-/

## Versioning

Changes to this workflow are versioned here, tagged with approval date and scope, and reviewed by the founder before they become the standard — the same rule the blueprint sets for every capability in the library.
