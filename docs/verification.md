# Verification record

Earlier baseline verified locally on October 29, 2026. CI workflows define repeatable checks; remote run results are available in the repository's GitHub Actions. AWS test apply progress is recorded separately below; earlier local results do not imply a completed cloud deployment.

## October 31 AWS GitOps implementation and provisioning

| Check / component | Observed status |
| --- | --- |
| Script, policy, chart, CLI, provider and GitOps recovery tests | 44 passed |
| Terraform module tests | 8 passed with mock providers |
| GitOps source/deployment workflow Actionlint | Passed locally |
| Terraform target | AWS account 812752207041, us-west-2, isolated idea-board test stack |
| Remote state | Versioned private S3, TLS requirement, rotating customer KMS key; current bootstrap/application state objects verified SSE-KMS |
| Registry | Two immutable private ECR repositories created |
| CI federation | Exact source-repository/aws-test OIDC publisher role created; no cluster administration |
| Database | Private encrypted RDS available; live API uses ideas_app over TLS 1.3, without superuser/CREATEROLE/CREATEDB |
| NAT / EKS / workers | Created; EKS 1.35.9 Ready with private API, private worker and no control-plane health issues |
| Argo CD / public application | Installed; application Synced/Healthy; public frontend/backend identity and create/read smoke passed |
| AI | NVIDIA/Groq/OpenAI adapters tested with mocked responses; no provider key or live AI response yet |

