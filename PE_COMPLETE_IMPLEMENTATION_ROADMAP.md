# PE Fund Document Processing - Complete Implementation Roadmap

Based on comprehensive analysis of competitors (Canoe, Cobalt LP, PitchBook), this roadmap ensures we build a production-grade system with near-zero error rates.

## Executive Summary

Our analysis reveals that competitors process 40+ distinct data fields from PE documents with sophisticated validation and reconciliation. Key findings:

1. **Capital Account Statements** are the cornerstone - containing 25+ fields that must reconcile perfectly
2. **Multi-source validation** is critical - QR data must match CAS data
3. **Time-series continuity** is non-negotiable - ending balance period N must equal beginning balance period N+1
4. **Automated reconciliation** with human review is industry standard

## Phase 1: Database Foundation (Week 1)

### Enhanced Schema Implementation

```sql
-- Run the migration we created
alembic upgrade pe_enhanced_001

-- Additional critical tables based on PDF analysis
CREATE TABLE pe_waterfall_structure (
    waterfall_id UUID PRIMARY KEY,
    fund_id UUID REFERENCES pe_fund_master,
    tier_number INTEGER,
    tier_type VARCHAR(50), -- 'RETURN_OF_CAPITAL', 'PREFERRED_RETURN', 'CATCH_UP', 'CARRIED_INTEREST'
    threshold_amount DECIMAL(20,2),
    gp_share DECIMAL(5,3),
    lp_share DECIMAL(5,3),
    description TEXT
);

CREATE TABLE pe_fee_schedule (
    schedule_id UUID PRIMARY KEY,
    fund_id UUID REFERENCES pe_fund_master,
    effective_date DATE,
    management_fee_rate DECIMAL(5,3),
    fee_basis VARCHAR(50), -- 'COMMITTED_CAPITAL', 'INVESTED_CAPITAL', 'NAV'
    fee_step_down JSON, -- {"year": rate} structure
    organizational_expense_cap DECIMAL(20,2)
);

CREATE TABLE pe_document_version (
    version_id UUID PRIMARY KEY,
    doc_id VARCHAR(36) REFERENCES pe_document,
    version_number INTEGER,
    upload_timestamp TIMESTAMP,
    replaces_version_id UUID,
    change_summary TEXT
);
```

## Phase 2: Multi-Method Extraction Engine (Week 2)

### Core Extraction Framework

```python
class EnhancedPEDocumentProcessor:
    """Production-grade document processor with multi-method extraction."""
    
    def __init__(self):
        self.extractors = {
            'capital_account': CapitalAccountExtractor(),
            'performance': PerformanceMetricsExtractor(),
            'cashflow': CashflowExtractor(),
            'commitment': CommitmentExtractor()
        }
        self.validators = {
            'capital_account': CapitalAccountValidator(),
            'performance': PerformanceValidator(),
            'cross_document': CrossDocumentValidator()
        }
    
    async def process_document(self, file_path: str, doc_type: str) -> ProcessingResult:
        """Process document with full extraction and validation."""
        
        # 1. Parse document
        parsed_data = await self.parse_document(file_path)
        
        # 2. Multi-method extraction
        extracted_data = {}
        extraction_audit = []
        
        for field_group, extractor in self.extractors.items():
            if extractor.applies_to(doc_type):
                # Extract using multiple methods
                results = await extractor.extract_multi_method(
                    parsed_data,
                    methods=['table', 'regex', 'llm', 'positional']
                )
                
                # Reconcile and score
                reconciled = self.reconcile_extraction_results(results)
                extracted_data[field_group] = reconciled['data']
                
                # Audit trail
                extraction_audit.extend(reconciled['audit'])
        
        # 3. Validate extracted data
        validation_results = await self.validate_all(extracted_data, doc_type)
        
        # 4. Store with confidence scores
        result = await self.store_with_audit(
            extracted_data,
            extraction_audit,
            validation_results
        )
        
        return result
```

### Field-Specific Extractors

