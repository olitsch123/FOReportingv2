# FOReportingv2 – Configuration

Keep **only secrets & local paths** in `.env`; track everything else in Git.

## .env (secrets/paths only, NOT committed)
DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/foreport
OPENAI_API_KEY=sk-...
OPENAI_VECTOR_STORE_ID=vs_...
INVESTOR1_PATH=C:\\Users\\OliverGötz\\Equivia GmbH\\01_BrainWeb Investment GmbH - Dokumente\\09 Funds
INVESTOR2_PATH=C:\\Users\\OliverGötz\\01_pecunalta GmbH - Documents
CHROMA_DIR=./data/chroma/pe_docs

## config/runtime.yaml (tracked)
All non-secrets (vector backend, models, scoring weights, tolerances, etc.).

## Loader
app/config.py merges runtime.yaml + .env and never prints secrets.
