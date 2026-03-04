import json
import uuid
import logging
import time
from chaosmesh.client import Client, Experiment
from chaosmesh.k8s.selector import Selector
from kubernetes import client as k8s_client, config as k8s_config
from kubernetes.client.exceptions import ApiException
import os

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def initialize_kubernetes_config():
    """
    初始化Kubernetes配置，确保能正确连接到EKS集群
    """
    try:
        # 检查是否在集群内运行
        if os.path.exists('/var/run/secrets/kubernetes.io/serviceaccount'):
            logger.info("Loading in-cluster Kubernetes configuration")
            k8s_config.load_incluster_config()
        else:
            logger.info("Loading Kubernetes configuration from kubeconfig")
            k8s_config.load_kube_config()
        
        # 验证连接
        v1_test = k8s_client.CoreV1Api()
        namespaces = v1_test.list_namespace(limit=1)
        logger.info(f"✓ Kubernetes connection verified - found {len(namespaces.items)} namespace(s)")
        
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Kubernetes configuration: {e}")
        logger.error("Please ensure:")
        logger.error("1. kubectl is configured and can access the cluster")
        logger.error("2. For EKS: aws eks update-kubeconfig --region <region> --name <cluster-name>")
        logger.error("3. IAM permissions include eks:DescribeCluster and appropriate RBAC permissions")
        return False

def initialize_chaos_mesh_client():
    """
    初始化Chaos Mesh客户端，包含健康检查
    """
    try:
        # 首先确保Kubernetes配置已正确加载
        if not initialize_kubernetes_config():
            raise Exception("Kubernetes configuration failed")
        
        # 创建Chaos Mesh客户端
        client = Client(version="v1alpha1")
        
        # 验证Chaos Mesh是否可用
        v1 = k8s_client.CoreV1Api()
        
        # 检查chaos-mesh命名空间是否存在
        try:
            v1.read_namespace("chaos-mesh")
            logger.info("Chaos Mesh namespace found")
        except ApiException as e:
            if e.status == 404:
                logger.error("Chaos Mesh namespace not found. Please install Chaos Mesh first.")
                raise Exception("Chaos Mesh not installed")
            else:
                raise
        
        # 检查Chaos Mesh控制器是否运行
        pods = v1.list_namespaced_pod(
            namespace="chaos-mesh",
            label_selector="app.kubernetes.io/name=chaos-mesh"
        )
        
        running_pods = [pod for pod in pods.items if pod.status.phase == "Running"]
        if not running_pods:
            logger.error("No running Chaos Mesh controller pods found")
            raise Exception("Chaos Mesh controller not running")
        
        logger.info(f"Found {len(running_pods)} running Chaos Mesh controller pods")
        return client
        
    except Exception as e:
        logger.error(f"Failed to initialize Chaos Mesh client: {e}")
        logger.error("Please ensure:")
        logger.error("1. Chaos Mesh is installed: helm install chaos-mesh chaos-mesh/chaos-mesh -n chaos-mesh --create-namespace")
        logger.error("2. Chaos Mesh controllers are running")
        logger.error("3. RBAC permissions are correctly configured")
        raise

# 初始化客户端
try:
    client = initialize_chaos_mesh_client()
except Exception as e:
    logger.error(f"Chaos Mesh client initialization failed: {e}")
    client = None

__all__ = [
    "pod_fault",
    "pod_stress_test",
    "host_stress_test",
    "host_disk_fault",
    "network_fault",
    "delete_experiment",
]


