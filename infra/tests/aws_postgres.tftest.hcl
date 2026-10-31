mock_provider "aws" {}
mock_provider "random" {}
variables {
  name                   = "test-staging"
  ha                     = false
  vpc_id                 = "vpc-0123456789abcdef0"
  node_security_group_id = "sg-0123456789abcdef0"
  subnet_group_name      = "private-db"
  deletion_protection    = true
}
run "private_bounded_database" {
  command = plan
  module { source = "./modules/aws/postgres" }
  assert {
    condition     = !aws_db_instance.ideas.publicly_accessible && aws_db_instance.ideas.storage_encrypted && aws_db_instance.ideas.deletion_protection
    error_message = "Database must remain private, encrypted and protected."
  }
  assert {
    condition     = aws_db_instance.ideas.max_allocated_storage == 100 && aws_db_instance.ideas.backup_retention_period == 7 && aws_db_instance.ideas.storage_type == "gp3"
    error_message = "Staging must bound storage and retain backups."
  }
  assert {
    condition     = anytrue([for parameter in aws_db_parameter_group.ideas.parameter : parameter.name == "rds.force_ssl" && parameter.value == "1"])
    error_message = "TLS must be enforced at the database."
  }
}
run "production_database_is_ha" {
  command = plan
  module { source = "./modules/aws/postgres" }
  variables { ha = true }
  assert {
    condition     = aws_db_instance.ideas.multi_az && aws_db_instance.ideas.backup_retention_period >= 14
    error_message = "Production requires Multi-AZ and >=14 days of backups."
  }
}
run "invalid_storage_rejected" {
  command = plan
  module { source = "./modules/aws/postgres" }
  variables { database = { storage_gb = 100, max_storage_gb = 50 } }
  expect_failures = [var.database]
}
