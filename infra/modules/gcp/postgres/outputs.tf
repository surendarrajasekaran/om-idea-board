output "database_url" {
  sensitive = true
  value     = "postgresql+psycopg://ideas_app:${random_password.application.result}@${google_sql_database_instance.ideas.private_ip_address}:5432/${var.database.name}?sslmode=verify-ca&sslrootcert=/etc/postgresql/ca/ca.crt"
}
output "migration_database_url" {
  sensitive = true
  value     = "postgresql+psycopg://ideas:${random_password.database.result}@${google_sql_database_instance.ideas.private_ip_address}:5432/${var.database.name}?sslmode=verify-ca&sslrootcert=/etc/postgresql/ca/ca.crt"
}
output "application_password" {
  sensitive = true
  value     = random_password.application.result
}
output "database_host" { value = google_sql_database_instance.ideas.private_ip_address }

output "database_ca_certificate" {
  sensitive = true
  value     = google_sql_database_instance.ideas.server_ca_cert[0].cert
}
