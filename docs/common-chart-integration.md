# Supplied nucleus chart integration

`deploy/charts/nucleus` is an unchanged copy of the user-supplied nucleus 1.1.0 chart. `deploy/charts/nucleus-source.json` records SHA-256 checksums for its Chart.yaml, defaults, README, and templates. Contract tests verify every copied file. This is the single canonical chart copy. The GitOps publisher renders it and the source component values at the release source commit, then publishes only generated manifests and recovery metadata. Optional upstream templates remain intact to preserve the reusable chart contract and recorded hashes. There are no replacement application Deployment templates.

| Component | Custom values | Release/Service name | Port | Exposure |
| --- | --- | --- | --- | --- |
| Frontend | `deploy/frontend/custom-values.yaml` | `idea-board-frontend` | 8080 / Service 80 | LoadBalancer |
| Backend | `deploy/backend/custom-values.yaml` | `idea-board-backend` | 8000 | ClusterIP |

The namespace is `<name>-<environment>`, including `idea-board-test` for the current AWS target. The frontend's `BACKEND_HOST` matches the fixed backend Service name. The same release names work on different clusters; environments use different namespaces.

## Values mapping

- Validated AI replicas → `workload.replicaCount`.
- Validated CPU/memory requests → `resources.requests`; fixed limits are 1 CPU and 512Mi memory. GKE profiles below 250m CPU/256Mi memory are raised to those portable minimums.
- Image → `image.repository`, `image.tag`. The original chart concatenates `repository:tag`; for digest pinning we use a valid `repository:commit@sha256:digest` reference. Digest-only input becomes `repository:pinned@sha256:digest`; the digest selects the content.
- Private registry access → `image.pullSecrets` referencing a namespace Secret.
- Database connection → `envFrom` referencing `idea-board-database`. No database password appears in Helm values or release artifacts.
- Backend migration → chart-supported `initContainers`, templated with the same backend image. Each pod runs `python -m app.migrate` before starting the API; PostgreSQL advisory locking serializes the additive migration.
- Readiness `/health/ready`, liveness `/health/live`, and startup probes → native chart probe fields.
- Production defaults are at least two replicas; the chart emits the enabled PodDisruptionBudget only with multiple replicas.

Both root filesystems are read-only. Bounded writable volumes hold Nginx's rendered configuration, cache and temporary files. Both drop Linux capabilities and disable privilege escalation and service-account token automounting.

## Cloud public endpoint

Both clouds use the chart's `LoadBalancer` Service, so no extra ingress controller is needed for this case study. AWS values request an NLB supported by EKS's legacy service controller; this avoids a separate controller/IAM bootstrap. GKE uses its external L4 load balancer. Staging can serve HTTP on the allocated hostname/IP. Production requires a provided TLS Secret and DNS hostname; Nginx serves TLS on 8443 through Service 443 without an ingress-controller dependency. DNS ownership and certificate issuance/renewal remain external prerequisites. No domain or certificate is invented.

AWS documentation: https://docs.aws.amazon.com/eks/latest/userguide/network-load-balancing.html

## Rollout and failure recovery

For the Argo-managed AWS test application, use [GitOps delivery](gitops.md). For separate targets outside Argo ownership, `scripts/run_platform.py` initializes matching remote state, optionally applies infrastructure, builds/publishes/scans images, obtains a run-scoped kubeconfig, then invokes `scripts/deploy.py`.

The deployer validates the profile and image references, checks Terraform name/cloud/environment outputs, applies namespace admission, quotas and network policies, and records deployed revisions. It refuses an existing failed/pending Helm release rather than assuming a fresh installation. It updates separate runtime/migration database Secrets, a read-only database CA Secret and optional registry credentials through stdin, then upgrades backend and frontend with Helm's failure rollback and bounded waits. Helm 3 (`--atomic`) and Helm 4 (`--rollback-on-failure`) are supported.

After rollout it waits for public load-balancer readiness, measures twenty HTTP probes and container restart deltas, performs the bounded AI/policy health assessment, and runs a real create/read smoke test. Failures restore attempted releases in reverse order to the recorded revisions. First-install releases have no known-good version and are removed on failure. Existing successful installations are checked again after recovery. Recovery failures are recorded explicitly; the release command exits nonzero even when recovery succeeds.

Sanitized `deployment.json` and `health.json` include target, immutable images, profile, public URL, previous revisions, final status, and recovery result. They never contain database/registry credentials. Secrets are not automatically deleted during recovery, and application rollback never reverts database data or schema. Do not introduce destructive migrations without a versioned expand/contract process.

## Rendering without cloud access

```sh
.venv/bin/python scripts/ai_ops.py --output artifacts/profile.json plan \
  --environment staging --goal 'Cost-sensitive staging'
.venv/bin/python scripts/deploy.py --cloud aws --environment staging \
  --frontend-image ghcr.io/surendarrajasekaran/om-idea-board/frontend:COMMIT \
  --backend-image ghcr.io/surendarrajasekaran/om-idea-board/backend:COMMIT \
  --profile artifacts/profile.json --render-only \
  --database-egress-cidr 10.40.21.0/24 --database-egress-cidr 10.40.22.0/24 \
  --output artifacts/render-aws
```

Use `--cloud gcp` to render GCP settings. Render-only never connects to Kubernetes or Terraform and never deploys anything.

Namespace admission/quota/network policies are owned by the deployment layer outside Helm so application rollback cannot remove them. Render-only also writes `namespace-rendered.yaml`; apply it as a control-plane resource, not as a third nucleus release. Render CIDRs must match the actual private database subnets/reservation. The runtime API gets only its limited database Secret; the migration init container gets administrator credentials and application-role bootstrap inputs. Both mount the CA. The frontend uses a read-only root plus bounded config/cache/tmp volumes; provided TLS material is also mounted read-only.
