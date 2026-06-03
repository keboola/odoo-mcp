output "workload_identity_provider" {
  description = "The full resource name of the WIF provider for GitHub Actions"
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "service_account_email" {
  description = "The email of the security reviewer service account"
  value       = google_service_account.security_reviewer.email
}
