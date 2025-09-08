"""Security validation utilities."""

import os
import re
from pathlib import Path
from typing import List, Optional

from app.exceptions import ValidationError, ConfigurationError


class SecurityValidator:
    """Security validation utilities for input sanitization."""
    
    @staticmethod
    def validate_file_path(file_path: str, allowed_base_paths: Optional[List[str]] = None) -> str:
        """
        Validate file path to prevent path traversal attacks.
        
        Args:
            file_path: The file path to validate
            allowed_base_paths: List of allowed base paths (from config)
            
        Returns:
            Validated absolute file path
            
        Raises:
            ValidationError: If path is invalid or potentially malicious
        """
        try:
            # Convert to Path object for safe handling
            path = Path(file_path)
            
            # Check for path traversal attempts
            if '..' in file_path or '~' in file_path:
                raise ValidationError(
                    field_name="file_path",
                    value=file_path,
                    validation_rule="Path traversal not allowed"
                )
            
            # Get absolute path
            abs_path = path.resolve()
            
            # Validate against allowed base paths if provided
            if allowed_base_paths:
                is_allowed = False
                for base_path in allowed_base_paths:
                    try:
                        base_abs = Path(base_path).resolve()
                        if abs_path.is_relative_to(base_abs):
                            is_allowed = True
                            break
                    except (ValueError, OSError):
                        continue
                
                if not is_allowed:
                    raise ValidationError(
                        field_name="file_path",
                        value=file_path,
                        validation_rule="Path not within allowed directories"
                    )
            
            # Check if file exists and is readable
            if not abs_path.exists():
                raise ValidationError(
                    field_name="file_path",
                    value=file_path,
                    validation_rule="File does not exist"
                )
            
            if not abs_path.is_file():
                raise ValidationError(
                    field_name="file_path", 
                    value=file_path,
                    validation_rule="Path is not a file"
                )
            
            return str(abs_path)
            
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(
                field_name="file_path",
                value=file_path,
                validation_rule=f"Path validation failed: {str(e)}"
            )
    
    @staticmethod
    def validate_investor_code(investor_code: str) -> str:
        """
        Validate investor code format.
        
        Args:
            investor_code: The investor code to validate
            
        Returns:
            Validated investor code
            
        Raises:
            ValidationError: If code format is invalid
        """
        if not investor_code or not isinstance(investor_code, str):
            raise ValidationError(
                field_name="investor_code",
                value=investor_code,
                validation_rule="Investor code must be a non-empty string"
            )
        
        # Allow only alphanumeric characters, underscores, and hyphens
        if not re.match(r'^[a-zA-Z0-9_-]+$', investor_code):
            raise ValidationError(
                field_name="investor_code",
                value=investor_code,
                validation_rule="Investor code must contain only alphanumeric characters, underscores, and hyphens"
            )
        
        # Limit length
        if len(investor_code) > 50:
            raise ValidationError(
                field_name="investor_code",
                value=investor_code,
                validation_rule="Investor code must be 50 characters or less"
            )
        
        return investor_code.lower()
    
    @staticmethod
    def validate_fund_id(fund_id: str) -> str:
        """
        Validate fund ID format (UUID).
        
        Args:
            fund_id: The fund ID to validate
            
        Returns:
            Validated fund ID
            
        Raises:
            ValidationError: If ID format is invalid
        """
        if not fund_id or not isinstance(fund_id, str):
            raise ValidationError(
                field_name="fund_id",
                value=fund_id,
                validation_rule="Fund ID must be a non-empty string"
            )
        
        # Validate UUID format
        import uuid
        try:
            uuid.UUID(fund_id)
            return fund_id
        except ValueError:
            raise ValidationError(
                field_name="fund_id",
                value=fund_id,
                validation_rule="Fund ID must be a valid UUID"
            )
    
    @staticmethod
    def sanitize_text_input(text: str, max_length: int = 10000) -> str:
        """
        Sanitize text input to prevent injection attacks.
        
        Args:
            text: The text to sanitize
            max_length: Maximum allowed length
            
        Returns:
            Sanitized text
            
        Raises:
            ValidationError: If text is invalid
        """
        if not isinstance(text, str):
            raise ValidationError(
                field_name="text_input",
                value=text,
                validation_rule="Input must be a string"
            )
        
        # Check length
        if len(text) > max_length:
            raise ValidationError(
                field_name="text_input",
                value=f"Length: {len(text)}",
                validation_rule=f"Text must be {max_length} characters or less"
            )
        
        # Remove potentially dangerous characters/patterns
        dangerous_patterns = [
            r'<script[^>]*>.*?</script>',  # Script tags
            r'javascript:',               # JavaScript URLs
            r'on\w+\s*=',                # Event handlers
            r'<iframe[^>]*>.*?</iframe>', # Iframes
        ]
        
        sanitized = text
        for pattern in dangerous_patterns:
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        
        return sanitized.strip()
    
    @staticmethod
    def validate_api_key_format(api_key: str, service: str) -> bool:
        """
        Validate API key format for external services.
        
        Args:
            api_key: The API key to validate
            service: The service name (openai, etc.)
            
        Returns:
            True if format is valid
            
        Raises:
            ValidationError: If API key format is invalid
        """
        if not api_key or not isinstance(api_key, str):
            return False
        
        # Service-specific validation
        if service.lower() == "openai":
            # OpenAI keys start with 'sk-' and are typically 51 characters
            if not api_key.startswith('sk-') or len(api_key) < 20:
                raise ValidationError(
                    field_name="openai_api_key",
                    value="[REDACTED]",
                    validation_rule="OpenAI API key must start with 'sk-' and be at least 20 characters"
                )
        
        return True
    
    @staticmethod
    def get_allowed_file_extensions() -> List[str]:
        """Get list of allowed file extensions for upload."""
        return ['.pdf', '.xlsx', '.xls', '.csv', '.docx', '.txt']
    
    @staticmethod
    def validate_file_extension(file_path: str) -> bool:
        """
        Validate file extension against allowed types.
        
        Args:
            file_path: The file path to validate
            
        Returns:
            True if extension is allowed
            
        Raises:
            ValidationError: If extension is not allowed
        """
        path = Path(file_path)
        extension = path.suffix.lower()
        
        allowed_extensions = SecurityValidator.get_allowed_file_extensions()
        
        if extension not in allowed_extensions:
            raise ValidationError(
                field_name="file_extension",
                value=extension,
                validation_rule=f"File extension must be one of: {', '.join(allowed_extensions)}"
            )
        
        return True
    
    @staticmethod
    def validate_file_size(file_path: str, max_size_mb: int = 100) -> bool:
        """
        Validate file size to prevent DoS attacks.
        
        Args:
            file_path: The file path to check
            max_size_mb: Maximum allowed size in MB
            
        Returns:
            True if size is acceptable
            
        Raises:
            ValidationError: If file is too large
        """
        try:
            file_size = Path(file_path).stat().st_size
            max_size_bytes = max_size_mb * 1024 * 1024
            
            if file_size > max_size_bytes:
                raise ValidationError(
                    field_name="file_size",
                    value=f"{file_size / 1024 / 1024:.2f} MB",
                    validation_rule=f"File size must be {max_size_mb} MB or less"
                )
            
            return True
            
        except OSError as e:
            raise ValidationError(
                field_name="file_path",
                value=file_path,
                validation_rule=f"Cannot access file: {str(e)}"
            )


def validate_processing_request(file_path: str, investor_code: str, allowed_paths: List[str]) -> tuple[str, str]:
    """
    Comprehensive validation for document processing requests.
    
    Args:
        file_path: The file path to process
        investor_code: The investor code
        allowed_paths: List of allowed base paths
        
    Returns:
        Tuple of (validated_file_path, validated_investor_code)
        
    Raises:
        ValidationError: If any validation fails
    """
    validator = SecurityValidator()
    
    # Validate investor code
    validated_investor = validator.validate_investor_code(investor_code)
    
    # Validate file path
    validated_path = validator.validate_file_path(file_path, allowed_paths)
    
    # Validate file extension
    validator.validate_file_extension(validated_path)
    
    # Validate file size
    validator.validate_file_size(validated_path)
    
    return validated_path, validated_investor