"""Rate limiting for API endpoints."""

import time
from collections import defaultdict, deque
from typing import Dict, Optional

from fastapi import HTTPException, Request

from app.exceptions import APIError


class RateLimiter:
    """Simple in-memory rate limiter for API endpoints."""
    
    def __init__(self):
        """Initialize rate limiter."""
        self.requests: Dict[str, deque] = defaultdict(deque)
        self.blocked_ips: Dict[str, float] = {}
    
    def is_allowed(
        self, 
        client_ip: str, 
        requests_per_minute: int = 60,
        burst_limit: int = 10,
        block_duration: int = 300  # 5 minutes
    ) -> bool:
        """
        Check if request is allowed based on rate limits.
        
        Args:
            client_ip: Client IP address
            requests_per_minute: Requests allowed per minute
            burst_limit: Burst limit for short periods
            block_duration: How long to block after limit exceeded (seconds)
            
        Returns:
            True if request is allowed
            
        Raises:
            HTTPException: If rate limit exceeded
        """
        current_time = time.time()
        
        # Check if IP is currently blocked
        if client_ip in self.blocked_ips:
            if current_time < self.blocked_ips[client_ip]:
                time_remaining = int(self.blocked_ips[client_ip] - current_time)
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. Try again in {time_remaining} seconds.",
                    headers={"Retry-After": str(time_remaining)}
                )
            else:
                # Block expired, remove from blocked list
                del self.blocked_ips[client_ip]
        
        # Clean old requests (older than 1 minute)
        minute_ago = current_time - 60
        while self.requests[client_ip] and self.requests[client_ip][0] < minute_ago:
            self.requests[client_ip].popleft()
        
        # Check burst limit (last 10 seconds)
        ten_seconds_ago = current_time - 10
        recent_requests = sum(1 for req_time in self.requests[client_ip] if req_time > ten_seconds_ago)
        
        if recent_requests >= burst_limit:
            # Block the IP
            self.blocked_ips[client_ip] = current_time + block_duration
            raise HTTPException(
                status_code=429,
                detail=f"Burst limit exceeded. Blocked for {block_duration} seconds.",
                headers={"Retry-After": str(block_duration)}
            )
        
        # Check requests per minute limit
        if len(self.requests[client_ip]) >= requests_per_minute:
            # Block the IP
            self.blocked_ips[client_ip] = current_time + block_duration
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Blocked for {block_duration} seconds.",
                headers={"Retry-After": str(block_duration)}
            )
        
        # Record this request
        self.requests[client_ip].append(current_time)
        return True
    
    def get_client_ip(self, request: Request) -> str:
        """Extract client IP from request, handling proxies."""
        # Check for forwarded IP headers (for load balancers/proxies)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct client IP
        return request.client.host if request.client else "unknown"
    
    def cleanup_old_entries(self):
        """Cleanup old entries to prevent memory leaks."""
        current_time = time.time()
        
        # Remove old request records
        for client_ip in list(self.requests.keys()):
            minute_ago = current_time - 60
            while self.requests[client_ip] and self.requests[client_ip][0] < minute_ago:
                self.requests[client_ip].popleft()
            
            # Remove empty deques
            if not self.requests[client_ip]:
                del self.requests[client_ip]
        
        # Remove expired blocks
        for client_ip in list(self.blocked_ips.keys()):
            if current_time >= self.blocked_ips[client_ip]:
                del self.blocked_ips[client_ip]


# Global rate limiter instance
rate_limiter = RateLimiter()


def check_rate_limit(request: Request, requests_per_minute: int = 60) -> bool:
    """
    Dependency to check rate limits for endpoints.
    
    Args:
        request: FastAPI request object
        requests_per_minute: Rate limit threshold
        
    Returns:
        True if allowed
        
    Raises:
        HTTPException: If rate limit exceeded
    """
    client_ip = rate_limiter.get_client_ip(request)
    return rate_limiter.is_allowed(client_ip, requests_per_minute)


def check_processing_rate_limit(request: Request) -> bool:
    """Stricter rate limit for processing endpoints."""
    return check_rate_limit(request, requests_per_minute=10)


def check_chat_rate_limit(request: Request) -> bool:
    """Rate limit for chat/AI endpoints."""
    return check_rate_limit(request, requests_per_minute=30)