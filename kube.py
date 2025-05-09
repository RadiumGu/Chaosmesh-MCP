from kubernetes import client, config

config.load_kube_config()
v1 = client.CoreV1Api()


def get_pod_logs(pod_name: str, namespace: str, container_name: str, tail_lines: int = 20) -> str:
    """
    Retrieve logs for a specific pod and container.

    Args:
        pod_name (str): Name of the pod.
        namespace (str): Namespace of the pod.
        container_name (str): Name of the container.
        tail_lines (int): Number of lines to return from the end of the logs.
            Default is 20.

    Returns:
        str: Logs from the specified container in the pod.
    """
    try:
        # Retrieve logs for the specified container in the pod
        logs = v1.read_namespaced_pod_log(
            name=pod_name, namespace=namespace, container=container_name, tail_lines=tail_lines)
        return logs

    except Exception as e:
        print(f"Error retrieving logs: {e}")
        return None


def get_pods_by_service(service_name: str, namespace: str) -> list[str]:
    """
    Retrieve all pods for a specific service in a namespace.

    Args:
        service_name (str): Name of the service.
        namespace (str): Namespace of the service.

    Returns:
        list: List of pod names.
    """
    try:
        # List all pods in the specified namespace
        pods = v1.list_namespaced_pod(namespace=namespace)
        pod_names = [pod.metadata.name for pod in pods.items if pod.metadata.labels.get(
            'app') == service_name]
        return pod_names

    except Exception as e:
        print(f"Error retrieving pods: {e}")
        return []


def get_service_pod_logs(service_name: str, namespace: str, container_name: str, type: str = "all", tail_lines: int = 20) -> dict:
    """
    Retrieve logs for all pods of a specific service in a namespace.

    Args:
        service_name (str): Name of the service.
        namespace (str): Namespace of the service.
        container_name (str): Name of the container.
        type (str): Type of logs to retrieve. Default is "all".
            - "all": Retrieve logs from all pods.
            - "one": Retrieve logs from one pod.
        tail_lines (int): Number of lines to return from the end of the logs.
            Default is 20.

    Returns:
        dict: Dictionary with pod names as keys and logs as values.
    """
    pod_logs = {}
    pod_names = get_pods_by_service(service_name, namespace)

    if not pod_names:
        print(
            f"No pods found for service '{service_name}' in namespace '{namespace}'.")
        return pod_logs

    if type == "one":
        pod_names = [pod_names[0]]

    for pod_name in pod_names:
        logs = get_pod_logs(pod_name, namespace, container_name, tail_lines)
        if logs:
            pod_logs[pod_name] = logs
        else:
            print(f"No logs found for pod '{pod_name}'.")

    return pod_logs
