# PE Fund Document Processing Implementation Plan

## Executive Summary

Based on competitor analysis (Canoe, Cobalt LP, PitchBook), we need to build a production-grade system that:
1. **Extracts** all critical financial data points with near-zero error rate
2. **Validates** extracted data through multiple cross-checks
3. **Stores** time-series data for accurate portfolio tracking
4. **Enables** intelligent chat and forecasting capabilities

## Critical Data Points Identified

### 1. Fund Master Data
```yaml
pe_fund:
  - fund_name: "Astorg VII"
  - fund_id: "AST-VII-2020"
  - fund_manager: "Astorg Partners"
  - vintage_year: 2020
  - fund_size: 10000000000  # €10B
  - currency: "EUR"
  - fund_type: "Buyout"
  - investment_strategy: "Mid-market buyout"
  - legal_structure: "SCSp"
  - domicile: "Luxembourg"
```

### 2. Investor/LP Information
```yaml
pe_investor:
  - investor_name: "BrainWeb Investment GmbH"
  - investor_id: "BWI-001"
  - investor_type: "Family Office"
  
pe_commitment:
  - commitment_amount: 50000000  # €50M
  - commitment_date: "2020-06-15"
  - share_class: "Class A"
  - management_fee_pct: 2.0
  - carried_interest_pct: 20.0
  - preferred_return: 8.0
```

### 3. Capital Account Time Series (Most Critical)
```yaml
pe_capital_account:
  - as_of_date: "2023-12-31"
  - period: "Q4 2023"
  - beginning_balance: 35000000
  - contributions: 5000000
  - distributions_roc: 2000000  # Return of Capital
  - distributions_gain: 1500000  # Realized Gains
  - distributions_income: 100000
  - management_fees: 250000
  - partnership_expenses: 50000
  - realized_gain_loss: 1500000
  - unrealized_gain_loss: 3000000
  - ending_balance_nav: 40700000
  - unfunded_commitment: 15000000
  - recallable_distributions: 2000000
```

### 4. Performance Metrics
```yaml
pe_performance:
  - as_of_date: "2023-12-31"
  - irr_gross: 0.185  # 18.5%
  - irr_net: 0.145   # 14.5%
  - moic_gross: 1.85
  - moic_net: 1.65
  - tvpi: 1.65
  - dpi: 0.35
  - rvpi: 1.30
  - quartile_rank: 1  # Top quartile
```

### 5. Transaction Records
```yaml
pe_cashflow:
  - transaction_id: "CALL-2024-001"
  - fund_id: "AST-VII-2020"
  - investor_id: "BWI-001"
  - flow_type: "CALL"
  - amount: 5000000
  - due_date: "2024-02-15"
  - payment_date: "2024-02-14"
  - purpose: "Portfolio Investment - TechCo Acquisition"
  - call_number: 12
  - percentage_of_commitment: 10.0
```

## Implementation Steps

### Phase 1: Enhanced Database Schema (Week 1)

