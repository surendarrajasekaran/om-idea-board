moved {
  from = module.vpc
  to   = module.network.module.vpc
}
moved {
  from = module.eks
  to   = module.kubernetes.module.eks
}
moved {
  from = aws_security_group.database
  to   = module.postgres.aws_security_group.database
}
moved {
  from = random_password.database
  to   = module.postgres.random_password.database
}
moved {
  from = random_id.snapshot
  to   = module.postgres.random_id.snapshot
}
moved {
  from = aws_db_instance.ideas
  to   = module.postgres.aws_db_instance.ideas
}
