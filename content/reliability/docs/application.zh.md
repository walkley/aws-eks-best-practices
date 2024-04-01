# 运行高可用性应用程序

您的客户期望您的应用程序随时可用，包括在您进行更改时，尤其是在流量高峰期间。可扩展且有弹性的架构可确保您的应用程序和服务持续运行而不中断，从而让您的用户满意。可扩展的基础架构可根据业务需求进行扩展和缩减。消除单点故障是提高应用程序可用性和弹性的关键一步。

通过Kubernetes，您可以以高度可用和有弹性的方式运行和操作应用程序。它的声明式管理可确保一旦设置了应用程序，Kubernetes将不断尝试[使当前状态与期望状态相匹配](https://kubernetes.io/docs/concepts/architecture/controller/#desired-vs-current)。

## 建议

### 避免运行单个Pod

如果您的整个应用程序在单个Pod中运行，那么如果该Pod被终止，您的应用程序将无法使用。不要使用单个Pod部署应用程序，而是创建[Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)。如果由Deployment创建的Pod失败或被终止，Deployment [控制器](https://kubernetes.io/docs/concepts/architecture/controller/)将启动一个新的Pod，以确保始终运行指定数量的副本Pod。

### 运行多个副本

使用Deployment运行应用程序的多个副本Pod有助于以高度可用的方式运行。如果一个副本失败，其余副本将继续运行，尽管容量会降低，直到Kubernetes创建另一个Pod来弥补损失。此外，您可以使用[Horizontal Pod Autoscaler](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)根据工作负载需求自动扩展副本。

### 跨节点调度副本

如果所有副本都运行在同一个节点上，而该节点变得不可用，那么运行多个副本就没有太大用处了。请考虑使用pod反亲和性或pod拓扑分布约束，将Deployment的副本分散到多个工作节点上。

您还可以通过跨多个可用区运行应用程序来进一步提高典型应用程序的可靠性。

#### 使用Pod反亲和性规则

下面的清单告诉Kubernetes调度器*优先*将pod放置在不同的节点和可用区。它不要求使用不同的节点或可用区，因为如果这样做，一旦每个可用区都有一个pod在运行，Kubernetes就无法再调度任何pod了。如果您的应用程序只需要三个副本，您可以对`topologyKey: topology.kubernetes.io/zone`使用`requiredDuringSchedulingIgnoredDuringExecution`,Kubernetes调度器将不会在同一个可用区调度两个pod。

```
apiVersion: apps/v1
kind: Deployment
metadata:
  name: spread-host-az
  labels:
    app: web-server
spec:
  replicas: 4
  selector:
    matchLabels:
      app: web-server
  template:
    metadata:
      labels:
        app: web-server
    spec:
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values:
                  - web-server
              topologyKey: topology.kubernetes.io/zone
            weight: 100
          - podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values:
                  - web-server
              topologyKey: kubernetes.io/hostname 
            weight: 99
      containers:
      - name: web-app
        image: nginx:1.16-alpine
```

#### 使用Pod拓扑分布约束

与 pod 反亲和规则类似，pod 拓扑分布约束允许您使应用程序跨不同的故障(或拓扑)域(如主机或可用区)可用。当您试图通过在每个不同的拓扑域中拥有多个副本来确保容错性和可用性时，这种方法效果很好。另一方面，pod 反亲和规则很容易产生一个在拓扑域中只有一个副本的结果，因为彼此具有反亲和性的 pod 具有排斥效应。在这种情况下，专用节点上的单个副本对于容错性并不理想，也不是资源的良好利用。使用拓扑分布约束，您可以更好地控制调度程序应该尝试在拓扑域之间应用的分布或分布。在这种方法中，以下是一些重要的属性:

1. `maxSkew` 用于控制或确定跨拓扑域的最大不均衡程度。例如，如果一个应用程序有 10 个副本并部署在 3 个可用区，您无法获得均匀的分布，但可以影响分布的不均衡程度。在这种情况下，`maxSkew` 可以是 1 到 10 之间的任何值。值为 1 意味着您可能最终会在 3 个可用区之间获得 `4,3,3`、`3,4,3` 或 `3,3,4` 的分布。相比之下，值为 10 意味着您可能最终会在 3 个可用区之间获得 `10,0,0`、`0,10,0` 或 `0,0,10` 的分布。
2. `topologyKey` 是节点标签之一的键，定义了应该用于 pod 分布的拓扑域类型。例如，区域分布将具有以下键值对:
```
topologyKey: "topology.kubernetes.io/zone"
```
3. `whenUnsatisfiable` 属性用于确定如果无法满足所需约束时您希望调度程序如何响应。
4. `labelSelector` 用于查找匹配的 pod，以便调度程序在根据您指定的约束决定放置 pod 的位置时可以了解它们。

除了上述内容外，您还可以在 [Kubernetes 文档](https://kubernetes.io/docs/concepts/scheduling-eviction/topology-spread-constraints/)中进一步阅读其他字段。

![跨3个可用区的 Pod 拓扑分布约束](./images/pod-topology-spread-constraints.jpg)

```
apiVersion: apps/v1
kind: Deployment
metadata:
  name: spread-host-az
  labels:
    app: web-server
spec:
  replicas: 10
  selector:
    matchLabels:
      app: web-server
  template:
    metadata:
      labels:
        app: web-server
    spec:
      topologySpreadConstraints:
      - maxSkew: 1
        topologyKey: "topology.kubernetes.io/zone"
        whenUnsatisfiable: ScheduleAnyway
        labelSelector:
          matchLabels:
            app: express-test
      containers:
      - name: web-app
        image: nginx:1.16-alpine
```

### 运行 Kubernetes Metrics Server

安装 Kubernetes [metrics server](https://github.com/kubernetes-sigs/metrics-server) 以帮助扩展您的应用程序。Kubernetes 自动扩缩器插件如 [HPA](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/) 和 [VPA](https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler) 需要跟踪应用程序的指标以对其进行扩缩。metrics-server 收集可用于做出扩缩决策的资源指标。这些指标是从 kubelets 收集的，并以 [Metrics API 格式](https://github.com/kubernetes/metrics)提供服务。

metrics server 不会保留任何数据，它也不是一种监控解决方案。它的目的是向其他系统公开 CPU 和内存使用情况指标。如果您想跟踪应用程序的状态随时间的变化，您需要一个监控工具，如 Prometheus 或 Amazon CloudWatch。

请按照 [EKS 文档](https://docs.aws.amazon.com/eks/latest/userguide/metrics-server.html)在您的 EKS 集群中安装 metrics-server。

## 水平 Pod 自动缩放器 (HPA)

HPA 可以根据需求自动扩缩您的应用程序，并在高峰流量期间帮助您避免影响客户。它作为 Kubernetes 中的一个控制循环实现，定期从提供资源指标的 API 查询指标。

HPA 可以从以下 API 获取指标:
1. `metrics.k8s.io` 也称为资源指标 API - 提供 Pod 的 CPU 和内存使用情况
2. `custom.metrics.k8s.io` - 从其他指标收集器(如 Prometheus)提供指标;这些指标是__内部__的，属于您的 Kubernetes 集群。
3. `external.metrics.k8s.io` - 提供__外部__于您的 Kubernetes 集群的指标(例如，SQS 队列深度、ELB 延迟)。

您必须使用这三个 API 中的一个来提供指标，以扩缩您的应用程序。

### 基于自定义或外部指标扩缩应用程序

您可以使用自定义或外部指标来扩缩应用程序，而不是基于 CPU 或内存利用率。[自定义指标](https://github.com/kubernetes-sigs/custom-metrics-apiserver) API 服务器提供 HPA 可用于自动扩缩应用程序的 `custom-metrics.k8s.io` API。

您可以使用 [Kubernetes 指标 API 的 Prometheus 适配器](https://github.com/directxman12/k8s-prometheus-adapter)从 Prometheus 收集指标并与 HPA 一起使用。在这种情况下，Prometheus 适配器将以 [指标 API 格式](https://github.com/kubernetes/metrics/blob/master/pkg/apis/metrics/types.go)公开 Prometheus 指标。

部署 Prometheus 适配器后，您可以使用 kubectl 查询自定义指标。
`kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1/`

顾名思义，外部指标为水平 Pod 自动缩放器提供了使用外部于 Kubernetes 集群的指标来扩缩部署的能力。例如，在批处理工作负载中，通常会根据 SQS 队列中的作业数量来扩缩副本数量。

要使用 CloudWatch 指标自动扩缩一个 Deployment，例如[基于 SQS 队列深度扩缩批处理应用程序](https://github.com/awslabs/k8s-cloudwatch-adapter/blob/master/samples/sqs/README.md)，你可以使用 [`k8s-cloudwatch-adapter`](https://github.com/awslabs/k8s-cloudwatch-adapter)。`k8s-cloudwatch-adapter` 是一个社区项目，并非由 AWS 维护。

## 垂直 Pod 自动缩放器 (VPA)

VPA 会自动调整你的 Pod 的 CPU 和内存预留，帮助你"正确调整"应用程序的规模。对于需要垂直扩缩的应用程序 - 通过增加资源分配来实现 - 你可以使用 [VPA](https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler) 自动扩缩 Pod 副本或提供扩缩建议。

如果 VPA 需要扩缩你的应用程序，你的应用程序可能会暂时不可用，因为 VPA 当前的实现不会对 Pod 进行就地调整；相反，它会重新创建需要扩缩的 Pod。

[EKS 文档](https://docs.aws.amazon.com/eks/latest/userguide/vertical-pod-autoscaler.html)包含了设置 VPA 的演练。

[Fairwinds Goldilocks](https://github.com/FairwindsOps/goldilocks/) 项目提供了一个仪表板，用于可视化 VPA 对 CPU 和内存请求和限制的建议。它的 VPA 更新模式允许你根据 VPA 建议自动扩缩 Pod。

## 更新应用程序

现代应用程序需要在高度稳定和可用的情况下快速创新。Kubernetes 为你提供了工具，可以持续更新应用程序而不会影响客户。

让我们来看看一些使快速部署变更而不牺牲可用性成为可能的最佳实践。

### 拥有执行回滚的机制

拥有撤销按钮可以避免灾难性事故。在更新生产集群之前，最佳实践是在单独的较低环境(测试或开发环境)中测试部署。使用CI/CD管道可以帮助您自动化和测试部署。通过持续部署管道，如果升级出现缺陷，您可以快速恢复到旧版本。

您可以使用Deployment来更新正在运行的应用程序。这通常是通过更新容器镜像来完成的。您可以使用`kubectl`来更新Deployment，如下所示:

```bash
kubectl --record deployment.apps/nginx-deployment set image nginx-deployment nginx=nginx:1.16.1
```

`--record`参数记录对Deployment的更改，如果您需要执行回滚，这将很有帮助。`kubectl rollout history deployment`向您显示集群中记录的Deployment更改。您可以使用`kubectl rollout undo deployment <DEPLOYMENT_NAME>`回滚更改。

默认情况下，当您更新需要重新创建Pod的Deployment时，Deployment将执行[滚动更新](https://kubernetes.io/docs/tutorials/kubernetes-basics/update/update-intro/)。换句话说，Kubernetes将只更新Deployment中运行的一部分Pod，而不是所有Pod。您可以通过`RollingUpdateStrategy`属性控制Kubernetes执行滚动更新的方式。

在执行Deployment的*滚动更新*时，您可以使用[`Max Unavailable`](https://kubernetes.io/docs/tutorials/kubernetes-basics/update/update-intro/)属性指定更新期间可以不可用的最大Pod数量。Deployment的`Max Surge`属性允许您设置可以超过所需Pod数量创建的最大Pod数量。

考虑调整 `max unavailable` 以确保滚动更新不会中断客户。例如，Kubernetes 默认设置 `max unavailable` 为 25%，这意味着如果你有 100 个 Pod，在滚动更新期间可能只有 75 个 Pod 处于活跃状态。如果你的应用程序需要至少 80 个 Pod，这种滚动更新可能会造成中断。相反，你可以将 `max unavailable` 设置为 20%，以确保在整个滚动更新过程中至少有 80 个功能性 Pod。

### 使用蓝/绿部署

变更本身就存在风险，但无法撤销的变更可能会带来灾难性后果。允许你通过 *回滚* 有效地倒回时间的变更程序使得增强和实验更加安全。蓝/绿部署为你提供了一种在出现问题时快速撤销变更的方法。在这种部署策略中，你为新版本创建一个环境。这个环境与正在更新的应用程序的当前版本完全相同。一旦新环境被配置好，流量就会被路由到新环境。如果新版本产生了预期的结果而没有生成错误，旧环境就会被终止。否则，流量将恢复到旧版本。

你可以在 Kubernetes 中通过创建一个与现有版本的 Deployment 完全相同的新 Deployment 来执行蓝/绿部署。一旦你验证新 Deployment 中的 Pod 运行没有错误，你就可以通过更改路由流量到你应用程序 Pod 的 Service 中的 `selector` 规范来开始向新 Deployment 发送流量。

许多持续集成工具如 [Flux](https://fluxcd.io)、[Jenkins](https://www.jenkins.io) 和 [Spinnaker](https://spinnaker.io) 都允许你自动化蓝/绿部署。AWS Containers Blog 包含了使用 AWS Load Balancer Controller 的演练: [使用 AWS Load Balancer Controller 进行蓝/绿部署、金丝雀部署和 A/B 测试](https://aws.amazon.com/blogs/containers/using-aws-load-balancer-controller-for-blue-green-deployment-canary-deployment-and-a-b-testing/)

### 使用金丝雀部署

金丝雀部署是蓝/绿部署的一种变体，可以显著降低变更带来的风险。在这种部署策略中，你会在旧的 Deployment 旁边创建一个新的 Deployment，其中包含较少的 Pod，并将少量流量分配给新的 Deployment。如果指标显示新版本的性能与现有版本一样好或更好，你就可以逐步增加新 Deployment 的流量，同时扩展它，直到所有流量都被分配到新的 Deployment。如果出现问题，你可以将所有流量路由到旧的 Deployment，并停止向新的 Deployment 发送流量。

尽管 Kubernetes 没有原生的方式来执行金丝雀部署，但你可以使用诸如 [Flagger](https://github.com/weaveworks/flagger) 与 [Istio](https://docs.flagger.app/tutorials/istio-progressive-delivery) 或 [App Mesh](https://docs.flagger.app/install/flagger-install-on-eks-appmesh) 等工具。

## 健康检查和自我修复

任何软件都难免有 bug，但 Kubernetes 可以帮助你最小化软件故障的影响。过去，如果应用程序崩溃，就必须手动重启应用程序来修复。Kubernetes 让你能够检测 Pod 中的软件故障，并自动用新的副本替换它们。使用 Kubernetes，你可以监控应用程序的健康状况，并自动替换不健康的实例。

Kubernetes 支持三种[健康检查](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)：

1. 存活探针
2. 启动探针 (Kubernetes 1.16+ 版本支持)
3. 就绪探针

[Kubelet](https://kubernetes.io/docs/reference/command-line-tools-reference/kubelet/)，Kubernetes 代理，负责运行所有上述检查。Kubelet 可以通过三种方式检查 Pod 的健康状况：kubelet 可以在 Pod 的容器内运行 shell 命令、向其容器发送 HTTP GET 请求或在指定端口打开 TCP 套接字。

如果选择基于 `exec` 的探针（在容器内运行 shell 脚本），请确保 shell 命令在 `timeoutSeconds` 值过期之前退出。否则，您的节点将有 `<defunct>` 进程，导致节点故障。

## 建议
### 使用存活探针移除不健康的 Pod

存活探针可以检测*死锁*情况，即进程继续运行但应用程序变得无响应。例如，如果您运行的是在端口 80 上侦听的 Web 服务，您可以配置存活探针向 Pod 的端口 80 发送 HTTP GET 请求。Kubelet 将定期向 Pod 发送 GET 请求并期望响应；如果 Pod 响应在 200-399 之间，则 kubelet 认为该 Pod 是健康的；否则，该 Pod 将被标记为不健康。如果 Pod 连续失败健康检查，kubelet 将终止它。

您可以使用 `initialDelaySeconds` 来延迟第一次探测。

在使用存活探针时，请确保您的应用程序不会出现所有Pod同时失败存活探针的情况，因为Kubernetes将尝试替换所有Pod，从而使您的应用程序离线。此外，Kubernetes将继续创建新的Pod，这些Pod也将失败存活探针，给控制平面带来不必要的压力。避免将存活探针配置为依赖于Pod外部的因素，例如外部数据库。换句话说，无响应的外部数据库不应使您的Pod失败存活探针。

Sandor Szücs的帖子[存活探针是危险的](https://srcco.de/posts/kubernetes-liveness-probes-are-dangerous.html)描述了由于配置错误的探针可能导致的问题。

### 对于启动时间较长的应用程序使用启动探针

当您的应用程序需要额外的时间启动时，您可以使用启动探针来延迟存活探针和就绪探针。例如，需要从数据库中加载缓存的Java应用程序可能需要长达两分钟才能完全启动。在完全启动之前，任何存活或就绪探针都可能失败。配置启动探针将允许Java应用程序在执行存活或就绪探针之前变为"健康"状态。

在启动探针成功之前，所有其他探针都将被禁用。您可以定义Kubernetes应该等待应用程序启动的最长时间。如果在配置的最长时间后，Pod仍然失败启动探针，它将被终止，并创建一个新的Pod。

启动探针类似于存活探针 - 如果它们失败，则会重新创建Pod。正如Ricardo A.在他的帖子[Fantastic Probes And How To Configure Them](https://medium.com/swlh/fantastic-probes-and-how-to-configure-them-fef7e030bd2f)中解释的那样，当应用程序的启动时间不可预测时，应该使用启动探针。如果你知道你的应用程序需要10秒钟才能启动，你应该使用带有`initialDelaySeconds`的存活/就绪探针。

### 使用就绪探针检测部分不可用性

虽然存活探针检测应用程序中通过终止Pod(因此，重新启动应用程序)来解决的故障，但就绪探针检测应用程序可能暂时不可用的情况。在这些情况下，应用程序可能会暂时无响应;但是，一旦此操作完成，它就会再次变得健康。

例如，在密集的磁盘I/O操作期间，应用程序可能暂时无法处理请求。在这种情况下，终止应用程序的Pod并不是一种补救措施;同时，发送到Pod的额外请求也可能失败。

你可以使用就绪探针来检测应用程序中的临时不可用性，并停止向其Pod发送请求，直到它再次可用为止。与存活探针不同，存活探针失败会导致重新创建Pod，而就绪探针失败意味着Pod将不会从Kubernetes服务接收任何流量。当就绪探针成功时，Pod将恢复从服务接收流量。

就像存活探针一样，避免配置依赖于Pod外部资源(如数据库)的就绪探针。这里有一个场景，配置不当的就绪探针可能会导致应用程序无法正常工作 - 如果Pod的就绪探针在应用程序的数据库无法访问时失败，其他Pod副本也将同时失败，因为它们共享相同的健康检查标准。以这种方式设置探针将确保每当数据库不可用时，Pod的就绪探针将失败，并且Kubernetes将停止向*所有*Pod发送流量。

使用就绪探针的一个副作用是，它们可能会增加更新Deployment所需的时间。新副本将不会接收流量，除非就绪探针成功;在此之前，旧副本将继续接收流量。

---

## 处理中断

Pod有有限的生命周期 - 即使您有长期运行的Pod，也应确保Pod在到期时正确终止。根据您的升级策略，Kubernetes集群升级可能需要您创建新的工作节点，这需要在较新的节点上重新创建所有Pod。正确的终止处理和Pod中断预算可以帮助您避免在从旧节点删除Pod并在较新节点上重新创建Pod时出现服务中断。

首选的升级工作节点的方式是创建新的工作节点并终止旧的节点。在终止工作节点之前，你应该先`drain`它。当一个工作节点被drained时，它上面的所有pods都会被*安全地*逐出。这里的"安全"是关键词;当一个工作节点上的pods被逐出时，它们不会简单地收到一个`SIGKILL`信号。相反，每个被逐出的Pod中的每个容器的主进程(PID 1)都会收到一个`SIGTERM`信号。在发送`SIGTERM`信号之后，Kubernetes会给进程一些时间(宽限期),然后再发送`SIGKILL`信号。默认的宽限期是30秒;你可以使用kubectl中的`grace-period`标志或在你的Podspec中声明`terminationGracePeriodSeconds`来覆盖默认值。

`kubectl delete pod <pod名称> --grace-period=<秒数>`

在容器中，主进程没有PID 1是很常见的情况。考虑这个基于Python的示例容器:

```
$ kubectl exec python-app -it ps
 PID USER TIME COMMAND
 1   root 0:00 {script.sh} /bin/sh ./script.sh
 5   root 0:00 python app.py
```

在这个例子中，shell脚本收到了`SIGTERM`,而主进程(在这个例子中是一个Python应用程序)没有收到`SIGTERM`信号。当Pod被终止时，Python应用程序将被粗暴地杀死。可以通过更改容器的[`ENTRYPOINT`](https://docs.docker.com/engine/reference/builder/#entrypoint)来启动Python应用程序来解决这个问题。或者，你可以使用像[dumb-init](https://github.com/Yelp/dumb-init)这样的工具来确保你的应用程序可以处理信号。

您也可以使用 [Container hooks](https://kubernetes.io/docs/concepts/containers/container-lifecycle-hooks/#container-hooks) 在容器启动或停止时执行脚本或 HTTP 请求。`PreStop` 钩子操作在容器收到 `SIGTERM` 信号之前运行，并且必须在发送此信号之前完成。`terminationGracePeriodSeconds` 值适用于从 `PreStop` 钩子操作开始执行时，而不是从发送 `SIGTERM` 信号时开始计算。

## 建议

### 使用 Pod 中断预算保护关键工作负载

Pod 中断预算或 PDB 可以在应用程序的副本数量低于声明的阈值时暂时中止驱逐进程。一旦可用副本数量超过阈值，驱逐进程将继续进行。您可以使用 PDB 来声明 `minAvailable` 和 `maxUnavailable` 副本数量。例如，如果您希望至少有三个应用程序副本可用，您可以创建一个 PDB。

```
apiVersion: policy/v1beta1
kind: PodDisruptionBudget
metadata:
  name: my-svc-pdb
spec:
  minAvailable: 3
  selector:
    matchLabels:
      app: my-svc
```

上述 PDB 策略告诉 Kubernetes 在三个或更多副本可用之前暂停驱逐进程。节点排空操作遵守 `PodDisruptionBudgets`。在 EKS 托管节点组升级期间，[节点会在十五分钟超时后被排空](https://docs.aws.amazon.com/eks/latest/userguide/managed-node-update-behavior.html)。十五分钟后，如果更新未被强制执行(在 EKS 控制台中称为滚动更新),则更新将失败。如果强制执行更新，则会删除 Pod。

对于自管理节点，您还可以使用诸如 [AWS Node Termination Handler](https://github.com/aws/aws-node-termination-handler) 之类的工具，它可确保 Kubernetes 控制平面对可能导致您的 EC2 实例变得不可用的事件(如 [EC2 维护](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/monitoring-instances-status-check_sched.html)事件和 [EC2 Spot 中断](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-interruptions.html))做出适当响应。它使用 Kubernetes API 来隔离节点，确保不会在其上调度新的 Pod，然后将其排空，终止任何正在运行的 Pod。

您可以使用 Pod 反亲和性来调度 Deployment 的 Pod 到不同节点，并在节点升级期间避免与 PDB 相关的延迟。

### 实践混沌工程
> 混沌工程是一种在分布式系统上进行实验的学科，目的是建立对系统在生产环境中抵御动荡条件的能力的信心。

在他的博客中，Dominik Tornow 解释说 [Kubernetes 是一个声明式系统](https://medium.com/@dominik.tornow/the-mechanics-of-kubernetes-ac8112eaa302),*"用户向系统提供系统所需状态的表示。然后，系统会考虑当前状态和所需状态，以确定从当前状态过渡到所需状态的命令序列。"* 这意味着 Kubernetes 始终存储 *所需状态*,如果系统偏离，Kubernetes 将采取行动恢复状态。例如，如果工作节点变得不可用，Kubernetes 将重新调度 Pod 到另一个工作节点。同样，如果一个 `replica` 崩溃，则 [Deployment Controller](https://kubernetes.io/docs/concepts/architecture/controller/#design) 将创建一个新的 `replica`。通过这种方式，Kubernetes 控制器会自动修复故障。

混沌工程工具如 [Gremlin](https://www.gremlin.com) 可帮助您测试 Kubernetes 集群的弹性并识别单点故障。在集群(及更远范围)中引入人为混乱的工具可以发现系统性弱点、发现瓶颈和错误配置的机会，并在受控环境中纠正问题。混沌工程理念主张故意破坏和压力测试基础设施，以最大程度减少意外停机时间。

### 使用服务网格

您可以使用服务网格来提高应用程序的弹性。服务网格支持服务间通信，并增加了微服务网络的可观察性。大多数服务网格产品的工作方式是在每个服务旁运行一个小型网络代理，用于拦截和检查应用程序的网络流量。您可以将应用程序置于网格中而无需修改应用程序。使用服务代理的内置功能，您可以让它生成网络统计数据、创建访问日志，并为分布式跟踪向出站请求添加 HTTP 标头。

服务网格可以通过自动重试请求、超时、断路器和速率限制等功能帮助您提高微服务的弹性。

如果您运行多个集群，可以使用服务网格实现跨集群的服务间通信。

### 服务网格
+ [AWS App Mesh](https://aws.amazon.com/app-mesh/)
+ [Istio](https://istio.io)
+ [LinkerD](http://linkerd.io)
+ [Consul](https://www.consul.io)

---

## 可观察性

可观察性是一个包括监控、日志记录和跟踪在内的总括术语。基于微服务的应用程序本质上是分布式的。与单体应用程序只需监控单个系统不同，在分布式应用程序架构中，您需要监控每个组件的性能。您可以使用集群级监控、日志记录和分布式跟踪系统来识别集群中可能影响客户的问题。

Kubernetes内置的故障排查和监控工具有限。metrics-server收集资源指标并将其存储在内存中，但不会持久化。您可以使用kubectl查看Pod的日志，但Kubernetes不会自动保留日志。分布式跟踪的实现要么在应用程序代码级别完成，要么使用服务网格。

Kubernetes的可扩展性在这里展现出来。Kubernetes允许您引入首选的集中式监控、日志记录和跟踪解决方案。

## 建议

### 监控您的应用程序

您需要监控的现代应用程序指标数量不断增长。如果您有一种自动化的方式来跟踪您的应用程序，那就可以专注于解决客户的挑战。像 [Prometheus](https://prometheus.io) 或 [CloudWatch Container Insights](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/ContainerInsights.html) 这样的集群范围监控工具可以监控您的集群和工作负载，并在出现问题时或更好的是在出现问题之前向您发出信号。

监控工具允许您创建运营团队可以订阅的警报。考虑为可能导致中断或影响应用程序性能的事件激活警报的规则。

如果您不确定应该监控哪些指标，可以从以下方法中获取灵感:

- [RED 方法](https://www.weave.works/blog/a-practical-guide-from-instrumenting-code-to-specifying-alerts-with-the-red-method)。代表请求、错误和持续时间。
- [USE 方法](http://www.brendangregg.com/usemethod.html)。代表利用率、饱和度和错误。

Sysdig 的文章[Kubernetes 最佳警报实践](https://sysdig.com/blog/alerting-kubernetes/)包含了一个可能影响应用程序可用性的全面组件列表。

### 使用 Prometheus 客户端库暴露应用程序指标

除了监控应用程序状态和聚合标准指标外，您还可以使用 [Prometheus 客户端库](https://prometheus.io/docs/instrumenting/clientlibs/)暴露特定于应用程序的自定义指标，以提高应用程序的可观察性。

### 使用集中式日志工具收集和持久化日志

EKS 中的日志分为两类:控制平面日志和应用程序日志。EKS 控制平面日志直接从控制平面提供审计和诊断日志到您账户中的 CloudWatch Logs。应用程序日志是 Pod 在集群内运行时产生的日志。应用程序日志包括运行业务逻辑应用程序的 Pod 产生的日志，以及 Kubernetes 系统组件(如 CoreDNS、集群自动扩缩器、Prometheus 等)产生的日志。

[EKS 提供五种类型的控制平面日志](https://docs.aws.amazon.com/eks/latest/userguide/control-plane-logs.html):

1. Kubernetes API 服务器组件日志
2. 审计
3. 身份验证器
4. 控制器管理器
5. 调度器

控制器管理器和调度器日志可帮助诊断控制平面问题，如瓶颈和错误。默认情况下，EKS 控制平面日志不会发送到 CloudWatch Logs。您可以为账户中的每个集群启用控制平面日志记录，并选择要捕获的 EKS 控制平面日志类型

收集应用程序日志需要在集群中安装日志聚合工具，如 [Fluent Bit](http://fluentbit.io)、[Fluentd](https://www.fluentd.org) 或 [CloudWatch Container Insights](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/deploy-container-insights-EKS.html)。

Kubernetes 日志聚合工具以 DaemonSet 的形式运行，并从节点中抓取容器日志。应用程序日志随后被发送到集中的目的地进行存储。例如，CloudWatch Container Insights 可以使用 Fluent Bit 或 Fluentd 收集日志并将它们发送到 CloudWatch Logs 进行存储。Fluent Bit 和 Fluentd 支持许多流行的日志分析系统，如 Elasticsearch 和 InfluxDB，让您能够通过修改 Fluent Bit 或 Fluentd 的日志配置来更改日志的存储后端。

### 使用分布式跟踪系统识别瓶颈

典型的现代应用程序的组件分布在网络上，其可靠性取决于构成应用程序的每个组件的正常运行。您可以使用分布式跟踪解决方案来了解请求的流向以及系统如何进行通信。跟踪可以显示您的应用程序网络中存在瓶颈的位置，并防止可能导致级联故障的问题。

您有两种选择来在应用程序中实现跟踪：您可以使用共享库在代码级别实现分布式跟踪，或使用服务网格。

在代码级别实现跟踪可能存在缺点。在这种方法中，您必须对代码进行更改。如果您有多语言应用程序，这将变得更加复杂。您还需要负责维护跨服务的另一个库。

像 [LinkerD](http://linkerd.io)、[Istio](http://istio.io) 和 [AWS App Mesh](https://aws.amazon.com/app-mesh/) 这样的服务网格可用于在您的应用程序中实现分布式跟踪，而无需对应用程序代码进行大量更改。您可以使用服务网格来标准化指标生成、日志记录和跟踪。

像 [AWS X-Ray](https://aws.amazon.com/xray/) 和 [Jaeger](https://www.jaegertracing.io) 这样的跟踪工具支持共享库和服务网格实现。

考虑使用像 [AWS X-Ray](https://aws.amazon.com/xray/) 或 [Jaeger](https://www.jaegertracing.io) 这样同时支持共享库和服务网格实现的跟踪工具，这样即使以后采用服务网格，您也不必更换工具。