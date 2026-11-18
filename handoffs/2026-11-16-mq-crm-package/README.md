# Meeting Point — M&Q CRM Work Package for Moose (delivered Nov 16, 2026)

This folder, on branch `handoff/moose-crm-package-2026-11-16` of the M&Q AI CONNECT repo, is the standing delivery point between Muse (Chief of Staff) and Moose (Chief Technology & Development). Packages land here as dated folders; the founder no longer carries files by hand.

## Contents of this package

| File | What it is | SHA-256 |
|---|---|---|
| `00-RELAY-MESSAGE.md` | The founder's relay instructions — read first | `2e0c1f4ae28ed9d3e75ef45dfeeec6986b08d084fcd238a4baff2f61774766dd` |
| `01-relay-packet.md` | CRM next-stage packet: directive, annex, Addenda 2–4 | `d9ddebd5d5b884aad6db2ecf8c0d445c95299bd13a5223990344f942f227ae65` |
| `02-evidence-register-v1.md` | Master Evidence Register v1 — the frozen comparison baseline | `6bd0cf99fc0ec64612212c4272f4e9ee6bc6d25e6d267d22013e739166860679` |
| `03-langchain-langfuse-poc-brief.md` | Workstream B brief: LangChain/Langfuse evaluation + synthetic-data POC | `beec836724f465d5f04651a084d27924c5025627d140a52a8fa4997536342d20` |

## Protocol

1. **Pull** this branch and folder.
2. **Verify** every file's SHA-256 yourself against the table above — Muse's hashes do not substitute for yours.
3. **Acknowledge** by adding `ACK.md` in this folder: receipt of all files, your verified hashes, and any missing, mismatched, or unreadable material. Nothing is marked received until `ACK.md` exists.
4. **Work** per the relay message. Batch reports go in a `reports/` subfolder here, workstreams reported separately, each batch stating: inspected · changed · why · files affected · tests run and actual results · remaining limitations · implemented / tested / deployed status.
5. **Delivered files are never edited after delivery.** Corrections and updates arrive as new files — the addenda discipline. Register v1 is frozen.

## Security (permanent)

No database identifiers or credentials ever appear in this repo, in chats, or in reports. `MONGO_URL` is a private credential; `DB_NAME` is private operational configuration. Langfuse keys pass founder → Moose directly, never through Git. Synthetic data only in the POC.

## Status

**PREPARED by Muse — Nov 16, 2026 · AWAITING MOOSE ACKNOWLEDGMENT** (receipt + his independent fingerprint verification, per step 3).

*Knowledge Is The Legacy. Technology + People = Access.*