```python
class CapitalAccountExtractor(BaseExtractor):
    """Extract capital account fields with high accuracy."""
    
    def __init__(self):
        self.field_definitions = {
            'beginning_balance': {
                'patterns': [
                    r'beginning\s+balance[\s:]+\$?([\d,]+\.?\d*)',
                    r'opening\s+balance[\s:]+\$?([\d,]+\.?\d*)',
                    r'balance[,\s]+beginning[\s:]+\$?([\d,]+\.?\d*)'
                ],
                'table_headers': ['Beginning Balance', 'Opening Balance', 'Balance, Beginning'],
                'llm_prompt': "Extract the beginning balance amount"
            },
            'ending_balance': {
                'patterns': [
                    r'ending\s+balance[\s:]+\$?([\d,]+\.?\d*)',
                    r'closing\s+balance[\s:]+\$?([\d,]+\.?\d*)',
                    r'nav[\s:]+\$?([\d,]+\.?\d*)',
                    r'net\s+asset\s+value[\s:]+\$?([\d,]+\.?\d*)'
                ],
                'table_headers': ['Ending Balance', 'NAV', 'Net Asset Value', 'Balance, Ending'],
                'llm_prompt': "Extract the ending balance/NAV amount"
            },
            'contributions': {
                'patterns': [
                    r'contributions?[\s:]+\$?([\d,]+\.?\d*)',
                    r'capital\s+calls?[\s:]+\$?([\d,]+\.?\d*)',
                    r'paid[\s-]in[\s:]+\$?([\d,]+\.?\d*)'
                ],
                'table_headers': ['Contributions', 'Capital Calls', 'Paid-in Capital'],
                'period_variants': ['Period', 'QTD', 'YTD', 'ITD']
            },
            'distributions': {
                'patterns': [
                    r'distributions?[\s:]+\$?([\d,]+\.?\d*)',
                    r'proceeds[\s:]+\$?([\d,]+\.?\d*)'
                ],
                'subtypes': {
                    'return_of_capital': ['Return of Capital', 'ROC', 'Capital Return'],
                    'realized_gains': ['Realized Gains', 'Gains', 'Capital Gains'],
                    'income': ['Income', 'Dividends', 'Interest'],
                    'tax': ['Tax Distribution', 'Withholding']
                }
            }
        }
    
    async def extract_multi_method(self, parsed_data: Dict, methods: List[str]) -> Dict:
        """Extract using multiple methods and return all results."""
        results = {}
        
        for method in methods:
            if method == 'table':
                results['table'] = await self.extract_from_tables(parsed_data['tables'])
            elif method == 'regex':
                results['regex'] = await self.extract_with_regex(parsed_data['text'])
            elif method == 'llm':
                results['llm'] = await self.extract_with_llm(parsed_data['text'])
            elif method == 'positional':
                results['positional'] = await self.extract_by_position(parsed_data['pages'])
        
        return results
```

### Intelligent Reconciliation

```python
class ExtractionReconciler:
    """Reconcile results from multiple extraction methods."""
    
    def reconcile(self, results: Dict[str, Any], field_name: str) -> Dict[str, Any]:
        """Reconcile extraction results with confidence scoring."""
        
        # Collect all values with their methods
        values = []
        for method, data in results.items():
            if field_name in data and data[field_name] is not None:
                values.append({
                    'method': method,
                    'value': self.normalize_value(data[field_name]),
                    'confidence': self.get_method_confidence(method)
                })
        
        if not values:
            return {'value': None, 'confidence': 0.0, 'source': 'none'}
        
        # Group by normalized value
        value_groups = {}
        for v in values:
            key = str(v['value'])
            if key not in value_groups:
                value_groups[key] = []
            value_groups[key].append(v)
        
        # Score each value group
        scored_values = []
        for value, sources in value_groups.items():
            score = sum(s['confidence'] for s in sources) / len(sources)
            score *= len(sources) / len(values)  # Bonus for consensus
            
            scored_values.append({
                'value': sources[0]['value'],  # Use first normalized value
                'score': score,
                'sources': sources,
                'consensus': len(sources) / len(values)
            })
        
        # Select best value
        best = max(scored_values, key=lambda x: x['score'])
        
        return {
            'value': best['value'],
            'confidence': best['score'],
            'source': ','.join(s['method'] for s in best['sources']),
            'consensus': best['consensus'],
            'alternatives': [v for v in scored_values if v != best]
        }
```

