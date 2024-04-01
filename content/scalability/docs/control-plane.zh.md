# Kubernetes 控制平面

Kubernetes 控制平面包括 Kubernetes API 服务器、Kubernetes 控制器管理器、调度器和 Kubernetes 正常运行所需的其他组件。这些组件的可扩展性限制因集群中运行的内容而有所不同，但对扩展影响最大的领域包括 Kubernetes 版本、利用率和单个节点扩展。

## 使用 EKS 1.24 或更高版本

EKS 1.24 引入了许多更改，并将容器运行时从 docker 切换到了 [containerd](https://containerd.io/)。Containerd 通过限制容器运行时功能以紧密对应 Kubernetes 的需求，从而提高了单个节点的性能，帮助集群扩展。Containerd 在 EKS 的每个受支持版本中都可用，如果您希望在 1.24 之前的版本中切换到 containerd，请使用 [`--container-runtime` 引导标志](https://docs.aws.amazon.com/eks/latest/userguide/eks-optimized-ami.html#containerd-bootstrap)。

## 限制工作负载和节点突发

!!! 注意
    为了避免达到控制平面的 API 限制，您应该限制一次增加集群规模两位数百分比的扩展峰值(例如，从 1000 个节点到 1100 个节点或一次从 4000 个到 4500 个 pod)。

随着集群的增长，EKS 控制平面将自动扩展，但对于它可以扩展的速度有限制。当您首次创建 EKS 集群时，控制平面不会立即能够扩展到数百个节点或数千个 pod。要了解更多关于 EKS 如何进行扩展改进，请阅读[此博客文章](https://aws.amazon.com/blogs/containers/amazon-eks-control-plane-auto-scaling-enhancements-improve-speed-by-4x/)。

扩展大型应用程序需要基础架构适应并完全就绪（例如预热负载均衡器）。为了控制扩展速度，请确保您根据应用程序的正确指标进行扩展。CPU和内存扩展可能无法准确预测您的应用程序约束，在Kubernetes Horizontal Pod Autoscaler (HPA)中使用自定义指标(例如每秒请求数)可能是更好的扩展选择。

要使用自定义指标，请参阅[Kubernetes文档](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale-walkthrough/#autoscaling-on-multiple-metrics-and-custom-metrics)中的示例。如果您有更高级的扩展需求或需要根据外部源(例如AWS SQS队列)进行扩展，则使用[KEDA](https://keda.sh)进行基于事件的工作负载扩展。

## 安全地缩减节点和Pod

### 替换长时间运行的实例

定期替换节点可以通过避免配置漂移和仅在长时间运行后才会发生的问题(例如缓慢内存泄漏)来保持集群健康。自动化替换将为您提供良好的流程和实践，用于节点升级和安全补丁。如果您集群中的每个节点都定期替换，那么维护单独的流程进行持续维护所需的工作量就会减少。

使用Karpenter的[生存时间(TTL)](https://aws.github.io/aws-eks-best-practices/karpenter/#use-timers-ttl-to-automatically-delete-nodes-from-the-cluster)设置在实例运行指定时间后将其替换。自管理节点组可以使用`max-instance-lifetime`设置自动循环节点。托管节点组当前没有此功能，但您可以在[GitHub上](https://github.com/aws/containers-roadmap/issues/1190)跟踪此请求。

### 删除利用率低的节点

您可以在没有正在运行的工作负载时使用Kubernetes集群自动扩缩器中的缩减阈值[`--scale-down-utilization-threshold`](https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/FAQ.md#how-does-scale-down-work)或在Karpenter中使用`ttlSecondsAfterEmpty`配置程序设置来删除节点。

### 使用Pod中断预算和安全节点关闭

从Kubernetes集群中删除Pod和节点需要控制器对多个资源(例如EndpointSlices)进行更新。频繁或过于快速地执行此操作可能会导致API服务器限制和应用程序中断，因为更改会传播到控制器。[Pod中断预算](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/)是一种最佳实践，可以减缓集群中节点被删除或重新调度时的工作负载可用性，从而保护工作负载可用性。

## 运行Kubectl时使用客户端缓存

如果使用kubectl命令效率低下，可能会给Kubernetes API服务器增加额外负载。您应该避免运行重复使用kubectl的脚本或自动化(例如在for循环中)或在没有本地缓存的情况下运行命令。

`kubectl`有一个客户端缓存，可以缓存来自集群的发现信息，从而减少所需的API调用次数。缓存默认启用，每10分钟刷新一次。

如果您从容器或没有客户端缓存运行kubectl，可能会遇到API限制问题。建议保留您的集群缓存，通过挂载`--cache-dir`来避免进行不必要的API调用。

## 禁用kubectl压缩

在您的 kubeconfig 文件中禁用 kubectl 压缩可以减少 API 和客户端 CPU 使用率。默认情况下，服务器会压缩发送到客户端的数据以优化网络带宽。这会增加每个请求的客户端和服务器 CPU 负载，禁用压缩可以减少开销和延迟，前提是您有足够的带宽。要禁用压缩，您可以使用 `--disable-compression=true` 标志或在 kubeconfig 文件中设置 `disable-compression: true`。

```
apiVersion: v1
clusters:
- cluster:
    server: serverURL
    disable-compression: true
  name: cluster
```

## 分片集群自动扩缩器

[Kubernetes 集群自动扩缩器已经过测试](https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/proposals/scalability_tests.md),可以扩展到 1000 个节点。在超过 1000 个节点的大型集群上，建议以分片模式运行多个集群自动扩缩器实例。每个集群自动扩缩器实例都被配置为扩展一组节点组。以下示例显示了两个集群自动扩缩配置，每个配置都被配置为扩展 4 个节点组。

ClusterAutoscaler-1

```
autoscalingGroups:
- name: eks-core-node-grp-20220823190924690000000011-80c1660e-030d-476d-cb0d-d04d585a8fcb
  maxSize: 50
  minSize: 2
- name: eks-data_m1-20220824130553925600000011-5ec167fa-ca93-8ca4-53a5-003e1ed8d306
  maxSize: 450
  minSize: 2
- name: eks-data_m2-20220824130733258600000015-aac167fb-8bf7-429d-d032-e195af4e25f5
  maxSize: 450
  minSize: 2
- name: eks-data_m3-20220824130553914900000003-18c167fa-ca7f-23c9-0fea-f9edefbda002
  maxSize: 450
  minSize: 2
```

ClusterAutoscaler-2

```
autoscalingGroups:
- name: eks-data_m4-2022082413055392550000000f-5ec167fa-ca86-6b83-ae9d-1e07ade3e7c4
  maxSize: 450
  minSize: 2
- name: eks-data_m5-20220824130744542100000017-02c167fb-a1f7-3d9e-a583-43b4975c050c
  maxSize: 450
  minSize: 2
- name: eks-data_m6-2022082413055392430000000d-9cc167fa-ca94-132a-04ad-e43166cef41f
  maxSize: 450
  minSize: 2
- name: eks-data_m7-20220824130553921000000009-96c167fa-ca91-d767-0427-91c879ddf5af
  maxSize: 450
  minSize: 2
```

## API 优先级和公平性

![](../images/APF.jpg)

### 概述

<iframe width="560" height="315" src="https://www.youtube.com/embed/YnPPHBawhE0" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe>

为了在请求量增加的时期保护自身免受过载，API 服务器会限制在给定时间内可以处理的正在进行的请求数量。一旦超过此限制，API 服务器将开始拒绝请求并向客户端返回 429 HTTP 响应代码"Too Many Requests"。服务器丢弃请求并让客户端稍后重试比没有服务器端对请求数量的限制并导致控制平面过载（可能会导致性能下降或不可用）要好得多。

Kubernetes 用于配置这些正在进行的请求如何在不同请求类型之间划分的机制称为 [API 优先级和公平性](https://kubernetes.io/docs/concepts/cluster-administration/flow-control/)。API 服务器通过将 `--max-requests-inflight` 和 `--max-mutating-requests-inflight` 标志指定的值相加来配置它可以接受的总正在进行的请求数。EKS 使用这些标志的默认值 400 和 200 个请求，允许同时分派总共 600 个请求。但是，随着它响应利用率和工作负载变化的增加而扩展控制平面的大小，它相应地将正在进行的请求配额增加到 2000 (可能会更改)。APF 指定了这些正在进行的请求配额如何在不同的请求类型之间进一步细分。请注意，EKS 控制平面高度可用，每个集群至少注册了 2 个 API 服务器。这意味着您的集群可以处理的总正在进行的请求数是每个 kube-apiserver 设置的正在进行的配额的两倍(如果进一步水平扩展则更高)。这相当于最大的 EKS 集群每秒可处理数千个请求。

有两种Kubernetes对象，称为PriorityLevelConfigurations和FlowSchemas，用于配置总请求数在不同请求类型之间的划分方式。这些对象由API Server自动维护，EKS使用给定Kubernetes小版本的默认配置。PriorityLevelConfigurations表示允许请求总数的一部分。例如，workload-high PriorityLevelConfiguration被分配了总600个请求中的98个。分配给所有PriorityLevelConfigurations的请求总和将等于600(或略高于600，因为如果授予某个级别的请求为小数，API Server将向上舍入)。要检查集群中的PriorityLevelConfigurations及分配给每个级别的请求数，您可以运行以下命令。这些是EKS 1.24上的默认值:

```
$ kubectl get --raw /metrics | grep apiserver_flowcontrol_request_concurrency_limit
apiserver_flowcontrol_request_concurrency_limit{priority_level="catch-all"} 13
apiserver_flowcontrol_request_concurrency_limit{priority_level="global-default"} 49
apiserver_flowcontrol_request_concurrency_limit{priority_level="leader-election"} 25
apiserver_flowcontrol_request_concurrency_limit{priority_level="node-high"} 98
apiserver_flowcontrol_request_concurrency_limit{priority_level="system"} 74
apiserver_flowcontrol_request_concurrency_limit{priority_level="workload-high"} 98
apiserver_flowcontrol_request_concurrency_limit{priority_level="workload-low"} 245
```

第二种对象是 FlowSchema。具有给定一组属性的 API 服务器请求将被归类为同一个 FlowSchema。这些属性包括经过身份验证的用户或请求的属性，例如 API 组、命名空间或资源。FlowSchema 还指定此类请求应映射到哪个 PriorityLevelConfiguration。这两个对象一起表示"我希望此类型的请求计入此份正在进行的请求"。当请求到达 API 服务器时，它将检查每个 FlowSchema 直到找到一个与所有必需属性匹配的 FlowSchema。如果多个 FlowSchema 与请求匹配，API 服务器将选择具有最小匹配优先级的 FlowSchema，该优先级在对象中指定为属性。

可以使用以下命令查看 FlowSchema 到 PriorityLevelConfiguration 的映射:

```
$ kubectl get flowschemas
名称                           优先级             匹配优先级           区分方法              时间     缺少PL
exempt                         exempt            1                    <none>                7h19m   False
eks-exempt                     exempt            2                    <none>                7h19m   False
probes                         exempt            2                    <none>                7h19m   False
system-leader-election         leader-election   100                  ByUser                7h19m   False
endpoint-controller            workload-high     150                  ByUser                7h19m   False
workload-leader-election       leader-election   200                  ByUser                7h19m   False
system-node-high               node-high         400                  ByUser                7h19m   False
system-nodes                   system            500                  ByUser                7h19m   False
kube-controller-manager        workload-high     800                  ByNamespace           7h19m   False
kube-scheduler                 workload-high     800                  ByNamespace           7h19m   False
kube-system-service-accounts   workload-high     900                  ByNamespace           7h19m   False
eks-workload-high              workload-high     1000                 ByUser                7h14m   False
service-accounts               workload-low      9000                 ByUser                7h19m   False
global-default                 global-default    9900                 ByUser                7h19m   False
catch-all                      catch-all         10000                ByUser                7h19m   False
```

PriorityLevelConfigurations 可以有 Queue、Reject 或 Exempt 三种类型。对于 Queue 和 Reject 类型，将对该优先级别的最大并发请求数量实施限制，但是当达到该限制时的行为会有所不同。例如，workload-high PriorityLevelConfiguration 使用 Queue 类型，并为 controller-manager、endpoint-controller、scheduler、eks 相关控制器以及运行在 kube-system 命名空间中的 pod 提供 98 个可用请求。由于使用了 Queue 类型，API 服务器将尝试将请求保存在内存中，并希望在这些请求超时之前，并发请求的数量降低到低于 98。如果某个请求在队列中超时或者已经有太多请求排队，API 服务器别无选择，只能丢弃该请求并向客户端返回 429。请注意，排队可能会阻止请求收到 429，但代价是请求的端到端延迟会增加。

现在考虑映射到 Reject 类型的 catch-all PriorityLevelConfiguration 的 catch-all FlowSchema。如果客户端达到 13 个并发请求的限制，API 服务器将不会执行排队，而是立即丢弃请求并返回 429 响应码。最后，映射到 Exempt 类型的 PriorityLevelConfiguration 的请求永远不会收到 429，并且总是会立即被分发。这用于诸如 healthz 请求或来自 system:masters 组的高优先级请求。

### 监控 APF 和丢弃的请求

要确认是否有请求因 APF 而被丢弃，可以监控 API 服务器的 `apiserver_flowcontrol_rejected_requests_total` 指标，以检查受影响的 FlowSchemas 和 PriorityLevelConfigurations。例如，该指标显示有 100 个来自 service-accounts FlowSchema 的请求由于在 workload-low 队列中超时而被丢弃:

```
% kubectl get --raw /metrics | grep apiserver_flowcontrol_rejected_requests_total
apiserver_flowcontrol_rejected_requests_total{flow_schema="service-accounts",priority_level="workload-low",reason="time-out"} 100
```

检查给定的 PriorityLevelConfiguration 是否接近收到 429 或由于排队而导致延迟增加，您可以比较并发限制与实际并发使用量之间的差异。在此示例中，我们有 100 个请求的缓冲区。

```
% kubectl get --raw /metrics | grep 'apiserver_flowcontrol_request_concurrency_limit.*workload-low'
apiserver_flowcontrol_request_concurrency_limit{priority_level="workload-low"} 245

% kubectl get --raw /metrics | grep 'apiserver_flowcontrol_request_concurrency_in_use.*workload-low'
apiserver_flowcontrol_request_concurrency_in_use{flow_schema="service-accounts",priority_level="workload-low"} 145
```

要检查给定的 PriorityLevelConfiguration 是否正在排队但不一定丢弃请求，可以参考 `apiserver_flowcontrol_current_inqueue_requests` 指标:

```
% kubectl get --raw /metrics | grep 'apiserver_flowcontrol_current_inqueue_requests.*workload-low'
apiserver_flowcontrol_current_inqueue_requests{flow_schema="service-accounts",priority_level="workload-low"} 10
```

其他有用的 Prometheus 指标包括:

- apiserver_flowcontrol_dispatched_requests_total
- apiserver_flowcontrol_request_execution_seconds
- apiserver_flowcontrol_request_wait_duration_seconds

请参阅上游文档以获取 [APF 指标](https://kubernetes.io/docs/concepts/cluster-administration/flow-control/#observability)的完整列表。

### 防止请求被丢弃

#### 通过更改工作负载来防止 429

当由于某个 PriorityLevelConfiguration 超出其允许的最大并发请求数而导致 APF 丢弃请求时，受影响的 FlowSchemas 中的客户端可以减少同时执行的请求数量。这可以通过在发生 429 错误的时间段内减少发送的总请求数量来实现。请注意，长时间运行的请求(如耗时较长的列表调用)尤其成问题，因为它们在整个执行期间都被视为并发请求。减少这些耗时请求的数量或优化这些列表调用的延迟(例如，通过减少每个请求获取的对象数量或切换到使用 watch 请求)可以帮助减少给定工作负载所需的总并发量。

#### 通过更改 APF 设置来防止 429 错误

!!! 警告
    只有在您知道自己在做什么的情况下才能更改默认的 APF 设置。错误配置的 APF 设置可能会导致 API 服务器请求被丢弃和工作负载中断。

防止请求被丢弃的另一种方法是更改 EKS 集群上安装的默认 FlowSchemas 或 PriorityLevelConfigurations。EKS 为给定的 Kubernetes 次要版本安装上游默认的 FlowSchemas 和 PriorityLevelConfigurations 设置。如果对象上的以下注释设置为 false，API 服务器将自动将这些对象与其默认值进行协调:

```
  metadata:
    annotations:
      apf.kubernetes.io/autoupdate-spec: "false"
```

从高层次来看，可以修改 APF 设置以:

- 为您关心的请求分配更多并发容量。
- 隔离非必需或昂贵的请求，这些请求可能会耗尽其他请求类型的容量。

这可以通过更改默认的 FlowSchemas 和 PriorityLevelConfigurations 或创建这些类型的新对象来实现。操作员可以增加相关 PriorityLevelConfigurations 对象的 assuredConcurrencyShares 值，以增加分配给它们的正在进行的请求的比例。此外，如果应用程序可以处理由于请求在被分派之前排队而导致的额外延迟，那么在任何给定时间可以排队的请求数量也可以增加。

或者，可以创建特定于客户工作负载的新 FlowSchema 和 PriorityLevelConfigurations 对象。请注意，无论是为现有的 PriorityLevelConfigurations 还是为新的 PriorityLevelConfigurations 分配更多的 assuredConcurrencyShares，都会导致其他 bucket 可以处理的请求数量减少，因为每个 API 服务器的总限制将保持在 600 个正在进行的请求。

在更改 APF 默认值时，应在非生产集群上监控以下指标，以确保更改设置不会导致意外的 429 错误:

1. 应监控所有 FlowSchemas 的 `apiserver_flowcontrol_rejected_requests_total` 指标，以确保没有 bucket 开始丢弃请求。
2. 应比较 `apiserver_flowcontrol_request_concurrency_limit` 和 `apiserver_flowcontrol_request_concurrency_in_use` 的值，以确保正在使用的并发性不会有违反该优先级别限制的风险。

定义新的 FlowSchema 和 PriorityLevelConfiguration 的一个常见用例是隔离。假设我们想将来自 pod 的长时间运行的列表事件调用与其他请求隔离开来，分配自己的请求份额。这将防止使用现有服务帐户 FlowSchema 的重要 pod 请求收到 429 错误并被剥夺请求能力。请记住，正在进行的总请求数是有限的，但是，此示例显示可以修改 APF 设置以更好地为给定工作负载划分请求能力:

示例 FlowSchema 对象用于隔离列出事件请求:

```
apiVersion: flowcontrol.apiserver.k8s.io/v1beta1
kind: FlowSchema
metadata:
  name: list-events-default-service-accounts
spec:
  distinguisherMethod:
    type: ByUser
  matchingPrecedence: 8000
  priorityLevelConfiguration:
    name: catch-all
  rules:
  - resourceRules:
    - apiGroups:
      - '*'
      namespaces:
      - default
      resources:
      - events
      verbs:
      - list
    subjects:
    - kind: ServiceAccount
      serviceAccount:
        name: default
        namespace: default
```

- 此 FlowSchema 捕获了由默认命名空间中的服务帐户发出的所有列出事件调用。
- 匹配优先级 8000 低于现有 service-accounts FlowSchema 使用的值 9000，因此这些列出事件调用将匹配 list-events-default-service-accounts 而不是 service-accounts。
- 我们使用 catch-all PriorityLevelConfiguration 来隔离这些请求。此存储桶只允许这些长时间运行的列出事件调用使用 13 个并发请求。一旦它们尝试同时发出超过 13 个此类请求，Pod 就会开始收到 429 错误。

## 从 API 服务器检索资源

从 API 服务器获取信息是任何规模集群的预期行为。随着集群中资源数量的增加，请求频率和数据量可能会很快成为控制平面的瓶颈，并导致 API 延迟和缓慢。根据延迟的严重程度，如果不小心的话，可能会导致意外的停机时间。

了解您正在请求什么以及请求的频率是避免此类问题的第一步。以下是根据扩展最佳实践限制查询量的指导。本节中的建议按照从已知可扩展性最佳的选项开始的顺序提供。

### 使用共享信息器

在构建与Kubernetes API集成的控制器和自动化时，您通常需要从Kubernetes资源中获取信息。如果定期轮询这些资源，可能会给API服务器带来大量负载。

使用client-go库中的[informer](https://pkg.go.dev/k8s.io/client-go/informers)可以让您基于事件而不是轮询来监视资源变化的好处。Informer通过为事件和变化使用共享缓存，进一步减少了负载，因此监视相同资源的多个控制器不会增加额外负载。

控制器应避免在大型集群中轮询没有标签和字段选择器的集群范围资源。每个未过滤的轮询都需要从etcd通过API服务器发送大量不必要的数据，然后由客户端进行过滤。通过基于标签和命名空间进行过滤，您可以减少API服务器为完成请求所需执行的工作量和发送到客户端的数据量。

### 优化Kubernetes API使用

使用自定义控制器或自动化调用Kubernetes API时，重要的是要限制只调用所需的资源。如果没有限制，您可能会给API服务器和etcd带来不必要的负载。

建议您尽可能使用watch参数。如果不带任何参数，默认行为是列出对象。要使用watch而不是list，您可以在API请求的末尾附加`?watch=true`。例如，要使用watch获取默认命名空间中的所有pod，请使用:

```
/api/v1/namespaces/default/pods?watch=true
```

如果您正在列出对象，您应该限制列出的范围和返回的数据量。您可以通过在请求中添加`limit=500`参数来限制返回的数据。`fieldSelector`参数和`/namespace/`路径可用于确保您的列表范围尽可能小。例如，要仅列出默认命名空间中正在运行的pod，请使用以下API路径和参数。

```
/api/v1/namespaces/default/pods?fieldSelector=status.phase=Running&limit=500
```

或列出所有正在运行的 pod:

```
/api/v1/pods?fieldSelector=status.phase=Running&limit=500
```

限制 watch 调用或列出对象的另一个选择是使用[`resourceVersions`，您可以在 Kubernetes 文档中阅读相关内容](https://kubernetes.io/docs/reference/using-api/api-concepts/#resource-versions)。如果不使用 `resourceVersion` 参数，您将收到最新可用的版本，这需要 etcd 仲裁读取，这是数据库中最昂贵和最慢的读取方式。resourceVersion 取决于您尝试查询的资源，可以在 `metadata.resourseVersion` 字段中找到。在使用 watch 调用而不仅仅是 list 调用的情况下，也建议这样做。

有一个特殊的 `resourceVersion=0` 可用，它将从 API 服务器缓存返回结果。这可以减少 etcd 负载，但不支持分页。

```
/api/v1/namespaces/default/pods?resourceVersion=0
```
建议使用 watch 并将 resourceVersion 设置为从前一个 list 或 watch 接收到的最新已知值。这在 client-go 中会自动处理。但如果您使用其他语言的 k8s 客户端，建议再次检查。

```
/api/v1/namespaces/default/pods?watch=true&resourceVersion=362812295
```
如果您在不带任何参数的情况下调用 API，这将对 API 服务器和 etcd 造成最大的资源消耗。此调用将获取所有命名空间中的所有 pod，而不进行分页或限制范围，并需要从 etcd 进行仲裁读取。

```
/api/v1/pods
```