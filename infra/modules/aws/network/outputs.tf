output "vpc_id" { value = module.vpc.vpc_id }
output "private_subnet_ids" { value = module.vpc.private_subnets }
output "database_subnet_group_name" { value = module.vpc.database_subnet_group_name }
output "cidr" { value = var.cidr }

output "database_egress_cidrs" { value = [for i in [21, 22] : cidrsubnet(var.cidr, 8, i)] }