1. **Update Alembic Migrations**
```sql
-- New tables needed
CREATE TABLE pe_fund_master (
    fund_id UUID PRIMARY KEY,
    fund_code VARCHAR(50) UNIQUE NOT NULL,
    fund_name VARCHAR(255) NOT NULL,
    fund_manager VARCHAR(255),
    vintage_year INTEGER,
    fund_size DECIMAL(20,2),
    target_size DECIMAL(20,2),
    currency VARCHAR(3),
    fund_type VARCHAR(50),
    investment_strategy TEXT,
    legal_structure VARCHAR(100),
    domicile VARCHAR(100),
    inception_date DATE,
    final_close_date DATE,
    term_years INTEGER,
    extension_years INTEGER,
    management_company VARCHAR(255),
    general_partner VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE pe_share_class (
    class_id UUID PRIMARY KEY,
    fund_id UUID REFERENCES pe_fund_master,
    class_code VARCHAR(20),
    class_name VARCHAR(100),
    currency VARCHAR(3),
    management_fee_pct DECIMAL(5,2),
    carried_interest_pct DECIMAL(5,2),
    preferred_return_pct DECIMAL(5,2),
    fee_terms JSON
);

CREATE TABLE pe_capital_account (
    account_id UUID PRIMARY KEY,
    fund_id UUID REFERENCES pe_fund_master,
    investor_id UUID REFERENCES pe_investor,
    as_of_date DATE NOT NULL,
    period_type VARCHAR(20), -- 'QUARTERLY', 'ANNUAL', 'MONTHLY'
    period_label VARCHAR(20), -- 'Q4 2023', 'FY 2023'
    
    -- Balances
    beginning_balance DECIMAL(20,2),
    ending_balance DECIMAL(20,2),
    
    -- Activity
    contributions DECIMAL(20,2),
    distributions_total DECIMAL(20,2),
    distributions_roc DECIMAL(20,2),
    distributions_gain DECIMAL(20,2),
    distributions_income DECIMAL(20,2),
    distributions_tax DECIMAL(20,2),
    
    -- Fees & Expenses
    management_fees DECIMAL(20,2),
    partnership_expenses DECIMAL(20,2),
    organizational_expenses DECIMAL(20,2),
    
    -- Gains/Losses
    realized_gain_loss DECIMAL(20,2),
    unrealized_gain_loss DECIMAL(20,2),
    
    -- Commitments
    total_commitment DECIMAL(20,2),
    drawn_commitment DECIMAL(20,2),
    unfunded_commitment DECIMAL(20,2),
    recallable_distributions DECIMAL(20,2),
    
    -- Share info
    ownership_pct DECIMAL(10,6),
    shares_owned DECIMAL(20,6),
    
    -- Metadata
    source_doc_id UUID,
    extraction_confidence DECIMAL(3,2),
    validated BOOLEAN DEFAULT FALSE,
    validation_notes TEXT,
    
    UNIQUE(fund_id, investor_id, as_of_date)
);

-- Add indexes for time-series queries
CREATE INDEX idx_capital_account_time ON pe_capital_account(fund_id, investor_id, as_of_date);
CREATE INDEX idx_capital_account_period ON pe_capital_account(fund_id, period_type, as_of_date);
```

### Phase 2: Enhanced Extraction Logic (Week 2)

1. **Multi-Pattern Extraction**
```python
class EnhancedPEExtractor:
    def extract_capital_account_fields(self, text, tables):
        """Extract with multiple validation methods."""
        
        # Method 1: Table extraction
        table_data = self.extract_from_tables(tables)
        
        # Method 2: Regex patterns
        regex_data = self.extract_with_regex(text)
        
        # Method 3: LLM extraction
        llm_data = self.extract_with_llm(text)
        
        # Method 4: Positional extraction (for PDFs)
        position_data = self.extract_by_position(text)
        
        # Reconcile and validate
        final_data = self.reconcile_extractions([
            table_data, regex_data, llm_data, position_data
        ])
        
        return final_data
```

2. **Field-Specific Extractors**
```python
# Each field type has specialized extraction
extractors = {
    'nav': NAVExtractor(),           # Handles NAV/ending balance
    'irr': IRRExtractor(),           # Handles IRR formats (%, basis points)
    'date': DateExtractor(),         # Handles various date formats
    'currency': CurrencyExtractor(), # Handles amounts with currency
    'percentage': PercentageExtractor()
}
```

### Phase 3: Multi-Level Validation (Week 3)

1. **Document-Level Validation**
```python
class DocumentValidator:
    def validate_capital_account(self, data):
        errors = []
        
        # 1. Balance equation check
        calculated_ending = (
            data['beginning_balance'] + 
            data['contributions'] - 
            data['distributions_total'] - 
            data['fees'] + 
            data['realized_gain_loss'] + 
            data['unrealized_gain_loss']
        )
        
        if abs(calculated_ending - data['ending_balance']) > 0.01:
            errors.append(f"Balance mismatch: {calculated_ending} != {data['ending_balance']}")
        
        # 2. Commitment check
        if data['drawn_commitment'] + data['unfunded_commitment'] != data['total_commitment']:
            errors.append("Commitment calculation error")
        
        # 3. Distribution breakdown
        dist_sum = sum([
            data.get('distributions_roc', 0),
            data.get('distributions_gain', 0),
            data.get('distributions_income', 0),
            data.get('distributions_tax', 0)
        ])
        
        if abs(dist_sum - data['distributions_total']) > 0.01:
            errors.append("Distribution breakdown mismatch")
        
        return errors
```

