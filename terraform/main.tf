# =============================================================================
# A) GCP Resources - Vertex AI, Service Account, Workload Identity Federation
# =============================================================================

# Enable Vertex AI API
resource "google_project_service" "vertex_ai" {
  project            = var.gcp_project_id
  service            = "aiplatform.googleapis.com"
  disable_on_destroy = false
}

# Service account for GitHub Actions security reviewer
resource "google_service_account" "security_reviewer" {
  project      = var.gcp_project_id
  account_id   = "gh-odoo-mcp-security-reviewer"
  display_name = "GitHub Actions Security Reviewer (odoo-mcp-server)"
}

# Grant Vertex AI User role to the service account
resource "google_project_iam_member" "vertex_ai_user" {
  project = var.gcp_project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.security_reviewer.email}"
}

# Workload Identity Pool for GitHub Actions (separate pool for this repo)
resource "google_iam_workload_identity_pool" "github" {
  project                   = var.gcp_project_id
  workload_identity_pool_id = "github-actions-odoo-mcp"
  display_name              = "GitHub Actions (odoo-mcp-server)"
}

# OIDC Provider for GitHub
resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.gcp_project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-oidc"
  display_name                       = "GitHub OIDC"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
  }

  attribute_condition = "assertion.repository == '${var.github_org}/${var.github_repo_name}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# Allow GitHub Actions to impersonate the service account via WIF
resource "google_service_account_iam_member" "wif_impersonation" {
  service_account_id = google_service_account.security_reviewer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_org}/${var.github_repo_name}"
}

# =============================================================================
# B) GitHub Secrets - GCP / Reviewer
# =============================================================================

resource "github_actions_secret" "gcp_workload_identity_provider" {
  repository      = var.github_repo_name
  secret_name     = "GCP_WORKLOAD_IDENTITY_PROVIDER"
  plaintext_value = google_iam_workload_identity_pool_provider.github.name
}

resource "github_actions_secret" "gcp_service_account" {
  repository      = var.github_repo_name
  secret_name     = "GCP_SERVICE_ACCOUNT"
  plaintext_value = google_service_account.security_reviewer.email
}

resource "github_actions_secret" "vertex_project_id" {
  repository      = var.github_repo_name
  secret_name     = "VERTEX_PROJECT_ID"
  plaintext_value = var.gcp_project_id
}

resource "github_actions_secret" "gemini_api_key" {
  repository      = var.github_repo_name
  secret_name     = "GEMINI_API_KEY"
  plaintext_value = var.gemini_api_key
}

resource "github_actions_secret" "anthropic_api_key" {
  count           = var.anthropic_api_key != "" ? 1 : 0
  repository      = var.github_repo_name
  secret_name     = "ANTHROPIC_API_KEY"
  plaintext_value = var.anthropic_api_key
}
