output "cluster_name" {
  value = var.cloud == "aws" ? module.aws[0].cluster_name : module.gcp[0].cluster_name
}
output "database_url" {
  description = "Sensitive SQLAlchemy connection URI; deliver to the common chart's existing Secret."
  sensitive   = true
  value       = var.cloud == "aws" ? module.aws[0].database_url : module.gcp[0].database_url
}
output "cloud" { value = var.cloud }
output "region" { value = var.region }
output "environment" { value = var.environment }
output "gcp_project" { value = var.gcp_project }
