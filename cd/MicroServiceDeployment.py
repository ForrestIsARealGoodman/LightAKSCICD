from MicroService import *
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import requests
import os
import time


AKS_API = r"https://management.azure.com/subscriptions" \
          r"/{0}/resourceGroups/{1}" \
          r"/providers/Microsoft.ContainerService" \
          r"/managedClusters/{2}/runCommand?api-version=2022-09-01"

TABLE_SUB = "subinfo"
TABLE_AKS = "aksinfo"
# release__cloud2.9
RELEASE_VERSION_PREFIX = r"release__"
# feature__wem-24503-ci
FEATURE_VERSION_PREFIX = r"feature__"
FEATURE_BRANCH_PREFIX = r"wem"

# deploy command result
PROVISION_SUCCEED = "Succeeded"
PROVISION_FAILED = "Failed"
PROVISION_RUNNING = "Running"


def get_parser():
    parser = ArgumentParser(description=__doc__,
                            formatter_class=ArgumentDefaultsHelpFormatter)

    parser.add_argument("-sub", "--subscription_name",
                        help="subscription_name",
                        type=str,
                        required=True)

    parser.add_argument("-component", "--component_name",
                        help="component_name",
                        type=str,
                        required=True)

    parser.add_argument("-release", "--release_version",
                        help="release_version",
                        type=str,
                        required=True)

    parser.add_argument("-wait", "--wait_for_completion",
                        help="wait for latest command completion",
                        action='store_true',
                        required=False)

    parser.add_argument("-A", "--all_branch",
                        help="support for both images generated based on feature and release branch ",
                        action='store_true',
                        required=False)

    return parser


class MicroServiceDeploymentException(Exception):
    def __init__(self, error_msg):
        super().__init__(self)
        self._error_msg = error_msg

    def __str__(self):
        return self._error_msg


