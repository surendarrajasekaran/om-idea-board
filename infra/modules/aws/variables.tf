variable "name" { type = string }
variable "region" { type = string }
variable "admin_cidrs" { type = list(string) }
variable "ha" { type = bool }
variable "kubernetes_version" { type = string }
variable "deletion_protection" { type = bool }
