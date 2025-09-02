# FOReportingv2 — AI Rules & Field Library (NAV observations + dual vector backend)

This repo uses a **Field Library** (YAML/CSV) for multilingual, low-error extraction from CSV/XLSX/PDF.
It defines canonical fields, synonyms, regex patterns, anchors by doc_type, validation equations, and units/locales.
Extractors load these configs at runtime; originals (Field Library.xlsx, Canoe PDF) are only used to seed the YAML/CSV.

## Vector store backends
- **ChromaDB (default)**: local, persisted at CHROMA_DIR. No OpenAI vector store ID required.
- **OpenAI Vector Store (optional)**: set `VECTOR_BACKEND=openai` and provide `OPENAI_VECTOR_STORE_ID`.
  Metadata keys must include `{doc_id, doc_type, fund_id, investor_id, period_end, page_no}` for consistent retrieval & citations.

## NAV observations (point-in-time)
- Store **as_of_date**, optionally **statement_date**, **coverage_start/end** in `pe_nav_observation`.
- Link to `dim_period` for month-end. Keep **AS_REPORTED** vs **NORMALIZED** via a `scenario` column or views.
- Restatements: `version_no`, `restates_nav_obs_id`.

## Monthly bridge
- Kept as a view/materialized table over **observations + cashflows** (nav_begin, contributions, distributions, fees, pnl, nav_end).
- This powers finance dashboards, while Power BI can use observations for “as-of” analytics.

## Field Library bundle (`app/pe_docs/mapping/`)
- field_library.yaml   — canonical fields; synonyms (EN/DE…); patterns; anchors by doc_type; scoring weights; thresholds; tolerances.
- column_map.csv       — CSV/XLSX header aliases → canonical fields.
- regex_bank.yaml      — dates, currency symbols, parentheses negatives, unit multipliers.
- phrase_bank.yaml     — multilingual anchors (e.g., NAV reconciliation; Capital Account Statement).
- validation_rules.yaml — CAS equation; NAV bridge; fee plausibility; QR↔CAS; continuity.
- units.yaml           — currency symbols, multipliers (k/m), decimal conventions per locale.

## Resolver
Signals (weights from YAML): **alias**, **synonym**, **regex**, **embedding similarity**, **context**.  
Returns `(canonical_field, value, confidence, evidence[])`; applies locale & units.

## PDF strategy
- Table-first extraction (Camelot/Tabula) with **bbox**; anchor-based neighborhoods for context.
- Parentheses negatives; unit scaling (k/m); language-aware decimal rules.
- LLM structured extraction fallback with strict JSON schema (canonical fields only); cross-check rules; mark `needs_review` if inconsistent.

## Validation
- CAS equation: `|ending − (opening + pic − dist − fees + pnl)| ≤ tolerance`.
- QR↔CAS flows per period equal; Unfunded = Commitment − cum PIC + Recallable.
- Fee plausibility (base × rate ≈ reported); NAV continuity.
- KPIs: TVPI/DPI/RVPI; IRR/XIRR if dates complete; label reported vs computed.

## Provenance
All rows include `source_trace` with `{file_id, job_id, doc_id, page, table_bbox, step, rule_ids_used, candidates}`.
Originals are archived; quarantined files carry reasons. Idempotent upserts prevent duplicates.

## Environment (excerpt)
OPENAI_API_KEY=…
DATABASE_URL=postgresql+psycopg2://…
VECTOR_BACKEND=chroma | openai
CHROMA_DIR=./data/chroma/pe_docs
OPENAI_VECTOR_STORE_ID=vs_...         # only if VECTOR_BACKEND=openai
INVESTOR1_PATH=…
INVESTOR2_PATH=…
PE_SYNC_MODE=true
PE_RESYNC_ON_START=true
PE_RESCAN_CRON="0 * * * *"
PE_RETRY_MAX=5
PE_RETRY_BACKOFF=2.0
REPORTING_CCY=EUR
