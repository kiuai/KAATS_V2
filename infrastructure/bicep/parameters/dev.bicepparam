// ─────────────────────────────────────────────────────────────────────────────
// Dev environment parameters
// Optimised for cost: serverless SQL (auto-pause 1h), Serverless Cosmos,
// LRS storage, no private networking, Standard Key Vault.
// ─────────────────────────────────────────────────────────────────────────────

using '../main.bicep'

param environment = 'dev'
param location = 'eastus'
param resourceGroupName = 'rg-kaats-dev'
param appName = 'kaats'

// Azure AD — replace with your actual values
param azureTenantId = '<your-tenant-id>'
param azureClientId = '<your-client-id>'
param sqlEntraAdminObjectId = '<your-entra-admin-object-id>'
param sqlEntraAdminLogin = 'svc-kaats-dev@yourdomain.com'

// Azure OpenAI
param azureOpenAiEndpoint = 'https://aoai-kaats-dev.openai.azure.com/'
param azureOpenAiDeploymentName = 'gpt-4o'
param azureOpenAiModelName = 'gpt-4o'

// Application
param sqlDatabaseName = 'kaats_dev'
param cosmosDatabaseName = 'kaats'
param allowedOrigins = 'http://localhost:5173,https://ca-frontend-kaats-dev.azurecontainerapps.io'
param imageTag = 'latest'

// Communication Services
param acsSenderAddress = 'noreply@dev.kaats.kiu.ai'
param frontendBaseUrl = 'http://localhost:5173'

// Infrastructure toggles
param enablePrivateNetworking = false
param storageSkuName = 'Standard_LRS'
param keyVaultSku = 'standard'
param cosmosCapacityMode = 'Serverless'
param cosmosMaxThroughput = 1000      // ignored for Serverless
param sqlDisableSqlAuth = false       // allow password auth in dev
param sqlGeoRedundantBackup = false
param sqlBackupRetentionDays = 7
param keyVaultPurgeProtection = false
param alwaysOn = false                // scale to zero overnight — saves cost
