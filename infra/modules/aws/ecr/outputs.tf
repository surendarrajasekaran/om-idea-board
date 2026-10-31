output "repository_urls" { value = { for service, repository in aws_ecr_repository.service : service => repository.repository_url } }
output "repository_arns" { value = { for service, repository in aws_ecr_repository.service : service => repository.arn } }
output "registry_id" { value = values(aws_ecr_repository.service)[0].registry_id }
