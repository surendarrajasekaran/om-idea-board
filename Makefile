GITOPS_DIR ?= ../infra-helm-charts
export GITOPS_DIR

.PHONY: up down test build helm-check security-check
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
security-check:
	.venv/bin/python scripts/security_scan.py config

helm-check:
	helm lint "$(GITOPS_DIR)/helm-templates/nucleus" -f "$(GITOPS_DIR)/helm-overides/idea-fe/custom-values.yaml"
	helm lint "$(GITOPS_DIR)/helm-templates/nucleus" -f "$(GITOPS_DIR)/helm-overides/idea-be/custom-values.yaml"
	helm lint "$(GITOPS_DIR)/helm-templates/argocd-app-controller" -f "$(GITOPS_DIR)/helm-overides/argocd-app-controller/custom-values.yaml"
