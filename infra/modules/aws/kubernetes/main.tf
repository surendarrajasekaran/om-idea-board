module "eks" {
  source                                   = "terraform-aws-modules/eks/aws"
  version                                  = "20.37.2"
  cluster_name                             = var.name
  cluster_upgrade_policy                   = { support_type = "STANDARD" }
  cluster_version                          = var.kubernetes_version
  cluster_endpoint_public_access           = var.public_cluster_endpoint
  cluster_endpoint_private_access          = true
  cluster_endpoint_public_access_cidrs     = var.public_cluster_endpoint ? var.admin_cidrs : null
  enable_cluster_creator_admin_permissions = true
  cluster_enabled_log_types                = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
  cloudwatch_log_group_retention_in_days   = var.log_retention_days
  access_entries = { for arn in var.administrator_arns : arn => {
    principal_arn = arn
    policy_associations = {
      administrator = {
        policy_arn   = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
        access_scope = { type = "cluster" }
      }
    }
  } }
  vpc_id                                       = var.vpc_id
  subnet_ids                                   = var.subnet_ids
  node_security_group_enable_recommended_rules = false
  node_security_group_additional_rules = {
    ingress_nodes = {
      description = "Node and pod traffic within this node group"
      protocol    = "tcp", from_port = 1025, to_port = 65535, type = "ingress", self = true
    }
    egress_nodes = {
      description = "Node and pod traffic within this node group"
      protocol    = "tcp", from_port = 1025, to_port = 65535, type = "egress", self = true
    }
    egress_https = {
      description = "HTTPS for registry images and AWS bootstrap APIs; pod egress separately denied"
      protocol    = "tcp", from_port = 443, to_port = 443, type = "egress", cidr_blocks = ["0.0.0.0/0"]
    }
    egress_dns_tcp = {
      description = "VPC resolver and CoreDNS TCP"
      protocol    = "tcp", from_port = 53, to_port = 53, type = "egress", cidr_blocks = [var.network_cidr]
    }
    egress_dns_udp = {
      description = "VPC resolver and CoreDNS UDP"
      protocol    = "udp", from_port = 53, to_port = 53, type = "egress", cidr_blocks = [var.network_cidr]
    }
    egress_database = {
      description = "Private PostgreSQL subnets only"
      protocol    = "tcp", from_port = 5432, to_port = 5432, type = "egress", cidr_blocks = var.database_egress_cidrs
    }
  }
  cluster_addons = {
    coredns    = {}
    kube-proxy = {}
    vpc-cni = {
      before_compute       = true
      configuration_values = jsonencode({ enableNetworkPolicy = "true" })
    }
  }
  eks_managed_node_groups = {
    app = {
      iam_role_additional_policies = var.enable_ssm_access ? { session_manager = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore" } : {}
      ami_type                     = "AL2023_x86_64_STANDARD"
      instance_types               = var.node_pool.instance_types
      capacity_type                = var.node_pool.capacity_type
      disk_size                    = var.node_pool.disk_size
      metadata_options = {
        http_endpoint               = "enabled"
        http_tokens                 = "required"
        http_put_response_hop_limit = 1
        instance_metadata_tags      = "disabled"
      }
      block_device_mappings = {
        root = {
          device_name = "/dev/xvda"
          ebs         = { volume_size = var.node_pool.disk_size, volume_type = "gp3", encrypted = true, delete_on_termination = true }
        }
      }
      min_size     = max(var.node_pool.min_size, var.ha ? 2 : 1)
      max_size     = var.node_pool.max_size
      desired_size = max(var.node_pool.desired_size, var.ha ? 2 : 1)
    }
  }
}
