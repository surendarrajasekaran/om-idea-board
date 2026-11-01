# Operations

## Migrations

Run `python -m app.migrate` from the backend image before a release. Version one creates the ideas table if absent and serializes PostgreSQL execution with an advisory transaction lock. It never drops data. Cloud init containers also create/update a distinct application login with only SELECT/INSERT and sequence usage, refusing privileged/pre-grouped runtime roles. Managed database administrators do not have unrestricted PostgreSQL superuser privileges; role bootstrap is tested under a non-superuser database owner with CREATEROLE/CREATEDB. This is an initial-schema migration, not a full future migration framework. Introduce versioned Alembic migrations before changing the schema.

A successful application rollback must not roll back database data or destructive migrations automatically. Use expand/contract schema changes so the previous application version remains compatible. Test backups and restores before relying on them.

## Health and diagnostics

- `/health/live` checks the process. A database outage should not cause a liveness restart loop.
- `/health/ready` verifies access to the actual ideas table, detecting a missing migration.
- Backend `/metrics` exposes request count and duration by normalized route. It is not publicly proxied. Add scraping/alerting through the common platform's existing observability chart.
- `scripts/probe.py` measures short-term readiness latency/error rate. This is a post-deploy probe window, not a production traffic baseline or load test.
- `scripts/smoke.py` checks the frontend and a real write/read operation, creating a labeled idea. Run against both public endpoints after deployment.

For Compose failures: inspect `docker compose ps`, `docker compose logs migrate`, then backend/frontend/database logs. Never upload logs containing credentials to the AI service. The AI health interface accepts aggregate numeric fields only.

## Rollback policy

The Argo-managed AWS test application recovers through Git. The health workflow verifies release convergence, HTTP readiness and create/read behavior, then commits a previous verified snapshot's images/resources if recovery is required. Current security controls and Secret references persist. Snapshot hashes, expected-release checks and fast-forward pushes reject corrupted/stale observations. A pending recovery must converge and pass checks before it is marked healthy. The first installation has no automatic recovery target. See [GitOps delivery](gitops.md) for thresholds and guardrails.

The standalone health CLI returns code 3 for rollback recommendations and code 2 for invalid evidence or required-live AI failure. Manual deployment of separate targets outside Argo ownership records known-good Helm revisions and restores attempted releases in reverse order on failure; a failed first installation is uninstalled. That command remains unsuccessful after recovery. Do not run manual Helm recovery against the Argo-managed AWS test application.

## Security and scope limits

This case study intentionally implements a public, anonymous board. It has no user accounts, moderation, edit/delete API, or data ownership. The frontend rate limit is basic per-IP abuse mitigation; a public production product needs the organization's existing authentication, moderation, edge protections, TLS, and retention policy. Client IP handling behind a load balancer must follow the supplied chart's trusted-proxy configuration.

The list API returns all ideas to match the brief. Add cursor pagination and retention before high-volume use. The frontend uses external Google Fonts with system fallbacks. Application pods request only the permissions provided by the common chart; no pod IAM access is required by the application itself.

State contains database credentials. Restrict and audit state access. Rotate database passwords with a coordinated database/Secret change. Do not print `terraform output -raw database_url`, put it in command-line arguments, or copy it into a build artifact.

The custom values set resource requests/limits, non-root users, disabled service-account token mounts, and disruption budgets for multiple replicas. Review base-image/Action digests, horizontal autoscaling, workload spread, cluster RBAC, organization-specific TLS/PKI policy, and additional network integrations before production operation. Those additional controls are not automatically supplied by this case-study flow.

## Hardened deployment operations

Read [the platform review](platform-review.md) for residual risks and [the module guide](../infra/README.md) for private access, capacity and certificate configuration. Default API access is private. Production requires an existing TLS Secret and DNS hostname; staging HTTP is an explicit development/assignment tradeoff.

Namespace security policies persist through application rollback. Changing private DB ranges requires updating the generated allow policies from current Terraform outputs. RDS failover remains within the allowed DB subnets; policies do not pin a transient DNS-resolved RDS IP. GKE DNS rules include the node-local resolver addresses but allow only port 53, not metadata HTTP. Do not enable blanket Internet egress to repair a missing integration; add the intended destination/port and validate it.

Database and CA credentials are shared cluster Secrets, not Helm values. Rotation must coordinate the database, Secret and compatible application revisions. The rollout fingerprint includes both database URLs and the CA. Application rollback does not undo credential/CA changes or role bootstrap. Keep overlapping CA trust during rotation and validate read/write before removing old trust. The migration role's SQL diagnostics are sanitized to avoid exposing password literals.

SQL connection/query/lock/idle deadlines prevent unbounded database waits. Future migrations get longer bounded deadlines and still need expand/contract design. Test restores, alert routes, TLS expiry and node/add-on upgrades on real infrastructure; none are established by the local checks.
