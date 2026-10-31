resource "aws_security_group" "database" {
  name_prefix = "${var.name}-database-"
  description = "PostgreSQL from EKS nodes only"
  vpc_id      = var.vpc_id
  ingress {
    description     = "PostgreSQL from app nodes"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.node_security_group_id]
  }
}
resource "random_password" "database" {
  length  = 32
  special = false
}
resource "random_id" "snapshot" { byte_length = 4 }
resource "aws_db_instance" "ideas" {
  identifier                      = var.name
  engine                          = "postgres"
  engine_version                  = "16"
  instance_class                  = coalesce(var.instance_class, var.ha ? "db.t3.small" : "db.t3.micro")
  allocated_storage               = var.database.storage_gb
  max_allocated_storage           = var.database.max_storage_gb
  storage_encrypted               = true
  db_name                         = var.database.name
  username                        = "ideas"
  password                        = random_password.database.result
  multi_az                        = var.ha
  publicly_accessible             = false
  db_subnet_group_name            = var.subnet_group_name
  vpc_security_group_ids          = [aws_security_group.database.id]
  backup_retention_period         = max(var.database.backup_days, var.ha ? 14 : 7)
  deletion_protection             = var.deletion_protection
  skip_final_snapshot             = false
  final_snapshot_identifier       = "${var.name}-final-${random_id.snapshot.hex}"
  auto_minor_version_upgrade      = true
  apply_immediately               = false
  storage_type                    = "gp3"
  parameter_group_name            = aws_db_parameter_group.ideas.name
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  copy_tags_to_snapshot           = true
  allow_major_version_upgrade     = false
  depends_on                      = [aws_cloudwatch_log_group.database]
  maintenance_window              = "sun:04:00-sun:05:00"
  backup_window                   = "02:00-03:00"
}

resource "aws_db_parameter_group" "ideas" {
  name_prefix = "${var.name}-"
  family      = "postgres16"
  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }
  lifecycle { create_before_destroy = true }
}
resource "aws_cloudwatch_log_group" "database" {
  for_each          = toset(["postgresql", "upgrade"])
  name              = "/aws/rds/instance/${var.name}/${each.key}"
  retention_in_days = var.database.log_retention_days
}
resource "random_password" "application" {
  length  = 32
  special = false
}
