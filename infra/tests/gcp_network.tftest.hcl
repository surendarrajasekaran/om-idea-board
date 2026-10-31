mock_provider "google" {}
variables {
  name              = "reusable-test"
  project           = "test-project"
  region            = "asia-south1"
  flow_logs_enabled = true
}
run "custom_address_space" {
  command = plan
  module { source = "./modules/gcp/network" }
  variables {
    cidrs = { nodes = "10.90.0.0/20", pods = "10.91.0.0/16", services = "10.92.0.0/20", master = "172.17.0.0/28", sql = "10.93.0.0/16" }
  }
  assert {
    condition     = google_compute_subnetwork.app.ip_cidr_range == "10.90.0.0/20" && google_compute_subnetwork.app.private_ip_google_access
    error_message = "Network must use caller address space and private Google access."
  }
  assert {
    condition     = google_compute_subnetwork.app.log_config[0].flow_sampling == 0.1 && google_compute_global_address.sql.address == "10.93.0.0"
    error_message = "Flow evidence and SQL reservation must use configured policy."
  }
}
run "overlap_is_rejected" {
  command = plan
  module { source = "./modules/gcp/network" }
  variables { cidrs = { nodes = "10.60.0.0/20" } }
  expect_failures = [var.cidrs]
}
