from kubernetes import client


def correct_some_keys_format(key_name):
    index_underline = key_name.find('_')
    while index_underline != -1:
        sub_str = key_name[index_underline:index_underline+2]
        new_str = key_name[index_underline+1].upper()
        new_key = key_name.replace(sub_str, new_str)
        key_name = new_key
        index_underline = key_name.find('_')
    return key_name


def remove_none_from_dict(d):
    if type(d) is dict:
        return dict((correct_some_keys_format(k), remove_none_from_dict(v)) for k, v in d.items() if v and remove_none_from_dict(v))
    elif type(d) is list:
        return [remove_none_from_dict(v) for v in d if v and remove_none_from_dict(v)]
    else:
        return d


class K8sResourceWrapperException(Exception):
    def __init__(self, error_msg):
        super().__init__(self)
        self._error_msg = error_msg

    def __str__(self):
        return self._error_msg


class K8sResourceWrapper:
    def __init__(self, app_name):
        self._app_name = app_name
        self._container_name = app_name

    def init_params(self):
        pass

    def create_deployment(self, container_params):
        """
        pod_container - map
        key:value
        image_file
        request_limit
        resource_limit
        namespace
        concurrent_num
        """
        port_list = None
        if "port" in container_params:
            port_list = list()
            port_obj = client.V1ContainerPort(container_port=container_params["port"])
            port_list.append(port_obj)
        image_file = container_params["image_file"]
        request_limit = None
        resource_limit = None
        if "request_limit" in container_params:
            # {"cpu": "100m", "memory": "200Mi"}
            request_limit = container_params["request_limit"]
        if "resource_limit" in container_params:
            # {"cpu": "500m", "memory": "500Mi"}
            resource_limit = container_params["resource_limit"]
        labels = {"app": self._app_name}
        replicas_num = container_params["concurrent_num"]
        namespace = container_params["namespace"]
        strategy = {"type": "RollingUpdate", "rollingUpdate": {"maxSurge": 1, "maxUnavailable": 0}}
        env = None
        if "env" in container_params and container_params["env"] is not None:
            env = list()
            for each_env in container_params["env"]:
                env_var = client.V1EnvVar(
                    name=each_env["name"],
                    value=each_env["value"]
                )
                env.append(env_var)
        env_from = list()
        if "envfrom" in container_params and container_params["envfrom"] is not None:
            if "secret" in container_params["envfrom"] and container_params["envfrom"]["secret"] is not None:
                for each_secret_ref in container_params["envfrom"]["secret"]:
                    secret_name_ref = client.V1SecretEnvSource(
                        name=each_secret_ref
                    )
                    env_from_secret = client.V1EnvFromSource(
                        secret_ref=secret_name_ref
                    )
                    env_from.append(env_from_secret)
            if "config" in container_params["envfrom"] and container_params["envfrom"]["config"]:
                for each_config_ref in container_params["envfrom"]["config"]:
                    config_name_ref = client.V1ConfigMapEnvSource(
                        name=each_config_ref
                    )
                    env_from_config = client.V1EnvFromSource(
                        config_map_ref=config_name_ref
                    )
                    env_from.append(env_from_config)
        # begin to construct params
        container = client.V1Container(
            name=self._container_name,
            image=image_file,
            ports=port_list,
            resources=client.V1ResourceRequirements(
                requests=request_limit,
                limits=resource_limit,
            ),
            env=env,
            env_from=env_from
        )
        # Create and configure a spec section
        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels=labels),
            spec=client.V1PodSpec(containers=[container]),
        )
        # Create the specification of deployment
        spec = client.V1DeploymentSpec(
            replicas=replicas_num, template=template, selector={"matchLabels": labels}, strategy=strategy)

        # Instantiate the deployment object
        deployment = client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=client.V1ObjectMeta(name=self._container_name, namespace=namespace),
            spec=spec,
        )

        deployment_dict = remove_none_from_dict(deployment.to_dict())
        print(repr(deployment_dict))
        return deployment_dict

    def create_service(self, container_params):
        container_port = container_params["port"]
        namespace = container_params["namespace"]
        service_name = "svc" + self._app_name
        selector = {"app": self._app_name}
        ports_obj = [client.V1ServicePort(
            port=8080,
            target_port=container_port,
            name="http-port"
        )]
        spec_obj = client.V1ServiceSpec(
            selector=selector,
            ports=ports_obj
        )
        service = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(name=service_name, namespace=namespace),
            spec=spec_obj
        )
        service_dict = remove_none_from_dict(service.to_dict())
        print(repr(service_dict))
        return service_dict

    @staticmethod
    def create_config_map(container_params):
        configmap_name = container_params["configmap_name"]
        namespace = container_params["namespace"]
        json_content = container_params["appsettings"]
        data_body = {"appsettings.json": json_content}
        config_map = client.V1ConfigMap(
            api_version="v1",
            kind="ConfigMap",
            metadata=client.V1ObjectMeta(name=configmap_name, namespace=namespace),
            data=data_body
        )
        config_dict = remove_none_from_dict(config_map.to_dict())
        print(repr(config_dict))
        return config_dict


if __name__ == '__main__':
    component = "archivedatabase"
    import json
    import yaml
    from collections import OrderedDict

    class quoted(str):
        pass

    def quoted_presenter(dumper, data):
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='"')


    class literal(str):
        pass

    def literal_presenter(dumper, data):
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')


    def ordered_dict_presenter(dumper, data):
        return dumper.represent_dict(data.items())
    # yaml.add_representer(quoted, quoted_presenter)
    yaml.add_representer(Literal, literal_presenter)
    # yaml.add_representer(OrderedDict, ordered_dict_presenter)

    test_env_appsettings_path = r"config\production-appsettings.json"
    test_yaml_file_path = r"config\configmap-archivedatabase.yaml"
    with open(test_env_appsettings_path, "r") as config_reader:
        test_config_json = config_reader.read()
        test_params = dict()
        test_params['configmap_name'] = f"{component}-appsettings"
        test_params['namespace'] = component
        #json.dumps(config_json)
        test_params['appsettings'] = literal(test_config_json.replace('\t', ""))
        test_config_map_obj = K8sResourceWrapper.create_config_map(test_params)
        with open(test_yaml_file_path, 'w') as test_yaml_writer:
            yaml.dump(test_config_map_obj, test_yaml_writer)
