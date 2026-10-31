cloud               = "gcp"
name                = "idea-board"
environment         = "staging"
region              = "asia-south1"
gcp_project         = "replace-with-project-id"
admin_cidrs         = ["203.0.113.10/32"]
deletion_protection = true

# Private API is the secure default. Replace admin_cidrs with the runner/VPN
# source visible to that endpoint. Public access is an explicit reviewed opt-in.
public_cluster_endpoint = false
flow_logs_enabled       = true
log_retention_days      = 14
database                = { storage_gb = 20, max_storage_gb = 100, backup_days = 7 }
labels                  = { owner = "platform", cost_center = "case-study" }
