"""Security configuration and settings."""

import os
from typing import List

from app.config import load_settings


class SecurityConfig:
    """Security configuration management."""
    
    def __init__(self):
        """Initialize security configuration."""
        self.settings = load_settings()
        self._validate_security_settings()
    
    def _validate_security_settings(self):
        """Validate that required security settings are configured."""
        required_settings = [
            "OPENAI_API_KEY",
            "DATABASE_URL"
        ]
        
        missing_settings = []
        for setting in required_settings:
            if not self.settings.get(setting):
                missing_settings.append(setting)
        
        if missing_settings:
            raise ValueError(f"Missing required security settings: {', '.join(missing_settings)}")
    
    def get_allowed_file_paths(self) -> List[str]:
        """Get list of allowed base paths for file operations."""
        paths = []
        
        # Add investor paths
        investor1_path = self.settings.get("INVESTOR1_PATH")
        investor2_path = self.settings.get("INVESTOR2_PATH")
        
        if investor1_path:
            paths.append(investor1_path)
        if investor2_path:
            paths.append(investor2_path)
        
        # Add data directory for test documents
        data_path = os.path.join(os.getcwd(), "data")
        paths.append(data_path)
        
        return paths
    
    def get_cors_settings(self) -> dict:
        """Get CORS settings for production."""
        allowed_origins = self.settings.get("ALLOWED_ORIGINS", "").split(",") if self.settings.get("ALLOWED_ORIGINS") else ["*"]
        
        # In production, restrict CORS origins
        if self.settings.get("DEPLOYMENT_MODE") == "production":
            # Remove wildcard in production
            allowed_origins = [origin for origin in allowed_origins if origin != "*"]
            
            # Add default production origins if none specified
            if not allowed_origins:
                allowed_origins = [
                    "https://forreporting.com",
                    "https://app.forreporting.com"
                ]
        
        return {
            "allow_origins": allowed_origins,
            "allow_credentials": True,
            "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["*"],
            "expose_headers": ["X-Request-ID"]
        }
    
    def get_security_headers(self) -> dict:
        """Get security headers for HTTP responses."""
        headers = {
            # Prevent clickjacking
            "X-Frame-Options": "DENY",
            
            # Prevent MIME sniffing
            "X-Content-Type-Options": "nosniff",
            
            # XSS protection
            "X-XSS-Protection": "1; mode=block",
            
            # Referrer policy
            "Referrer-Policy": "strict-origin-when-cross-origin",
            
            # Content Security Policy
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' https:; "
                "connect-src 'self' https:; "
                "frame-ancestors 'none';"
            )
        }
        
        # Add HSTS in production
        if self.settings.get("DEPLOYMENT_MODE") == "production":
            headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return headers
    
    def is_development_mode(self) -> bool:
        """Check if running in development mode."""
        return self.settings.get("DEPLOYMENT_MODE", "local").lower() in ["local", "development", "dev"]
    
    def get_file_upload_limits(self) -> dict:
        """Get file upload security limits."""
        return {
            "max_file_size_mb": 100,
            "allowed_extensions": [".pdf", ".xlsx", ".xls", ".csv", ".docx", ".txt"],
            "max_files_per_request": 10,
            "virus_scan_enabled": False,  # Would be enabled in production
            "quarantine_suspicious_files": True
        }
    
    def get_database_security_config(self) -> dict:
        """Get database security configuration."""
        return {
            "connection_timeout": 30,
            "query_timeout": 60,
            "max_connections": 20,
            "ssl_required": self.settings.get("DEPLOYMENT_MODE") == "production",
            "audit_queries": True,
            "mask_sensitive_data": True
        }
    
    def get_api_security_config(self) -> dict:
        """Get API security configuration."""
        return {
            "rate_limit_enabled": True,
            "rate_limit_requests_per_minute": 60,
            "rate_limit_burst": 10,
            "require_api_key": not self.is_development_mode(),
            "log_failed_auth_attempts": True,
            "block_suspicious_ips": True,
            "request_id_header": "X-Request-ID"
        }


# Global security config instance
security_config = SecurityConfig()