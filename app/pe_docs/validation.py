"""Validation module for PE documents data."""

import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, date
from decimal import Decimal
from dataclasses import dataclass
from structlog import get_logger
from app.pe_docs.config import get_pe_config

logger = get_logger()
pe_config = get_pe_config()


@dataclass
class ValidationResult:
    """Result of document validation."""
    is_valid: bool
    errors: List[Dict[str, Any]]
    warnings: List[Dict[str, Any]]
    confidence: float = 0.0
    requires_review: bool = False


class PEDataValidator:
    """Validate PE document extracted data."""
    
    def __init__(self):
        """Initialize validator."""
        self.tolerance_pct = 0.01  # 1% default tolerance
    
    def validate_document_data(self, 
                             doc_type: str, 
                             data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate document data based on type.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Common validations
        errors.extend(self._validate_common_fields(data))
        
        # Type-specific validations
        if doc_type == 'capital_account_statement':
            errors.extend(self._validate_cas_data(data))
        elif doc_type in ['quarterly_report', 'annual_report']:
            errors.extend(self._validate_report_data(data))
        elif doc_type == 'capital_call_notice':
            errors.extend(self._validate_call_notice(data))
        elif doc_type == 'distribution_notice':
            errors.extend(self._validate_dist_notice(data))
        
        is_valid = len(errors) == 0
        
        if not is_valid:
            logger.warning(
                "validation_failed",
                doc_type=doc_type,
                error_count=len(errors),
                errors=errors[:5]  # Log first 5 errors
            )
        
        return is_valid, errors
    
    def _validate_common_fields(self, data: Dict[str, Any]) -> List[str]:
        """Validate common fields across document types."""
        errors = []
        
        # Date validations
        date_fields = ['as_of_date', 'period_end_date', 'statement_date']
        for field in date_fields:
            if field in data and data[field]:
                if not self._is_valid_date(data[field]):
                    errors.append(f"Invalid date format for {field}: {data[field]}")
        
        # Currency validation
        if 'currency' in data:
            if data['currency'] not in ['USD', 'EUR', 'GBP', 'CHF', 'JPY']:
                errors.append(f"Invalid currency: {data['currency']}")
        
        return errors
    
    def _validate_cas_data(self, data: Dict[str, Any]) -> List[str]:
        """Validate Capital Account Statement data."""
        errors = []
        
        # Required fields
        required = ['beginning_balance', 'ending_balance']
        for field in required:
            if field not in data or data[field] is None:
                errors.append(f"Missing required field: {field}")
        
        # CAS equation validation
        if all(field in data for field in ['beginning_balance', 'ending_balance', 
                                           'contributions', 'distributions', 'fees', 'pnl']):
            beginning = Decimal(str(data.get('beginning_balance', 0)))
            ending = Decimal(str(data.get('ending_balance', 0)))
            contributions = Decimal(str(data.get('contributions', 0)))
            distributions = Decimal(str(data.get('distributions', 0)))
            fees = Decimal(str(data.get('fees', 0)))
            pnl = Decimal(str(data.get('pnl', 0)))
            
            # CAS equation: ending = beginning + contributions - distributions - fees + pnl
            calculated = beginning + contributions - distributions - fees + pnl
            tolerance = abs(ending) * Decimal(str(self.tolerance_pct))
            
            if abs(ending - calculated) > tolerance:
                errors.append(
                    f"CAS equation imbalance: {ending} != {calculated} "
                    f"(beginning={beginning} + contrib={contributions} "
                    f"- dist={distributions} - fees={fees} + pnl={pnl})"
                )
        
        # Unfunded commitment validation
        if 'commitment' in data and 'drawn_capital' in data:
            commitment = Decimal(str(data['commitment']))
            drawn = Decimal(str(data.get('drawn_capital', 0)))
            unfunded = data.get('unfunded_commitment')
            
            if unfunded is not None:
                calculated_unfunded = commitment - drawn
                if abs(Decimal(str(unfunded)) - calculated_unfunded) > 1:
                    errors.append(
                        f"Unfunded commitment mismatch: {unfunded} != "
                        f"{commitment} - {drawn}"
                    )
        
        return errors
    
    def _validate_report_data(self, data: Dict[str, Any]) -> List[str]:
        """Validate Quarterly/Annual Report data."""
        errors = []
        
        # Performance metrics validation
        metrics = ['irr', 'moic', 'dpi', 'rvpi', 'tvpi']
        for metric in metrics:
            if metric in data and data[metric] is not None:
                value = float(data[metric])
                
                if metric == 'irr':
                    # IRR typically between -100% and 1000%
                    if value < -1 or value > 10:
                        errors.append(f"IRR out of reasonable range: {value}")
                
                elif metric in ['moic', 'dpi', 'rvpi', 'tvpi']:
                    # Multiples typically between 0 and 10x
                    if value < 0 or value > 10:
                        errors.append(f"{metric.upper()} out of range: {value}")
        
        # TVPI = DPI + RVPI validation
        if all(m in data and data[m] is not None for m in ['tvpi', 'dpi', 'rvpi']):
            tvpi = float(data['tvpi'])
            dpi = float(data['dpi'])
            rvpi = float(data['rvpi'])
            
            calculated_tvpi = dpi + rvpi
            if abs(tvpi - calculated_tvpi) > 0.01:
                errors.append(
                    f"TVPI calculation mismatch: {tvpi} != {dpi} + {rvpi}"
                )
        
        # NAV continuity check
        if 'nav' in data and data['nav'] is not None:
            nav = float(data['nav'])
            if nav < 0:
                errors.append(f"Negative NAV: {nav}")
        
        return errors
    
    def _validate_call_notice(self, data: Dict[str, Any]) -> List[str]:
        """Validate Capital Call Notice data."""
        errors = []
        
        # Required fields
        required = ['call_amount', 'due_date']
        for field in required:
            if field not in data or data[field] is None:
                errors.append(f"Missing required field: {field}")
        
        # Amount validation
        if 'call_amount' in data and data['call_amount'] is not None:
            amount = float(data['call_amount'])
            if amount <= 0:
                errors.append(f"Invalid call amount: {amount}")
        
        # Due date validation
        if 'due_date' in data and data['due_date']:
            if not self._is_future_date(data['due_date']):
                errors.append(f"Due date is in the past: {data['due_date']}")
        
        return errors
    
    def _validate_dist_notice(self, data: Dict[str, Any]) -> List[str]:
        """Validate Distribution Notice data."""
        errors = []
        
        # Required fields
        required = ['distribution_amount', 'payment_date']
        for field in required:
            if field not in data or data[field] is None:
                errors.append(f"Missing required field: {field}")
        
        # Amount validation
        if 'distribution_amount' in data and data['distribution_amount'] is not None:
            amount = float(data['distribution_amount'])
            if amount <= 0:
                errors.append(f"Invalid distribution amount: {amount}")
        
        # Distribution breakdown validation
        breakdown_fields = ['return_of_capital', 'realized_gains', 'income']
        breakdown_sum = sum(
            float(data.get(field, 0)) 
            for field in breakdown_fields 
            if field in data and data[field] is not None
        )
        
        if breakdown_sum > 0 and 'distribution_amount' in data:
            total = float(data['distribution_amount'])
            if abs(total - breakdown_sum) > 1:
                errors.append(
                    f"Distribution breakdown mismatch: {total} != {breakdown_sum}"
                )
        
        return errors
    
    def _is_valid_date(self, date_str: str) -> bool:
        """Check if date string is valid."""
        # Common date formats
        formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%B %d, %Y',
            '%b %d, %Y',
            '%d %B %Y',
            '%d %b %Y'
        ]
        
        for fmt in formats:
            try:
                datetime.strptime(date_str, fmt)
                return True
            except ValueError:
                continue
        
        return False
    
    def _is_future_date(self, date_str: str) -> bool:
        """Check if date is in the future."""
        for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%B %d, %Y']:
            try:
                dt = datetime.strptime(date_str, fmt).date()
                return dt > date.today()
            except ValueError:
                continue
        
        return False
    
    def validate_time_series(self, 
                           observations: List[Dict[str, Any]], 
                           field: str = 'nav') -> List[str]:
        """Validate time series data for continuity and consistency."""
        errors = []
        
        if not observations:
            return errors
        
        # Sort by date
        sorted_obs = sorted(
            observations, 
            key=lambda x: x.get('as_of_date', '')
        )
        
        # Check for continuity
        for i in range(1, len(sorted_obs)):
            prev = sorted_obs[i-1]
            curr = sorted_obs[i]
            
            if field in prev and field in curr:
                prev_val = float(prev[field])
                curr_val = float(curr[field])
                
                # Check for unreasonable jumps (>50% change)
                if prev_val > 0:
                    pct_change = abs(curr_val - prev_val) / prev_val
                    if pct_change > 0.5:
                        errors.append(
                            f"Large {field} change ({pct_change:.1%}) between "
                            f"{prev.get('as_of_date')} and {curr.get('as_of_date')}"
                        )
        
        return errors
    
    def cross_validate_documents(self, 
                               qr_data: Dict[str, Any], 
                               cas_data: Dict[str, Any]) -> List[str]:
        """Cross-validate data between QR and CAS."""
        errors = []
        
        # Validate NAV consistency
        if 'nav' in qr_data and 'ending_balance' in cas_data:
            qr_nav = float(qr_data['nav'])
            cas_nav = float(cas_data['ending_balance'])
            
            tolerance = abs(qr_nav) * self.tolerance_pct
            if abs(qr_nav - cas_nav) > tolerance:
                errors.append(
                    f"NAV mismatch between QR ({qr_nav}) and CAS ({cas_nav})"
                )
        
        # Validate cashflow consistency
        if 'distributions' in qr_data and 'distributions' in cas_data:
            qr_dist = float(qr_data['distributions'])
            cas_dist = float(cas_data['distributions'])
            
            if abs(qr_dist - cas_dist) > 1:
                errors.append(
                    f"Distribution mismatch between QR ({qr_dist}) and CAS ({cas_dist})"
                )
        
        return errors


