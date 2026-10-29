output "cluster_name" { value = module.eks.cluster_name }
output "database_url" {
  sensitive = true
  value     = "postgresql+psycopg://ideas:${random_password.database.result}@${aws_db_instance.ideas.address}:5432/ideas?sslmode=require"
}
