variable "name" {
  type = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,39}$", var.name))
    error_message = "Use a 3-40 character lowercase resource prefix, starting with a letter."
  }
}
variable "vpc_id" { type = string }
variable "subnet_ids" { type = list(string) }
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
variable "log_retention_days" {
  type = number
  validation {
    condition     = contains([7, 14, 30, 60, 90, 180, 365], var.log_retention_days)
    error_message = "Use a supported bounded log retention: 7, 14, 30, 60, 90, 180 or 365 days."
  }
}
variable "administrator_arns" { type = set(string) }
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

variable "public_cluster_endpoint" {
  type        = bool
  default     = false
  description = "Explicit opt-in to a CIDR-restricted public control plane; default requires private runner connectivity."
}

variable "network_cidr" { type = string }
variable "database_egress_cidrs" { type = list(string) }

variable "enable_ssm_access" {
  type        = bool
  default     = false
  description = "Allow administrator-controlled Session Manager access to private test nodes, with no inbound SSH."
}
