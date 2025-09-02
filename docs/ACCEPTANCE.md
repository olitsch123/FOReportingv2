# FOReportingv2 — PE Module Acceptance (NAV Observations)

**Do not stop** until all checks pass.

1) Drop a bundle into each investor folder:
   - PDFs: Quarterly Report (QR), Capital Account Statement (CAS), Capital Call, Distribution, LPA, PPM, Subscription.
   - XLSX: multi-tabs for Fees/NAV/Holdings.

2) Watcher behavior:
   - Registers files by SHA-256; `ingestion_file.file_hash` is unique.
   - Creates `ingestion_job` (QUEUED → RUNNING → DONE/ERROR).
   - Skips already-processed files (same hash), but processes modified content (new hash).
   - Rescan at boot and hourly (if enabled) registers any missed files.

3) Pipeline per file (SYNC):
   classify → parse → extract → validate → Postgres upserts → Chroma upserts → archive originals.
   - Failures: status=ERROR + detailed logs + move to quarantine.

4) Streamlit shows:
   - “PE — Portfolio”: NAV bridge (from observations + cashflows), flows, unfunded, KPIs (TVPI/DPI/RVPI/IRR), filters & drill-downs.
   - “PE — Documents & RAG”: doc list by type/period/fund, scoped search/chat, **page-level citations**.

5) Idempotency & lineage:
   - Re-running on same files creates no duplicates; facts have `source_trace` with page/bbox/rules.
   - Vector chunks keyed by (doc_id, page_no, chunk_sha).

6) Start commands unchanged:
   - Backend:  `python -m app.main`
   - Frontend: `streamlit run app/frontend/dashboard.py`

7) Backups (recommended):
   - Postgres: nightly `pg_dump` to `./backups/postgres/`.
   - ChromaDB: nightly zip of `./data/chroma/pe_docs/`.
