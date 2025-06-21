import argparse
import json
from mcp.server.fastmcp import FastMCP
import fault_inject
import kube

mcp = FastMCP("Chaos Mesh", log_level="INFO")


@mcp.tool()
def pod_kill(service: str, duration: str, mode: str, value: str) -> dict:
    """
    Kill pods of a service.

    Args:
        service (str): The name of the service to kill, e.g., "adservice".
        duration (str): The duration of the experiment, e.g., "5m".
        mode (str): The mode of the experiment, The mode options include one (selecting a random Pod), all (selecting all eligible Pods), fixed (selecting a specified number of eligible Pods), fixed-percent (selecting a specified percentage of Pods from the eligible Pods), and random-max-percent (selecting the maximum percentage of Pods from the eligible Pods).
        value (str): value (str): The value for the mode configuration, depending on mode. For example, when mode is set to fixed-percent, value specifies the percentage of Pods.

    Returns:
        dict: The applied experiment's resource in Kubernetes.
    """
    return fault_inject.pod_fault(
        service=service,
        type="POD_KILL",
        kwargs={"duration": duration, "mode": mode, "value": value},
    )


@mcp.tool()
def container_kill(service: str, duration: str, mode: str, value: str, container_names: list[str]) -> dict:
    """
    Kill containers within a pod.

    Args:
        service (str): The name of the service to inject fault into.
        duration (str): Duration of the stress.
        mode (str): Mode of pod selection.
        value (str): Mode value.
        container_names (list[str]): List of container names to kill.

    Returns:
        dict: The applied experiment's resource.
    """
    return fault_inject.pod_fault(
        service=service,
        type="CONTAINER_KILL",
        kwargs={"duration": duration, "mode": mode,
                "value": value, "container_names": container_names},
    )


@mcp.tool()
def pod_failure(service: str, duration: str, mode: str, value: str) -> dict:
    """
    Inject a failure into pods of a service.

    Args:
        service (str): The name of the service to kill, e.g., "adservice".
        duration (str): Duration of the stress.
        mode (str): Mode of pod selection.
        value (str): Mode value.

    Returns:
        dict: The applied experiment's resource in Kubernetes.
    """
    return fault_inject.pod_fault(
        service=service,
        type="POD_FAILURE",
        kwargs={"duration": duration, "mode": mode, "value": value},
    )


@mcp.tool()
def pod_cpu_stress(service: str, duration: str, mode: str, value: str, container_names: list[str], workers: int, load: int) -> dict:
    """
    Apply CPU stress on pods.

    Args:
        service (str): Service name.
        duration (str): Duration of the stress.
        mode (str): Mode of pod selection.
        value (str): Mode value.
        container_names (list[str]): Containers to stress.
        workers (int): The number of workers for the stress test.
        load (int): The percentage of CPU occupied. 0 means that no additional CPU is added, and 100 refers to full load. The final sum of CPU load is workers * load.

    Returns:
        dict: Applied stress test configuration.
    """
    return fault_inject.pod_stress_test(
        service=service,
        type="POD_STRESS_CPU",
        container_names=container_names,
        kwargs={"duration": duration, "mode": mode,
                "value": value, "workers": workers, "load": load},
    )


@mcp.tool()
def pod_memory_stress(service: str, duration: str, mode: str, value: str, container_names: list[str], size: str, time: str) -> dict:
    """
    Apply memory stress on pods.

    Args:
        service (str): Service name.
        duration (str): Experiment duration.
        mode (str): Mode of pod selection.
        value (str): Mode value.
        container_names (list[str]): Containers to stress.
        size (str): The memory size to be occupied or a percentage of the total memory size. The final sum of the occupied memory size is size. e.g., "256MB", "50%".
        time (str): The time to reach the memory size. The growth model is a linear model. e.g., "10min".

    Returns:
        dict: Applied memory stress test resource.
    """
    return fault_inject.pod_stress_test(
        service=service,
        type="POD_STRESS_MEMORY",
        container_names=container_names,
        kwargs={"duration": duration, "mode": mode,
                "value": value, "size": size, "time": time},
    )