## Phase 3: Comprehensive Validation Framework (Week 3)

### Multi-Level Validation

```python
class ProductionValidationFramework:
    """Production-grade validation with cross-document checks."""
    
    def __init__(self):
        self.validators = {
            'mathematical': MathematicalValidator(),
            'continuity': ContinuityValidator(),
            'cross_reference': CrossReferenceValidator(),
            'business_rules': BusinessRulesValidator()
        }
    
    async def validate_capital_account(self, data: Dict, context: Dict) -> ValidationResult:
        """Comprehensive capital account validation."""
        
        errors = []
        warnings = []
        
        # 1. Mathematical validation
        math_result = self.validators['mathematical'].validate_balance_equation(data)
        if not math_result.is_valid:
            errors.extend(math_result.errors)
        
        # 2. Distribution breakdown validation
        dist_result = self.validators['mathematical'].validate_distribution_breakdown(data)
        if not dist_result.is_valid:
            errors.extend(dist_result.errors)
        
        # 3. Commitment validation
        commit_result = self.validators['business_rules'].validate_commitment_math(data)
        if not commit_result.is_valid:
            errors.extend(commit_result.errors)
        
        # 4. Time-series continuity
        if 'previous_period' in context:
            cont_result = self.validators['continuity'].validate_period_continuity(
                data, context['previous_period']
            )
            if not cont_result.is_valid:
                errors.extend(cont_result.errors)
        
        # 5. Cross-document validation
        if 'related_documents' in context:
            for related_doc in context['related_documents']:
                cross_result = self.validators['cross_reference'].validate_against_document(
                    data, related_doc
                )
                if not cross_result.is_valid:
                    warnings.extend(cross_result.errors)
        
        # Calculate confidence
        confidence = self.calculate_validation_confidence(errors, warnings)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            confidence=confidence,
            requires_review=confidence < 0.95 or len(errors) > 0
        )
```

### Specific Validation Rules

```python
class MathematicalValidator:
    """Mathematical validation rules."""
    
    def validate_balance_equation(self, data: Dict) -> ValidationResult:
        """Core balance equation validation."""
        
        # Extract values with defaults
        beginning = Decimal(str(data.get('beginning_balance', 0)))
        ending = Decimal(str(data.get('ending_balance', 0)))
        contributions = Decimal(str(data.get('contributions_period', 0)))
        distributions = Decimal(str(data.get('distributions_period', 0)))
        fees = Decimal(str(data.get('management_fees_period', 0)))
        expenses = Decimal(str(data.get('partnership_expenses_period', 0)))
        realized_gl = Decimal(str(data.get('realized_gain_loss_period', 0)))
        unrealized_gl = Decimal(str(data.get('unrealized_gain_loss_period', 0)))
        
        # Calculate expected ending balance
        expected = (
            beginning + 
            contributions - 
            distributions - 
            fees - 
            expenses + 
            realized_gl + 
            unrealized_gl
        )
        
        # Check with tolerance
        tolerance = max(abs(ending) * Decimal('0.0001'), Decimal('1'))  # 0.01% or $1
        difference = abs(ending - expected)
        
        if difference > tolerance:
            return ValidationResult(
                is_valid=False,
                errors=[{
                    'field': 'ending_balance',
                    'message': f'Balance equation mismatch: {ending} != {expected} (diff: {difference})',
                    'severity': 'critical',
                    'values': {
                        'beginning': float(beginning),
                        'contributions': float(contributions),
                        'distributions': float(distributions),
                        'fees': float(fees),
                        'expenses': float(expenses),
                        'realized_gl': float(realized_gl),
                        'unrealized_gl': float(unrealized_gl),
                        'expected_ending': float(expected),
                        'actual_ending': float(ending),
                        'difference': float(difference)
                    }
                }]
            )
        
        return ValidationResult(is_valid=True)
```

