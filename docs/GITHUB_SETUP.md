# KAATS — GitHub Actions Setup Guide

This document covers every manual setup step required before the CI/CD
workflows will run successfully.

---

## 1. Required GitHub Secrets

Add these secrets at **Settings → Secrets and variables → Actions → Secrets** for
the repository (or at the org level for multi-repo use).

| Secret name | Value | Notes |
|---|---|---|
| `AZURE_CLIENT_ID` | App registration Client ID | From step 3 |
| `AZURE_TENANT_ID` | Your Entra Directory (tenant) ID | Azure Portal → Entra ID → Overview |
| `AZURE_SUBSCRIPTION_ID` | Azure Subscription ID | `az account show --query id` |
| `ACR_LOGIN_SERVER` | `acrkaatsprod.azurecr.io` | Output of Bicep `acrLoginServer` |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook URL | See section 6 |
| `CODECOV_TOKEN` | Codecov upload token | Optional — coverage reports |

> **Note:** Do not store `AZURE_CLIENT_SECRET` as a GitHub secret.
> The workflows use **OIDC federated credentials** — no secret is needed.

---

## 2. Azure OIDC Federated Credential Setup

OIDC lets GitHub Actions authenticate to Azure without storing any credentials.
Run these commands once per environment (dev, staging, prod).

### 2a. Create an App Registration (if you don't have one)

```bash
# Create the app registration
az ad app create --display-name "kaats-github-actions"

# Note the appId (CLIENT_ID) from the output
APP_ID=$(az ad app list --display-name "kaats-github-actions" --query "[0].appId" -o tsv)

# Create a service principal for the app
az ad sp create --id "${APP_ID}"
SP_OBJECT_ID=$(az ad sp show --id "${APP_ID}" --query "id" -o tsv)
```

### 2b. Add Federated Credentials

Add one credential per trigger type. Replace `<org>/<repo>` with your GitHub
repository name (e.g. `kiuai/KAATS_V2`).

```bash
REPO="kiuai/KAATS_V2"

# For push to main branch (build.yml, deploy-staging.yml)
az ad app federated-credential create \
  --id "${APP_ID}" \
  --parameters '{
    "name": "github-actions-main",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:'"${REPO}"':ref:refs/heads/main",
    "audiences": ["api://AzureADTokenExchange"]
  }'

# For production tags (deploy-production.yml)
az ad app federated-credential create \
  --id "${APP_ID}" \
  --parameters '{
    "name": "github-actions-tags",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:'"${REPO}"':ref:refs/tags/*",
    "audiences": ["api://AzureADTokenExchange"]
  }'

# For production environment (deploy-production.yml with manual trigger)
az ad app federated-credential create \
  --id "${APP_ID}" \
  --parameters '{
    "name": "github-actions-production-env",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:'"${REPO}"':environment:production",
    "audiences": ["api://AzureADTokenExchange"]
  }'

# For staging environment
az ad app federated-credential create \
  --id "${APP_ID}" \
  --parameters '{
    "name": "github-actions-staging-env",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:'"${REPO}"':environment:staging",
    "audiences": ["api://AzureADTokenExchange"]
  }'

# For pull requests (pr-preview.yml)
az ad app federated-credential create \
  --id "${APP_ID}" \
  --parameters '{
    "name": "github-actions-pull-requests",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:'"${REPO}"':pull_request",
    "audiences": ["api://AzureADTokenExchange"]
  }'
```

### 2c. Assign Azure RBAC Roles

The app registration's service principal needs the following roles to manage
Container Apps and ACR:

```bash
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

# Contributor on each resource group (allows manage Container Apps)
for RG in rg-kaats-dev rg-kaats-staging rg-kaats-prod; do
  az role assignment create \
    --assignee "${SP_OBJECT_ID}" \
    --role "Contributor" \
    --scope "/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RG}"
done

# AcrPush — push images from CI pipeline
ACR_ID=$(az acr show --name acrkaatsprod --query id -o tsv)
az role assignment create \
  --assignee "${SP_OBJECT_ID}" \
  --role "AcrPush" \
  --scope "${ACR_ID}"
```

### 2d. Store the Client ID in GitHub Secrets

```bash
echo "Add this to GitHub Secrets as AZURE_CLIENT_ID:"
echo "${APP_ID}"
```

---

## 3. GitHub Environments

Navigate to **Settings → Environments** and create:

### `staging`

