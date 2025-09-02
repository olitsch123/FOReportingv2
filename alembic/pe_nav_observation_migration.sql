-- Alembic SQL skeleton for FOReportingv2 (PE NAV observations + time tables)

-- 1) dim_date (daily)
create table if not exists dim_date (
  date_id serial primary key,
  d date not null unique,
  year int not null, month int not null, day int not null,
  quarter int not null, week int not null
);

-- 2) dim_period (month-end)
create table if not exists dim_period (
  period_id serial primary key,
  period_date date not null unique,
  month smallint not null check (month between 1 and 12),
  quarter smallint not null check (quarter between 1 and 4),
  year int not null
);

-- 3) pe_nav_observation (source-of-truth NAV)
create table if not exists pe_nav_observation (
  nav_obs_id bigserial primary key,
  fund_id uuid not null,
  investor_id uuid,
  scope varchar(24) not null default 'FUND', -- FUND | INVESTOR | SHARE_CLASS
  nav_value numeric(24,8) not null,
  currency varchar(3) not null,
  as_of_date date not null,
  statement_date date,
  coverage_start date,
  coverage_end date,
  period_id int references dim_period(period_id),
  scenario varchar(16) not null default 'AS_REPORTED',
  is_reported boolean not null default true,
  version_no int not null default 1,
  restates_nav_obs_id bigint references pe_nav_observation(nav_obs_id),
  doc_id uuid,
  source_trace jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_navobs_fi_date on pe_nav_observation(fund_id, investor_id, as_of_date);
create index if not exists idx_navobs_period on pe_nav_observation(fund_id, investor_id, period_id);

-- 4) (example) monthly bridge view (derive from observations + cashflows)
-- Replace schema/table names if needed; build in ORM as well.
/*
create or replace view v_pe_nav_bridge_monthly as
select
  f.fund_id,
  n.investor_id,
  p.period_id,
  -- NAV BO, flows, NAV EO computed from subqueries over pe_nav_observation and pe_cashflow
  ...
from (select distinct fund_id from pe_nav_observation) f
cross join (select distinct investor_id from pe_cashflow) n
join dim_period p on true;
*/
