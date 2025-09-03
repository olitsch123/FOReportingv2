"""Data resolver for PE documents - maps extracted data to database entities."""
from typing import Dict, List, Any, Optional
from datetime import date, datetime
from sqlalchemy.orm import Session
from app.database.models import Fund, Investor
from app.config import settings

class DataResolver:
    """Resolves extracted data to database entities."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def resolve_fund(self, fund_data: Dict[str, Any], org_code: str) -> Optional[str]:
        """
        Resolve fund from extracted data, create if not exists.
        Returns fund_id.
        """
        fund_name = fund_data.get('fund_name', '').strip()
        if not fund_name:
            return None
        
        # Look for existing fund
        fund = self.db.query(Fund).filter(
            Fund.name.ilike(f"%{fund_name}%")
        ).first()
        
        if not fund:
            # Create new fund
            fund = Fund(
                name=fund_name,
                fund_code=self._generate_fund_code(fund_name),
                asset_class=fund_data.get('asset_class', 'Private Equity'),
                vintage_year=fund_data.get('vintage_year'),
                target_size=fund_data.get('target_size'),
                currency=fund_data.get('currency', 'EUR'),
                management_company=fund_data.get('management_company'),
                investment_focus=fund_data.get('investment_focus'),
                metadata={
                    'org_code': org_code,
                    'source': 'pe_docs_extraction',
                    'extracted_terms': fund_data.get('terms', {})
                }
            )
            self.db.add(fund)
            self.db.flush()  # Get ID without committing
        
        return str(fund.id)
    
    def resolve_investor(self, investor_data: Dict[str, Any], investor_code: str, org_code: str) -> Optional[str]:
        """
        Resolve investor from extracted data, create if not exists.
        Returns investor_id.
        """
        investor_name = investor_data.get('investor_name', '').strip()
        if not investor_name:
            # Use investor_code as fallback
            investor_name = investor_code
        
        # Look for existing investor
        investor = self.db.query(Investor).filter(
            Investor.name.ilike(f"%{investor_name}%")
        ).first()
        
        if not investor:
            # Create new investor
            investor = Investor(
                name=investor_name,
                investor_code=investor_code,
                investor_type=investor_data.get('investor_type', 'Unknown'),
                metadata={
                    'org_code': org_code,
                    'source': 'pe_docs_extraction',
                    'extracted_data': investor_data
                }
            )
            self.db.add(investor)
            self.db.flush()
        
        return str(investor.id)
    
    def resolve_period_id(self, as_of_date: date) -> int:
        """
        Resolve period_id for a given as_of_date (month-end of as_of_date).
        """
        # Get month-end of as_of_date
        if as_of_date.day == 1:
            # If it's the first day, use previous month-end
            if as_of_date.month == 1:
                month_end = date(as_of_date.year - 1, 12, 31)
            else:
                # Get last day of previous month
                import calendar
                prev_month = as_of_date.month - 1
                year = as_of_date.year
                last_day = calendar.monthrange(year, prev_month)[1]
                month_end = date(year, prev_month, last_day)
        else:
            # Get last day of current month
            import calendar
            last_day = calendar.monthrange(as_of_date.year, as_of_date.month)[1]
            month_end = date(as_of_date.year, as_of_date.month, last_day)
        
        # Query dim_period for this month-end
        from app.database.models import Base
        result = self.db.execute(
            "SELECT period_id FROM dim_period WHERE period_end = %s",
            (month_end,)
        ).fetchone()
        
        if result:
            return result[0]
        
        # Create period if not exists
        self.db.execute(
            "INSERT INTO dim_period (period_end, year, month, quarter) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
            (month_end, month_end.year, month_end.month, (month_end.month - 1) // 3 + 1)
        )
        
        # Get the period_id
        result = self.db.execute(
            "SELECT period_id FROM dim_period WHERE period_end = %s",
            (month_end,)
        ).fetchone()
        
        return result[0] if result else None
    
    def _generate_fund_code(self, fund_name: str) -> str:
        """Generate fund code from fund name."""
        # Simple code generation - take first letters of words
        words = fund_name.upper().split()
        code = ''.join(word[0] for word in words if word and word[0].isalpha())
        
        # Ensure minimum length
        if len(code) < 3:
            code = fund_name[:3].upper().replace(' ', '')
        
        # Add counter if needed for uniqueness
        base_code = code[:10]  # Limit length
        counter = 1
        final_code = base_code
        
        while self.db.query(Fund).filter(Fund.fund_code == final_code).first():
            final_code = f"{base_code}{counter:02d}"
            counter += 1
        
        return final_code
    
    def resolve_currency(self, currency_code: str) -> str:
        """Resolve and validate currency code."""
        if not currency_code:
            return settings.get('REPORTING_CCY', 'EUR')
        
        # Normalize currency code
        currency_code = currency_code.upper().strip()
        
        # Common currency mappings
        currency_map = {
            'EURO': 'EUR',
            'EUROS': 'EUR', 
            'DOLLAR': 'USD',
            'DOLLARS': 'USD',
            'POUND': 'GBP',
            'POUNDS': 'GBP'
        }
        
        return currency_map.get(currency_code, currency_code)
    
    def validate_nav_observation(self, nav_obs: Dict[str, Any]) -> bool:
        """Validate NAV observation data."""
        required_fields = ['nav', 'as_of_date']
        
        for field in required_fields:
            if field not in nav_obs or nav_obs[field] is None:
                return False
        
        # Validate NAV is positive
        if nav_obs['nav'] <= 0:
            return False
        
        # Validate date is reasonable
        as_of_date = nav_obs['as_of_date']
        if isinstance(as_of_date, str):
            try:
                as_of_date = datetime.strptime(as_of_date, '%Y-%m-%d').date()
            except ValueError:
                return False
        
        # Check date is not in future
        if as_of_date > date.today():
            return False
        
        # Check date is not too old (e.g., before 1990)
        if as_of_date.year < 1990:
            return False
        
        return True
    
    def validate_cashflow(self, cashflow: Dict[str, Any]) -> bool:
        """Validate cashflow data."""
        required_fields = ['flow_type', 'amount', 'flow_date']
        
        for field in required_fields:
            if field not in cashflow or cashflow[field] is None:
                return False
        
        # Validate flow type
        valid_types = ['CALL', 'DIST', 'FEE', 'TAX', 'OTHER']
        if cashflow['flow_type'] not in valid_types:
            return False
        
        # Validate amount is positive
        if cashflow['amount'] <= 0:
            return False
        
        # Validate date
        flow_date = cashflow['flow_date']
        if isinstance(flow_date, str):
            try:
                flow_date = datetime.strptime(flow_date, '%Y-%m-%d').date()
            except ValueError:
                return False
        
        if flow_date > date.today():
            return False
        
        if flow_date.year < 1990:
            return False
        
        return True

def create_resolver(db: Session) -> DataResolver:
    """Create resolver instance with database session."""
    return DataResolver(db)