@mcp.tool()
def host_cpu_stress(address: list[str], duration: str, workers: int, load: int) -> dict:
    """
    Apply CPU stress to hosts.

    Args:
        address (list[str]): List of target host IPs.
        duration (str): Stress duration.
        workers (int): Number of CPU stress workers.
        load (int): CPU load percentage per worker.

    Returns:
        dict: Stress test resource.
    """
    return fault_inject.host_stress_test(
        type="HOST_STRESS_CPU",
        address=address,
        kwargs={"duration": duration, "workers": workers, "load": load},
    )


@mcp.tool()
def host_memory_stress(address: list[str], duration: str, size: str, time: str) -> dict:
    """
    Apply memory stress to hosts.

    Args:
        address (list[str]): Host addresses.
        duration (str): Duration of experiment.
        size (str): Memory size to allocate.
        time (str): Time to gradually consume memory.

    Returns:
        dict: Memory stress configuration.
    """
    return fault_inject.host_stress_test(
        type="HOST_STRESS_MEMORY",
        address=address,
        kwargs={"duration": duration, "size": size, "time": time},
    )


@mcp.tool()
def host_disk_fill(address: list[str], duration: str, size: str, path: str, payload_process_num: int, fill_by_fallocate: bool) -> dict:
    """
    Fill disk on hosts.

    Args:
        address (list[str]): Host IPs.
        duration (str): Experiment duration.
        size (str): The size of the payload, e.g., "1024K".
        path (str): Target path.
        payload_process_num (int): Number of fill processes.
        fill_by_fallocate (bool): Use fallocate or not.

    Returns:
        dict: Disk fault resource.
    """
    return fault_inject.host_disk_fault(
        type="HOST_FILL",
        address=address,
        size=size,
        path=path,
        kwargs={"duration": duration, "payload_process_num": payload_process_num,
                "fill_by_fallocate": fill_by_fallocate},
    )


@mcp.tool()
def host_read_payload(address: list[str], duration: str, size: str, path: str, payload_process_num: int) -> dict:
    """
    Read payload on hosts.

    Args:
        address (list[str]): Host IPs.
        duration (str): Experiment duration.
        size (str): Disk size to fill.
        path (str): Target path.
        payload_process_num (int): The number of processes to read or write the payload.

    Returns:
        dict: Disk fault resource.
    """
    return fault_inject.host_disk_fault(
        type="HOST_READ_PAYLOAD",
        address=address,
        size=size,
        path=path,
        kwargs={"duration": duration,
                "payload_process_num": payload_process_num},
    )


@mcp.tool()
def host_write_payload(address: list[str], duration: str, size: str, path: str, payload_process_num: int) -> dict:
    """
    Write payload on hosts.

    Args:
        address (list[str]): Host IPs.
        duration (str): Experiment duration.
        size (str): Disk size to fill.
        path (str): Target path.
        payload_process_num (int): The number of processes to read or write the payload.

    Returns:
        dict: Disk fault resource.
    """
    return fault_inject.host_disk_fault(
        type="HOST_WRITE_PAYLOAD",
        address=address,
        size=size,
        path=path,
        kwargs={"duration": duration,
                "payload_process_num": payload_process_num},
    )


