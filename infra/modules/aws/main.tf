module "network" {
  source             = "./network"
  name               = var.name
  ha                 = var.ha
  cidr               = var.network_cidr
  availability_zones = var.availability_zones
  flow_logs_enabled  = var.flow_logs_enabled
  log_retention_days = var.log_retention_days
}
module "ecr" {
  source   = "./ecr"
  name     = var.name
  services = setunion(["frontend", "backend"], var.additional_ecr_services)
}
module "kubernetes" {
  source                  = "./kubernetes"
  name                    = var.name
  ha                      = var.ha
  vpc_id                  = module.network.vpc_id
  network_cidr            = module.network.cidr
  database_egress_cidrs   = module.network.database_egress_cidrs
  subnet_ids              = module.network.private_subnet_ids
  public_cluster_endpoint = var.public_cluster_endpoint
  admin_cidrs             = var.admin_cidrs
  kubernetes_version      = var.kubernetes_version
  node_pool               = var.node_pool
  administrator_arns      = var.administrator_arns
  enable_ssm_access       = var.enable_ssm_access
  log_retention_days      = var.log_retention_days
}
module "postgres" {
  source                 = "./postgres"
  name                   = var.name
  ha                     = var.ha
  vpc_id                 = module.network.vpc_id
  node_security_group_id = module.kubernetes.node_security_group_id
  subnet_group_name      = module.network.database_subnet_group_name
  instance_class         = var.database_instance_class
  database               = var.database
  deletion_protection    = var.deletion_protection
}

module "ci_registry_access" {
  count                      = var.github_repository == "" ? 0 : 1
  source                     = "./ci-registry-access"
  name                       = var.name
  github_repository          = var.github_repository
  github_environment         = var.github_environment
  repository_arns            = [for service in ["frontend", "backend"] : module.ecr.repository_arns[service]]
  existing_oidc_provider_arn = var.github_oidc_provider_arn
  subject_prefix             = var.github_oidc_subject_prefix
}
