import json
import os
import yaml
import zipfile
import base64

from StorageTableHandler import *
from K8sResourceHandler import *
from Utility import *
from azure.identity import ManagedIdentityCredential
from azure.keyvault.secrets import SecretClient

TABLE_MICROSERVICE = "microservice"
TABLE_BUILD = "buildinfo"
RESOURCE_FILE_DEPLOYMENT = ["deployment", "statefulset"]


def generate_yaml_file(yaml_file, resource_dict):
    temporary_dir = os.path.join(os.getcwd(), "deployment")
    if not os.path.exists(temporary_dir):
        os.makedirs(temporary_dir)
    deployment_yaml = os.path.join(temporary_dir, yaml_file)
    with open(deployment_yaml, 'w') as yaml_writer:
        yaml.dump(resource_dict, yaml_writer)


def write_variable_to_local(var_map):
    if var_map is None or len(var_map) == 0:
        return
    temporary_dir = os.path.join(os.getcwd(), "deployment")
    if not os.path.exists(temporary_dir):
        os.makedirs(temporary_dir)
    var_json_file = os.path.join(temporary_dir, "vars.json")
    with open(var_json_file, 'w') as json_writer:
        json.dump(var_map, json_writer)


def read_variable_from_local():
    temporary_dir = os.path.join(os.getcwd(), "deployment")
    if not os.path.exists(temporary_dir):
        return None
    var_json_file = os.path.join(temporary_dir, "vars.json")
    with open(var_json_file, 'r') as json_reader:
        var_map = json.load(json_reader)
    return var_map


class MicroServiceInfo:
    def __init__(self):
        self.app_name = ""
        self.image_name = ""
        self.service_type = ""
        self.param_dict = dict()
        self.resource_base64_hash = ""
        self.config_base64_hash = ""
        self.build_image = ""
        self.deployment_resource = None
        self.service_resource = None

    def dump_deployment_resource_to_local(self, container_name):
        pass

    def dump_service_resource_to_local(self, container_name):
        pass


class MicroServiceException(Exception):
    def __init__(self, error_msg):
        super().__init__(self)
        self._error_msg = error_msg

    def __str__(self):
        return self._error_msg


