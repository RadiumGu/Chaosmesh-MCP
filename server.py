import json
from mcp.server.fastmcp import FastMCP
import fault_inject
import kube

mcp = FastMCP("Chaos Mesh", log_level="INFO")


@mcp.tool()
def pod_fault(service: str, type: str, kwargs: str = "") -> dict:
    """
    Inject a fault into a pod
    Args:
        service (str): The name of the service to inject the fault into, e.g., "adservice".
        type (str): The type of fault to inject, one of "POD_FAILURE", "POD_KILL", "CONTAINER_KILL".
            - POD_FAILURE: Simulate a pod failure.
            - POD_KILL: Simulate a pod kill.
            - CONTAINER_KILL: Simulate a container kill.
        kwargs: Additional arguments for the experiment, you shuld pass in this format: {"key": "value", ...}.
            - duration (str): The duration of the experiment, e.g., "5m" for 5 minutes.
            - container_names (list[str]): The names of the containers to inject the fault into, only used for "CONTAINER_KILL".
            - mode (str): The mode of the experiment, The mode options include one (selecting a random Pod), all (selecting all eligible Pods), fixed (selecting a specified number of eligible Pods), fixed-percent (selecting a specified percentage of Pods from the eligible Pods), and random-max-percent (selecting the maximum percentage of Pods from the eligible Pods).
            - value (str): The value for the mode configuration, depending on mode. For example, when mode is set to fixed-percent, value specifies the percentage of Pods.

    Returns:
        dict: The applied experiment's resource in Kubernetes.
    """

    return fault_inject.pod_fault(
        service=service,
        type=type,
        kwargs=kwargs,
    )


@mcp.tool()
def pod_stress_test(service: str, type: str, container_names: list[str], kwargs: str = "") -> dict:
    """
    Simulate a stress test on a pod
    Args:
        service (str): The name of the service to inject the fault into, e.g., "adservice".
        type (str): The type of fault to inject, one of "POD_CPU_STRESS", "POD_MEMORY_STRESS".
            - POD_CPU_STRESS: Simulate a CPU stress test.
            - POD_MEMORY_STRESS: Simulate a memory stress test.
        container_names (list[str]): The names of the containers to inject the fault into.
        kwargs: Additional arguments for the experiment, you shuld pass in this format: {"key": "value", ...}.
            - duration (str): The duration of the experiment, e.g., "5m" for 5 minutes.
            - mode (str): The mode of the experiment, The mode options include one (selecting a random Pod), all (selecting all eligible Pods), fixed (selecting a specified number of eligible Pods), fixed-percent (selecting a specified percentage of Pods from the eligible Pods), and random-max-percent (selecting the maximum percentage of Pods from the eligible Pods).
            - value (str): The value for the mode configuration, depending on mode. For example, when mode is set to fixed-percent, value specifies the percentage of Pods.
            - workers (int): The number of workers for the stress test.
            - load (int): The percentage of CPU occupied. 0 means that no additional CPU is added, and 100 refers to full load. The final sum of CPU load is workers * load.
            - size (str): The memory size to be occupied or a percentage of the total memory size. The final sum of the occupied memory size is size. e.g., "256MB", "50%".
            - time (str): The time to reach the memory size. The growth model is a linear model. e.g., "10min".
    Returns:
        dict: The applied experiment's resource in Kubernetes.
    """
    return fault_inject.pod_stress_test(
        service=service,
        type=type,
        container_names=container_names,
        kwargs=kwargs,
    )


@mcp.tool()
def host_stress_test(type: str, address: list[str], kwargs: str = "") -> dict:
    """
    Simulate a stress test on a host
    Args:
        type (str): The type of fault to inject, one of "HOST_CPU_STRESS", "HOST_MEMORY_STRESS".
            - HOST_CPU_STRESS: Simulate a CPU stress test.
            - HOST_MEMORY_STRESS: Simulate a memory stress test.
        address (list[str]): The addresses of the hosts to inject the fault into.
        kwargs: Additional arguments for the experiment, you shuld pass in this format: {"key": "value", ...}.
            - duration (str): The duration of the experiment, e.g., "5m" for 5 minutes.
            - workers (int): The number of workers for the stress test.
            - load (int): The percentage of CPU occupied. 0 means that no additional CPU is added, and 100 refers to full load. The final sum of CPU load is workers * load.
            - size (str): The memory size to be occupied or a percentage of the total memory size. The final sum of the occupied memory size is size. e.g., "256MB", "50%".
            - time (str): The time to reach the memory size. The growth model is a linear model. e.g., "10min".
    Returns:
        dict: The applied experiment's resource in Kubernetes.
    """

    return fault_inject.host_stress_test(
        type=type,
        address=address,
        kwargs=kwargs,
    )


