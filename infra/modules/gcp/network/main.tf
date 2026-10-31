resource "google_project_service" "api" {
  for_each           = toset(["compute.googleapis.com", "container.googleapis.com", "sqladmin.googleapis.com", "servicenetworking.googleapis.com", "iam.googleapis.com", "logging.googleapis.com", "monitoring.googleapis.com"])
  project            = var.project
  service            = each.key
  disable_on_destroy = false
}
resource "google_compute_network" "app" {
  project                         = var.project
  name                            = var.name
  auto_create_subnetworks         = false
  delete_default_routes_on_create = false
  depends_on                      = [google_project_service.api]
}
resource "google_compute_subnetwork" "app" {
  project                  = var.project
  name                     = var.name
  region                   = var.region
  network                  = google_compute_network.app.id
  ip_cidr_range            = var.cidrs.nodes
  private_ip_google_access = true
  dynamic "log_config" {
    for_each = var.flow_logs_enabled ? [1] : []
    content {
      aggregation_interval = "INTERVAL_10_MIN"
      flow_sampling        = 0.1
      metadata             = "EXCLUDE_ALL_METADATA"
    }
  }
  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = var.cidrs.pods
  }
  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = var.cidrs.services
  }
}
resource "google_compute_router" "app" {
  project = var.project
  name    = var.name
  region  = var.region
  network = google_compute_network.app.id
}
resource "google_compute_router_nat" "app" {
  project                            = var.project
  name                               = var.name
  router                             = google_compute_router.app.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}
resource "google_compute_global_address" "sql" {
  project       = var.project
  name          = "${var.name}-sql"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  address       = cidrhost(var.cidrs.sql, 0)
  network       = google_compute_network.app.id
}
resource "google_service_networking_connection" "sql" {
  network                 = google_compute_network.app.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.sql.name]
}