class MicroService:
    def __init__(self, component, deploy_version, storage_table_obj):
        self._component = component
        self._deploy_version = deploy_version
        # key:container(pod) name,
        # value: AKSResource (deployment.yaml, service.yaml)
        self._microservice_info = MicroServiceInfo()
        self._storage_handler = storage_table_obj
        # key: micro app name,
        # value: docker image
        self._kv_credential = None
        self._kv_endpoint = None
        self._kv_secret_client = None
        self._resource_dir = "resource_tmp"
        self._config_dir = "config_tmp"

    def init_params(self, endpoint, account_name, access_key):
        self._storage_handler = StorageTableHandlerClass(endpoint, account_name, access_key)

    def cook_micro_app_resource(self, image_repo, sub_name):
        # fetch image from table 'buildinfo' and 'acrinfo'
        # fetch container info from table TABLE_CONTAINER
        self.get_image_info(image_repo)
        self.get_microservice_info()

        # create deployment and service resource yaml file
        k8s_command = "kubectl apply"
        print("handle native resource files")
        # only handle resource files once
        k8s_command, k8s_context = self.handle_resource_files(self._microservice_info.resource_base64_hash,
                                                              self._microservice_info.config_base64_hash,
                                                              sub_name,
                                                              self._microservice_info.build_image)

        return k8s_command, k8s_context

    def handle_resource_files(self, resource_base64_hashcode, config_base64_hashcode, sub_name, build_image):
        # decode yaml resource file zip file
        # unzip files
        # replace image info for all statefulset and deployment yaml
        # zip files
        # generate new command and context hash code
        k8s_command = "kubectl apply"
        if not os.path.exists(self._resource_dir):
            os.makedirs(self._resource_dir)
        zip_bytes = base64.b64decode(resource_base64_hashcode)
        resource_zip = os.path.join(self._resource_dir, self._resource_dir + ".zip")
        with open(resource_zip, 'wb') as zip_writer:
            zip_writer.write(zip_bytes)
        with zipfile.ZipFile(resource_zip, 'r') as zip_ref:
            zip_ref.extractall(self._resource_dir)
        zip_file_deployment = os.path.join(self._resource_dir, self._resource_dir + "_new.zip")
        with zipfile.ZipFile(zip_file_deployment, "w") as zip_writer:
            for each_file in os.listdir(self._resource_dir):
                if each_file.endswith(".yaml"):
                    yaml_file_path = os.path.join(self._resource_dir, each_file)
                    if each_file.split("-")[0] in RESOURCE_FILE_DEPLOYMENT:
                        MicroService.replace_build_image_for_resource_files(build_image, yaml_file_path)
                        self.replace_kv_secret_for_resource_files(yaml_file_path)
                    k8s_command += " -f " + each_file
                    zip_writer.write(yaml_file_path, os.path.basename(yaml_file_path))
            yaml_file_path = self.handle_config_files(config_base64_hashcode, sub_name)
            if yaml_file_path is not None:
                k8s_command += " -f " + os.path.basename(yaml_file_path)
                zip_writer.write(yaml_file_path, os.path.basename(yaml_file_path))
        with open(zip_file_deployment, "rb") as rb_reader:
            bytes_stream = rb_reader.read()
            context = base64.b64encode(bytes_stream).decode("utf-8", "ignore")
        print(f"k8s_command:{k8s_command}")
        print(f"context:{context}")
        return k8s_command, context

    def handle_config_files(self, config_base64_hashcode, sub_name):
        if not config_base64_hashcode or len(config_base64_hashcode) == 0:
            print("skip appsettings config as it is empty")
            return None
        else:
            config_map_file = f"configmap-{self._component}.yaml"
            yaml_file_path = os.path.join(self._resource_dir, config_map_file)
            if not os.path.exists(self._config_dir):
                os.makedirs(self._config_dir)
            config_zip_bytes = base64.b64decode(config_base64_hashcode)
            config_zip = os.path.join(self._config_dir, self._config_dir + ".zip")
            with open(config_zip, 'wb') as zip_writer:
                zip_writer.write(config_zip_bytes)
            with zipfile.ZipFile(config_zip, 'r') as zip_ref:
                zip_ref.extractall(self._config_dir)
            env_appsettings_name = f"{sub_name}-appsettings.json"
            env_appsettings_path = os.path.join(self._config_dir, env_appsettings_name)
            if not os.path.exists(env_appsettings_path):
                raise MicroServiceException(f"failed to find the correct env appsettings file:{env_appsettings_name}")
            with open(env_appsettings_path, "r") as config_reader:
                # format the appsettings.json
                yaml.add_representer(Literal, literal_presenter)
                config_json = config_reader.read()
                params = dict()
                params['configmap_name'] = "appsettingconfig"
                params['namespace'] = self._component
                params['appsettings'] = Literal(config_json.replace('\t', ""))
                config_map_obj = K8sResourceWrapper.create_config_map(params)
                with open(yaml_file_path, 'w') as yaml_writer:
                    yaml.dump(config_map_obj, yaml_writer)
            return yaml_file_path

    def replace_kv_secret_for_resource_files(self, resource_file):
        # check if it has any kv secret defined
        # get the list of kv secret to be queried
        # fulfill the deployment/statefulset template file
        yaml_dict = dict()
        with open(resource_file, 'r') as yaml_reader:
            try:
                yaml_dict = yaml.safe_load(yaml_reader)
                print(repr(yaml_dict))
            except yaml.YAMLError as exc:
                raise MicroServiceException(exc)
        container_list = yaml_dict["spec"]["template"]["spec"]["containers"]
        # format yaml string value with double quotes ""
        yaml.add_representer(Quoted, quoted_presenter)
        for each_container in container_list:
            if "env" in each_container:
                env_vars = each_container["env"]
                for each_var in env_vars:
                    # format with "{{ kv_secret }}"
                    if check_var_substr(each_var["value"]):
                        print(f"{each_var['name']} has kv secret")
                        kv_secret_name = get_var_substr(each_var["value"])
                        print(f"trying to get the value of kv secret:{kv_secret_name}")
                        each_var["value"] = Quoted(self.query_kv_secret(kv_secret_name))
        with open(resource_file, 'w') as yaml_writer:
            yaml.dump(yaml_dict, yaml_writer)

    def set_kv_endpoint(self, kv_endpoint):
        if kv_endpoint and len(kv_endpoint) != 0:
            self._kv_endpoint = kv_endpoint
        else:
            raise MicroServiceException(f"Invalid endpoint:{kv_endpoint}")

    def query_kv_secret(self, kv_secret_name):
        if self._kv_credential is None or self._kv_secret_client is None:
            self._kv_credential = ManagedIdentityCredential()
            self._kv_secret_client = SecretClient(vault_url=self._kv_endpoint, credential=self._kv_credential)
        return self._kv_secret_client.get_secret(kv_secret_name).value

    @staticmethod
    def replace_build_image_for_resource_files(build_image, resource_file):
        yaml_dict = dict()
        with open(resource_file, 'r') as yaml_reader:
            try:
                yaml_dict = yaml.safe_load(yaml_reader)
                print(repr(yaml_dict))
            except yaml.YAMLError as exc:
                raise MicroServiceException(exc)
        container_obj = yaml_dict["spec"]["template"]["spec"]["containers"][0]
        container_obj["image"] = build_image
        with open(resource_file, 'w') as yaml_writer:
            yaml.dump(yaml_dict, yaml_writer)

    def get_hash_yaml_zip(self):
        zip_dir = "deployment"
        zip_file = os.path.join(zip_dir, self._component + ".zip")
        with zipfile.ZipFile(zip_file, "w") as zip_writer:
            for each_file in os.listdir(zip_dir):
                if each_file.endswith(".yaml"):
                    yaml_file_path = os.path.join(zip_dir, each_file)
                    zip_writer.write(yaml_file_path, os.path.basename(yaml_file_path))
        with open(zip_file, "rb") as rb_reader:
            bytes_stream = rb_reader.read()
            context = base64.b64encode(bytes_stream).decode("utf-8", "ignore")
        print(f"{context}")
        return str(context)

    def get_microservice_info(self):
        name_filter_app = u"PartitionKey eq \'{0}\'"
        name_filter = name_filter_app.format(self._component)
        service_entities = self._storage_handler.query_tables(TABLE_MICROSERVICE, name_filter)
        if service_entities is None or len(service_entities) == 0:
            raise MicroServiceException(f"No service info was found with component:{self._component}")
        entity = service_entities[0]
        self._microservice_info.service_type = entity["RowKey"]
        self._microservice_info.resource_base64_hash = entity["ResourceStr"]
        self._microservice_info.config_base64_hash = entity["ConfigStr"]

    def get_image_info(self, image_repo):
        component_filter_build = u"PartitionKey eq \'{0}\' and RowKey eq \'{1}\'"
        component_filter = component_filter_build.format(self._component, self._deploy_version)
        query_entities = self._storage_handler.query_tables(TABLE_BUILD, component_filter)
        if query_entities is None or len(query_entities) == 0:
            raise MicroServiceException(f"No image queried for component:{self._component}")
        service_entity = query_entities[0]
        base_image = service_entity["latest_build"]
        full_image = image_repo + "/" + base_image
        self._microservice_info.build_image = full_image


if __name__ == '__main__':
    pass

