# A simple lightweight CI/CD pipeline based on Azure kubernetes
## CI 
### Directory&Files Description
| Code Repo               |   Resource          | Configuration       |   Jenkinsfile     | Dockerfile     |
|-------------------------|:-------------------:|:-------------------:|:--------------:|--------------:|
| Project code, suggests one repo one microservice  | deployment yaml files   | private yaml files, need to be defined in the deployment yaml and  mapped into pod  | Jenkins file, add your customerized parameters | docker build file |

### Prerequesitive - Azure Storage AccountTables
* aksinfo

| PartitionKey            |      RowKey         | Resource Group      |   AKSType     |
|-------------------------|:-------------------:|:-------------------:|--------------:|
| subscription nick name  | subscription name   | aks resource group  | AKS uage type |

* buildinfo

| PartitionKey            |      RowKey         | Last Build          |  
|-------------------------|:-------------------:|--------------------:|
| project name            | branch name         | image build name    |

* microservice

| PartitionKey            |      RowKey            | ResourceStr         |  ConfigStr                                   |  
|-------------------------|:----------------------:|:-------------------:|---------------------------------------------:|
| project name            |  "resource" in default | K8s deployment yaml base64 code| private configure files base64 code to be mapped into pod |

* subinfo

| PartitionKey            |      RowKey         | ContainerRegistry   |    KeyVault     |   SubscriptionId    | 
|-------------------------|:-------------------:|:--------------------:|:--------------:|--------------------:|
| subscription nick name  | subscription name   | acr url              |  Key Vault url | Subscription Id     |

### Process
* Build docker image
* Convert resource files inside resource folder into base64 encoded string
* Convert config files inside resource folder into base64 encoded string
* Upload build info in above tables

## CD
### Configure jenkins file
### run CD job