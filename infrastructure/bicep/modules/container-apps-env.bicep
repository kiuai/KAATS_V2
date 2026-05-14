// ─────────────────────────────────────────────────────────────────────────────
// Container Apps Environment
// Consumption workload profile. Optional VNet injection for prod.
// ─────────────────────────────────────────────────────────────────────────────

@description('Azure region')
param location string

@description('Resource suffix (appName-env)')
param suffix string

@description('Log Analytics workspace resource ID')
param logAnalyticsWorkspaceId string

@description('Log Analytics customer ID')
param logAnalyticsCustomerId string

@secure()
@description('Log Analytics primary shared key')
param logAnalyticsPrimaryKey string

@description('Enable VNet integration (Container Apps subnet injection)')
param enableVnetIntegration bool

@description('Container Apps infrastructure subnet ID (required when enableVnetIntegration = true)')
param infrastructureSubnetId string

// ─────────────────────────────────────────────────────────────────────────────
// Managed Environment
// ─────────────────────────────────────────────────────────────────────────────

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${suffix}'
  location: location
  tags: { component: 'container-apps-env' }
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsCustomerId
        sharedKey: logAnalyticsPrimaryKey
      }
    }
    vnetConfiguration: enableVnetIntegration ? {
      infrastructureSubnetId: infrastructureSubnetId
      internal: false         // keep external to allow public ingress to api + frontend
    } : null
    zoneRedundant: false
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Outputs
// ─────────────────────────────────────────────────────────────────────────────

output environmentId string = env.id
output environmentName string = env.name
output defaultDomain string = env.properties.defaultDomain
output staticIp string = env.properties.staticIp
