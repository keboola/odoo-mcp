# -----------------------------------------------------------------------------
# GCP
# -----------------------------------------------------------------------------

variable "gcp_project_id" {
  description = "GCP project ID for Vertex AI and WIF resources"
  type        = string
}

variable "gcp_region" {
  description = "GCP region for Vertex AI"
  type        = string
  default     = "europe-west1"
}

# -----------------------------------------------------------------------------
# GitHub
# -----------------------------------------------------------------------------

variable "github_org" {
  description = "GitHub organization that owns the repository"
  type        = string
}

variable "github_repo_name" {
  description = "Name of the GitHub repository (without org prefix)"
  type        = string
}

# -----------------------------------------------------------------------------
# API Keys
# -----------------------------------------------------------------------------

variable "gemini_api_key" {
  description = "Gemini API key for the AI code reviewer"
  type        = string
  sensitive   = true
}

variable "anthropic_api_key" {
  description = "Anthropic API key for Claude-based security reviewer (optional, uses Vertex AI via WIF instead)"
  type        = string
  sensitive   = true
  default     = ""
}
