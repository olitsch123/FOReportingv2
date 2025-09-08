"""Centralized field mapping to ensure consistency across frontend, API, and database."""

from enum import Enum
from typing import Any, Dict, Optional


class FieldType(Enum):
    """Field data types."""
    UUID = "uuid"
    STRING = "string"
    DECIMAL = "decimal"
    DATE = "date"
    INTEGER = "integer"
    BOOLEAN = "boolean"


class TableMapping:
    """Centralized table and field mappings."""
    
    # PE Fund Master table mapping
    PE_FUND_MASTER = {
        'table_name': 'pe_fund_master',
        'primary_key': 'fund_id',
        'fields': {
            'fund_id': {'db_type': FieldType.UUID, 'required': True},
            'fund_code': {'db_type': FieldType.STRING, 'max_length': 50, 'required': True},
            'fund_name': {'db_type': FieldType.STRING, 'max_length': 255, 'required': True},
            'currency': {'db_type': FieldType.STRING, 'max_length': 3, 'required': False},
            'fund_manager': {'db_type': FieldType.STRING, 'max_length': 255, 'required': False},
            'vintage_year': {'db_type': FieldType.INTEGER, 'required': False},
            'fund_size': {'db_type': FieldType.DECIMAL, 'precision': 20, 'scale': 2, 'required': False}
        }
    }
    
    # PE Document table mapping
    PE_DOCUMENT = {
        'table_name': 'pe_document',
        'primary_key': 'doc_id',
        'fields': {
            'doc_id': {'db_type': FieldType.STRING, 'max_length': 36, 'required': True},
            'doc_type': {'db_type': FieldType.STRING, 'max_length': 40, 'required': True},
            'fund_id': {'db_type': FieldType.STRING, 'max_length': 36, 'required': False},  # VARCHAR to match UUID string
            'investor_id': {'db_type': FieldType.STRING, 'max_length': 36, 'required': False},
            'path': {'db_type': FieldType.STRING, 'required': False},
            'file_hash': {'db_type': FieldType.STRING, 'max_length': 64, 'required': False},
            'embedding_status': {'db_type': FieldType.STRING, 'max_length': 50, 'required': False},
            'chunk_count': {'db_type': FieldType.INTEGER, 'required': False}
        }
    }
    
    # PE Capital Account table mapping
    PE_CAPITAL_ACCOUNT = {
        'table_name': 'pe_capital_account',
        'primary_key': 'account_id',
        'unique_constraints': [['fund_id', 'investor_id', 'as_of_date']],
        'fields': {
            'account_id': {'db_type': FieldType.UUID, 'required': True},
            'fund_id': {'db_type': FieldType.UUID, 'required': True},
            'investor_id': {'db_type': FieldType.STRING, 'max_length': 36, 'required': True},
            'as_of_date': {'db_type': FieldType.DATE, 'required': True},
            'period_type': {'db_type': FieldType.STRING, 'max_length': 20, 'required': False},
            'reporting_currency': {'db_type': FieldType.STRING, 'max_length': 3, 'required': False},
            'beginning_balance': {'db_type': FieldType.DECIMAL, 'precision': 20, 'scale': 2, 'required': False},
            'ending_balance': {'db_type': FieldType.DECIMAL, 'precision': 20, 'scale': 2, 'required': False},
            'contributions_period': {'db_type': FieldType.DECIMAL, 'precision': 20, 'scale': 2, 'required': False},
            'distributions_period': {'db_type': FieldType.DECIMAL, 'precision': 20, 'scale': 2, 'required': False},
            'management_fees_period': {'db_type': FieldType.DECIMAL, 'precision': 20, 'scale': 2, 'required': False},
            'partnership_expenses_period': {'db_type': FieldType.DECIMAL, 'precision': 20, 'scale': 2, 'required': False},
            'realized_gain_loss_period': {'db_type': FieldType.DECIMAL, 'precision': 20, 'scale': 2, 'required': False},
            'unrealized_gain_loss_period': {'db_type': FieldType.DECIMAL, 'precision': 20, 'scale': 2, 'required': False},
            'total_commitment': {'db_type': FieldType.DECIMAL, 'precision': 20, 'scale': 2, 'required': False},
            'drawn_commitment': {'db_type': FieldType.DECIMAL, 'precision': 20, 'scale': 2, 'required': False},
            'unfunded_commitment': {'db_type': FieldType.DECIMAL, 'precision': 20, 'scale': 2, 'required': False}
        }
    }
    
    # PE Investor table mapping
    PE_INVESTOR = {
        'table_name': 'pe_investor',
        'primary_key': 'investor_id',
        'fields': {
            'investor_id': {'db_type': FieldType.STRING, 'max_length': 36, 'required': True},
            'investor_code': {'db_type': FieldType.STRING, 'max_length': 50, 'required': True},
            'investor_name': {'db_type': FieldType.STRING, 'max_length': 255, 'required': True},
            'investor_type': {'db_type': FieldType.STRING, 'max_length': 50, 'required': False}
        }
    }


