.PHONY: up down test build infra-check helm-check security-check
up:
	docker compose up --build --wait --wait-timeout 240
down:
	docker compose down
test:
	PYTHONPATH=backend .venv/bin/pytest -q backend/tests
	.venv/bin/python -m unittest discover -s tests -v
	npm --prefix frontend test
build:
	npm --prefix frontend run build
infra-check:
	terraform -chdir=infra fmt -check -recursive
	terraform -chdir=infra init -backend=false
	terraform -chdir=infra validate
	terraform -chdir=infra test

security-check:
	.venv/bin/python scripts/security_scan.py config

helm-check:
	helm lint deploy/charts/nucleus -f deploy/frontend/custom-values.yaml
	helm lint deploy/charts/nucleus -f deploy/backend/custom-values.yaml