2. **Cross-Document Validation**
```python
class CrossDocumentValidator:
    def validate_continuity(self, current, previous):
        """Validate time-series continuity."""
        errors = []
        
        # Ending balance of previous period should match beginning of current
        if previous['ending_balance'] != current['beginning_balance']:
            errors.append(
                f"Balance continuity break: {previous['ending_balance']} != {current['beginning_balance']}"
            )
        
        # Unfunded commitment should decrease or stay same (unless recommitment)
        if current['unfunded_commitment'] > previous['unfunded_commitment']:
            if not current.get('has_recommitment'):
                errors.append("Unexpected increase in unfunded commitment")
        
        return errors
```

3. **Performance Metrics Validation**
```python
class PerformanceValidator:
    def validate_metrics(self, data):
        errors = []
        
        # TVPI = DPI + RVPI
        calculated_tvpi = data['dpi'] + data['rvpi']
        if abs(calculated_tvpi - data['tvpi']) > 0.01:
            errors.append(f"TVPI mismatch: {data['tvpi']} != {data['dpi']} + {data['rvpi']}")
        
        # MOIC reasonableness
        if data['moic'] < 0 or data['moic'] > 10:
            errors.append(f"MOIC out of reasonable range: {data['moic']}")
        
        # IRR reasonableness
        if data['irr'] < -1 or data['irr'] > 2:  # -100% to 200%
            errors.append(f"IRR out of reasonable range: {data['irr']}")
        
        return errors
```

### Phase 4: Reconciliation Agent (Week 4)

1. **Automated Reconciliation**
```python
class ReconciliationAgent:
    def __init__(self):
        self.validators = {
            'capital_account': CapitalAccountValidator(),
            'performance': PerformanceValidator(),
            'cashflow': CashflowValidator()
        }
    
    async def reconcile_document(self, doc_id):
        """Run all reconciliation checks."""
        doc = await self.get_document(doc_id)
        extracted_data = doc.extracted_data
        
        # Recalculate all metrics
        recalculated = self.recalculate_metrics(extracted_data)
        
        # Compare and flag differences
        differences = self.compare_data(extracted_data, recalculated)
        
        # Create reconciliation report
        report = {
            'doc_id': doc_id,
            'timestamp': datetime.utcnow(),
            'differences': differences,
            'confidence': self.calculate_confidence(differences),
            'requires_review': len(differences) > 0
        }
        
        # Store reconciliation results
        await self.store_reconciliation(report)
        
        # Alert if significant differences
        if report['requires_review']:
            await self.send_alert(report)
        
        return report
```

2. **KPI Recalculation Engine**
```python
class KPIRecalculator:
    def recalculate_irr(self, cashflows):
        """Recalculate IRR from cashflow data."""
        # Use numpy or scipy for IRR calculation
        dates = [cf['date'] for cf in cashflows]
        amounts = [cf['amount'] for cf in cashflows]
        
        # Add current NAV as final cashflow
        dates.append(datetime.now())
        amounts.append(-self.current_nav)
        
        irr = npf.irr(amounts)
        return irr
    
    def recalculate_moic(self, capital_account):
        """Recalculate MOIC from capital account."""
        total_contributed = capital_account['contributions_total']
        total_distributed = capital_account['distributions_total']
        current_nav = capital_account['ending_balance']
        
        moic = (total_distributed + current_nav) / total_contributed
        return moic
```

### Phase 5: Enhanced PE API Endpoints (Week 5)

