# 监控

Prometheus 是一个[毕业的 CNCF 项目](https://www.cncf.io/projects/)，它无疑是与 Kubernetes 原生集成的最流行的监控系统。Prometheus 收集有关容器、Pod、节点和集群的指标。此外，Prometheus 利用 AlertsManager，让您可以编程警报，以便在集群中出现问题时警告您。Prometheus 将指标数据存储为由指标名称和键/值对标识的时间序列数据。Prometheus 包括一种使用名为 PromQL 的语言进行查询的方式，这是 Prometheus 查询语言的缩写。

Prometheus 指标收集的高级架构如下所示:

![Prometheus Metrics collection](./images/prom.png)

Prometheus 使用拉取机制，并通过导出器从目标抓取指标，并使用 [kube state metrics](https://github.com/kubernetes/kube-state-metrics) 从 Kubernetes API 抓取指标。这意味着应用程序和服务必须公开包含 Prometheus 格式化指标的 HTTP(S) 端点。然后，Prometheus 将根据其配置，定期从这些 HTTP(S) 端点拉取指标。

导出器允许您将第三方指标作为 Prometheus 格式化指标进行消费。Prometheus 导出器通常部署在每个节点上。有关导出器的完整列表，请参阅 Prometheus [exporters](https://prometheus.io/docs/instrumenting/exporters/)。虽然 [node exporter](https://github.com/prometheus/node_exporter) 适合导出 Linux 节点的主机硬件和操作系统指标，但它不适用于 Windows 节点。

在使用稳定的 [Prometheus helm chart](https://github.com/prometheus-community/helm-charts) 的 **混合节点 EKS 集群中包含 Windows 节点**时，您将在 Windows 节点上看到失败的 Pod，因为此导出器不适用于 Windows。您需要单独处理 Windows 工作节点池，而是在 Windows 工作节点组上安装 [Windows exporter](https://github.com/prometheus-community/windows_exporter)。

为了在 Windows 节点上设置 Prometheus 监控，您需要在 Windows 服务器本身上下载并安装 WMI 导出器，然后在 Prometheus 配置文件的抓取配置中设置目标。
[发布页面](https://github.com/prometheus-community/windows_exporter/releases)提供了所有可用的 .msi 安装程序，包括各自的功能集和错误修复。安装程序将把 windows_exporter 设置为 Windows 服务，并在 Windows 防火墙中创建一个例外。如果在不带任何参数的情况下运行安装程序，导出器将使用默认设置运行，包括启用的收集器、端口等。

您可以查看本指南的**调度最佳实践**部分，其中建议使用污点/容忍度或 RuntimeClass 来选择性地仅将节点导出器部署到 Linux 节点，而在引导节点或使用您选择的配置管理工具(例如 chef、Ansible、SSM 等)时，Windows 导出器将安装在 Windows 节点上。

请注意，与作为 daemonset 安装在 Linux 节点上的节点导出器不同，在 Windows 节点上，WMI 导出器安装在主机本身上。导出器将导出诸如 CPU 使用率、内存和磁盘 I/O 使用率等指标，还可用于监控 IIS 站点和应用程序、网络接口和服务。

windows_exporter 将默认公开所有启用的收集器的指标。这是收集指标的推荐方式，以避免错误。但是，对于高级用途，windows_exporter 可以传递一个可选的收集器列表来过滤指标。Prometheus 配置中的 collect[] 参数可以让您这样做。

Windows 的默认安装步骤包括在引导过程中下载并启动导出器作为服务，并带有参数，例如您要过滤的收集器。

```powershell
> Powershell Invoke-WebRequest https://github.com/prometheus-community/windows_exporter/releases/download/v0.13.0/windows_exporter-0.13.0-amd64.msi -OutFile <DOWNLOADPATH>

> msiexec /i <DOWNLOADPATH> ENABLED_COLLECTORS="cpu,cs,logical_disk,net,os,system,container,memory"
```

默认情况下，可以在端口9182的/metrics端点上抓取指标。
此时，Prometheus可以通过在Prometheus配置中添加以下scrape_config来消费指标

```yaml
scrape_configs:
    - job_name: "prometheus"
      static_configs:
        - targets: ['localhost:9090']
    ...
    - job_name: "wmi_exporter"
      scrape_interval: 10s
      static_configs:
        - targets: ['<windows-node1-ip>:9182', '<windows-node2-ip>:9182', ...]
```

使用以下命令重新加载Prometheus配置

```bash

> ps aux | grep prometheus
> kill HUP <PID>

```

添加目标的更好和推荐的方式是使用名为ServiceMonitor的自定义资源定义，它作为[Prometheus operator](https://github.com/prometheus-operator/kube-prometheus/releases)]的一部分提供了ServiceMonitor对象的定义和一个控制器，该控制器将激活我们定义的ServiceMonitor并自动构建所需的Prometheus配置。

ServiceMonitor声明性地指定了应该如何监控Kubernetes服务组，用于在Kubernetes内定义您希望从中抓取指标的应用程序。在ServiceMonitor中，我们指定了操作员可以用来识别Kubernetes服务的Kubernetes标签，而该服务又识别了我们希望监控的Pod。

为了利用ServiceMonitor，请创建一个指向特定Windows目标的Endpoint对象、一个无头服务和Windows节点的ServiceMontor。

```yaml
apiVersion: v1
kind: Endpoints
metadata:
  labels:
    k8s-app: wmiexporter
  name: wmiexporter
  namespace: kube-system
subsets:
- addresses:
  - ip: NODE-ONE-IP
    targetRef:
      kind: Node
      name: NODE-ONE-NAME
  - ip: NODE-TWO-IP
    targetRef:
      kind: Node
      name: NODE-TWO-NAME
  - ip: NODE-THREE-IP
    targetRef:
      kind: Node
      name: NODE-THREE-NAME
  ports:
  - name: http-metrics
    port: 9182
    protocol: TCP

---
apiVersion: v1
kind: Service ##无头服务
metadata:
  labels:
    k8s-app: wmiexporter
  name: wmiexporter
  namespace: kube-system
spec:
  clusterIP: None
  ports:
  - name: http-metrics
    port: 9182
    protocol: TCP
    targetPort: 9182
  sessionAffinity: None
  type: ClusterIP
  
---
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor ##自定义ServiceMonitor对象
metadata:
  labels:
    k8s-app: wmiexporter
  name: wmiexporter
  namespace: monitoring
spec:
  endpoints:
  - interval: 30s
    port: http-metrics
  jobLabel: k8s-app
  namespaceSelector:
    matchNames:
    - kube-system
  selector:
    matchLabels:
      k8s-app: wmiexporter
```

有关该操作符和ServiceMonitor的使用的更多详细信息，请查看官方[操作符](https://github.com/prometheus-operator/kube-prometheus)文档。请注意，Prometheus支持使用许多[服务发现](https://prometheus.io/blog/2015/06/01/advanced-service-discovery/)选项进行动态目标发现。