## Phase 4: Automated Reconciliation Agent (Week 4)

### Reconciliation Engine

```python
class PEReconciliationAgent:
    """Automated reconciliation with alerting."""
    
    def __init__(self):
        self.reconcilers = {
            'nav': NAVReconciler(),
            'cashflow': CashflowReconciler(),
            'performance': PerformanceReconciler(),
            'commitment': CommitmentReconciler()
        }
        self.alert_service = AlertService()
    
    async def run_comprehensive_reconciliation(self, fund_id: str, as_of_date: date):
        """Run all reconciliation checks for a fund."""
        
        reconciliation_id = str(uuid.uuid4())
        results = []
        
        # 1. NAV reconciliation (QR vs CAS)
        nav_result = await self.reconcile_nav(fund_id, as_of_date)
        results.append(nav_result)
        
        # 2. Cashflow reconciliation
        cf_result = await self.reconcile_cashflows(fund_id, as_of_date)
        results.append(cf_result)
        
        # 3. Performance metrics recalculation
        perf_result = await self.reconcile_performance(fund_id, as_of_date)
        results.append(perf_result)
        
        # 4. Commitment tracking
        commit_result = await self.reconcile_commitments(fund_id, as_of_date)
        results.append(commit_result)
        
        # Store results
        await self.store_reconciliation_results(reconciliation_id, results)
        
        # Alert on issues
        critical_issues = [r for r in results if r['status'] == 'FAIL']
        if critical_issues:
            await self.alert_service.send_reconciliation_alert(
                fund_id, critical_issues, reconciliation_id
            )
        
        return {
            'reconciliation_id': reconciliation_id,
            'timestamp': datetime.utcnow(),
            'fund_id': fund_id,
            'as_of_date': as_of_date,
            'results': results,
            'status': 'PASS' if not critical_issues else 'FAIL',
            'requires_review': len(critical_issues) > 0
        }
    
    async def reconcile_nav(self, fund_id: str, as_of_date: date) -> Dict:
        """Reconcile NAV across documents."""
        
        # Get CAS NAV
        cas_nav = await self.get_cas_nav(fund_id, as_of_date)
        
        # Get QR NAV
        qr_nav = await self.get_qr_nav(fund_id, as_of_date)
        
        if not cas_nav or not qr_nav:
            return {
                'type': 'nav_reconciliation',
                'status': 'MISSING_DATA',
                'message': 'Missing CAS or QR data for NAV reconciliation'
            }
        
        # Compare with tolerance
        tolerance = max(cas_nav * 0.0001, 1)  # 0.01% or $1
        difference = abs(cas_nav - qr_nav)
        
        if difference > tolerance:
            return {
                'type': 'nav_reconciliation',
                'status': 'FAIL',
                'message': f'NAV mismatch: CAS ${cas_nav:,.2f} vs QR ${qr_nav:,.2f}',
                'difference': difference,
                'tolerance': tolerance,
                'percentage_diff': (difference / cas_nav) * 100
            }
        
        return {
            'type': 'nav_reconciliation',
            'status': 'PASS',
            'cas_nav': cas_nav,
            'qr_nav': qr_nav
        }
```

### Performance Recalculation

