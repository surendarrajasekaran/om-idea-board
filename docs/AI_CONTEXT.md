# AI continuation context

Updated November 1, 2026. This file records current project state; historical test/deployment evidence lives in [verification](verification.md).

## Repositories and ownership

- Source: `surendarrajasekaran/om-idea-board`; GitOps desired state: `surendarrajasekaran/infra-helm-charts`.
- GitOps `helm-common/nucleus` is the single canonical unchanged nucleus 1.1.0 chart, with `helm-common/nucleus-source.json` hashes. GitOps values are `helm-overides/idea-fe/custom-values.yaml` and `helm-overides/idea-be/custom-values.yaml`.
- `gitops_release.py` updates the current GitOps values with immutable images/resources/release identity, previews Helm rendering and records checksummed rendered/value snapshots. Argo renders the chart twice using separate release names, plus a directory source including only namespace controls. Rendered application files are evidence/recovery inputs, not Argo's application source.
- Source CI checks out the reviewed GitOps revision in `deploy/gitops/chart-source.json`; local checks use a sibling checkout or `GITOPS_DIR`. There is no duplicate chart in the application repository.
- Argo CD owns the AWS test application's rollout and Git-based recovery. The old GHCR/direct-Helm Actions workflow is retired. Manual `run_platform.py`/`deploy.py` remain for separate, non-Argo targets and shared rendering/bootstrap utilities.
- Both cloud Terraform implementations remain part of the assignment. AWS is deployed; GCP deployment and its second public URL are still outstanding.

## Verified AWS baseline

Account `812752207041`, profile `mit-qa-administratoraccess`, region `us-west-2`, name `idea-board`, environment `test`, namespace/cluster `idea-board-test`. Preserve unrelated account resources, including `louvre` and `signal-demo` workloads.

Private EKS API and worker, one `t3.medium`, one managed NAT, private encrypted RDS PostgreSQL 16, immutable ECR frontend/backend repositories and a mirrored hardened Argo image are provisioned. Argo's UI is private and its unused ApplicationSet controller is scaled to zero. The anonymous public board uses HTTP: [AWS test board](http://af0d4388f01a74cebb0d087102ac80e7-5adda6a4d01432b5.elb.us-west-2.amazonaws.com).

The Gemini baseline source release `41282749169` and independent health run `41282887901` passed with `source=live-ai`: matching component identities, create/read success, 20 requests, zero failures and p95 110.77 ms. The current release and healthy history are authoritative in GitOps `release.json`/`status.json`; later source releases can supersede that baseline. The prior Git recovery drill used deterministic policy and preserved data; it was not an AI-triggered rollback drill.

## AI and delivery configuration

The user selected Gemini only, model `gemini-3.5-flash-lite`. Each repository has repository variable `AI_ENVIRONMENT=GEMINI_API_KEY` selecting the dedicated environment where the rotated secret `GEMINI_API_KEY` was saved. That environment has `AI_PROVIDER=gemini`, `AI_MODEL=gemini-3.5-flash-lite`. AWS publisher jobs use `aws-test` independently. No self-hosted provider was integrated.

`gitops-release.yml` verifies, proposes a bounded profile, builds/scans immutable Linux amd64 ECR images and publishes desired state using environment secret `GITOPS_SSH_KEY`. The CI role is ECR-push only, without EKS/state administration. Its trust uses exact immutable subject `repo:surendarrajasekaran@35868093/om-idea-board@1438722777:environment:aws-test` and STS audience; GitHub's repository settings confirmed immutable subjects. The Terraform module also supports validated legacy repository prefixes.

Gemini uses a fixed HTTPS endpoint, an unredirected key header, native JSON-schema output, local validation, a 30-second timeout and a 1,200-token output cap. Test policy permits one replica and at most 250m requested CPU per component; production requires at least two replicas. Provider/schema failures explicitly fall back to policy, or fail when live AI is required. The manual AI check tests a replacement key/model with one proposal. A free-tier billing project is required for free quota; a key/model name does not establish billing tier.

The GitOps monitor verifies both component versions, 20 readiness requests and a new-release create/read operation. It has HTTP-only evidence; it does not observe CPU, memory, pod restarts or logs. Hard gates force recovery when failed even if AI recommends keeping a release. Recovery updates current Helm values with previous verified images/resources, retains current security/Secret/CA references, re-renders the current chart, validates rendered/value snapshot hashes, rejects stale pushes and guards pending recovery. Pre-migration manifest-only snapshots are also supported. No database/data/infrastructure rollback occurs. Healthy unchanged releases skip AI calls.

## State, credentials and tools

- Terraform 1.11.4 is available at `/tmp/om-platform-tools/terraform`; the system binary may be older. AWS target configuration, backend files, plans/state, kubeconfig and artifacts are ignored and can contain credentials. Preserve operational state during repository cleanup.
- State bucket: `idea-board-tfstate-812752207041-us-west-2`, KMS alias `idea-board-terraform-state`; bootstrap/application state use separate prefixes and native S3 locking.
- Private administration uses `scripts/private_eks.py` with a run-scoped kubeconfig, SSM and verified cluster CA/hostname. Avoid printing session-manager process arguments because they can contain session credentials.
- Bootstrap creates namespace controls and database credential/CA Secrets over the private API; neither Secrets nor database URLs enter Git or model requests. Runtime `ideas_app` is nonprivileged; migration credentials are separate and TLS is verified.
- Personal GitHub user is `surendarrajasekaran`. Repo-local credential helpers select that user's token; the globally active work account is intentionally preserved. Personal `gh` calls obtain that user's token in process environment without printing it.
- Monitor helpers are reviewed in source `scripts/` and synchronized into GitOps `automation/` when behavior changes. The separate copies let the health workflow run from its own repository.

## Checks and remaining scope

Python/chart/policy/recovery tests, PostgreSQL tests, frontend tests/build, Terraform mock-provider tests, Compose persistence, dependency audits, configuration/image scans and pinned workflow lint are exercised in CI. The supplied chart's optional templates remain intact to preserve its reusable 1.1.0 contract and provenance. See verification for exact runs and counts.

Remaining assignment work: GCP live deployment and second URL. Production work includes trusted HTTPS/DNS, authentication/moderation, availability, monitored backups/restores and alerting as described in [platform review](platform-review.md) and [operations](operations.md). Application deployments under Argo must use the GitOps flow, never the manual Helm path.