@mcp.tool()
def host_disk_fault(type: str, address: list[str], size: str, path: str, kwargs: str = "") -> dict:
    """
    Simulate a disk fault on a host
    Args:
        type (str): The type of fault to inject, one of "HOST_DISK_FILL", "HOST_READ_PAYLOAD", "HOST_WRITE_PAYLOAD".
            - HOST_DISK_FILL: Simulate a disk fill.
            - HOST_READ_PAYLOAD: Simulate a disk read payload.
            - HOST_WRITE_PAYLOAD: Simulate a disk write payload.
        address (list[str]): The addresses of the hosts to inject the fault into.
        size (str): The size of the payload, e.g., "1024K".
        path (str): The path to the file to be read or written.
        kwargs: Additional arguments for the experiment, you shuld pass in this format: {"key": "value", ...}.
            - payload_process_num (int): The number of processes to read or write the payload.
            - fill_by_fallocate (bool): Whether to fill the disk by fallocate.
            - duration (str): The duration of the experiment, e.g., "5m" for 5 minutes.
    Returns:
        dict: The applied experiment's resource in Kubernetes.
    """

    return fault_inject.host_disk_fault(
        type=type,
        address=address,
        size=size,
        path=path,
        kwargs=kwargs,
    )


@mcp.tool()
def network_fault(service: str, type: str, kwargs: str = "") -> dict:
    """
    Simulate a network fault on a pod
    Args:
        service (str): The name of the service to inject the fault into, e.g., "adservice".
        type (str): The type of fault to inject, one of "NETWORK_PARTITION", "NETWORK_BANDWIDTH".
            - NETWORK_PARTITION: Simulate a network partition.
            - NETWORK_BANDWIDTH: Simulate a network bandwidth limitation.
        kwargs: Additional arguments for the experiment, you shuld pass in this format: {"key": "value", ...}.
            - mode (str): The mode of the experiment, The mode options include one (selecting a random Pod), all (selecting all eligible Pods), fixed (selecting a specified number of eligible Pods), fixed-percent (selecting a specified percentage of Pods from the eligible Pods), and random-max-percent (selecting the maximum percentage of Pods from the eligible Pods).
            - value (str): The value for the mode configuration, depending on mode. For example, when mode is set to fixed-percent, value specifies the percentage of Pods.
            - direction (str): The direction of target packets. Available values include from (the packets from target), to (the packets to target), and both ( the packets from or to target). This parameter makes Chaos only take effect for a specific direction of packets.
            - externalTargets (list[str]): The network targets except for Kubernetes, which can be IPv4 addresses or domains. This parameter only works with direction: to. e,.g., ["www.example.com", "1.1.1.1"].
            - device (str): The affected network interface. e.g., "eth0".
            - rate (str): The bandwidth limit. Allows bit, kbit, mbit, gbit, tbit, bps, kbps, mbps, gbps, tbps unit. bps means bytes per second. e.g., "1mbps".
            - limit (int): The number of bytes waiting in queue.
            - buffer (int): The maximum number of bytes that can be sent instantaneously.
            - target_service (str): Used in combination with direction, making Chaos only effective for some packets.
    Returns:
        dict: The applied experiment's resource in Kubernetes.
    """
    return fault_inject.network_fault(
        service=service,
        type=type,
        kwargs=kwargs,
    )


@mcp.tool()
def get_logs(service_name: str, namespace: str, container_name: str, type: str = "all", tail_lines: int = 20) -> dict:
    """
    Retrieve logs for the pods of a specific service in a namespace.

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
    return kube.get_service_pod_logs(
        service_name=service_name,
        namespace=namespace,
        container_name=container_name,
        type=type,
        tail_lines=tail_lines
    )


@mcp.tool()
def get_load_test_results() -> str:
    """
    Retrieve and parse the loadgenerator test output logs. Attention: this result is the aggregated result of the beginning of the test to now.
    Args:
        None

    Returns:
        str: The parsed load test results.
    """
    log_dict = kube.get_service_pod_logs(
        service_name="loadgenerator",
        namespace="default",
        container_name="main",
        type="one",
        tail_lines=20
    )

    return next(iter(log_dict.values()), None)


@mcp.resource(
    uri="service://all",
    name="all_services",
    description="All services in the cluster"
)
def all_services() -> list[dict]:
    """
    Get all services in the cluster
    Returns:
        list[dict]: A list of all services in the cluster.
    """
    with open("services.json", "r") as f:
        data = json.load(f)
    return data


if __name__ == "__main__":
    mcp.run(transport='sse')
