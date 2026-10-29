provider "aws" {
  region                      = var.cloud == "aws" ? var.region : "us-east-1"
  access_key                  = var.cloud == "aws" ? null : "unused"
  secret_key                  = var.cloud == "aws" ? null : "unused"
  skip_credentials_validation = var.cloud != "aws"
  skip_requesting_account_id  = var.cloud != "aws"
  skip_metadata_api_check     = var.cloud != "aws"
  default_tags { tags = { Project = var.name, Environment = var.environment, ManagedBy = "terraform" } }
}
provider "google" {
  project      = var.cloud == "gcp" ? var.gcp_project : "unused-project"
  region       = var.cloud == "gcp" ? var.region : "us-central1"
  access_token = var.cloud == "gcp" ? null : "unused"
}
locals {
  name = "${var.name}-${var.environment}"
  ha   = var.environment == "production"
}
module "aws" {
  count               = var.cloud == "aws" ? 1 : 0
  source              = "./modules/aws"
  name                = local.name
  region              = var.region
  admin_cidrs         = var.admin_cidrs
  ha                  = local.ha
  kubernetes_version  = var.kubernetes_version
  deletion_protection = var.deletion_protection
}
module "gcp" {
  count               = var.cloud == "gcp" ? 1 : 0
  source              = "./modules/gcp"
  name                = local.name
  project             = var.gcp_project
  region              = var.region
  admin_cidrs         = var.admin_cidrs
  ha                  = local.ha
  deletion_protection = var.deletion_protection
}
