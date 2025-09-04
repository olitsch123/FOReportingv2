# FOReporting v2 Gap Analysis

## Current State vs. Required State

### ✅ What We Have

1. **Basic Infrastructure**
   - FastAPI backend with error handling
   - PostgreSQL database with Alembic
   - Docker setup for deployment
   - Vector store integration (Chroma/OpenAI)
   - File watcher for document ingestion

2. **Document Processing**
   - PDF, Excel, CSV processors
   - AI-powered classification
   - Basic text extraction
   - Embedding generation

3. **PE Module Structure**
   - Field library configuration
   - Basic classifiers
   - PDF parser with table extraction
   - Validation framework
   - Storage interfaces

### ❌ Critical Gaps to Address

#### 1. **Database Schema Gaps**
- Missing tables:
  - `pe_fund_master` (comprehensive fund information)
  - `pe_share_class` (share class details)
  - `pe_capital_account` (time-series capital data)
  - `pe_portfolio_company` (holdings information)
  - `pe_benchmark` (benchmark data)
  - `extraction_audit` (audit trail)
  - `reconciliation_log` (reconciliation results)

#### 2. **Extraction Accuracy Gaps**
- No multi-method extraction reconciliation
- Missing specialized extractors for:
  - Complex table structures (nested tables)
  - Multi-currency handling
  - Percentage vs. basis points disambiguation
  - Date format normalization
- No confidence scoring system
- No extraction audit trail

#### 3. **Validation Gaps**
- Missing cross-document validation
- No time-series continuity checks
- No automated reconciliation
- Missing KPI recalculation engine
- No anomaly detection

#### 4. **Data Model Gaps**
- Incomplete capital account structure
- Missing performance attribution
- No fee calculation engine
- Limited transaction categorization
- No benchmark comparison

#### 5. **API Endpoint Gaps**
- No time-series aggregation endpoints
- Missing forecasting capabilities
- No portfolio analytics endpoints
- Limited export capabilities
- No reconciliation status endpoints

## Implementation Priorities

### Priority 1: Data Model Enhancement (Week 1)
```sql
-- Critical new tables needed
CREATE TABLE pe_fund_master (
    -- Complete fund information
);

CREATE TABLE pe_capital_account (
    -- Time-series capital data with all fields from competitors
);

CREATE TABLE extraction_audit (
    -- Track every extraction with confidence
);
```

### Priority 2: Extraction Engine Upgrade (Week 2)

1. **Multi-Method Extraction**
```python
class MultiMethodExtractor:
    """Extract using multiple methods and reconcile."""
    
    def extract_field(self, doc, field_name):
        results = []
        
        # Method 1: Table extraction
        if tables := self.extract_from_tables(doc, field_name):
            results.append({
                'method': 'table',
                'value': tables,
                'confidence': 0.9
            })
        
        # Method 2: Regex patterns
        if regex := self.extract_with_regex(doc, field_name):
            results.append({
                'method': 'regex',
                'value': regex,
                'confidence': 0.8
            })
        
        # Method 3: LLM extraction
        if llm := self.extract_with_llm(doc, field_name):
            results.append({
                'method': 'llm',
                'value': llm,
                'confidence': 0.7
            })
        
        # Reconcile results
        final_value = self.reconcile_results(results)
        
        # Audit trail
        self.log_extraction(field_name, results, final_value)
        
        return final_value
```

2. **Field-Specific Extractors**
```python
# NAV/Balance extractor
class NAVExtractor(BaseExtractor):
    def extract(self, text, context):
        patterns = [
            r'ending\s+balance[\s:]+[$€£]?([\d,]+\.?\d*)',
            r'nav[\s:]+[$€£]?([\d,]+\.?\d*)',
            r'net\s+asset\s+value[\s:]+[$€£]?([\d,]+\.?\d*)'
        ]
        # ... specialized logic
```

### Priority 3: Validation Framework (Week 3)

1. **Capital Account Validator**
```python
class CapitalAccountValidator:
    def validate(self, account_data):
        validations = [
            self.validate_balance_equation,
            self.validate_commitment_math,
            self.validate_distribution_breakdown,
            self.validate_fee_reasonableness,
            self.validate_period_continuity
        ]
        
        errors = []
        for validation in validations:
            if error := validation(account_data):
                errors.append(error)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            confidence=self.calculate_confidence(errors)
        )
```

