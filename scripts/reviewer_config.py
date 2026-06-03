"""Centralized configuration for AI code reviewers (security + general).

All reviewer settings are loaded from environment variables with sensible defaults.
Required variables (API keys) should be set in the CI workflow or GitHub secrets.
"""
import os

# =============================================================================
# Security Reviewer (Claude via Vertex AI)
# =============================================================================

VERTEX_PROJECT_ID = os.environ.get("VERTEX_PROJECT_ID", "")
VERTEX_REGION = os.environ.get("VERTEX_REGION", "europe-west1")
SECURITY_MODEL = os.environ.get("SECURITY_REVIEWER_MODEL", "claude-opus-4-6")
SECURITY_MAX_TOKENS = int(os.environ.get("SECURITY_REVIEWER_MAX_TOKENS", "8192"))
SECURITY_MAX_FILES = int(os.environ.get("SECURITY_REVIEWER_MAX_FILES", "15"))
SECURITY_MAX_FILE_SIZE = int(os.environ.get("SECURITY_REVIEWER_MAX_FILE_SIZE", "25000"))
SECURITY_MAX_PRESCAN_FINDINGS = int(os.environ.get("SECURITY_REVIEWER_MAX_PRESCAN", "20"))


# =============================================================================
# AI Code Reviewer (Gemini)
# =============================================================================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODELS = os.environ.get("AI_REVIEWER_MODELS", "gemini-flash-latest,gemini-pro-latest").split(",")
GEMINI_MAX_FILE_SIZE = int(os.environ.get("AI_REVIEWER_MAX_FILE_SIZE", "20000"))


# =============================================================================
# Shared Settings
# =============================================================================

API_TIMEOUT = int(os.environ.get("REVIEWER_API_TIMEOUT", "30"))
