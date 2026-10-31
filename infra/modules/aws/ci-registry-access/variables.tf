variable "name" { type = string }
variable "github_repository" { type = string }
variable "github_environment" { type = string }
variable "repository_arns" { type = list(string) }
variable "existing_oidc_provider_arn" {
  type    = string
  default = null
}
