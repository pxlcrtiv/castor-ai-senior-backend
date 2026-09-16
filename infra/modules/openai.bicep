// Azure OpenAI Service with private endpoint

param location string
param resourceName string
param deploymentName string
param modelVersion string
param subnetId string

resource openAi 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: resourceName
  location: location
  kind: 'OpenAI'
  sku: { name: 'S0' }
  properties: {
    publicNetworkAccess: 'Disabled'
    networkAcls: { defaultAction: 'Deny' }
  }
}

resource deployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAi
  name: deploymentName
  properties: {
    model: {
      format: 'OpenAI'
      name: deploymentName
      version: modelVersion
    }
    scaleSettings: {
      scaleType: 'Standard'
    }
  }
}

resource privateEndpoint 'Microsoft.Network/privateEndpoints@2024-03-01' = {
  name: 'pe-${resourceName}'
  location: location
  properties: {
    subnet: { id: subnetId }
    privateLinkServiceConnections: [
      {
        name: 'plc-${resourceName}'
        properties: {
          privateLinkServiceId: openAi.id
          groupIds: ['account']
        }
      }
    ]
  }
}

output endpoint string = openAi.properties.endpoint
output primaryKeyName string = openAi.listKeys().primaryKeyName
output primaryKey string = openAi.listKeys().primaryKey
