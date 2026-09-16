// VNet with a single subnet for Container Apps

param location string
param vnetName string
param subnetName string
param addressPrefix string
param subnetPrefix string

resource vnet 'Microsoft.Network/virtualNetworks@2024-03-01' = {
  name: vnetName
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [addressPrefix]
    }
    subnets: [
      {
        name: subnetName
        properties: {
          addressPrefix: subnetPrefix
          serviceEndpoints: [
            { service: 'Microsoft.ContainerRegistry/registries' }
            { service: 'Microsoft.OpenAI/accounts' }
          ]
          privateEndpointNetworkPolicies: 'Enabled'
        }
      }
    ]
  }
}

output vnetId string = vnet.id
output subnetId string = vnet.properties.subnets[0].id
