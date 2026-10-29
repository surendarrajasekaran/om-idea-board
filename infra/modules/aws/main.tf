data "aws_availability_zones" "available" { state = "available" }
module "vpc" {
  source               = "terraform-aws-modules/vpc/aws"
  version              = "5.21.0"
  name                 = var.name
  cidr                 = "10.40.0.0/16"
  azs                  = slice(data.aws_availability_zones.available.names, 0, 2)
  public_subnets       = ["10.40.1.0/24", "10.40.2.0/24"]
  private_subnets      = ["10.40.11.0/24", "10.40.12.0/24"]
  database_subnets     = ["10.40.21.0/24", "10.40.22.0/24"]
  enable_nat_gateway   = true
  single_nat_gateway   = !var.ha
  enable_dns_hostnames = true
  public_subnet_tags   = { "kubernetes.io/role/elb" = "1" }
  private_subnet_tags  = { "kubernetes.io/role/internal-elb" = "1" }
}
module "eks" {
  source                                   = "terraform-aws-modules/eks/aws"
  version                                  = "20.37.2"
  cluster_name                             = var.name
  cluster_version                          = var.kubernetes_version
  cluster_endpoint_public_access           = true
  cluster_endpoint_private_access          = true
  cluster_endpoint_public_access_cidrs     = var.admin_cidrs
  enable_cluster_creator_admin_permissions = true
  cluster_enabled_log_types                = ["api", "audit", "authenticator"]
  vpc_id                                   = module.vpc.vpc_id
  subnet_ids                               = module.vpc.private_subnets
  cluster_addons = {
    coredns    = {}
    kube-proxy = {}
    vpc-cni    = { before_compute = true }
  }
  eks_managed_node_groups = {
    app = {
      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = ["t3.medium"]
      min_size       = 2
      max_size       = 4
      desired_size   = 2
    }
  }
}
resource "aws_security_group" "database" {
  name_prefix = "${var.name}-database-"
  description = "PostgreSQL from EKS nodes only"
  vpc_id      = module.vpc.vpc_id
  ingress {
    description     = "PostgreSQL from app nodes"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }
}
resource "random_password" "database" {
  length  = 32
  special = false
}
resource "random_id" "snapshot" { byte_length = 4 }
resource "aws_db_instance" "ideas" {
  identifier                 = var.name
  engine                     = "postgres"
  engine_version             = "16"
  instance_class             = var.ha ? "db.t3.small" : "db.t3.micro"
  allocated_storage          = 20
  max_allocated_storage      = 100
  storage_encrypted          = true
  db_name                    = "ideas"
  username                   = "ideas"
  password                   = random_password.database.result
  multi_az                   = var.ha
  publicly_accessible        = false
  db_subnet_group_name       = module.vpc.database_subnet_group_name
  vpc_security_group_ids     = [aws_security_group.database.id]
  backup_retention_period    = var.ha ? 14 : 7
  deletion_protection        = var.deletion_protection
  skip_final_snapshot        = false
  final_snapshot_identifier  = "${var.name}-final-${random_id.snapshot.hex}"
  auto_minor_version_upgrade = true
  apply_immediately          = false
}
