# Verification record

Verified locally on October 29, 2026. CI workflows define repeatable checks; no GitHub-hosted run or cloud apply is claimed.

## Observed local results

| Check | Result |
| --- | --- |
| Backend tests, isolated SQLite | 11 passed |
| Same backend tests, PostgreSQL 16 in Docker | 11 passed |
| AI policy tests, mocked model API | 10 passed |
| Common-chart contract, deployment policy and recovery transaction tests | 12 passed |
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

## Cloud evidence — not deployed

| Field | AWS | GCP |
| --- | --- | --- |
| Environment | Pending | Pending |
| Public application URL | Pending | Pending |
| Frontend image digest | Pending | Pending |
| Backend image digest | Pending | Pending |
| Common chart version | nucleus 1.1.0 vendored unchanged | nucleus 1.1.0 vendored unchanged |
| Infrastructure workflow run | Pending | Pending |
| Release/deployment workflow run | Pending | Pending |
| Smoke test | Pending | Pending |
| Health report | Pending | Pending |
| Rollback exercise | Pending | Pending |

Replace pending entries only with observed results. The deployment acceptance criteria are: public frontend works, new idea persists and appears through the API, database remains private, readiness passes, and a deliberately failed release returns to the prior healthy chart revision.
