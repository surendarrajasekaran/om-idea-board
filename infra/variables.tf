variable "cloud" {
  type        = string
  description = "Cloud adapter: aws or gcp."
  validation {
    condition     = contains(["aws", "gcp"], var.cloud)
    error_message = "cloud must be aws or gcp."
  }
}
variable "name" {
  type    = string
  default = "idea-board"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,20}$", var.name))
    error_message = "Use 3-21 lowercase letters, digits, or hyphens, starting with a letter."
  }
}
variable "environment" {
  type    = string
  default = "staging"
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "Use staging or production."
  }
}
variable "region" {
  type = string
}
variable "gcp_project" {
  type    = string
  default = ""
}
variable "admin_cidrs" {
  type        = list(string)
  description = "Trusted administrator/runner public IPv4 CIDRs for the Kubernetes API."
  validation {
    condition     = length(var.admin_cidrs) > 0 && alltrue([for cidr in var.admin_cidrs : can(cidrnetmask(cidr)) && cidr != "0.0.0.0/0"])
    error_message = "Supply valid restricted IPv4 CIDRs; 0.0.0.0/0 is forbidden."
  }
}
variable "kubernetes_version" {
  type    = string
  default = "1.33"
}
variable "deletion_protection" {
  type    = bool
  default = true
}