def _apply_stress_chaos_via_kubectl(type: str, namespace: str, name: str, **kwargs) -> dict:
    """
    Workaround function to apply StressChaos using kubectl due to chaos-mesh Python client bug.
    The client doesn't include 'value' and 'containerNames' fields in the spec.
    """
    import subprocess
    import tempfile
    import yaml
    from dataclasses import asdict
    
    # Build the StressChaos spec
    spec = {
        "apiVersion": "chaos-mesh.org/v1alpha1",
        "kind": "StressChaos",
        "metadata": {
            "name": name,
            "namespace": namespace
        },
        "spec": {
            "selector": asdict(kwargs.get('selector')),
            "mode": kwargs.get('mode', 'all'),
            "duration": kwargs.get('duration', ''),
        }
    }
    
    # Add value if mode requires it
    if kwargs.get('mode') in ['fixed', 'fixed-percent', 'random-max-percent']:
        spec["spec"]["value"] = kwargs.get('value', '')
    
    # Add stressors based on type
    if type == "POD_STRESS_CPU":
        spec["spec"]["stressors"] = {
            "cpu": {
                "workers": kwargs.get('workers', 1),
                "load": kwargs.get('load', 100)
            }
        }
    elif type == "POD_STRESS_MEMORY":
        spec["spec"]["stressors"] = {
            "memory": {
                "workers": kwargs.get('workers', 1),
                "size": kwargs.get('size', '256MB')
            }
        }
    
    # Add containerNames if provided
    if kwargs.get('container_names'):
        spec["spec"]["containerNames"] = kwargs.get('container_names')
    
    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(spec, f)
        temp_file = f.name
    
    try:
        # Apply using kubectl
        result = subprocess.run(
            ['kubectl', 'apply', '-f', temp_file],
            capture_output=True,
            text=True,
            check=True
        )
        logger.info(f"Successfully applied StressChaos: {result.stdout}")
        
        # Return a dict similar to what the client would return
        return {
            "apiVersion": spec["apiVersion"],
            "kind": spec["kind"],
            "metadata": spec["metadata"],
            "spec": spec["spec"]
        }
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to apply StressChaos: {e.stderr}")
        return {
            "error": f"Failed to apply StressChaos: {e.stderr}",
            "experiment_name": name,
            "namespace": namespace,
            "type": type
        }
    finally:
        # Clean up temp file
        import os
        try:
            os.unlink(temp_file)
        except:
            pass


def pod_fault(service: str, type: str, namespace: str = "default", **kwargs) -> dict:
    """
    Inject a fault into a pod
    Args:
        service (str): The name of the service to inject the fault into, e.g., "adservice".
        type (str): The type of fault to inject, one of "POD_FAILURE", "POD_KILL", "CONTAINER_KILL".
            - POD_FAILURE: Simulate a pod failure.
            - POD_KILL: Simulate a pod kill.
            - CONTAINER_KILL: Simulate a container kill.
        namespace (str): The namespace where the service is located. Default is "default".
        kwargs: Additional arguments for the experiment.
            - duration (str): The duration of the experiment, e.g., "5m" for 5 minutes.
            - container_names (list[str]): The names of the containers to inject the fault into, only used for "CONTAINER_KILL".
            - mode (str): The mode of the experiment, The mode options include one (selecting a random Pod), all (selecting all eligible Pods), fixed (selecting a specified number of eligible Pods), fixed-percent (selecting a specified percentage of Pods from the eligible Pods), and random-max-percent (selecting the maximum percentage of Pods from the eligible Pods).
            - value (str): The value for the mode configuration, depending on mode. For example, when mode is set to fixed-percent, value specifies the percentage of Pods.

    Returns:
        dict: The applied experiment's resource in Kubernetes.
    """
    # 验证服务是否存在
    try:
        # 检查指定命名空间中是否有匹配的pods
        v1 = k8s_client.CoreV1Api()
        pods = v1.list_namespaced_pod(
            namespace=namespace,
            label_selector=f"app={service}"
        )
        
        if not pods.items:
            # 尝试其他常见的标签选择器
            alternative_selectors = [
                f"app.kubernetes.io/name={service}",
                f"k8s-app={service}"
            ]
            
            for selector in alternative_selectors:
                pods = v1.list_namespaced_pod(
                    namespace=namespace,
                    label_selector=selector
                )
                if pods.items:
                    break
            
            if not pods.items:
                return {
                    "error": f"No pods found for service '{service}' in namespace '{namespace}'. Please check service name and namespace."
                }
        
        logger.info(f"Found {len(pods.items)} pods for service '{service}' in namespace '{namespace}'")
        
    except Exception as e:
        logger.warning(f"Could not verify service existence: {e}")
    
    # 将namespace添加到kwargs中
    kwargs['namespace'] = namespace
    
    return _pod_fault_inject(
        service=service,
        type=type,
        **kwargs,
    )


