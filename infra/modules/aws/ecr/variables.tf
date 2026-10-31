variable "name" {
  type        = string
  description = "Repository prefix, normally application-environment."
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,39}$", var.name))
    error_message = "Use a 3-40 character lowercase repository prefix."
  }
}
variable "services" {
  type    = set(string)
  default = ["frontend", "backend"]
  validation {
    condition     = length(var.services) > 0 && alltrue([for service in var.services : can(regex("^[a-z][a-z0-9-]{0,39}$", service))])
    error_message = "Supply safe, nonempty service names."
  }
}
variable "untagged_retention_days" {
  type    = number
  default = 7
  validation {
    condition     = var.untagged_retention_days >= 1 && var.untagged_retention_days <= 365 && floor(var.untagged_retention_days) == var.untagged_retention_days
    error_message = "Keep untagged images for an integer 1-365 days."
  }
}