```python
class PerformanceRecalculator:
    """Recalculate performance metrics from cashflows."""
    
    async def recalculate_metrics(self, fund_id: str, investor_id: str, as_of_date: date):
        """Recalculate all performance metrics."""
        
        # Get cashflow history
        cashflows = await self.get_cashflow_history(fund_id, investor_id)
        
        # Get current NAV
        current_nav = await self.get_nav(fund_id, investor_id, as_of_date)
        
        # Prepare cashflow series for IRR
        cf_series = []
        for cf in cashflows:
            # Contributions are negative, distributions positive
            amount = -cf['amount'] if cf['flow_type'] == 'CALL' else cf['amount']
            cf_series.append({
                'date': cf['flow_date'],
                'amount': amount
            })
        
        # Add current NAV as final cashflow
        cf_series.append({
            'date': as_of_date,
            'amount': current_nav
        })
        
        # Calculate IRR
        irr = self.calculate_irr(cf_series)
        
        # Calculate multiples
        total_contributed = sum(
            cf['amount'] for cf in cashflows 
            if cf['flow_type'] == 'CALL'
        )
        total_distributed = sum(
            cf['amount'] for cf in cashflows 
            if cf['flow_type'] in ['DIST', 'DIST_ROC', 'DIST_GAIN']
        )
        
        moic = (total_distributed + current_nav) / total_contributed if total_contributed > 0 else 0
        dpi = total_distributed / total_contributed if total_contributed > 0 else 0
        rvpi = current_nav / total_contributed if total_contributed > 0 else 0
        tvpi = dpi + rvpi
        
        return {
            'irr': irr,
            'moic': moic,
            'tvpi': tvpi,
            'dpi': dpi,
            'rvpi': rvpi,
            'total_contributed': total_contributed,
            'total_distributed': total_distributed,
            'current_nav': current_nav,
            'calculation_date': as_of_date
        }
```

## Phase 5: Production API Implementation (Week 5)

### Enhanced API Endpoints

```python
# In app/pe_docs/api_enhanced.py

@router.get("/pe/capital-account-series/{fund_id}")
async def get_capital_account_series(
    fund_id: str,
    investor_id: Optional[str] = None,
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    frequency: Literal["monthly", "quarterly", "annual"] = "quarterly",
    include_forecast: bool = False,
    db: Session = Depends(get_db)
):
    """Get capital account time series with analytics."""
    
    # Get historical data
    accounts = await pe_storage.get_capital_accounts(
        fund_id, investor_id, start_date, end_date
    )
    
    # Fill gaps with interpolation
    complete_series = interpolate_time_series(accounts, frequency)
    
    # Add period-over-period analytics
    for i in range(1, len(complete_series)):
        current = complete_series[i]
        previous = complete_series[i-1]
        
        # Calculate changes
        current['nav_change'] = current['ending_balance'] - previous['ending_balance']
        current['nav_change_pct'] = (
            (current['ending_balance'] - previous['ending_balance']) / 
            previous['ending_balance'] * 100
            if previous['ending_balance'] > 0 else 0
        )
        
        # Calculate contribution/distribution pace
        current['contribution_pace'] = (
            current['contributions_itd'] / current['total_commitment'] * 100
            if current['total_commitment'] > 0 else 0
        )
    
    # Add forecast if requested
    if include_forecast:
        forecast = await generate_forecast(fund_id, investor_id, end_date)
        complete_series.extend(forecast)
    
    return {
        'fund_id': fund_id,
        'investor_id': investor_id,
        'start_date': start_date,
        'end_date': end_date,
        'frequency': frequency,
        'data_points': len(complete_series),
        'series': complete_series
    }

@router.post("/pe/reconcile/{fund_id}")
async def trigger_reconciliation(
    fund_id: str,
    as_of_date: date = Query(...),
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Trigger reconciliation for a fund."""
    
    # Check permissions
    # ... permission check ...
    
    # Schedule reconciliation
    task_id = str(uuid.uuid4())
    background_tasks.add_task(
        run_reconciliation_task,
        task_id,
        fund_id,
        as_of_date
    )
    
    return {
        'task_id': task_id,
        'fund_id': fund_id,
        'as_of_date': as_of_date,
        'status': 'scheduled',
        'message': 'Reconciliation task scheduled'
    }

@router.get("/pe/extraction-audit/{doc_id}")
async def get_extraction_audit(
    doc_id: str,
    field_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get extraction audit trail for a document."""
    
    query = db.query(ExtractionAudit).filter(
        ExtractionAudit.doc_id == doc_id
    )
    
    if field_name:
        query = query.filter(ExtractionAudit.field_name == field_name)
    
    audits = query.order_by(ExtractionAudit.extraction_timestamp.desc()).all()
    
    return {
        'doc_id': doc_id,
        'audit_count': len(audits),
        'audits': [
            {
                'field_name': a.field_name,
                'extracted_value': a.extracted_value,
                'extraction_method': a.extraction_method,
                'confidence_score': float(a.confidence_score),
                'validation_status': a.validation_status,
                'manual_override': a.manual_override,
                'timestamp': a.extraction_timestamp
            }
            for a in audits
        ]
    }
```

