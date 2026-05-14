// ─────────────────────────────────────────────────────────────────────────────
// Container Apps Jobs — agent-runner
// Event-triggered job: fires when a message lands in the "agent-jobs" Service
// Bus queue. Burst-scales agents beyond the always-on worker pool.
// Image is the same worker image (shares the KAATS worker code path).
// ─────────────────────────────────────────────────────────────────────────────

@description('Azure region')
param location string

@description('Resource suffix (appName-env)')
param suffix string

@description('Container Apps Environment resource ID')
param containerAppsEnvironmentId string

@description('User-Assigned Managed Identity resource ID')
param managedIdentityId string

@description('ACR login server')
param acrLoginServer string

@description('Container image tag')
param imageTag string

@description('Key Vault URI')
param keyVaultUri string

// ── Connection details ────────────────────────────────────────────────────────
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
param serviceBusNamespaceFqdn string
param serviceBusQueueName string
param environment string

// ─────────────────────────────────────────────────────────────────────────────
// Secrets (Key Vault refs)
// ─────────────────────────────────────────────────────────────────────────────

var kvSecrets = [
  { name: 'secret-key',                          kvPath: 'secrets/secret-key' }
  { name: 'azure-client-secret',                 kvPath: 'secrets/azure-client-secret' }
  { name: 'azure-openai-api-key',                kvPath: 'secrets/azure-openai-api-key' }
  { name: 'azure-cosmos-key',                    kvPath: 'secrets/azure-cosmos-key' }
  { name: 'azure-service-bus-connection-string', kvPath: 'secrets/azure-service-bus-connection-string' }
  { name: 'azure-storage-account-key',           kvPath: 'secrets/azure-storage-account-key' }
  { name: 'azure-sql-password',                  kvPath: 'secrets/azure-sql-password' }
]

var secretsArray = [for s in kvSecrets: {
  name: s.name
  keyVaultUrl: '${keyVaultUri}${s.kvPath}'
  identity: managedIdentityId
}]

// ─────────────────────────────────────────────────────────────────────────────
// Environment variables
// ─────────────────────────────────────────────────────────────────────────────

var jobEnv = [
  { name: 'ENVIRONMENT',                         value: environment }
  { name: 'AZURE_TENANT_ID',                     value: azureTenantId }
  { name: 'AZURE_CLIENT_ID',                     value: azureClientId }
  { name: 'AZURE_OPENAI_ENDPOINT',               value: azureOpenAiEndpoint }
  { name: 'AZURE_OPENAI_DEPLOYMENT_NAME',        value: azureOpenAiDeploymentName }
  { name: 'AZURE_SQL_SERVER',                    value: sqlServerFqdn }
  { name: 'AZURE_SQL_DATABASE',                  value: sqlDatabaseName }
  { name: 'AZURE_SQL_USERNAME',                  value: sqlAdminLogin }
  { name: 'AZURE_COSMOS_ENDPOINT',               value: cosmosEndpoint }
  { name: 'AZURE_COSMOS_DATABASE',               value: cosmosDatabaseName }
  { name: 'AZURE_STORAGE_ACCOUNT_NAME',          value: storageAccountName }
  { name: 'AZURE_STORAGE_CONTAINER_EVIDENCE',    value: 'evidence' }
  { name: 'AZURE_KEY_VAULT_URL',                 value: keyVaultUri }
  { name: 'PLAYWRIGHT_BROWSERS_PATH',            value: '/ms-playwright' }
  { name: 'MAX_CONCURRENT_AGENTS',               value: '1' }   // 1 per job instance
  // Secrets
  { name: 'SECRET_KEY',                          secretRef: 'secret-key' }
  { name: 'AZURE_CLIENT_SECRET',                 secretRef: 'azure-client-secret' }
  { name: 'AZURE_OPENAI_API_KEY',                secretRef: 'azure-openai-api-key' }
  { name: 'AZURE_COSMOS_KEY',                    secretRef: 'azure-cosmos-key' }
  { name: 'AZURE_SERVICE_BUS_CONNECTION_STRING', secretRef: 'azure-service-bus-connection-string' }
  { name: 'AZURE_STORAGE_ACCOUNT_KEY',           secretRef: 'azure-storage-account-key' }
  { name: 'AZURE_SQL_PASSWORD',                  secretRef: 'azure-sql-password' }
]

// ─────────────────────────────────────────────────────────────────────────────
// Container Apps Job — Event trigger (Service Bus)
// ─────────────────────────────────────────────────────────────────────────────

resource agentRunnerJob 'Microsoft.App/jobs@2024-03-01' = {
  name: 'job-agent-runner-${suffix}'
  location: location
  tags: { component: 'agent-runner-job', tier: 'backend' }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityId}': {}
    }
  }
  properties: {
    environmentId: containerAppsEnvironmentId
    configuration: {
      triggerType: 'Event'
      replicaTimeout: 3600          // 1 hour max per agent run
      replicaRetryLimit: 1
      eventTriggerConfig: {
        replicaCompletionCount: 1
        parallelism: 1
        scale: {
          minExecutions: 0
          maxExecutions: 20          // burst up to 20 parallel agent executions
          pollingInterval: 30
          rules: [
            {
              name: 'sb-agent-jobs'
              type: 'azure-servicebus'
              auth: [
                {
                  secretRef: 'azure-service-bus-connection-string'
                  triggerParameter: 'connection'
                }
              ]
              metadata: {
                queueName: serviceBusQueueName
                namespace: split(serviceBusNamespaceFqdn, '.')[0]
                messageCount: '1'       // trigger per message
              }
            }
          ]
        }
      }
      registries: [
        {
          server: acrLoginServer
          identity: managedIdentityId
        }
      ]
      secrets: secretsArray
    }
    template: {
      containers: [
        {
          name: 'agent-runner'
          image: '${acrLoginServer}/kaats/worker:${imageTag}'
          resources: {
            cpu: json('2.0')
            memory: '4Gi'
          }
          env: jobEnv
        }
      ]
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Outputs
// ─────────────────────────────────────────────────────────────────────────────

output jobName string = agentRunnerJob.name
output jobId string = agentRunnerJob.id
