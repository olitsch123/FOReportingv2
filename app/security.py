"""Security utilities for FOReporting v2."""

import secrets
import hashlib
import hmac
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import jwt
from passlib.context import CryptContext
from structlog import get_logger
from app.config import load_settings

logger = get_logger()
settings = load_settings()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
JWT_SECRET_KEY = settings.get("JWT_SECRET_KEY", secrets.token_urlsafe(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


class SecurityManager:
    """Manage security operations."""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against hash."""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def generate_token() -> str:
        """Generate a secure random token."""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def generate_api_key() -> str:
        """Generate an API key."""
        return f"forp_{secrets.token_hex(24)}"
    
    @staticmethod
    def create_jwt_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT token."""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
        
        to_encode.update({"exp": expire})
        
        encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def verify_jwt_token(token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("jwt_token_expired", token=token[:10] + "...")
            return None
        except jwt.InvalidTokenError:
            logger.warning("jwt_token_invalid", token=token[:10] + "...")
            return None
    
    @staticmethod
    def hash_file(file_path: str, chunk_size: int = 8192) -> str:
        """Calculate SHA-256 hash of a file."""
        sha256_hash = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                sha256_hash.update(chunk)
        
        return sha256_hash.hexdigest()
    
    @staticmethod
    def hmac_sign(data: str, key: str) -> str:
        """Create HMAC signature for data."""
        return hmac.new(
            key.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename to prevent directory traversal."""
        # Remove path separators and dangerous characters
        sanitized = filename.replace("/", "_").replace("\\", "_")
        sanitized = sanitized.replace("..", "_")
        
        # Remove null bytes
        sanitized = sanitized.replace("\x00", "")
        
        # Limit length
        if len(sanitized) > 255:
            name, ext = sanitized.rsplit(".", 1) if "." in sanitized else (sanitized, "")
            sanitized = name[:250] + "." + ext if ext else name[:255]
        
        return sanitized
    
    @staticmethod
    def validate_file_type(filename: str, allowed_types: list) -> bool:
        """Validate file type against allowed list."""
        ext = filename.lower().split(".")[-1] if "." in filename else ""
        return ext in [t.lower().strip(".") for t in allowed_types]
    
    @staticmethod
    def redact_sensitive_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive fields from data."""
        sensitive_fields = [
            "password", "api_key", "secret", "token", 
            "authorization", "ssn", "tax_id", "bank_account"
        ]
        
        redacted = data.copy()
        
        for key, value in redacted.items():
            # Check field names
            if any(sensitive in key.lower() for sensitive in sensitive_fields):
                if isinstance(value, str) and len(value) > 4:
                    redacted[key] = value[:4] + "*" * (len(value) - 4)
                else:
                    redacted[key] = "***REDACTED***"
            
            # Recurse into nested dicts
            elif isinstance(value, dict):
                redacted[key] = SecurityManager.redact_sensitive_data(value)
        
        return redacted


class InputSanitizer:
    """Sanitize user inputs."""
    
    @staticmethod
    def sanitize_sql_identifier(identifier: str) -> str:
        """Sanitize SQL identifiers to prevent injection."""
        # Only allow alphanumeric and underscore
        sanitized = "".join(c for c in identifier if c.isalnum() or c == "_")
        
        # Must start with letter
        if sanitized and not sanitized[0].isalpha():
            sanitized = "f_" + sanitized
        
        # Limit length
        return sanitized[:63]  # PostgreSQL identifier limit
    
    @staticmethod
    def sanitize_path(path: str) -> str:
        """Sanitize file paths."""
        # Remove dangerous patterns
        dangerous_patterns = ["../", "..\\", "~", "$", "|", ";", "&", ">", "<"]
        
        sanitized = path
        for pattern in dangerous_patterns:
            sanitized = sanitized.replace(pattern, "")
        
        # Remove null bytes
        sanitized = sanitized.replace("\x00", "")
        
        return sanitized
    
    @staticmethod
    def escape_html(text: str) -> str:
        """Escape HTML special characters."""
        escape_map = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#x27;",
            "/": "&#x2F;"
        }
        
        for char, escape in escape_map.items():
            text = text.replace(char, escape)
        
        return text


class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self):
        self.attempts = {}
        self.window_seconds = 60
        self.max_attempts = 100
    
    def check_rate_limit(self, key: str) -> bool:
        """Check if rate limit exceeded."""
        now = datetime.utcnow()
        
        # Clean old entries
        self.attempts = {
            k: v for k, v in self.attempts.items()
            if (now - v["first"]).total_seconds() < self.window_seconds
        }
        
        if key not in self.attempts:
            self.attempts[key] = {"first": now, "count": 1}
            return True
        
        entry = self.attempts[key]
        if (now - entry["first"]).total_seconds() > self.window_seconds:
            # Reset window
            self.attempts[key] = {"first": now, "count": 1}
            return True
        
        if entry["count"] >= self.max_attempts:
            return False
        
        entry["count"] += 1
        return True


# Global instances
security_manager = SecurityManager()
input_sanitizer = InputSanitizer()
rate_limiter = RateLimiter()