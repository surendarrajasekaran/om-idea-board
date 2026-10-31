variable "name" {
  type = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,39}$", var.name))
    error_message = "Use a 3-40 character lowercase resource prefix, starting with a letter."
  }
}
variable "ha" { type = bool }
variable "cidr" {
  type    = string
  default = "10.40.0.0/16"
  validation {
    condition     = can(cidrnetmask(var.cidr)) && try(tonumber(split("/", var.cidr)[1]) == 16, false)
    error_message = "Use an IPv4 /16 VPC; six /24 subnets are derived without overlapping."
  }
}
variable "availability_zones" {
  type    = list(string)
  default = []
  validation {
    condition     = length(var.availability_zones) == 0 || (length(var.availability_zones) == 2 && length(distinct(var.availability_zones)) == 2)
    error_message = "Supply exactly two distinct availability zones, or leave empty for discovery."
  }
}
variable "flow_logs_enabled" { type = bool }
variable "log_retention_days" {
  type = number
  validation {
    condition     = contains([7, 14, 30, 60, 90, 180, 365], var.log_retention_days)
    error_message = "Use a supported bounded log retention: 7, 14, 30, 60, 90, 180 or 365 days."
  }
}
