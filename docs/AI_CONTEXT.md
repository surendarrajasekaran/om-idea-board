# AI continuation context

Historical baseline updated October 30, 2026. This is a project handoff for a new AI session or another laptop. It records implementation history and observed results; it is not a claim that cloud deployment has happened. Read the current source and Git status before continuing, because this snapshot can become stale.

## Current continuation status - October 31, 2026

The October 31 platform/security and GitOps changes supersede baseline commit `6349e55`. Read Git status and [verification](verification.md) for publication and deployment evidence. AWS test provisioning in account `812752207041` / `us-west-2` has created private RDS, ECR, an exact-environment GitHub publisher role and KMS-backed state storage. EKS/NAT/worker and Argo CD are created. Public frontend/backend identity and create/read checks passed; a healthy baseline is committed to the deployment repository. The backend uses a nonprivileged ideas_app role with TLS 1.3, and live pod egress restrictions were verified. No live AI success is claimed. New source/workflow publication awaits the personal GitHub token workflow scope; the deployment repository is published, with its scheduled workflow still local. Follow [the GitOps guide](gitops.md) for the current two-repository deployment model; use the older direct Helm flow below only for other targets.


### November 1 observed recovery

The failed test release `rollback-drill-20261031` was recovered through Git commit `bd79b81` and Argo reconciliation. The healthy recovery is `recovery-1793509010408156000`; commit `26d6c69` records verified health and clears pending recovery. Public release identities and create/read passed, and the baseline verification idea persisted. The test used a 60-second convergence override and deterministic fallback, not a live model. GitHub Actions files still need the personal token's workflow authorization, and AWS SSO expired overnight. The further ApplicationSet zero-replica optimization is committed/rendered but awaits reauthentication to apply.

### AWS test GitOps continuation

