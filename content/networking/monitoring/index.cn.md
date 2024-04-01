# 监控 EKS 工作负载的网络性能问题

## 监控 CoreDNS 流量以检测 DNS 节流问题

运行 DNS 密集型工作负载有时会由于 DNS 节流而遇到间歇性的 CoreDNS 故障，这可能会影响应用程序，您可能会遇到偶尔的 UnknownHostException 错误。

CoreDNS 的 Deployment 具有反亲和性策略，该策略指示 Kubernetes 调度程序在集群中的单独工作节点上运行 CoreDNS 实例，即它应该避免在同一工作节点上共存副本。这有效地减少了每个网络接口的 DNS 查询数量，因为来自每个副本的流量都通过不同的 ENI 路由。如果您注意到由于每秒 1024 个数据包的限制而导致 DNS 查询被节流，您可以 1) 尝试增加 CoreDNS 副本的数量或 2) 实现 [NodeLocal DNSCache](https://kubernetes.io/docs/tasks/administer-cluster/nodelocaldns/)。有关更多信息，请参阅 [监控 CoreDNS 指标](https://aws.github.io/aws-eks-best-practices/reliability/docs/dataplane/#monitor-coredns-metrics)。

### 挑战
* 数据包丢弃发生在几秒钟内，很难监控这些模式以确定是否实际发生了 DNS 节流。
* DNS 查询在弹性网络接口级别被节流。因此，节流的查询不会出现在查询日志中。
* 流日志不会捕获所有 IP 流量。例如，实例联系 Amazon DNS 服务器时生成的流量。如果您使用自己的 DNS 服务器，则会记录到该 DNS 服务器的所有流量

### 解决方案
识别工作节点中DNS节流问题的一种简单方法是捕获`linklocal_allowance_exceeded`指标。[linklocal_allowance_exceeded](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/metrics-collected-by-CloudWatch-agent.html#linux-metrics-enabled-by-CloudWatch-agent)是因为到本地代理服务的流量PPS超过网络接口的最大值而被丢弃的数据包数量。这会影响到DNS服务、实例元数据服务和Amazon时间同步服务的流量。我们不仅可以实时跟踪此事件，还可以将此指标流式传输到[Amazon Managed Service for Prometheus](https://aws.amazon.com/prometheus/),并在[Amazon Managed Grafana](https://aws.amazon.com/grafana/)中将其可视化

## 使用Conntrack指标监控DNS查询延迟

另一个可以帮助监控CoreDNS节流/查询延迟的指标是`conntrack_allowance_available`和`conntrack_allowance_exceeded`。
由于超出连接跟踪限制而导致的连接失败可能会产生比超出其他限制更大的影响。当依赖TCP传输数据时，由于TCP的拥塞控制功能，由于超出EC2实例网络限制(如带宽、PPS等)而导致的排队或丢弃数据包通常会被优雅地处理。受影响的流量将被减慢，丢失的数据包将被重新传输。但是，当实例超出其连接跟踪限制时，在关闭一些现有连接以腾出空间供新连接使用之前，将无法建立新连接。

`conntrack_allowance_available` 和 `conntrack_allowance_exceeded` 可帮助客户监控每个实例的连接跟踪允许值，这个值因实例而异。这些网络性能指标让客户了解当实例的网络带宽、每秒数据包数 (PPS)、连接跟踪数以及链路本地服务访问 (Amazon DNS、实例元数据服务、Amazon 时间同步) 等网络允许值被超过时，有多少数据包被排队或丢弃。

`conntrack_allowance_available` 是指实例在达到该实例类型的连接跟踪允许值之前可以建立的跟踪连接数 (仅支持基于 nitro 的实例)。
`conntrack_allowance_exceeded` 是指由于连接跟踪超过实例的最大值而被丢弃的数据包数量，无法建立新连接。

## 其他重要的网络性能指标

其他重要的网络性能指标包括:

`bw_in_allowance_exceeded` (该指标的理想值应为零) 是指由于入站总带宽超过实例的最大值而被排队和/或丢弃的数据包数量

`bw_out_allowance_exceeded` (该指标的理想值应为零) 是指由于出站总带宽超过实例的最大值而被排队和/或丢弃的数据包数量

`pps_allowance_exceeded` (该指标的理想值应为零) 是指由于双向 PPS 超过实例的最大值而被排队和/或丢弃的数据包数量

## 捕获指标以监控网络性能问题

Elastic Network Adapter (ENA) 驱动程序会从启用了该功能的实例中发布上述网络性能指标。所有网络性能指标都可以使用 CloudWatch 代理发布到 CloudWatch。有关更多信息，请参阅[博客](https://aws.amazon.com/blogs/networking-and-content-delivery/amazon-ec2-instance-level-network-performance-metrics-uncover-new-insights/)。

现在让我们捕获上述指标，将它们存储在 Amazon Managed Service for Prometheus 中并使用 Amazon Managed Grafana 进行可视化

### 先决条件
* ethtool - 确保工作节点已安装 ethtool
* 在您的 AWS 账户中配置了 AMP 工作区。有关说明，请参阅 AMP 用户指南中的[创建工作区](https://docs.aws.amazon.com/prometheus/latest/userguide/AMP-onboard-create-workspace.html)。
* Amazon Managed Grafana 工作区

### 部署 Prometheus ethtool 导出器
该部署包含一个 python 脚本，用于从 ethtool 中提取信息并以 prometheus 格式发布。

```
kubectl apply -f https://raw.githubusercontent.com/Showmax/prometheus-ethtool-exporter/master/deploy/k8s-daemonset.yaml
```

### 部署 ADOT 收集器以抓取 ethtool 指标并将其存储在 Amazon Managed Service for Prometheus 工作区中
在每个安装了 AWS Distro for OpenTelemetry (ADOT) 的集群中，您都必须具有此角色，以授予您的 AWS 服务账户将指标存储到 Amazon Managed Service for Prometheus 的权限。按照以下步骤使用 IRSA 创建并将您的 IAM 角色关联到您的 Amazon EKS 服务账户:

```
eksctl create iamserviceaccount --name adot-collector --namespace default --cluster <CLUSTER_NAME> --attach-policy-arn arn:aws:iam::aws:policy/AmazonPrometheusRemoteWriteAccess --attach-policy-arn arn:aws:iam::aws:policy/AWSXrayWriteOnlyAccess --attach-policy-arn arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy --region <REGION> --approve  --override-existing-serviceaccounts
```

让我们部署 ADOT 收集器来从 Prometheus ethtool 导出器中抓取指标并将其存储在 Amazon Managed Service for Prometheus 中

以下过程使用了一个示例 YAML 文件，其中 mode 值为 deployment。这是默认模式，并将 ADOT 收集器部署为独立应用程序。此配置从示例应用程序接收 OTLP 指标，并从集群上的 pod 中抓取 Amazon Managed Service for Prometheus 指标

```
curl -o collector-config-amp.yaml https://raw.githubusercontent.com/aws-observability/aws-otel-community/master/sample-configs/operator/collector-config-amp.yaml
```

在 collector-config-amp.yaml 中，将以下内容替换为您自己的值：
* mode: deployment
* serviceAccount: adot-collector
* endpoint: "<YOUR_REMOTE_WRITE_ENDPOINT>"
* region: "<YOUR_AWS_REGION>"
* name: adot-collector

```
kubectl apply -f collector-config-amp.yaml 
```

一旦 adot 收集器部署完成，指标将成功存储在 Amazon Prometheus 中

### 在 Amazon Managed Service for Prometheus 中配置警报管理器以发送通知
让我们配置记录规则和警报规则来检查到目前为止讨论过的指标。

我们将使用 [ACK Controller for Amazon Managed Service for Prometheus](https://github.com/aws-controllers-k8s/prometheusservice-controller) 来设置警报和记录规则。

让我们为Amazon Managed Service for Prometheus服务部署ACL控制器:

```
export SERVICE=prometheusservice
export RELEASE_VERSION=`curl -sL https://api.github.com/repos/aws-controllers-k8s/$SERVICE-controller/releases/latest | grep '"tag_name":' | cut -d'"' -f4`
export ACK_SYSTEM_NAMESPACE=ack-system
export AWS_REGION=us-east-1
aws ecr-public get-login-password --region us-east-1 | helm registry login --username AWS --password-stdin public.ecr.aws
helm install --create-namespace -n $ACK_SYSTEM_NAMESPACE ack-$SERVICE-controller \
oci://public.ecr.aws/aws-controllers-k8s/$SERVICE-chart --version=$RELEASE_VERSION --set=aws.region=$AWS_REGION
```

运行该命令后，片刻之后您应该会看到以下消息:

```
You are now able to create Amazon Managed Service for Prometheus (AMP) resources!

The controller is running in "cluster" mode.

The controller is configured to manage AWS resources in region: "us-east-1"

The ACK controller has been successfully installed and ACK can now be used to provision an Amazon Managed Service for Prometheus workspace.
```

现在让我们创建一个yaml文件来设置警报管理器定义和规则组。
将下面的内容保存为 `rulegroup.yaml`

```
apiVersion: prometheusservice.services.k8s.aws/v1alpha1
kind: RuleGroupsNamespace
metadata:
   name: default-rule
spec:
   workspaceID: <您的工作区ID>
   name: default-rule
   configuration: |
     groups:
     - name: ppsallowance
       rules:
       - record: metric:pps_allowance_exceeded
         expr: rate(node_net_ethtool{device="eth0",type="pps_allowance_exceeded"}[30s])
       - alert: PPSAllowanceExceeded
         expr: rate(node_net_ethtool{device="eth0",type="pps_allowance_exceeded"} [30s]) > 0
         labels:
           severity: critical
           
         annotations:
           summary: 由于总允许值超出而导致连接被丢弃 (实例 {{ $labels.instance }})
           description: "PPSAllowanceExceeded大于0"
     - name: bw_in
       rules:
       - record: metric:bw_in_allowance_exceeded
         expr: rate(node_net_ethtool{device="eth0",type="bw_in_allowance_exceeded"}[30s])
       - alert: BWINAllowanceExceeded
         expr: rate(node_net_ethtool{device="eth0",type="bw_in_allowance_exceeded"} [30s]) > 0
         labels:
           severity: critical
           
         annotations:
           summary: 由于总允许值超出而导致连接被丢弃 (实例 {{ $labels.instance }})
           description: "BWInAllowanceExceeded大于0"
     - name: bw_out
       rules:
       - record: metric:bw_out_allowance_exceeded
         expr: rate(node_net_ethtool{device="eth0",type="bw_out_allowance_exceeded"}[30s])
       - alert: BWOutAllowanceExceeded
         expr: rate(node_net_ethtool{device="eth0",type="bw_out_allowance_exceeded"} [30s]) > 0
         labels:
           severity: critical
           
         annotations:
           summary: 由于总允许值超出而导致连接被丢弃 (实例 {{ $labels.instance }})
           description: "BWoutAllowanceExceeded大于0"            
     - name: conntrack
       rules:
       - record: metric:conntrack_allowance_exceeded
         expr: rate(node_net_ethtool{device="eth0",type="conntrack_allowance_exceeded"}[30s])
       - alert: ConntrackAllowanceExceeded
         expr: rate(node_net_ethtool{device="eth0",type="conntrack_allowance_exceeded"} [30s]) > 0
         labels:
           severity: critical
           
         annotations:
           summary: 由于总允许值超出而导致连接被丢弃 (实例 {{ $labels.instance }})
           description: "ConnTrackAllowanceExceeded大于0"
     - name: linklocal
       rules:
       - record: metric:linklocal_allowance_exceeded
         expr: rate(node_net_ethtool{device="eth0",type="linklocal_allowance_exceeded"}[30s])
       - alert: LinkLocalAllowanceExceeded
         expr: rate(node_net_ethtool{device="eth0",type="linklocal_allowance_exceeded"} [30s]) > 0
         labels:
           severity: critical
           
         annotations:
           summary: 由于PPS速率允许值超出而导致本地服务的数据包被丢弃 (实例 {{ $labels.instance }})
           description: "LinkLocalAllowanceExceeded大于0"
```

将 WORKSPACE-ID 替换为您正在使用的工作区的工作区 ID。

现在让我们配置警报管理器定义。将下面的文件保存为 `alertmanager.yaml`

```
apiVersion: prometheusservice.services.k8s.aws/v1alpha1  
kind: AlertManagerDefinition
metadata:
  name: alert-manager
spec:
  workspaceID: <您的 WORKSPACE-ID >
  configuration: |
    alertmanager_config: |
      route:
         receiver: default_receiver
       receivers:
       - name: default_receiver
          sns_configs:
          - topic_arn: TOPIC-ARN
            sigv4:
              region: REGION
            message: |
              alert_type: {{ .CommonLabels.alertname }}
              event_type: {{ .CommonLabels.event_type }}     
```

将 WORKSPACE-ID 替换为新工作区的工作区 ID，将 TOPIC-ARN 替换为您希望发送警报的 [Amazon Simple Notification Service](https://aws.amazon.com/sns/) 主题的 ARN，将 REGION 替换为当前工作负载所在的区域。请确保您的工作区有权限向 Amazon SNS 发送消息。

### 在 Amazon Managed Grafana 中可视化 ethtool 指标
让我们在 Amazon Managed Grafana 中可视化指标并构建一个仪表板。按照 [将 Amazon Prometheus 添加为数据源](https://docs.aws.amazon.com/grafana/latest/userguide/AMP-adding-AWS-config.html) 中的说明，将 Amazon Managed Service for Prometheus 配置为 Amazon Managed Grafana 控制台中的数据源。

现在让我们在 Amazon Managed Grafana 中探索指标:
单击探索按钮，搜索 ethtool:

![Node_ethtool metrics](./explore_metrics.png)

让我们使用查询 `rate(node_net_ethtool{device="eth0",type="linklocal_allowance_exceeded"}[30s])` 为 linklocal_allowance_exceeded 指标构建一个仪表板。它将产生如下仪表板。

![linklocal_allowance_exceeded dashboard](./linklocal.png)

我们可以清楚地看到没有丢弃任何数据包，因为该值为零。

让我们使用查询 `rate(node_net_ethtool{device="eth0",type="conntrack_allowance_exceeded"}[30s])` 为 conntrack_allowance_exceeded 指标构建一个仪表板。它将产生如下仪表板。

![conntrack_allowance_exceeded 仪表板](./conntrack.png)

只要按照[这里](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch-Agent-network-performance.html)所述运行 cloudwatch 代理，就可以在 CloudWatch 中可视化 `conntrack_allowance_exceeded` 指标。在 CloudWatch 中的结果仪表板如下所示:

![CW_NW_Performance](./cw_metrics.png)

我们可以清楚地看到，值为零，没有丢弃任何数据包。如果您使用基于 Nitro 的实例，您可以为 `conntrack_allowance_available` 创建类似的仪表板，并主动监控您的 EC2 实例中的连接。您可以进一步扩展这一功能，在 Amazon Managed Grafana 中配置警报，以向 Slack、SNS、Pagerduty 等发送通知。