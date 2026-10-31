mock_provider "google" {}
mock_provider "random" {}
variables {
  project             = "test-project"
  name                = "test-staging"
  ha                  = false
  region              = "asia-south1"
  network_id          = "projects/test-project/global/networks/test"
  deletion_protection = true
  labels              = { project = "test" }
}
run "private_bounded_database" {
  command = plan
  module { source = "./modules/gcp/postgres" }
  assert {
    condition     = !google_sql_database_instance.ideas.settings[0].ip_configuration[0].ipv4_enabled && google_sql_database_instance.ideas.settings[0].ip_configuration[0].ssl_mode == "ENCRYPTED_ONLY"
    error_message = "Cloud SQL must reject public and plaintext connections."
  }
  assert {
    condition     = google_sql_database_instance.ideas.settings[0].disk_autoresize_limit == 100 && google_sql_database_instance.ideas.settings[0].backup_configuration[0].point_in_time_recovery_enabled
    error_message = "Storage growth must be bounded, and PITR enabled."
  }
}
run "production_database_is_ha" {
  command = plan
  module { source = "./modules/gcp/postgres" }
  variables { ha = true }
  assert {
    condition     = google_sql_database_instance.ideas.settings[0].availability_type == "REGIONAL" && google_sql_database_instance.ideas.settings[0].backup_configuration[0].backup_retention_settings[0].retained_backups >= 14
    error_message = "Production requires regional HA and >=14 retained backups."
  }
}
