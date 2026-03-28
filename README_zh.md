[English](README.md) | 中文

# Chaos Mesh MCP Server

基于 Model Context Protocol (MCP) 的 Chaos Mesh 故障注入服务器，针对 AWS EKS 环境优化，支持全命名空间操作。

## 功能特性

- **Pod 故障注入**：Kill Pod、注入故障、CPU/内存压力测试
- **网络混沌**：模拟网络延迟、分区、带宽限制
- **主机级混沌**：节点 CPU/内存压力、磁盘操作
- **EKS 优化**：针对 AWS EKS 的 RBAC 和认证增强支持
- **命名空间支持**：所有工具支持自定义命名空间
- **完善的错误处理**：详细错误信息和重试机制
- **健康监控**：内置健康检查和诊断

---

## EKS 认证方式

MCP Server 连接 EKS 集群有以下两种认证方式：

### 方式一：静态 ServiceAccount Token（推荐）

通过运行 setup 脚本生成，产出一个包含长期 ServiceAccount Token 的独立 kubeconfig 文件。**运行时不依赖 AWS CLI 或 IAM 凭证。**

```bash
# 一次性执行：创建 RBAC + 生成 kubeconfig
./setup-eks-permissions.sh

# 用生成的 kubeconfig 启动 MCP Server
python server.py --kubeconfig ./chaos-mesh-mcp-kubeconfig
```

**优点：** 可移植、运行时无 AWS 依赖、权限最小化（仅 Chaos Mesh 相关）

**缺点：** Token 有固定有效期（默认 1 年），到期需重新生成

---

### 方式二：管理员 kubeconfig（exec 认证）

如果集群管理员直接提供 kubeconfig 文件（通常由 `aws eks update-kubeconfig` 生成），MCP Server 可以直接使用。该格式在每次请求时通过 `aws eks get-token` 获取临时 Token。

```bash
# 用管理员提供的 kubeconfig 启动
python server.py --kubeconfig /path/to/admin-kubeconfig
```

或通过环境变量设置：

```bash
export KUBECONFIG=/path/to/admin-kubeconfig
python server.py
```

**前提条件：**
- MCP Server 所在机器必须安装 `aws` CLI
- 机器必须有有效的 AWS 凭证（IAM Role / `~/.aws/credentials`）
- 该 IAM 身份必须在 EKS 的 `aws-auth` ConfigMap 中有映射

**优点：** 复用已有管理员凭证，无需额外配置

**缺点：** 依赖 AWS CLI + IAM 凭证，权限为 admin 级别（范围过大）

---

> **建议：** 生产环境使用方式一。测试时如管理员可直接提供 kubeconfig，使用方式二更快捷。

---

## 使用 uvx 快速开始（推荐）

### 1. 一次性环境配置

```bash
cd /home/ec2-user/mcp-servers/Chaosmesh-MCP

# 运行 uvx 设置脚本（包含 EKS 权限配置和 kubeconfig 生成）
./setup-uvx.sh
```

脚本会自动完成：
- 安装 Chaos Mesh（如未安装）
- 创建必要的 RBAC 权限
- 生成包含 ServiceAccount 凭证的 `chaos-mesh-mcp-kubeconfig`
- 创建 uvx 环境配置
- 验证配置是否正确

### 2. MCP 配置

添加到 `~/.aws/amazonq/mcp.json`：

```json
{
  "mcpServers": {
    "chaosmesh-mcp": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/RadiumGu/Chaosmesh-MCP.git",
        "chaosmesh-mcp",
        "--kubeconfig",
        "/home/ec2-user/mcp-servers/Chaosmesh-MCP/chaos-mesh-mcp-kubeconfig",
        "--skip-env-check",
        "--transport",
        "stdio"
      ],
      "env": {
        "KUBECONFIG": "/home/ec2-user/mcp-servers/Chaosmesh-MCP/chaos-mesh-mcp-kubeconfig",
        "AWS_REGION": "us-east-2"
      },
      "autoApprove": [],
      "disabled": false,
      "transportType": "stdio"
    }
  }
}
```

### 3. 开始使用

重启 Amazon Q CLI：

```bash
/quit
q chat
```

MCP Server 将通过 uvx 按需自动启动。

---

## 命名空间支持

所有工具均支持指定自定义命名空间：

- `pod_kill(service, duration, mode, value, namespace="default")`
- `pod_failure(service, duration, mode, value, namespace="default")`
- `pod_cpu_stress(service, duration, mode, value, container_names, workers, load, namespace="default")`
- `pod_memory_stress(service, duration, mode, value, container_names, size, time, namespace="default")`
- `container_kill(service, duration, mode, value, container_names, namespace="default")`
- `network_partition(service, mode, value, direction, external_targets, namespace="default")`
- `network_bandwidth(service, mode, value, direction, rate, limit, buffer, external_targets, namespace="default")`
- `delete_experiment(type, name, namespace="default")`
- `inject_delay_fault(service, delay, namespace="default")`
- `remove_delay_fault(service, namespace="default")`

### 新增命名空间管理工具

- `list_namespaces()` — 列出集群中所有命名空间
- `list_services_in_namespace(namespace="default")` — 列出指定命名空间中的服务
- `health_check()` — 系统健康检查

### 使用示例

```python
# 列出所有命名空间
namespaces = list_namespaces()

# 列出 votingapp 命名空间中的服务
services = list_services_in_namespace("votingapp")

# 在 votingapp 命名空间中杀死 50% 的 pods，持续 30 秒
pod_kill(
    service="votingapp",
    duration="30s",
    mode="fixed-percent",
    value="50",
    namespace="votingapp"
)

# 检查系统健康状态
health_status = health_check()
```

---

## 故障排除

### 常见问题

1. **kubeconfig 文件不存在** — 运行 `./setup-uvx.sh` 或 `./setup-eks-permissions.sh`
2. **权限错误** — 确保 AWS 凭证有 EKS 访问权限
3. **连接问题** — 验证 kubectl 是否能访问集群
4. **服务未找到** — 使用 `list_services_in_namespace()` 确认服务名和命名空间

### 查看日志

```bash
# 查看 Chaos Mesh 控制器日志
kubectl logs -n chaos-mesh -l app.kubernetes.io/name=chaos-mesh

# 查看所有命名空间的实验
kubectl get podchaos --all-namespaces
```

---

## 文档

- **[README.md](README.md)** — 英文版
- **[README_zh.md](README_zh.md)** — 本文件（中文版）
- **[EKS-SETUP.md](EKS-SETUP.md)** — EKS 专项配置指南
- **[SETUP.md](SETUP.md)** — 通用安装指南
- **[UVX-USAGE.md](UVX-USAGE.md)** — uvx 使用指南
- **[MIGRATION-TO-UVX.md](MIGRATION-TO-UVX.md)** — 从手动安装迁移到 uvx
