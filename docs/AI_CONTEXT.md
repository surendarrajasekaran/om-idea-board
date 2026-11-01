# AI continuation context

Updated November 1, 2026. This file records current project state; historical test/deployment evidence lives in [verification](verification.md).

## Repositories and ownership

- Source: `surendarrajasekaran/om-idea-board`; GitOps desired state: `surendarrajasekaran/infra-helm-charts`.
- GitOps `helm-common/nucleus` is the single canonical unchanged nucleus 1.1.0 chart, with `helm-common/nucleus-source.json` hashes. GitOps values are `helm-overides/idea-fe/custom-values.yaml` and `helm-overides/idea-be/custom-values.yaml`.
- `gitops_release.py` updates the current GitOps values with immutable images/resources/release identity, previews Helm rendering and records checksummed rendered/value snapshots. The generic GitOps `helm-templates/argocd-app-controller` chart creates two Applications using bootstrap values in `bootstrap/idea-board-applications.yaml`: `idea-board-backend` and `idea-board-frontend`. Each renders the chart with its own stable release name; backend also includes only namespace controls as an additional source. The separate Helm bootstrap release is `idea-board-test-apps` in `argocd`, with no parent Application. They reconcile independently; the release monitor checks the pair. Rendered application files are evidence/recovery inputs, not Argo's application source.
- Source CI checks out the reviewed GitOps revision in `deploy/gitops/chart-source.json`; local checks use a sibling checkout or `GITOPS_DIR`. There is no duplicate chart in the application repository.
- Argo CD owns the AWS test application's rollout and Git-based recovery. The old GHCR/direct-Helm Actions workflow is retired. Manual `run_platform.py`/`deploy.py` remain for separate, non-Argo targets and shared rendering/bootstrap utilities.
- Both cloud Terraform implementations remain part of the assignment. AWS is deployed; GCP deployment and its second public URL are still outstanding.

## Two-Application bootstrap and ownership

GitOps `de890e7` adds the generic Application chart and removes the old combined `bootstrap/idea-board-test.yaml`. Application definitions are installed/upgraded through Helm bootstrap release `idea-board-test-apps`; component image/resource values still reconcile automatically from Git. Both Applications were privately verified Synced/Healthy, with no conditions. Migration preserved all eight resource UIDs and identical Deployment/Service specifications. Default deletion has no cascading finalizer; no replica-ignore rules weaken AI sizing reconciliation.

Source `56b646d` pins the new GitOps revision, adds chart tests and a tracked-chart ownership guard, removes an obsolete scanner exclusion and updates private bootstrap flags. All 64 script/platform tests passed locally; source CI `41294713094` and GitOps validation `41294657818` passed. Release `41294713160` passed and published GitOps `80d786f`. Both Applications then reconciled that revision and their ready Deployments matched the exact images/resources/release IDs. Independent health `41294864083` passed live-ai/keep, paired convergence, create/read, 20 requests with zero failures and p95 78.13 ms. GitOps `3078959` records it healthy without pending rollback. Current release/history files remain authoritative.

## Latest Helm migration and demo evidence

Source `d5a7717` passed CI `41291253831` (58 script/platform cases; 74 application/platform overall plus 11 Terraform cases) and ECR/GitOps release `41291253782`. GitOps `16a83ee` published Helm values and checksummed rendered/value snapshots for release `d5a7717f2cbe9164dfb98d365435f602cbcd8a98-41291253782-1`. The live Argo Application was applied with backend Helm, frontend Helm and a controls-only directory source; private API verification returned Synced/Healthy, three matching revisions, no conditions and two ready Deployments. New-release health `41291414658` returned live-ai/keep, create/read passed, 20 requests, zero failures, p95 96.12 ms.

Planner/health commands now print safe input and accepted result and write escaped job-summary tables. AI-check accepts a goal; visible planning demo `41289856695` passed. Tests cover redaction, HTML/log injection, fallback labels and Helm recovery from old/new snapshots. See [demo steps](gitops.md#demo) and [verification](verification.md).

The final image/resource-only publisher follow-up `89f5f4e` passed CI `41292570632`, release `41292570647` and health `41292767079`. Argo reconciled the new Helm value commit automatically and was Synced/Healthy; both ready Deployments matched their values' images/resources/release IDs. Normal publication preserves current database/CA Secret references as well as recovery. Later GitOps `release.json`/`status.json` remain authoritative.

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
