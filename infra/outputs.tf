output "cluster_name" {
  value = var.cloud == "aws" ? module.aws[0].cluster_name : module.gcp[0].cluster_name
}
output "database_url" {
  description = "Sensitive SQLAlchemy connection URI; deliver to the common chart's existing Secret."
  sensitive   = true
  value       = var.cloud == "aws" ? module.aws[0].database_url : module.gcp[0].database_url
}
output "cloud" { value = var.cloud }
output "repository_urls" { value = var.cloud == "aws" ? module.aws[0].repository_urls : {} }
output "region" { value = var.region }
output "environment" { value = var.environment }
output "gcp_project" { value = var.gcp_project }

output "name" { value = var.name }
output "migration_database_url" {
  value     = var.cloud == "aws" ? module.aws[0].migration_database_url : module.gcp[0].migration_database_url
  sensitive = true
}
output "application_password" {
  value     = var.cloud == "aws" ? module.aws[0].application_password : module.gcp[0].application_password
  sensitive = true
}
output "database_host" {
  value = var.cloud == "aws" ? module.aws[0].database_host : module.gcp[0].database_host
}

output "database_egress_cidrs" { value = var.cloud == "aws" ? module.aws[0].database_egress_cidrs : module.gcp[0].database_egress_cidrs }

output "database_ca_certificate" {
  sensitive = true
  value     = var.cloud == "aws" ? module.aws[0].database_ca_certificate : module.gcp[0].database_ca_certificate
}

output "ecr_push_role_arn" { value = var.cloud == "aws" ? module.aws[0].ecr_push_role_arn : null }