| Setting | Value |
|---|---|
| **Deployment protection rules** | None (auto-deploy) |
| **Environment secrets** | None needed (use repo secrets) |
| **Wait timer** | 0 |

### `production`

| Setting | Value |
|---|---|
| **Deployment protection rules** | ✅ Required reviewers: add 2+ members of `production-approvers` team |
| **Wait timer** | 0 |
| **Deployment branches** | `main` only, and tags matching `v*.*.*` |

> After setting up the environment, create a team named `production-approvers` in your
> GitHub org and add the appropriate people. At least **2 reviews** are required before
> a production deployment proceeds.

---

## 4. Branch Protection on `main`

Navigate to **Settings → Branches → Add rule** and configure:

| Setting | Value |
|---|---|
| Branch name pattern | `main` |
| ✅ Require a pull request before merging | Yes |
| → Required approvals | 1 |
| ✅ Require status checks to pass | Yes |
| → Required checks | `backend-quality`, `backend-test`, `frontend-quality`, `security`, `migration-check` |
| ✅ Require branches to be up to date | Yes |
| ✅ Do not allow bypassing the above settings | Yes |
| ❌ Allow force pushes | **No** |
| ❌ Allow deletions | No |

---

## 5. Repository Labels

Create these labels (used by `database-migration-check.yml`):

```bash
gh label create "migration:destructive" \
  --color "d93f0b" \
  --description "Acknowledges that this PR contains destructive DB migrations"

gh label create "security" \
  --color "e11d48" \
  --description "Security-related issue or PR"

gh label create "automated" \
  --color "0075ca" \
  --description "Created by an automated workflow"

gh label create "production-incident" \
  --color "b60205" \
  --description "Production deployment incident"

gh label create "deployment" \
  --color "0052cc" \
  --description "Deployment-related issue"
```

---

## 6. Slack Webhook

1. Go to your Slack workspace → **Apps → Incoming Webhooks → Add to Slack**
2. Choose the channel (e.g. `#kaats-deployments`)
3. Copy the webhook URL
4. Add it to GitHub Secrets as `SLACK_WEBHOOK_URL`

The webhook is used by `deploy-staging.yml`, `deploy-production.yml`, and
`security-audit.yml`.

---

## 7. Codecov (Optional)

For the coverage upload in `ci.yml`:

1. Sign in to [codecov.io](https://codecov.io) with GitHub
2. Add the KAATS repository
3. Copy the upload token
4. Add it to GitHub Secrets as `CODECOV_TOKEN`

If `CODECOV_TOKEN` is not set, the upload step uses `fail_ci_if_error: false`
and CI will still pass.

---

## 8. Cosign — Keyless Image Signing

No setup required. The `build.yml` workflow uses **keyless signing** via
Sigstore's Fulcio CA. The signing identity is the GitHub Actions OIDC token,
so no private key needs to be stored.

Verify a signed image:
```bash
cosign verify \
  --certificate-identity-regexp "https://github.com/kiuai/KAATS_V2/.*" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  acrkaatsprod.azurecr.io/kaats/api:abc1234
```

---

## 9. First-Time Deployment Checklist

Run these steps in order for a fresh environment:

```bash
# 1. Deploy infrastructure
cd infrastructure/bicep/scripts
./deploy.sh dev latest

# 2. Trigger the full pipeline by pushing to main
git push origin main

# 3. Monitor workflow runs
gh run watch

# 4. Verify staging deployment
curl https://ca-api-kaats-staging.azurecontainerapps.io/health/live

# 5. Promote to production by tagging
git tag v1.0.0 && git push origin v1.0.0
# → approve the workflow in GitHub UI → production deployment proceeds
```

---

## 10. Troubleshooting

### OIDC authentication fails

```
Error: AADSTS70021: No matching federated identity record found
```

Ensure the federated credential `subject` exactly matches the GitHub Actions
context. For a push to main, the subject must be `repo:<org>/<repo>:ref:refs/heads/main`.
For an environment, it must be `repo:<org>/<repo>:environment:<env-name>`.

### Container App revision not found

If `az containerapp revision list` returns empty, the revision may still be
provisioning. The `run-migrations.sh` script retries for up to 2 minutes.

### ACR login fails in build.yml

Ensure the service principal has `AcrPush` role on the ACR resource (not just
the resource group). A `Contributor` role on the RG alone is not enough for
the `az acr login` command.
