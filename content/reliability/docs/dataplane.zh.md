# EKS 数据平面

要运行高可用且可恢复的应用程序，您需要一个高可用且可恢复的数据平面。弹性数据平面可确保 Kubernetes 能够自动扩展和修复您的应用程序。一个可恢复的数据平面由两个或更多工作节点组成，可以随工作负载的增长而扩展和收缩，并能自动从故障中恢复。

在 EKS 中，您可以选择 [EC2 实例](https://docs.aws.amazon.com/eks/latest/userguide/worker.html)或 [Fargate](https://docs.aws.amazon.com/eks/latest/userguide/fargate.html) 作为工作节点。如果选择 EC2 实例，您可以自行管理工作节点或使用 [EKS 托管节点组](https://docs.aws.amazon.com/eks/latest/userguide/managed-node-groups.html)。您可以在集群中混合使用托管节点、自管理节点和 Fargate。

EKS on Fargate 提供了最简单的途径来实现可恢复的数据平面。Fargate 在隔离的计算环境中运行每个 Pod。在 Fargate 上运行的每个 Pod 都有自己的工作节点。当 Kubernetes 扩展 Pod 时，Fargate 会自动扩展数据平面。您可以使用 [horizontal pod autoscaler](https://docs.aws.amazon.com/eks/latest/userguide/horizontal-pod-autoscaler.html) 来扩展数据平面和工作负载。

扩展 EC2 工作节点的首选方式是使用 [Kubernetes Cluster Autoscaler](https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/cloudprovider/aws/README.md)、[EC2 Auto Scaling 组](https://docs.aws.amazon.com/autoscaling/ec2/userguide/AutoScalingGroup.html)或社区项目如 [Atlassian's Escalator](https://github.com/atlassian/escalator)。

## 建议

### 使用 EC2 Auto Scaling 组创建工作节点

使用 EC2 Auto Scaling 组创建工作节点而不是创建单个 EC2 实例并将其加入集群是最佳实践。Auto Scaling 组会自动替换任何终止或失败的节点，确保集群始终有能力运行您的工作负载。

### 使用Kubernetes集群自动扩缩器来扩缩节点

当由于集群资源不足而无法运行 Pod 时，集群自动扩缩器会调整数据平面的大小，并且添加另一个工作节点会有所帮助。尽管集群自动扩缩器是一个反应性过程，但它会等到由于集群容量不足而导致 Pod 处于*Pending*状态时才会启动。发生这种情况时，它会向集群添加 EC2 实例。每当集群资源耗尽时，新的副本或新的 Pod 将处于不可用(*Pending 状态*)状态，直到添加工作节点为止。如果数据平面无法足够快地扩展以满足工作负载的需求，这种延迟可能会影响您应用程序的可靠性。如果工作节点持续利用率低且其上的所有 Pod 都可以调度到其他工作节点上，集群自动扩缩器会将其终止。

### 使用集群自动扩缩器配置过度配置

当集群中的 Pod 已经处于*Pending*状态时，集群自动扩缩器会触发数据平面的扩缩。因此，您的应用程序需要更多副本与实际获得更多副本之间可能会有延迟。应对这种可能延迟的一种选择是通过添加超过所需的副本来增加应用程序的副本数量。

另一种Cluster Autoscaler推荐的模式使用[*pause* Pods和优先级抢占功能](https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/FAQ.md#how-can-i-configure-overprovisioning-with-cluster-autoscaler)。*pause Pod*运行一个[pause容器](https://github.com/kubernetes/kubernetes/tree/master/build/pause)，顾名思义，它什么也不做，只是作为集群中其他Pod可以使用的计算能力的占位符。由于它以*非常低的优先级*运行，当需要创建另一个Pod而集群没有可用容量时，pause Pod会从节点中被驱逐。Kubernetes调度器注意到pause Pod的驱逐并尝试重新调度它。但由于集群运行在满负荷状态，pause Pod保持*Pending*状态，Cluster Autoscaler对此做出反应，增加节点。

有一个Helm Chart可用于安装[cluster overprovisioner](https://github.com/helm/charts/tree/master/stable/cluster-overprovisioner)。

### 使用Cluster Autoscaler与多个Auto Scaling组

启用`--node-group-auto-discovery`标志运行Cluster Autoscaler。这样做将允许Cluster Autoscaler找到包含特定定义标签的所有自动伸缩组，并防止需要在清单中定义和维护每个自动伸缩组。

### 使用Cluster Autoscaler与本地存储

默认情况下，Cluster Autoscaler不会缩减部署了带有本地存储的Pod的节点。将`--skip-nodes-with-local-storage`标志设置为false，以允许Cluster Autoscaler缩减这些节点。

### 跨多个可用区运行工作节点和工作负载

您可以通过在多个可用区运行工作节点和Pod来保护工作负载免受单个可用区故障的影响。您可以使用创建节点所在的子网来控制工作节点创建的可用区。

如果您使用的是Kubernetes 1.18+版本，跨可用区域分布Pod的推荐方法是使用[Pod拓扑分布约束](https://kubernetes.io/docs/concepts/workloads/pods/pod-topology-spread-constraints/#spread-constraints-for-pods)。

下面的部署将尽可能跨可用区域分布Pod，如果不可能，也允许这些Pod运行:

```
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-server
spec:
  replicas: 3
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
          whenUnsatisfiable: ScheduleAnyway
          topologyKey: topology.kubernetes.io/zone
          labelSelector:
            matchLabels:
              app: web-server
      containers:
      - name: web-app
        image: nginx
        resources:
          requests:
            cpu: 1
```

!!! note
    `kube-scheduler`只通过带有这些标签的节点来感知拓扑域。如果上述部署被部署到只有单个区域的集群中，所有的Pod将调度到那些节点上，因为`kube-scheduler`不知道其他区域。为了使调度器按预期工作这种拓扑分布，必须在所有区域中已经存在节点。这个问题将在Kubernetes 1.24版本中通过添加`MinDomainsInPodToplogySpread`[特性门控](https://kubernetes.io/docs/concepts/workloads/pods/pod-topology-spread-constraints/#api)来解决，它允许指定一个`minDomains`属性来告知调度器可用域的数量。

!!! warning
    将`whenUnsatisfiable`设置为`DoNotSchedule`将导致如果无法满足拓扑分布约束，Pod将无法被调度。只有在您更希望Pod不运行而不是违反拓扑分布约束时，才应该这样设置。

在较旧版本的 Kubernetes 上，您可以使用 pod 反亲和性规则来跨多个可用区调度 pod。下面的清单告知 Kubernetes 调度器*优先*将 pod 调度到不同的可用区。

```
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-server
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
              topologyKey: failure-domain.beta.kubernetes.io/zone
            weight: 100
      containers:
      - name: web-app
        image: nginx
```

!!! warning
    不要要求将 pod 调度到不同的可用区，否则部署中的 pod 数量永远不会超过可用区的数量。

### 使用 EBS 卷时确保每个可用区有足够容量

如果您使用 [Amazon EBS 来提供持久卷](https://docs.aws.amazon.com/eks/latest/userguide/ebs-csi.html)，那么您需要确保 pod 和关联的 EBS 卷位于同一个可用区。在撰写本文时，EBS 卷仅在单个可用区内可用。Pod 无法访问位于不同可用区的基于 EBS 的持久卷。Kubernetes [调度器知道工作节点](https://kubernetes.io/docs/reference/kubernetes-api/labels-annotations-taints/#topologykubernetesiozone)所在的可用区。Kubernetes 将始终在与卷所在的同一可用区调度需要 EBS 卷的 Pod。但是，如果卷所在的可用区中没有可用的工作节点，则无法调度该 Pod。

为每个可用区创建具有足够容量的Auto Scaling组，以确保集群始终有能力在与它们需要的EBS卷相同的可用区中调度pod。此外，您应该启用Cluster Autoscaler中的`--balance-similar-node-groups`功能。

如果您运行的应用程序使用EBS卷但没有高可用性要求，那么您可以将应用程序的部署限制在单个可用区。在EKS中，工作节点会自动添加`failure-domain.beta.kubernetes.io/zone`标签，其中包含可用区的名称。您可以通过运行`kubectl get nodes --show-labels`来查看附加到节点的标签。有关内置节点标签的更多信息，请参见[此处](https://kubernetes.io/docs/concepts/configuration/assign-pod-node/#built-in-node-labels)。您可以使用节点选择器在特定可用区中调度pod。

在下面的示例中，pod将仅在`us-west-2c`可用区中调度:

```
apiVersion: v1
kind: Pod
metadata:
  name: single-az-pod
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: failure-domain.beta.kubernetes.io/zone
            operator: In
            values:
            - us-west-2c
  containers:
  - name: single-az-container
    image: kubernetes/pause
```

持久卷(由EBS支持)也会自动标记可用区的名称;您可以通过运行`kubectl get pv -L topology.ebs.csi.aws.com/zone`来查看持久卷所属的可用区。当创建pod并声明卷时，Kubernetes将在与该卷相同的可用区中的节点上调度Pod。

考虑这种情况;您有一个 EKS 集群，其中有一个节点组。该节点组在三个可用区中分布有三个工作节点。您有一个使用 EBS 支持的持久卷的应用程序。当您创建此应用程序及其相应的卷时，它的 Pod 会在三个可用区中的第一个可用区中创建。然后，运行此 Pod 的工作节点变为不健康并随后无法使用。集群自动缩放器将用新的工作节点替换不健康的节点;但是，由于自动缩放组跨越三个可用区，新的工作节点可能会在第二或第三个可用区中启动，而不是按需求在第一个可用区中启动。由于受可用区约束的 EBS 卷仅存在于第一个可用区，但在该可用区中没有可用的工作节点，因此无法调度该 Pod。因此，您应该在每个可用区中创建一个节点组，以便总是有足够的容量来运行无法在其他可用区中调度的 Pod。

或者，[EFS](https://github.com/kubernetes-sigs/aws-efs-csi-driver) 可以在运行需要持久存储的应用程序时简化集群自动缩放。客户端可以从该区域中的所有可用区并发访问 EFS 文件系统。即使使用 EFS 支持的持久卷的 Pod 被终止并在不同的可用区中重新调度，它也能够挂载该卷。

### 运行 node-problem-detector

工作节点中的故障可能会影响您的应用程序的可用性。[node-problem-detector](https://github.com/kubernetes/node-problem-detector) 是一个 Kubernetes 插件，您可以在集群中安装它来检测工作节点问题。您可以使用 [npd 的补救系统](https://github.com/kubernetes/node-problem-detector#remedy-systems)自动排空和终止该节点。

### 为系统和 Kubernetes 守护进程保留资源

您可以通过[为操作系统和Kubernetes守护进程预留计算资源](https://kubernetes.io/docs/tasks/administer-cluster/reserve-compute-resources/)来提高工作节点的稳定性。如果没有声明`limits`，Pods(尤其是那些没有声明`limits`的Pods)可能会耗尽系统资源，导致节点处于操作系统进程和Kubernetes守护进程(`kubelet`、容器运行时等)与Pods竞争系统资源的情况。您可以使用`kubelet`标志`--system-reserved`和`--kube-reserved`分别为系统进程(`udev`、`sshd`等)和Kubernetes守护进程预留资源。

如果您使用[EKS优化的Linux AMI](https://docs.aws.amazon.com/eks/latest/userguide/eks-optimized-ami.html)，则默认情况下会为系统和Kubernetes守护进程预留CPU、内存和存储。当基于此AMI启动工作节点时，EC2用户数据将配置为触发[`bootstrap.sh`脚本](https://github.com/awslabs/amazon-eks-ami/blob/master/files/bootstrap.sh)。此脚本根据EC2实例上可用的CPU内核数和总内存计算CPU和内存预留。计算出的值将写入位于`/etc/kubernetes/kubelet/kubelet-config.json`的`KubeletConfiguration`文件。

如果您在节点上运行自定义守护进程，并且默认情况下预留的CPU和内存量不足，您可能需要增加系统资源预留。

`eksctl`提供了最简单的方式来自定义[系统和Kubernetes守护进程的资源预留](https://eksctl.io/usage/customizing-the-kubelet/)。

### 实现QoS

对于关键应用程序，请考虑为Pod中的容器定义`requests`=`limits`。这将确保如果另一个Pod请求资源，该容器不会被杀死。

为所有容器实现CPU和内存限制是一种最佳实践，因为它可以防止容器无意中消耗系统资源，从而影响其他并存进程的可用性。

### 为所有工作负载配置和调整资源请求/限制

为工作负载调整资源请求和限制可以应用以下一般指导原则:

- 不要为CPU指定资源限制。在没有限制的情况下，请求充当[容器获得相对CPU时间的权重](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/#how-pods-with-resource-limits-are-run)。这允许您的工作负载使用全部CPU，而不会受到人为限制或资源饥饿。

- 对于非CPU资源，配置`requests`=`limits`可提供最可预测的行为。如果`requests`!=`limits`,容器的[QOS](https://kubernetes.io/docs/tasks/configure-pod-container/quality-service-pod/#qos-classes)也会从Guaranteed降低到Burstable，从而更容易在[节点压力](https://kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/)事件中被驱逐。

- 对于非CPU资源，不要指定远大于请求的限制。配置的`limits`相对于`requests`越大，节点就越有可能过度使用资源，从而导致工作负载中断的可能性越高。

- 正确调整请求尺寸对于使用诸如[Karpenter](https://aws.github.io/aws-eks-best-practices/karpenter/)或[Cluster AutoScaler](https://aws.github.io/aws-eks-best-practices/cluster-autoscaling/)之类的节点自动缩放解决方案尤为重要。这些工具会根据您的工作负载请求来确定要供应的节点数量和大小。如果您的请求过小而限制过大，您可能会发现您的工作负载被驱逐或因内存不足而被终止，因为它们被密集地打包在一个节点上。

确定资源请求可能很困难，但像[Vertical Pod Autoscaler](https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler)这样的工具可以通过观察运行时容器的资源使用情况来帮助您"调整"请求大小。其他可能有助于确定请求大小的工具包括:

- [Goldilocks](https://github.com/FairwindsOps/goldilocks)
- [Parca](https://www.parca.dev/)
- [Prodfiler](https://prodfiler.com/)
- [rsg](https://mhausenblas.info/right-size-guide/)

### 为命名空间配置资源配额

命名空间旨在用于跨多个团队或项目的多用户环境。它们为名称提供了一个范围，并且是在多个团队、项目、工作负载之间划分集群资源的一种方式。您可以限制命名空间中的总体资源消耗。[`ResourceQuota`](https://kubernetes.io/docs/concepts/policy/resource-quotas/)对象可以通过类型限制可以在命名空间中创建的对象的数量，以及该项目中的资源可能消耗的总计算资源量。您可以限制在给定命名空间中可以请求的总存储和/或计算(CPU和内存)资源量。

> 如果为命名空间启用了诸如CPU和内存之类的计算资源的资源配额，则用户必须为该命名空间中的每个容器指定请求或限制。

考虑为每个命名空间配置配额。考虑使用`LimitRanges`自动将预配置的限制应用于命名空间内的容器。

### 限制命名空间内的容器资源使用

资源配额有助于限制命名空间可以使用的资源量。[`LimitRange`对象](https://kubernetes.io/docs/concepts/policy/limit-range/)可以帮助您实现容器可以请求的最小和最大资源。使用`LimitRange`您可以为容器设置默认请求和限制，如果在您的组织中设置计算资源限制不是标准做法，这将很有帮助。顾名思义，`LimitRange`可以在命名空间中强制每个Pod或容器的最小和最大计算资源使用。以及，在命名空间中强制每个PersistentVolumeClaim的最小和最大存储请求。

考虑将 `LimitRange` 与 `ResourceQuota` 一起使用，以在容器和命名空间级别强制执行限制。设置这些限制将确保容器或命名空间不会侵占集群中其他租户使用的资源。

## CoreDNS

CoreDNS 在 Kubernetes 中履行名称解析和服务发现功能。它默认安装在 EKS 集群上。为了互操作性，CoreDNS 的 Kubernetes 服务仍被命名为 [kube-dns](https://kubernetes.io/docs/tasks/administer-cluster/dns-custom-nameservers/)。CoreDNS Pod 作为 Deployment 的一部分运行在 `kube-system` 命名空间中，在 EKS 中，默认情况下，它运行两个副本，并声明了请求和限制。DNS 查询被发送到运行在 `kube-system` 命名空间中的 `kube-dns` 服务。

## 建议
### 监控 CoreDNS 指标
CoreDNS 内置支持 [Prometheus](https://github.com/coredns/coredns/tree/master/plugin/metrics)。您应该特别考虑监控 CoreDNS 延迟 (`coredns_dns_request_duration_seconds_sum`,在 [1.7.0](https://github.com/coredns/coredns/blob/master/notes/coredns-1.7.0.md) 版本之前，该指标被称为 `core_dns_response_rcode_count_total`)、错误 (`coredns_dns_responses_total`, NXDOMAIN, SERVFAIL, FormErr) 和 CoreDNS Pod 的内存消耗。

出于故障排查目的，您可以使用 kubectl 查看 CoreDNS 日志:

```shell
for p in $(kubectl get pods -n kube-system -l k8s-app=kube-dns -o jsonpath='{.items[*].metadata.name}'); do kubectl logs $p -n kube-system; done
```

### 使用 NodeLocal DNSCache
您可以通过运行 [NodeLocal DNSCache](https://kubernetes.io/docs/tasks/administer-cluster/nodelocaldns/) 来提高集群 DNS 性能。此功能在集群节点上以 DaemonSet 的形式运行 DNS 缓存代理。所有 Pod 都使用运行在节点上的 DNS 缓存代理进行名称解析，而不是使用 `kube-dns` 服务。

### 为 CoreDNS 配置 cluster-proportional-scaler

提高 Cluster DNS 性能的另一种方法是根据集群中的节点数量和 CPU 核心数[自动水平扩展 CoreDNS Deployment](https://kubernetes.io/docs/tasks/administer-cluster/dns-horizontal-autoscaling/#enablng-dns-horizontal-autoscaling)。[Horizontal cluster-proportional-autoscaler](https://github.com/kubernetes-sigs/cluster-proportional-autoscaler/blob/master/README.md) 是一个容器，它根据可调度数据平面的大小调整 Deployment 的副本数量。

节点和节点中 CPU 核心的总和是您可以扩展 CoreDNS 的两个指标。您可以同时使用这两个指标。如果您使用较大的节点，CoreDNS 的扩展将基于 CPU 核心数。而如果您使用较小的节点，CoreDNS 副本的数量则取决于您的数据平面中的 CPU 核心数。比例自动缩放器配置如下所示：

```
linear: '{"coresPerReplica":256,"min":1,"nodesPerReplica":16}'
```

### 为节点组选择 AMI
EKS 提供了优化的 EC2 AMI，客户可以使用这些 AMI 创建自管理和托管的节点组。这些 AMI 在每个区域的每个受支持的 Kubernetes 版本中都有发布。当发现任何 CVE 或错误时，EKS 会将这些 AMI 标记为已弃用。因此，建议在为节点组选择 AMI 时不要使用已弃用的 AMI。

可以使用以下命令通过 Ec2 describe-images api 过滤已弃用的 AMI：

```
aws ec2 describe-images --image-id ami-0d551c4f633e7679c --no-include-deprecated
```

您也可以通过验证 describe-image 输出是否包含 DeprecationTime 字段来识别已弃用的 AMI。例如：

```
aws ec2 describe-images --image-id ami-xxx --no-include-deprecated
{
    "Images": [
        {
            "Architecture": "x86_64",
            "CreationDate": "2022-07-13T15:54:06.000Z",
            "ImageId": "ami-xxx",
            "ImageLocation": "123456789012/eks_xxx",
            "ImageType": "machine",
            "Public": false,
            "OwnerId": "123456789012",
            "PlatformDetails": "Linux/UNIX",
            "UsageOperation": "RunInstances",
            "State": "available",
            "BlockDeviceMappings": [
                {
                    "DeviceName": "/dev/xvda",
                    "Ebs": {
                        "DeleteOnTermination": true,
                        "SnapshotId": "snap-0993a2fc4bbf4f7f4",
                        "VolumeSize": 20,
                        "VolumeType": "gp2",
                        "Encrypted": false
                    }
                }
            ],
            "Description": "EKS Kubernetes Worker AMI with AmazonLinux2 image, (k8s: 1.19.15, docker: 20.10.13-2.amzn2, containerd: 1.4.13-3.amzn2)",
            "EnaSupport": true,
            "Hypervisor": "xen",
            "Name": "aws_eks_optimized_xxx",
            "RootDeviceName": "/dev/xvda",
            "RootDeviceType": "ebs",
            "SriovNetSupport": "simple",
            "VirtualizationType": "hvm",
            "DeprecationTime": "2023-02-09T19:41:00.000Z"
        }
    ]
}
```