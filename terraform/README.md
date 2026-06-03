# Terraform — Optional Reviewer Infrastructure

This is an **optional, reference** Terraform setup that provisions the cloud
resources for the AI/security pull-request reviewers in `.github/workflows/`.
You do **not** need it to run the MCP server — only if you want the automated
PR reviewers enabled on your fork.

It creates:

- A GCP service account + IAM binding for **Vertex AI** (used by the security
  reviewer, which calls Claude via Vertex).
- A **Workload Identity Federation** pool/provider so GitHub Actions can
  impersonate that service account without long-lived keys.
- The GitHub Actions **secrets** the workflows expect
  (`GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_SERVICE_ACCOUNT`, `VERTEX_PROJECT_ID`,
  `GEMINI_API_KEY`, and optionally `ANTHROPIC_API_KEY`).

## Usage

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars   # then edit values
terraform init
terraform plan
terraform apply
```

You will need:

- A GCP project with billing enabled and permission to create service accounts,
  IAM bindings, and a Workload Identity pool.
- A GitHub token with `repo` scope for the `github` provider
  (`export GITHUB_TOKEN=...`).
- A Gemini API key (for the general reviewer).

The default Terraform backend is `local`. Point `backend.tf` at a remote backend
(GCS bucket, Terraform Cloud, etc.) if you want shared state.

## Not using the reviewers?

Delete the `ai-review.yml` and `security-review.yml` workflows and this
`terraform/` directory. The rest of the project (server + `ci.yml`) works
without them.
