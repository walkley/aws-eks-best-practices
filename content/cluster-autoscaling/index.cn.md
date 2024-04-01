# Kubernetes 集群自动扩缩器

<iframe width="560" height="315" src="https://www.youtube.com/embed/FIBc8GkjFU0" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe>

## 概述

[Kubernetes 集群自动扩缩器](https://github.com/kubernetes/autoscaler/tree/master/cluster-autoscaler)是由 [SIG Autoscaling](https://github.com/kubernetes/community/tree/master/sig-autoscaling) 维护的一种流行的集群自动扩缩解决方案。它负责确保您的集群有足够的节点来调度您的 Pod，而不会浪费资源。它会监视无法调度的 Pod 和利用率较低的节点。然后，它会模拟添加或删除节点，然后再将更改应用到您的集群。集群自动扩缩器中的 AWS 云驱动程序实现控制您的 EC2 Auto Scaling 组的 `.DesiredReplicas` 字段。

![](./architecture.png)

本指南将为配置集群自动扩缩器并选择最佳的权衡集提供一种思维模型，以满足您组织的需求。虽然没有一种最佳配置，但有一组配置选项可以让您在性能、可扩展性、成本和可用性之间进行权衡。此外，本指南还将提供在 AWS 上优化配置的技巧和最佳实践。

### 术语表

以下术语将在本文档中频繁使用。这些术语可能有广泛的含义，但就本文档而言，仅限于下面的定义。

**可扩展性**是指集群自动扩缩器在 Kubernetes 集群的 Pod 和节点数量增加时的性能表现。随着可扩展性限制的达到，集群自动扩缩器的性能和功能会下降。当集群自动扩缩器超出其可扩展性限制时，它可能无法再在您的集群中添加或删除节点。

**性能**指的是集群自动扩缩器能够做出和执行扩缩决策的速度。性能完美的集群自动扩缩器会立即做出决策并触发扩缩操作以响应刺激因素，例如一个 pod 无法被调度。

**可用性**意味着 pod 可以被快速且无中断地调度。这包括新创建的 pod 需要被调度时，以及缩减节点终止其上调度的任何剩余 pod 时。

**成本**由扩容和缩容事件背后的决策决定。如果现有节点利用率不足或添加了一个过大的新节点用于接收传入的 pod，资源就会被浪费。根据使用场景，由于过于积极的缩减决策而过早终止 pod 可能会产生相关成本。

**节点组**是集群内一组节点的抽象 Kubernetes 概念。它不是一个真正的 Kubernetes 资源，而是存在于集群自动扩缩器、集群 API 和其他组件中的抽象概念。节点组内的节点共享诸如标签和污点等属性，但可能包含多个可用区或实例类型。

**EC2 Auto Scaling 组**可用作 EC2 上节点组的一种实现。EC2 Auto Scaling 组被配置为启动自动加入其 Kubernetes 集群的实例，并将标签和污点应用于 Kubernetes API 中对应的节点资源。

**EC2 托管节点组**是 EC2 上节点组的另一种实现。它抽象了手动配置 EC2 Auto Scaling 组的复杂性，并提供了诸如节点版本升级和优雅节点终止等额外的管理功能。

### 操作集群自动扩缩器

集群自动扩缩器通常作为[Deployment](https://github.com/kubernetes/autoscaler/tree/master/cluster-autoscaler/cloudprovider/aws/examples)安装在集群中。它使用[领导者选举](https://en.wikipedia.org/wiki/Leader_election)来确保高可用性，但同一时间只有一个副本在工作。它不是水平可扩展的。对于基本设置，使用提供的[安装说明](https://docs.aws.amazon.com/eks/latest/userguide/cluster-autoscaler.html)应该可以开箱即用，但有一些需要注意的地方。

确保:

* 集群自动扩缩器的版本与集群的版本匹配。跨版本兼容性[未经测试或不受支持](https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/README.md#releases)。
* 启用[自动发现](https://github.com/kubernetes/autoscaler/tree/master/cluster-autoscaler/cloudprovider/aws#auto-discovery-setup),除非您有特定的高级用例阻止使用此模式。

### 对IAM角色采用最小权限访问

当使用[自动发现](https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/cloudprovider/aws/README.md#Auto-discovery-setup)时，我们强烈建议您采用最小权限访问，限制`autoscaling:SetDesiredCapacity`和`autoscaling:TerminateInstanceInAutoScalingGroup`操作仅对当前集群范围内的自动伸缩组。

这将防止在一个集群中运行的集群自动扩缩器修改另一个集群中的节点组，即使`--node-group-auto-discovery`参数没有使用标签(例如`k8s.io/cluster-autoscaler/<cluster-name>`)将范围缩小到集群的节点组。

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "autoscaling:SetDesiredCapacity",
                "autoscaling:TerminateInstanceInAutoScalingGroup"
            ],
            "Resource": "*",
            "Condition": {
                "StringEquals": {
                    "aws:ResourceTag/k8s.io/cluster-autoscaler/enabled": "true",
                    "aws:ResourceTag/k8s.io/cluster-autoscaler/<my-cluster>": "owned"
                }
            }
        },
        {
            "Effect": "Allow",
            "Action": [
                "autoscaling:DescribeAutoScalingGroups",
                "autoscaling:DescribeAutoScalingInstances",
                "autoscaling:DescribeLaunchConfigurations",
                "autoscaling:DescribeScalingActivities",
                "autoscaling:DescribeTags",
                "ec2:DescribeImages",
                "ec2:DescribeInstanceTypes",
                "ec2:DescribeLaunchTemplateVersions",
                "ec2:GetInstanceTypesFromInstanceRequirements",
                "eks:DescribeNodegroup"
            ],
            "Resource": "*"
        }
    ]
}
```

### 配置您的节点组

有效的自动扩缩容从正确配置一组节点组开始。选择正确的节点组集对于最大化工作负载的可用性和降低成本至关重要。AWS使用EC2自动扩缩容组实现节点组，这些组适用于大量用例。但是，集群自动扩缩容器对您的节点组做出了一些假设。保持您的EC2自动扩缩容组配置与这些假设一致将最小化不希望的行为。

确保:

* 每个节点组中的节点都具有相同的调度属性，如标签、污点和资源。
  * 对于混合实例策略，实例类型在 CPU、内存和 GPU 方面必须具有相同的形状
  * 策略中指定的第一个实例类型将用于模拟调度。
  * 如果您的策略有更多资源的其他实例类型，在扩展后资源可能会被浪费。
  * 如果您的策略有较少资源的其他实例类型，Pod 可能无法在这些实例上调度。
* 节点数量多的节点组优于节点数量少的多个节点组。这将对可扩展性产生最大影响。
* 在两个系统都提供支持的情况下，尽可能优先选择 EC2 功能(例如区域、混合实例策略)

*注意:我们建议使用 [EKS 托管节点组](https://docs.aws.amazon.com/eks/latest/userguide/managed-node-groups.html)。托管节点组具有强大的管理功能，包括集群自动扩缩器的功能，如自动发现 EC2 Auto Scaling 组和优雅的节点终止。*

## 优化性能和可扩展性

了解自动扩缩算法的运行时复杂度将有助于您调整集群自动扩缩器，使其在大于 [1,000 个节点](https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/proposals/scalability_tests.md) 的大型集群中继续顺利运行。

调整集群自动扩缩器可扩展性的主要因素是为进程提供的资源、算法的扫描间隔以及集群中的节点组数量。还有其他一些因素涉及到该算法的真实运行时复杂度，例如调度插件的复杂度和 Pod 的数量。这些被视为不可配置的参数，因为它们是集群工作负载的自然属性，无法轻易调整。

集群自动扩缩器将整个集群的状态加载到内存中，包括 Pod、节点和节点组。在每个扫描间隔期间，算法会识别无法调度的 Pod 并模拟为每个节点组进行调度。调整这些因素会带来不同的权衡，应该根据您的使用场景仔细考虑。

### 垂直自动扩缩集群自动扩缩器

扩大集群自动扩缩器以适应更大规模集群的最简单方法是增加其部署的资源请求。对于大型集群，内存和 CPU 都应该增加，尽管这在很大程度上取决于集群大小。自动扩缩算法会将所有 Pod 和节点存储在内存中，在某些情况下可能会导致内存占用超过 1GB。通常情况下资源增加是手动完成的。如果发现持续的资源调整带来了运维负担，可以考虑使用 [Addon Resizer](https://github.com/kubernetes/autoscaler/tree/master/addon-resizer) 或 [Vertical Pod Autoscaler](https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler)。

### 减少节点组数量

最小化节点组数量是确保集群自动扩缩器在大型集群上继续良好运行的一种方式。对于一些按团队或应用程序划分节点组的组织来说，这可能是一个挑战。虽然 Kubernetes API 完全支持这种做法，但这被视为集群自动扩缩器的反模式，会对可扩展性产生影响。使用多个节点组有许多原因(例如 Spot 或 GPU),但在许多情况下，有可以在使用少量节点组的同时实现相同效果的替代设计。

确保:

* Pod 隔离使用命名空间而不是节点组完成。
  * 在低信任多租户集群中可能无法实现。
  * Pod ResourceRequests 和 ResourceLimits 设置正确以避免资源争用。
  * 更大的实例类型将导致更优化的装箱和减少系统 pod 开销。
* 使用 NodeTaints 或 NodeSelectors 调度 pod 作为例外情况，而不是常规做法。
* 区域资源定义为具有多个可用区的单个 EC2 Auto Scaling 组。

### 减少扫描间隔

较低的扫描间隔(例如 10 秒)将确保集群自动扩缩器在 pod 无法调度时尽快做出响应。但是，每次扫描都会导致对 Kubernetes API 和 EC2 Auto Scaling 组或 EKS 托管节点组 API 发出许多 API 调用。这些 API 调用可能会导致速率限制，甚至导致您的 Kubernetes 控制平面服务不可用。

默认扫描间隔为 10 秒，但在 AWS 上，启动新实例需要更长时间。这意味着可以增加间隔而不会显著增加整体扩展时间。例如，如果启动节点需要 2 分钟，将间隔更改为 1 分钟将导致 API 调用减少 6 倍，而扩展速度仅慢 38%。

### 跨节点组分片

可以将集群自动扩缩器配置为在特定的节点组集上运行。使用此功能，可以部署多个集群自动扩缩器实例，每个实例配置为在不同的节点组集上运行。此策略使您能够使用任意大量的节点组，以成本换取可扩展性。我们只建议在提高性能时作为最后手段使用此方法。

集群自动扩缩器最初并非为此配置而设计，因此存在一些副作用。由于各个分片之间不会通信，因此有可能多个自动扩缩器尝试调度一个无法调度的 Pod。这可能导致多个节点组不必要地扩容。这些额外的节点将在 `scale-down-delay` 后缩减。

```
metadata:
  name: cluster-autoscaler
  namespace: cluster-autoscaler-1

...

--nodes=1:10:k8s-worker-asg-1
--nodes=1:10:k8s-worker-asg-2

---

metadata:
  name: cluster-autoscaler
  namespace: cluster-autoscaler-2

...

--nodes=1:10:k8s-worker-asg-3
--nodes=1:10:k8s-worker-asg-4
```

请确保:

* 每个分片都配置为指向一组唯一的 EC2 Auto Scaling 组
* 每个分片都部署在单独的命名空间中，以避免领导者选举冲突

## 优化成本和可用性

### Spot 实例

您可以在节点组中使用 Spot 实例，与按需实例相比可节省高达 90% 的费用，但代价是 Spot 实例可能会在 EC2 需要回收容量时随时被中断。当您的 EC2 Auto Scaling 组由于可用容量不足而无法扩容时，将发生 Insufficient Capacity Error。选择多种实例系列可以增加您利用多个 Spot 容量池实现所需扩容的机会，并降低 Spot 实例中断对集群可用性的影响。使用 Spot 实例的混合实例策略是提高多样性而不增加节点组数量的绝佳方式。请记住，如果您需要保证资源，请使用按需实例而不是 Spot 实例。

在配置混合实例策略时，所有实例类型都必须具有相似的资源容量。自动缩放器的调度模拟器使用混合实例策略中的第一个实例类型。如果后续实例类型更大，在扩容后可能会浪费资源。如果更小，您的 Pod 可能由于容量不足而无法在新实例上调度。例如，M4、M5、M5a 和 M5n 实例都具有相似的 CPU 和内存量，是混合实例策略的绝佳候选。[EC2 实例选择器](https://github.com/aws/amazon-ec2-instance-selector)工具可以帮助您识别相似的实例类型。

![](./spot_mix_instance_policy.jpg)

建议将按需和 Spot 容量隔离到单独的 EC2 Auto Scaling 组中。这比使用[基本容量策略](https://docs.aws.amazon.com/autoscaling/ec2/userguide/asg-purchase-options.html#asg-instances-distribution)更可取，因为调度属性有根本不同。由于 Spot 实例可能随时被中断(当 EC2 需要回收容量时)，用户通常会为其可抢占节点添加污点，需要显式的 Pod 容忍度来容忍抢占行为。这些污点导致节点具有不同的调度属性，因此它们应该被分离到多个 EC2 Auto Scaling 组中。

集群自动缩放器有一个[扩展器](https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/FAQ.md#what-are-expanders)的概念，它提供了不同的策略来选择要扩展的节点组。`--expander=least-waste` 策略是一个不错的通用默认值。如果您要为 Spot 实例多样化使用多个节点组(如上图所示)，它可以进一步优化节点组的成本，通过扩展在扩展活动后利用率最高的组。

### 优先级节点组/ASG

您也可以通过使用 Priority expander 来配置基于优先级的自动扩缩容。`--expander=priority` 使您的集群能够优先考虑某个节点组/ASG,如果由于任何原因无法扩缩该节点组，它将选择优先级列表中的下一个节点组。这在某些情况下很有用，例如，您希望使用 P3 实例类型，因为它们的 GPU 可为您的工作负载提供最佳性能，但作为第二选择，您也可以使用 P2 实例类型。

```
apiVersion: v1
kind: ConfigMap
metadata:
  name: cluster-autoscaler-priority-expander
  namespace: kube-system
data:
  priorities: |-
    10:
      - .*p2-node-group.*
    50:
      - .*p3-node-group.*
```

Cluster Autoscaler 将尝试扩缩与名称 *p3-node-group* 匹配的 EC2 Auto Scaling 组。如果在 `--max-node-provision-time` 内无法成功执行此操作，它将尝试扩缩与名称 *p2-node-group* 匹配的 EC2 Auto Scaling 组。
该值默认为 15 分钟，可以缩短以更快响应节点组选择，但如果值过低，可能会导致不必要的扩缩。

### 超配置

Cluster Autoscaler 通过确保仅在需要时向集群添加节点，并在未使用时将其删除，从而最小化成本。这会显著影响部署延迟，因为许多 pod 将被迫等待节点扩缩才能被调度。节点可能需要多分钟才能可用，这可能会使 pod 调度延迟增加一个数量级。

这可以通过使用[过度配置](https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/FAQ.md#how-can-i-configure-overprovisioning-with-cluster-autoscaler)来缓解，它以调度延迟为代价。过度配置是使用具有负优先级的临时 Pod 实现的，这些 Pod 占用集群中的空间。当新创建的 Pod 无法调度且具有更高优先级时，临时 Pod 将被驱逐以腾出空间。然后，这些临时 Pod 变为无法调度，从而触发集群自动扩缩器扩展新的过度配置节点。

过度配置还有其他不太明显的好处。如果没有过度配置，高度利用的集群的一个副作用是 Pod 将根据 Pod 或节点亲和性的 `preferredDuringSchedulingIgnoredDuringExecution` 规则做出次优调度决策。一个常见的用例是使用反亲和性将高可用应用程序的 Pod 跨可用区域分离。过度配置可以显著提高正确区域的节点可用的机会。

过度配置容量的数量是您组织需要仔细考虑的业务决策。从本质上讲，这是性能和成本之间的权衡。做出这个决策的一种方式是确定您的平均扩展频率，并将其除以扩展新节点所需的时间。例如，如果平均每 30 秒需要一个新节点，而 EC2 需要 30 秒来配置一个新节点，那么单个节点的过度配置将确保总有一个额外的节点可用，以额外 EC2 实例的成本为代价，减少 30 秒的调度延迟。为了改善区域调度决策，请过度配置与 EC2 Auto Scaling 组中可用区域数量相等的节点数量，以确保调度程序可以为传入的 Pod 选择最佳区域。

### 防止缩减驱逐

有些工作负载被驱逐的代价很高。大数据分析、机器学习任务和测试运行程序最终会完成，但如果中断则必须重新启动。Cluster Autoscaler 将尝试缩减任何低于 scale-down-utilization-threshold 的节点，这将中断该节点上的任何剩余 pod。可以通过确保昂贵的驱逐 pod 受到 Cluster Autoscaler 识别的标签保护来防止这种情况。

确保:

* 昂贵的驱逐 pod 具有注解 `cluster-autoscaler.kubernetes.io/safe-to-evict=false`

## 高级用例

### EBS 卷

持久存储对于构建有状态应用程序(如数据库或分布式缓存)至关重要。[EBS 卷](https://aws.amazon.com/premiumsupport/knowledge-center/eks-persistent-storage/)支持在 Kubernetes 上实现此用例，但仅限于特定区域。如果使用单独的 EBS 卷跨多个可用区域进行分片，这些应用程序就可以实现高可用性。Cluster Autoscaler 可以平衡 EC2 Auto Scaling 组的扩缩容。

确保:

* 通过设置 `balance-similar-node-groups=true` 启用节点组均衡。
* 节点组配置相同，除了不同的可用区域和 EBS 卷。

### 协同调度

机器学习分布式训练作业可以从最小化同区域节点配置的延迟中获得显著收益。这些工作负载将多个 pod 部署到特定区域。可以通过为所有协同调度的 pod 设置 Pod 亲和性或使用 `topologyKey: failure-domain.beta.kubernetes.io/zone` 设置节点亲和性来实现。然后 Cluster Autoscaler 将扩展特定区域以满足需求。您可能希望为每个可用区域分配多个 EC2 Auto Scaling 组，以实现整个协同调度工作负载的故障转移。

确保:

* 通过设置 `balance-similar-node-groups=false` 启用节点组均衡
* 当集群包含区域节点组和区域节点组时，使用[节点亲和性](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/#affinity-and-anti-affinity)和/或[Pod抢占](https://kubernetes.io/docs/concepts/configuration/pod-priority-preemption/)。
  * 使用[节点亲和性](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/#affinity-and-anti-affinity)强制或鼓励区域 Pod 避开区域节点组，反之亦然。
  * 如果区域 Pod 调度到区域节点组上，这将导致您的区域 Pod 的容量不平衡。
  * 如果您的区域工作负载可以容忍中断和重新调度，请配置[Pod抢占](https://kubernetes.io/docs/concepts/configuration/pod-priority-preemption/)以使区域扩展的 Pod 能够强制抢占和重新调度到较少争用的区域。

### 加速器

某些集群利用了诸如 GPU 之类的专用硬件加速器。在扩展时，加速器设备插件可能需要几分钟时间才能向集群公布资源。集群自动扩缩器已模拟该节点将具有加速器，但在加速器准备就绪并更新节点的可用资源之前，待处理的 Pod 无法调度到该节点上。这可能会导致[重复不必要的扩展](https://github.com/kubernetes/kubernetes/issues/54959)。

此外，即使加速器未被使用，具有加速器和高 CPU 或内存利用率的节点也不会被视为缩减对象。由于加速器的相对成本较高，这种行为可能会很昂贵。相反，集群自动扩缩器可以应用特殊规则，如果节点有未占用的加速器，则将其视为缩减对象。

为确保这些情况的正确行为，您可以在加速器节点上配置kubelet，在加入集群之前为节点添加标签。集群自动扩缩器将使用此标签选择器来触发加速器优化行为。

确保:

* GPU节点的Kubelet配置了 `--node-labels k8s.amazonaws.com/accelerator=$ACCELERATOR_TYPE`
* 带有加速器的节点遵守上述相同的调度属性规则。

### 从0开始扩缩

集群自动扩缩器能够将节点组扩缩到0，这可以带来显著的成本节省。它通过检查自动伸缩组的启动配置或启动模板中指定的实例类型来检测自动伸缩组的CPU、内存和GPU资源。某些Pod需要额外的资源，如`WindowsENI`或`PrivateIPv4Address`或特定的节点选择器或污点，这些无法从启动配置中发现。集群自动扩缩器可以通过从EC2自动伸缩组上的标签发现这些因素来考虑这些因素。例如:

```
Key: k8s.io/cluster-autoscaler/node-template/resources/$RESOURCE_NAME
Value: 5
Key: k8s.io/cluster-autoscaler/node-template/label/$LABEL_KEY
Value: $LABEL_VALUE
Key: k8s.io/cluster-autoscaler/node-template/taint/$TAINT_KEY
Value: NoSchedule
```

*注意:请记住，当扩缩到零时，您的容量将返回到EC2，将来可能无法使用。*

## 其他参数

有许多配置选项可用于调整集群自动扩缩器的行为和性能。
完整的参数列表可在[GitHub](https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/FAQ.md#what-are-the-parameters-to-ca)上找到。

|  |  |  |
|-|-|-|
| 参数 | 描述 | 默认值 |
| scan-interval | 集群重新评估扩缩容的频率 | 10秒 |
| max-empty-bulk-delete | 同时可删除的最大空节点数 | 10 |
| scale-down-delay-after-add | 扩容后恢复缩容评估的时间 | 10分钟 |
| scale-down-delay-after-delete | 节点删除后恢复缩容评估的时间，默认为scan-interval | scan-interval |
| scale-down-delay-after-failure | 缩容失败后恢复缩容评估的时间 | 3分钟 |
| scale-down-unneeded-time | 节点被视为不需要的时间后才有资格缩容 | 10分钟 |
| scale-down-unready-time | 未就绪节点被视为不需要的时间后才有资格缩容 | 20分钟 |
| scale-down-utilization-threshold | 节点利用率水平，定义为请求资源总和除以容量，低于该值时节点可被视为缩容对象 | 0.5 |
| scale-down-non-empty-candidates-count | 在一次迭代中作为带排空的缩容候选对象考虑的非空节点的最大数量。较低值意味着更好的CA响应能力但可能导致较慢的缩容延迟。较高值可能会影响大规模集群(数百个节点)的CA性能。设置为非正值将关闭此启发式 - CA将不限制其考虑的节点数量。" | 30 |
| scale-down-candidates-pool-ratio | 当前一次迭代中的某些候选节点不再有效时，作为额外非空缩容候选对象考虑的节点比例。较低值意味着更好的CA响应能力但可能导致较慢的缩容延迟。较高值可能会影响大规模集群(数百个节点)的CA性能。设置为1.0将关闭此启发式 - CA将把所有节点作为额外候选对象。 | 0.1 |
| scale-down-candidates-pool-min-count | 当前一次迭代中的某些候选节点不再有效时，作为额外非空缩容候选对象考虑的最小节点数。在计算额外候选对象的池大小时，我们取 `max(#nodes * scale-down-candidates-pool-ratio, scale-down-candidates-pool-min-count)` | 50 |

## 其他资源

本页包含了一系列 Cluster Autoscaler 演示文稿和演示。如果您想在此添加演示文稿或演示，请发送拉取请求。

| 演示文稿/演示 | 演讲者 |
| ------------ | ------- |
| [Kubernetes 上的自动扩缩容和成本优化：从 0 到 100](https://sched.co/Zemi) | Guy Templeton, Skyscanner & Jiaxin Shan, Amazon |
| [SIG-Autoscaling 深入探讨](https://youtu.be/odxPyW_rZNQ) | Maciek Pytel & Marcin Wielgus |

## 参考

* [https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/FAQ.md](https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/FAQ.md)
* [https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/cloudprovider/aws/README.md](https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/cloudprovider/aws/README.md)
* [https://github.com/aws/amazon-ec2-instance-selector](https://github.com/aws/amazon-ec2-instance-selector)
* [https://github.com/aws/aws-node-termination-handler](https://github.com/aws/aws-node-termination-handler)