def pod_stress_test(service: str, type: str, container_names: list[str], namespace: str = "default", **kwargs) -> dict:
    """
    Simulate a stress test on a pod
    Args:
        service (str): The name of the service to inject the fault into, e.g., "adservice".
        type (str): The type of fault to inject, one of "POD_STRESS_CPU", "POD_STRESS_MEMORY".
            - POD_STRESS_CPU: Simulate a CPU stress test.
            - POD_STRESS_MEMORY: Simulate a memory stress test.
        container_names (list[str]): The names of the containers to inject the fault into.
        namespace (str): The namespace where the service is located. Default is "default".
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
    # 将namespace添加到kwargs中
    kwargs['namespace'] = namespace
    
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
    Simulate a disk fault on a host via kubectl apply (workaround for Python client missing mode field).
    type: HOST_DISK_FILL | HOST_READ_PAYLOAD | HOST_WRITE_PAYLOAD
    """
    action_map = {
        "HOST_DISK_FILL": "disk-fill",
        "HOST_READ_PAYLOAD": "disk-read-payload",
        "HOST_WRITE_PAYLOAD": "disk-write-payload",
    }
    action = action_map.get(type)
    if action is None:
        return {"error": f"Invalid type: {type}. Valid: {list(action_map.keys())}"}

    name = _gen_name(type.lower().replace("_", "-"))
    duration = kwargs.get("duration", "1m")
    mode = kwargs.get("mode", "one")
    payload_process_num = kwargs.get("payload_process_num", 1)
    fill_by_fallocate = kwargs.get("fill_by_fallocate", True)

    spec_action = {}
    if type == "HOST_DISK_FILL":
        spec_action = {
            "disk-fill": {
                "size": size,
                "path": path,
                "fill-by-fallocate": fill_by_fallocate,
            }
        }
    elif type == "HOST_READ_PAYLOAD":
        spec_action = {
            "disk-read-payload": {
                "size": size,
                "path": path,
                "payload-process-num": payload_process_num,
            }
        }
    elif type == "HOST_WRITE_PAYLOAD":
        spec_action = {
            "disk-write-payload": {
                "size": size,
                "path": path,
                "payload-process-num": payload_process_num,
            }
        }

    manifest = {
        "apiVersion": "chaos-mesh.org/v1alpha1",
        "kind": "PhysicalMachineChaos",
        "metadata": {"name": name, "namespace": "default"},
        "spec": {
            "action": action,
            "mode": mode,
            "address": address,
            "duration": duration,
            **spec_action,
        }
    }
    return _apply_chaos_crd(manifest)


