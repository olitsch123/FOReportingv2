# FOReporting v2 Security Guidelines

## Overview

This document outlines security best practices and configurations for FOReporting v2.

## Environment Variables

### Secrets Management

All secrets MUST be stored in the `.env` file, which is:
- **NEVER** committed to version control (included in `.gitignore`)
- **NEVER** hardcoded in source code
- **NEVER** logged or displayed in UI

Required secrets in `.env`:
```env
# Database
DATABASE_URL=postgresql+psycopg://user:password@host:5432/db
POSTGRES_PASSWORD=<strong-password>

# API Keys
OPENAI_API_KEY=sk-...
OPENAI_VECTOR_STORE_ID=vs_...

# JWT (auto-generated if not set)
JWT_SECRET_KEY=<random-32-byte-string>

# Optional Authentication
ADMIN_PASSWORD=<strong-password>
API_KEY_SALT=<random-salt>
```

### Configuration Separation

Non-secret configuration goes in `config/runtime.yaml`:
- Model names
- Scoring weights
- Thresholds
- Feature flags

## Input Validation

### File Uploads
- Maximum file size: 500MB
- Allowed types: PDF, XLSX, CSV, DOCX
- Filename sanitization to prevent directory traversal
- Virus scanning (if configured)

### API Inputs
- All inputs validated with Pydantic models
- SQL injection prevention via parameterized queries
- XSS prevention via HTML escaping
- Path traversal prevention

### Validation Examples

```python
# File path validation
from app.validators import FilePathValidator

validator = FilePathValidator(file_path="/path/to/file.pdf")
# Raises ValueError if path contains .., ~, or other dangerous patterns

# Investor code validation
from app.validators import InvestorCodeValidator

validator = InvestorCodeValidator(investor_code="brainweb")
# Only allows alphanumeric and underscore/hyphen
```

## Authentication & Authorization

### API Authentication (Future)
- JWT tokens with 24-hour expiration
- API keys for service-to-service communication
- Rate limiting per API key

### Session Management
- Secure session cookies (HTTPOnly, Secure, SameSite)
- Session timeout after inactivity
- CSRF protection on state-changing operations

## Data Protection

### Encryption
- All data in transit uses HTTPS
- Database connections use SSL/TLS
- Sensitive data encrypted at rest (if configured)

### Data Sanitization
- PII redaction in logs
- Sensitive field masking in API responses
- Secure file deletion after processing

## Infrastructure Security

### Docker Security
- Non-root user in containers
- Read-only file systems where possible
- Resource limits to prevent DoS
- Security scanning of base images

### Network Security
- Principle of least privilege for service communication
- Database not exposed externally
- Firewall rules limiting ingress/egress

### Monitoring
- Failed authentication attempts logged
- Unusual file access patterns detected
- API rate limit violations tracked

## Development Practices

### Code Security
- Dependency scanning with `pip-audit`
- Static analysis with `bandit`
- Regular dependency updates
- Code review for security issues

### Secret Scanning
- Pre-commit hooks to prevent secret commits
- Regular repository scanning
- Rotation of exposed secrets

## Deployment Security

### Production Checklist
- [ ] All secrets in environment variables
- [ ] Debug mode disabled
- [ ] HTTPS enforced
- [ ] Security headers configured
- [ ] Rate limiting enabled
- [ ] Logging configured (without secrets)
- [ ] Backup encryption enabled
- [ ] Monitoring alerts configured

### Security Headers
```python
# Configured in middleware
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Content-Security-Policy: default-src 'self'
```

## Incident Response

### Security Incidents
1. Isolate affected systems
2. Preserve logs and evidence
3. Notify stakeholders
4. Apply patches/fixes
5. Document lessons learned

### Common Vulnerabilities
- SQL Injection → Use ORM/parameterized queries
- XSS → Escape user input
- CSRF → Use CSRF tokens
- File Upload → Validate type/size/content
- Authentication Bypass → Proper session management

## Compliance

### GDPR Considerations
- User consent for data processing
- Right to deletion implementation
- Data portability features
- Privacy policy compliance

### Audit Trail
- All document access logged
- User actions tracked
- Immutable audit log
- Regular audit reviews

## Updates and Patches

### Security Updates
- Monitor security advisories
- Apply patches promptly
- Test in staging first
- Document all changes

### Dependency Management
```bash
# Check for vulnerabilities
pip-audit

# Update dependencies
pip install --upgrade -r requirements.txt

# Generate security report
safety check
```

## Contact

For security concerns or vulnerability reports:
- Email: security@foreporting.com
- Use PGP encryption for sensitive reports
- Response within 48 hours