"""Configuration for PE Documents module."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import yaml

from app.config import load_settings

settings = load_settings()


class PEConfig:
    """Configuration manager for PE Documents module."""
    
    def __init__(self):
        self.base_path = Path(__file__).parent
        self.mapping_path = self.base_path / "mapping"
        self._field_library = None
        self._column_map = None
        self._regex_bank = None
        self._phrase_bank = None
        self._validation_rules = None
        self._units = None
        
    @property
    def field_library(self) -> Dict[str, Any]:
        """Load field library configuration."""
        if self._field_library is None:
            with open(self.mapping_path / "field_library.yaml", 'r', encoding='utf-8') as f:
                self._field_library = yaml.safe_load(f)
        return self._field_library
    
    @property
    def column_map(self) -> pd.DataFrame:
        """Load column mapping CSV."""
        if self._column_map is None:
            self._column_map = pd.read_csv(
                self.mapping_path / "column_map.csv",
                encoding='utf-8'
            )
        return self._column_map
    
    @property
    def regex_bank(self) -> Dict[str, Any]:
        """Load regex patterns."""
        if self._regex_bank is None:
            with open(self.mapping_path / "regex_bank.yaml", 'r', encoding='utf-8') as f:
                self._regex_bank = yaml.safe_load(f) or {}
        return self._regex_bank
    
    @property
    def phrase_bank(self) -> Dict[str, Any]:
        """Load phrase anchors."""
        if self._phrase_bank is None:
            with open(self.mapping_path / "phrase_bank.yaml", 'r', encoding='utf-8') as f:
                self._phrase_bank = yaml.safe_load(f) or {}
        return self._phrase_bank
    
    @property
    def validation_rules(self) -> Dict[str, Any]:
        """Load validation rules."""
        if self._validation_rules is None:
            with open(self.mapping_path / "validation_rules.yaml", 'r', encoding='utf-8') as f:
                self._validation_rules = yaml.safe_load(f) or {}
        return self._validation_rules
    
    @property
    def units(self) -> Dict[str, Any]:
        """Load unit configurations."""
        if self._units is None:
            with open(self.mapping_path / "units.yaml", 'r', encoding='utf-8') as f:
                self._units = yaml.safe_load(f) or {}
        return self._units
    
    def get_canonical_fields(self) -> List[Dict[str, Any]]:
        """Get all canonical field definitions."""
        return self.field_library.get('fields', [])
    
    def get_field_by_name(self, canonical_name: str) -> Optional[Dict[str, Any]]:
        """Get field definition by canonical name."""
        for field in self.get_canonical_fields():
            if field.get('canonical') == canonical_name:
                return field
        return None
    
    def get_doc_type_anchors(self, doc_type: str) -> List[str]:
        """Get anchor phrases for document type classification."""
        return self.phrase_bank.get(doc_type, {}).get('anchors', [])
    
    def get_column_mapping(self, header: str) -> Optional[str]:
        """Map a column header to canonical field name."""
        # Case-insensitive matching
        header_lower = str(header).lower().strip()
        
        # Check column map
        for _, row in self.column_map.iterrows():
            if str(row.get('header', '')).lower().strip() == header_lower:
                return row.get('canonical')
        
        # Direct match with canonical names
        for field in self.get_canonical_fields():
            if field.get('canonical', '').lower() == header_lower:
                return field.get('canonical')
            # Check aliases
            for alias in field.get('aliases', []):
                if alias.lower() == header_lower:
                    return field.get('canonical')
        
        return None
    
    def get_validation_rule(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """Get validation rule by ID."""
        rules = self.validation_rules.get('rules', [])
        for rule in rules:
            if rule.get('id') == rule_id:
                return rule
        return None
    
    def get_currency_symbol(self, symbol: str) -> Optional[str]:
        """Convert currency symbol to ISO code."""
        return self.units.get('currency_symbols', {}).get(symbol)
    
    def get_multiplier(self, unit: str) -> Optional[float]:
        """Get numeric multiplier for unit."""
        return self.units.get('multipliers', {}).get(unit.lower())
    
    def get_decimal_format(self, locale: str = 'en') -> tuple:
        """Get decimal and thousand separator for locale."""
        formats = self.units.get('decimal', {})
        return tuple(formats.get(locale, ['.', ',']))


# Singleton instance
_pe_config = None

def get_pe_config() -> PEConfig:
    """Get or create PE configuration singleton."""
    global _pe_config
    if _pe_config is None:
        _pe_config = PEConfig()
    return _pe_config