@mcp.tool()
def network_bandwidth(service: str, mode: str, value: str, direction: str, rate: str, limit: int, buffer: int, external_targets: list[str]) -> dict:
    """
    Limit network bandwidth to a pod.

    Args:
        service (str): Service to affect.
        mode (str): Mode of pod selection.
        value (str): Mode value.
        direction (str): The direction of target packets. Available values include from (the packets from target), to (the packets to target), and both ( the packets from or to target). This parameter makes Chaos only take effect for a specific direction of packets.
        rate (str): The bandwidth limit. Allows bit, kbit, mbit, gbit, tbit, bps, kbps, mbps, gbps, tbps unit. bps means bytes per second. e.g., "1mbps".
        limit (int): The number of bytes waiting in queue.
        buffer (int): The maximum number of bytes that can be sent instantaneously.
        external_targets (list[str]): The network targets except for Kubernetes, which can be IPv4 addresses or domains or service name. e,.g., ["www.example.com", "1.1.1.1", "checkoutservice].

    Returns:
        dict: Bandwidth limit configuration.
    """
    return fault_inject.network_fault(
        service=service,
        type="NETWORK_BANDWIDTH",
        kwargs={"mode": mode, "value": value, "direction": direction, "rate": rate,
                "limit": limit, "buffer": buffer, "external_targets": external_targets},
    )


@mcp.tool()
def network_partition(service: str, mode: str, value: str, direction: str, external_targets: list[str]) -> dict:
    """
    Apply a network partition for a pod.

    Args:
        service (str): The name of the service to inject the fault into, e.g., "adservice".
        mode (str): The mode of the experiment.
        value (str): The value for the mode configuration.
        direction (str): The direction of target packets.
        external_targets (list[str]): The network targets except for Kubernetes, which can be IPv4 addresses or domains or service name."

    Response:
        dict: The applied experiment's resource in Kubernetes.
    """
    return fault_inject.network_fault(
        service=service,
        type="NETWORK_PARTITION",
        kwargs={"mode": mode, "value": value, "direction": direction,
                "external_targets": external_targets},
    )


@mcp.tool()
def get_logs(service_name: str, namespace: str, container_name: str) -> dict:
    """
    Retrieve logs for the pods of a specific service in a namespace.

    Args:
        service_name (str): Name of the service.
        namespace (str): Namespace of the service.
        container_name (str): Name of the container.

    Returns:
        dict: Dictionary with pod names as keys and logs as values.
    """
    return kube.get_service_pod_logs(
        service_name=service_name,
        namespace=namespace,
        container_name=container_name,
        type="all",
        tail_lines=50
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

    result = next(iter(log_dict.values()), None)
    return result if result is not None else ""


@mcp.tool()
def delete_experiment(type: str, name: str) -> dict:
    """
    Delete a fault injection experiment
    Args:
        type (str): The type of fault to delete.
        name (str): The name of the experiment to delete.
    Returns:
        dict: The result of the deletion.
    """
    return fault_inject.delete_experiment(
        type=type,
        name=name,
    )


@mcp.tool()
def load_generate(rate: int) -> list[str]:
    """
    Generate load on the cluster
    Args:
        rate (int): The rate of the load generator.
    Returns:
        list[str]: The response of the load generation.
    """
    return kube.load_generate(rate=rate)


@mcp.tool()
def inject_delay_fault(service: str, delay: int) -> dict:
    """
    Inject a delay fault into a service. Attention: this fault affects the request to the service, not the service itself.
    Args:
        service (str): The name of the service to inject the fault into.
        delay (int): The delay time in seconds.
    Returns:
        dict: The result of the fault injection.
    """
    return kube.inject_delay_fault(
        service_name=service,
        delay_seconds=delay,
    )


@mcp.tool()
def remove_delay_fault(service: str) -> dict:
    """
    Remove a delay fault from a service
    Args:
        service (str): The name of the service to remove the fault from.
    Returns:
        dict: The result of the fault removal.
    """
    return kube.remove_delay_fault(service)


@mcp.resource(
    uri="service://all",
    name="all_services",
    description="All services in the cluster and their call relationships.",
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


def main():
    parser = argparse.ArgumentParser(
        description="Run the MCP with a specified transport.")
    parser.add_argument('--transport', type=str, default='stdio',
                        help="Specify the transport type.")
    args = parser.parse_args()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
