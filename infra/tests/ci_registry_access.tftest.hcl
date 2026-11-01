mock_provider "aws" {}
variables {
  name                       = "idea-board-test"
  github_repository          = "example/board"
  github_environment         = "aws-test"
  existing_oidc_provider_arn = "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
  repository_arns            = ["arn:aws:ecr:us-west-2:123456789012:repository/idea-board-test/frontend", "arn:aws:ecr:us-west-2:123456789012:repository/idea-board-test/backend"]
}
run "legacy_environment_subject" {
  command = plan
  module { source = "./modules/aws/ci-registry-access" }
  assert {
    condition     = jsondecode(aws_iam_role.publisher.assume_role_policy).Statement[0].Condition.StringEquals["token.actions.githubusercontent.com:sub"] == "repo:example/board:environment:aws-test"
    error_message = "Legacy subjects must bind one exact repository and environment."
  }
}
run "immutable_environment_subject" {
  command = plan
  module { source = "./modules/aws/ci-registry-access" }
  variables { subject_prefix = "repo:example@123/board@456" }
  assert {
    condition     = jsondecode(aws_iam_role.publisher.assume_role_policy).Statement[0].Condition.StringEquals["token.actions.githubusercontent.com:sub"] == "repo:example@123/board@456:environment:aws-test" && jsondecode(aws_iam_role.publisher.assume_role_policy).Statement[0].Condition.StringEquals["token.actions.githubusercontent.com:aud"] == "sts.amazonaws.com"
    error_message = "Immutable IDs must retain exact environment and STS audience checks."
  }
}
run "unrelated_repository_rejected" {
  command = plan
  module { source = "./modules/aws/ci-registry-access" }
  variables { subject_prefix = "repo:other@123/board@456" }
  expect_failures = [var.subject_prefix]
}
