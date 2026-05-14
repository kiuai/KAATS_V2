// ─────────────────────────────────────────────────────────────────────────────
// Azure Service Bus — Standard tier
// Queues: agent-jobs, ai-jobs, crawl-jobs, result-events
// Managed identity gets Azure Service Bus Data Owner role.
// ─────────────────────────────────────────────────────────────────────────────

@description('Azure region')
param location string

@description('Resource suffix (appName-env)')
param suffix string

@description('Managed identity principal ID for role assignments')
param managedIdentityPrincipalId string

@description('Enable private endpoint')
param enablePrivateEndpoint bool

@description('Private endpoint subnet resource ID')
param privateEndpointSubnetId string

@description('Private DNS Zone resource ID for Service Bus')
param privateDnsZoneServiceBusId string

// ─────────────────────────────────────────────────────────────────────────────
// Namespace
// ─────────────────────────────────────────────────────────────────────────────

resource namespace 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' = {
  name: 'sb-${suffix}'
  location: location
  tags: { component: 'service-bus' }
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  properties: {
    minimumTlsVersion: '1.2'
    publicNetworkAccess: enablePrivateEndpoint ? 'Disabled' : 'Enabled'
    disableLocalAuth: false   // set to true after migrating all consumers to MI
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Queues
// agent-jobs: primary intake queue; drives Container Apps scaling
// ai-jobs, crawl-jobs, result-events: internal pipeline queues
// ─────────────────────────────────────────────────────────────────────────────

var queueDefaults = {
  maxSizeInMegabytes: 5120                       // 5 GB
  lockDuration: 'PT5M'                           // 5-minute lock
  maxDeliveryCount: 3
  deadLetteringOnMessageExpiration: true
  enablePartitioning: false
  requiresDuplicateDetection: false
  requiresSession: false
  defaultMessageTimeToLive: 'P14D'               // 14 days
  duplicateDetectionHistoryTimeWindow: 'PT10M'
}

resource queueAgentJobs 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: namespace
  name: 'agent-jobs'
  properties: queueDefaults
}

resource queueAiJobs 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: namespace
  name: 'ai-jobs'
  properties: queueDefaults
}

resource queueCrawlJobs 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: namespace
  name: 'crawl-jobs'
  properties: queueDefaults
}

resource queueResultEvents 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: namespace
  name: 'result-events'
  properties: {
    maxSizeInMegabytes: 1024
    lockDuration: 'PT2M'
    maxDeliveryCount: 5
    deadLetteringOnMessageExpiration: true
    enablePartitioning: false
    requiresDuplicateDetection: false
    requiresSession: false
    defaultMessageTimeToLive: 'P3D'
    duplicateDetectionHistoryTimeWindow: 'PT10M'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Authorization Rule for connection string (used until full MI migration)
// ─────────────────────────────────────────────────────────────────────────────

resource authRule 'Microsoft.ServiceBus/namespaces/authorizationRules@2022-10-01-preview' = {
  parent: namespace
  name: 'kaats-app'
  properties: {
    rights: ['Listen', 'Send', 'Manage']
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Role: Azure Service Bus Data Owner → managed identity
// ─────────────────────────────────────────────────────────────────────────────

var serviceBusDataOwnerId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '090c5cfd-751d-490a-894a-3ce6f1109419'
)

resource roleSbDataOwner 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(namespace.id, managedIdentityPrincipalId, serviceBusDataOwnerId)
  scope: namespace
  properties: {
    roleDefinitionId: serviceBusDataOwnerId
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Private Endpoint  (prod only)
// ─────────────────────────────────────────────────────────────────────────────

resource privateEndpoint 'Microsoft.Network/privateEndpoints@2023-11-01' = if (enablePrivateEndpoint) {
  name: 'pe-sb-${suffix}'
  location: location
  properties: {
    subnet: { id: privateEndpointSubnetId }
    privateLinkServiceConnections: [
      {
        name: 'plsc-sb-${suffix}'
        properties: {
          privateLinkServiceId: namespace.id
          groupIds: ['namespace']
        }
      }
    ]
  }
}

resource dnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-11-01' = if (enablePrivateEndpoint) {
  parent: privateEndpoint
  name: 'dns-group-sb'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'privatelink-servicebus-windows-net'
        properties: { privateDnsZoneId: privateDnsZoneServiceBusId }
      }
    ]
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Outputs
// ─────────────────────────────────────────────────────────────────────────────

output namespaceId string = namespace.id
output namespaceName string = namespace.name
output namespaceFqdn string = '${namespace.name}.servicebus.windows.net'
output agentJobsQueueName string = queueAgentJobs.name
output connectionString string = authRule.listKeys().primaryConnectionString
