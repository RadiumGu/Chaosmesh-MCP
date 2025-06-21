# MCP Server

MCP Server is a tool for injecting faults and performing stress tests on Kubernetes pods and hosts using `Chaos Mesh`. It also provides utilities for retrieving logs and monitoring load test results.

## Features

- **Pod Fault Injection**: Simulate pod failures, pod kills, and container kills.
- **Pod Stress Testing**: Simulate CPU and memory stress tests on pods.
- **Host Stress Testing**: Simulate CPU and memory stress tests on hosts.
- **Host Disk Faults**: Simulate disk fill, read payload, and write payload faults on hosts.
- **Network Faults**: Simulate network partition and bandwidth limitations.
- **Log Retrieval**: Retrieve logs for specific services and containers.
- **Load Test Monitoring**: Parse and retrieve aggregated load test results.

## Project Structure

- `fault_inject.py`: Contains functions for injecting faults and performing stress tests.
- `kube.py`: Provides utilities for interacting with Kubernetes, such as retrieving pod logs.
- `server.py`: Implements the MCP server and exposes tools for fault injection and log retrieval.
- `test.py`: Contains test cases and examples for using the fault injection and logging utilities.
- `services.json`: Defines the services in the cluster, including their namespaces, labels, and containers.

## Installation

### Prerequisites:

Before starting, make sure you have `chaosmesh` installed. You can install `chaosmesh` [here](https://chaos-mesh.org/docs/production-installation-using-helm/) .
Before starting, make sure you have `uv` installed. You can install `uv` [here](https://docs.astral.sh/uv/getting-started/installation/) .


### 1. Clone the repository:

```bash
git clone https://github.com/RadiumGu/Chaosmesh-MCP.git
cd mcp_server
```

### 2. Build and set up the virtual environment using `uv`:

```bash
uv venv
source .venv/bin/activate
```

### 3. Install dependencies:

```bash
uv sync
```

### 4. Install `Chaos Mesh` in your Kubernetes cluster.

You can intall it [here](https://chaos-mesh.org/docs/production-installation-using-helm/).

## Usage

Run the MCP server using the following command:

```bash
uv run python server.py
```

You can specify the transport method by adding the `--transport` argument. By default, the `transport` parameter is set to `stdio`.

## Service Infomation

Write the `services.json` file to show the services in your cluster. You can write anything useful, the more detailed the better.
