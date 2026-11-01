# Verification record

Earlier baseline verified locally on October 29, 2026. CI workflows define repeatable checks; remote run results are available in the repository's GitHub Actions. AWS test apply progress is recorded separately below; earlier local results do not imply a completed cloud deployment.

## November 1 unified chart and override layout

The current GitOps layout places nucleus at `helm-templates/nucleus` (provenance at `helm-templates/nucleus-source.json`) and Application definitions' values at `helm-overides/argocd-app-controller/custom-values.yaml`. The generic chart remains `helm-templates/argocd-app-controller`; frontend/backend overrides retain their existing locations. Superseded `helm-common` and `bootstrap/idea-board-applications.yaml` paths were removed after the live cutover. Bootstrap retains only the scoped AppProject manifest.

Application rendering, release publication, recovery, CI, tests and operator commands now use the new paths. Source and GitOps recovery helpers remain identical. Original nucleus files and checksums were preserved; frontend/backend renders compared equal before/after the move. All 64 script/platform tests passed, plus Helm and workflow lint.

Helm bootstrap release `idea-board-test-apps` revision 2 installed the new Application values. Private API verification confirmed both Applications actually compared `helm-templates/nucleus`, with Synced/Healthy status and no conditions. All eight managed resources retained identical UIDs and specifications. The old directory was then removed in GitOps `45ae6e4`; source CI pins that cleaned revision. GitOps validation rejects reintroduction of the old chart directory or old bootstrap values file. Immutable release snapshots remain recovery inputs and were preserved.

