# Reusable infrastructure modules

The root is a thin environment composition layer. Cloud adapters contain no provider configuration and can also be called from another Terraform project. Each adapter is composed from independently reusable `network`, `kubernetes`, and `postgres` modules:

| Module | Inputs owned by caller | Responsibility |
| --- | --- | --- |
| `modules/aws/network` | Resource prefix, `/16` CIDR, two optional AZ names, HA, flow-log policy | Two-AZ VPC; derived public/private/database subnets; private-node NAT; flow logs |
| `modules/aws/kubernetes` | VPC/private subnet IDs, administrator CIDRs/role ARNs, node pool, Kubernetes version | EKS, access entries, add-ons, private API, encrypted nodes, IMDSv2, network-policy enforcement |
| `modules/aws/ecr` | Resource prefix, repository names, untagged retention | Private immutable scan-on-push repositories; retains tagged rollback images |
| `modules/aws/ci-registry-access` | Exact GitHub repository/environment, repository ARNs, existing OIDC provider | Short-lived GitHub federation and repository-scoped ECR publishing |
| `bootstrap` | Bucket name, account/region and OIDC ownership | Versioned private TLS-only state bucket, rotating KMS key, optional GitHub OIDC provider |
| `modules/aws/postgres` | VPC/node SG/database subnet group, database settings, class, HA | Private encrypted RDS, TLS enforcement, backups, log retention and separate passwords |
| `modules/gcp/network` | Project, region, five non-overlapping CIDRs, flow logs | VPC, pod/service ranges, NAT and SQL private service connection |
| `modules/gcp/kubernetes` | Project/network/subnet, master CIDR, trusted runner CIDRs | GKE Autopilot, private API, dedicated node service account and Dataplane V2 |
| `modules/gcp/postgres` | Project/network, region, database settings, tier, HA | Private Cloud SQL, per-instance CA, encrypted connections, PITR and bounded disk growth |

The database modules provision credentials but do not execute SQL. A bootstrap/migration process must create the limited runtime role. This application's migration image does that; another consumer can supply its own bootstrap process. The sensitive output contract is `database_url` (runtime `ideas_app`), `migration_database_url` (administrator), and `application_password`. Non-password connection metadata includes `database_host`, `database_ca_certificate`, and `database_egress_cidrs`. The public CA certificate output is still marked sensitive to preserve the provider's sensitivity boundary. Never print or export sensitive outputs to CI artifacts.

## Customize an environment

Keep account credentials in your normal cloud identity flow. Put non-secret capacity/address settings in an ignored `.tfvars` file:

```hcl
cloud       = "aws"
name        = "workboard"
environment = "staging"
region      = "ap-south-1"
admin_cidrs = ["10.20.1.10/32"] # Runner/VPN source visible to the private API.
public_cluster_endpoint = false
aws_network_cidr = "10.90.0.0/16"
aws_availability_zones = ["ap-south-1a", "ap-south-1b"]
aws_node_pool = {
  instance_types = ["t3.medium"] # Release images and AMI are x86_64.
  min_size = 1
  desired_size = 1
  max_size = 3
  capacity_type = "ON_DEMAND"
  disk_size = 20
}
database = {
  name = "ideas"
  storage_gb = 20
  max_storage_gb = 100
  backup_days = 7
  log_retention_days = 14 # RDS logs; GCP logs follow the project's Logging bucket policy.
}
labels = { owner = "platform", cost_center = "engineering" }
```

Use `--name workboard` in both `infra_init.py` and `run_platform.py`. The runner overrides the `.tfvars` target name/cloud/region/environment to match its CLI arguments. State uses `workboard/<environment>`, Kubernetes uses `workboard-<environment>`, and Services/releases/Secrets use `workboard-*`. The default `idea-board` preserves its original state path.

For GCP, replace AWS-specific settings with:

```hcl
gcp_project = "your-project-id"
gcp_network_cidrs = {
  nodes = "10.90.0.0/20"
  pods = "10.91.0.0/16"
  services = "10.92.0.0/20"
  master = "172.17.0.0/28"
  sql = "10.93.0.0/16"
}
gcp_database_tier = "db-custom-1-3840"
```

All five ranges must be disjoint. SQL reserves a `/16`; the control plane uses a `/28`. Confirm project/VPN/peering ranges do not overlap before planning. Cloud SQL owns automatic disk expansion: Terraform ignores later `disk_size` drift so a subsequent apply cannot try to shrink the live disk. `max_storage_gb` remains an enforced growth cap. Change initial `storage_gb` before creation; expand an existing disk through the Cloud SQL API/console, then keep the cap above its actual size.

## Call an adapter from another project

```hcl
module "platform" {
  source = "./om-idea-board/infra/modules/aws"
  name = "another-app-staging"
  region = "ap-south-1"
  ha = false
  admin_cidrs = ["10.20.1.10/32"]
  kubernetes_version = "1.35"
  deletion_protection = true
  administrator_arns = []
  flow_logs_enabled = true
  log_retention_days = 14
}
```

Configure AWS/random providers in the caller. For a registry/Git source, pin a reviewed commit or release. Child modules inherit providers and contain no environment-specific backend or credentials. Direct layer consumers must supply their required network references; they do not have to provision an entire platform.