Public AWS test URL: [Idea Board](http://af0d4388f01a74cebb0d087102ac80e7-5adda6a4d01432b5.elb.us-west-2.amazonaws.com). The baseline health report measured 20 requests, zero failures and p95 561.68 ms from the operator laptop; this is a small remote smoke observation, not a load benchmark. The assessment was explicitly `policy-fallback`, and the real create/read smoke created verification idea 1. Healthy status was committed to the deployment repository.

Live isolation checks confirmed the backend cannot connect to public HTTPS or instance metadata. The worker has no public IP, encrypted 20 GiB gp3, required IMDSv2 and hop limit 1. The private SSM path preserves endpoint CA/hostname checks. A final exact-target Terraform plan returned no differences.

Both actual published Linux amd64 frontend/backend digests passed the fixable HIGH/CRITICAL Trivy gate. The initial upstream Argo image and older Redis image failed their scans. The selected Docker hardened Argo 3.5.6 package scan and Redis 8.10.3 scan passed; the Argo mirror's platform manifest digest matches its upstream exactly. The hardened-image scan did not discover embedded Go module metadata, so it is a distribution-package result with maintained vendor provenance, not a complete language-level vulnerability claim.

GitHub workflow authorization and AWS SSO renewal completed on November 1. Source and deployment workflows are now published through the personal account. The first remote run passed application/frontend/Compose and Terraform module tests, but exposed two Linux portability issues: read-only provider initialization needed explicit Linux h1 hashes, and a fixed scanner UID made its private cache impossible for the host runner to delete. Provider lock entries are generated from signed registry packages for Linux amd64 and macOS arm64; the scanner now uses the unprivileged host UID/GID and a private disposable cache. Follow the repository's Actions run results for the subsequent pipeline evidence. No live model call has been made.

The GitOps implementation adds nine meaningful cases to the preceding 35-script suite, including immutable history, snapshot corruption, stale recovery, recovery preserving security/Secret references while restoring images/resources, no-first-release recovery, provider response validation and matching frontend/backend identity. The shared Terraform suite adds ECR coverage. The 13 PostgreSQL and three React cases bring the distinct application/platform total to 60; repeat backend runs are not counted twice.

## November 1 GitOps recovery exercise

The deliberately incompatible backend image was published in deployment commit `c2db359`. The HTTP monitor used an explicit 60-second convergence window for this controlled exercise (the scheduled default remains 600 seconds). It observed that the requested frontend/backend identity did not converge, with the previous healthy application continuing to answer readiness requests. The policy fallback committed recovery `bd79b81`, restoring the known-good application images/resources while preserving security controls and Secret references.

Argo CD applied recovery release `recovery-1793509010408156000`. Both public release identities matched; 20 readiness samples had zero failures, a real create/read smoke passed and verification idea 2 was created. Verification idea 1 from the baseline remained readable, demonstrating data persistence across this recovery. Healthy-state commit `26d6c69` cleared `rollback_pending`. This was real Git-to-Argo application recovery, driven by a manual invocation of the prepared health helper; it was not a live model decision or a remotely scheduled Actions run.

The private administration session expired during a controller Helm update, leaving a pending Helm revision. Restoring its last deployed controller revision and retrying the configuration update succeeded. This controller maintenance recovery is separate from the application's GitOps recovery.

The further cost change that scales the unused ApplicationSet controller to zero is applied after renewed AWS SSO access. The chart ignores an `applicationSet.enabled` setting; the corrected configuration uses `replicas: 0` and was render-verified.

## October 31 platform/security verification

These results cover local changes after `6349e55`, not a new published GitHub run or cloud deployment. Detailed scope, exceptions and remaining risks are in [the platform review](platform-review.md).

| Check | Observed result |
| --- | --- |
| Backend API suite with isolated SQLite | 11 passed; 2 PostgreSQL-only role cases skipped |
| Backend API and runtime-role suite on disposable PostgreSQL 16 | 13 passed, including non-superuser migration administrator |
| Script/chart/CLI/preflight/network/recovery suite | 35 passed |
| React tests and production build | 3 passed; build passed |
| Terraform 1.11.4 init with tracked lock, format and provider validation | Passed |
| Mock-provider Terraform database/network cases | 7 passed; no cloud resources created |
| Both-cloud IaC/container-source HIGH/CRITICAL gate | Passed with one scoped node-HTTPS exception, expiring 2027-01-31 |
| Local arm64 frontend/backend image archive scans | 0 fixable HIGH/CRITICAL vulnerabilities in both images |
| Frontend npm audit and pinned backend runtime pip audit | No known vulnerabilities reported |
| Python lint/format, YAML formatting, Helm lint and Actionlint | Passed |
| Unmodified nucleus chart hashes and rendered contracts | Passed |
| Custom stack production HTTPS/Secret/security render | Passed; includes separate namespace controls |
| Docker Compose image build, startup, create/read smoke | Passed |
| Non-root/read-only Nginx with bounded writable paths and HTTPS | Passed with certificate verification against a disposable localhost test CA |
| Backend restart persistence | Passed |

The 51 application/platform cases are 13 PostgreSQL backend/role cases + 35 script/chart/CLI cases + 3 React cases; SQLite repeats the applicable backend cases. The separate seven Terraform cases use mocked providers. Container scans cover locally built arm64 images; release CI must scan its own Linux amd64 artifact digests. The scanner's HIGH/CRITICAL gate ignores unfixed image issues, not all severity levels. Its configuration exception allows node TCP/443 to dynamic registries/APIs; it does not exempt arbitrary node egress or application pod egress.

The initial scan harness exposed that the current vulnerability database expands beyond 1 GiB; the shared scanner now uses disposable disk with bounded process memory instead of a 1 GiB memory-only cache. Final image scans passed using that corrected configuration. No Docker socket, state, local variable files or persistent credentials were mounted into the scanner.

Private API routing, cloud resource availability, real policy enforcement, production DNS/PKI/CA rotation, two public URLs and live-cluster rollback/restores remain unverified. A localhost test CA is local TLS evidence only. The Starlette test-client deprecation warning remains non-failing. No live OpenAI request was made.

## Historical October 29 baseline

## Observed local results

| Check | Result |
| --- | --- |
| Backend tests, isolated SQLite | 11 passed |
| Same backend tests, PostgreSQL 16 in Docker | 11 passed |
| AI policy tests, mocked model API | 10 passed |
| Common-chart contract, deployment policy and recovery transaction tests | 12 passed |
| Direct CLI import/standard-library regression check | Passed for all six entry points |
| Patched frontend and backend container scans (Trivy, local arm64) | 0 fixable HIGH/CRITICAL findings |
| Helm lint, frontend and backend values | Passed |
| AWS and GCP release rendering | Passed; both parse as valid YAML |
| GitHub Actions semantic validation (Actionlint) | Passed |
| React interaction tests | 3 passed |
| Production frontend build | Passed |
| Python lint | Passed |
| JavaScript/workflow formatting | Passed |
| NPM dependency audit | 0 vulnerabilities |
| Python pinned runtime audit | No known vulnerabilities |
| Terraform provider/module initialization | Passed; provider lock file recorded |
| Terraform format and schema validation | Passed |
| Full Compose build and ordered startup | Passed |
| Frontend → API → PostgreSQL smoke | Passed: readiness, create, read |
| Browser submission/search/reload | Passed; saved ideas persisted |
| Backend restart | Saved ideas remained available afterward |
| Desktop 1280 px and mobile 390 px layout | Visually inspected |
| Readiness probe window | 20 requests, 0 failures; p95 approximately 11 ms |
| Health decision CLI | keep, explicitly labeled policy-fallback |

The Starlette test client currently emits a deprecation warning about its httpx compatibility path; tests still pass. No live OpenAI request was performed. Aggregate probe timing is a local smoke observation, not a performance benchmark. Container vulnerability scanning gates both release CI and the laptop build flow. The initial frontend base had fixable findings; the runtime was upgraded and rebuilt. The initial backend binary PostgreSQL wheel bundled old native libraries; production now uses the patched distribution libpq instead. Final scan results are recorded below.

The local preview uses Docker Compose at http://localhost:8080. Test ideas remain in the local development volume. Screenshots and generated AI/probe reports are in ignored `artifacts/`, not committed application data.

## Historical cloud acceptance checklist (update from observed GitOps results)

| Field | AWS | GCP |
| --- | --- | --- |
| Environment | test / mit-qa / us-west-2 | Pending |
| Public application URL | [AWS test](http://af0d4388f01a74cebb0d087102ac80e7-5adda6a4d01432b5.elb.us-west-2.amazonaws.com) | Pending |
| Frontend image digest | Pending | Pending |
| Backend image digest | Pending | Pending |
| Common chart version | nucleus 1.1.0 vendored unchanged | nucleus 1.1.0 vendored unchanged |
| Infrastructure workflow run | Pending | Pending |
| Release/deployment workflow run | Pending | Pending |
| Smoke test | Public create/read passed | Pending |
| Health report | Keep, policy-fallback; HTTP-only | Pending |
| Rollback exercise | Verified Git recovery and public create/read; baseline data persisted | Pending |

Replace pending entries only with observed results. The deployment acceptance criteria are: public frontend works, new idea persists and appears through the API, database remains private, readiness passes, and a deliberately failed release returns to the prior verified healthy application through a GitOps recovery commit.

The first remote CI run caught a Python 3.12 standard-library shadowing issue in the `platform.py` script name. The entry point is now `scripts/run_platform.py`, and a subprocess regression test covers every CLI. Consult GitHub Actions for the latest run status.

## November 1 federation compatibility

GitHub's OIDC settings returned an immutable owner/repository subject prefix. The first ECR authentication attempt failed because its trust policy still used the legacy name-only subject. The Terraform interface now accepts the exact prefix, validates its repository binding and preserves the aws-test environment and STS audience restrictions. Three mock-provider trust cases passed (legacy, immutable and unrelated-repository rejection), bringing the current Terraform suite to 11. The reviewed live plan changes only the existing ECR publisher's trust policy.