class DocumentValidator:
    """Enhanced document validator with multi-level validation."""
    
    def __init__(self):
        """Initialize validator."""
        self.pe_validator = PEDataValidator()
        self.tolerance_pct = 0.001  # 0.1% tolerance for financial data
    
    async def validate_document(
        self,
        doc_type: str,
        extracted_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """Validate document with comprehensive checks."""
        errors = []
        warnings = []
        
        # 1. Field-level validation
        field_errors = self._validate_required_fields(doc_type, extracted_data)
        errors.extend(field_errors)
        
        # 2. Mathematical validation
        if doc_type in ['capital_account_statement', 'quarterly_report']:
            math_errors = self._validate_capital_account_math(extracted_data)
            errors.extend(math_errors)
        
        # 3. Business rule validation
        rule_errors = self._validate_business_rules(doc_type, extracted_data)
        errors.extend(rule_errors)
        
        # 4. Cross-period validation if context provided
        if context and context.get('previous_period'):
            continuity_errors = self._validate_period_continuity(
                extracted_data,
                context['previous_period']
            )
            warnings.extend(continuity_errors)
        
        # Calculate confidence based on validation results
        confidence = self._calculate_validation_confidence(
            extracted_data,
            errors,
            warnings
        )
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=[{'type': 'error', 'message': e} for e in errors],
            warnings=[{'type': 'warning', 'message': w} for w in warnings],
            confidence=confidence,
            requires_review=confidence < 0.85 or len(errors) > 0
        )
    
    def _validate_required_fields(self, doc_type: str, data: Dict[str, Any]) -> List[str]:
        """Validate required fields are present."""
        errors = []
        
        required_fields = {
            'capital_account_statement': [
                'beginning_balance',
                'ending_balance',
                'total_commitment'
            ],
            'quarterly_report': [
                'ending_balance',
                'as_of_date'
            ],
            'capital_call_notice': [
                'call_amount',
                'due_date'
            ],
            'distribution_notice': [
                'distribution_amount',
                'payment_date'
            ]
        }
        
        fields = required_fields.get(doc_type, [])
        for field in fields:
            if field not in data or data[field] is None:
                errors.append(f"Required field missing: {field}")
        
        return errors
    
    def _validate_capital_account_math(self, data: Dict[str, Any]) -> List[str]:
        """Validate capital account balance equation."""
        errors = []
        
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
        tolerance = max(abs(ending) * Decimal(str(self.tolerance_pct)), Decimal('1'))
        difference = abs(ending - expected)
        
        if difference > tolerance:
            errors.append(
                f"Balance equation mismatch: ending balance {ending} != "
                f"calculated {expected} (difference: {difference})"
            )
        
        return errors
    
    def _validate_business_rules(self, doc_type: str, data: Dict[str, Any]) -> List[str]:
        """Validate business rules."""
        errors = []
        
        # Unfunded commitment should not exceed total commitment
        if 'unfunded_commitment' in data and 'total_commitment' in data:
            unfunded = Decimal(str(data['unfunded_commitment']))
            total = Decimal(str(data['total_commitment']))
            
            if unfunded > total:
                errors.append(
                    f"Unfunded commitment ({unfunded}) exceeds "
                    f"total commitment ({total})"
                )
        
        # Drawn commitment + unfunded should equal total
        if all(k in data for k in ['drawn_commitment', 'unfunded_commitment', 'total_commitment']):
            drawn = Decimal(str(data['drawn_commitment']))
            unfunded = Decimal(str(data['unfunded_commitment']))
            total = Decimal(str(data['total_commitment']))
            
            if abs((drawn + unfunded) - total) > 1:
                errors.append(
                    f"Commitment math error: drawn ({drawn}) + "
                    f"unfunded ({unfunded}) != total ({total})"
                )
        
        return errors
    
    def _validate_period_continuity(
        self,
        current: Dict[str, Any],
        previous: Dict[str, Any]
    ) -> List[str]:
        """Validate continuity between periods."""
        warnings = []
        
        # Ending balance of previous should match beginning of current
        if 'ending_balance' in previous and 'beginning_balance' in current:
            prev_ending = Decimal(str(previous['ending_balance']))
            curr_beginning = Decimal(str(current['beginning_balance']))
            
            if abs(prev_ending - curr_beginning) > 1:
                warnings.append(
                    f"Period continuity break: previous ending ({prev_ending}) "
                    f"!= current beginning ({curr_beginning})"
                )
        
        return warnings
    
    def _calculate_validation_confidence(
        self,
        data: Dict[str, Any],
        errors: List[str],
        warnings: List[str]
    ) -> float:
        """Calculate confidence score based on validation results."""
        # Start with base confidence
        confidence = 1.0
        
        # Reduce for errors
        confidence -= len(errors) * 0.15
        
        # Reduce for warnings
        confidence -= len(warnings) * 0.05
        
        # Bonus for having all critical fields
        critical_fields = [
            'beginning_balance',
            'ending_balance',
            'total_commitment'
        ]
        
        if all(field in data and data[field] is not None for field in critical_fields):
            confidence += 0.1
        
        # Ensure confidence is between 0 and 1
        return max(0.0, min(1.0, confidence))