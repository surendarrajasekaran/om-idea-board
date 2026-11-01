# AI continuation context

Updated November 1, 2026. Current ownership is below; historical evidence is in [verification](verification.md).

## Repositories and Argo ownership

Source: `surendarrajasekaran/om-idea-board`. GitOps: `surendarrajasekaran/infra-helm-charts`.

GitOps has four functional folders: `argocd-manifests`, `helm-templates`, `helm-overides` and `releases`. It has no copied `automation` scripts or `environments` directory. The unchanged nucleus 1.1.0 chart and original checksums remain under `helm-templates`. Source CI pins a reviewed GitOps commit through `deploy/gitops/chart-source.json`; local checks use its sibling checkout or `GITOPS_DIR`. Never copy charts into the app repository.

The parent Application `idea-board-controller` is bootstrapped from `argocd-manifests/idea-board-controller.yaml`. It renders `helm-templates/argocd-app-controller` using `helm-overides/argocd-app-controller/custom-values.yaml` and manages two child Applications, `idea-board-backend` and `idea-board-frontend`. There are three Application entries. Definition changes reconcile from Git; do not install the app-controller chart or services separately with Helm. The Argo controller installation remains Helm release `argocd`. The obsolete standalone `idea-board-test-apps` release has been uninstalled while retaining the existing child Applications.

Backend also owns namespace controls from `argocd-manifests/idea-board-aws-test/controls.yaml`. The parent's project permits only Applications in `argocd`; the workload project permits approved namespaced resources in `idea-board-test`, denying Secrets/cluster resources. Projects and the parent are administrative bootstrap configuration. Parent and child definitions have no cascading-deletion finalizer by default and no replica-ignore rules. The services reconcile independently; the monitor verifies their paired release identity.

## Release records and monitoring

Current release metadata and health status are `releases/idea-board-aws-test/release.json` and `status.json`. Immutable checksummed rendered/value snapshots are subdirectories beside them. Current rendered frontend/backend duplicates were removed. Records are required for guarded recovery, not for Argo itself. Never edit archived snapshots.

Application CI builds/scans immutable amd64 ECR images, proposes bounded resources and updates the two component values plus release records/namespace controls. Image/resource publication and recovery preserve current Secret/CA references and hardening. Recovery accepts pre-Helm snapshots but re-renders the current chart for the active Helm target. Hard HTTP gates can force recovery; pending recovery blocks another rollback. Database migrations/data/infrastructure never roll back automatically.

The GitOps health workflow checks out a pinned reviewed source revision for health/AI/recovery scripts instead of maintaining copies. Update its source pin when reviewing helper changes. It has HTTP-only telemetry: paired frontend/backend identity, 20 readiness requests and new-release create/read. It cannot observe pod restarts, logs, CPU or memory. Healthy unchanged releases skip AI. Gemini errors/out-of-policy responses explicitly fall back to policy; required-live planning fails instead.

## AWS, AI and credentials

Account `812752207041`, profile `mit-qa-administratoraccess`, region `us-west-2`, namespace/cluster `idea-board-test`. Preserve unrelated account workloads. Private EKS API/worker, one `t3.medium`, one managed NAT, private encrypted PostgreSQL 16 and immutable ECR repos remain provisioned. Argo UI is private; unused ApplicationSet controller replicas are zero. The anonymous HTTP board uses synthetic data: http://af0d4388f01a74cebb0d087102ac80e7-5adda6a4d01432b5.elb.us-west-2.amazonaws.com.

Gemini only: `gemini-3.5-flash-lite`. Both repos set `AI_ENVIRONMENT=GEMINI_API_KEY`, selecting the environment holding the rotated `GEMINI_API_KEY` secret and provider/model variables. AWS publisher jobs use `aws-test` separately. Never print key values. Requests use fixed HTTPS, unredirected authentication, strict JSON schema/local validation, 30-second timeout and 1,200-token cap. Test plans allow one replica and at most 250m requested CPU per service; production requires at least two replicas. Actual billing depends on project tier. AI logs/job summaries display only approved redacted fields. Demo workflow run `41289856695` shows the submitted goal and accepted plan.

CI uses ECR-only OIDC, with exact subject `repo:surendarrajasekaran@35868093/om-idea-board@1438722777:environment:aws-test` and STS audience. It has no EKS/state administration. Personal GitHub identity is `surendarrajasekaran`; use repo-local helpers or capture that user's gh token into process environment without printing it. Preserve the globally active work identity.

Private administration uses run-scoped kubeconfig, SSM and validated cluster CA/hostname. Never print session-manager process arguments. Terraform 1.11.4 is at `/tmp/om-platform-tools/terraform`; state/vars/plans/artifacts are ignored and may contain credentials. State bucket `idea-board-tfstate-812752207041-us-west-2`, KMS alias `idea-board-terraform-state`. Bootstrap owns namespaces/database credential and CA Secrets. Runtime DB role is nonprivileged and TLS-verified.

## Scope and checks

Both cloud Terraform adapters and manual non-Argo utilities remain required for the assignment. AWS is deployed; GCP live deployment/second URL remain outstanding. Never run direct deployment utilities against this Argo-managed target. Production work includes HTTPS/DNS, authentication, availability, backup restore tests and alerting. Local parent/state refactor checks passed 65 script/platform tests, including chart provenance, ownership and real Helm publication/recovery; hosted/live evidence belongs in verification.