def network_fault(service: str, type: str, namespace: str = "default", **kwargs) -> dict:
    """
    Simulate a network fault on a pod
    Args:
        service (str): The name of the service to inject the fault into, e.g., "adservice".
        type (str): The type of fault to inject, one of "NETWORK_PARTITION", "NETWORK_BANDWIDTH".
            - NETWORK_PARTITION: Simulate a network partition.
            - NETWORK_BANDWIDTH: Simulate a network bandwidth limitation.
        namespace (str): The namespace where the service is located. Default is "default".
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
    # 将namespace添加到kwargs中
    kwargs['namespace'] = namespace
    
    return _pod_fault_inject(service=service, type=type, **kwargs)


def delete_experiment(type: str, name: str, namespace: str = "default") -> dict:
    """
    Delete a fault injection experiment
    Args:
        type (str): The type of fault to delete.
        name (str): The name of the experiment to delete.
        namespace (str): The namespace where the experiment is located. Default is "default".
    Returns:
        dict: The result of the deletion.
    """
    try:
        experiment_type = Experiment[type]
    except KeyError:
        return {
            "error": f"Invalid experiment type: {type}. Valid types are: {list(Experiment.__dict__.keys())}"
        }

    logger.info(f'Deleting experiment of type: {type} with name: {name} in namespace: {namespace}')

    return client.delete_experiment(
        experiment_type=experiment_type,
        namespace=namespace,
        name=name,
    )


def _pod_fault_inject(service: str, type: str, namespace: str = "default", **kwargs) -> dict:
    selector = Selector(
        labelSelectors={"app": service}, 
        namespaces=[namespace],
        pods={}
    )
    kwargs['selector'] = selector

    return _fault_inject(
        type=type,
        namespace=namespace,
        **kwargs,
    )


def _fault_inject(type: str, namespace: str = "default", **kwargs) -> dict:
    """
    改进的故障注入函数，包含重试机制和更好的错误处理
    """
    if client is None:
        return {
            "error": "Chaos Mesh client not initialized. Please check Chaos Mesh installation."
        }
    
    logger.info(f'Starting fault injection of type: {type} in namespace: {namespace}')
    logger.info(f'Additional arguments: {kwargs}')

    try:
        experiment_type = Experiment[type]
    except KeyError:
        available_types = [attr for attr in dir(Experiment) if not attr.startswith('_')]
        return {
            "error": f"Invalid experiment type: {type}. Valid types are: {available_types}"
        }

    # 生成唯一的实验名称，确保符合Kubernetes命名规范
    # 将下划线替换为连字符，确保名称符合RFC 1123规范
    experiment_name = f"{type.lower().replace('_', '-')}-{str(uuid.uuid4())[:8]}"
    
    # Workaround for StressChaos: chaos-mesh Python client has a bug where it doesn't include
    # 'value' and 'containerNames' fields in the spec. Use kubectl to apply YAML directly.
    if type in ["POD_STRESS_CPU", "POD_STRESS_MEMORY"]:
        logger.info(f"Using kubectl workaround for {type}")
        return _apply_stress_chaos_via_kubectl(
            type=type,
            namespace=namespace,
            name=experiment_name,
            **kwargs
        )
    
    # 添加重试机制
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt + 1}/{max_retries} to start experiment in namespace: {namespace}")
            
            r = client.start_experiment(
                experiment_type=experiment_type,
                namespace=namespace,
                name=experiment_name,
                **kwargs,
            )

            logger.info(f'Experiment started successfully: {experiment_name} in namespace: {namespace}')
            return r

        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 指数退避
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.error(f"All {max_retries} attempts failed")
                return {
                    "error": f"Failed to start experiment after {max_retries} attempts: {str(e)}",
                    "experiment_name": experiment_name,
                    "namespace": namespace,
                    "type": type
                }


# ─────────────────────────────────────────────────────────────────────────────
# Generic kubectl-based CRD applier
# ─────────────────────────────────────────────────────────────────────────────

def _apply_chaos_crd(manifest: dict) -> dict:
    """Apply any Chaos Mesh CRD manifest via kubectl apply."""
    import subprocess, tempfile, yaml, os
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(manifest, f)
        tmp = f.name
    try:
        result = subprocess.run(['kubectl', 'apply', '-f', tmp],
                                capture_output=True, text=True, check=True)
        logger.info(f"kubectl apply: {result.stdout.strip()}")
        return {
            "apiVersion": manifest.get("apiVersion"),
            "kind": manifest.get("kind"),
            "metadata": manifest.get("metadata"),
            "spec": manifest.get("spec"),
        }
    except subprocess.CalledProcessError as e:
        logger.error(f"kubectl apply failed: {e.stderr}")
        return {"error": e.stderr, "manifest": manifest}
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass


def _delete_chaos_crd(kind: str, name: str, namespace: str) -> dict:
    """Delete a Chaos Mesh CRD resource via kubectl."""
    import subprocess
    resource_map = {
        "NetworkChaos": "networkchaos",
        "DNSChaos": "dnschaos",
        "HTTPChaos": "httpchaos",
        "IOChaos": "iochaos",
        "TimeChaos": "timechaos",
        "KernelChaos": "kernelchaos",
    }
    crd = resource_map.get(kind, kind.lower())
    try:
        result = subprocess.run(
            ['kubectl', 'delete', crd, name, '-n', namespace, '--ignore-not-found'],
            capture_output=True, text=True, check=True)
        return {"status": "deleted", "kind": kind, "name": name, "namespace": namespace}
    except subprocess.CalledProcessError as e:
        return {"error": e.stderr}


def _gen_name(prefix: str) -> str:
    return f"{prefix}-{str(uuid.uuid4())[:8]}"


def _selector_spec(service: str, namespace: str) -> dict:
    return {
        "namespaces": [namespace],
        "labelSelectors": {"app": service},
    }


# ─────────────────────────────────────────────────────────────────────────────
# NetworkChaos – delay / loss / corrupt / duplicate
# ─────────────────────────────────────────────────────────────────────────────

def network_delay(service: str, namespace: str = "default",
                  duration: str = "1m", mode: str = "all", value: str = "",
                  latency: str = "100ms", jitter: str = "0ms", correlation: str = "0",
                  direction: str = "to", external_targets: list = None) -> dict:
    spec = {
        "selector": _selector_spec(service, namespace),
        "mode": mode,
        "action": "delay",
        "duration": duration,
        "delay": {"latency": latency, "jitter": jitter, "correlation": correlation},
        "direction": direction,
    }
    if mode in ("fixed", "fixed-percent", "random-max-percent"):
        spec["value"] = value
    if external_targets:
        spec["externalTargets"] = external_targets
    manifest = {
        "apiVersion": "chaos-mesh.org/v1alpha1",
        "kind": "NetworkChaos",
        "metadata": {"name": _gen_name("net-delay"), "namespace": namespace},
        "spec": spec,
    }
    return _apply_chaos_crd(manifest)


def network_loss(service: str, namespace: str = "default",
                 duration: str = "1m", mode: str = "all", value: str = "",
                 loss: str = "50", correlation: str = "0",
                 direction: str = "to", external_targets: list = None) -> dict:
    spec = {
        "selector": _selector_spec(service, namespace),
        "mode": mode,
        "action": "loss",
        "duration": duration,
        "loss": {"loss": loss, "correlation": correlation},
        "direction": direction,
    }
    if mode in ("fixed", "fixed-percent", "random-max-percent"):
        spec["value"] = value
    if external_targets:
        spec["externalTargets"] = external_targets
    manifest = {
        "apiVersion": "chaos-mesh.org/v1alpha1",
        "kind": "NetworkChaos",
        "metadata": {"name": _gen_name("net-loss"), "namespace": namespace},
        "spec": spec,
    }
    return _apply_chaos_crd(manifest)


def network_corrupt(service: str, namespace: str = "default",
                    duration: str = "1m", mode: str = "all", value: str = "",
                    corrupt: str = "50", correlation: str = "0",
                    direction: str = "to", external_targets: list = None) -> dict:
    spec = {
        "selector": _selector_spec(service, namespace),
        "mode": mode,
        "action": "corrupt",
        "duration": duration,
        "corrupt": {"corrupt": corrupt, "correlation": correlation},
        "direction": direction,
    }
    if mode in ("fixed", "fixed-percent", "random-max-percent"):
        spec["value"] = value
    if external_targets:
        spec["externalTargets"] = external_targets
    manifest = {
        "apiVersion": "chaos-mesh.org/v1alpha1",
        "kind": "NetworkChaos",
        "metadata": {"name": _gen_name("net-corrupt"), "namespace": namespace},
        "spec": spec,
    }
    return _apply_chaos_crd(manifest)


def network_duplicate(service: str, namespace: str = "default",
                      duration: str = "1m", mode: str = "all", value: str = "",
                      duplicate: str = "50", correlation: str = "0",
                      direction: str = "to", external_targets: list = None) -> dict:
    spec = {
        "selector": _selector_spec(service, namespace),
        "mode": mode,
        "action": "duplicate",
        "duration": duration,
        "duplicate": {"duplicate": duplicate, "correlation": correlation},
        "direction": direction,
    }
    if mode in ("fixed", "fixed-percent", "random-max-percent"):
        spec["value"] = value
    if external_targets:
        spec["externalTargets"] = external_targets
    manifest = {
        "apiVersion": "chaos-mesh.org/v1alpha1",
        "kind": "NetworkChaos",
        "metadata": {"name": _gen_name("net-dup"), "namespace": namespace},
        "spec": spec,
    }
    return _apply_chaos_crd(manifest)


# ─────────────────────────────────────────────────────────────────────────────
# DNSChaos
# ─────────────────────────────────────────────────────────────────────────────

def dns_chaos(service: str, namespace: str = "default",
              duration: str = "1m", mode: str = "all", value: str = "",
              action: str = "error", scope: str = "outer",
              patterns: list = None) -> dict:
    """
    action: 'error' (DNS解析失败) | 'random' (返回随机IP)
    scope: 'outer' | 'inner' | 'all'
    patterns: list of domain patterns, e.g. ["*.google.com", "github.com"]
    """
    spec = {
        "selector": _selector_spec(service, namespace),
        "mode": mode,
        "action": action,
        "duration": duration,
    }
    if mode in ("fixed", "fixed-percent", "random-max-percent"):
        spec["value"] = value
    if patterns:
        spec["patterns"] = patterns
    # Note: scope field not supported by current Chaos Mesh CRD version
    manifest = {
        "apiVersion": "chaos-mesh.org/v1alpha1",
        "kind": "DNSChaos",
        "metadata": {"name": _gen_name("dns"), "namespace": namespace},
        "spec": spec,
    }
    return _apply_chaos_crd(manifest)


# ─────────────────────────────────────────────────────────────────────────────
# HTTPChaos
# ─────────────────────────────────────────────────────────────────────────────

def http_chaos(service: str, namespace: str = "default",
               duration: str = "1m", mode: str = "all", value: str = "",
               target: str = "Request", port: int = 80,
               action: str = "delay",
               delay: str = "1s",
               abort: bool = False,
               replace: dict = None,
               patch: dict = None,
               path: str = "*", method: str = None,
               code: int = None) -> dict:
    """
    action: 'delay' | 'abort' | 'replace' | 'patch'
    target: 'Request' | 'Response'
    """
    spec = {
        "selector": _selector_spec(service, namespace),
        "mode": mode,
        "target": target,
        "port": port,
        "duration": duration,
    }
    if mode in ("fixed", "fixed-percent", "random-max-percent"):
        spec["value"] = value
    if path and path != "*":
        spec["path"] = path
    if method:
        spec["method"] = method
    if code:
        spec["code"] = code

    if action == "delay":
        spec["delay"] = delay
    elif action == "abort":
        spec["abort"] = True
    elif action == "replace" and replace:
        spec["replace"] = replace
    elif action == "patch" and patch:
        spec["patch"] = patch

    manifest = {
        "apiVersion": "chaos-mesh.org/v1alpha1",
        "kind": "HTTPChaos",
        "metadata": {"name": _gen_name("http"), "namespace": namespace},
        "spec": spec,
    }
    return _apply_chaos_crd(manifest)


# ─────────────────────────────────────────────────────────────────────────────
# IOChaos
# ─────────────────────────────────────────────────────────────────────────────

def io_chaos(service: str, namespace: str = "default",
             duration: str = "1m", mode: str = "all", value: str = "",
             action: str = "latency",
             volume_path: str = "/",
             path: str = "**/*",
             delay: str = "100ms",
             errno: int = None,
             percent: int = 100,
             container_names: list = None) -> dict:
    """
    action: 'latency' | 'fault' | 'attrOverride' | 'mistake'
    """
    spec = {
        "selector": _selector_spec(service, namespace),
        "mode": mode,
        "action": action,
        "duration": duration,
        "volumePath": volume_path,
        "path": path,
        "percent": percent,
    }
    if mode in ("fixed", "fixed-percent", "random-max-percent"):
        spec["value"] = value
    if container_names:
        spec["containerNames"] = container_names
    if action == "latency":
        spec["delay"] = delay
    elif action == "fault" and errno:
        spec["errno"] = errno

    manifest = {
        "apiVersion": "chaos-mesh.org/v1alpha1",
        "kind": "IOChaos",
        "metadata": {"name": _gen_name("io"), "namespace": namespace},
        "spec": spec,
    }
    return _apply_chaos_crd(manifest)


# ─────────────────────────────────────────────────────────────────────────────
# TimeChaos
# ─────────────────────────────────────────────────────────────────────────────

def time_chaos(service: str, namespace: str = "default",
               duration: str = "1m", mode: str = "all", value: str = "",
               time_offset: str = "-5m",
               container_names: list = None) -> dict:
    """
    time_offset: e.g. '+5m30s', '-1h', '100ms'
    """
    spec = {
        "selector": _selector_spec(service, namespace),
        "mode": mode,
        "duration": duration,
        "timeOffset": time_offset,
    }
    if mode in ("fixed", "fixed-percent", "random-max-percent"):
        spec["value"] = value
    if container_names:
        spec["containerNames"] = container_names

    manifest = {
        "apiVersion": "chaos-mesh.org/v1alpha1",
        "kind": "TimeChaos",
        "metadata": {"name": _gen_name("time"), "namespace": namespace},
        "spec": spec,
    }
    return _apply_chaos_crd(manifest)


# ─────────────────────────────────────────────────────────────────────────────
# KernelChaos
# ─────────────────────────────────────────────────────────────────────────────

def kernel_chaos(service: str, namespace: str = "default",
                 duration: str = "1m", mode: str = "all", value: str = "",
                 fail_kern_request: dict = None) -> dict:
    """
    fail_kern_request example:
    {
        "callchain": [{"funcname": "alloc_pages"}],
        "failtype": 0,   # 0=slab, 1=page, 2=bio
        "headers": ["BIO_QUEUE"],
        "probability": 1,
        "times": 1
    }
    """
    if fail_kern_request is None:
        fail_kern_request = {
            "callchain": [{"funcname": "alloc_pages"}],
            "failtype": 0,
            "probability": 1,
            "times": 1,
        }
    spec = {
        "selector": _selector_spec(service, namespace),
        "mode": mode,
        "duration": duration,
        "failKernRequest": fail_kern_request,
    }
    if mode in ("fixed", "fixed-percent", "random-max-percent"):
        spec["value"] = value

    manifest = {
        "apiVersion": "chaos-mesh.org/v1alpha1",
        "kind": "KernelChaos",
        "metadata": {"name": _gen_name("kernel"), "namespace": namespace},
        "spec": spec,
    }
    return _apply_chaos_crd(manifest)