[Source CI `274b9ce`](https://github.com/surendarrajasekaran/om-idea-board/actions/runs/41295652661), [cleaned-layout validation](https://github.com/surendarrajasekaran/infra-helm-charts/actions/runs/41295618991), [ECR/GitOps release](https://github.com/surendarrajasekaran/om-idea-board/actions/runs/41295652686) and [published values validation](https://github.com/surendarrajasekaran/infra-helm-charts/actions/runs/41295856633) passed. GitOps `79c6b60` published release `274b9ce243b7f9537e177270665ddee02ca46880-41295652686-1`. Both Applications reconciled it as Synced/Healthy with no conditions; both ready Deployments matched their images/resources/release IDs and all eight original resource UIDs were preserved. [Independent health](https://github.com/surendarrajasekaran/infra-helm-charts/actions/runs/41295856757) confirmed paired convergence, successful create/read and live-ai/keep, with 20 requests, zero failures and p95 156.88 ms. All 11 preexisting immutable recovery snapshots passed checksum verification during cleanup; the new release adds its own snapshot. No disruptive live rollback drill was performed.

## November 1 separate Argo Applications and repository ownership

This supersedes the earlier single-Application bootstrap. GitOps commit `de890e7` adds reusable chart `helm-templates/argocd-app-controller`, two-Application values `bootstrap/idea-board-applications.yaml` and separate scoped AppProject `bootstrap/idea-board-project.yaml`. The obsolete combined bootstrap manifest was removed. Source commit `56b646d` pins that reviewed GitOps revision, upgrades the private bootstrap command and removes an obsolete source-scanner exclusion. The application repository tracks no `helm-common`, `helm-overides` or `helm-templates` paths; a CI ownership check prevents reintroduction.

- [Generic chart validation](https://github.com/surendarrajasekaran/infra-helm-charts/actions/runs/41294657818) passed. Real Helm tests cover exactly two Applications, a single owner for namespace controls, disabled entries, explicit false overrides, reuse across repositories/projects, directory/Kustomize normalization and rejected invalid configuration. All 64 script/platform tests passed locally.
- [Source CI](https://github.com/surendarrajasekaran/om-idea-board/actions/runs/41294713094) passed backend, frontend, infrastructure, security and Compose jobs, including the pinned generic chart and chart-ownership guard.
- The old `idea-board-test` Application was paused and deleted without a cascading finalizer. Its eight existing resources were transferred by exact tracking annotation to `idea-board-backend` or `idea-board-frontend`. Helm release `idea-board-test-apps` revision 1 now creates exactly those two Application definitions in `argocd`; no parent Application or extra controller Pod was added.
- Private API verification returned **Synced / Healthy** for both Applications with no conditions. All eight resource UIDs were preserved. Both Deployment and Service specifications were identical before/after ownership transfer, and both Deployments remained ready `1/1`. Backend owns its Helm resources and the namespace controls; frontend owns its Helm resources. AppProject permissions and Secret bootstrap remain unchanged.
- [First two-Application release](https://github.com/surendarrajasekaran/om-idea-board/actions/runs/41294713160) passed tests, planning, both image builds/scans and publication. GitOps `80d786f` published release `56b646d9d6202261b2c4465e5e73cf7f8e5f7422-41294713160-1`; [value validation](https://github.com/surendarrajasekaran/infra-helm-charts/actions/runs/41294864170) passed. Both Applications then reconciled that revision and were Synced/Healthy without conditions. Both ready Deployments exactly matched their values' immutable images, resources and release IDs; all eight original resource UIDs still matched.
- [Independent new-release health](https://github.com/surendarrajasekaran/infra-helm-charts/actions/runs/41294864083) passed with `source=live-ai`, `decision=keep`, matching paired release identity and successful create/read. Twenty readiness requests had zero failures and p95 78.13 ms. Its artifact matches the exact release ID above; GitOps `3078959` records it healthy, with no pending rollback. Coverage remains HTTP only.
- The two Applications reconcile independently. Sync waves order controls before backend resources within its Application; they do not guarantee ordering between independently reconciled Applications. The existing paired-version HTTP monitor and Git recovery still cover both services together. No disruptive rollback drill was performed for this definition-only migration.

## November 1 direct Helm values and visible AI planning

This migration supersedes the earlier chart-ownership layouts below. The canonical chart and service values now live only in `infra-helm-charts`, at `helm-common/nucleus`, `helm-overides/idea-fe/custom-values.yaml` and `helm-overides/idea-be/custom-values.yaml`. Application CI checks out reviewed GitOps revision `015a3dd` for chart contracts through `deploy/gitops/chart-source.json`.

- [Source CI `d5a7717`](https://github.com/surendarrajasekaran/om-idea-board/actions/runs/41291253831) passed: 58 script/chart/policy/provider/recovery cases, 74 application/platform cases overall, 11 Terraform mock-provider cases, lint/build, audits, configuration scans and Compose persistence.
- [ECR/GitOps release](https://github.com/surendarrajasekaran/om-idea-board/actions/runs/41291253782) passed, updating both service values with immutable tags/digests, the accepted resource profile and release identity. GitOps commit `16a83ee` includes `delivery=helm`, rendered snapshots and new checksummed Helm-value snapshots. [GitOps chart/value validation](https://github.com/surendarrajasekaran/infra-helm-charts/actions/runs/41291414593) passed.
- The live Argo Application was changed to three sources: backend Helm, frontend Helm and directory security controls (`include: controls.yaml`). Private API verification returned **Synced / Healthy**, three matching Git revisions and no conditions. Both existing Deployments were ready `1/1`; their images matched this release and each requested 250m CPU / 128Mi memory, with fixed 1 CPU / 512Mi limits. Seeded Helm rendering preserved the prior live resource definitions, apart from environment-variable ordering.
- [New-release AI health](https://github.com/surendarrajasekaran/infra-helm-charts/actions/runs/41291414658) passed with `source=live-ai`, `decision=keep`, version convergence and successful create/read. Twenty requests had zero failures and p95 96.12 ms; coverage is HTTP only.
- [Visible AI planning demo](https://github.com/surendarrajasekaran/om-idea-board/actions/runs/41289856695) passed with its submitted goal and validated JSON plan printed in Actions. Planner and health commands also append escaped, credential-redacted job-summary tables. The one-call AI-check workflow accepts a goal. Four output tests cover live/fallback/skipped labeling, untrusted text/command escaping, secret redaction and unchanged release data.
- Real Helm recovery tests verify value updates, current security/Secret preservation, value-snapshot corruption detection and compatibility with older manifest-only snapshots. No new disruptive live rollback drill was performed during this migration.

A final publisher follow-up (`89f5f4e`) limits updates to image coordinates, bounded resources and release identity, preserving current GitOps configuration such as rotated database/CA Secret references. The added regression assertions passed in all 58 platform cases. [Follow-up CI](https://github.com/surendarrajasekaran/om-idea-board/actions/runs/41292570632), [native Helm release](https://github.com/surendarrajasekaran/om-idea-board/actions/runs/41292570647) and [health verification](https://github.com/surendarrajasekaran/infra-helm-charts/actions/runs/41292767079) passed. Without another Application change, Argo reconciled GitOps commit `fc020a1` through its Helm sources and was Synced/Healthy. Both ready Deployments' images, resources and release identity matched their respective values files exactly. Verified follow-up release: `89f5f4e393e8bfaab6744ca2c0b6559f4fafc2d6-41292570647-1`.

Verified Helm release: `d5a7717f2cbe9164dfb98d365435f602cbcd8a98-41291253782-1`. Rollback updates the same Helm values and preview snapshots; rendered application YAML under `manifests` is evidence/recovery data and is excluded from Argo's directory source. Namespace controls and database/CA Secret ownership are unchanged.

## November 1 repository cleanup

The application repository now owns the single canonical nucleus 1.1.0 chart and frontend/backend values. The GitOps publisher renders those files at its source commit; chart and value changes trigger the application release workflow. The duplicate chart, values and provenance copy were removed from the GitOps repository (24 files), leaving rendered desired state, bootstrap definitions, monitor helpers and immutable recovery snapshots.

The retired GHCR/direct-Helm Actions workflow was removed. The README and AI handoff were consolidated around ECR/GitOps/Gemini, and manual non-Argo deployment/operations documentation was corrected. Both cloud Terraform adapters, the original chart/provenance, operational state and release recovery history were retained.

- A real Helm regression test publishes into a GitOps repository with no chart directory. All **52** script/chart/policy/CLI/provider/recovery cases passed. Rendering the pre-cleanup release with the same inputs produced byte-identical frontend, backend and security-control manifests.
- [Source CI for cleanup commit `4a7ede4`](https://github.com/surendarrajasekaran/om-idea-board/actions/runs/41283855193) passed, including 68 application/platform cases, 11 Terraform mock-provider cases, dependency/configuration checks and Compose persistence. Local Ruff, Actionlint and Markdown file-link checks passed.
- [ECR/GitOps release from the canonical chart](https://github.com/surendarrajasekaran/om-idea-board/actions/runs/41283855117) passed verification, planning, both image scans and publication. GitOps release commit: `09b649d`.
- GitOps cleanup commit `a863b1b` removed the duplicate chart files. [Health verification executed from that repository](https://github.com/surendarrajasekaran/infra-helm-charts/actions/runs/41284101126) passed with `source=live-ai`, `decision=keep`, matching component versions and successful create/read. It observed 20 requests, zero failures and p95 **230.86 ms**, with no policy violations. This is HTTP-only smoke evidence.

Verified release: `4a7ede45f00627b1d8366e066580691cccf19c15-41283855117-1`. The actual current release and recovery status remain authoritative in the GitOps repository's `release.json` and `status.json`.

## November 1 Gemini live verification

The selected provider is `gemini`, model `gemini-3.5-flash-lite`. Both repositories set repository variable `AI_ENVIRONMENT=GEMINI_API_KEY` to select the dedicated environment containing the rotated `GEMINI_API_KEY` secret. Its environment variables select the provider/model. AWS build/publish jobs continue to use `aws-test`. No key values are stored in source, reports or Terraform.

- [Standalone required-live provider check](https://github.com/surendarrajasekaran/om-idea-board/actions/runs/41282655825) passed and produced `source=live-ai`. The original `gemini-flash-latest` checks returned HTTP 503 and timed out; the user approved switching to the pinned Flash-Lite model.
- [Source CI](https://github.com/surendarrajasekaran/om-idea-board/actions/runs/41282734678) passed for `aef4b5e`: 67 application/platform cases (13 PostgreSQL backend, 51 script/chart/policy/provider/recovery, 3 React), 11 Terraform mock-provider cases, Compose/persistence, lint/build/audits and configuration scans. The seven new Gemini cases include multiple invalid-response/model subcases, safe HTTP diagnostics, no key forwarding on redirects, bounded output and quota fallback.
- [Required-live ECR/GitOps release](https://github.com/surendarrajasekaran/om-idea-board/actions/runs/41282749169) passed with `require_ai=true`. Gemini proposed one replica, 250m CPU and 128Mi requested memory per component. Both Linux amd64 images passed the fixable HIGH/CRITICAL scan gate. GitOps release commit: `e4f9e9d`.
- [Independent deployed-release health](https://github.com/surendarrajasekaran/infra-helm-charts/actions/runs/41282887901) passed with `source=live-ai`, `decision=keep`, no policy violations, exact frontend/backend version convergence and a successful create/read smoke test. HTTP evidence: 20 requests, zero failures, p95 **110.77 ms**. Coverage is HTTP only; this is a small smoke window rather than a load benchmark. Health commit `36fbb8c` records the release as healthy with no pending recovery.

Current healthy release: `aef4b5e18879954f2041dc0886eca756515657fb-41282749169-1`.

| Image | Verified deployment digest |
| --- | --- |
| Frontend | `sha256:1ad2523feb923143bcb921103d977cff5bc23d22e7f852b826a1b472d5745291` |
| Backend | `sha256:7119ba1be9607409d9473124c70e9a416d136f762b08c193109d989049d34a56` |

The earlier rollback drill below exercised Git recovery with deterministic policy. This Gemini verification exercised a healthy live assessment; it does not claim a new AI-triggered rollback drill. Healthy steady-state observations avoid further model calls. A Free Tier project is required for free quota; billing-enabled project usage may be charged under Google's pricing.

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
| AI | Gemini Flash-Lite live planning and deployed HTTP health assessment passed; 51 script/chart/policy tests pass, including 7 Gemini cases and additional subcases. See November 1 evidence below |

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

## November 1 automated delivery accepted

The full hosted delivery path is now observed, including the corrected federation trust:

| Evidence | Result |
| --- | --- |
| [Latest code CI](https://github.com/surendarrajasekaran/om-idea-board/actions/runs/41276404191) | Passed: backend, frontend, Compose, both-cloud configuration scan and 11 Terraform cases |
| [ECR and GitOps release](https://github.com/surendarrajasekaran/om-idea-board/actions/runs/41275785592) | Attempt 2 passed: exact OIDC authentication, both Linux amd64 builds/scans and GitOps publication |
| GitOps release commit | `0015f83`; application source commit `f2f202a` (the subsequent `4f1b503` changes infrastructure trust/tests/docs only) |
| Argo CD | Synced and Healthy; public frontend/backend identities match the CI release |
| [New-release health workflow](https://github.com/surendarrajasekaran/infra-helm-charts/actions/runs/41276535583) | Passed with 20 requests, zero failures, p95 153.21 ms, and a real create/read smoke |
| Healthy-state commit | `6408d3e` records the CI release as healthy, with no pending rollback |
| Unused ApplicationSet controller | Zero replicas; four Argo controller/cache/server pods remain |

Current release: `f2f202a189c020d222b335c25db52eb2c82f5008-41275785592-2`. This is a successful CI → private ECR → separate GitOps repository → Argo CD → hosted health check execution. The latency figure is a small GitHub-runner smoke window, not a load benchmark. Its health source is explicitly `policy-fallback`; a live NVIDIA/Groq/OpenAI request remains unverified until a provider API key is configured. The scheduled health workflow is now published and enabled.

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
| Frontend image digest | sha256:7d4e5480ef3aa6d5c4f4f8fe3574a1d178f9d11aee1cfa578c1df31ea99ed54e | Pending |
| Backend image digest | sha256:af21eb50ca9a2e94b4befde5b3b2a97077df258691a5f8723320a66761517beb | Pending |
| Common chart version | nucleus 1.1.0 vendored unchanged | nucleus 1.1.0 vendored unchanged |
| Infrastructure provisioning | Authenticated Terraform CLI applies succeeded | Pending |
| Release/deployment workflow run | [Passed](https://github.com/surendarrajasekaran/om-idea-board/actions/runs/41275785592) | Pending |
| Smoke test | Public create/read passed | Pending |
| Health report | Keep, policy-fallback; HTTP-only | Pending |
| Rollback exercise | Verified Git recovery and public create/read; baseline data persisted | Pending |

Replace pending entries only with observed results. The deployment acceptance criteria are: public frontend works, new idea persists and appears through the API, database remains private, readiness passes, and a deliberately failed release returns to the prior verified healthy application through a GitOps recovery commit.

The first remote CI run caught a Python 3.12 standard-library shadowing issue in the `platform.py` script name. The entry point is now `scripts/run_platform.py`, and a subprocess regression test covers every CLI. Consult GitHub Actions for the latest run status.

## November 1 federation compatibility

GitHub's OIDC settings returned an immutable owner/repository subject prefix. The first ECR authentication attempt failed because its trust policy still used the legacy name-only subject. The Terraform interface now accepts the exact prefix, validates its repository binding and preserves the aws-test environment and STS audience restrictions. Three mock-provider trust cases passed (legacy, immutable and unrelated-repository rejection), bringing the current Terraform suite to 11. The reviewed live plan changes only the existing ECR publisher's trust policy.
