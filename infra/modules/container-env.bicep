// Container Apps Environment with VNet integration

param location string
param environmentName string
param vnetId string
param subnetId string

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: environmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
    }
    vnetConfiguration: {
      internal: true
      infrastructureSubnetId: subnetId
    }
  }
}

output name string = environment.name
