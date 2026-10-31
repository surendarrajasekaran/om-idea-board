variable "aws_additional_ecr_services" {
  type        = set(string)
  default     = []
  description = "Additional platform image repositories; application CI cannot publish to these."
}

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
    condition     = contains(["test", "staging", "production"], var.environment)
    error_message = "Use test, staging or production."
  }
}
variable "aws_account_id" {
  type        = string
  default     = null
  description = "Optional expected account guard; set for real AWS plans/applies."
  validation {
    condition     = var.aws_account_id == null ? true : can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "Expected AWS account ID must contain 12 digits."
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
  description = "Trusted administrator/runner source IPv4 CIDRs as seen by the selected Kubernetes API endpoint."
  validation {
    condition     = length(var.admin_cidrs) > 0 && alltrue([for cidr in var.admin_cidrs : can(cidrnetmask(cidr)) && try(tonumber(split("/", cidr)[1]) >= 24, false)])
    error_message = "Supply trusted IPv4 administrator/runner CIDRs of /24 or narrower."
  }
}
variable "kubernetes_version" {
  type    = string
  default = "1.35"
}
variable "deletion_protection" {
  type    = bool
  default = true
}

variable "aws_network_cidr" {
  type    = string
  default = "10.40.0.0/16"
  validation {
    condition     = can(cidrnetmask(var.aws_network_cidr)) && try(tonumber(split("/", var.aws_network_cidr)[1]) == 16, false)
    error_message = "Use an IPv4 /16 VPC; six /24 subnets are derived without overlapping."
  }
}


variable "aws_availability_zones" {
  type    = list(string)
  default = []
  validation {
    condition     = length(var.aws_availability_zones) == 0 || (length(var.aws_availability_zones) == 2 && length(distinct(var.aws_availability_zones)) == 2)
    error_message = "Supply exactly two distinct availability zones, or leave empty for discovery."
  }
}


variable "aws_node_pool" {
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
      var.aws_node_pool.min_size >= 1 && var.aws_node_pool.min_size <= var.aws_node_pool.desired_size &&
      var.aws_node_pool.desired_size <= var.aws_node_pool.max_size &&
      alltrue([for n in [var.aws_node_pool.min_size, var.aws_node_pool.desired_size, var.aws_node_pool.max_size, var.aws_node_pool.disk_size] : n == floor(n)]) &&
      var.aws_node_pool.disk_size >= 20 && length(var.aws_node_pool.instance_types) > 0 &&
      contains(["ON_DEMAND", "SPOT"], var.aws_node_pool.capacity_type)
    )
    error_message = "Use nonempty instance types, integer 1 <= min <= desired <= max, disk >= 20 GiB, and ON_DEMAND or SPOT."
  }
  validation {
    condition     = var.environment != "production" || (var.aws_node_pool.max_size >= 2 && var.aws_node_pool.capacity_type == "ON_DEMAND")
    error_message = "Production requires max_size >= 2 and an on-demand baseline."
  }
}



variable "aws_database_instance_class" {
  type     = string
  default  = null
  nullable = true
}


variable "gcp_network_cidrs" {
  type = object({
    nodes    = optional(string, "10.50.0.0/20")
    pods     = optional(string, "10.60.0.0/16")
    services = optional(string, "10.70.0.0/20")
    master   = optional(string, "172.16.0.0/28")
    sql      = optional(string, "10.80.0.0/16")
  })
  default = {}
  validation {
    condition = alltrue([for cidr in values(var.gcp_network_cidrs) : can(cidrnetmask(cidr))]) && try(
      tonumber(split("/", var.gcp_network_cidrs.master)[1]) == 28 && tonumber(split("/", var.gcp_network_cidrs.sql)[1]) == 16, false
    )
    error_message = "Supply IPv4 CIDRs; master must be /28 and SQL /16."
  }
  validation {
    condition = alltrue(flatten([for a in values(var.gcp_network_cidrs) : [for b in values(var.gcp_network_cidrs) :
      a == b ? false : try(cidrhost("${split("/", a)[0]}/${min(tonumber(split("/", a)[1]), tonumber(split("/", b)[1]))}", 0) != cidrhost("${split("/", b)[0]}/${min(tonumber(split("/", a)[1]), tonumber(split("/", b)[1]))}", 0), false)
      if a != b
    ]])) && length(distinct(values(var.gcp_network_cidrs))) == 5
    error_message = "Node, pod, service, control-plane and SQL ranges must not overlap."
  }
}



variable "gcp_database_tier" {
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


variable "flow_logs_enabled" {
  type        = bool
  default     = true
  description = "Collect network flow evidence. Disable only after accepting the observability gap."
}
variable "log_retention_days" {
  type    = number
  default = 14
  validation {
    condition     = contains([7, 14, 30, 60, 90, 180, 365], var.log_retention_days)
    error_message = "Use a supported bounded log retention: 7, 14, 30, 60, 90, 180 or 365 days."
  }
}
variable "aws_administrator_arns" {
  type        = set(string)
  default     = []
  description = "Additional stable IAM role ARNs for EKS administration, separate from the creator."
  validation {
    condition     = alltrue([for arn in var.aws_administrator_arns : can(regex("^arn:aws[a-z-]*:iam::[0-9]{12}:role/[A-Za-z0-9+=,.@_/-]+$", arn))])
    error_message = "Use IAM role ARNs, never STS session ARNs or wildcard principals."
  }
}
variable "labels" {
  type        = map(string)
  default     = {}
  description = "Cost ownership labels/tags; project, environment and managed_by are reserved."
  validation {
    condition     = alltrue([for k, v in var.labels : can(regex("^[a-z][a-z0-9_-]{0,62}$", k)) && can(regex("^[a-z0-9_-]{0,63}$", v))])
    error_message = "Use portable lowercase GCP label keys/values (up to 63 characters)."
  }
}

variable "public_cluster_endpoint" {
  type        = bool
  default     = false
  description = "Explicit opt-in to a CIDR-restricted public control plane; default requires private runner connectivity."
}

variable "aws_enable_ssm_access" {
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

variable "github_oidc_provider_arn" {
  type        = string
  default     = null
  description = "Reuse the account's GitHub OIDC provider; bootstrap creates it once when absent."
}
