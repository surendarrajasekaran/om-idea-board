variable "name" {
  type = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,39}$", var.name))
    error_message = "Use a 3-40 character lowercase resource prefix, starting with a letter."
  }
}
variable "project" { type = string }
variable "region" { type = string }
variable "flow_logs_enabled" { type = bool }
variable "cidrs" {
  type = object({
    nodes    = optional(string, "10.50.0.0/20")
    pods     = optional(string, "10.60.0.0/16")
    services = optional(string, "10.70.0.0/20")
    master   = optional(string, "172.16.0.0/28")
    sql      = optional(string, "10.80.0.0/16")
  })
  default = {}
  validation {
    condition = alltrue([for cidr in values(var.cidrs) : can(cidrnetmask(cidr))]) && try(
      tonumber(split("/", var.cidrs.master)[1]) == 28 && tonumber(split("/", var.cidrs.sql)[1]) == 16, false
    )
    error_message = "Supply IPv4 CIDRs; master must be /28 and SQL /16."
  }
  validation {
    condition = alltrue(flatten([for a in values(var.cidrs) : [for b in values(var.cidrs) :
      a == b ? false : try(cidrhost("${split("/", a)[0]}/${min(tonumber(split("/", a)[1]), tonumber(split("/", b)[1]))}", 0) != cidrhost("${split("/", b)[0]}/${min(tonumber(split("/", a)[1]), tonumber(split("/", b)[1]))}", 0), false)
      if a != b
    ]])) && length(distinct(values(var.cidrs))) == 5
    error_message = "Node, pod, service, control-plane and SQL ranges must not overlap."
  }
}
