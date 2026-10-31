variable "name" {
  type = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,39}$", var.name))
    error_message = "Use a 3-40 character lowercase resource prefix, starting with a letter."
  }
}
variable "region" { type = string }
variable "network_id" { type = string }
variable "ha" { type = bool }
variable "deletion_protection" { type = bool }
variable "labels" { type = map(string) }
variable "tier" {
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



variable "project" { type = string }
