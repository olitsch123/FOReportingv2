# TIME SERIES & POINT-IN-TIME — FOReportingv2 PE Module

## Why NAV observations?
Monthly `nav_bo/nav_eo` are perfect for a bridge, but you lose fidelity for:
- **as-of** views, restatements, and investor vs fund scopes,
- multiple observation dates in a single period,
- Power BI time intelligence across month/quarter/year with mixed “as-of” semantics.

So we store **NAV observations** as the source of truth and **derive** monthly bridges.

## Core tables
- `pe_nav_observation(fund_id, investor_id?, scope, nav_value, currency, as_of_date, statement_date?, coverage_start?, coverage_end?, period_id, scenario, version_no, restates_nav_obs_id, doc_id, source_trace)`
- `pe_cashflow(fund_id, investor_id, flow_date, flow_type, amount, currency, ...)`
- `dim_date(d)`, `dim_period(period_date)`
- **Optional**: `dim_currency`, `fx_rate_daily` to convert to `REPORTING_CCY` in views.

## Periodization
- `period_id = month_end(as_of_date)` via `dim_period`.
- Monthly bridge view aggregates cashflows in (prev_period_end, period_end] and picks last NAV observation ≤ period_end and ≤ prev_period_end for nav_end/nav_begin.

## Restatements & scenarios
- If a later document restates a NAV, insert a new observation with `version_no = old.version_no + 1` and `restates_nav_obs_id = old.nav_obs_id`.
- Keep `scenario='AS_REPORTED'` vs `scenario='NORMALIZED'` (ex: currency normalization).

## Fund vs Investor scope
- FUND-level observation: `investor_id NULL` and `scope='FUND'`.
- INVESTOR-level observation: explicit `investor_id` and `scope='INVESTOR'`.
- SHARE_CLASS scope can be added via `pe_fund_shareclass` if reports include share-class NAVs.

## Power BI
Relate:
- Facts (nav_observation, cashflow) → `dim_date.d` and → `dim_period.period_date`.
- Bridge view → `dim_period` for month aggregations.
This supports “as of X” dashboards and classic monthly finance statements simultaneously.

## FX
If reporting currency is needed, create a view joining `fx_rate_daily` on (currency, d/as_of_date) to convert NAV and flows to `REPORTING_CCY` without overwriting source values.
