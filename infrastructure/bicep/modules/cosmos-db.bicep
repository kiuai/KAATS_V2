// ─────────────────────────────────────────────────────────────────────────────
// Cosmos DB — Core (SQL) API
// Containers: agent_run_logs, evidence_metadata, audit_log (TTL 365d),
//             ai_generation_log (TTL 90d)
// All partition key: /company_id
// Serverless (dev/staging) | Autoscale 400–N RU (prod)
// ─────────────────────────────────────────────────────────────────────────────

@description('Azure region')
param location string

@description('Resource suffix (appName-env)')
param suffix string

@description('Cosmos DB database name')
param databaseName string

@description('Capacity mode: Serverless | Autoscale')
@allowed(['Serverless', 'Autoscale'])
param capacityMode string

@description('Max RUs for autoscale (ignored for Serverless)')
param maxThroughput int

@description('Managed identity principal ID for role assignments')
param managedIdentityPrincipalId string

@description('Enable private endpoint')
param enablePrivateEndpoint bool

@description('Private endpoint subnet resource ID')
param privateEndpointSubnetId string

@description('Private DNS Zone resource ID for Cosmos DB')
param privateDnsZoneCosmosId string

// ─────────────────────────────────────────────────────────────────────────────
// Account
// ─────────────────────────────────────────────────────────────────────────────

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2023-11-15' = {
  name: 'cosmos-${suffix}'
  location: location
  kind: 'GlobalDocumentDB'
  tags: { component: 'cosmos-db' }
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    capabilities: capacityMode == 'Serverless' ? [{ name: 'EnableServerless' }] : []
    backupPolicy: {
      type: 'Continuous'
      continuousModeProperties: {
        tier: 'Continuous7Days'
      }
    }
    publicNetworkAccess: enablePrivateEndpoint ? 'Disabled' : 'Enabled'
    enableAutomaticFailover: false
    enableMultipleWriteLocations: false
    disableLocalAuth: false
    minimalTlsVersion: 'Tls12'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Database
// ─────────────────────────────────────────────────────────────────────────────

resource db 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-11-15' = {
  parent: cosmos
  name: databaseName
  properties: {
    resource: { id: databaseName }
    // Database-level throughput only relevant for Dedicated mode.
    // Serverless: no throughput setting needed. Autoscale: set per container.
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Containers
// ─────────────────────────────────────────────────────────────────────────────

var autoscaleSettings = capacityMode == 'Autoscale' ? {
  autoscaleSettings: { maxThroughput: maxThroughput }
} : {}

// agent_run_logs — no TTL (retained indefinitely, archived to blob)
resource containerAgentRunLogs 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-11-15' = {
  parent: db
  name: 'agent_run_logs'
  properties: {
    resource: {
      id: 'agent_run_logs'
      partitionKey: {
        paths: ['/company_id']
        kind: 'Hash'
        version: 2
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        includedPaths: [{ path: '/*' }]
        excludedPaths: [{ path: '/steps/*' }]  // large nested array — exclude from index
      }
    }
    options: autoscaleSettings
  }
}

// evidence_metadata — no TTL
resource containerEvidenceMetadata 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-11-15' = {
  parent: db
  name: 'evidence_metadata'
  properties: {
    resource: {
      id: 'evidence_metadata'
      partitionKey: {
        paths: ['/company_id']
        kind: 'Hash'
        version: 2
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        includedPaths: [{ path: '/*' }]
      }
    }
    options: autoscaleSettings
  }
}

// audit_log — TTL 365 days
resource containerAuditLog 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-11-15' = {
  parent: db
  name: 'audit_log'
  properties: {
    resource: {
      id: 'audit_log'
      partitionKey: {
        paths: ['/company_id']
        kind: 'Hash'
        version: 2
      }
      defaultTtl: 31536000   // 365 days in seconds
      indexingPolicy: {
        indexingMode: 'consistent'
        includedPaths: [{ path: '/*' }]
      }
    }
    options: autoscaleSettings
  }
}

// ai_generation_log — TTL 90 days
resource containerAiGenerationLog 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-11-15' = {
  parent: db
  name: 'ai_generation_log'
  properties: {
    resource: {
      id: 'ai_generation_log'
      partitionKey: {
        paths: ['/company_id']
        kind: 'Hash'
        version: 2
      }
      defaultTtl: 7776000    // 90 days in seconds
      indexingPolicy: {
        indexingMode: 'consistent'
        includedPaths: [{ path: '/*' }]
        excludedPaths: [{ path: '/prompt_text/*' }]
      }
    }
    options: autoscaleSettings
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Role: Cosmos DB Built-in Data Contributor → managed identity
// This is a Cosmos-specific data-plane RBAC role (not ARM RBAC)
// ─────────────────────────────────────────────────────────────────────────────

resource cosmosRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2023-11-15' = {
  parent: cosmos
  name: guid(cosmos.id, managedIdentityPrincipalId, '00000000-0000-0000-0000-000000000002')
  properties: {
    roleDefinitionId: '${cosmos.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    principalId: managedIdentityPrincipalId
    scope: cosmos.id
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Private Endpoint  (prod only)
// ─────────────────────────────────────────────────────────────────────────────

resource privateEndpoint 'Microsoft.Network/privateEndpoints@2023-11-01' = if (enablePrivateEndpoint) {
  name: 'pe-cosmos-${suffix}'
  location: location
  properties: {
    subnet: { id: privateEndpointSubnetId }
    privateLinkServiceConnections: [
      {
        name: 'plsc-cosmos-${suffix}'
        properties: {
          privateLinkServiceId: cosmos.id
          groupIds: ['Sql']
        }
      }
    ]
  }
}

resource dnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-11-01' = if (enablePrivateEndpoint) {
  parent: privateEndpoint
  name: 'dns-group-cosmos'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'privatelink-documents-azure-com'
        properties: { privateDnsZoneId: privateDnsZoneCosmosId }
      }
    ]
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Outputs
// ─────────────────────────────────────────────────────────────────────────────

output endpoint string = cosmos.properties.documentEndpoint
output accountName string = cosmos.name
output primaryKey string = cosmos.listKeys().primaryMasterKey
