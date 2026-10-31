mock_provider "aws" {}
variables { name = "idea-board-test" }
run "immutable_scanned_repositories" {
  command = plan
  module { source = "./modules/aws/ecr" }
  assert {
    condition     = length(aws_ecr_repository.service) == 2 && alltrue([for repository in aws_ecr_repository.service : repository.image_tag_mutability == "IMMUTABLE" && repository.image_scanning_configuration[0].scan_on_push && !repository.force_delete])
    error_message = "Every service needs an immutable scanned repository protected from forced deletion."
  }
  assert {
    condition     = alltrue([for policy in aws_ecr_lifecycle_policy.service : jsondecode(policy.policy).rules[0].selection.tagStatus == "untagged"])
    error_message = "Cleanup must preserve tagged release images needed for rollback."
  }
}
