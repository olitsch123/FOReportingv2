"""Subfolder management for organized PE document processing."""

import logging
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class DocumentCategory(Enum):
    """Standard PE document categories based on subfolder structure."""
    GENERAL = "01_General"
    QUARTERLY_REPORTS = "02_Quarterly_Reports"  
    CAPITAL_ACCOUNT_STATEMENTS = "03_CAS"
    FINANCIAL_STATEMENTS = "04_Financial_Statements"
    CAPITAL_CALLS = "05_Capital_Calls"
    OTHER = "06_Other"
    PITCHBOOK_DATA = "07_PitchbookData"


@dataclass
class SubfolderInfo:
    """Information about a subfolder."""
    path: str
    category: DocumentCategory
    fund_name: str
    file_count: int
    last_modified: Optional[str] = None


@dataclass 
class FundStructure:
    """Represents a fund's document structure."""
    fund_name: str
    fund_path: str
    subfolders: Dict[DocumentCategory, SubfolderInfo]
    total_files: int


class SubfolderManager:
    """Manages subfolder scanning and selective processing."""
    
    def __init__(self):
        """Initialize subfolder manager."""
        self.supported_extensions = {'.pdf', '.xlsx', '.xls', '.csv', '.docx', '.txt'}
        
    def scan_fund_structure(self, base_path: str) -> List[FundStructure]:
        """Scan the base investor path and return organized fund structures."""
        try:
            base = Path(base_path)
            if not base.exists():
                logger.warning(f"Base path does not exist: {base_path}")
                return []
            
            fund_structures = []
            
            # Find all fund folders (direct subdirectories of base_path)
            for fund_folder in base.iterdir():
                if not fund_folder.is_dir():
                    continue
                
                # Skip excluded folders
                if fund_folder.name.startswith('!'):
                    continue
                
                fund_structure = self._analyze_fund_folder(fund_folder)
                if fund_structure:
                    fund_structures.append(fund_structure)
            
            return sorted(fund_structures, key=lambda x: x.fund_name)
            
        except Exception as e:
            logger.error(f"Error scanning fund structure: {e}")
            return []
    
    def _analyze_fund_folder(self, fund_path: Path) -> Optional[FundStructure]:
        """Analyze a single fund folder structure."""
        try:
            subfolders = {}
            total_files = 0
            
            # Look for standard subfolders
            for category in DocumentCategory:
                subfolder_path = fund_path / category.value
                
                if subfolder_path.exists() and subfolder_path.is_dir():
                    file_count = self._count_supported_files(subfolder_path)
                    
                    subfolders[category] = SubfolderInfo(
                        path=str(subfolder_path),
                        category=category,
                        fund_name=fund_path.name,
                        file_count=file_count,
                        last_modified=self._get_last_modified(subfolder_path)
                    )
                    total_files += file_count
            
            # Only return if we found at least one standard subfolder
            if subfolders:
                return FundStructure(
                    fund_name=fund_path.name,
                    fund_path=str(fund_path),
                    subfolders=subfolders,
                    total_files=total_files
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error analyzing fund folder {fund_path}: {e}")
            return None
    
    def _count_supported_files(self, folder_path: Path) -> int:
        """Count supported files in a folder, applying exclusion rules."""
        count = 0
        
        try:
            for file_path in folder_path.rglob("*"):
                if file_path.is_file():
                    # Apply exclusion rules
                    if self._should_exclude_file(file_path):
                        continue
                    
                    # Check if supported
                    if file_path.suffix.lower() in self.supported_extensions:
                        count += 1
        
        except Exception as e:
            logger.warning(f"Error counting files in {folder_path}: {e}")
        
        return count
    
    def _should_exclude_file(self, file_path: Path) -> bool:
        """Check if file should be excluded based on rules."""
        # 1. Skip Python scripts
        if file_path.suffix.lower() == '.py':
            return True
        
        # 2. Skip [Date]_Fund_Documents.xlsx pattern
        if file_path.name.endswith('_Fund_Documents.xlsx') and '[' in file_path.name:
            return True
        
        # 3. Skip files in folders starting with "!"
        for parent in file_path.parents:
            if parent.name.startswith('!'):
                return True
        
        return False
    
    def _get_last_modified(self, folder_path: Path) -> Optional[str]:
        """Get last modified time of most recent file in folder."""
        try:
            latest_time = None
            
            for file_path in folder_path.rglob("*"):
                if file_path.is_file() and not self._should_exclude_file(file_path):
                    mtime = file_path.stat().st_mtime
                    if latest_time is None or mtime > latest_time:
                        latest_time = mtime
            
            if latest_time:
                from datetime import datetime
                return datetime.fromtimestamp(latest_time).strftime('%Y-%m-%d %H:%M:%S')
            
        except Exception as e:
            logger.warning(f"Error getting last modified for {folder_path}: {e}")
        
        return None
    
    def get_files_in_subfolders(
        self, 
        base_path: str, 
        selected_categories: List[DocumentCategory],
        fund_filter: Optional[str] = None
    ) -> List[Dict]:
        """Get files from specific subfolders matching criteria."""
        
        files = []
        fund_structures = self.scan_fund_structure(base_path)
        
        for fund_structure in fund_structures:
            # Apply fund filter if specified
            if fund_filter and fund_filter.lower() not in fund_structure.fund_name.lower():
                continue
            
            # Check selected categories
            for category in selected_categories:
                if category in fund_structure.subfolders:
                    subfolder_info = fund_structure.subfolders[category]
                    subfolder_files = self._get_files_from_path(subfolder_info.path)
                    
                    # Add metadata
                    for file_info in subfolder_files:
                        file_info.update({
                            'fund_name': fund_structure.fund_name,
                            'document_category': category.value,
                            'subfolder_path': subfolder_info.path
                        })
                    
                    files.extend(subfolder_files)
        
        return files
    
    def _get_files_from_path(self, folder_path: str) -> List[Dict]:
        """Get all supported files from a specific path."""
        files = []
        
        try:
            path = Path(folder_path)
            if not path.exists():
                return files
            
            for file_path in path.rglob("*"):
                if file_path.is_file():
                    # Apply exclusion rules
                    if self._should_exclude_file(file_path):
                        continue
                    
                    # Check if supported
                    if file_path.suffix.lower() in self.supported_extensions:
                        files.append({
                            'file_path': str(file_path),
                            'filename': file_path.name,
                            'file_size': file_path.stat().st_size,
                            'file_type': file_path.suffix.lower(),
                            'modified_date': file_path.stat().st_mtime
                        })
        
        except Exception as e:
            logger.error(f"Error getting files from {folder_path}: {e}")
        
        return files