- Source repository: `surendarrajasekaran/om-idea-board`; deployment repository: `surendarrajasekaran/infra-helm-charts`.
- Profile `mit-qa-administratoraccess`, region `us-west-2`, Terraform name `idea-board`, environment `test`. Preserve existing account resources such as the unrelated `louvre` cluster/databases.
- Use Terraform 1.11.4 (the laptop's system Terraform may be older). Local target `.tfvars`, backend files, state/plan, kubeconfig and cloud artifacts are ignored. State and saved plans contain database credentials.
- ECR repositories are immutable `idea-board-test/frontend` and `idea-board-test/backend`. The GitHub OIDC publisher role is scoped to those repositories and source-repo environment `aws-test`.
- `gitops-release.yml` verifies/builds/scans then commits rendered chart output to the separate repo. A write deploy key exists as its environment secret `GITOPS_SSH_KEY`. Argo pulls public Git and EKS workers pull private ECR through their AWS role; app CI has no cluster administration.
- `bootstrap_gitops.py` installs namespace controls/DB CA and credential Secrets plus the private Argo controller. `private_eks.py` provides run-scoped CA-verified SSM forwarding through the optional SSM-managed worker.
- Health helpers are reviewed in source `scripts/` and copied into deployment `automation/`. Synchronize those copies when changing behavior. HTTP-only monitoring checks exact frontend/backend release identity, readiness and new-release write/read behavior, then records healthy history or commits guarded recovery. No Helm rollback under Argo auto-sync.
- `AI_PROVIDER=nvidia` and its model variable are configured in both `aws-test` GitHub environments. An `AI_API_KEY` has not been supplied; policy fallback remains explicit. OpenAI and Groq adapters are available; real API responses remain unverified.


- AWS and GCP adapters now compose separate provider-free network/Kubernetes/PostgreSQL modules, with moved blocks retaining original resource address history. CIDRs, AZs, node pools, database classes/tiers, storage/backup bounds and ownership labels are configurable.
- `--name` isolates state prefixes, output targets, namespaces, releases, Services and Secrets. The `idea-board` default retains its state path. Invalid profiles/images/flags and missing local-build publishing identity fail before provisioning.
- APIs default to private; provide runner/VPN routing and the real source CIDR. Restricted public opt-in is explicit. EKS defaults to 1.35 and STANDARD support (automatic control-plane upgrade after standard support, rather than extended-support enrollment). Staging uses one worker; production enforces >=2 on-demand workers.
- Runtime `ideas_app` credentials are separate from migration credentials. SQL bootstrap grants SELECT/INSERT and sequence usage only and rejects privileged or grouped application roles. Tests cover a non-superuser migration owner with CREATEROLE/CREATEDB, matching managed-service constraints more closely than a local superuser alone.
- RDS verifies hostname/CA (`verify-full`); Cloud SQL verifies its unique per-instance CA (`verify-ca`) for private-IP connections. A CA Secret is mounted into init and runtime containers. Database credential/CA fingerprints trigger backend rollout.
- Namespace controls enforce Restricted Pod Security, quotas, default-deny networking and explicit frontend/API/DB/DNS paths. They are applied outside Helm so rollback cannot remove the security boundary. EKS enables VPC CNI policy enforcement. GKE has a dedicated minimal node service account. EKS node IMDSv2 uses hop limit 1 and encrypted gp3 root disks.
- Both application containers have read-only roots. Nginx receives bounded writable config/cache/tmp volumes. Production requires `--tls-secret` and `--public-host`; the existing certificate Secret and owned DNS remain operator prerequisites. Renewed certificate fingerprints trigger frontend rollout on redeploy. Recovery derives the restored protocol/hostname from the Service.
- Storage growth caps, DB availability/backup floors, query/connection/lock deadlines, sampled flow logs, AWS log retention and node capacity bounds are explicit. Cloud SQL disk growth drift is ignored to avoid shrink attempts; initial storage remains configurable before creation.
- All external Actions and base/PostgreSQL image indices are pinned. The old mutable Trivy Action reference was removed after checking its upstream compromise advisory. `scripts/security_scan.py` uses an isolated digest-pinned 0.76.1 container for configuration, immutable registry image and local archive scans. It sees no Docker socket and uses disposable disk cache rather than fitting the expanded vulnerability DB into RAM.
- CI and release verification include both-cloud HIGH/CRITICAL configuration gates and mock-provider Terraform tests. There is one scoped expiring node-HTTPS exception in `.trivyignore.yaml`, with a rationale and a January 31, 2027 review deadline. This is not a zero-risk/zero-all-severity claim.
- Workflows share target mutation locks and use per-run Terraform directories. Checkout credentials do not persist. Local publishing requires `GHCR_PUBLISH_TOKEN`; only separate read-only `GHCR_TOKEN` can become a cluster pull Secret. Docker credentials are scoped to a temporary config; cloud/AI/registry credentials are limited to the required workflow steps.
- Current verification includes 60 application/platform tests (13 real PostgreSQL backend/role cases, 44 script/chart/policy/CLI/recovery cases, 3 React cases), eight mock-provider Terraform cases, lint/build/format/Helm/Actionlint checks, dependency audits, both-cloud config scans and local arm64 image scans. Compose smoke/persistence and certificate-verified HTTPS under a non-root/read-only frontend passed. Consult verification for scope limits. Fresh GitHub CI for this unpushed work is still pending.

Remaining: review a real plan, configure bootstrap trust/state/private routing and PKI/DNS, deploy to both clouds, verify enforcement and CA handling, exercise actual rollback/restores, record public URLs/digests/evidence. No live AI request or cloud apply was executed during this pass. Do not upload local credentials/state/plans/logs as handoff material.

## Historical October 30 implementation snapshot

## User objective and agreed scope

Implement the supplied **Dev Ops Case Study** clearly and completely: an Idea Board application, containers, modular infrastructure for two clouds, AI-assisted CI/CD, public deployments on both clouds, and documentation/evidence.

The user asked for autonomous implementation and a push to `https://github.com/surendarrajasekaran/om-idea-board`, then plans to pull on another laptop with AWS/GCP configured. The development laptop handled implementation and available verification. Actual cloud execution is the next phase on the configured laptop.

The user initially asked to defer Kubernetes deployment files because they had a common chart. They subsequently provided the nucleus chart, authorized reusing it with separate frontend/backend `custom-values.yaml` files, and requested the full flow. That chart integration is now implemented; it is not still waiting for a chart.

## Git checkpoints

- Branch: `main`; remote: `origin`, the GitHub repository above.
- `775f8ae`: initial application/platform implementation, including nucleus integration.
- `e97221b`: fixed Linux/Python 3.12 CLI module shadowing and added regression coverage.
- Both implementation commits were pushed. Local and remote `main` matched `e97221bae81f09c47a27cee416b106fec6b9ff9c` before adding this handoff document.
- Successful verification run for `e97221b`: [GitHub Actions run 40935839136](https://github.com/surendarrajasekaran/om-idea-board/actions/runs/40935839136). All four jobs passed: backend, frontend, infrastructure, Compose.
- The earlier run for `775f8ae` failed only at the Compose smoke CLI import; this was fixed rather than ignored.
- This context document is a later documentation commit. Inspect `git log` for its exact revision and any subsequent changes.

## What exists

### Application

- React frontend in `frontend/`: responsive board, submit form, search, loading/error/empty states, refresh, and accessible controls.
- FastAPI backend in `backend/app/`: `GET /api/ideas`, `POST /api/ideas`, trimmed 1–1000-character validation, database error handling, liveness/readiness endpoints, and Prometheus metrics.
- SQLAlchemy model: PostgreSQL `ideas(id, content, created_at)`; newest-first results.
- Initial additive migration: `python -m app.migrate`, serialized with a PostgreSQL advisory transaction lock. This is initial-schema creation, not a full versioned migration framework.
- Nginx serves the frontend on 8080 and proxies same-origin API requests to the backend on 8000. Database/backend ports are internal in Compose; frontend binds localhost:8080.
- Docker Compose starts PostgreSQL 16, migration, backend, then frontend; named volume persists ideas.

### Containers and dependency decisions

- Multi-stage frontend/backend Dockerfiles; non-root runtime users (frontend 101, backend 10001).
- Frontend runtime: `nginxinc/nginx-unprivileged:stable-alpine` with runtime package upgrades. The earlier 1.28 Alpine base had fixable vulnerabilities.
- Backend runtime: Python 3.12 slim, updated distribution packages, system `libpq5`, and pure psycopg wrapper. Production deliberately excludes `psycopg-binary`: that wheel bundled old native libraries caught by the image scan.
- `psycopg-binary` remains a **development-only** convenience for native tests; it is not copied into production images.
- Runtime Python packages are pinned in `backend/requirements.txt`; dev requirements include script tooling. Script requirements are in `scripts/requirements.txt` (PyYAML).
- Frontend package lock is tracked; Vite/Vitest were updated to patched versions. Prettier formats application source/workflows; the copied chart stays unchanged.

### Infrastructure

- Shared Terraform root in `infra/`, with `cloud`, `region`, `environment`, `admin_cidrs`, optional GCP project, and deletion-protection inputs.
- AWS adapter: two-AZ VPC, NAT/private nodes, EKS managed node group, private RDS PostgreSQL 16, database security group, backups and encryption. Production enables database Multi-AZ and longer backup retention.
- GCP adapter: VPC/subnet/pod-service ranges, Cloud NAT, GKE Autopilot with private nodes, private Cloud SQL PostgreSQL 16, encrypted database connections, backups/PITR; production uses regional database availability.
- Kubernetes API public access is restricted to supplied administrator/runner CIDRs. Example `203.0.113.10/32` is documentation-only and must be replaced.
- Outputs include `cluster_name`, sensitive `database_url`, `cloud`, `region`, `environment`, and `gcp_project`.
- `scripts/infra_init.py` selects S3 or GCS remote state by writing ignored `infra/backend.tf`. State buckets/trust identities are bootstrap prerequisites, not created by this stack.
- Provider/module versions and provider lock file are tracked. Terraform was initialized and validated; no real cloud plan/apply was performed.
- Run clouds sequentially in one checkout or use separate clones. The initializer uses `-reconfigure`, not cross-cloud state migration.

### Common chart

- Original chart was supplied from a sibling `nucleus/nucleus` directory; that external directory was not edited.
- A portable, unchanged copy of nucleus **1.1.0** is tracked under `deploy/charts/nucleus`.
- `deploy/charts/nucleus-source.json` records per-file SHA-256 hashes, checked by tests.
- User-specific values:
  - `deploy/frontend/custom-values.yaml`
  - `deploy/backend/custom-values.yaml`
- Cloud frontend Service overlays: `deploy/clouds/aws.yaml`, `deploy/clouds/gcp.yaml`.
- Two releases/Services: `idea-board-backend` and `idea-board-frontend`, in namespace `idea-board-staging` or `idea-board-production`.
- Backend is ClusterIP; frontend is LoadBalancer. AWS overlay requests an NLB supported by EKS's legacy service controller; GKE uses an external L4 load balancer. No additional ingress controller is bootstrapped.
- This baseline uses HTTP and allocated cloud hostname/IP. DNS/TLS and production identity/edge controls were not configured.
- Backend uses an existing database Secret through `envFrom`; migration runs in the chart-supported init container using the exact backend image.
- Probes, non-root security contexts, disabled service-account token mounts, resource requests/limits, and disruption budgets for multiple replicas are set through chart values.
- The chart builds image strings as `repository:tag`; digest-pinned images therefore use `repository:commit@sha256:digest` (or `pinned@sha256:digest` for digest-only input). Do not replace this with an incompatible invented chart key.

### AI behavior

- `scripts/ai_ops.py` uses the OpenAI Responses API with strict structured output and additional local validation. No model-generated command or arbitrary IaC is executed.
- Resource profile: replicas 1/2/3, CPU 100m/250m/500m, memory 128Mi/256Mi/512Mi, short rationale. Production requires at least two replicas.
- Profiles map to known nucleus replica/resource keys. GCP raises proposals below the configured 250m CPU/256Mi floor; limits are 1 CPU/512Mi.
- Health input is aggregate numeric probe evidence only: requests, failures, p95 latency, restart delta. No raw logs, idea content, database URI, or credentials go to the model.
- Deterministic failure gates: error rate >5%, p95 >1500ms, or new container restarts. AI cannot override failed gates, but may recommend rollback for additional concerns.
- `OPENAI_API_KEY` and `OPENAI_MODEL` are explicit environment settings. Without live credentials or with rejected/unavailable responses, output is visibly labeled `policy-fallback`; `--require-ai` fails instead.
- No live OpenAI request was made during verification. API calls are mocked in tests; local health runs used policy fallback.

### Full deployment flow

The current entry point is **`scripts/run_platform.py`**, never `scripts/platform.py`. The old name shadowed Python's standard-library `platform`, breaking `uuid` imports on Linux/Python 3.12. A subprocess regression test now invokes `--help` on all six CLIs.

`run_platform.py` performs:

1. Prerequisite checks and profile creation/reuse.
2. Matching remote-state initialization.
3. Terraform plan to a saved file and apply; local plan file is removed afterward.
4. Linux amd64 image build/push with Git commit tags, SBOM/provenance, digest capture, and fixable HIGH/CRITICAL vulnerability gate via Trivy.
5. A temporary run-scoped kubeconfig for the selected EKS/GKE cluster, preserving the user's default context.
6. Invocation of `scripts/deploy.py` with explicit context, images, target, and profile.

`deploy.py` validates target/profile/images, reads sensitive Terraform outputs without printing them, creates the namespace, records deployed Helm revisions, updates database/optional registry Secrets through stdin, and upgrades backend then frontend. It supports Helm 3 `--atomic` and Helm 4 `--rollback-on-failure`.

It waits for public endpoint readiness, measures probes/restart deltas, assesses health, and runs a real create/read smoke test. A failure restores attempted releases in reverse order to recorded known-good revisions; a failed first installation is removed. Recovery is checked and recorded; overall failure remains a nonzero exit. Database data/schema and infrastructure are never automatically destroyed on application failure.

Sanitized `deployment.json`, `health.json`, and profile files go under ignored `artifacts/<cloud>-<environment>/`. Secrets are not stored in chart values/artifacts. `--skip-infra`, `--skip-build`, `--profile`, and explicit image references support reusing verified release artifacts. Skipping builds also skips their scan and assumes images were already scanned.

### Workflows

- `ci.yml` (**Verify**): PR/main push checks; backend/PostgreSQL tests, AI/chart/CLI tests, frontend tests/build/audit, Terraform validation, full Compose smoke and persistence checks.
- `infrastructure.yml` (**Infrastructure**): main-only manual plan/apply, OIDC credentials, remote state; trusted self-hosted Linux runner labeled `idea-board` with fixed egress.
- `release.yml` (**Release and deploy**): main-only manual release, reusable tests, validated AI profile, commit-tagged images/digests, GHCR publishing, provenance/SBOM, scans, then optional deployment (default true) to existing infrastructure using exact artifacts.
- `reusable-tests.yml`: release verification.
- `actionlint.yaml` declares the custom runner label. Actionlint passed locally.
- Source pushes do not automatically provision/deploy clouds. No privileged workflow was dispatched during implementation.

## Observed verification

- 11 backend tests passed with isolated SQLite, and the same 11 passed with real PostgreSQL 16 in Docker, including after switching the runtime to system libpq.
- 10 AI policy tests, 12 chart/deployment/recovery tests, 1 CLI regression test, and 3 React tests passed. Together with the 11 backend cases, that is 37 distinct tests; the PostgreSQL run repeats the backend cases.
- Full Docker Compose startup, public-proxy smoke create/read, and persistence after backend restart passed.
- Frontend production build, Python lint/format, workflow/value formatting, Helm lint, AWS/GCP render-only output parsing, Terraform format/schema validation, and Actionlint passed.
- Browser submission/search/reload and desktop/mobile layouts were inspected.
- Dependency audits were clear at the time tested.
- Final local **arm64** frontend/backend images had zero fixable HIGH/CRITICAL findings in Trivy. This does not establish that future bases or Linux amd64 release images stay clear; the release flow scans them again.
- A local readiness window had 20 requests, zero failures, approximately 11ms p95; this is smoke evidence, not a performance benchmark.
- GitHub CI for `e97221b` passed all four jobs; link above.
- Known non-failing warning: Starlette test client deprecates its httpx compatibility path.

## Remaining real-world work

On the configured laptop:

1. Pull current main and inspect Git status/user changes. Install tools/dependencies listed in `docs/full-flow.md`.
2. Verify actual AWS/GCP identities, projects, permissions, billing, quotas, and supported cluster versions. Configure remote-state buckets and real laptop/runner egress CIDRs.
3. Configure GHCR publishing and cluster image pulls. For private images, use a suitably scoped persistent read token or pre-existing namespace pull secret; never persist the short-lived Actions publishing token in Kubernetes. Configure optional live AI credentials/model if required.
4. Copy/edit ignored AWS/GCP `.tfvars`; execute the full flow once per cloud. No actual project IDs, account IDs, bucket names, secrets, or deployed URLs were supplied in this repository.
5. Verify actual public URLs and application persistence. Exercise a deliberately failing release and confirm recovery on each real cluster; mocked recovery tests are not live rollback evidence.
6. Record observed URLs, digests, chart version, workflow links, health reports, and rollback results in `docs/verification.md`. Public two-cloud URLs remain incomplete until observed.

Primary instructions/commands: [full-flow guide](full-flow.md). Architecture/bootstrap: [README](../README.md). Chart mapping: [integration details](common-chart-integration.md). Requirements: [traceability](requirements.md). Operations/limitations: [operations](operations.md).

## Local-only artifacts and boundaries

The original case-study PDF is not committed. Credentials, `.env`, local `.tfvars`, Terraform state/plan/cache, virtual environments, node_modules, screenshots, and generated reports are excluded by `.gitignore`. Do not upload them as a substitute for this handoff. A localhost URL or generated configuration is not evidence of a successful public cloud deployment.

The application is intentionally an anonymous, basic board. Authentication, moderation, pagination, production TLS/domain setup, full monitoring/alerting, future versioned schema migrations, autoscaling, and comprehensive cluster telemetry/alerting are beyond the implemented case-study baseline and should not be described as already present.
