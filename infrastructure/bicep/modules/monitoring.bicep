// ─────────────────────────────────────────────────────────────────────────────
// Monitoring — Log Analytics Workspace + Application Insights
// ─────────────────────────────────────────────────────────────────────────────

@description('Azure region')
param location string

@description('Resource suffix (appName-env)')
param suffix string

@description('Managed identity principal ID for role assignments')
param managedIdentityPrincipalId string

// ─────────────────────────────────────────────────────────────────────────────
// Log Analytics Workspace
// ─────────────────────────────────────────────────────────────────────────────

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: 'log-${suffix}'
  location: location
  tags: { component: 'monitoring' }
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Application Insights
// ─────────────────────────────────────────────────────────────────────────────

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${suffix}'
  location: location
  kind: 'web'
  tags: { component: 'monitoring' }
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
    IngestionMode: 'LogAnalytics'
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
    RetentionInDays: 30
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Role: Log Analytics Contributor for the managed identity
// ─────────────────────────────────────────────────────────────────────────────

var logAnalyticsContributorId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '92aaf0da-9dab-42b6-94a3-d43ce8d16293'
)

resource roleLogAnalytics 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(logAnalytics.id, managedIdentityPrincipalId, logAnalyticsContributorId)
  scope: logAnalytics
  properties: {
    roleDefinitionId: logAnalyticsContributorId
    principalId: managedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Outputs
// ─────────────────────────────────────────────────────────────────────────────

output logAnalyticsWorkspaceId string = logAnalytics.id
output logAnalyticsCustomerId string = logAnalytics.properties.customerId
output logAnalyticsPrimaryKey string = logAnalytics.listKeys().primarySharedKey
output appInsightsConnectionString string = appInsights.properties.ConnectionString
output appInsightsInstrumentationKey string = appInsights.properties.InstrumentationKey