class MicroServiceDeployment:
    def __init__(self):
        self._storage_handler = None
        self._micro_service = None
        self._sub_name = ""
        self._component_name = ""
        self._deploy_version = ""
        self._wait_flag = False

    def init_params(self):
        cd_endpoint = "<CI build table endpoint url>"
        cd_account_name = os.environ['<CI build storage account name>']
        cd_key = os.environ['<CI build storage account name>']
        dict_param = get_parser().parse_args()
        self._sub_name = dict_param.subscription_name
        release_version = dict_param.release_version
        self._component_name = dict_param.component_name
        all_branch_flag = dict_param.all_branch
        if RELEASE_VERSION_PREFIX in release_version:
            self._deploy_version = release_version
        else:
            self._deploy_version = f"{RELEASE_VERSION_PREFIX}{release_version}"
        if all_branch_flag:
            if FEATURE_VERSION_PREFIX in release_version:
                self._deploy_version = release_version
            elif FEATURE_BRANCH_PREFIX in release_version.lower():
                self._deploy_version = f"{FEATURE_VERSION_PREFIX}{release_version}"
            else:
                pass
        self._wait_flag = dict_param.wait_for_completion
        if not self._wait_flag:
            self._storage_handler = StorageTableHandlerClass(cd_endpoint, cd_account_name, cd_key)
            self._micro_service = MicroService(self._component_name, self._deploy_version, self._storage_handler)

    def enter_job(self):
        if self._wait_flag:
            self.wait_for_completion()
        else:
            self.start_deployment()

    def start_deployment(self):
        # get aks api url
        # get image repo
        image_repo, aks_api_url = self.get_aks_info()

        # construct aks command
        # https://learn.microsoft.com/en-us/rest/api/aks/managed-clusters/run-command?tabs=HTTP
        headers = self.get_az_api_token_headers()
        resource_command, hash_context = self._micro_service.cook_micro_app_resource(image_repo, self._sub_name)
        try:
            data_command = dict()
            data_command["command"] = resource_command
            data_command["context"] = hash_context
            data_command["clusterToken"] = ""
            print(aks_api_url)
            print(repr(data_command))
            r = requests.post(url=aks_api_url, headers=headers, data=json.dumps(data_command))
            print(r.status_code)
            if r.status_code == 202:
                print(r.headers["Location"])
                # store query command result url
                var_map = dict()
                var_map["LASTCOMMAND"] = r.headers["Location"]
                write_variable_to_local(var_map)
        except requests.exceptions.RequestException as e:
            raise MicroServiceDeploymentException(f"failed to submit aks command due to:{repr(e)}")
        finally:
            print(f"submitted remote aks command:{resource_command} for component:{self._component_name} in sub:{self._sub_name}")

    def wait_for_completion(self):
        var_map = read_variable_from_local()
        query_command_url = var_map['LASTCOMMAND']
        print(f"query_command_url:{query_command_url}")
        headers = self.get_az_api_token_headers()
        try:
            r = requests.get(url=query_command_url, headers=headers)
            print(f"query command result:{r.status_code}")
            if r.status_code != 202 and r.status_code != 200:
                print("skip command waiting operation: token might be expired")
                return
            res = r.json()
            provision_state = res["properties"]["provisioningState"]
            while provision_state != PROVISION_SUCCEED and provision_state != PROVISION_FAILED:
                print(f"provision state:{provision_state}, sleep 3 secs...")
                time.sleep(3)
                r = requests.get(url=query_command_url, headers=headers)
                res = r.json()
                provision_state = res["properties"]["provisioningState"]
            if provision_state == PROVISION_FAILED:
                failed_reason = res["properties"]["reason"]
                raise MicroServiceDeploymentException(f"failed to deploy command due to:{failed_reason}")
            if provision_state == PROVISION_SUCCEED:
                exit_code = int(res["properties"]["exitCode"])
                msg_log = res["properties"]["logs"]
                if exit_code != 0:
                    # raise DeployMicroAppException(f"failed to deploy command due to:{msg_log}")
                    print(f"Warning!!! Deployed Resource return:{exit_code}, logs:{msg_log}")
                else:
                    print(f"Deployed Resource Successfully, logs:{msg_log}")
        except requests.exceptions.RequestException as e:
            raise MicroServiceDeploymentException(f"failed to get the result of last command due to:{repr(e)}")

    def get_az_api_token_headers(self):
        client_id = os.environ[f"{self._sub_name}_client_id"]
        spn_secret = os.environ[f"{self._sub_name}_secret"]
        tenant_id = os.environ[f"{self._sub_name}_tenant"]
        return get_bearer_token(tenant_id, client_id, spn_secret)

    def get_aks_info(self):
        # get aks name, resource group
        name_filter_aks = u"PartitionKey eq \'{0}\' "
        name_filter = name_filter_aks.format(self._sub_name)
        aks_entities = self._storage_handler.query_tables(TABLE_AKS, name_filter)
        if aks_entities is None or len(aks_entities) == 0:
            raise MicroServiceDeploymentException(f"No aks info for subscription:{self._sub_name}")
        aks_service = aks_entities[0]["RowKey"]
        resource_group = aks_entities[0]["ResourceGroup"]
        # get subscription id, container registry
        sub_entities = self._storage_handler.query_tables(TABLE_SUB, name_filter)
        if sub_entities is None or len(sub_entities) == 0:
            raise MicroServiceDeploymentException(f"No info for subscription:{self._sub_name}")
        sub_id = sub_entities[0]["SubscriptionId"]
        container_registry = sub_entities[0]["ContainerRegistry"]
        kv_endpoint = sub_entities[0]["KeyVault"]
        self._micro_service.set_kv_endpoint(kv_endpoint)
        aks_api_url = AKS_API.format(sub_id, resource_group, aks_service)
        return container_registry, aks_api_url


def get_bearer_token(tenant, client_id, spn_secret):
    auth_url = f'https://login.microsoftonline.com/{tenant}/oauth2/token?api-version=1.0'
    dict_body = dict()
    dict_body["grant_type"] = "client_credentials"
    dict_body["resource"] = "https://management.core.windows.net/"
    dict_body["client_id"] = client_id
    dict_body["client_secret"] = spn_secret
    try:
        r = requests.post(url=auth_url, data=dict_body)
        token = r.json()['access_token']
    except requests.exceptions.RequestException as e:
        raise e
    headers = {"Content-Type": "application/json", "Authorization": f'Bearer {token}', "charset": "utf-8"}
    return headers


def run_job():
    app_deploy = MicroServiceDeployment()
    app_deploy.init_params()
    app_deploy.enter_job()


if __name__ == '__main__':
    run_job()
