provider "aws" {
  allowed_account_ids         = var.cloud == "aws" && var.aws_account_id != null ? [var.aws_account_id] : null
  region                      = var.cloud == "aws" ? var.region : "us-east-1"
  access_key                  = var.cloud == "aws" ? null : "unused"
  secret_key                  = var.cloud == "aws" ? null : "unused"
  skip_credentials_validation = var.cloud != "aws"
  skip_requesting_account_id  = var.cloud != "aws"
  skip_metadata_api_check     = var.cloud != "aws"
  default_tags { tags = merge(var.labels, { project = var.name, environment = var.environment, managed_by = "terraform" }) }
}
provider "google" {
  project      = var.cloud == "gcp" ? var.gcp_project : "unused-project"
  region       = var.cloud == "gcp" ? var.region : "us-central1"
  access_token = var.cloud == "gcp" ? null : "unused"
}
locals {
  name   = "${var.name}-${var.environment}"
  ha     = var.environment == "production"
  labels = merge(var.labels, { project = var.name, environment = var.environment, managed_by = "terraform" })
}
module "aws" {
  count                    = var.cloud == "aws" ? 1 : 0
  source                   = "./modules/aws"
  name                     = local.name
  region                   = var.region
  public_cluster_endpoint  = var.public_cluster_endpoint
  admin_cidrs              = var.admin_cidrs
  ha                       = local.ha
  kubernetes_version       = var.kubernetes_version
  deletion_protection      = var.deletion_protection
  network_cidr             = var.aws_network_cidr
  availability_zones       = var.aws_availability_zones
  node_pool                = var.aws_node_pool
  database_instance_class  = var.aws_database_instance_class
  database                 = var.database
  administrator_arns       = var.aws_administrator_arns
  enable_ssm_access        = var.aws_enable_ssm_access
  github_repository        = var.github_repository
  github_oidc_provider_arn = var.github_oidc_provider_arn
  github_environment       = "aws-${var.environment}"
  flow_logs_enabled        = var.flow_logs_enabled
  log_retention_days       = var.log_retention_days
}
module "gcp" {
  count                   = var.cloud == "gcp" ? 1 : 0
  source                  = "./modules/gcp"
  name                    = local.name
  project                 = var.gcp_project
  region                  = var.region
  public_cluster_endpoint = var.public_cluster_endpoint
  admin_cidrs             = var.admin_cidrs
  ha                      = local.ha
  deletion_protection     = var.deletion_protection
  network_cidrs           = var.gcp_network_cidrs
  database_tier           = var.gcp_database_tier
  database                = var.database
  labels                  = local.labels
  flow_logs_enabled       = var.flow_logs_enabled
  log_retention_days      = var.log_retention_days
}
