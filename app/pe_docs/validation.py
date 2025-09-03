"""Validation rules for PE document data."""
from typing import Dict, List, Any, Optional, Tuple
from datetime import date
from .config import field_library

class ValidationEngine:
    """Validation engine for PE document data."""
    
    def __init__(self):
        self.rules = field_library.validation_rules.get('rules', [])
        self.tolerances = {}
        
    def set_tolerances(self, tolerances: Dict[str, float]):
        """Set validation tolerances."""
        self.tolerances = tolerances
    
    def validate_cas_equation(self, period_data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate CAS equation: ending = opening + contributions - distributions - fees + pnl
        """
        required_fields = ['opening_balance', 'ending_balance']
        optional_fields = ['contributions', 'distributions', 'fees', 'pnl']
        
        # Check required fields
        for field in required_fields:
            if field not in period_data or period_data[field] is None:
                return False, f"Missing required field: {field}"
        
        opening = period_data['opening_balance']
        ending = period_data['ending_balance']
        contributions = period_data.get('contributions', 0)
        distributions = period_data.get('distributions', 0)
        fees = period_data.get('fees', 0)
        pnl = period_data.get('pnl', 0)
        
        # Calculate expected ending balance
        expected_ending = opening + contributions - distributions - fees + pnl
        
        # Check against tolerance
        tolerance = self.tolerances.get('nav_bridge', 0.005)  # 0.5% default
        difference = abs(ending - expected_ending)
        relative_error = difference / max(abs(ending), 1) if ending != 0 else difference
        
        if relative_error <= tolerance:
            return True, None
        else:
            return False, f"CAS equation failed: ending={ending}, expected={expected_ending:.2f}, error={relative_error:.3%}"
    
    def validate_nav_continuity(self, nav_observations: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """
        Validate NAV continuity across periods for same fund/investor.
        """
        errors = []
        
        if len(nav_observations) < 2:
            return True, []  # Can't validate continuity with single observation
        
        # Group by fund_id and investor_id
        groups = {}
        for obs in nav_observations:
            key = (obs.get('fund_id'), obs.get('investor_id'))
            if key not in groups:
                groups[key] = []
            groups[key].append(obs)
        
        # Check each group
        for (fund_id, investor_id), obs_list in groups.items():
            # Sort by as_of_date
            obs_list.sort(key=lambda x: x['as_of_date'])
            
            for i in range(1, len(obs_list)):
                prev_obs = obs_list[i-1]
                curr_obs = obs_list[i]
                
                # Check for reasonable NAV progression
                prev_nav = prev_obs['nav']
                curr_nav = curr_obs['nav']
                
                # Flag extreme changes (>500% or <-90%)
                if prev_nav > 0:
                    change_ratio = (curr_nav - prev_nav) / prev_nav
                    if change_ratio > 5.0:  # >500% increase
                        errors.append(f"Extreme NAV increase: {prev_nav} -> {curr_nav} ({change_ratio:.1%})")
                    elif change_ratio < -0.9:  # >90% decrease
                        errors.append(f"Extreme NAV decrease: {prev_nav} -> {curr_nav} ({change_ratio:.1%})")
        
        return len(errors) == 0, errors
    
    def validate_cashflow_consistency(self, cashflows: List[Dict[str, Any]], nav_observations: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """
        Validate cashflow consistency with NAV observations.
        """
        errors = []
        
        # Group cashflows by fund/investor
        cf_groups = {}
        for cf in cashflows:
            key = (cf.get('fund_id'), cf.get('investor_id'))
            if key not in cf_groups:
                cf_groups[key] = []
            cf_groups[key].append(cf)
        
        # Group NAV observations by fund/investor
        nav_groups = {}
        for obs in nav_observations:
            key = (obs.get('fund_id'), obs.get('investor_id'))
            if key not in nav_groups:
                nav_groups[key] = []
            nav_groups[key].append(obs)
        
        # Check consistency for each fund/investor
        for key in cf_groups:
            if key not in nav_groups:
                continue
            
            cf_list = cf_groups[key]
            nav_list = nav_groups[key]
            
            # Sort by date
            cf_list.sort(key=lambda x: x['flow_date'])
            nav_list.sort(key=lambda x: x['as_of_date'])
            
            # Check that major cashflows are reflected in NAV changes
            for cf in cf_list:
                if cf['amount'] < 10000:  # Skip small flows
                    continue
                
                cf_date = cf['flow_date']
                
                # Find NAV observations around this cashflow
                before_nav = None
                after_nav = None
                
                for nav_obs in nav_list:
                    nav_date = nav_obs['as_of_date']
                    if nav_date <= cf_date:
                        before_nav = nav_obs
                    elif nav_date > cf_date and after_nav is None:
                        after_nav = nav_obs
                        break
                
                # Validate impact
                if before_nav and after_nav:
                    expected_change = cf['amount'] if cf['flow_type'] == 'CALL' else -cf['amount']
                    actual_change = after_nav['nav'] - before_nav['nav']
                    
                    # Allow for reasonable variance (other factors affect NAV)
                    if cf['flow_type'] == 'CALL' and actual_change < expected_change * 0.5:
                        errors.append(f"Capital call of {cf['amount']} not reflected in NAV change")
                    elif cf['flow_type'] == 'DIST' and actual_change > -expected_change * 0.5:
                        errors.append(f"Distribution of {cf['amount']} not reflected in NAV change")
        
        return len(errors) == 0, errors
    
    def validate_unfunded_commitment(self, commitment_data: Dict[str, Any], cashflows: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """
        Validate unfunded commitment calculations.
        """
        errors = []
        
        commitment_amount = commitment_data.get('commitment_amount')
        unfunded = commitment_data.get('unfunded')
        
        if commitment_amount is None or unfunded is None:
            return True, []  # Can't validate without data
        
        # Calculate total calls
        total_calls = sum(cf['amount'] for cf in cashflows if cf['flow_type'] == 'CALL')
        
        # Expected unfunded = commitment - total calls
        expected_unfunded = commitment_amount - total_calls
        
        # Check against tolerance
        tolerance = self.tolerances.get('unfunded', 0.01)  # 1% tolerance
        difference = abs(unfunded - expected_unfunded)
        relative_error = difference / max(commitment_amount, 1)
        
        if relative_error > tolerance:
            errors.append(f"Unfunded mismatch: reported={unfunded}, expected={expected_unfunded:.2f}")
        
        return len(errors) == 0, errors
    
    def validate_fee_plausibility(self, fees: List[Dict[str, Any]], nav_observations: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """
        Validate fee amounts are plausible relative to NAV.
        """
        errors = []
        
        for fee in fees:
            fee_amount = fee.get('amount', 0)
            fee_type = fee.get('fee_type', '')
            
            # Find corresponding NAV
            nav_value = None
            for nav_obs in nav_observations:
                # Simple matching - could be more sophisticated
                nav_value = nav_obs.get('nav')
                break
            
            if nav_value and fee_amount > 0:
                fee_ratio = fee_amount / nav_value
                
                # Management fees typically 1-3% annually
                if 'management' in fee_type.lower():
                    if fee_ratio > 0.1:  # >10% seems excessive
                        errors.append(f"Management fee seems high: {fee_amount} vs NAV {nav_value} ({fee_ratio:.1%})")
                
                # Performance fees typically up to 20%
                elif 'performance' in fee_type.lower() or 'carried' in fee_type.lower():
                    if fee_ratio > 0.25:  # >25% seems excessive
                        errors.append(f"Performance fee seems high: {fee_amount} vs NAV {nav_value} ({fee_ratio:.1%})")
        
        return len(errors) == 0, errors
    
    def calculate_kpis(self, cashflows: List[Dict[str, Any]], nav_observations: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Calculate KPIs: TVPI, DPI, RVPI, IRR.
        """
        kpis = {}
        
        if not cashflows or not nav_observations:
            return kpis
        
        # Get latest NAV
        latest_nav_obs = max(nav_observations, key=lambda x: x['as_of_date'])
        current_nav = latest_nav_obs['nav']
        
        # Calculate totals
        total_calls = sum(cf['amount'] for cf in cashflows if cf['flow_type'] == 'CALL')
        total_distributions = sum(cf['amount'] for cf in cashflows if cf['flow_type'] == 'DIST')
        
        if total_calls > 0:
            # DPI = Distributions / Paid-in Capital
            kpis['DPI'] = total_distributions / total_calls
            
            # RVPI = Residual Value / Paid-in Capital  
            kpis['RVPI'] = current_nav / total_calls
            
            # TVPI = Total Value / Paid-in Capital
            kpis['TVPI'] = (current_nav + total_distributions) / total_calls
        
        # IRR calculation (simplified - would need more sophisticated calc for real IRR)
        if total_calls > 0 and len(cashflows) > 1:
            # Simple approximation based on time and returns
            cf_sorted = sorted(cashflows, key=lambda x: x['flow_date'])
            first_call_date = cf_sorted[0]['flow_date']
            last_date = latest_nav_obs['as_of_date']
            
            years = (last_date - first_call_date).days / 365.25
            if years > 0:
                total_value = current_nav + total_distributions
                # Simple IRR approximation
                kpis['IRR'] = ((total_value / total_calls) ** (1/years)) - 1
        
        return kpis

# Global validation engine
validation_engine = ValidationEngine()