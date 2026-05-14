// ─────────────────────────────────────────────────────────────────────────────
// Container Apps — api, worker, scheduler, frontend
// All apps share one User-Assigned Managed Identity and pull secrets from
// Key Vault via secretRef bindings.
// ─────────────────────────────────────────────────────────────────────────────

@description('Azure region')
param location string

@description('Resource suffix (appName-env)')
param suffix string

@description('Container Apps Environment resource ID')
param containerAppsEnvironmentId string

@description('User-Assigned Managed Identity resource ID')
param managedIdentityId string

@description('ACR login server (e.g. acrkaatsprod.azurecr.io)')
param acrLoginServer string

@description('Container image tag')
param imageTag string

@description('Key Vault URI (https://kv-*.vault.azure.net/)')
param keyVaultUri string

// ── Connection details (non-secret) ──────────────────────────────────────────
param azureTenantId string
param azureClientId string
param azureOpenAiEndpoint string
param azureOpenAiDeploymentName string
param sqlServerFqdn string
param sqlDatabaseName string
param sqlAdminLogin string
param cosmosEndpoint string
param cosmosDatabaseName string
param storageAccountName string
param allowedOrigins string
param appInsightsConnectionString string
param serviceBusNamespaceFqdn string

@description('Environment label')
param environment string

@description('Enable always-on min replicas')
param alwaysOn bool

// ─────────────────────────────────────────────────────────────────────────────
// Shared secret bindings  (Key Vault references via managed identity)
// secret `name` becomes the secretRef value used in env arrays
// ─────────────────────────────────────────────────────────────────────────────

var kvSecrets = [
  { name: 'secret-key',                        kvPath: 'secrets/secret-key' }
  { name: 'azure-client-secret',               kvPath: 'secrets/azure-client-secret' }
  { name: 'azure-openai-api-key',              kvPath: 'secrets/azure-openai-api-key' }
  { name: 'azure-cosmos-key',                  kvPath: 'secrets/azure-cosmos-key' }
  { name: 'azure-service-bus-connection-string', kvPath: 'secrets/azure-service-bus-connection-string' }
  { name: 'azure-storage-account-key',         kvPath: 'secrets/azure-storage-account-key' }
  { name: 'azure-sql-password',                kvPath: 'secrets/azure-sql-password' }
]

var secretsArray = [for s in kvSecrets: {
  name: s.name
  keyVaultUrl: '${keyVaultUri}${s.kvPath}'
  identity: managedIdentityId
}]

// ─────────────────────────────────────────────────────────────────────────────
// Shared environment variables (non-secret)
// ─────────────────────────────────────────────────────────────────────────────

var commonEnv = [
  { name: 'ENVIRONMENT',                     value: environment }
  { name: 'AZURE_TENANT_ID',                 value: azureTenantId }
  { name: 'AZURE_CLIENT_ID',                 value: azureClientId }
  { name: 'AZURE_OPENAI_ENDPOINT',           value: azureOpenAiEndpoint }
  { name: 'AZURE_OPENAI_DEPLOYMENT_NAME',    value: azureOpenAiDeploymentName }
  { name: 'AZURE_SQL_SERVER',                value: sqlServerFqdn }
  { name: 'AZURE_SQL_DATABASE',              value: sqlDatabaseName }
  { name: 'AZURE_SQL_USERNAME',              value: sqlAdminLogin }
  { name: 'AZURE_COSMOS_ENDPOINT',           value: cosmosEndpoint }
  { name: 'AZURE_COSMOS_DATABASE',           value: cosmosDatabaseName }
  { name: 'AZURE_STORAGE_ACCOUNT_NAME',      value: storageAccountName }
  { name: 'AZURE_STORAGE_CONTAINER_EVIDENCE', value: 'evidence' }
  { name: 'AZURE_KEY_VAULT_URL',             value: keyVaultUri }
  { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
  { name: 'LOG_LEVEL',                       value: environment == 'prod' ? 'WARNING' : 'INFO' }
  { name: 'OPENAPI_ENABLED',                 value: environment == 'prod' ? 'false' : 'true' }
  // OpenTelemetry service name is set per-container below using concat()
]

var commonEnvWithSecrets = concat(commonEnv, [
  { name: 'SECRET_KEY',                        secretRef: 'secret-key' }
  { name: 'AZURE_CLIENT_SECRET',               secretRef: 'azure-client-secret' }
  { name: 'AZURE_OPENAI_API_KEY',              secretRef: 'azure-openai-api-key' }
  { name: 'AZURE_COSMOS_KEY',                  secretRef: 'azure-cosmos-key' }
  { name: 'AZURE_SERVICE_BUS_CONNECTION_STRING', secretRef: 'azure-service-bus-connection-string' }
  { name: 'AZURE_STORAGE_ACCOUNT_KEY',         secretRef: 'azure-storage-account-key' }
  { name: 'AZURE_SQL_PASSWORD',                secretRef: 'azure-sql-password' }
])

// ─────────────────────────────────────────────────────────────────────────────
// API Container App  (external ingress, port 8000)
// ─────────────────────────────────────────────────────────────────────────────

resource api 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-api-${suffix}'
  location: location
  tags: { component: 'api', tier: 'backend' }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityId}': {}
    }
  }
  properties: {
    environmentId: containerAppsEnvironmentId
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
        corsPolicy: {
          allowedOrigins: split(allowedOrigins, ',')
          allowedMethods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS']
          allowedHeaders: ['*']
          allowCredentials: true
        }
      }
      registries: [
        {
          server: acrLoginServer
          identity: managedIdentityId
        }
      ]
      secrets: secretsArray
      activeRevisionsMode: 'Single'
    }
    template: {
      containers: [
        {
          name: 'api'
          image: '${acrLoginServer}/kaats/api:${imageTag}'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: concat(commonEnvWithSecrets, [
            { name: 'ALLOWED_ORIGINS',    value: allowedOrigins }
            { name: 'OTEL_SERVICE_NAME',  value: 'kaats-api' }
          ])
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health/live'
                port: 8000
                scheme: 'HTTP'
              }
              initialDelaySeconds: 15
              periodSeconds: 30
              failureThreshold: 3
              successThreshold: 1
              timeoutSeconds: 5
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health/ready'
                port: 8000
                scheme: 'HTTP'
              }
              initialDelaySeconds: 10
              periodSeconds: 15
              failureThreshold: 3
              successThreshold: 1
              timeoutSeconds: 5
            }
          ]
        }
      ]
      scale: {
        minReplicas: alwaysOn ? 1 : 0
        maxReplicas: 10
        rules: [
          {
            name: 'http-concurrency'
            http: {
              metadata: {
                concurrentRequests: '50'
              }
            }
          }
        ]
      }
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Worker Container App  (no ingress, scales on Service Bus queue depth)
// ─────────────────────────────────────────────────────────────────────────────

