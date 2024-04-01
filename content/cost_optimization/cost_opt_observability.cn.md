---
date: 2023-09-29
authors: 
  - Rachel Leekin
  - Nirmal Mehta
---
# 成本优化 - 可观测性

## 简介

可观测性工具可帮助您高效地检测、修复和调查工作负载。随着您对 EKS 的使用增加，遥测数据的成本自然也会增加。有时，在平衡您的运营需求、衡量对您的业务至关重要的内容以及控制可观测性成本方面，可能会有一些挑战。本指南重点介绍了可观测性三大支柱的成本优化策略:日志、指标和跟踪。这些最佳实践中的每一个都可以独立应用，以适应您组织的优化目标。

## 日志记录

日志记录在监控和排查集群中应用程序的故障时起着至关重要的作用。有几种策略可用于优化日志记录成本。下面列出的最佳实践策略包括检查您的日志保留策略，以实施对保留日志数据时间的细粒度控制、根据重要性将日志数据发送到不同的存储选项，以及利用日志过滤来缩小存储的日志消息类型。有效管理日志遥测数据可以为您的环境节省成本。

## EKS 控制平面

### 优化您的控制平面日志

Kubernetes 控制平面是一组[组件](https://kubernetes.io/docs/concepts/overview/components/#control-plane-components),用于管理集群，这些组件会将不同类型的信息作为日志流发送到 [Amazon CloudWatch](https://aws.amazon.com/cloudwatch/) 中的日志组。虽然启用所有控制平面日志类型都有好处，但您应该了解每个日志中的信息以及存储所有日志遥测数据的相关成本。您需要为从集群发送到 Amazon CloudWatch Logs 的日志支付标准的 [CloudWatch Logs 数据引入和存储成本](https://aws.amazon.com/cloudwatch/pricing/)。在启用它们之前，请评估每个日志流是否必需。

例如，在非生产集群中，可以选择性地启用特定的日志类型，如仅用于分析的 API 服务器日志，之后再将其停用。但对于生产集群，您可能无法重现事件，解决问题需要更多日志信息，因此您可以启用所有日志类型。有关进一步的控制平面成本优化实施细节，请参阅此[博客](https://aws.amazon.com/blogs/containers/understanding-and-cost-optimizing-amazon-eks-control-plane-logs/)文章。

#### 将日志流式传输到 S3

将控制平面日志通过 CloudWatch Logs 订阅流式传输到 S3 是另一种成本优化最佳实践。利用 CloudWatch Logs [订阅](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/Subscriptions.html)允许您选择性地将日志转发到 S3，与无限期保留在 CloudWatch 中相比，这种方式提供了更高的成本效益。例如，对于生产集群，您可以创建一个关键日志组，并利用订阅在 15 天后将这些日志流式传输到 S3。这将确保您可以快速访问日志进行分析，同时通过将日志移至更具成本效益的存储来节省成本。

!!! attention
    截至 2023 年 9 月 5 日，EKS 日志在 Amazon CloudWatch Logs 中被归类为 Vended Logs。Vended Logs 是 AWS 服务代表客户本地发布的特定 AWS 服务日志，可享受批量折扣定价。请访问 [Amazon CloudWatch 定价页面](https://aws.amazon.com/cloudwatch/pricing/)了解有关 Vended Logs 定价的更多信息。

## EKS 数据平面

### 日志保留

Amazon CloudWatch 的默认保留策略是永不过期，无限期保留日志，并产生适用于您所在 AWS 区域的存储成本。为了减少存储成本，您可以根据工作负载要求为每个日志组自定义保留策略。

在开发环境中，较长的保留期可能并不是必需的。但在生产环境中，您可以设置更长的保留策略以满足故障排除、合规性和容量规划要求。例如，如果您在节日高峰季运行电子商务应用程序，系统承受更大负载，可能会出现一些问题，但这些问题可能不会立即显现出来，您将希望设置更长的日志保留期，以便进行详细的故障排查和事后分析。

您可以在AWS CloudWatch控制台或[AWS API](https://docs.aws.amazon.com/cli/latest/reference/logs/put-retention-policy.html)中[配置您的保留期](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/Working-with-log-groups-and-streams.html#SettingLogRetention),持续时间为1天到10年，具体取决于每个日志组。拥有灵活的保留期可以节省日志存储成本，同时也能保留关键日志。

### 日志存储选项

存储是可观察性成本的主要驱动因素，因此优化日志存储策略至关重要。您的策略应与工作负载要求保持一致，同时保持性能和可扩展性。减少存储日志成本的一种策略是利用AWS S3存储桶及其不同的存储层。

#### 直接将日志转发到S3

考虑将不太重要的日志(如开发环境日志)直接转发到S3而不是Cloudwatch。这可以立即影响日志存储成本。一种选择是使用Fluentbit将日志直接转发到S3。您可以在`[OUTPUT]`部分中定义这一点，该部分是FluentBit用于保留容器日志的目标。请在[此处](https://docs.fluentbit.io/manual/pipeline/outputs/s3#worker-support)查看其他配置参数。

```
[OUTPUT]
        Name eks_to_s3
        Match application.* 
        bucket $S3_BUCKET name
        region us-east-2
        store_dir /var/log/fluentbit
        total_file_size 30M
        upload_timeout 3m
```

#### 仅将日志转发到 CloudWatch 以进行短期分析

对于更关键的日志，如生产环境中您可能需要立即对数据执行分析的情况，请考虑将日志转发到 CloudWatch。您可以在 `[OUTPUT]` 部分中定义这一点，该部分是 FluentBit 传输容器日志以进行保留的目标。请在[此处](https://docs.fluentbit.io/manual/pipeline/outputs/cloudwatch)查看其他配置参数。

```
[OUTPUT]
        Name eks_to_cloudwatch_logs
        Match application.*
        region us-east-2
        log_group_name fluent-bit-cloudwatch
        log_stream_prefix from-fluent-bit-
        auto_create_group On
```

但是，这不会立即影响您的成本节省。为了获得额外的节省，您将不得不将这些日志导出到 Amazon S3。

#### 从 CloudWatch 导出到 Amazon S3

为了长期存储Amazon CloudWatch日志，我们建议将您的Amazon EKS CloudWatch日志导出到Amazon简单存储服务(Amazon S3)。您可以通过在[控制台](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/S3ExportTasksConsole.html)或API中创建导出任务，将日志转发到Amazon S3存储桶。完成后，Amazon S3提供了许多选项来进一步降低成本。您可以定义自己的[Amazon S3生命周期规则](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lifecycle-mgmt.html)将日志移动到符合您需求的存储类，或利用[Amazon S3智能分层](https://aws.amazon.com/s3/storage-classes/intelligent-tiering/)存储类，让AWS根据您的使用模式自动将数据移动到长期存储。有关更多详细信息，请参阅此[博客](https://aws.amazon.com/blogs/containers/understanding-and-cost-optimizing-amazon-eks-control-plane-logs/)。例如，对于您的生产环境日志，它们在CloudWatch中保留超过30天后导出到Amazon S3存储桶。如果您需要在以后参考日志，您可以使用Amazon Athena查询Amazon S3存储桶中的数据。

### 减少日志级别

对您的应用程序实践选择性日志记录。您的应用程序和节点默认都会输出日志。对于您的应用程序日志，请调整日志级别以与工作负载和环境的严重性相一致。例如，下面的java应用程序正在输出`INFO`日志，这是典型的默认应用程序配置，并且根据代码可能会导致大量日志数据。


```java hl_lines="7"
import org.apache.log4j.*;

public class LogClass {
   private static org.apache.log4j.Logger log = Logger.getLogger(LogClass.class);
   
   public static void main(String[] args) {
      log.setLevel(Level.INFO);

log.debug("这是一条DEBUG消息，请查看!");
log.info("这是一条INFO消息，这里没什么可看的!");
log.warn("这是一条WARN消息，请调查一下!");
log.error("这是一条ERROR消息，请查看!");
log.fatal("这是一条FATAL消息，请调查一下!");
}
}
```

在开发环境中，将您的日志级别更改为`DEBUG`,这可以帮助您调试问题或在进入生产环境之前捕获潜在问题。

```java
log.setLevel(Level.DEBUG);
```

在生产环境中，考虑将您的日志级别修改为`ERROR`或`FATAL`。这将仅在您的应用程序出现错误时输出日志，减少日志输出并帮助您关注有关应用程序状态的重要数据。


```java
log.setLevel(Level.ERROR);
```

您可以微调各种Kubernetes组件的日志级别。例如，如果您使用[Bottlerocket](https://bottlerocket.dev/)作为您的EKS节点操作系统，有一些配置设置允许您调整kubelet进程的日志级别。下面是此配置设置的一个片段。注意默认[日志级别](https://github.com/bottlerocket-os/bottlerocket/blob/3f716bd68728f7fd825eb45621ada0972d0badbb/README.md?plain=1#L528)为**2**,它调整了`kubelet`进程的日志详细程度。

```toml hl_lines="2"
[settings.kubernetes]
log-level = "2"
image-gc-high-threshold-percent = "85"
image-gc-low-threshold-percent = "80"
```

对于开发环境，您可以将日志级别设置为大于**2**,以便查看更多事件，这对于调试很有用。对于生产环境，您可以将级别设置为**0**,以便仅查看关键事件。

### 利用过滤器

当使用默认的EKS Fluentbit配置将容器日志发送到Cloudwatch时，FluentBit捕获并将**所有**应用程序容器日志(附加了Kubernetes元数据)发送到Cloudwatch，如下所示`[INPUT]`配置块。

```
    [INPUT]
        Name                tail
        Tag                 application.*
        Exclude_Path        /var/log/containers/cloudwatch-agent*, /var/log/containers/fluent-bit*, /var/log/containers/aws-node*, /var/log/containers/kube-proxy*
        Path                /var/log/containers/*.log
        Docker_Mode         On
        Docker_Mode_Flush   5
        Docker_Mode_Parser  container_firstline
        Parser              docker
        DB                  /var/fluent-bit/state/flb_container.db
        Mem_Buf_Limit       50MB
        Skip_Long_Lines     On
        Refresh_Interval    10
        Rotate_Wait         30
        storage.type        filesystem
        Read_from_Head      ${READ_FROM_HEAD}
```

上面的 `[INPUT]` 部分正在接收所有容器日志。这可能会产生大量不必要的数据。过滤掉这些数据可以减少发送到 CloudWatch 的日志数据量，从而降低成本。您可以在输出到 CloudWatch 之前对日志应用过滤器。Fluentbit 在 `[FILTER]` 部分中定义了这一点。例如，过滤掉附加到日志事件的 Kubernetes 元数据可以减少日志量。

```
    [FILTER]
        Name                nest
        Match               application.*
        Operation           lift
        Nested_under        kubernetes
        Add_prefix          Kube.

    [FILTER]
        Name                modify
        Match               application.*
        Remove              Kube.<Metadata_1>
        Remove              Kube.<Metadata_2>
        Remove              Kube.<Metadata_3>
    
    [FILTER]
        Name                nest
        Match               application.*
        Operation           nest
        Wildcard            Kube.*
        Nested_under        kubernetes
        Remove_prefix       Kube.
```

## 指标

指标提供了有关系统性能的宝贵信息。通过将所有与系统相关或可用资源指标合并到一个集中位置，您可以获得比较和分析性能数据的能力。这种集中方法使您能够做出更明智的战略决策，例如扩大或缩小资源。此外，指标在评估资源健康状况方面也发挥着关键作用，让您可以在必要时采取主动措施。通常，可观察性成本会随着遥测数据收集和保留而增加。以下是您可以实施的一些策略，以降低指标遥测的成本:仅收集重要的指标，降低遥测数据的基数，并微调遥测数据收集的粒度。

### 监控重要内容并仅收集所需内容

第一个降低成本的策略是减少收集的指标数量，从而降低保留成本。

1. 首先从你和/或你的利益相关者的要求出发，倒推确定[最重要的指标](https://aws-observability.github.io/observability-best-practices/guides/#monitor-what-matters)。成功指标因人而异!了解什么是"良好"状态，并对此进行衡量。
2. 考虑深入研究你所支持的工作负载，并确定其关键性能指标(KPI),即"黄金信号"。这些应与业务和利益相关者的要求保持一致。使用Amazon CloudWatch和Metric Math计算SLI、SLO和SLA对于管理服务可靠性至关重要。请遵循本[指南](https://aws-observability.github.io/observability-best-practices/guides/operational/business/key-performance-indicators/#10-understanding-kpis-golden-signals)中概述的最佳实践，有效监控和维护EKS环境的性能。
3. 然后继续通过不同的基础设施层来[连接和关联](https://aws-observability.github.io/observability-best-practices/signals/metrics/#correlate-with-operational-metric-data)EKS集群、节点和其他基础设施指标与你的工作负载KPI。将你的业务指标和运营指标存储在一个可以将它们关联在一起并根据观察到的影响得出结论的系统中。
4. EKS从控制平面、集群kube-state-metrics、pod和节点公开指标。所有这些指标的相关性取决于你的需求，但你可能不需要跨不同层的每一个指标。你可以使用这个[EKS基本指标](https://aws-observability.github.io/observability-best-practices/guides/containers/oss/eks/best-practices-metrics-collection/)指南作为监控EKS集群和工作负载整体健康状况的基线。

以下是我们使用 `relabel_config` 仅保留 kubelet 指标和 `metric_relabel_config` 丢弃所有容器指标的 Prometheus 抓取配置示例。

```yaml
  kubernetes_sd_configs:
  - role: endpoints
    namespaces:
      names:
      - kube-system
  bearer_token_file: /var/run/secrets/kubernetes.io/serviceaccount/token
  tls_config:
    insecure_skip_verify: true
  relabel_configs:
  - source_labels: [__meta_kubernetes_service_label_k8s_app]
    regex: kubelet
    action: keep

  metric_relabel_configs:
  - source_labels: [__name__]
    regex: container_(network_tcp_usage_total|network_udp_usage_total|tasks_state|cpu_load_average_10s)
    action: drop
```

### 在适用的情况下降低基数

基数是指特定指标集合中数据值及其维度（例如 Prometheus 标签）的唯一性。高基数指标具有许多维度，每个维度指标组合的唯一性更高。更高的基数会导致更大的指标遥测数据大小和存储需求，从而增加成本。

在下面的高基数示例中，我们看到指标 Latency 具有维度 RequestID、CustomerID 和 Service，每个维度都有许多唯一值。基数是每个维度可能值数量组合的度量。在 Prometheus 中，每组唯一的维度/标签都被视为一个新的指标，因此高基数意味着更多的指标。

![high cardinality](../images/high-cardinality.png)

在具有许多指标和每个指标的维度/标签（集群、命名空间、服务、Pod、容器等）的 EKS 环境中，基数往往会增长。为了优化成本，请仔细考虑您正在收集的指标的基数。例如，如果您正在聚合特定指标以在集群级别进行可视化，那么您可以删除较低层的附加标签，如命名空间标签。

为了在 Prometheus 中识别高基数指标，您可以运行以下 PROMQL 查询来确定哪些抓取目标具有最高的指标数量(基数):

```promql
topk_max(5, max_over_time(scrape_samples_scraped[1h]))
```

以下 PROMQL 查询可帮助您确定哪些抓取目标具有最高的指标流转率(在给定的抓取中创建了多少新的指标序列):

```promql
topk_max(5, max_over_time(scrape_series_added[1h]))
```

如果您使用 Grafana，您可以使用 Grafana Lab 的 Mimirtool 来分析您的 Grafana 仪表板和 Prometheus 规则，以识别未使用的高基数指标。请按照[此指南](https://grafana.com/docs/grafana-cloud/account-management/billing-and-usage/control-prometheus-metrics-usage/usage-analysis-mimirtool/?pg=blog&plcmt=body-txt#analyze-and-reduce-metrics-usage-with-grafana-mimirtool)了解如何使用 `mimirtool analyze` 和 `mimirtool analyze prometheus` 命令来识别仪表板中未引用的活动指标。

### 考虑指标粒度

每秒而不是每分钟收集指标会对收集和存储的遥测数据量产生很大影响，从而增加成本。确定合理的抓取或指标收集间隔，在足够的粒度(以查看瞬时问题)和足够低的成本之间取得平衡。对于用于容量规划和较大时间窗口分析的指标，请降低粒度。

以下是 AWS Distro for Opentelemetry (ADOT) EKS Addon Collector 的[配置](https://docs.aws.amazon.com/eks/latest/userguide/deploy-deployment.html)中的一个片段。

!!! attention
    全局 Prometheus 抓取间隔设置为 15 秒。可以增加此抓取间隔，从而减少在 Prometheus 中收集的指标数据量。

```yaml hl_lines="22"
apiVersion: opentelemetry.io/v1alpha1
kind: OpenTelemetryCollector
metadata:
  name: my-collector-amp

...

config: |
    extensions:
      sigv4auth:
        region: "<YOUR_AWS_REGION>"
        service: "aps"

    receivers:
      #
      # Prometheus接收器的抓取配置
      # 这与使用社区Helm图表安装Prometheus时使用的配置相同
      #
      prometheus:
        config:
          global:
  scrape_interval: 15s
            scrape_timeout: 10s
```



## 跟踪

与跟踪相关的主要成本来自于跟踪存储的生成。对于跟踪，目标是收集足够的数据来诊断和了解性能方面。但是，由于X-Ray跟踪的成本是基于转发到X-Ray的数据，因此在转发后删除跟踪将不会降低您的成本。让我们回顾一下如何在保持数据以便您进行适当分析的同时降低跟踪成本的方法。


### 应用采样规则

默认情况下，X-Ray的采样率是保守的。定义采样规则，您可以控制收集的数据量。这将提高性能效率，同时降低成本。通过[降低采样率](https://docs.aws.amazon.com/xray/latest/devguide/xray-console-sampling.html#xray-console-custom),您可以只从您的工作负载所需的请求中收集跟踪，同时保持较低的成本结构。

例如，您有一个Java应用程序，您想调试所有请求的跟踪，针对1个有问题的路由。

**通过SDK配置从JSON文档加载采样规则**

```json
{
"version": 2,
  "rules": [
    {
"description": "debug-eks",
      "host": "*",
      "http_method": "PUT",
      "url_path": "/history/*",
      "fixed_target": 0,
      "rate": 1,
      "service_type": "debug-eks"
    }
  ],
  "default": {
"fixed_target": 1,
    "rate": 0.1
  }
}
```


**通过控制台**

![console](../images/console.png)

### 应用尾部采样与AWS Distro for OpenTelemetry (ADOT)

ADOT 尾部采样允许您控制服务中摄取的跟踪量。但是，尾部采样允许您在请求中的所有跨度完成后而不是在开始时定义采样策略。这进一步限制了传输到 CloudWatch 的原始数据量，从而降低了成本。

例如，如果您对登陆页面的流量采样 1%,对付款页面的请求采样 10%,这可能会在 30 分钟内留下 300 个跟踪。使用过滤特定错误的 ADOT 尾部采样规则，您可能只剩下 200 个跟踪，从而减少了存储的跟踪数量。

```yaml hl_lines="5"
processors:
  groupbytrace:
    wait_duration: 10s
    num_traces: 300 
    tail_sampling:
    decision_wait: 1s # 此值应小于 wait_duration
    policies:
      - ..... # 适用的策略**
  batch/tracesampling:
    timeout: 0s # 由于这将在前面的处理器中发生，因此无需再等待
    send_batch_max_size: 8196 # 这仍将允许我们限制发送到后续导出器的批次大小

service:
  pipelines:
    traces/tailsampling:
      receivers: [otlp]
      processors: [groupbytrace, tail_sampling, batch/tracesampling]
      exporters: [awsxray]
```

### 利用 Amazon S3 存储选项

您应该利用 AWS S3 存储桶及其不同的存储类来存储跟踪。在保留期限到期之前将跟踪导出到 S3。使用 Amazon S3 生命周期规则将跟踪数据移动到满足您要求的存储类。

例如，如果您有 90 天的跟踪数据，[Amazon S3 智能分层存储](https://aws.amazon.com/s3/storage-classes/intelligent-tiering/)可以根据您的使用模式自动将数据移动到长期存储。如果您需要在以后参考跟踪，可以使用 [Amazon Athena](https://aws.amazon.com/athena/) 查询 Amazon S3 中的数据。这可以进一步降低分布式跟踪的成本。


## 其他资源:

* [可观察性最佳实践指南](https://aws-observability.github.io/observability-best-practices/guides/)
* [最佳实践指标收集](https://aws-observability.github.io/observability-best-practices/guides/containers/oss/eks/)
* [AWS re:Invent 2022 - 亚马逊的可观察性最佳实践 (COP343)](https://www.youtube.com/watch?v=zZPzXEBW4P8)
* [AWS re:Invent 2022 - 现代应用程序的可观察性最佳实践 (COP344)](https://www.youtube.com/watch?v=YiegAlC_yyc)