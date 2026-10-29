variable "name" { type = string }
variable "project" {
  type = string
  validation {
    condition     = length(var.project) > 0
    error_message = "gcp_project is required for GCP."
  }
}
variable "region" { type = string }
variable "admin_cidrs" { type = list(string) }
variable "ha" { type = bool }
variable "deletion_protection" { type = bool }