class FieldMapper:
    """Utility class for field mapping and validation."""
    
    @staticmethod
    def get_table_mapping(table_name: str) -> Optional[Dict[str, Any]]:
        """Get table mapping by name."""
        mappings = {
            'pe_fund_master': TableMapping.PE_FUND_MASTER,
            'pe_document': TableMapping.PE_DOCUMENT,
            'pe_capital_account': TableMapping.PE_CAPITAL_ACCOUNT,
            'pe_investor': TableMapping.PE_INVESTOR
        }
        return mappings.get(table_name)
    
    @staticmethod
    def get_field_definition(table_name: str, field_name: str) -> Optional[Dict[str, Any]]:
        """Get field definition for a specific table and field."""
        table_mapping = FieldMapper.get_table_mapping(table_name)
        if not table_mapping:
            return None
        return table_mapping['fields'].get(field_name)
    
    @staticmethod
    def validate_field_value(table_name: str, field_name: str, value: Any) -> bool:
        """Validate a field value against its definition."""
        field_def = FieldMapper.get_field_definition(table_name, field_name)
        if not field_def:
            return False
        
        # Check required fields
        if field_def.get('required', False) and value is None:
            return False
        
        # Check string length
        if field_def['db_type'] == FieldType.STRING and value is not None:
            max_length = field_def.get('max_length')
            if max_length and len(str(value)) > max_length:
                return False
        
        return True
    
    @staticmethod
    def get_insert_statement(table_name: str, fields: Dict[str, Any]) -> str:
        """Generate a properly formatted INSERT statement."""
        table_mapping = FieldMapper.get_table_mapping(table_name)
        if not table_mapping:
            raise ValueError(f"Unknown table: {table_name}")
        
        # Build column list and value placeholders
        columns = []
        placeholders = []
        
        for field_name, value in fields.items():
            if field_name in table_mapping['fields']:
                field_def = table_mapping['fields'][field_name]
                columns.append(field_name)
                
                # Add proper casting for UUID fields
                if field_def['db_type'] == FieldType.UUID:
                    placeholders.append(f"CAST(:{field_name} AS uuid)")
                else:
                    placeholders.append(f":{field_name}")
        
        columns_str = ', '.join(columns)
        placeholders_str = ', '.join(placeholders)
        
        return f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders_str})"
    
    @staticmethod
    def get_upsert_statement(table_name: str, fields: Dict[str, Any], conflict_fields: list = None) -> str:
        """Generate a properly formatted UPSERT statement."""
        table_mapping = FieldMapper.get_table_mapping(table_name)
        if not table_mapping:
            raise ValueError(f"Unknown table: {table_name}")
        
        # Get base INSERT statement
        insert_stmt = FieldMapper.get_insert_statement(table_name, fields)
        
        # Determine conflict fields
        if not conflict_fields:
            conflict_fields = table_mapping.get('unique_constraints', [[table_mapping['primary_key']]])[0]
        
        # Build ON CONFLICT clause
        conflict_str = ', '.join(conflict_fields)
        
        # Build UPDATE SET clause for non-key fields
        update_fields = []
        for field_name in fields.keys():
            if field_name not in conflict_fields and field_name in table_mapping['fields']:
                update_fields.append(f"{field_name} = EXCLUDED.{field_name}")
        
        if update_fields:
            update_str = ', '.join(update_fields)
            return f"{insert_stmt} ON CONFLICT ({conflict_str}) DO UPDATE SET {update_str}"
        else:
            return f"{insert_stmt} ON CONFLICT ({conflict_str}) DO NOTHING"


# Field aliases for extraction consistency
EXTRACTION_FIELD_ALIASES = {
    'currency': 'reporting_currency',  # Map extraction 'currency' to DB 'reporting_currency'
    'fund_currency': 'currency',       # Map fund currency properly
    'other_fees_period': 'partnership_expenses_period',  # Map generic fees to specific field
    'realized_gain_period': 'realized_gain_loss_period',
    'unrealized_gain_period': 'unrealized_gain_loss_period'
}


def normalize_extracted_fields(extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize extracted field names to match database schema."""
    normalized = {}
    
    for key, value in extracted_data.items():
        # Apply field aliases
        normalized_key = EXTRACTION_FIELD_ALIASES.get(key, key)
        normalized[normalized_key] = value
    
    return normalized