2. **Cross-Document Validator**
```python
class CrossDocumentValidator:
    def validate_time_series(self, fund_id, investor_id):
        # Get all capital accounts in order
        accounts = self.get_accounts_chronological(fund_id, investor_id)
        
        for i in range(1, len(accounts)):
            prev = accounts[i-1]
            curr = accounts[i]
            
            # Validate continuity
            if prev.ending_balance != curr.beginning_balance:
                self.flag_discontinuity(prev, curr)
```

### Priority 4: Reconciliation Agent (Week 4)

```python
class ReconciliationAgent:
    async def run_daily_reconciliation(self):
        """Run automated reconciliation checks."""
        
        # Get all documents processed in last 24h
        recent_docs = await self.get_recent_documents()
        
        for doc in recent_docs:
            # Recalculate all metrics
            recalculated = await self.recalculate_metrics(doc)
            
            # Compare with extracted
            differences = self.compare_values(
                doc.extracted_data,
                recalculated
            )
            
            # Log results
            await self.log_reconciliation(
                doc_id=doc.id,
                differences=differences,
                status='PASS' if not differences else 'REVIEW'
            )
            
            # Alert if needed
            if differences:
                await self.send_alert(doc, differences)
```

### Priority 5: Enhanced API Layer (Week 5)

```python
# Time-series endpoint
@router.get("/pe/nav-series/{fund_id}")
async def get_nav_series(
    fund_id: str,
    start_date: date,
    end_date: date,
    frequency: Literal["daily", "monthly", "quarterly"] = "quarterly"
):
    """Get NAV time series with proper interpolation."""
    
    # Get data points
    data = await pe_storage.get_nav_observations(
        fund_id, start_date, end_date
    )
    
    # Interpolate missing points
    series = interpolate_nav_series(data, frequency)
    
    # Add analytics
    series_with_analytics = add_period_analytics(series)
    
    return series_with_analytics

# Forecasting endpoint
@router.post("/pe/forecast/{fund_id}")
async def create_forecast(
    fund_id: str,
    request: ForecastRequest
):
    """Generate cashflow and NAV forecast."""
    
    # Get historical data
    historical = await get_fund_history(fund_id)
    
    # Run forecast model
    forecast = PEForecastModel().predict(
        historical_data=historical,
        scenario=request.scenario,
        years_forward=request.years
    )
    
    return forecast
```

## Technical Debt to Address

1. **Lazy Loading Issue**: Need proper engine initialization
2. **UTF-8 Handling**: Already fixed with psycopg3
3. **Caching**: Need to implement proper caching for expensive operations
4. **Async Consistency**: Some methods mixing sync/async
5. **Error Recovery**: Need better retry mechanisms

## New Dependencies Needed

```python
# Add to requirements.txt
scipy>=1.11.0  # For IRR calculations
numpy-financial>=1.0.0  # For financial calculations
statsmodels>=0.14.0  # For time-series analysis
xlsxwriter>=3.1.0  # For Excel export
reportlab>=4.0.0  # For PDF generation
```

## Testing Requirements

1. **Extraction Accuracy Tests**
   - Test set of 100+ real documents
   - Target: 99.9% accuracy on critical fields
   
2. **Validation Tests**
   - Unit tests for each validation rule
   - Integration tests for full validation flow
   
3. **Performance Tests**
   - Document processing: < 30 seconds
   - API response: < 2 seconds
   
4. **Reconciliation Tests**
   - Test all calculation methods
   - Verify alert generation

## Success Criteria

1. **Zero Balance Mismatches**: 100% accurate balance calculations
2. **Complete Extraction**: All fields from competitor analysis extracted
3. **Full Audit Trail**: Every data point traceable to source
4. **Real-time Validation**: Immediate feedback on data quality
5. **Intelligent Chat**: Context-aware responses with current data

## Next Steps

1. **Week 1**: Implement enhanced database schema
2. **Week 2**: Build multi-method extraction engine
3. **Week 3**: Deploy validation framework
4. **Week 4**: Create reconciliation agent
5. **Week 5**: Enhance API endpoints
6. **Week 6**: Integration testing and optimization