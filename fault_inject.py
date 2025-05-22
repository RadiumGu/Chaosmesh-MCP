import json
import uuid
from chaosmesh.client import Client, Experiment
from chaosmesh.k8s.selector import Selector

__all__ = [
    "pod_fault",
    "pod_stress_test",
    "host_stress_test",
    "host_disk_fault",
    "network_fault",
    "delete_experiment",
]

client = Client(version="v1alpha1")


def pod_fault(service: str, type: str, **kwargs) -> dict:
    """
    Inject a fault into a pod
    Args:
        service (str): The name of the service to inject the fault into, e.g., "adservice".
        type (str): The type of fault to inject, one of "POD_FAILURE", "POD_KILL", "CONTAINER_KILL".
            - POD_FAILURE: Simulate a pod failure.
            - POD_KILL: Simulate a pod kill.
            - CONTAINER_KILL: Simulate a container kill.
        kwargs: Additional arguments for the experiment.
            - duration (str): The duration of the experiment, e.g., "5m" for 5 minutes.
            - container_names (list[str]): The names of the containers to inject the fault into, only used for "CONTAINER_KILL".
            - mode (str): The mode of the experiment, The mode options include one (selecting a random Pod), all (selecting all eligible Pods), fixed (selecting a specified number of eligible Pods), fixed-percent (selecting a specified percentage of Pods from the eligible Pods), and random-max-percent (selecting the maximum percentage of Pods from the eligible Pods).
            - value (str): The value for the mode configuration, depending on mode. For example, when mode is set to fixed-percent, value specifies the percentage of Pods.

    Returns:
        dict: The applied experiment's resource in Kubernetes.
    """
    return _pod_fault_inject(
        service=service,
        type=type,
        **kwargs,
    )


