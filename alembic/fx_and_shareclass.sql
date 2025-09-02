-- Additional Alembic SQL (FX + optional shareclass)

-- dim_currency
create table if not exists dim_currency (
  currency_id serial primary key,
  iso_code char(3) unique not null,
  name text
);

-- fx_rate_daily (ccy_from → ccy_to on date d)
create table if not exists fx_rate_daily (
  rate_id bigserial primary key,
  d date not null,
  ccy_from char(3) not null,
  ccy_to char(3) not null,
  rate numeric(18,8) not null,
  unique(d, ccy_from, ccy_to)
);

-- optional: fund share class scope
create table if not exists pe_fund_shareclass (
  shareclass_id uuid primary key,
  fund_id uuid not null,
  code text not null,
  currency char(3),
  terms_json jsonb,
  created_at timestamptz not null default now()
);
create index if not exists idx_shareclass_fund on pe_fund_shareclass(fund_id);
