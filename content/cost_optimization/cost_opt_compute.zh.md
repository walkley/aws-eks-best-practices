---
date: 2023-09-29
authors: 
  - Justin Garrison
  - Rajdeep Saha
---
# 成本优化 - 计算和自动扩缩

作为开发人员，您将对应用程序的资源需求（如CPU和内存）进行估计，但如果您不持续调整它们，它们可能会过时，从而增加成本并降低性能和可靠性。持续调整应用程序的资源需求比一开始就设置正确更为重要。

下面提到的最佳实践将帮助您构建和运行成本意识型工作负载，实现业务目标的同时最小化成本，让您的组织最大限度地实现投资回报。优化集群计算成本的高级重要性顺序为：

1. 正确调整工作负载大小
2. 减少未使用的容量
3. 优化计算容量类型（如Spot）和加速器（如GPU）

## 正确调整工作负载大小

在大多数EKS集群中，大部分成本来自用于运行容器化工作负载的EC2实例。如果不了解工作负载需求，您将无法正确调整计算资源大小。这就是为什么使用适当的请求和限制并根据需要对这些设置进行调整非常重要。此外，依赖项（如实例大小和存储选择）可能会影响工作负载性能，从而对成本和可靠性产生各种意外后果。

*请求*应与实际利用率相一致。如果容器的请求过高，将会产生未使用的容量，这是总集群成本的一个重要因素。每个pod中的每个容器（如应用程序和sidecar）都应该有自己的请求和限制设置，以确保pod的总限制尽可能准确。