## Phase 6: Quality Assurance & Testing (Week 6)

### Comprehensive Test Suite

```python
class PEExtractionTestSuite:
    """Test suite for PE document extraction."""
    
    def __init__(self):
        self.test_documents = self.load_test_documents()
        self.expected_results = self.load_expected_results()
    
    async def test_extraction_accuracy(self):
        """Test extraction accuracy across document types."""
        
        results = []
        
        for doc in self.test_documents:
            # Process document
            extracted = await self.processor.process_document(
                doc['path'], 
                doc['type']
            )
            
            # Compare with expected
            expected = self.expected_results[doc['id']]
            
            accuracy = self.calculate_accuracy(extracted, expected)
            results.append({
                'doc_id': doc['id'],
                'doc_type': doc['type'],
                'accuracy': accuracy,
                'errors': self.find_errors(extracted, expected)
            })
        
        # Summary
        overall_accuracy = sum(r['accuracy'] for r in results) / len(results)
        critical_fields_accuracy = self.calculate_critical_fields_accuracy(results)
        
        return {
            'overall_accuracy': overall_accuracy,
            'critical_fields_accuracy': critical_fields_accuracy,
            'by_document_type': self.group_by_type(results),
            'failed_documents': [r for r in results if r['accuracy'] < 0.95]
        }
```

## Implementation Timeline

### Week 1: Database & Infrastructure
- [ ] Run enhanced schema migration
- [ ] Set up extraction audit tables
- [ ] Configure reconciliation infrastructure
- [ ] Create test data set

### Week 2: Extraction Engine
- [ ] Implement multi-method extractors
- [ ] Build reconciliation logic
- [ ] Create confidence scoring
- [ ] Test extraction accuracy

### Week 3: Validation Framework
- [ ] Implement mathematical validators
- [ ] Build continuity checks
- [ ] Create cross-document validation
- [ ] Test validation rules

### Week 4: Reconciliation Agent
- [ ] Build automated reconciliation
- [ ] Implement recalculation engine
- [ ] Create alert system
- [ ] Test end-to-end flow

### Week 5: API & Integration
- [ ] Implement enhanced endpoints
- [ ] Build time-series analytics
- [ ] Create forecasting models
- [ ] Performance optimization

### Week 6: Testing & Deployment
- [ ] Run accuracy tests
- [ ] Performance testing
- [ ] User acceptance testing
- [ ] Production deployment

## Success Metrics

1. **Extraction Accuracy**: 99.9% on critical fields (NAV, contributions, distributions)
2. **Validation Coverage**: 100% of mathematical rules enforced
3. **Reconciliation**: 100% of discrepancies detected and flagged
4. **Processing Time**: < 30 seconds per document
5. **API Response**: < 2 seconds for queries
6. **Audit Trail**: 100% of extractions logged with confidence

## Risk Mitigation

1. **Data Integrity**: Never overwrite, always version
2. **Manual Override**: Allow but require justification
3. **Rollback**: Full rollback capability for any changes
4. **Monitoring**: Real-time alerts for anomalies
5. **Backup**: Automated backups before processing

This comprehensive implementation ensures we match or exceed competitor capabilities while maintaining the highest data quality standards.