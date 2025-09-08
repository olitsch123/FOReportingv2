"""Authentication and authorization for FOReporting v2."""

import logging
import os
from typing import Optional

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

# Security scheme for Bearer token
security = HTTPBearer(auto_error=False)


def get_api_key() -> str:
    """Get API key from environment."""
    api_key = os.getenv("API_KEY") or os.getenv("FORREPORTING_API_KEY")
    if not api_key:
        # Generate a warning but allow operation in development
        logger.warning("No API_KEY configured - authentication disabled")
        return "dev-mode-no-auth"
    return api_key


def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> bool:
    """Verify API key from header."""
    expected_key = get_api_key()
    
    # Allow dev mode without auth
    if expected_key == "dev-mode-no-auth":
        return True
    
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Provide X-API-Key header."
        )
    
    if x_api_key != expected_key:
        logger.warning(f"Invalid API key attempt: {x_api_key[:8]}...")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    
    return True


def verify_bearer_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> bool:
    """Verify Bearer token."""
    if not credentials:
        # Fall back to API key header
        return verify_api_key()
    
    expected_key = get_api_key()
    
    # Allow dev mode
    if expected_key == "dev-mode-no-auth":
        return True
    
    if credentials.credentials != expected_key:
        logger.warning(f"Invalid bearer token attempt: {credentials.credentials[:8]}...")
        raise HTTPException(
            status_code=401,
            detail="Invalid bearer token"
        )
    
    return True


def require_auth(use_bearer: bool = False):
    """Authentication dependency factory."""
    if use_bearer:
        return Depends(verify_bearer_token)
    else:
        return Depends(verify_api_key)


# Convenience dependencies
RequireAPIKey = Depends(verify_api_key)
RequireBearer = Depends(verify_bearer_token)