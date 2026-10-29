# Full flow on the configured laptop

The code is ready to execute; real cloud provisioning/public URL verification has not been performed on the development laptop. Do not mark those deliverables complete until the commands below succeed on each cloud.

## 1. Pull and install prerequisites

```sh
git clone https://github.com/surendarrajasekaran/om-idea-board.git
cd om-idea-board
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt
```

Install Terraform 1.10+ (tested 1.11.4), Helm 3.19+ or 4, kubectl compatible with your cluster version, Docker with Buildx, and AWS CLI v2 / Google Cloud CLI. For GKE also install `gke-gcloud-auth-plugin`. Authenticate AWS with the intended profile/role and GCP with Application Default Credentials. Ensure billing/API permissions, resource quotas, and your actual public egress CIDR are configured. The root README documents remote-state bucket and OIDC bootstrap.

## 2. Configure state and cloud variables

Create dedicated encrypted/versioned S3 and GCS state buckets outside this stack. Copy and edit the examples:

```sh
cp infra/environments/aws.example.tfvars infra/aws.tfvars
cp infra/environments/gcp.example.tfvars infra/gcp.tfvars
```

Replace the reserved example `admin_cidrs` with your laptop/runner egress CIDRs. Set the real GCP project. Use `staging` for initial verification and confirm the EKS Kubernetes version is supported in the target region. State and plan files contain database credentials; do not commit or share them.

## 3. Configure image and optional AI access

Authenticate Docker to GHCR with an identity allowed to publish this repository's packages. For private images, export `GHCR_USERNAME` and `GHCR_TOKEN` through your shell's secure secret mechanism. Local builds need package write permission; clusters only need package read access. For least privilege, use a read-only cluster token and a separate Docker login identity for publishing. Alternatively, use public packages or `--pull-secret EXISTING_NAMESPACE_SECRET`.

Do not put credentials in command history or tracked files. The deployment script sends credentials through stdin, not command-line arguments or Helm values. A supplied token becomes a persistent namespace pull secret; use an appropriate expiry/rotation policy, not a short-lived GitHub Actions token.

To use live AI, export `OPENAI_API_KEY` and `OPENAI_MODEL`. Add `--require-ai` to make an unavailable/rejected AI response fail the operation. Without these settings, JSON reports explicitly state `policy-fallback`.

## 4. AWS: full provision → build/scan → deploy → verify

```sh
.venv/bin/python scripts/platform.py \
  --cloud aws --environment staging --region ap-south-1 \
  --state-bucket YOUR_AWS_STATE_BUCKET --var-file infra/aws.tfvars \
  --goal 'Cost-sensitive staging with reliable service'
```

The command applies a saved Terraform plan without a second interactive prompt. It creates chargeable infrastructure. It then builds Linux amd64 images with the current Git commit tag, publishes SBOM/provenance, scans for fixable high/critical vulnerabilities, configures an isolated kubeconfig, deploys the supplied common chart twice, and checks the application. It exits nonzero if any stage fails.

## 5. GCP: the same flow with three cloud settings changed

```sh
.venv/bin/python scripts/platform.py \
  --cloud gcp --environment staging --region asia-south1 \
  --state-bucket YOUR_GCP_STATE_BUCKET --var-file infra/gcp.tfvars \
  --goal 'Cost-sensitive staging with reliable service'
```

Clouds use different remote state. Run them sequentially in this checkout; use separate clones for concurrent cloud operations. The script enforces matching cloud, environment, and region. It does not migrate or overwrite the other cloud's state.

## 6. Reuse built images or existing infrastructure

With existing remote state and images, skip expensive stages:

```sh
.venv/bin/python scripts/platform.py \
  --cloud aws --environment staging --region ap-south-1 \
  --state-bucket YOUR_AWS_STATE_BUCKET --skip-infra --skip-build \
  --frontend-image ghcr.io/surendarrajasekaran/om-idea-board/frontend:COMMIT@sha256:DIGEST \
  --backend-image ghcr.io/surendarrajasekaran/om-idea-board/backend:COMMIT@sha256:DIGEST
```

Replace COMMIT/DIGEST with real release artifacts. `--skip-build` assumes those images already passed scanning; it does not rebuild or rescan them. `--profile PATH` reuses the exact prepared JSON profile instead of asking AI again. `--tag TAG` can select an existing explicit tag when images are not passed separately. Mutable `latest` is rejected.

## 7. Evidence and recovery

The successful public URL is printed and saved to `artifacts/aws-staging/deployment.json` or `artifacts/gcp-staging/deployment.json`. The same directory contains the health report and profile (unless reusing an external profile). Record the actual URLs and deployment evidence in `docs/verification.md` after execution.

A failed rollout or post-deployment check restores recorded Helm revisions and checks recovery. On first installation, created releases are removed because there is no previous successful revision. The command still fails after successful recovery. Check `deployment.json` for recovery status; a failure before application deployment may have no deployment report. Infrastructure and database resources are never destroyed automatically on application failure.

The baseline public endpoints use HTTP and an anonymous board to match the case study. The smoke test adds one labeled idea per successful verification. Add your organization's DNS/TLS and authentication policies before using sensitive data.

## GitHub Actions equivalent

1. Configure the four cloud/environment environments and OIDC/state/runner variables in the README. Include the self-hosted runner's egress CIDR in the cluster API allowlist. Install AWS CLI on the trusted `idea-board` runner; GCP tooling is installed by its workflow steps.
2. Run **Infrastructure**, selecting cloud/environment and `apply`.
3. Run **Release and deploy**, selecting the same cloud/environment, `deploy=true`, and the AI requirement. It tests, prepares a profile, builds/scans/publishes images, and deploys using those exact artifacts. Set `GHCR_READ_TOKEN` + `GHCR_USERNAME`, `REGISTRY_PULL_SECRET`, or `GHCR_IMAGES_PUBLIC=true` for cluster pulls.
4. Download the sanitized deployment evidence artifact and update the actual URL record.

No cloud run is triggered automatically by a source push. PR/main push CI verifies the code; privileged provisioning and release operations are explicit dispatches on main.
