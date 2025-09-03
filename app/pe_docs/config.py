"""PE Documents configuration and field library loader."""
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
import csv

PE_DOCS_DIR = Path(__file__).parent
MAPPING_DIR = PE_DOCS_DIR / "mapping"

class FieldLibrary:
    """Field library for PE document processing."""
    
    def __init__(self):
        self.fields = {}
        self.column_map = {}
        self.regex_bank = {}
        self.phrase_bank = {}
        self.validation_rules = {}
        self.units = {}
        self._load_all()
    
    def _load_all(self):
        """Load all mapping files."""
        self._load_field_library()
        self._load_column_map()
        self._load_regex_bank()
        self._load_phrase_bank()
        self._load_validation_rules()
        self._load_units()
    
    def _load_field_library(self):
        """Load field library YAML."""
        path = MAPPING_DIR / "field_library.yaml"
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if data and 'fields' in data:
                    for field in data['fields']:
                        canonical = field.get('canonical')
                        if canonical:
                            self.fields[canonical] = field
    
    def _load_column_map(self):
        """Load column mapping CSV."""
        path = MAPPING_DIR / "column_map.csv"
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    alias = row.get('alias', '').strip()
                    canonical = row.get('canonical', '').strip()
                    if alias and canonical:
                        self.column_map[alias.lower()] = canonical
    
    def _load_regex_bank(self):
        """Load regex patterns."""
        path = MAPPING_DIR / "regex_bank.yaml"
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                self.regex_bank = yaml.safe_load(f) or {}
    
    def _load_phrase_bank(self):
        """Load phrase patterns."""
        path = MAPPING_DIR / "phrase_bank.yaml"
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                self.phrase_bank = yaml.safe_load(f) or {}
    
    def _load_validation_rules(self):
        """Load validation rules."""
        path = MAPPING_DIR / "validation_rules.yaml"
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                self.validation_rules = yaml.safe_load(f) or {}
    
    def _load_units(self):
        """Load units and currency mappings."""
        path = MAPPING_DIR / "units.yaml"
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                self.units = yaml.safe_load(f) or {}
    
    def get_canonical_field(self, alias: str) -> Optional[str]:
        """Get canonical field name from alias."""
        return self.column_map.get(alias.lower())
    
    def get_field_info(self, canonical: str) -> Optional[Dict[str, Any]]:
        """Get field information by canonical name."""
        return self.fields.get(canonical)
    
    def get_anchors_for_doc_type(self, doc_type: str) -> List[str]:
        """Get anchor patterns for document type."""
        return self.phrase_bank.get(doc_type, {}).get('anchors', [])

# Global field library instance
field_library = FieldLibrary()