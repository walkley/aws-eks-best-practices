# Kubernetes 上游 SLO

Amazon EKS 运行与上游 Kubernetes 版本相同的代码，并确保 EKS 集群在 Kubernetes 社区定义的 SLO 范围内运行。Kubernetes [可扩展性特别兴趣小组 (SIG)](https://github.com/kubernetes/community/tree/master/sig-scalability) 定义了可扩展性目标，并通过 SLI 和 SLO 调查性能瓶颈。

SLI 是我们衡量系统的方式，如指标或可用于确定系统运行"良好"程度的度量，例如请求延迟或计数。SLO 定义了系统运行"良好"时的预期值，例如请求延迟保持在 3 秒以下。Kubernetes SLO 和 SLI 专注于 Kubernetes 组件的性能，与关注 EKS 集群端点可用性的 Amazon EKS 服务 SLA 完全无关。

Kubernetes 有许多功能允许用户使用自定义插件或驱动程序扩展系统，如 CSI 驱动程序、准入 Webhook 和自动扩缩器。这些扩展可能会以不同方式极大影响 Kubernetes 集群的性能，即如果 Webhook 目标不可用，具有 `failurePolicy=Ignore` 的准入 Webhook 可能会增加 K8s API 请求的延迟。Kubernetes 可扩展性 SIG 使用["你承诺，我们承诺"框架](https://github.com/kubernetes/community/blob/master/sig-scalability/slos/slos.md#how-we-define-scalability)定义可扩展性:

> 如果你承诺:
>     - 正确配置集群
>     - "合理"使用可扩展性功能
>     - 将集群中的负载保持在[推荐限制](https://github.com/kubernetes/community/blob/master/sig-scalability/configs-and-limits/thresholds.md)内
>
> 那么我们承诺您的集群可扩展，即:
>     - 满足所有 SLO。

## Kubernetes SLO
Kubernetes SLO 并不包含可能影响集群的所有插件和外部限制，如工作节点扩缩容或准入 Webhook。这些 SLO 专注于 [Kubernetes 组件](https://kubernetes.io/docs/concepts/overview/components/)并确保 Kubernetes 操作和资源在预期范围内运行。SLO 帮助 Kubernetes 开发人员确保对 Kubernetes 代码的更改不会降低整个系统的性能。

[Kuberntes 可扩展性 SIG 定义了以下官方 SLO/SLI](https://github.com/kubernetes/community/blob/master/sig-scalability/slos/slos.md)。Amazon EKS 团队定期在 EKS 集群上运行这些 SLO/SLI 的可扩展性测试，以监控随着更改和新版本发布而可能出现的性能下降。

|目标	|定义	|SLO	|
|---	|---	|---	|
|API 请求延迟 (变更)	|对于每个 (资源，动词) 对，处理单个对象的变更 API 调用的延迟，以最近 5 分钟内的 99 百分位数计算	|在默认的 Kubernetes 安装中，对于每个 (资源，动词) 对，不包括虚拟和聚合资源以及自定义资源定义，每集群日 99 百分位数 <= 1 秒	|
|API 请求延迟 (只读)	|对于每个 (资源，范围) 对，处理非流式只读 API 调用的延迟，以最近 5 分钟内的 99 百分位数计算	|在默认的 Kubernetes 安装中，对于每个 (资源，范围) 对，不包括虚拟和聚合资源以及自定义资源定义，每集群日 99 百分位数: (a) 如果 `范围=资源` 则 <= 1 秒 (b) 否则 (如果 `范围=命名空间` 或 `范围=集群`) <= 30 秒	|
|Pod 启动延迟	|可调度无状态 Pod 的启动延迟，不包括拉取镜像和运行初始化容器的时间，从 Pod 创建时间戳到观察到所有容器都报告为已启动的时间，以最近 5 分钟内的 99 百分位数计算	|在默认的 Kubernetes 安装中，每集群日 99 百分位数 <= 5 秒	|

### API 请求延迟

`kube-apiserver` 默认将 `--request-timeout` 定义为 `1m0s`，这意味着请求在超时和取消之前最多可以运行一分钟(60秒)。延迟的 SLO 根据所做请求的类型(可变更或只读)进行了细分:

#### 可变更

Kubernetes 中的可变更请求会对资源进行更改，例如创建、删除或更新。这些请求代价很高，因为在返回更新后的对象之前，这些更改必须写入 [etcd 后端](https://kubernetes.io/docs/concepts/overview/components/#etcd)。[Etcd](https://etcd.io/) 是一个分布式键值存储，用于存储所有 Kubernetes 集群数据。

这种延迟是以 5 分钟内 99 百分位数来衡量 Kubernetes 资源的(资源、动词)对，例如它会测量 Create Pod 请求和 Update Node 请求的延迟。为满足 SLO，请求延迟必须 <= 1 秒。

#### 只读

只读请求会检索单个资源(例如 Get Pod X)或一个集合(例如"从命名空间 X 获取所有 Pod")。`kube-apiserver` 维护一个对象缓存，因此所请求的资源可能来自缓存，也可能需要先从 etcd 检索。
这些延迟也是以 5 分钟内 99 百分位数来衡量的，但只读请求可能有不同的范围。SLO 定义了两个不同的目标:

* 对于针对*单个*资源的请求(即 `kubectl get pod -n mynamespace my-controller-xxx`)而言，请求延迟应保持 <= 1 秒。
* 对于针对命名空间或集群中多个资源的请求(例如 `kubectl get pods -A`)而言，延迟应保持 <= 30 秒

SLO 针对不同的请求范围有不同的目标值，因为对 Kubernetes 资源列表的请求期望在 SLO 内返回请求中所有对象的详细信息。在大型集群或大量资源集合中，这可能会导致较大的响应大小，需要一些时间才能返回。例如，在运行数万个 Pod 的集群中，每个 Pod 在 JSON 中编码时大约为 1 KiB，返回集群中所有 Pod 将包含 10MB 或更多。Kubernetes 客户端可以帮助[使用 APIListChunking 检索大型资源集合](https://kubernetes.io/docs/reference/using-api/api-concepts/#retrieving-large-results-sets-in-chunks)来减小响应大小。

### Pod 启动延迟

该 SLO 主要关注从创建 Pod 到该 Pod 中的容器实际开始执行所需的时间。为了测量这一点，计算从记录在 Pod 上的创建时间戳到[对该 Pod 进行 WATCH](https://kubernetes.io/docs/reference/using-api/api-concepts/#efficient-detection-of-changes) 报告容器已启动的时间差(不包括容器镜像拉取和初始化容器执行的时间)。为了满足 SLO，每个集群日的 Pod 启动延迟的 99 百分位数必须保持在 <=5 秒以内。

请注意，此 SLO 假设该集群中已经存在可供 Pod 调度的就绪状态的工作节点。该 SLO 不包括镜像拉取或初始化容器执行，并且还将测试限制为不利用持久存储插件的"无状态 Pod"。

## Kubernetes SLI 指标

Kubernetes 还通过为跟踪这些 SLI 的 Kubernetes 组件添加 [Prometheus 指标](https://prometheus.io/docs/concepts/data_model/)来改善围绕 SLI 的可观测性。使用 [Prometheus 查询语言 (PromQL)](https://prometheus.io/docs/prometheus/latest/querying/basics/)，我们可以构建查询来在 Prometheus 或 Grafana 仪表板等工具中显示 SLI 性能随时间的变化情况，下面是上述 SLO 的一些示例。

### API 服务器请求延迟

|指标	|定义	|
|---	|---	|
|apiserver_request_sli_duration_seconds	| 针对每个动词、组、版本、资源、子资源、作用域和组件的响应延迟分布情况(不包括 Webhook 持续时间和优先级及公平队列等待时间)，单位为秒。	|
|apiserver_request_duration_seconds	| 针对每个动词、dry run 值、组、版本、资源、子资源、作用域和组件的响应延迟分布情况，单位为秒。	|  

*注意: `apiserver_request_sli_duration_seconds` 指标从 Kubernetes 1.27 版本开始可用。*

您可以使用这些指标来调查 API 服务器响应时间，并查看是否存在 Kubernetes 组件或其他插件/组件的瓶颈。下面的查询基于[社区 SLO 仪表板](https://github.com/kubernetes/perf-tests/tree/master/clusterloader2/pkg/prometheus/manifests/dashboards)。

**API 请求延迟 SLI (变更操作)** - 此时间*不包括* Webhook 执行或队列等待时间。   
`histogram_quantile(0.99, sum(rate(apiserver_request_sli_duration_seconds_bucket{verb=~"CREATE|DELETE|PATCH|POST|PUT", subresource!~"proxy|attach|log|exec|portforward"}[5m])) by (resource, subresource, verb, scope, le)) > 0`

**API 请求延迟总计(变更)** - 这是请求在 API 服务器上所花费的总时间，此时间可能比 SLI 时间更长，因为它包括了 Webhook 执行和 API 优先级和公平等待时间。
`histogram_quantile(0.99, sum(rate(apiserver_request_duration_seconds_bucket{verb=~"CREATE|DELETE|PATCH|POST|PUT", subresource!~"proxy|attach|log|exec|portforward"}[5m])) by (resource, subresource, verb, scope, le)) > 0`

在这些查询中，我们排除了不会立即返回的流式 API 请求，例如 `kubectl port-forward` 或 `kubectl exec` 请求(`subresource!~"proxy|attach|log|exec|portforward"`)。我们还过滤了只修改对象的 Kubernetes 动词(`verb=~"CREATE|DELETE|PATCH|POST|PUT"`)。然后，我们计算了过去 5 分钟内该延迟的 99 百分位数。

我们可以使用类似的查询来获取只读 API 请求，只需修改我们过滤的动词以包含只读操作 `LIST` 和 `GET`。根据请求的范围(即获取单个资源或列出多个资源),也有不同的 SLO 阈值。

**API 请求延迟 SLI (只读)** - 此时间*不*包括 Webhook 执行或排队等待时间。
对于单个资源(scope=resource, threshold=1s)
`histogram_quantile(0.99, sum(rate(apiserver_request_sli_duration_seconds_bucket{verb=~"GET", scope=~"resource"}[5m])) by (resource, subresource, verb, scope, le))`

对于同一命名空间中的资源集合(scope=namespace, threshold=5s)
`histogram_quantile(0.99, sum(rate(apiserver_request_sli_duration_seconds_bucket{verb=~"LIST", scope=~"namespace"}[5m])) by (resource, subresource, verb, scope, le))`

对于整个集群中的资源集合(scope=cluster, threshold=30s)
`histogram_quantile(0.99, sum(rate(apiserver_request_sli_duration_seconds_bucket{verb=~"LIST", scope=~"cluster"}[5m])) by (resource, subresource, verb, scope, le))`

**API 请求延迟总计(只读)** - 这是请求在 API 服务器上所花费的总时间，此时间可能比 SLI 时间更长，因为它包括了 webhook 执行和等待时间。
对于单个资源(scope=resource, threshold=1s)
`histogram_quantile(0.99, sum(rate(apiserver_request_duration_seconds_bucket{verb=~"GET", scope=~"resource"}[5m])) by (resource, subresource, verb, scope, le))`

对于同一命名空间中的资源集合(scope=namespace, threshold=5s)
`histogram_quantile(0.99, sum(rate(apiserver_request_duration_seconds_bucket{verb=~"LIST", scope=~"namespace"}[5m])) by (resource, subresource, verb, scope, le))`

对于整个集群中的资源集合(scope=cluster, threshold=30s)
`histogram_quantile(0.99, sum(rate(apiserver_request_duration_seconds_bucket{verb=~"LIST", scope=~"cluster"}[5m])) by (resource, subresource, verb, scope, le))`

SLI 指标通过排除请求在 API 优先级和公平队列中等待的时间、通过准入 webhook 或其他 Kubernetes 扩展的时间，从而提供了对 Kubernetes 组件性能的洞察。总体指标提供了更全面的视角，因为它反映了您的应用程序等待来自 API 服务器的响应所需的时间。比较这些指标可以洞察请求处理延迟的来源。

### Pod 启动延迟

|指标	| 定义	|
|---	|---	|
|kubelet_pod_start_sli_duration_seconds	|从 pod 创建时间戳到观察到所有容器都报告为已启动的时间，不包括拉取镜像和运行初始化容器的时间，以秒为单位	|
|kubelet_pod_start_duration_seconds	|从 kubelet 第一次看到 pod 到 pod 开始运行的时间，以秒为单位。这不包括调度 pod 或扩容工作节点容量的时间。	|

*注意: `kubelet_pod_start_sli_duration_seconds` 从 Kubernetes 1.27 版本开始可用。*

与上述查询类似，您可以使用这些指标来了解节点扩展、镜像拉取和初始化容器相比 Kubelet 操作延迟了多长时间才启动 pod。

**Pod 启动延迟 SLI -** 这是从创建 pod 到应用程序容器报告为运行的时间。这包括工作节点容量可用和 pod 调度所需的时间，但不包括拉取镜像或运行初始化容器所需的时间。
`histogram_quantile(0.99, sum(rate(kubelet_pod_start_sli_duration_seconds_bucket[5m])) by (le))`

**Pod 启动延迟总计 -** 这是 kubelet 第一次启动 pod 所需的时间。这是从 kubelet 通过 WATCH 接收 pod 时开始测量的，不包括工作节点扩展或调度的时间。这包括拉取镜像和运行初始化容器的时间。
`histogram_quantile(0.99, sum(rate(kubelet_pod_start_duration_seconds_bucket[5m])) by (le))`

## 您集群上的 SLO

如果您从 EKS 集群中收集 Prometheus 指标，您可以更深入地了解 Kubernetes 控制平面组件的性能。

[perf-tests 仓库](https://github.com/kubernetes/perf-tests/)包括 Grafana 仪表板，用于在测试期间显示集群的延迟和关键性能指标。perf-tests 配置利用了 [kube-prometheus-stack](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack),这是一个开源项目，预配置为收集 Kubernetes 指标，但您也可以[使用 Amazon Managed Prometheus 和 Amazon Managed Grafana。](https://aws-observability.github.io/terraform-aws-observability-accelerator/eks/)

如果您使用 `kube-prometheus-stack` 或类似的 Prometheus 解决方案，您可以安装相同的仪表板来实时观察集群上的 SLO。

1. 首先，您需要使用 `kubectl apply -f prometheus-rules.yaml` 安装仪表板中使用的 Prometheus 规则。您可以在这里下载规则副本：https://github.com/kubernetes/perf-tests/blob/master/clusterloader2/pkg/prometheus/manifests/prometheus-rules.yaml
    1. 请确保文件中的命名空间与您的环境匹配
    2. 如果您使用 `kube-prometheus-stack`，请验证标签是否与 `prometheus.prometheusSpec.ruleSelector` helm 值匹配
2. 然后，您可以在 Grafana 中安装仪表板。JSON 仪表板和生成它们的 Python 脚本可在此处获得：https://github.com/kubernetes/perf-tests/tree/master/clusterloader2/pkg/prometheus/manifests/dashboards
    1. [`slo.json` 仪表板](https://github.com/kubernetes/perf-tests/blob/master/clusterloader2/pkg/prometheus/manifests/dashboards/slo.json)显示了集群相对于 Kubernetes SLO 的性能

请考虑 SLO 专注于您集群中 Kubernetes 组件的性能，但您还可以查看其他指标，这些指标可以从不同角度或视角了解您的集群。Kubernetes 社区项目如 [Kube-state-metrics](https://github.com/kubernetes/kube-state-metrics/tree/main) 可帮助您快速分析集群中的趋势。Kubernetes 社区的大多数常见插件和驱动程序也会发出 Prometheus 指标，允许您调查自动缩放器或自定义调度程序等内容。

[Observability 最佳实践指南](https://aws-observability.github.io/observability-best-practices/guides/containers/oss/eks/best-practices-metrics-collection/#control-plane-metrics)有您可以使用的其他 Kubernetes 指标示例，以获得更深入的了解。