def pod_stress_test(service: str, type: str, container_names: list[str], **kwargs) -> dict:
    """
    Simulate a stress test on a pod
    Args:
        service (str): The name of the service to inject the fault into, e.g., "adservice".
        type (str): The type of fault to inject, one of "POD_STRESS_CPU", "POD_STRESS_MEMORY".
            - POD_STRESS_CPU: Simulate a CPU stress test.
            - POD_STRESS_MEMORY: Simulate a memory stress test.
        container_names (list[str]): The names of the containers to inject the fault into.
        kwargs: Additional arguments for the experiment.
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
    return _pod_fault_inject(
        service=service,
        type=type,
        container_names=container_names,
        **kwargs,
    )


def host_stress_test(type: str, address: list[str], **kwargs) -> dict:
    """
    Simulate a stress test on a host
    Args:
        type (str): The type of fault to inject, one of "HOST_STRESS_CPU", "HOST_STRESS_MEMORY".
            - HOST_STRESS_CPU: Simulate a CPU stress test.
            - HOST_STRESS_MEMORY: Simulate a memory stress test.
        address (list[str]): The addresses of the hosts to inject the fault into.
        kwargs: Additional arguments for the experiment.
            - duration (str): The duration of the experiment, e.g., "5m" for 5 minutes.
            - workers (int): The number of workers for the stress test.
            - load (int): The percentage of CPU occupied. 0 means that no additional CPU is added, and 100 refers to full load. The final sum of CPU load is workers * load.
            - size (str): The memory size to be occupied or a percentage of the total memory size. The final sum of the occupied memory size is size. e.g., "256MB", "50%".
            - time (str): The time to reach the memory size. The growth model is a linear model. e.g., "10min".
    Returns:
        dict: The applied experiment's resource in Kubernetes.
    """
    return _fault_inject(
        type=type,
        address=address,
        **kwargs,
    )


def host_disk_fault(type: str, address: list[str], size: str, path: str, **kwargs) -> dict:
    """
    Simulate a disk fault on a host
    Args:
        type (str): The type of fault to inject, one of "HOST_FILL", "HOST_READ_PAYLOAD", "HOST_WRITE_PAYLOAD".
            - HOST_FILL: Simulate a disk fill.
            - HOST_READ_PAYLOAD: Simulate a disk read payload.
            - HOST_WRITE_PAYLOAD: Simulate a disk write payload.
        address (list[str]): The addresses of the hosts to inject the fault into.
        size (str): The size of the payload, e.g., "1024K".
        path (str): The path to the file to be read or written.
        kwargs: Additional arguments for the experiment.
            - payload_process_num (int): The number of processes to read or write the payload.
            - fill_by_fallocate (bool): Whether to fill the disk by fallocate.
            - duration (str): The duration of the experiment, e.g., "5m" for 5 minutes.
    Returns:
        dict: The applied experiment's resource in Kubernetes.
    """
    return _fault_inject(
        type=type,
        address=address,
        size=size,
        path=path,
        **kwargs
    )


def network_fault(service: str, type: str, **kwargs) -> dict:
    """
    Simulate a network fault on a pod
    Args:
        service (str): The name of the service to inject the fault into, e.g., "adservice".
        type (str): The type of fault to inject, one of "NETWORK_PARTITION", "NETWORK_BANDWIDTH".
            - NETWORK_PARTITION: Simulate a network partition.
            - NETWORK_BANDWIDTH: Simulate a network bandwidth limitation.
        kwargs: Additional arguments for the experiment.
            - mode (str): The mode of the experiment, The mode options include one (selecting a random Pod), all (selecting all eligible Pods), fixed (selecting a specified number of eligible Pods), fixed-percent (selecting a specified percentage of Pods from the eligible Pods), and random-max-percent (selecting the maximum percentage of Pods from the eligible Pods).
            - value (str): The value for the mode configuration, depending on mode. For example, when mode is set to fixed-percent, value specifies the percentage of Pods.
            - direction (str): The direction of target packets. Available values include from (the packets from target), to (the packets to target), and both ( the packets from or to target). This parameter makes Chaos only take effect for a specific direction of packets.
            - external_targets (list[str]): The network targets except for Kubernetes, which can be IPv4 addresses or domains or service name. e,.g., ["www.example.com", "1.1.1.1", "checkoutservice].
            - device (str): The affected network interface. e.g., "eth0".
            - rate (str): The bandwidth limit. Allows bit, kbit, mbit, gbit, tbit, bps, kbps, mbps, gbps, tbps unit. bps means bytes per second. e.g., "1mbps".
            - limit (int): The number of bytes waiting in queue.
            - buffer (int): The maximum number of bytes that can be sent instantaneously.
            - duration (str): The duration of the experiment, e.g., "5m" for 5 minutes.
    Returns:
        dict: The applied experiment's resource in Kubernetes.
    """
    return _pod_fault_inject(service=service, type=type, **kwargs)


def delete_experiment(type: str, name: str) -> dict:
    """
    Delete a fault injection experiment
    Args:
        type (str): The type of fault to delete.
        name (str): The name of the experiment to delete.
    Returns:
        dict: The result of the deletion.
    """
    try:
        experiment_type = Experiment[type]
    except KeyError:
        return {
            "error": f"Invalid experiment type: {type}. Valid types are: {list(Experiment.__dict__.keys())}"
        }

    print(f'Deleting experiment of type: {type} with name: {name}')

    return client.delete_experiment(
        experiment_type=experiment_type,
        namespace="default",
        name=name,
    )


def _pod_fault_inject(service: str, type: str, **kwargs) -> dict:
    selector = Selector(
        labelSelectors={"app": service}, pods=None, namespaces=['default'])
    kwargs['selector'] = selector

    return _fault_inject(
        type=type,
        **kwargs,
    )


def _fault_inject(type: str, **kwargs) -> dict:
    print(f'Starting fault injection of type: {type}')
    print(f'Additional arguments: {kwargs}')

    try:
        experiment_type = Experiment[type]
    except KeyError:
        return {
            "error": f"Invalid experiment type: {type}. Valid types are: {list(Experiment.__dict__.keys())}"
        }

    r = client.start_experiment(
        experiment_type=experiment_type,
        namespace="default",
        name=str(uuid.uuid4()),
        **kwargs,
    )

    print(f'Experiment started: {r}')

    return r
