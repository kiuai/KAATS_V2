// ─────────────────────────────────────────────────────────────────────────────
// Azure OpenAI
// Deploys a Cognitive Services account of kind "OpenAI" and a model deployment.
// NOTE: OpenAI quota is region-specific; eastus and eastus2 have the most
// capacity for gpt-4o. Change location param if deploying to another region.
// ─────────────────────────────────────────────────────────────────────────────

@description('Azure region — must have OpenAI capacity for the requested model')
param location string

@description('Resource suffix (appName-env)')
param suffix string

@description('Name of the model deployment (used as AZURE_OPENAI_DEPLOYMENT_NAME)')
param deploymentName string

@description('Model identifier, e.g. gpt-4o')
param modelName string

@description('Managed identity principal ID for Cognitive Services User role')
param managedIdentityPrincipalId string

// ─────────────────────────────────────────────────────────────────────────────
// Cognitive Services Account (OpenAI kind)
// ─────────────────────────────────────────────────────────────────────────────

resource openAi 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: 'aoai-${suffix}'
  location: location
  kind: 'OpenAI'
  tags: { component: 'openai' }
  sku: {
    name: 'S0'
  }
  properties: {
    publicNetworkAccess: 'Enabled'
    customSubDomainName: 'aoai-${suffix}'
    networkAcls: {
      defaultAction: 'Allow'
    }
    disableLocalAuth: false
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Model Deployment
// ─────────────────────────────────────────────────────────────────────────────

resource deployment 'Microsoft.CognitiveServices/accounts/deployments@2023-05-01' = {
  parent: openAi
  name: deploymentName
  sku: {
    name: 'Standard'
    capacity: 30      // 30K TPM — adjust to your quota
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: '2024-05-13'    // latest stable gpt-4o as of Aug 2025
    }
    versionUpgradeOption: 'OnceCurrentVersionExpired'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Role: Cognitive Services OpenAI User → managed identity
// Allows the app to call the OpenAI endpoint with managed identity auth
// (in addition to API key, which is stored in Key Vault as fallback)
// ─────────────────────────────────────────────────────────────────────────────

var cognitiveServicesOpenAiUserId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
)

resource roleCognitiveUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAi.id, managedIdentityPrincipalId, cognitiveServicesOpenAiUserId)
  scope: openAi
  properties: {
    roleDefinitionId: cognitiveServicesOpenAiUserId
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Outputs
// ─────────────────────────────────────────────────────────────────────────────

output endpoint string = openAi.properties.endpoint
output accountName string = openAi.name
output primaryKey string = openAi.listKeys().key1
output deploymentName string = deployment.name
