cloud       = "aws"
name        = "idea-board"
environment = "staging"
region      = "ap-south-1"
# Replace with your actual administrator AND stable CI runner egress CIDRs.
admin_cidrs         = ["203.0.113.10/32"]
kubernetes_version  = "1.33"
deletion_protection = true
