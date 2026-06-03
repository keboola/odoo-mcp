"""
Security patterns for detecting potential vulnerabilities in code changes.

This module defines regex patterns for pre-scanning code before LLM analysis,
and file sensitivity classifications for prioritizing security review focus.

Adapted for Odoo MCP Server: OAuth tokens, XML-RPC calls, MCP protocol security.
"""

# Regex patterns for detecting security issues
# These run as a quick pre-scan before sending to Claude for deeper analysis

SECURITY_PATTERNS = {
    # CRITICAL: Credential exposure in logs or output
    'credential_logging': [
        r'logger\.(info|debug|error|warning|critical)\s*\([^)]*password',
        r'print\s*\([^)]*password',
        r'logging\.(info|debug|error|warning|critical)\s*\([^)]*password',
        r'logger\.(info|debug|error|warning|critical)\s*\([^)]*api_key',
        r'logger\.(info|debug|error|warning|critical)\s*\([^)]*secret',
        r'logger\.(info|debug|error|warning|critical)\s*\([^)]*token(?!ize|_valid)',
        r'logger\.(info|debug|error|warning|critical)\s*\([^)]*bearer',
    ],

    # CRITICAL: Hardcoded credentials
    'hardcoded_credentials': [
        r'password\s*=\s*["\'][^"\']{4,}["\']',
        r'api_key\s*=\s*["\'][^"\']{8,}["\']',
        r'client_secret\s*=\s*["\'][^"\']{8,}["\']',
        r'secret\s*=\s*["\'][^"\']{8,}["\']',
        r'token\s*=\s*["\'][^"\']{10,}["\']',
        r'GOCSPX-',  # Google OAuth client secret prefix
        r'ANTHROPIC_API_KEY\s*=\s*["\'][^"\']+["\']',
        r'GEMINI_API_KEY\s*=\s*["\'][^"\']+["\']',
    ],

    # HIGH: PII in logs
    'pii_logging': [
        r'logger\.(info|debug)\s*\([^)]*email',
        r'logger\.(info|debug)\s*\([^)]*phone',
        r'logger\.(info|debug)\s*\([^)]*employee.*name',
        r'logger\.(info|debug)\s*\([^)]*bank_account',
        r'logger\.(info|debug)\s*\([^)]*identification',
        r'print\s*\([^)]*email',
    ],

    # HIGH: Security control bypass
    'security_bypass': [
        r'yolo_mode\s*=\s*["\']full["\']',  # YOLO mode bypass
        r'verify\s*=\s*False',               # SSL verification disabled
        r'dev_mode\s*=\s*True',              # Dev mode enabled
        r'#.*token_valid',                    # Commented out token validation
        r'pass\s*#.*security',               # Security check passed over
    ],

    # HIGH: Injection risks
    'injection_risks': [
        r'execute_kw\s*\([^)]*f["\']',       # f-string in XML-RPC execute_kw
        r'xmlrpc.*f["\']',                    # f-string in XML-RPC
        r'eval\s*\(',                          # eval() usage
        r'exec\s*\(',                          # exec() usage
        r'subprocess.*shell\s*=\s*True',       # Shell injection risk
        r'os\.system\s*\(',                    # OS command execution
    ],

    # MEDIUM: Error message exposure
    'error_exposure': [
        r'except.*:\s*\n\s*return\s+str\(e\)',   # Raw exception to user
        r'raise\s+.*password',                    # Password in exception
        r'raise\s+.*api_key',                     # API key in exception
        r'raise\s+.*token',                       # Token in exception
        r'HTTPException.*detail=.*password',      # Password in HTTP error
        r'HTTPException.*detail=.*token',         # Token in HTTP error
    ],

    # LOW: Potential issues to flag
    'potential_issues': [
        r'ssl\._create_unverified_context',      # Unverified SSL
        r'random\.',                              # Not cryptographically secure
        r'md5\s*\(',                              # Weak hash
        r'sha1\s*\(',                             # Weak hash
    ],
}

# File sensitivity classification based on filename patterns
# Used to prioritize review focus and add context to findings

