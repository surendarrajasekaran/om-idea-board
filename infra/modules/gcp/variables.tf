variable "name" { type = string }
variable "project" {
  type = string
  validation {
    condition     = length(var.project) > 0
    error_message = "gcp_project is required for GCP."
  }
}
variable "region" { type = string }
variable "admin_cidrs" {
  type        = list(string)
  description = "Trusted administrator/runner source IPv4 CIDRs as seen by the selected Kubernetes API endpoint."
  validation {
    condition     = length(var.admin_cidrs) > 0 && alltrue([for cidr in var.admin_cidrs : can(cidrnetmask(cidr)) && try(tonumber(split("/", cidr)[1]) >= 24, false)])
    error_message = "Supply trusted IPv4 administrator/runner CIDRs of /24 or narrower."
  }
}
variable "ha" { type = bool }
variable "deletion_protection" { type = bool }

variable "network_cidrs" {
  type = object({
    nodes    = optional(string, "10.50.0.0/20")
    pods     = optional(string, "10.60.0.0/16")
    services = optional(string, "10.70.0.0/20")
    master   = optional(string, "172.16.0.0/28")
    sql      = optional(string, "10.80.0.0/16")
  })
  default = {}
  validation {
    condition = alltrue([for cidr in values(var.network_cidrs) : can(cidrnetmask(cidr))]) && try(
      tonumber(split("/", var.network_cidrs.master)[1]) == 28 && tonumber(split("/", var.network_cidrs.sql)[1]) == 16, false
    )
    error_message = "Supply IPv4 CIDRs; master must be /28 and SQL /16."
  }
  validation {
    condition = alltrue(flatten([for a in values(var.network_cidrs) : [for b in values(var.network_cidrs) :
      a == b ? false : try(cidrhost("${split("/", a)[0]}/${min(tonumber(split("/", a)[1]), tonumber(split("/", b)[1]))}", 0) != cidrhost("${split("/", b)[0]}/${min(tonumber(split("/", a)[1]), tonumber(split("/", b)[1]))}", 0), false)
      if a != b
    ]])) && length(distinct(values(var.network_cidrs))) == 5
    error_message = "Node, pod, service, control-plane and SQL ranges must not overlap."
  }
}


variable "database_tier" {
  type     = string
  default  = null
  nullable = true
}

variable "database" {
  type = object({
    name               = optional(string, "ideas")
    storage_gb         = optional(number, 20)
    max_storage_gb     = optional(number, 100)
    backup_days        = optional(number, 7)
    log_retention_days = optional(number, 14)
  })
  default = {}
  validation {
    condition = (
      can(regex("^[a-z][a-z0-9_]{0,30}$", var.database.name)) &&
      var.database.storage_gb >= 20 && var.database.max_storage_gb >= var.database.storage_gb &&
      var.database.backup_days >= 7 && var.database.backup_days <= 35 &&
      contains([7, 14, 30, 60, 90, 180, 365], var.database.log_retention_days) &&
      alltrue([for n in [var.database.storage_gb, var.database.max_storage_gb, var.database.backup_days] : n == floor(n)])
    )
    error_message = "Use a safe database name, integer storage >= 20 GiB, max >= initial, backups 7-35 days and bounded log retention."
  }
}



variable "flow_logs_enabled" { type = bool }
variable "log_retention_days" { type = number }
variable "labels" { type = map(string) }

variable "public_cluster_endpoint" {
  type        = bool
  default     = false
  description = "Explicit opt-in to a CIDR-restricted public control plane; default requires private runner connectivity."
}
