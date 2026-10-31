resource "google_container_cluster" "app" {
  project           = var.project
  name              = var.name
  location          = var.region
  network           = var.network_id
  subnetwork        = var.subnetwork_id
  enable_autopilot  = true
  resource_labels   = var.labels
  datapath_provider = "ADVANCED_DATAPATH"
  cluster_autoscaling {
    auto_provisioning_defaults {
      service_account = google_service_account.nodes.email
      oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
    }
  }
  logging_config { enable_components = ["SYSTEM_COMPONENTS", "WORKLOADS"] }
  monitoring_config { enable_components = ["SYSTEM_COMPONENTS"] }
  deletion_protection = var.deletion_protection
  depends_on          = [google_project_iam_member.nodes]
  release_channel { channel = "REGULAR" }
  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }
  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = !var.public_cluster_endpoint
    master_ipv4_cidr_block  = var.master_cidr
  }
  master_authorized_networks_config {
    private_endpoint_enforcement_enabled = true
    gcp_public_cidrs_access_enabled      = false
    dynamic "cidr_blocks" {
      for_each = var.admin_cidrs
      content {
        cidr_block   = cidr_blocks.value
        display_name = "administrator-${cidr_blocks.key}"
      }
    }
  }
}

resource "google_service_account" "nodes" {
  project      = var.project
  account_id   = "${substr(var.name, 0, 18)}-${substr(sha256(var.name), 0, 5)}-nodes"
  display_name = "${var.name} GKE nodes (no application permissions)"
}
resource "google_project_iam_member" "nodes" {
  project = var.project
  role    = "roles/container.defaultNodeServiceAccount"
  member  = "serviceAccount:${google_service_account.nodes.email}"
}
