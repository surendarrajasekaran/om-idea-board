resource "aws_ecr_repository" "service" {
  for_each             = var.services
  name                 = "${var.name}/${each.key}"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false
  encryption_configuration { encryption_type = "AES256" }
  image_scanning_configuration { scan_on_push = true }
}

resource "aws_ecr_lifecycle_policy" "service" {
  for_each   = aws_ecr_repository.service
  repository = each.value.name
  # Tagged release images remain available for GitOps rollback. Do not expire
  # them based on age/count without first checking deployed and recovery digests.
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Expire untagged images after the cleanup window"
      selection = {
        tagStatus   = "untagged"
        countType   = "sinceImagePushed"
        countUnit   = "days"
        countNumber = var.untagged_retention_days
      }
      action = { type = "expire" }
    }]
  })
}
