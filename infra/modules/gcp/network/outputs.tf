output "network_id" { value = google_compute_network.app.id }
output "subnetwork_id" { value = google_compute_subnetwork.app.id }
output "ready" {
  value      = google_compute_network.app.id
  depends_on = [google_compute_router_nat.app, google_service_networking_connection.sql]
}

output "database_egress_cidrs" { value = [var.cidrs.sql] }