FILE_SENSITIVITY = {
    # CRITICAL: Direct credential and auth handling
    'config.py': 'CRITICAL',
    'settings.py': 'CRITICAL',
    'secrets.py': 'CRITICAL',
    '.env': 'CRITICAL',
    'http_server.py': 'CRITICAL',
    'token_validator.py': 'CRITICAL',
    'resource_server.py': 'CRITICAL',

    # HIGH: Core business logic with sensitive operations
    'odoo_client.py': 'HIGH',
    'client.py': 'HIGH',
    'user_mapping.py': 'HIGH',
    'auth.py': 'HIGH',
    'authentication.py': 'HIGH',

    # MEDIUM: Data handling and external services
    'metadata.py': 'MEDIUM',
    'server.py': 'MEDIUM',
    'resources.py': 'MEDIUM',
    'tools.py': 'MEDIUM',

    # LOW: Utilities and tests
    'utils.py': 'LOW',
    'helpers.py': 'LOW',
}

# File patterns for sensitivity (when exact match not found)
FILE_SENSITIVITY_PATTERNS = [
    (r'.*config.*\.py$', 'CRITICAL'),
    (r'.*secret.*\.py$', 'CRITICAL'),
    (r'.*credential.*\.py$', 'CRITICAL'),
    (r'.*oauth.*\.py$', 'CRITICAL'),
    (r'.*token.*\.py$', 'CRITICAL'),
    (r'.*auth.*\.py$', 'HIGH'),
    (r'.*client.*\.py$', 'HIGH'),
    (r'.*service.*\.py$', 'MEDIUM'),
    (r'.*resource.*\.py$', 'MEDIUM'),
    (r'.*tool.*\.py$', 'MEDIUM'),
    (r'.*test.*\.py$', 'LOW'),
    (r'.*_test\.py$', 'LOW'),
]

# OWASP Top 10 2021 categories for structured reporting
OWASP_CATEGORIES = {
    'A01': 'Broken Access Control',
    'A02': 'Cryptographic Failures',
    'A03': 'Injection',
    'A04': 'Insecure Design',
    'A05': 'Security Misconfiguration',
    'A06': 'Vulnerable Components',
    'A07': 'Identification and Authentication Failures',
    'A08': 'Software and Data Integrity Failures',
    'A09': 'Security Logging and Monitoring Failures',
    'A10': 'Server-Side Request Forgery',
}

# Mapping of pattern categories to OWASP categories
PATTERN_TO_OWASP = {
    'credential_logging': 'A09',
    'hardcoded_credentials': 'A02',
    'pii_logging': 'A09',
    'security_bypass': 'A05',
    'injection_risks': 'A03',
    'error_exposure': 'A05',
    'potential_issues': 'A02',
}


def get_file_sensitivity(filename: str) -> str:
    """
    Determine the security sensitivity level of a file.

    Args:
        filename: The name or path of the file

    Returns:
        Sensitivity level: CRITICAL, HIGH, MEDIUM, or LOW
    """
    import os
    import re

    basename = os.path.basename(filename)

    # Check exact matches first
    if basename in FILE_SENSITIVITY:
        return FILE_SENSITIVITY[basename]

    # Check patterns
    for pattern, sensitivity in FILE_SENSITIVITY_PATTERNS:
        if re.match(pattern, filename, re.IGNORECASE):
            return sensitivity

    # Default to MEDIUM for Python files, LOW for others
    if filename.endswith('.py'):
        return 'MEDIUM'
    return 'LOW'


def get_severity_for_category(category: str) -> str:
    """
    Get the default severity level for a pattern category.

    Args:
        category: The pattern category name

    Returns:
        Severity level: CRITICAL, HIGH, MEDIUM, or LOW
    """
    severity_map = {
        'credential_logging': 'CRITICAL',
        'hardcoded_credentials': 'CRITICAL',
        'pii_logging': 'HIGH',
        'security_bypass': 'CRITICAL',
        'injection_risks': 'HIGH',
        'error_exposure': 'MEDIUM',
        'potential_issues': 'LOW',
    }
    return severity_map.get(category, 'MEDIUM')
