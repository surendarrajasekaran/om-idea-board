module "network" {
  source            = "./network"
  name              = var.name
  project           = var.project
  region            = var.region
  cidrs             = var.network_cidrs
  flow_logs_enabled = var.flow_logs_enabled
}
module "kubernetes" {
  source                  = "./kubernetes"
  name                    = var.name
  project                 = var.project
  region                  = var.region
  network_id              = module.network.ready
  subnetwork_id           = module.network.subnetwork_id
  master_cidr             = var.network_cidrs.master
  public_cluster_endpoint = var.public_cluster_endpoint
  admin_cidrs             = var.admin_cidrs
  deletion_protection     = var.deletion_protection
  labels                  = var.labels
}
module "postgres" {
  source              = "./postgres"
  project             = var.project
  name                = var.name
  region              = var.region
  network_id          = module.network.ready
  ha                  = var.ha
  tier                = var.database_tier
  database            = var.database
  deletion_protection = var.deletion_protection
  labels              = var.labels
}
