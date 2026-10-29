output "cluster_name" { value = google_container_cluster.app.name }
output "database_url" {
  sensitive  = true
  value      = "postgresql+psycopg://ideas:${random_password.database.result}@${google_sql_database_instance.ideas.private_ip_address}:5432/ideas?sslmode=require"
  depends_on = [google_sql_user.ideas, google_sql_database.ideas]
}
