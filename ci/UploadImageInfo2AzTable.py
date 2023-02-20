from StorageTableHandler import *
from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import yaml
import os
import json
import zipfile
import base64

TABLE_BUILD = "buildinfo"
TABLE_MICROSERVICE = "microservice"
RESOURCE_FOLDER = "resource"
CONFIG_FOLDER = "configuration"


def get_parser():
    parser = ArgumentParser(description=__doc__,
                            formatter_class=ArgumentDefaultsHelpFormatter)

    parser.add_argument("-account", "--account_name",
                        help="account_name",
                        type=str,
                        required=True)

    parser.add_argument("-key", "--access_key",
                        help="access_key",
                        type=str,
                        required=True)

    parser.add_argument("-component", "--component_name",
                        help="component_name",
                        type=str,
                        required=True)

    parser.add_argument("-branch", "--branch_name",
                        help="branch_name",
                        type=str,
                        required=True)

    parser.add_argument("-image", "--build_image",
                        help="image_name",
                        type=str,
                        required=True)

    return parser


class HandleImageException(Exception):
    def __init__(self, error_msg):
        super().__init__(self)
        self._error_msg = error_msg

    def __str__(self):
        return self._error_msg


class HandleImageInfo:
    def __init__(self):
        self._storage_handler = None
        self._component_name = None
        self._branch_name = None
        self._image_name = None
        self._resource_dir = None
        self._config_dir = None
        self.find_correct_dir_name()

    def find_correct_dir_name(self):
        # capitalize()
        if os.path.exists(RESOURCE_FOLDER):
            self._resource_dir = RESOURCE_FOLDER
        elif os.path.exists(RESOURCE_FOLDER.capitalize()):
            self._resource_dir = RESOURCE_FOLDER.capitalize()

        if os.path.exists(CONFIG_FOLDER):
            self._config_dir = CONFIG_FOLDER
        elif os.path.exists(CONFIG_FOLDER.capitalize()):
            self._config_dir = CONFIG_FOLDER.capitalize()

    def upload_build_info(self):
        # insert or update data
        entity_params = dict()
        entity_params["PartitionKey"] = self._component_name
        entity_params["RowKey"] = str(self._branch_name).replace("/", "__")
        entity_params["latest_build"] = self._image_name
        self._storage_handler.insert_data(TABLE_BUILD, entity_params)
        print(f"uploaded build info for:{self._component_name}:{self._image_name}")

    def upload_micro_service_info(self):
        if os.path.exists(self._resource_dir) and len(os.listdir(self._resource_dir)) != 0:
            print(f"Resource config files exists, will compress resource config data!")
            entity_params_dict = self.handle_resource_config()
            self._storage_handler.insert_data(TABLE_MICROSERVICE, entity_params_dict)
        else:
            raise HandleImageException("resource folder: resource/Resource does not exist")

    def upload_deployment_note(self):
        print(f"skip deployment_note info for:{self._component_name}")

    def get_hash_zip(self, folder_name, suffix):
        zip_context = ""
        if os.path.exists(folder_name) and len(os.listdir(folder_name)) != 0:
            zip_file = r"{0}\{1}_{2}.zip".format(folder_name, self._component_name, folder_name)
            with zipfile.ZipFile(zip_file, "w") as zip_writer:
                for each_file in os.listdir(folder_name):
                    if each_file.endswith(suffix):
                        each_file_path = os.path.join(folder_name, each_file)
                        zip_writer.write(each_file_path, os.path.basename(each_file_path))
            with open(zip_file, "rb") as rb_reader:
                bytes_stream = rb_reader.read()
                zip_context = str(base64.b64encode(bytes_stream).decode("utf-8", "ignore"))
            print(f"{folder_name}:{suffix}:{zip_context}")
        return zip_context

    def handle_resource_config(self):
        entity_params = dict()
        entity_params["PartitionKey"] = self._component_name
        entity_params["RowKey"] = "resource"
        entity_params["ResourceStr"] = self.get_hash_zip(self._resource_dir, ".yaml")
        entity_params["ConfigStr"] = self.get_hash_zip(self._config_dir, ".json")
        return entity_params.copy()

    def upload_info(self):
        endpoint = "https://cdbuild.table.core.windows.net/"
        dict_param = get_parser().parse_args()
        account_name = dict_param.account_name
        access_key = dict_param.access_key
        self._component_name = dict_param.component_name
        self._branch_name = dict_param.branch_name
        self._image_name = dict_param.build_image
        self._storage_handler = StorageTableHandlerClass(endpoint, account_name, access_key)
        # begin to upload CI info
        self.upload_micro_service_info()
        self.upload_build_info()
        self.upload_deployment_note()


def run_task():
    image_handler = HandleImageInfo()
    image_handler.upload_info()


def run_test():
    image_handler = HandleImageInfo()
    image_handler._component_name = "dashboardbackend"
    entity_params_list = image_handler.handle_resource_config()
    for each_entity_params in entity_params_list:
        print(repr(each_entity_params))


if __name__ == '__main__':
    run_task()

