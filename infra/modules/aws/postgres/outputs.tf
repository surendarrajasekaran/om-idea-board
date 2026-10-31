output "database_url" {
  sensitive = true
  value     = "postgresql+psycopg://ideas_app:${random_password.application.result}@${aws_db_instance.ideas.address}:5432/${var.database.name}?sslmode=verify-full&sslrootcert=/etc/postgresql/ca/ca.crt"
}
output "migration_database_url" {
  sensitive = true
  value     = "postgresql+psycopg://ideas:${random_password.database.result}@${aws_db_instance.ideas.address}:5432/${var.database.name}?sslmode=verify-full&sslrootcert=/etc/postgresql/ca/ca.crt"
}
output "application_password" {
  sensitive = true
  value     = random_password.application.result
}
output "database_host" { value = aws_db_instance.ideas.address }

output "database_ca_certificate" {
  sensitive = true
  value     = ""
} # RDS global trust bundle is obtained over HTTPS by the deployer.
