from kubernetes import client, config, utils
import requests

config.load_kube_config()
v1 = client.CoreV1Api()
api = client.CustomObjectsApi()


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
        return ""


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


def load_generate(rate: int) -> list[str]:
    url = "http://localhost:80"
    results = []

    def send_request():
        try:
            response = requests.get(url=url, timeout=5)
            return f"Status: {response.status_code}"
        except Exception as e:
            return f"Error: {str(e)}"

    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=min(rate, 100)) as executor:
        futures = [executor.submit(send_request) for _ in range(rate)]
        for future in as_completed(futures):
            results.append(future.result())

    return results


def inject_delay_fault(service_name: str, delay_seconds: int):
    virtual_service_manifest = {
        "apiVersion": "networking.istio.io/v1",
        "kind": "VirtualService",
        "metadata": {
            "name": f"{service_name}-delay",
            "namespace": "default",
        },
        "spec": {
            "hosts": [service_name],
            "http": [
                {
                    "fault": {
                        "delay": {
                            "fixedDelay": f"{delay_seconds}s",
                            "percentage": {
                                "value": 100,
                            }
                        }
                    },
                    "route": [
                        {
                            "destination": {
                                "host": service_name
                            }
                        }
                    ]
                }
            ]
        }
    }

    r = api.create_namespaced_custom_object(
        group="networking.istio.io",
        version="v1",
        namespace="default",
        plural="virtualservices",
        body=virtual_service_manifest,
    )
    print(
        f"Injected delay fault for service '{service_name}' with {delay_seconds} seconds delay.")

    return r


def remove_delay_fault(service_name: str):
    try:
        r = api.delete_namespaced_custom_object(
            group="networking.istio.io",
            version="v1",
            namespace="default",
            plural="virtualservices",
            name=f"{service_name}-delay",
        )
        print(r)
        print(f"Removed delay fault for service '{service_name}'.")
    except Exception as e:
        print(f"Error removing delay fault: {e}")
