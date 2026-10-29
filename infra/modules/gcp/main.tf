resource "google_project_service" "api" {
  for_each           = toset(["compute.googleapis.com", "container.googleapis.com", "sqladmin.googleapis.com", "servicenetworking.googleapis.com"])
  project            = var.project
  service            = each.key
  disable_on_destroy = false
}
resource "google_compute_network" "app" {
  name                    = var.name
  auto_create_subnetworks = false
  depends_on              = [google_project_service.api]
}
resource "google_compute_subnetwork" "app" {
  name                     = var.name
  region                   = var.region
  network                  = google_compute_network.app.id
  ip_cidr_range            = "10.50.0.0/20"
  private_ip_google_access = true
  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.60.0.0/16"
  }
  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.70.0.0/20"
  }
}
resource "google_compute_router" "app" {
  name    = var.name
  region  = var.region
  network = google_compute_network.app.id
}
resource "google_compute_router_nat" "app" {
  name                               = var.name
  router                             = google_compute_router.app.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}
resource "google_compute_global_address" "sql" {
  name          = "${var.name}-sql"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.app.id
}
resource "google_service_networking_connection" "sql" {
  network                 = google_compute_network.app.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.sql.name]
}
resource "google_container_cluster" "app" {
  name                = var.name
  location            = var.region
  network             = google_compute_network.app.id
  subnetwork          = google_compute_subnetwork.app.id
  enable_autopilot    = true
  deletion_protection = var.deletion_protection
  release_channel { channel = "REGULAR" }
  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }
  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }
  master_authorized_networks_config {
    dynamic "cidr_blocks" {
      for_each = var.admin_cidrs
      content {
        cidr_block   = cidr_blocks.value
        display_name = "administrator-${cidr_blocks.key}"
      }
    }
  }
  depends_on = [google_compute_router_nat.app]
}
resource "random_password" "database" {
  length  = 32
  special = false
}
resource "google_sql_database_instance" "ideas" {
  name                = var.name
  region              = var.region
  database_version    = "POSTGRES_16"
  deletion_protection = var.deletion_protection
  settings {
    tier                        = var.ha ? "db-custom-2-7680" : "db-custom-1-3840"
    availability_type           = var.ha ? "REGIONAL" : "ZONAL"
    disk_size                   = 20
    disk_autoresize             = true
    deletion_protection_enabled = var.deletion_protection
    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = 7
    }
    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.app.id
      ssl_mode        = "ENCRYPTED_ONLY"
    }
  }
  depends_on = [google_service_networking_connection.sql]
}
resource "google_sql_database" "ideas" {
  name     = "ideas"
  instance = google_sql_database_instance.ideas.name
}
resource "google_sql_user" "ideas" {
  name     = "ideas"
  instance = google_sql_database_instance.ideas.name
  password = random_password.database.result
}
