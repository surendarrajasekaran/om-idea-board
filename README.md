# Idea Board

A small React + FastAPI + PostgreSQL application with container builds, two Terraform cloud adapters, and bounded AI tools for release planning and health assessment.

**Current status:** AWS test is running in `mit-qa` / `us-west-2`: private EKS, private RDS, immutable ECR images and Argo CD GitOps delivery. [Open the test board](http://af0d4388f01a74cebb0d087102ac80e7-5adda6a4d01432b5.elb.us-west-2.amazonaws.com). Public create/read and readiness checks passed, and the baseline release is recorded healthy. Both repositories and their Actions workflows are published through the personal GitHub account. The release pipeline publishes scanned ECR digests to GitOps; live AI still needs a provider API key. GCP and its second public URL remain pending. See [verification](docs/verification.md) for precise evidence and limitations.

The AWS test delivery path now uses private ECR and a separate Argo CD GitOps repository. Read the [GitOps guide](docs/gitops.md) for the two-repository pipeline, private-cluster administration, Gemini/NVIDIA/Groq/OpenAI providers and guarded recovery. Observed cloud progress is tracked in [verification](docs/verification.md).

For continuation in a new AI session or on another laptop, read [the AI context handoff](docs/AI_CONTEXT.md).

## Architecture

```mermaid
flowchart LR
  Browser --> Web[React / Nginx :8080]
  Web -->|same-origin /api| API[FastAPI :8000]
  API --> DB[(Private PostgreSQL)]
  Git[GitHub] --> CI[Tests / builds / image scan]
  CI --> Registry[ECR for AWS / GHCR for legacy flow: immutable digest]
  Goal[Environment + resource goal] --> AI[AI structured proposal]
  AI --> Policy[Schema + resource policy]
  Policy --> Profile[Release profile artifact]
  Registry --> Chart[Supplied nucleus common Helm chart]
  Profile --> Chart
  TF[Shared Terraform interface] --> AWS[AWS: VPC / EKS / RDS]
  TF --> GCP[GCP: VPC / GKE / Cloud SQL]
  Chart --> GitOps[AWS desired state in infra-helm-charts]
  GitOps --> Argo[Argo CD inside EKS]
  Argo --> AWS
  Chart --> GCP
```

The frontend proxies `/api/` to the backend, so browsers need no cloud-specific API URL or CORS configuration. PostgreSQL is not exposed publicly. The database has one `ideas` table: integer `id`, `content` (1–1000 trimmed characters), and server-generated `created_at`. Ideas are returned newest first. User content is displayed as text, never rendered as HTML.

### Repository map

| Path | Purpose |
| --- | --- |
| `frontend/` | React board, search, submission, loading/error/empty states, Nginx proxy, tests |
| `backend/` | REST API, explicit initial migration, health endpoints, Prometheus metrics, tests |
| `docker-compose.yml` | Local PostgreSQL → migration → API → frontend startup order |
| `infra/` | Shared cloud interface and AWS/GCP implementation modules |
| `scripts/ai_ops.py` | Validated AI resource profile and health decisions |
| `scripts/probe.py` | HTTP readiness measurements; no logs or idea content sent to AI |
| `scripts/run_platform.py` | Laptop/CI flow: provision, publish/scan images, deploy and verify |
| `scripts/deploy.py` | Two common-chart releases and failure recovery |
| `deploy/` | Unmodified nucleus chart and frontend/backend custom values |
| `scripts/smoke.py` | Frontend/readiness/create/read deployment verification |
| `.github/workflows/` | CI, protected infrastructure operations, release preparation |
| `docs/common-chart-integration.md` | Common-chart values mapping and rollback behavior |
| `docs/requirements.md` | Case-study requirements and honest completion status |
| `docs/operations.md` | Migration, health, rollback, and incident procedures |

## Run locally with Docker Compose

Prerequisites: Docker Engine/Desktop with Compose v2 and a free port 8080.

```sh
cp .env.example .env
# Set POSTGRES_PASSWORD in .env. Use URI-safe letters/digits for this local Compose URI.
docker compose up --build --wait --wait-timeout 240
```

Open [the local application](http://localhost:8080).

```sh
curl --fail http://localhost:8080/api/ideas
curl --fail -X POST http://localhost:8080/api/ideas \
  -H 'Content-Type: application/json' \
  -d '{"content":"Make deployment easier to understand"}'
python3 scripts/smoke.py --url http://localhost:8080
```

The smoke command creates one identifiable verification idea. PostgreSQL uses a named volume. `docker compose down` stops the stack and preserves ideas. `docker compose down --volumes` deliberately deletes local database data. Backend and database ports are internal to Compose; only the frontend binds to the host loopback address.

Changing the database password after first startup also requires changing the existing database role password or explicitly recreating the development volume. Replacing `.env` alone does not update an initialized PostgreSQL volume.

### API

| Method | Path | Result |
| --- | --- | --- |
| GET | `/api/ideas` | JSON array of ideas |
| POST | `/api/ideas` | Accepts `{"content":"..."}`; returns saved idea, HTTP 201 |
| GET | `/health/live` | Process liveness (frontend and backend) |
| GET | `/health/release` | Backend release identity plus frontend release header for GitOps convergence |
| GET | `/health/ready` | API can query the migrated ideas table; 503 otherwise |
| GET | `/metrics` | Backend-only Prometheus counters and latency histogram |
| GET | `/docs` | Backend-only generated API documentation |

Nginx enforces an 8 KiB request body limit and a per-client API request limit. Invalid input returns HTTP 422. Database failures return HTTP 503 without exposing connection information. Metrics use route templates to avoid unbounded URL labels.

## Development and tests

Use Python 3.12 and Node.js 22 for consistency with CI and container builds.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt
PYTHONPATH=backend .venv/bin/pytest -q backend/tests
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/ruff check backend scripts tests
npm --prefix frontend ci
npm --prefix frontend test
npm --prefix frontend run build
```

Backend tests default to an isolated SQLite database per test for quick local checks. CI runs those same tests against real PostgreSQL 16 and separately builds and smoke-tests the entire Compose stack, including a backend restart and data persistence check.

For a PostgreSQL-only test run, use a dedicated disposable database; the test fixture deletes all ideas after every test:

```sh
TEST_DATABASE_URL='postgresql+psycopg://ideas:password@localhost:5432/ideas_test' \
  PYTHONPATH=backend .venv/bin/pytest -q backend/tests
```

For app development without Docker, provide a PostgreSQL `DATABASE_URL`, run the migration, and start the API. Vite proxies to port 8000:

```sh
export DATABASE_URL='postgresql+psycopg://ideas:password@localhost:5432/ideas'
(cd backend && ../.venv/bin/python -m app.migrate)
(cd backend && ../.venv/bin/uvicorn app.main:app --reload)
# In another terminal:
npm --prefix frontend run dev
```

## Cloud-agnostic approach

The application containers, database schema, AI policies, and common-chart deployment are shared. Terraform normalizes cloud-specific services behind one interface:

| Capability | AWS adapter | GCP adapter |
| --- | --- | --- |
| Kubernetes | EKS, private managed worker nodes | Regional GKE Autopilot, private nodes |
| PostgreSQL | RDS PostgreSQL 16 | Cloud SQL PostgreSQL 16 |
| Networking | VPC, two AZs, public/private/database subnets, NAT | VPC, pod/service secondary ranges, Cloud NAT, private service access |
| Database access | Private RDS security group allows EKS nodes | Private Cloud SQL IP with encrypted connections |
| Control plane | Private API by default; explicit public opt-in restricted to trusted CIDRs | Private API and worker nodes; authorized networks enforced |
| Production database | Multi-AZ, 14-day backups | Regional availability, PITR |
| Remote state | Encrypted S3 with native lock file | GCS with native locking |

Switch cloud using `cloud`, `region`, and (for GCP) `gcp_project`; credentials and the remote state bucket also differ. Environment (`test`, `staging` or `production`) sets database availability. Node sizes are intentionally adapter-owned, rather than claiming AWS and GCP instance types are interchangeable. Adding a third provider means implementing the same outputs (`cluster_name`, sensitive `database_url`) and adding authentication/state initialization for that provider.

The initial migration is additive and serialized by a PostgreSQL advisory lock. Containers run under non-root users. Production backend uses the distribution-patched PostgreSQL client library rather than bundled binary-wheel libraries; runtime package upgrades are applied during image builds. Database storage encryption, backups, and deletion protection are enabled. Cloud connections verify trust: RDS uses `verify-full` with its official CA bundle, and Cloud SQL uses `verify-ca` with its unique per-instance CA. Only migration init containers receive administrator credentials; the API receives a separate SELECT/INSERT role. Namespace policies deny other network paths and enforce Restricted Pod Security. See the module guide for CA rotation and identity-verification limits.

## Provision infrastructure locally

Prerequisites: Terraform 1.10+, AWS CLI or Google Cloud CLI, appropriate cloud account/project permissions, billing enabled, and private runner/VPN connectivity and the administrator/runner source CIDRs visible to the API (or an explicit restricted public endpoint opt-in). No credentials are included in this repository.

1. Create a dedicated remote-state bucket outside this stack. For S3: enable encryption, versioning, block public access, and permit state read/write plus `.tflock` read/write/delete. For GCS: enable uniform bucket-level access and versioning and grant object read/write/delete to the Terraform identity. Use separate buckets or prefixes per environment, with narrow IAM access. **Terraform state contains the database password; sensitive outputs do not remove it from state.**
2. Authenticate with `aws sso login` / your AWS role or `gcloud auth application-default login`.
3. Copy the relevant example into an ignored local `.tfvars` file. Replace the documentation-only CIDR and GCP project ID. Verify the chosen Kubernetes version is supported in your EKS region.
4. Initialize that cloud's remote state, inspect the plan, then apply:

AWS:

```sh
cp infra/environments/aws.example.tfvars infra/aws.tfvars
# Edit infra/aws.tfvars and replace the example CIDR.
python3 scripts/infra_init.py --cloud aws --environment staging \
  --bucket YOUR_AWS_STATE_BUCKET --region ap-south-1
terraform -chdir=infra plan -var-file=aws.tfvars -out=release.tfplan
terraform -chdir=infra apply release.tfplan
```

GCP:

```sh
cp infra/environments/gcp.example.tfvars infra/gcp.tfvars
# Edit infra/gcp.tfvars and replace the project and example CIDR.
python3 scripts/infra_init.py --cloud gcp --environment staging \
  --bucket YOUR_GCP_STATE_BUCKET --region asia-south1
terraform -chdir=infra plan -var-file=gcp.tfvars -out=release.tfplan
terraform -chdir=infra apply release.tfplan
```

The initializer writes an ignored `infra/backend.tf` and runs `terraform init -reconfigure`. It selects a separate cloud/environment state location; it never migrates state between clouds. Use separate working directories for simultaneous provisioning. Keep `--environment` consistent with the `.tfvars` environment to prevent placing a production stack in staging state. Delete local saved plan files after use; they contain secrets.

This creates chargeable infrastructure. Deletion protection is enabled by default; review costs before applying. To intentionally tear down a disposable environment, first apply `deletion_protection=false` to that exact cloud/environment state, then run `terraform destroy` with the same variable file. RDS retains a final snapshot; account for snapshot and bucket storage afterward.

## GitHub Actions setup

Create GitHub Environments named `aws-staging`, `gcp-staging`, and, if needed, `aws-production` / `gcp-production`. Configure required reviewers for production and restrict deployment branches to `main`.

### Identity and state bootstrap

These are trust roots created by the account administrator before the infrastructure workflow can authenticate:

- **AWS:** configure GitHub's OIDC provider and an IAM role. Restrict trust to your repository's exact environment subject, for example `repo:OWNER/REPO:environment:aws-staging`, and audience `sts.amazonaws.com`. Grant the reviewed permissions to manage this stack, state bucket objects, IAM roles needed by EKS, and `iam:PassRole`. Do not use unrestricted account administrator access as the permanent CI policy. The infrastructure creator receives EKS administration; a different deployment identity needs an explicit EKS access entry.
- **GCP:** configure a Workload Identity Pool/provider and service account. Restrict federation to the repository and intended environment/branch. Grant `roles/iam.workloadIdentityUser` to that restricted principal. The provisioning identity needs compute/network, GKE, Cloud SQL, service usage, and state-object administration for the selected project/bucket. The deployment identity needs GKE access plus Kubernetes RBAC.
- **Runner:** infrastructure uses a trusted self-hosted Linux runner with labels `self-hosted`, `linux`, `idea-board`, fixed egress, Python, and network access to cloud APIs. Provide private routing to the cluster API and include the source CIDR visible there in `ADMIN_CIDRS`. Public egress CIDRs apply only when explicitly enabling a public endpoint. Do not run untrusted PR code on that runner. App verification and image builds use GitHub-hosted runners.

Set these **environment variables** in GitHub Settings → Environments:

| Variable | AWS | GCP |
| --- | --- | --- |
| `REGION` | e.g. `ap-south-1` | e.g. `asia-south1` |
| `STATE_BUCKET` | Existing S3 state bucket | Existing GCS state bucket |
| `ADMIN_CIDRS` | JSON array of trusted runner/VPN CIDRs, /24 or narrower | Same, as seen by the private API |
| `STACK_NAME` | Optional resource/state prefix; default `idea-board` | Same |
| `INFRA_TFVARS_JSON` | Optional non-secret JSON for capacity/network policy | Same |
| `AWS_ADMINISTRATOR_ARNS` | Optional JSON array of stable EKS administrator role ARNs | — |
| `TLS_SECRET` / `PUBLIC_HOST` | Required for production HTTPS; existing namespace TLS Secret and owned DNS name | Same |
| `AWS_ROLE_ARN` | GitHub OIDC provisioning role | — |
| `GCP_PROJECT` | — | GCP project ID |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | — | Full provider resource path |
| `GCP_SERVICE_ACCOUNT` | — | Provisioning service-account email |
| `AI_PROVIDER` / `AI_MODEL` | `gemini` / `gemini-flash-latest` for this test | Same, or another supported provider/model |

Set `GEMINI_API_KEY` as an **environment secret** in both repositories for live Gemini. Provider-specific keys override the legacy `AI_API_KEY`. Do not place it in a variable, chart value, image, or Terraform state.

### Workflow behavior

1. **Verify** runs on PRs and main pushes: backend PostgreSQL tests, AI policy tests, frontend tests/build, Terraform formatting/validation, and full Compose smoke/persistence checks. Configure these checks as required branch protection.
2. **Infrastructure** is manually dispatched on `main`. Select cloud/environment and `plan` (default) or `apply`. OIDC obtains short-lived credentials, remote state is initialized, and Terraform plans. `apply` applies that exact saved plan within the same protected job. Sensitive plan binaries are not uploaded. GitHub logs may still contain infrastructure metadata; restrict log access appropriately.
3. **Release and deploy** is manually dispatched on `main`. It reruns application tests, generates a validated profile, builds both images with the full commit SHA, publishes to GHCR, generates provenance/SBOM, and scans for fixable high/critical vulnerabilities. Artifacts contain image digests and the JSON profile. Scans gate release completion; an image may already have been pushed before its scan fails.
4. **Application deployment** runs after successful release image scans when the workflow's `deploy` input is true (default). It authenticates with OIDC, reads the existing remote-state outputs, consumes the exact image digests and prepared profile artifacts, deploys both releases of the supplied common chart, checks readiness and real writes, and restores the recorded revisions on failure. Select `deploy=false` for image preparation only. See [the integration details](docs/common-chart-integration.md).

For private GHCR images, set the environment secret `GHCR_READ_TOKEN` (a long-lived, least-privileged package read token), plus `GHCR_USERNAME` as a variable; or configure `REGISTRY_PULL_SECRET` for a pre-existing namespace secret. Public images can instead use `GHCR_IMAGES_PUBLIC=true`. The workflow fails early if no access path is declared. A short-lived Actions `GITHUB_TOKEN` is used only for publishing, never stored as a persistent cluster pull secret.

No workflow sends secrets or cloud credentials to pull-request code. The main-only dispatch guards also prevent selecting an arbitrary feature branch for privileged jobs. External Actions are pinned to verified commit SHAs and base/PostgreSQL images to multi-architecture digests. The shared scanner is digest-pinned and isolated; source scans run for both clouds. Dependabot proposes weekly updates. Review the scoped, expiring node-HTTPS exception and the remaining account/PKI/operations responsibilities in the platform review.

## AI integration

The AWS test uses Gemini’s native `generateContent` API with JSON-schema output and strict local validation. Set `AI_PROVIDER=gemini`, `AI_MODEL=gemini-flash-latest` and secret `GEMINI_API_KEY`; see the [GitOps guide](docs/gitops.md) for both-repository setup, free-tier billing conditions and provider alternatives. No AI-generated shell, Terraform, or Kubernetes commands are executed.

### Resource planning

The input is an environment plus a high-level goal, such as “cost-sensitive staging” or “high-availability production”. The output is restricted to:

- Replicas: 1, 2, or 3 (production requires at least 2).
- CPU request: `100m`, `250m`, or `500m`.
- Memory request: `128Mi`, `256Mi`, or `512Mi`.
- A short rationale.

Unknown keys, wrong types, out-of-range values, and a one-replica production proposal are rejected locally even after API schema validation. Natural-language goals are passed as data, not interpolated into shell commands. These profiles are proposed application settings; they do not currently resize database or node infrastructure, and map into the common chart's replica count and resource requests. GCP values use portable minimums of 250m CPU/256Mi memory and at least 1 GiB requested memory per vCPU (500m therefore needs 512Mi); smaller proposals are raised to the required floor.

```sh
# Without credentials, this transparently reports source=policy-fallback.
python3 scripts/ai_ops.py --output artifacts/profile.json plan \
  --environment staging --goal 'Cost-sensitive staging'

# With AI_PROVIDER=gemini, AI_MODEL=gemini-flash-latest and GEMINI_API_KEY exported securely, require a real response:
python3 scripts/ai_ops.py --require-ai --output artifacts/profile.json plan \
  --environment production --goal 'High availability during a product launch'
```

### Health assessment

`probe.py` gathers a fixed number of HTTP readiness samples and accepts a measured **new-restart delta**. `ai_ops.py health` evaluates only numeric aggregates, never raw application logs, idea content, headers, or connection strings. Hard gates trigger rollback when error rate exceeds 5%, p95 latency exceeds 1500 ms, or any new restart occurs. AI can recommend rollback for additional concerns, but cannot suppress failed hard gates.

```sh
python3 scripts/probe.py --url http://localhost:8080 --count 20 \
  --new-restarts 0 --output artifacts/samples.json
python3 scripts/ai_ops.py --output artifacts/health.json health \
  --samples artifacts/samples.json
```

Exit codes: `0` = valid plan / keep; `2` = invalid input or required AI unavailable; `3` = rollback recommendation. A nonzero exit is a release failure. The deployment orchestrator uses the same assessment functions and fails the release on a rollback decision or invalid/required-AI failure; it restores the known-good revisions and verifies recovery.

The API timeout is 30 seconds, output is bounded, and server-side storage is disabled with `store=false`. Provider-side retention policies still apply. Missing credentials, a refusal, or an invalid/incomplete model response uses explicit conservative `policy-fallback` defaults, unless `--require-ai` is set. Production deployments should select that policy deliberately. Tests mock the API; no live AI call is claimed as verified.

Value: resource goals become small, auditable proposals instead of hand-edited settings; health decisions combine measurable gates with a readable explanation. The deterministic path keeps operation possible during an AI service outage. This is a bounded release assistant, not trained anomaly detection or a replacement for monitoring.

## Deployment evidence

| Target | Application URL | State |
| --- | --- | --- |
| AWS | Pending | Full flow implemented; not yet applied on a cloud account |
| GCP | Pending | Full flow implemented; not yet applied on a cloud account |

After running the full flow successfully on both clouds, run `scripts/smoke.py` against each public URL and record actual URLs, image digests, health reports, and workflow run links in [the verification record](docs/verification.md). Do not substitute localhost or invented cloud URLs for that deliverable.
