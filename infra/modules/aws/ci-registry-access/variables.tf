variable "name" { type = string }
variable "github_repository" { type = string }
variable "github_environment" { type = string }
variable "repository_arns" { type = list(string) }
variable "existing_oidc_provider_arn" {
  type    = string
  default = null
}
variable "subject_prefix" {
  type        = string
  default     = null
  description = "Exact GitHub repo subject segment; use immutable IDs when enabled."
  validation {
    condition = var.subject_prefix == null || (
      can(regex("^repo:[A-Za-z0-9_.-]+(@[0-9]+)?/[A-Za-z0-9_.-]+(@[0-9]+)?$", var.subject_prefix)) &&
      try(replace(var.subject_prefix, "/@[0-9]+/", "") == "repo:${var.github_repository}", false)
    )
    error_message = "Use the exact repo subject segment for github_repository, with optional numeric immutable IDs and no wildcards."
  }
}