利用诸如 [Goldilocks](https://www.youtube.com/watch?v=DfmQWYiwFDk)、[KRR](https://www.youtube.com/watch?v=uITOzpf82RY) 和 [Kubecost](https://aws.amazon.com/blogs/containers/aws-and-kubecost-collaborate-to-deliver-cost-monitoring-for-eks-customers/) 等工具来估算容器的资源请求和限制。根据应用程序的性质、性能/成本要求和复杂性，您需要评估最佳的扩缩容指标、应用程序性能开始下降的饱和点，以及如何相应地调整请求和限制。有关此主题的更多指导，请参阅[应用程序正确调整大小](https://aws.github.io/aws-eks-best-practices/scalability/docs/node_efficiency/#application-right-sizing)。

我们建议使用 Horizontal Pod Autoscaler (HPA) 来控制应该运行多少副本的应用程序，使用 Vertical Pod Autoscaler (VPA) 来调整每个副本所需的请求和限制，以及使用诸如 [Karpenter](http://karpenter.sh/) 或 [Cluster Autoscaler](https://github.com/kubernetes/autoscaler) 之类的节点自动扩缩器来持续调整集群中的节点总数。本文档后面的部分记录了使用 Karpenter 和 Cluster Autoscaler 进行成本优化的技术。

Vertical Pod Autoscaler 可以调整分配给容器的请求和限制，以使工作负载以最佳方式运行。您应该在审核模式下运行 VPA，这样它不会自动进行更改和重新启动您的 Pod。它将根据观察到的指标建议进行更改。对于影响生产工作负载的任何更改，您都应该首先在非生产环境中审查和测试这些更改，因为这些更改可能会影响应用程序的可靠性和性能。

## 减少消耗

节省成本的最佳方式是减少资源配置。实现这一目标的一种方式是根据当前需求调整工作负载。您应该从确保工作负载定义了其需求并能够动态扩展开始成本优化工作。这需要从应用程序获取指标，并设置诸如 [`PodDisruptionBudgets`](https://kubernetes.io/docs/tasks/run-application/configure-pdb/) 和 [Pod Readiness Gates](https://kubernetes-sigs.github.io/aws-load-balancer-controller/v2.5/deploy/pod_readiness_gate/) 等配置，以确保您的应用程序可以安全地动态扩展和缩减。

Horizontal Pod Autoscaler 是一种灵活的工作负载自动扩缩器，可以根据 CPU、内存或自定义指标(如队列深度、与 Pod 的连接数等)等各种指标来调整副本数量，以满足应用程序的性能和可靠性要求。

Kubernetes Metrics Server 支持根据内置指标(如 CPU 和内存使用情况)进行扩缩，但如果您想根据其他指标(如 Amazon CloudWatch 或 SQS 队列深度)进行扩缩，您应该考虑使用事件驱动的自动扩缩项目，如 [KEDA](https://keda.sh/)。请参阅[此博客文章](https://aws.amazon.com/blogs/mt/proactive-autoscaling-of-kubernetes-workloads-with-keda-using-metrics-ingested-into-amazon-cloudwatch/),了解如何将 KEDA 与 CloudWatch 指标一起使用。如果您不确定要监控和扩缩哪些指标，请查看[关于监控重要指标的最佳实践](https://aws-observability.github.io/observability-best-practices/guides/#monitor-what-matters)。

减少工作负载消耗可以在集群中创建过剩容量，并通过合适的自动扩缩容配置，允许您自动缩减节点并降低总体支出。我们建议您不要尝试手动优化计算容量。Kubernetes调度程序和节点自动扩缩容器被设计为为您处理此过程。

## 减少未使用的容量

在确定了应用程序的正确大小并减少了过多的请求后，您可以开始减少已配置的计算容量。如果您花时间正确调整了上述部分中的工作负载大小，那么您应该能够动态地执行此操作。在AWS中使用Kubernetes有两个主要的节点自动扩缩容器。

### Karpenter和集群自动扩缩容器

Karpenter和Kubernetes集群自动扩缩容器都会随着pod的创建或删除以及计算需求的变化而扩缩集群中的节点数量。两者的主要目标是相同的，但Karpenter采用了不同的节点管理配置和取消配置方法，可以帮助降低成本并优化整个集群的使用情况。

随着集群规模的增长和工作负载种类的增加，预先配置节点组和实例变得越来越困难。与工作负载请求一样，设置初始基线并根据需要不断调整也很重要。

### 集群自动扩缩容器优先级扩展器

Kubernetes集群自动扩缩容器通过在应用程序扩缩时扩缩一组节点(称为节点组)来工作。如果您没有动态扩缩工作负载，那么集群自动扩缩容器将无法帮助您节省资金。集群自动扩缩容器需要集群管理员提前为工作负载创建节点组。这些节点组需要配置为使用具有相同"配置文件"的实例，即大致相同的CPU和内存量。

您可以拥有多个节点组，并且可以配置集群自动缩放器来设置优先级缩放级别，每个节点组可以包含不同大小的节点。节点组可以具有不同的容量类型，并且可以使用优先级扩展器首先扩展较便宜的组。

以下是使用 `ConfigMap` 优先使用预留容量而不是使用按需实例的集群配置示例片段。您可以使用相同的技术来优先使用 Graviton 或 Spot 实例而不是其他类型。

```yaml
apiVersion: eksctl.io/v1alpha5
kind: ClusterConfig
metadata:
  name: my-cluster
managedNodeGroups:
  - name: managed-ondemand
    minSize: 1
    maxSize: 7
    instanceType: m5.xlarge
  - name: managed-reserved
    minSize: 2
    maxSize: 10
    instanceType: c5.2xlarge
```

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: cluster-autoscaler-priority-expander
  namespace: kube-system
data:
  priorities: |-
    10:
      - .*ondemand.*
    50:
      - .*reserved.*
```

使用节点组可以帮助底层计算资源按默认方式执行预期操作，例如跨多个可用区域分布节点，但并非所有工作负载都具有相同的要求或期望，因此最好让应用程序明确声明其要求。有关集群自动缩放器的更多信息，请参阅[最佳实践部分](https://aws.github.io/aws-eks-best-practices/cluster-autoscaling/)。

### 取消调度器

集群自动缩放器可以根据需要调度新 Pod 或节点利用率不足来从集群中添加和删除节点容量。但它无法全面查看 Pod 已调度到节点后的放置情况。如果您正在使用集群自动缩放器，您还应该查看 [Kubernetes 取消调度器](https://github.com/kubernetes-sigs/descheduler),以避免浪费集群中的容量。

如果集群中有10个节点，每个节点的利用率为60%,那么集群中有40%的预配置容量未被使用。使用Cluster Autoscaler，您可以将每个节点的利用率阈值设置为60%,但这只会在利用率低于60%时尝试缩减单个节点。

使用descheduler，它可以在pod被调度或节点被添加到集群后查看集群容量和利用率。它会尝试保持集群总容量高于指定的阈值。它还可以根据节点污点或加入集群的新节点删除pod，以确保pod在最佳计算环境中运行。请注意，descheduler不会调度替换被驱逐的pod，而是依赖默认调度程序。

### Karpenter整合

Karpenter采用"无组"的节点管理方法。这种方法对于不同类型的工作负载更加灵活，并且对集群管理员的前期配置要求更少。Karpenter使用provisioner和节点模板来定义可以创建哪种类型的EC2实例以及实例创建时的设置，而不是预先定义组并根据工作负载需求缩放每个组。

Bin packing是将更多工作负载打包到更少数量的最佳大小实例上，以更充分利用实例资源的做法。虽然这有助于减少计算成本，只为工作负载预配所需资源，但也存在权衡。启动新工作负载可能需要更长时间，因为需要向集群添加容量，尤其是在大规模扩展事件期间。在设置bin packing时，请权衡成本优化、性能和可用性之间的平衡。

Karpenter 可以持续监控和整合以提高实例资源利用率并降低计算成本。Karpenter 还可以为您的工作负载选择更具成本效益的工作节点。这可以通过将 provisioner 中的 "consolidation" 标志设置为 true 来实现(下面是示例代码片段)。下面的示例显示了一个启用了整合的 provisioner 示例。在编写本指南时，Karpenter 不会用更便宜的 Spot 实例替换正在运行的 Spot 实例。有关 Karpenter 整合的更多详细信息，请参阅[此博客](https://aws.amazon.com/blogs/containers/optimizing-your-kubernetes-compute-costs-with-karpenter-consolidation/)。

```yaml
apiVersion: karpenter.sh/v1alpha5
kind: Provisioner
metadata:
  name: enable-binpacking
spec:
  consolidation:
    enabled: true
```

对于可能不可中断的工作负载(例如没有检查点的长期运行批处理作业),请考虑使用 `do-not-evict` 注解对 pod 进行注解。通过选择不驱逐 pod，您告诉 Karpenter 不应主动删除包含此 pod 的节点。但是，如果在节点正在排空时添加了 `do-not-evict` pod,则仍会驱逐其余 pod，但该 pod 将阻止终止，直到它被删除。在任一情况下，节点都将被封锁以防止在该节点上调度额外的工作。下面是一个示例，显示了如何设置注解:

```yaml hl_lines="8"
apiVersion: v1
kind: Pod
metadata:
  name: label-demo
  labels:
    environment: production
  annotations:  
    "karpenter.sh/do-not-evict": "true"
spec:
  containers:
  - name: nginx
    image: nginx
    ports:
    - containerPort: 80
```

### 通过调整 Cluster Autoscaler 参数删除利用率较低的节点

节点利用率定义为请求资源之和除以容量。默认情况下 `scale-down-utilization-threshold` 设置为 50%。该参数可与 `scale-down-unneeded-time` 一起使用，后者确定节点在有资格缩减之前应该处于未使用状态的时间长度 - 默认为 10 分钟。仍在缩减节点上运行的 Pod 将由 kube-scheduler 调度到其他节点。调整这些设置可以帮助删除利用率较低的节点，但重要的是您首先测试这些值，以免过早强制集群缩减。

您可以通过确保昂贵的 Pod 被集群自动缩放器识别的标签保护而防止缩减发生。为此，请确保昂贵的 Pod 具有注解 `cluster-autoscaler.kubernetes.io/safe-to-evict=false`。下面是设置注解的示例 yaml:

```yaml hl_lines="8"
apiVersion: v1
kind: Pod
metadata:
  name: label-demo
  labels:
    environment: production
  annotations:  
    "cluster-autoscaler.kubernetes.io/safe-to-evict": "false"
spec:
  containers:
  - name: nginx
    image: nginx
    ports:
    - containerPort: 80
```

### 为集群自动缩放器和 Karpenter 标记节点

AWS 资源[标签](https://docs.aws.amazon.com/tag-editor/latest/userguide/tagging.html)用于组织您的资源，并详细跟踪您的 AWS 成本。它们与用于成本跟踪的 Kubernetes 标签没有直接关联。建议从 Kubernetes 资源标签开始，并利用诸如 [Kubecost](https://aws.amazon.com/blogs/containers/aws-and-kubecost-collaborate-to-deliver-cost-monitoring-for-eks-customers/) 之类的工具，根据 Pod、命名空间等上的 Kubernetes 标签获取基础设施成本报告。

工作节点需要有标签以在AWS成本资源管理器中显示计费信息。使用集群自动缩放器时，可以使用[启动模板](https://docs.aws.amazon.com/eks/latest/userguide/launch-templates.html)为托管节点组中的工作节点添加标签。对于自管理节点组，可以使用[EC2自动缩放组](https://docs.aws.amazon.com/autoscaling/ec2/userguide/ec2-auto-scaling-tagging.html)为实例添加标签。对于由Karpenter供应的实例，可以使用[节点模板中的spec.tags](https://karpenter.sh/docs/concepts/nodeclasses/#spectags)为其添加标签。

### 多租户集群

在由不同团队共享的集群上工作时，您可能无法查看在同一节点上运行的其他工作负载。虽然资源请求可以帮助隔离一些"噪音邻居"问题，如CPU共享，但它们可能无法隔离所有资源边界，如磁盘I/O耗尽。并非工作负载消耗的每种资源都可以被隔离或限制。消耗共享资源的速率高于其他工作负载的工作负载应通过节点[污点和容忍度](https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/)进行隔离。针对此类工作负载的另一种高级技术是[CPU绑定](https://kubernetes.io/docs/tasks/administer-cluster/cpu-management-policies/#static-policy),它可确保容器使用独占CPU而非共享CPU。

在节点级别隔离工作负载可能会更昂贵，但可以调度[BestEffort](https://kubernetes.io/docs/concepts/workloads/pods/pod-qos/#besteffort)作业或利用使用[预留实例](https://aws.amazon.com/ec2/pricing/reserved-instances/)、[Graviton处理器](https://aws.amazon.com/ec2/graviton/)或[Spot](https://aws.amazon.com/ec2/spot/)等方式获得额外节省。

共享集群也可能存在集群级别的资源约束，如IP耗尽、Kubernetes服务限制或API扩展请求。您应该查看[可扩展性最佳实践指南](https://aws.github.io/aws-eks-best-practices/scalability/docs/control-plane/),以确保您的集群避免这些限制。

您可以在命名空间或Karpenter provisioner级别隔离资源。[资源配额](https://kubernetes.io/docs/concepts/policy/resource-quotas/)提供了一种方式来设置命名空间中工作负载可以消耗的资源数量限制。这可以作为一个很好的初始防护措施，但应该持续评估，以确保它不会人为地限制工作负载的扩展。

Karpenter provisioner可以[设置集群中某些可消耗资源的限制](https://karpenter.sh/docs/concepts/nodepools/#speclimitsresources)(例如CPU、GPU),但您需要配置租户应用程序使用适当的provisioner。这可以防止单个provisioner在集群中创建太多节点，但应该持续评估，以确保限制没有设置得太低，从而阻止工作负载扩展。

### 计划自动扩缩容

您可能需要在周末和非工作时间缩减集群。这对于测试和非生产集群尤其重要，您希望在不使用时将其缩减为零。像[cluster-turndown](https://github.com/kubecost/cluster-turndown)和[kube-downscaler](https://codeberg.org/hjacobs/kube-downscaler)这样的解决方案可以根据cron计划将副本缩减为零。

## 优化计算容量类型

在优化集群中计算总容量并利用装箱后，您应该查看已在集群中配置的计算类型以及为这些资源付费的方式。AWS 提供了[计算节省计划](https://aws.amazon.com/savingsplans/compute-pricing/)可以降低您的计算成本，我们将其分为以下容量类型:

* Spot
* 节省计划
* 按需
* Fargate

每种容量类型在管理开销、可用性和长期承诺方面都有不同的权衡，您需要决定哪种适合您的环境。任何环境都不应该仅依赖单一容量类型，您可以在单个集群中混合多种运行类型，以优化特定工作负载需求和成本。

### Spot

[Spot](https://aws.amazon.com/ec2/spot/) 容量类型从可用区的空闲容量中配置 EC2 实例。Spot 提供高达 90% 的折扣，但当其他地方需要这些实例时，它们可能会被中断。此外，可能并不总是有容量来配置新的 Spot 实例，现有的 Spot 实例也可能会在[2 分钟的中断通知](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-interruptions.html)后被回收。如果您的应用程序有较长的启动或关闭过程，Spot 实例可能不是最佳选择。

Spot 计算应使用各种实例类型，以降低无法获得 Spot 容量的可能性。需要处理实例中断以安全关闭节点。使用 Karpenter 或作为 Managed Node Group 的一部分配置的节点自动支持[实例中断通知](https://aws.github.io/aws-eks-best-practices/karpenter/#enable-interruption-handling-when-using-spot)。如果您使用自行管理的节点，则需要单独运行[节点终止处理程序](https://github.com/aws/aws-node-termination-handler)以正常关闭 Spot 实例。

在单个集群中平衡 Spot 和按需实例是可能的。使用 Karpenter，您可以创建[加权供应商](https://karpenter.sh/docs/concepts/scheduling/#on-demandspot-ratio-split)来实现不同容量类型的平衡。使用 Cluster Autoscaler，您可以创建[混合节点组，其中包含 Spot 和按需或预留实例](https://aws.amazon.com/blogs/containers/amazon-eks-now-supports-provisioning-and-managing-ec2-spot-instances-in-managed-node-groups/)。

以下是使用 Karpenter 优先于按需实例提供 Spot 实例的示例。在创建供应商时，您可以指定 Spot、按需或两者(如下所示)。当您同时指定两者时，如果 pod 没有明确指定需要使用 Spot 还是按需，那么 Karpenter 会在使用[价格-容量优化分配策略](https://aws.amazon.com/blogs/compute/introducing-price-capacity-optimized-allocation-strategy-for-ec2-spot-instances/)供应节点时优先考虑 Spot。

```yaml hl_lines="9"
apiVersion: karpenter.sh/v1alpha5
kind: Provisioner
metadata:
  name: spot-prioritized
spec:
  requirements:
    - key: "karpenter.sh/capacity-type" 
      operator: In
        values: ["spot", "on-demand"]
```

### 节省计划、预留实例和 AWS EDP

您可以使用[计算节省计划](https://aws.amazon.com/savingsplans/compute-pricing/)来降低计算支出。节省计划为 1 年或 3 年的计算使用承诺提供了降低价格。使用情况可以应用于 EKS 集群中的 EC2 实例，但也适用于 Lambda 和 Fargate 等任何计算使用。使用节省计划，您可以在承诺期内降低成本，并且仍然可以选择任何 EC2 实例类型。

计算节省计划可以将您的 EC2 成本降低高达 66%,而无需承诺您想要使用的实例类型、系列或区域。节省会自动应用于您使用的实例。

EC2 实例储蓄计划可为特定区域和 EC2 系列（例如 C 系列实例）的使用承诺提供高达 72% 的计算节省。您可以在该区域内的任何可用区使用该实例系列的任何代数（例如 c5 或 c6）和任何实例大小。折扣将自动应用于您账户中符合储蓄计划条件的任何实例。

[预留实例](https://aws.amazon.com/ec2/pricing/reserved-instances/)类似于 EC2 实例储蓄计划，但它们还可以保证在可用区或区域中的容量，并比按需实例节省高达 72% 的成本。一旦您计算出所需的预留容量，就可以选择预留时长（1 年或 3 年）。折扣将自动应用于您在账户中运行的那些 EC2 实例。

客户还可以选择与 AWS 签订企业协议。企业协议允许客户量身定制最适合其需求的协议。客户可以根据 AWS EDP (企业折扣计划) 享受定价折扣。有关企业协议的更多信息，请联系您的 AWS 销售代表。

### 按需

与现场实例相比，按需 EC2 实例的好处是可用性不会中断；与储蓄计划相比，没有长期承诺。如果您希望在集群中降低成本，应该减少使用按需 EC2 实例。

在优化工作负载需求后，您应该能够为集群计算出最小和最大容量。这个数字可能会随时间变化，但很少会降低。请考虑为最小容量以下的所有容量使用储蓄计划，为不会影响应用程序可用性的容量使用现场实例。任何其他可能不会持续使用或需要保证可用性的容量都可以使用按需实例。

正如本节所述，减少使用量的最佳方式是消耗更少资源，并尽可能充分利用您配置的资源。使用Cluster Autoscaler，您可以通过 `scale-down-utilization-threshold` 设置删除利用率较低的节点。对于Karpenter，建议启用整合。

要手动识别可用于您的工作负载的EC2实例类型，您应该使用 [ec2-instance-selector](https://github.com/aws/amazon-ec2-instance-selector),它可以显示每个区域中可用的实例以及与EKS兼容的实例。对于x86处理器架构、4 Gb内存、2个vCPU和在us-east-1区域中可用的实例，示例用法如下:

```bash
ec2-instance-selector --memory 4 --vcpus 2 --cpu-architecture x86_64 \
  -r us-east-1 --service eks
c5.large
c5a.large
c5ad.large
c5d.large
c6a.large
c6i.large
t2.medium
t3.medium
t3a.medium
```

对于非生产环境，您可以在夜间和周末等未使用时段自动缩减集群。kubecost项目 [cluster-turndown](https://github.com/kubecost/cluster-turndown) 就是一个基于预定时间表自动缩减集群的控制器示例。

### Fargate计算

Fargate计算是EKS集群的一种完全托管的计算选项。它通过在Kubernetes集群中为每个pod调度一个节点来提供pod隔离。它允许您根据工作负载的CPU和RAM需求调整计算节点的大小，从而严格控制集群中的工作负载使用情况。

Fargate可以将工作负载缩放到最小0.25个vCPU和0.5 GB内存，最大16个vCPU和120 GB内存。可用的 [pod大小变体](https://docs.aws.amazon.com/eks/latest/userguide/fargate-pod-configuration.html) 数量有限制，您需要了解您的工作负载最适合哪种Fargate配置。例如，如果您的工作负载需要1个vCPU和0.5 GB内存，最小的Fargate pod将是1个vCPU和2 GB内存。

虽然 Fargate 有许多好处，例如无需管理 EC2 实例或操作系统，但由于每个部署的 pod 都被隔离为集群中的单独节点，因此可能需要比传统 EC2 实例更多的计算能力。这需要对诸如 Kubelet、日志代理和通常部署到节点的任何 DaemonSet 等进行更多重复。Fargate 不支持 DaemonSet，它们需要转换为 pod "sidecar" 并与应用程序一起运行。

Fargate 无法从 bin packing 或 CPU 过度配置中获益，因为工作负载的边界是一个不可突发或在工作负载之间共享的节点。Fargate 将为您节省 EC2 实例管理时间(这本身就有成本),但 CPU 和内存成本可能比其他 EC2 容量类型更高。Fargate pod 可以利用计算节省计划来降低按需成本。

## 优化计算使用

节省计算基础设施成本的另一种方式是为工作负载使用更高效的计算。这可以来自更高性能的通用计算，如 [Graviton 处理器](https://aws.amazon.com/ec2/graviton/),比 x86 便宜 20% 且能效高 60%——或者特定于工作负载的加速器，如 GPU 和 [FPGA](https://aws.amazon.com/ec2/instance-types/f1/)。您需要构建可以[在 arm 架构上运行](https://aws.amazon.com/blogs/containers/how-to-build-your-containers-for-arm-and-save-with-graviton-and-spot-instances-on-amazon-ecs/)的容器，并[设置具有适当加速器](https://aws.amazon.com/blogs/compute/running-gpu-accelerated-kubernetes-workloads-on-p3-and-p2-ec2-instances-with-amazon-eks/)的节点以满足您的工作负载需求。

EKS 能够运行混合架构（例如 amd64 和 arm64）的集群，如果您的容器为多种架构编译，您可以通过在 Provisioner 中允许这两种架构来利用 Graviton 处理器和 Karpenter。但是，为了保持一致的性能，建议您将每个工作负载保持在单一计算架构上，只有在没有额外容量可用时才使用不同的架构。

Provisioner 可以配置为支持多种架构，工作负载也可以在其工作负载规范中请求特定架构。

```yaml
apiVersion: karpenter.sh/v1alpha5
kind: Provisioner
metadata:
  name: default
spec:
  requirements:
  - key: "kubernetes.io/arch"
    operator: In
    values: ["arm64", "amd64"]
```

使用 Cluster Autoscaler，您需要为 Graviton 实例创建一个节点组，并在您的工作负载上设置[节点容忍度](https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/)以利用新的容量。

GPU 和 FPGA 可以大大提高您的工作负载性能，但工作负载需要优化以使用加速器。许多用于机器学习和人工智能的工作负载类型可以使用 GPU 进行计算，实例可以添加到集群中并使用资源请求挂载到工作负载中。

```yaml
spec:
  template:
    spec:
    - containers:
      ...
      resources:
          limits:
            nvidia.com/gpu: "1"
```

某些 GPU 硬件可以在多个工作负载之间共享，因此可以配置和使用单个 GPU。要了解如何配置工作负载 GPU 共享，请参阅[虚拟 GPU 设备插件](https://aws.amazon.com/blogs/opensource/virtual-gpu-device-plugin-for-inference-workload-in-kubernetes/)以获取更多信息。您还可以参考以下博客文章：

* [在 Amazon EKS 上使用 NVIDIA 时间分片和加速型 EC2 实例实现 GPU 共享](https://aws.amazon.com/blogs/containers/gpu-sharing-on-amazon-eks-with-nvidia-time-slicing-and-accelerated-ec2-instances/)
* [在 Amazon EKS 上使用 NVIDIA 的多实例 GPU (MIG) 最大化 GPU 利用率：每个 GPU 运行更多 Pod 以提高性能](https://aws.amazon.com/blogs/containers/maximizing-gpu-utilization-with-nvidias-multi-instance-gpu-mig-on-amazon-eks-running-more-pods-per-gpu-for-enhanced-performance/)