resource worker 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-worker-${suffix}'
  location: location
  tags: { component: 'worker', tier: 'backend' }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityId}': {}
    }
  }
  properties: {
    environmentId: containerAppsEnvironmentId
    configuration: {
      // No ingress — internal only
      registries: [
        {
          server: acrLoginServer
          identity: managedIdentityId
        }
      ]
      secrets: secretsArray
      activeRevisionsMode: 'Single'
    }
    template: {
      containers: [
        {
          name: 'worker'
          image: '${acrLoginServer}/kaats/worker:${imageTag}'
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          env: concat(commonEnvWithSecrets, [
            { name: 'PLAYWRIGHT_BROWSERS_PATH', value: '/ms-playwright' }
            { name: 'MAX_CONCURRENT_AGENTS',    value: '3' }
            { name: 'OTEL_SERVICE_NAME',         value: 'kaats-worker' }
          ])
        }
      ]
      scale: {
        minReplicas: alwaysOn ? 1 : 0
        maxReplicas: 5
        rules: [
          {
            name: 'sb-queue-length'
            custom: {
              type: 'azure-servicebus'
              auth: [
                {
                  secretRef: 'azure-service-bus-connection-string'
                  triggerParameter: 'connection'
                }
              ]
              metadata: {
                queueName: 'agent-jobs'
                namespace: '${split(serviceBusNamespaceFqdn, '.')[0]}'
                messageCount: '3'
              }
            }
          }
        ]
      }
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Scheduler Container App  (no ingress, singleton — exactly 1 replica)
// ─────────────────────────────────────────────────────────────────────────────

resource scheduler 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-scheduler-${suffix}'
  location: location
  tags: { component: 'scheduler', tier: 'backend' }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityId}': {}
    }
  }
  properties: {
    environmentId: containerAppsEnvironmentId
    configuration: {
      registries: [
        {
          server: acrLoginServer
          identity: managedIdentityId
        }
      ]
      secrets: secretsArray
      activeRevisionsMode: 'Single'
    }
    template: {
      containers: [
        {
          name: 'scheduler'
          image: '${acrLoginServer}/kaats/scheduler:${imageTag}'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: concat(commonEnvWithSecrets, [
            { name: 'SCHEDULER_INTERVAL_SECONDS', value: '60' }
            { name: 'OTEL_SERVICE_NAME',           value: 'kaats-scheduler' }
          ])
        }
      ]
      scale: {
        minReplicas: 1      // always exactly 1 — singleton evaluator
        maxReplicas: 1
      }
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Frontend Container App  (external ingress, port 80, nginx)
// ─────────────────────────────────────────────────────────────────────────────

resource frontend 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-frontend-${suffix}'
  location: location
  tags: { component: 'frontend', tier: 'frontend' }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityId}': {}
    }
  }
  properties: {
    environmentId: containerAppsEnvironmentId
    configuration: {
      ingress: {
        external: true
        targetPort: 80
        transport: 'http'
      }
      registries: [
        {
          server: acrLoginServer
          identity: managedIdentityId
        }
      ]
      activeRevisionsMode: 'Single'
    }
    template: {
      containers: [
        {
          name: 'frontend'
          image: '${acrLoginServer}/kaats/frontend:${imageTag}'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            { name: 'VITE_API_URL', value: 'https://${api.properties.configuration.ingress.fqdn}' }
          ]
        }
      ]
      scale: {
        minReplicas: alwaysOn ? 1 : 0
        maxReplicas: 5
        rules: [
          {
            name: 'http-concurrency'
            http: {
              metadata: {
                concurrentRequests: '100'
              }
            }
          }
        ]
      }
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Outputs
// ─────────────────────────────────────────────────────────────────────────────

output apiUrl string = 'https://${api.properties.configuration.ingress.fqdn}'
output frontendUrl string = 'https://${frontend.properties.configuration.ingress.fqdn}'
output apiName string = api.name
output workerName string = worker.name
output schedulerName string = scheduler.name
output frontendName string = frontend.name
