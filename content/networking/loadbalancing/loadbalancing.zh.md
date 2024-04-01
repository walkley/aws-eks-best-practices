# 避免 Kubernetes 应用程序和 AWS 负载均衡器出现错误和超时

创建必需的 Kubernetes 资源（Service、Deployment、Ingress 等）后，您的 Pod 应该能够通过弹性负载均衡器从客户端接收流量。但是，当您对应用程序或 Kubernetes 环境进行更改时，可能会发现出现错误、超时或连接重置。这些更改可能会触发应用程序部署或扩缩容操作（手动或自动）。

不幸的是，即使您的应用程序没有记录问题，也可能会生成这些错误。这是因为控制集群中资源的 Kubernetes 系统可能运行速度比控制负载均衡器的目标注册和运行状况的 AWS 系统更快。您的 Pod 也可能在应用程序准备好接收请求之前就开始接收流量。

让我们回顾一下 Pod 变为就绪的过程以及如何将流量路由到 Pod。

## Pod 就绪状态

来自 [2019 年 Kubecon 演讲](https://www.youtube.com/watch?v=Vw9GmSeomFg)的这张图显示了 Pod 变为就绪并接收 `LoadBalancer` 服务流量的步骤：
![readiness.png](readiness.png)
*[Ready? A Deep Dive into Pod Readiness Gates for Service Health... - Minhan Xia & Ping Zou](https://www.youtube.com/watch?v=Vw9GmSeomFg)*
当创建作为 NodePort 服务成员的 Pod 时，Kubernetes 将执行以下步骤：

1. Pod 是在 Kubernetes 控制平面上创建的（即来自 `kubectl` 命令或缩放操作）。
2. Pod 由 `kube-scheduler` 调度并分配给集群中的一个节点。
3. 分配的节点上运行的 kubelet 将收到更新（通过 `watch`），并将与其本地容器运行时通信以启动 Pod 中指定的容器。
    1. 当容器启动运行（并且可选地通过 `ReadinessProbes`）后，kubelet 将通过向 `kube-apiserver` 发送更新来将 Pod 状态更新为 `Ready`
4. Endpoint Controller 将收到一个更新（通过 `watch`），表示有一个新的 Pod 已准备就绪，可以添加到 Service 的 Endpoints 列表中，并将把 Pod IP/端口元组添加到相应的 endpoints 数组中。
5. `kube-proxy` 收到一个更新（通过 `watch`），表示有一个新的 IP/端口需要添加到 Service 的 iptables 规则中。
    1. 工作节点上的本地 iptables 规则将使用 NodePort Service 的额外目标 Pod 进行更新。

!!! note
    当使用 Ingress 资源和 Ingress Controller（如 AWS Load Balancer Controller）时，步骤 5 由相关控制器代替 `kube-proxy` 处理。控制器将采取必要的配置步骤（如向负载均衡器注册/注销目标），以允许流量按预期流动。

[当一个 Pod 被终止](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#pod-termination)或进入非就绪状态时，会发生类似的过程。API 服务器将从控制器、kubelet 或 kubectl 客户端收到终止 Pod 的更新。步骤 3-5 将继续进行，但会从 endpoints 列表和 iptables 规则中删除 Pod IP/元组，而不是插入。

### 对 Deployments 的影响

下面是一个图表，显示了在应用程序部署触发 Pod 替换时所采取的步骤:
![deployments.png](deployments.png)
*[准备好了吗?深入探讨 Pod 就绪门控以确保服务健康状况... - Minhan Xia 和 Ping Zou](https://www.youtube.com/watch?v=Vw9GmSeomFg)*  
值得注意的是，在第一个 Pod 达到"就绪"状态之前，第二个 Pod 不会被部署。上一节中的步骤 4 和 5 也将与上述部署操作并行进行。

这意味着传播新 Pod 状态的操作可能在部署控制器继续处理下一个 Pod 时仍在进行中。由于此过程还会终止旧版本的 Pod，因此可能会导致 Pod 已达到就绪状态，但这些更改仍在传播中，而旧版本的 Pod 已被终止。

当使用来自 AWS 等云提供商的负载均衡器时，这个问题会加剧，因为上述 Kubernetes 系统默认情况下不会考虑注册时间或负载均衡器上的健康检查。**这意味着部署更新可能完全循环通过所有 Pod，但负载均衡器尚未完成对新 Pod 的健康检查或注册，这可能会导致服务中断。**

当一个 Pod 被终止时，也会出现类似的问题。根据负载均衡器的配置，Pod 可能需要一两分钟才能注销并停止接收新请求。**Kubernetes 不会为此注销延迟滚动部署，这可能会导致负载均衡器仍然将流量发送到已被终止的目标 Pod 的 IP/端口的状态。**

为了避免这些问题，我们可以添加配置，以确保 Kubernetes 系统的操作更符合 AWS 负载均衡器的行为。

## 建议

### 使用 IP 目标类型的负载均衡器

创建 `LoadBalancer` 类型服务时，流量将通过 **实例目标类型** 注册从负载均衡器发送到*集群中的任何节点*。然后每个节点将流量从 `NodePort` 重定向到服务的 Endpoints 数组中的 Pod/IP 元组，此目标可能在另一个工作节点上运行

!!! note
    请记住，该数组应该只包含"就绪"的 Pod

![nodeport.png](nodeport.png)

这为您的请求增加了一个额外的跳转，并增加了负载均衡器配置的复杂性。例如，如果上面的负载均衡器配置了会话亲和性，那么该亲和性只能在负载均衡器和后端节点之间保持(取决于亲和性配置)。

由于负载均衡器并不直接与后端 Pod 通信，因此很难控制与 Kubernetes 系统的流量流和时序。

使用 [AWS 负载均衡器控制器](https://github.com/kubernetes-sigs/aws-load-balancer-controller)时，可以使用 **IP 目标类型** 直接将 Pod IP/端口元组注册到负载均衡器:
![ip.png](ip.png)
这简化了从负载均衡器到目标 Pod 的流量路径。这意味着当注册新目标时，我们可以确保该目标是"就绪"的 Pod IP 和端口，负载均衡器的健康检查将直接命中 Pod，并且在查看 VPC 流日志或监控工具时，负载均衡器与 Pod 之间的流量将很容易跟踪。

使用 IP 注册还允许我们直接控制与后端 Pod 的流量时序和配置，而不是试图通过 `NodePort` 规则来管理连接。

### 利用 Pod 就绪门控

[Pod 就绪门控](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#pod-readiness-gate)是在允许 Pod 进入"就绪"状态之前必须满足的额外要求。

>[[...] AWS Load Balancer控制器可以在构成您的Ingress或Service后端的Pod上设置就绪状态条件。只有当ALB/NLB目标组中对应的目标显示"健康"状态时，Pod上的条件状态才会被设置为`True`。这可以防止在新创建的Pod在ALB/NLB目标组中"健康"并准备好接收流量之前，部署的滚动更新终止旧的Pod。](https://kubernetes-sigs.github.io/aws-load-balancer-controller/v2.4/deploy/pod_readiness_gate/)

就绪门控确保在部署期间创建新副本时，Kubernetes不会"移动太快",并避免出现Kubernetes已完成部署但新Pod尚未完成注册的情况。

要启用这些功能，您需要:

1. 部署最新版本的[AWS Load Balancer Controller](https://github.com/kubernetes-sigs/aws-load-balancer-controller) (**[*如果要升级旧版本，请参阅文档*](https://kubernetes-sigs.github.io/aws-load-balancer-controller/v2.4/deploy/upgrade/migrate_v1_v2/)**)
2. [为目标Pod所在的命名空间添加标签](https://kubernetes-sigs.github.io/aws-load-balancer-controller/v2.4/deploy/pod_readiness_gate/),标签为`elbv2.k8s.aws/pod-readiness-gate-inject: enabled`,以自动注入Pod就绪门控。
3. 要确保命名空间中的所有Pod都获得就绪门控配置，您需要在创建Pod之前创建Ingress或Service并为命名空间添加标签。

### 确保在终止之前从负载均衡器中注销Pod

当Pod被终止时，就绪部分的步骤4和5会与容器进程接收终止信号同时发生。这意味着，如果您的容器能够快速关闭，它可能会比负载均衡器注销目标更快。为了避免这种情况，请调整Pod规范:

1. 添加一个 `preStop` 生命周期钩子，允许应用程序注销并优雅地关闭连接。此钩子在由于 API 请求或诸如活跃性/启动探针失败、抢占、资源争用等管理事件导致容器终止之前立即被调用。关键是，[只要宽限期足够长以容纳执行，此钩子将在发送**终止信号之前**被调用并允许完成](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#pod-termination)。

```
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "sleep 180"] 
```

像上面这样的简单睡眠命令可用于在 Pod 被标记为 `Terminating`（并开始从负载均衡器注销）与向容器进程发送终止信号之间引入短暂延迟。如果需要，此钩子也可用于更高级的应用程序终止/关闭程序。

2. 扩展 `terminationGracePeriodSeconds` 以容纳整个 `prestop` 执行时间，以及您的应用程序优雅响应终止信号所需的时间。在下面的示例中，宽限期延长到 200 秒，这允许整个 `sleep 180` 命令完成，然后再额外 20 秒以确保我的应用可以优雅关闭。

```
    spec:
      terminationGracePeriodSeconds: 200
      containers:
      - name: webapp
        image: webapp-st:v1.3
        [...]
        lifecycle:
          preStop:
            exec:
              command: ["/bin/sh", "-c", "sleep 180"] 
```

### 确保 Pod 具有就绪探针

在 Kubernetes 中创建 Pod 时，默认的就绪状态是"就绪"，但大多数应用程序需要一两分钟的时间才能实例化并准备好接收请求。[您可以在 Pod 规范中定义一个 `readinessProbe`](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)，其中包含一个 exec 命令或网络请求，用于确定应用程序是否已完成启动并准备好接收流量。

使用定义了 `readinessProbe` 的 Pod 在创建时会处于"NotReady"状态，只有当 `readinessProbe` 成功时才会变为"Ready"状态。这可确保在应用程序完成启动之前不会将其置于"服务中"。

建议使用存活探针以允许在应用程序进入损坏状态时重新启动，例如死锁等情况，但对于有状态应用程序应谨慎使用，因为存活探针失败会触发应用程序重新启动。[启动探针](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/#define-startup-probes)也可用于启动缓慢的应用程序。

下面的探针使用针对端口 80 的 HTTP 探针来检查 Web 应用程序何时就绪(同样的探针配置也用于存活探针):

```
        [...]
        ports:
        - containerPort: 80
        livenessProbe:
          httpGet:
            path: /
            port: 80
          failureThreshold: 1
          periodSeconds: 10
          initialDelaySeconds: 5
        readinessProbe:
          httpGet:
            path: /
            port: 80
          periodSeconds: 5
        [...]
```

### 配置 Pod 中断预算

一个 [Pod 中断预算 (PDB)](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/#pod-disruption-budgets) 限制了在[自愿中断](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/#voluntary-and-involuntary-disruptions)期间同时停止的复制应用程序的 Pod 数量。例如，基于仲裁的应用程序希望确保运行的副本数量永远不会低于仲裁所需的数量。Web 前端可能希望确保为负载提供服务的副本数量永远不会低于总数的某个百分比。

PDB 将保护应用程序免受诸如节点排空或应用程序部署等影响。PDB 确保在执行这些操作时，至少有一定数量或百分比的 Pod 保持可用。

!!! attention
    PDB 不会保护应用程序免受主机操作系统故障或网络连接中断等非自愿中断的影响。

下面的示例确保始终至少有一个带有标签 `app: echoserver` 的 Pod 可用。[您可以为应用程序配置正确的副本数量或使用百分比](https://kubernetes.io/docs/tasks/run-application/configure-pdb/#think-about-how-your-application-reacts-to-disruptions):

```
apiVersion: policy/v1beta1
kind: PodDisruptionBudget
metadata:
  name: echoserver-pdb
  namespace: echoserver
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: echoserver
```

### 优雅地处理终止信号

当一个 pod 被终止时，容器内运行的应用程序将收到两个[信号](https://www.gnu.org/software/libc/manual/html_node/Standard-Signals.html)。第一个是 [`SIGTERM` 信号](https://www.gnu.org/software/libc/manual/html_node/Termination-Signals.html)，这是一个"礼貌"的请求进程停止执行。该信号可以被阻塞或应用程序可以简单地忽略该信号，因此在 `terminationGracePeriodSeconds` 经过后，应用程序将收到 [`SIGKILL` 信号](https://www.gnu.org/software/libc/manual/html_node/Termination-Signals.html)。`SIGKILL` 用于强制停止进程，它不能被[阻塞、处理或忽略](https://man7.org/linux/man-pages/man7/signal.7.html)，因此总是致命的。

这些信号由容器运行时用于触发应用程序关闭。`SIGTERM` 信号也将在 `preStop` 钩子执行**之后**发送。使用上述配置，`preStop` 钩子将确保 pod 已从负载均衡器中注销，因此当收到 `SIGTERM` 信号时，应用程序可以正常关闭任何剩余的打开连接。

!!! note
    [在使用"包装脚本"作为应用程序入口点的容器环境中处理信号可能会很复杂](https://petermalmgren.com/signal-handling-docker/)，因为脚本将是 PID 1，可能不会将信号转发给应用程序。


### 当心注销延迟

Elastic Load Balancing 停止向正在注销的目标发送请求。默认情况下，Elastic Load Balancing 在完成注销过程之前等待 300 秒，这有助于完成发往目标的正在进行的请求。要更改 Elastic Load Balancing 等待的时间，请更新注销延迟值。
正在注销的目标的初始状态为 `draining`。注销延迟过期后，注销过程完成，目标的状态为 `unused`。如果目标是自动伸缩组的一部分，它可以被终止并替换。

如果正在注销的目标没有正在进行的请求和活动连接，Elastic Load Balancing 会立即完成注销过程，而不会等待注销延迟过期。

!!! attention
    即使目标注销已完成，目标的状态将显示为 `draining`,直到注销延迟超时过期。超时过期后，目标将转换为 `unused` 状态。

[如果正在注销的目标在注销延迟过期之前终止连接，客户端将收到 500 级错误响应](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-target-groups.html#deregistration-delay)。

可以使用 Ingress 资源上的注释[`alb.ingress.kubernetes.io/target-group-attributes` 注释](https://kubernetes-sigs.github.io/aws-load-balancer-controller/v2.4/guide/ingress/annotations/#target-group-attributes)进行配置。示例:

```
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: echoserver-ip
  namespace: echoserver
  annotations:
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/load-balancer-name: echoserver-ip
    alb.ingress.kubernetes.io/target-group-attributes: deregistration_delay.timeout_seconds=30
spec:
  ingressClassName: alb
  rules:
    - host: echoserver.example.com
      http:
        paths:
          - path: /
            pathType: Exact
            backend:
              service:
                name: echoserver-service
                port:
                  number: 8080
```