1. **Time-Series Endpoints**
```python
@router.get("/pe/capital-account-series")
async def get_capital_account_series(
    fund_id: str,
    investor_id: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    frequency: str = "quarterly"  # quarterly, monthly, annual
):
    """Get capital account time series with interpolation."""
    
    # Get raw data points
    data_points = await get_capital_account_data(
        fund_id, investor_id, start_date, end_date
    )
    
    # Fill missing periods with interpolation
    complete_series = interpolate_time_series(
        data_points, frequency, start_date, end_date
    )
    
    # Calculate period-over-period changes
    enriched_series = calculate_changes(complete_series)
    
    return enriched_series
```

2. **Forecasting Endpoint**
```python
@router.post("/pe/forecast")
async def create_forecast(
    fund_id: str,
    scenario: str = "base",  # base, conservative, aggressive
    years_forward: int = 5
):
    """Create NAV and cashflow forecast."""
    
    # Get historical data
    historical = await get_historical_performance(fund_id)
    
    # Apply forecasting model
    forecast = PEForecastModel(
        historical_irr=historical['irr'],
        historical_pace=historical['contribution_pace'],
        j_curve_stage=historical['j_curve_stage']
    )
    
    projections = forecast.project(
        scenario=scenario,
        years=years_forward
    )
    
    return projections
```

### Phase 6: Intelligent Chat Enhancement (Week 6)

1. **Context-Aware RAG**
```python
class PEChatEnhancement:
    def build_context(self, query, investor_id):
        """Build rich context for chat."""
        
        # Get latest capital account
        latest_ca = self.get_latest_capital_account(investor_id)
        
        # Get recent transactions
        recent_txns = self.get_recent_transactions(investor_id, days=90)
        
        # Get performance trends
        performance = self.get_performance_summary(investor_id)
        
        # Build context prompt
        context = f"""
        Current Portfolio Status for {investor_id}:
        - Total NAV: €{latest_ca['total_nav']:,.0f}
        - Unfunded Commitments: €{latest_ca['unfunded']:,.0f}
        - YTD Net IRR: {performance['ytd_irr']:.1%}
        - Recent Activity: {len(recent_txns)} transactions
        
        Latest Holdings:
        {self.format_holdings(latest_ca['holdings'])}
        """
        
        return context
```

## Quality Assurance Strategy

### 1. Confidence Scoring
```python
confidence_factors = {
    'extraction_method': {
        'table': 0.9,
        'regex': 0.8,
        'llm': 0.7,
        'ocr': 0.5
    },
    'validation_passed': {
        'all': 1.0,
        'most': 0.8,
        'some': 0.6,
        'none': 0.3
    },
    'cross_reference': {
        'matched': 0.95,
        'close': 0.7,
        'mismatch': 0.3
    }
}
```

### 2. Manual Review Queue
- Documents with confidence < 0.8
- Balance mismatches > €1000
- Missing critical fields
- Unusual patterns detected

### 3. Audit Trail
```yaml
extraction_audit:
  - doc_id: "xxx"
  - field: "ending_balance"
  - extracted_value: 40700000
  - extraction_method: "table"
  - confidence: 0.95
  - validation_status: "passed"
  - manual_override: null
  - reviewer: null
  - timestamp: "2024-01-15T10:30:00Z"
```

## Performance Requirements

1. **Accuracy**: 99.9% for critical financial fields
2. **Processing Time**: < 30 seconds per document
3. **Validation Time**: < 5 seconds per document
4. **Query Response**: < 2 seconds for time-series data
5. **Chat Response**: < 3 seconds with full context

## Risk Mitigation

1. **Never Overwrite Data**: Always version, never update in place
2. **Require Dual Validation**: Both automated and manual for large amounts
3. **Maintain Audit Trail**: Every extraction, validation, and change logged
4. **Implement Rollback**: Ability to revert to previous versions
5. **Alert on Anomalies**: Immediate notification for unusual patterns

## Success Metrics

1. **Data Quality Score**: > 99% accuracy on test set
2. **User Adoption**: 100% of documents processed through system
3. **Time Savings**: 90% reduction in manual data entry
4. **Error Detection**: Catch 100% of balance mismatches
5. **Insights Generated**: Daily automated portfolio analytics