output "cluster_name" { value = module.kubernetes.cluster_name }
output "repository_urls" { value = module.ecr.repository_urls }
output "repository_arns" { value = module.ecr.repository_arns }
output "database_url" {
  value     = module.postgres.database_url
  sensitive = true
}
output "migration_database_url" {
  value     = module.postgres.migration_database_url
  sensitive = true
}
output "application_password" {
  value     = module.postgres.application_password
  sensitive = true
}
output "database_host" {
  value = module.postgres.database_host
}

output "database_egress_cidrs" { value = module.network.database_egress_cidrs }

output "database_ca_certificate" {
  sensitive = true
  value     = module.postgres.database_ca_certificate
}

output "ecr_push_role_arn" { value = var.github_repository == "" ? null : module.ci_registry_access[0].role_arn }