## Availability and cost policy

- Staging defaults to one on-demand AWS node and one NAT gateway. This reduces idle worker capacity but deliberately has no worker redundancy. Production forces at least two nodes, uses NAT per AZ, and rejects a Spot-only baseline. Spot is an explicit staging option; supply multiple compatible x86 instance types and accept interruptions.
- Node min/desired/max are configurable bounds, not a claim that Cluster Autoscaler is installed. GKE Autopilot manages node capacity itself.
- EKS defaults to 1.35 and `STANDARD` support policy. AWS automatically upgrades the control plane after standard support ends rather than enrolling in paid extended support. Maintain planned upgrades for nodes, add-ons and clients; do not rely on that automatic action as the upgrade procedure. Verify region/version availability before apply.
- Database class/tier can be overridden independently of code. Defaults retain dedicated Cloud SQL capacity and production Multi-AZ/regional databases. Storage is capped at 100 GiB by default; backups retain 7 days in staging and at least 14 daily backups in production. GCP PITR logs retain 7 days.
- Flow logs default on. AWS stores them for 14 days; GCP samples 10% at ten-minute aggregation and uses the project's Logging retention policy. Disabling logs is an explicit observability/cost tradeoff.
- NAT, Kubernetes control planes, load balancers, databases, snapshots and log ingestion all incur charges. This change has not measured a cloud bill or a workload benchmark. Scale from observed CPU, memory, connections and latency.

## Private API and HTTPS prerequisites

The default control plane requires private connectivity (runner in the VPC/VPN/peered network). Give GKE the source CIDR visible to the private endpoint. To use a public endpoint deliberately, set `public_cluster_endpoint=true` and allow only real administrator/runner `/24` or narrower CIDRs. Never use the documentation example as a real allowlist. The scanner gates the private default; an explicit public opt-in will require a reviewed policy decision instead of silently passing the default gate.

Production deployment also requires `--tls-secret` and `--public-host`. Create a `kubernetes.io/tls` Secret in the target namespace with a trusted certificate/key covering that DNS name. The frontend serves TLS on 8443 through Service port 443. Point DNS at the allocated load balancer; the deployer prints its address while waiting for readiness. After renewing the Secret, rerun deployment (the certificate fingerprint triggers a rollout) or explicitly restart the frontend to reload Nginx. Provision/renew certificates through your existing PKI or cert-manager workflow; certificate issuance, DNS ownership and renewal are not created here. HTTP remains available only through the staging Service configuration unless TLS is selected there too.

RDS clients use `verify-full` with the official RDS CA bundle obtained over HTTPS. Cloud SQL clients use `verify-ca` with that instance's private per-instance CA; this private-service-access/IP topology does not supply the DNS identity required by `verify-full`. The CA is mounted read-only into both migration and runtime containers. Rotate Cloud SQL CA material with the documented overlap/rollout procedure; do not replace the per-instance mode with a shared CA without revisiting identity verification.

## Existing state and verification

`moved.tf` in each adapter maps original resource/module addresses to the new layers. This preserves address history; it does not promise a zero-change plan. Security settings, capacity, control-plane reachability and explicit SQL address reservations can change live resources. For a previously applied GCP stack, set the SQL reservation to its actual existing allocated range before planning. Do not rename an existing stack/state prefix as a migration shortcut. Back up state, inspect the plan, and never approve an unexpected database/network replacement.

```sh
terraform -chdir=infra init -backend=false -lockfile=readonly
terraform -chdir=infra validate
terraform -chdir=infra test
.venv/bin/python scripts/security_scan.py config
```

Terraform tests use mock providers and create no cloud resources. CI scans both cloud configurations and gates HIGH/CRITICAL findings. The single scoped, expiring HTTPS-node-egress exception is documented in `.trivyignore.yaml` and the platform review. Tests also verify that the vendored nucleus chart remains unchanged.

## ECR and Argo CD test delivery

AWS adapters expose `repository_urls` and optional `ecr_push_role_arn`. The ECR module creates frontend/backend repositories with immutable tags, scan-on-push, AES-256 encryption and seven-day untagged cleanup. Tagged images are retained for verified rollback. `force_delete=false` prevents implicit image loss; review retention and storage costs as release history grows.

Set `github_repository` and reuse `github_oidc_provider_arn` to enable the narrowly scoped publisher role. Trust requires the exact GitHub environment subject and STS audience; the role grants no EKS, database, Terraform or general account administration. The account bootstrap is separate to avoid a new app destroying shared federation/state trust roots.

The selected test target uses optional `aws_enable_ssm_access=true` for private API administration through an SSM-managed worker. EKS public access CIDRs are omitted when the endpoint is private; private RFC1918 addresses must not be sent as public endpoint CIDRs. See [the GitOps guide](../docs/gitops.md) for the current target, KMS backend settings, bootstrap and ownership boundaries.

AWS honors Systems Manager Quick Setup `QSConfigId-` ownership tags without trying to remove them on each plan. RDS PostgreSQL 16 defaults to mandatory SSL; the managed parameter remains explicitly `1` with the provider-reported pending-reboot application method, avoiding repeated apply-method-only drift. Verify runtime SSL and parameter apply status after any parameter-group change.
