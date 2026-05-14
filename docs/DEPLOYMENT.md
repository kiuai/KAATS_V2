# KAATS Deployment Guide

Step-by-step procedures for deploying, validating, and rolling back the KAATS
application. Covers infrastructure provisioning, image builds, and database
migrations.

---

## Table of contents

1. [Prerequisites](#1-prerequisites)
2. [Environment overview](#2-environment-overview)
3. [Pre-deploy checklist](#3-pre-deploy-checklist)
4. [Deploy procedure](#4-deploy-procedure)
5. [Post-deploy validation](#5-post-deploy-validation)
6. [Rollback procedure](#6-rollback-procedure)
7. [Infrastructure changes (Bicep)](#7-infrastructure-changes-bicep)
8. [First-time environment setup](#8-first-time-environment-setup)

---

## 1. Prerequisites

| Tool | Min version | Purpose |
|---|---|---|
| Azure CLI (`az`) | 2.60 | Container Apps, Key Vault, ACR |
| Docker | 24 | Image builds |
| Python | 3.12 | Alembic migrations |
| Node.js | 20 | Frontend build |
| Bicep CLI | 0.28 | Infrastructure deployments |
| `jq` | 1.6 | JSON parsing in scripts |

Login before deploying:
```bash
az login
az acr login --name acrkaats<env>   # e.g. acrkaatsprod
```

---

## 2. Environment overview

| Environment | Branch | Container Apps env | Base URL |
|---|---|---|---|
| dev | any feature branch | `cae-kaats-dev` | `http://localhost:5173` |
| staging | `main` | `cae-kaats-staging` | `https://kaats-staging.kiu.ai` |
| prod | tagged release | `cae-kaats-prod` | `https://kaats.kiu.ai` |

CI/CD pipeline (GitHub Actions) handles staging deploys automatically on merge
to `main`. Production deploys require a manual `workflow_dispatch` trigger with
an explicit image tag.

---

## 3. Pre-deploy checklist

Complete all items before cutting a production deploy.

### Code readiness
- [ ] All CI checks pass on the target commit (lint, type-check, unit tests, E2E)
- [ ] No `TODO(release)` markers in the diff
- [ ] CHANGELOG updated (if maintained)

### Database migrations
- [ ] All new Alembic migrations have been reviewed for:
  - Backward compatibility (new NULLable columns, no dropped columns)
  - Index creation uses `CONCURRENTLY` or equivalent non-blocking DDL
  - `downgrade()` function is implemented and tested
- [ ] Migrations tested against a staging DB snapshot

### Secrets & configuration
- [ ] All new `Settings` fields have values in the target environment's Key Vault
- [ ] `acsSenderAddress` and `frontendBaseUrl` are set in the relevant `.bicepparam` file
- [ ] No secrets committed to the repository (check with `git diff --name-only HEAD~1 | xargs grep -l 'password\|secret\|key'`)

### Infrastructure
- [ ] Bicep diff reviewed (if infra changed): `az bicep build --file infrastructure/bicep/main.bicep`
- [ ] No breaking changes to Container Apps environment variables (check existing revisions)

---

## 4. Deploy procedure

### 4.1 Build and push images

```bash
ENV=prod
ACR=acrkaatsprod
TAG=$(git rev-parse --short HEAD)

# API
docker build -t ${ACR}.azurecr.io/kaats-api:${TAG} \
  -f backend/Dockerfile backend/
docker push ${ACR}.azurecr.io/kaats-api:${TAG}

# Worker
docker build -t ${ACR}.azurecr.io/kaats-worker:${TAG} \
  --target worker -f backend/Dockerfile backend/
docker push ${ACR}.azurecr.io/kaats-worker:${TAG}

# Scheduler
docker build -t ${ACR}.azurecr.io/kaats-scheduler:${TAG} \
  --target scheduler -f backend/Dockerfile backend/
docker push ${ACR}.azurecr.io/kaats-scheduler:${TAG}

# Frontend
docker build -t ${ACR}.azurecr.io/kaats-frontend:${TAG} \
  -f frontend/Dockerfile frontend/
docker push ${ACR}.azurecr.io/kaats-frontend:${TAG}
```

### 4.2 Run database migrations

Run migrations before updating the containers so that the new schema is in
place before new code starts serving traffic.

```bash
# Run Alembic in a temporary container (uses existing prod DB connection)
az containerapp job start \
  --name alembic-migrate \
  --resource-group rg-kaats-prod \
  --image ${ACR}.azurecr.io/kaats-api:${TAG} \
  --command "alembic upgrade head"
```

Alternatively, exec into the running API container:
```bash
az containerapp exec -n ca-api-kaats-prod -g rg-kaats-prod \
  --command "alembic upgrade head"
```

Verify the migration ran:
```bash
az containerapp exec -n ca-api-kaats-prod -g rg-kaats-prod \
  --command "alembic current"
# Should print the latest revision hash
```

### 4.3 Deploy new container revisions

```bash
RG=rg-kaats-prod

# API
az containerapp update \
  -n ca-api-kaats-prod -g ${RG} \
  --image ${ACR}.azurecr.io/kaats-api:${TAG}

# Worker
az containerapp update \
  -n ca-worker-kaats-prod -g ${RG} \
  --image ${ACR}.azurecr.io/kaats-worker:${TAG}

# Scheduler
az containerapp update \
  -n ca-scheduler-kaats-prod -g ${RG} \
  --image ${ACR}.azurecr.io/kaats-scheduler:${TAG}

# Frontend
az containerapp update \
  -n ca-frontend-kaats-prod -g ${RG} \
  --image ${ACR}.azurecr.io/kaats-frontend:${TAG}
```

Container Apps creates a new revision for each update. The old revision remains
available for rollback (see §6).

### 4.4 Verify rollout

```bash
# Watch revision status
az containerapp revision list \
  -n ca-api-kaats-prod -g ${RG} \
  --query "[].{name:name, active:properties.active, replicas:properties.replicas}" \
  -o table

# Tail logs
az containerapp logs show -n ca-api-kaats-prod -g ${RG} --tail 50 --follow
```

---

## 5. Post-deploy validation

Run these checks immediately after every production deploy.

### 5.1 Health endpoints

```bash
BASE=https://api.kaats.kiu.ai

# Must return 200
curl -sf ${BASE}/health/live | jq .

# Must return 200 (or 503 if a dependency is degraded — investigate if so)
curl -sf ${BASE}/health/ready | jq .
```

### 5.2 Smoke test (k6)

```bash
# Run the API smoke scenario (1 VU, all major endpoints)
k6 run --env BASE_URL=${BASE} load-tests/k6/scenarios/02-api-smoke.js
```

All checks should pass. Any failure indicates a broken endpoint.

### 5.3 Key user flows (manual)

1. Log in via Azure AD — confirm JWT is stored and `/auth/me` returns the correct user.
2. Navigate to `/systems` — confirm the list loads without errors.
3. Trigger a crawl agent run on a test system — confirm 202 response and the run appears in the list.
4. Check `/usage/quota` — confirm quota bars render and reflect accurate data.
5. Confirm the onboarding checklist appears for new companies.

### 5.4 Metrics baseline

Within 10 minutes of deploy, confirm in Application Insights:
- `http_req_failed` rate < 1 %
- `http_req_duration p(95)` < 500 ms
- No spike in `exceptions/count`

---

## 6. Rollback procedure

Container Apps preserves the previous active revision. Rollback is instant.

```bash
RG=rg-kaats-prod

# Find the previous revision name
az containerapp revision list \
  -n ca-api-kaats-prod -g ${RG} \
  --query "sort_by([], &properties.createdTime)[-2].name" -o tsv

# Activate it (deactivates the current revision)
PREV_REVISION=$(az containerapp revision list \
  -n ca-api-kaats-prod -g ${RG} \
  --query "sort_by([], &properties.createdTime)[-2].name" -o tsv)

az containerapp revision activate \
  -n ca-api-kaats-prod -g ${RG} \
  --revision ${PREV_REVISION}
```

**Database rollback:** If the migration is not backward-compatible, run
`alembic downgrade -1` before activating the old revision:

```bash
az containerapp exec -n ca-api-kaats-prod -g ${RG} \
  --command "alembic downgrade -1"
```

> **Warning:** Downgrading migrations that drop columns or tables may cause
> irreversible data loss. Always validate the `downgrade()` function in staging
> first.

---

## 7. Infrastructure changes (Bicep)

Use this procedure whenever Bicep templates or parameter files change.

```bash
ENV=prod
RG=rg-kaats-${ENV}

# 1. Validate (dry-run) — no changes applied
az deployment group what-if \
  --resource-group ${RG} \
  --template-file infrastructure/bicep/main.bicep \
  --parameters infrastructure/bicep/parameters/${ENV}.bicepparam

# 2. Review the what-if output carefully — especially deletions and replacements.

# 3. Apply
az deployment group create \
  --resource-group ${RG} \
  --template-file infrastructure/bicep/main.bicep \
  --parameters infrastructure/bicep/parameters/${ENV}.bicepparam \
  --mode Incremental
```

Always use `--mode Incremental` (never `Complete`) to avoid accidentally deleting
resources not managed by the template.

---

## 8. First-time environment setup

For provisioning a brand new environment from scratch.

### 8.1 Create resource group

```bash
az group create --name rg-kaats-${ENV} --location eastus
```

### 8.2 Provision infrastructure

```bash
az deployment group create \
  --resource-group rg-kaats-${ENV} \
  --template-file infrastructure/bicep/main.bicep \
  --parameters infrastructure/bicep/parameters/${ENV}.bicepparam
```

### 8.3 Populate Key Vault secrets

The Bicep deployment creates the Key Vault but does **not** populate secrets
(they contain sensitive values that should never be in source control).

```bash
KV=kv-kaats-${ENV}

az keyvault secret set --vault-name ${KV} --name azure-client-secret --value '<value>'
az keyvault secret set --vault-name ${KV} --name sql-password --value '<value>'
az keyvault secret set --vault-name ${KV} --name acs-connection-string --value '<value>'
az keyvault secret set --vault-name ${KV} --name secret-key --value "$(openssl rand -base64 48)"
```

### 8.4 Build and push initial images

Follow §4.1 using `TAG=latest` for the first deploy.

### 8.5 Run initial migrations

```bash
az containerapp exec -n ca-api-kaats-${ENV} -g rg-kaats-${ENV} \
  --command "alembic upgrade head"
```

### 8.6 Seed dev data (dev/staging only)

The dev auth shortcut (`POST /auth/callback` with `code=dev`) automatically
seeds a dev enterprise, company, and global-admin user on first call. No
manual seeding is required.

### 8.7 Verify

```bash
curl https://api.kaats.kiu.ai/health/ready | jq .
```
