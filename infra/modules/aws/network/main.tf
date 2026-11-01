data "aws_availability_zones" "available" { state = "available" }
module "vpc" {
  source                                          = "terraform-aws-modules/vpc/aws"
  version                                         = "6.7.3"
  name                                            = var.name
  cidr                                            = var.cidr
  azs                                             = length(var.availability_zones) == 0 ? slice(data.aws_availability_zones.available.names, 0, 2) : var.availability_zones
  public_subnets                                  = [cidrsubnet(var.cidr, 8, 1), cidrsubnet(var.cidr, 8, 2)]
  private_subnets                                 = [cidrsubnet(var.cidr, 8, 11), cidrsubnet(var.cidr, 8, 12)]
  database_subnets                                = [cidrsubnet(var.cidr, 8, 21), cidrsubnet(var.cidr, 8, 22)]
  enable_nat_gateway                              = true
  single_nat_gateway                              = !var.ha
  enable_dns_hostnames                            = true
  enable_flow_log                                 = var.flow_logs_enabled
  create_flow_log_cloudwatch_log_group            = var.flow_logs_enabled
  create_flow_log_cloudwatch_iam_role             = var.flow_logs_enabled
  flow_log_cloudwatch_log_group_retention_in_days = var.log_retention_days
  flow_log_max_aggregation_interval               = 600
  public_subnet_tags                              = { "kubernetes.io/role/elb" = "1" }
  private_subnet_tags                             = { "kubernetes.io/role/internal-elb" = "1" }
}
