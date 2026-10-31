variable "additional_ecr_services" {
  type    = set(string)
  default = []
}

variable "name" { type = string }
variable "region" { type = string }
variable "admin_cidrs" {
  type        = list(string)
  description = "Trusted administrator/runner source IPv4 CIDRs as seen by the selected Kubernetes API endpoint."
  validation {
    condition     = length(var.admin_cidrs) > 0 && alltrue([for cidr in var.admin_cidrs : can(cidrnetmask(cidr)) && try(tonumber(split("/", cidr)[1]) >= 24, false)])
    error_message = "Supply trusted IPv4 administrator/runner CIDRs of /24 or narrower."
  }
  validation {
    condition     = !var.public_cluster_endpoint || alltrue([for cidr in var.admin_cidrs : !can(regex("^(0[.]|10[.]|127[.]|169[.]254[.]|172[.](1[6-9]|2[0-9]|3[01])[.]|192[.]168[.])", cidrhost(cidr, 0)))])
    error_message = "AWS public endpoint allowlists require public source CIDRs; private CIDRs only apply to private routing."
  }
}
variable "ha" { type = bool }
variable "kubernetes_version" { type = string }
variable "deletion_protection" { type = bool }

variable "network_cidr" {
  type    = string
  default = "10.40.0.0/16"
  validation {
    condition     = can(cidrnetmask(var.network_cidr)) && try(tonumber(split("/", var.network_cidr)[1]) == 16, false)
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

variable "node_pool" {
  type = object({
    instance_types = optional(list(string), ["t3.medium"])
    min_size       = optional(number, 1)
    desired_size   = optional(number, 1)
    max_size       = optional(number, 3)
    disk_size      = optional(number, 20)
    capacity_type  = optional(string, "ON_DEMAND")
  })
  default = {}
  validation {
    condition = (
      var.node_pool.min_size >= 1 && var.node_pool.min_size <= var.node_pool.desired_size &&
      var.node_pool.desired_size <= var.node_pool.max_size &&
      alltrue([for n in [var.node_pool.min_size, var.node_pool.desired_size, var.node_pool.max_size, var.node_pool.disk_size] : n == floor(n)]) &&
      var.node_pool.disk_size >= 20 && length(var.node_pool.instance_types) > 0 &&
      contains(["ON_DEMAND", "SPOT"], var.node_pool.capacity_type)
    )
    error_message = "Use nonempty instance types, integer 1 <= min <= desired <= max, disk >= 20 GiB, and ON_DEMAND or SPOT."
  }
  validation {
    condition     = !var.ha || (var.node_pool.max_size >= 2 && var.node_pool.capacity_type == "ON_DEMAND")
    error_message = "Production requires max_size >= 2 and an on-demand baseline."
  }
}


variable "database_instance_class" {
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
variable "administrator_arns" { type = set(string) }

variable "public_cluster_endpoint" {
  type        = bool
  default     = false
  description = "Explicit opt-in to a CIDR-restricted public control plane; default requires private runner connectivity."
}

variable "enable_ssm_access" {
  type        = bool
  default     = false
  description = "Allow administrator-controlled Session Manager access to private test nodes, with no inbound SSH."
}

variable "github_repository" {
  type        = string
  default     = ""
  description = "Exact owner/repository permitted to push release images through OIDC."
  validation {
    condition     = var.github_repository == "" || can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "Use an exact owner/repository, without wildcards."
  }
}

variable "github_environment" {
  type    = string
  default = ""
  validation {
    condition     = var.github_repository == "" || can(regex("^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$", var.github_environment))
    error_message = "An exact GitHub environment is required when enabling CI registry access."
  }
}

variable "github_oidc_provider_arn" {
  type        = string
  default     = null
  description = "Reuse the account's GitHub OIDC provider; bootstrap creates it once when absent."
}
