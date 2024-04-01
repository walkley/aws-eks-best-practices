# Karpenter 最佳实践

## Karpenter

Karpenter 是一个开源集群自动扩缩器，它会自动响应无法调度的 Pod 而提供新节点。Karpenter 会评估待处理 Pod 的总体资源需求，并选择最佳实例类型来运行它们。它会自动缩减或终止没有任何非 DaemonSet Pod 的实例以减少浪费。它还支持一个整合功能，可以主动移动 Pod，并删除或替换为更便宜版本的节点以降低集群成本。

**使用 Karpenter 的原因**

在 Karpenter 推出之前，Kubernetes 用户主要依赖于 [Amazon EC2 Auto Scaling groups](https://docs.aws.amazon.com/autoscaling/ec2/userguide/AutoScalingGroup.html) 和 [Kubernetes Cluster Autoscaler](https://github.com/kubernetes/autoscaler/tree/master/cluster-autoscaler) (CAS) 来动态调整集群的计算能力。使用 Karpenter，您无需创建数十个节点组就能获得与 Karpenter 一样的灵活性和多样性。此外，Karpenter 与 Kubernetes 版本的耦合性不像 CAS 那么紧密，也不需要您在 AWS 和 Kubernetes API 之间来回切换。

Karpenter 将实例编排职责合并到一个系统中，这更简单、更稳定，并且对集群有意识。Karpenter 旨在通过提供简化的方式来克服 Cluster Autoscaler 带来的一些挑战:

* 根据工作负载需求提供节点。
* 通过灵活的 NodePool 选项按实例类型创建不同的节点配置。与管理许多特定的自定义节点组不同，Karpenter 可以让您使用单个灵活的 NodePool 来管理不同工作负载的容量。
* 通过快速启动节点和调度 Pod，实现大规模 Pod 调度的改进。

有关使用 Karpenter 的信息和文档，请访问 [karpenter.sh](https://karpenter.sh/) 网站。

## 建议

最佳实践分为关于 Karpenter 本身、节点池和 pod 调度的几个部分。

## Karpenter 最佳实践

以下最佳实践涵盖了与 Karpenter 本身相关的主题。

### 对于容量需求不断变化的工作负载使用 Karpenter

与 [Auto Scaling Groups](https://aws.amazon.com/blogs/containers/amazon-eks-cluster-multi-zone-auto-scaling-groups/) (ASG) 和 [Managed Node Groups](https://docs.aws.amazon.com/eks/latest/userguide/managed-node-groups.html) (MNG) 相比，Karpenter 将扩缩容管理更接近于 Kubernetes 原生 API。ASG 和 MNG 是 AWS 原生抽象，其扩缩容触发基于 AWS 级别的指标，例如 EC2 CPU 负载。[Cluster Autoscaler](https://docs.aws.amazon.com/eks/latest/userguide/autoscaling.html#cluster-autoscaler) 将 Kubernetes 抽象桥接到 AWS 抽象，但由于这种方式失去了一些灵活性，例如针对特定可用区域进行调度。

Karpenter 移除了一层 AWS 抽象，将一些灵活性直接带入 Kubernetes。Karpenter 最适合用于工作负载遇到高峰期或具有不同计算需求的集群。MNG 和 ASG 适合运行工作负载相对静态和一致的集群。根据需求，您可以混合使用动态和静态管理的节点。

### 在以下情况考虑其他自动扩缩容项目...

如果您需要 Karpenter 目前尚未开发的功能。由于 Karpenter 是一个相对较新的项目，如果您暂时需要 Karpenter 尚未包含的功能，请考虑其他自动扩缩容项目。

### 在 EKS Fargate 上或属于某个节点组的工作节点上运行 Karpenter 控制器

Karpenter 使用 [Helm 图表](https://karpenter.sh/docs/getting-started/)进行安装。Helm 图表会安装 Karpenter 控制器和一个 Webhook Pod 作为 Deployment，在控制器可用于扩展集群之前需要运行这些 Pod。我们建议至少有一个小型节点组，其中至少有一个工作节点。作为替代方案，您可以通过为 `karpenter` 命名空间创建 Fargate 配置文件，在 EKS Fargate 上运行这些 Pod。这样做会导致部署到此命名空间的所有 Pod 都在 EKS Fargate 上运行。不要在由 Karpenter 管理的节点上运行 Karpenter。

### 避免使用自定义启动模板与 Karpenter

Karpenter 强烈建议不要使用自定义启动模板。使用自定义启动模板会阻止多架构支持、自动升级节点的能力以及安全组发现。使用启动模板也可能导致混淆，因为某些字段在 Karpenter 的 NodePools 中重复，而其他字段则被 Karpenter 忽略，例如子网和实例类型。

您通常可以通过使用自定义用户数据和/或在 AWS 节点模板中直接指定自定义 AMI 来避免使用启动模板。有关如何执行此操作的更多信息，请参阅 [NodeClasses](https://karpenter.sh/docs/concepts/nodeclasses/)。

### 排除不适合您工作负载的实例类型

如果集群中运行的工作负载不需要特定实例类型，请考虑使用 [node.kubernetes.io/instance-type](http://node.kubernetes.io/instance-type) 键排除这些实例类型。

以下示例展示了如何避免配置大型 Graviton 实例。

```yaml
- key: node.kubernetes.io/instance-type
  operator: NotIn
  values:
  - m6g.16xlarge
  - m6gd.16xlarge
  - r6g.16xlarge
  - r6gd.16xlarge
  - c6g.16xlarge
```

### 在使用 Spot 实例时启用中断处理

Karpenter支持[原生中断处理](https://karpenter.sh/docs/concepts/disruption/#interruption)，通过`--interruption-queue-name` CLI参数启用，并指定SQS队列的名称。中断处理会监视即将发生的非自愿中断事件，这些事件可能会导致您的工作负载中断，例如:

* Spot实例中断警告
* 计划的变更健康事件(维护事件)
* 实例终止事件
* 实例停止事件

当Karpenter检测到这些事件将发生在您的节点上时，它会自动封锁、排空和终止节点，以在中断事件发生前为工作负载清理提供最大的时间。不建议与Karpenter一起使用AWS Node Termination Handler，原因如[此处](https://karpenter.sh/docs/faq/#interruption-handling)所述。

需要检查点或其他形式的优雅排空的Pod，在关机前需要2分钟，应该在其集群中启用Karpenter中断处理。

### **无出站互联网访问的Amazon EKS私有集群**

当在没有路由到互联网的VPC中配置EKS集群时，您必须确保已根据EKS文档中出现的私有集群[要求](https://docs.aws.amazon.com/eks/latest/userguide/private-clusters.html#private-cluster-requirements)配置了环境。此外，您需要确保在VPC中创建了STS VPC区域端点。否则，您将看到类似于下面显示的错误。

```console
{"level":"FATAL","time":"2024-02-29T14:28:34.392Z","logger":"controller","message":"Checking EC2 API connectivity, WebIdentityErr: failed to retrieve credentials\ncaused by: RequestError: send request failed\ncaused by: Post \"https://sts.<region>.amazonaws.com/\": dial tcp 54.239.32.126:443: i/o timeout","commit":"596ea97"}
```

这些更改在私有集群中是必需的，因为 Karpenter 控制器使用 IAM 角色服务账户 (IRSA)。配置了 IRSA 的 Pod 通过调用 AWS 安全令牌服务 (AWS STS) API 来获取凭证。如果没有出站互联网访问权限，您必须在 VPC 中创建并使用 ***AWS STS VPC 终端节点***。

私有集群还需要您创建 ***SSM 的 VPC 终端节点***。当 Karpenter 尝试供应新节点时，它会查询启动模板配置和 SSM 参数。如果您的 VPC 中没有 SSM VPC 终端节点，将导致以下错误:

```console
{"level":"ERROR","time":"2024-02-29T14:28:12.889Z","logger":"controller","message":"Unable to hydrate the AWS launch template cache, RequestCanceled: request context canceled\ncaused by: context canceled","commit":"596ea97","tag-key":"karpenter.k8s.aws/cluster","tag-value":"eks-workshop"}
...
{"level":"ERROR","time":"2024-02-29T15:08:58.869Z","logger":"controller.nodeclass","message":"discovering amis from ssm, getting ssm parameter \"/aws/service/eks/optimized-ami/1.27/amazon-linux-2/recommended/image_id\", RequestError: send request failed\ncaused by: Post \"https://ssm.<region>.amazonaws.com/\": dial tcp 67.220.228.252:443: i/o timeout","commit":"596ea97","ec2nodeclass":"default","query":"/aws/service/eks/optimized-ami/1.27/amazon-linux-2/recommended/image_id"}
```

没有 ***[价格列表查询 API](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/using-pelong.html) 的 VPC 终端节点***。
因此，定价数据将随着时间的推移而过时。
Karpenter 通过在其二进制文件中包含按需定价数据来解决这个问题，但只有在升级 Karpenter 时才会更新该数据。
定价数据请求失败将导致以下错误消息:

```console
{"level":"ERROR","time":"2024-02-29T15:08:58.522Z","logger":"controller.pricing","message":"获取按需定价数据时出错， RequestError: 发送请求失败\n原因: Post \"https://api.pricing.<region>.amazonaws.com/\": 拨号tcp 18.196.224.8:443: i/o超时; RequestError: 发送请求失败\n原因: Post \"https://api.pricing.<region>.amazonaws.com/\": 拨号tcp 18.185.143.117:443: i/o超时","commit":"596ea97"}
```

总之，要在完全私有的 EKS 集群中使用 Karpenter，您需要创建以下 VPC 终端节点:

```console
com.amazonaws.<region>.ec2
com.amazonaws.<region>.ecr.api
com.amazonaws.<region>.ecr.dkr
com.amazonaws.<region>.s3 – 用于拉取容器镜像
com.amazonaws.<region>.sts – 用于服务账户的 IAM 角色
com.amazonaws.<region>.ssm - 用于解析默认 AMI
com.amazonaws.<region>.sqs - 如果使用中断处理，则用于访问 SQS
```

!!! note
    Karpenter (控制器和 Webhook 部署)容器镜像必须在 Amazon ECR 私有或其他可从 VPC 内部访问的私有注册表中。原因是 Karpenter 控制器和 Webhook Pod 当前使用公共 ECR 镜像。如果这些镜像在 VPC 内部或与 VPC 对等的网络中不可用，那么当 Kubernetes 尝试从 ECR 公共拉取这些镜像时，您将得到镜像拉取错误。

更多信息，请参阅 [Issue 988](https://github.com/aws/karpenter/issues/988) 和 [Issue 1157](https://github.com/aws/karpenter/issues/1157)。

## 创建节点池

以下最佳实践涵盖了与创建节点池相关的主题。

### 在以下情况下创建多个节点池...

当不同团队共享集群并需要在不同的工作节点上运行工作负载时，或者有不同的操作系统或实例类型要求时，请创建多个节点池。例如，一个团队可能希望使用 Bottlerocket，而另一个团队可能希望使用 Amazon Linux。同样，一个团队可能可以访问昂贵的 GPU 硬件，而另一个团队则不需要。使用多个节点池可以确保每个团队都可以使用最合适的资源。

### 创建互斥或加权的节点池

建议创建互斥或加权的节点池，以提供一致的调度行为。如果没有这样做，并且多个节点池都匹配，Karpenter 将随机选择使用哪一个，从而导致意外结果。创建多个节点池的有用示例包括:

创建一个带有 GPU 的节点池，并且只允许特殊工作负载在这些(昂贵的)节点上运行:

```yaml
# NodePool for GPU Instances with Taints
apiVersion: karpenter.sh/v1beta1
kind: NodePool
metadata:
  name: gpu
spec:
  disruption:
    consolidateAfter: 1m0s
    consolidationPolicy: WhenEmpty
    expireAfter: Never
  template:
    metadata: {}
    spec:
      nodeClassRef:
        name: default
      requirements:
      - key: node.kubernetes.io/instance-type
        operator: In
        values:
        - p3.8xlarge
        - p3.16xlarge
      - key: kubernetes.io/os
        operator: In
        values:
        - linux
      - key: kubernetes.io/arch
        operator: In
        values:
        - amd64
      - key: karpenter.sh/capacity-type
        operator: In
        values:
        - on-demand
      taints:
      - effect: NoSchedule
        key: nvidia.com/gpu
        value: "true"
```

具有容忍污点的部署:

```yaml
# 部署 GPU 工作负载时将定义容忍度
apiVersion: apps/v1
kind: Deployment
metadata:
  name: inflate-gpu
spec:
  ...
    spec:
      tolerations:
      - key: "nvidia.com/gpu"
        operator: "Exists"
        effect: "NoSchedule"
```

对于另一个团队的通用部署，NodePool 规范可能包括 nodeAffinify。然后 Deployment 可以使用 nodeSelectorTerms 来匹配 `billing-team`。

```yaml
# 用于常规 EC2 实例的 NodePool
apiVersion: karpenter.sh/v1beta1
kind: NodePool
metadata:
  name: generalcompute
spec:
  disruption:
    expireAfter: Never
  template:
    metadata:
      labels:
        billing-team: my-team
    spec:
      nodeClassRef:
        name: default
      requirements:
      - key: node.kubernetes.io/instance-type
        operator: In
        values:
        - m5.large
        - m5.xlarge
        - m5.2xlarge
        - c5.large
        - c5.xlarge
        - c5a.large
        - c5a.xlarge
        - r5.large
        - r5.xlarge
      - key: kubernetes.io/os
        operator: In
        values:
        - linux
      - key: kubernetes.io/arch
        operator: In
        values:
        - amd64
      - key: karpenter.sh/capacity-type
        operator: In
        values:
        - on-demand
```

使用 nodeAffinity 的 Deployment：

```yaml
# Deployment 将定义 spec.affinity.nodeAffinity
kind: Deployment
metadata:
  name: workload-my-team
spec:
  replicas: 200
  ...
    spec:
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
              - matchExpressions:
                - key: "billing-team"
                  operator: "In"
                  values: ["my-team"]
```

### 使用计时器（TTL）自动从集群中删除节点

您可以在预配置的节点上使用计时器来设置何时删除没有工作负载 Pod 或已达到过期时间的节点。节点过期可用作升级的一种方式，以便淘汰旧节点并用更新版本替换。有关使用 `spec.disruption.expireAfter` 配置节点过期的信息，请参阅 Karpenter 文档中的[过期](https://karpenter.sh/docs/concepts/disruption/)。

### 避免过度限制 Karpenter 可以预配置的实例类型，尤其是在使用 Spot 时

在使用 Spot 时，Karpenter 使用[价格容量优化](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-fleet-allocation-strategy.html)分配策略来预配置 EC2 实例。该策略指示 EC2 从您要启动的实例数量的最深池中预配置实例，并且具有最低的中断风险。然后 EC2 Fleet 从这些池中价格最低的池中请求 Spot 实例。您允许 Karpenter 使用的实例类型越多，EC2 就越能优化您的 Spot 实例的运行时间。默认情况下，Karpenter 将使用 EC2 在您的集群所在的区域和可用区中提供的所有实例类型。Karpenter 根据待处理的 Pod 智能地从所有实例类型集合中进行选择，以确保您的 Pod 被调度到适当大小和配置的实例上。例如，如果您的 Pod 不需要 GPU，Karpenter 就不会将您的 Pod 调度到支持 GPU 的 EC2 实例类型上。当您不确定要使用哪些实例类型时，可以运行 Amazon [ec2-instance-selector](https://github.com/aws/amazon-ec2-instance-selector) 来生成与您的计算要求匹配的实例类型列表。例如，该 CLI 将内存、vCPU、架构和区域作为输入参数，并为您提供满足这些约束的 EC2 实例列表。

```console
$ ec2-instance-selector --memory 4 --vcpus 2 --cpu-architecture x86_64 -r ap-southeast-1
c5.large
c5a.large
c5ad.large
c5d.large
c6i.large
t2.medium
t3.medium
t3a.medium
```

在使用Spot实例时，您不应该对Karpenter设置太多约束，因为这样做可能会影响您的应用程序的可用性。例如，如果某种特定类型的实例全部被回收，而没有合适的替代实例可用于替换它们，那么您的pod将保持挂起状态，直到为配置的实例类型补充了spot容量。您可以通过跨不同可用区域分布实例来降低容量不足错误的风险，因为不同可用区域的spot池是不同的。也就是说，使用Spot时的一般最佳实践是允许Karpenter使用多种不同的实例类型。

## 调度Pod

以下最佳实践与使用Karpenter进行节点供应时在集群中部署pod有关。

### 遵循EKS高可用性最佳实践

如果您需要运行高度可用的应用程序，请遵循一般EKS最佳实践[建议](https://aws.github.io/aws-eks-best-practices/reliability/docs/application/#recommendations)。有关如何跨节点和区域分布pod的详细信息，请参阅Karpenter文档中的[拓扑扩展](https://karpenter.sh/docs/concepts/scheduling/#topology-spread)。使用[中断预算](https://karpenter.sh/docs/troubleshooting/#disruption-budgets)设置在尝试驱逐或删除pod时需要维护的最小可用pod数量。

### 使用分层约束来限制您的云提供商提供的计算功能

Karpenter的分层约束模型允许您创建一个复杂的NodePool和pod部署约束集，以获得pod调度的最佳匹配。pod规范可以请求的约束示例包括以下内容:

* 需要在只有特定应用程序可用的可用区域中运行。例如，您有一个 pod 需要与另一个运行在特定可用区域的 EC2 实例上的应用程序进行通信。如果您的目标是减少 VPC 中的跨可用区流量，您可能希望将 pod 与 EC2 实例位于同一可用区域。这种定位通常使用节点选择器来实现。有关[节点选择器](https://karpenter.sh/docs/concepts/scheduling/#selecting-nodes)的更多信息，请参阅 Kubernetes 文档。
* 需要特定类型的处理器或其他硬件。请参阅 Karpenter 文档中的[加速器](https://karpenter.sh/docs/concepts/scheduling/#acceleratorsgpu-resources)部分，了解需要在 GPU 上运行的 pod 的 podspec 示例。

### 创建计费警报以监控您的计算支出

当您配置集群自动扩缩容时，您应该创建计费警报，以在支出超过阈值时发出警告，并在 Karpenter 配置中添加资源限制。使用 Karpenter 设置资源限制类似于设置 AWS 自动扩缩组的最大容量，它代表 Karpenter NodePool 可以实例化的最大计算资源量。

!!! note
    无法为整个集群设置全局限制。限制适用于特定的 NodePools。

下面的代码段告诉 Karpenter 最多只能配置 1000 个 CPU 核心和 1000Gi 内存。只有在达到或超过限制时，Karpenter 才会停止添加容量。当超过限制时，Karpenter 控制器会将 "memory resource usage of 1001 exceeds limit of 1000" 或类似的消息写入控制器的日志中。如果您将容器日志路由到 CloudWatch 日志，您可以创建一个[指标过滤器](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/MonitoringLogData.html)来查找日志中的特定模式或术语，然后创建一个[CloudWatch 警报](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/AlarmThatSendsEmail.html)以在您配置的指标阈值被违反时通知您。

有关在 Karpenter 中使用限制的更多信息，请参阅 Karpenter 文档中的[设置资源限制](https://karpenter.sh/docs/concepts/nodepools/#speclimits)。

```yaml
spec:
  limits:
    cpu: 1000
    memory: 1000Gi
```

如果您不使用限制或限制 Karpenter 可以配置的实例类型，Karpenter 将根据需要继续为您的集群添加计算容量。虽然以这种方式配置 Karpenter 允许您的集群自由扩展，但也可能会产生重大的成本影响。正因为如此，我们建议配置计费警报。计费警报允许您在您的账户中计算的估计费用超过定义的阈值时得到警报和主动通知。有关更多信息，请参阅[设置 Amazon CloudWatch 计费警报以主动监控估计费用](https://aws.amazon.com/blogs/mt/setting-up-an-amazon-cloudwatch-billing-alarm-to-proactively-monitor-estimated-charges/)。

您也可以启用成本异常检测功能，这是AWS成本管理的一项功能，利用机器学习持续监控您的成本和使用情况，以检测异常支出。更多信息可以在[AWS成本异常检测入门指南](https://docs.aws.amazon.com/cost-management/latest/userguide/getting-started-ad.html)中找到。如果您已经在AWS Budgets中创建了预算，您还可以配置一个操作来在特定阈值被触发时通知您。通过预算操作，您可以发送电子邮件、发布消息到SNS主题或向Slack等聊天机器人发送消息。更多信息请参见[配置AWS Budgets操作](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-controls.html)。

### 使用karpenter.sh/do-not-disrupt注解防止Karpenter取消配置节点

如果您在Karpenter配置的节点上运行关键应用程序，例如*长时间运行*的批处理作业或有状态应用程序，*并且*节点的TTL已过期，当实例终止时，应用程序将被中断。通过向pod添加`karpenter.sh/karpenter.sh/do-not-disrupt`注解，您指示Karpenter保留该节点，直到Pod终止或删除`karpenter.sh/do-not-disrupt`注解。有关更多信息，请参阅[中断](https://karpenter.sh/docs/concepts/disruption/#node-level-controls)文档。

如果节点上仅剩与作业相关的非daemonset pod，只要作业状态为succeed或failed，Karpenter就能够定位和终止这些节点。

### 在使用整合时为所有非CPU资源配置requests=limits

整合和调度通常是通过比较 pod 的资源请求与节点上可分配的资源量来工作的。资源限制不被考虑在内。例如，内存限制大于内存请求的 pod 可能会超过请求值。如果同一节点上的多个 pod 同时超过限制，这可能会导致部分 pod 由于内存不足 (OOM) 而被终止。整合可能会增加这种情况发生的可能性，因为它只考虑 pod 的请求来将 pod 打包到节点上。

### 使用 LimitRanges 配置资源请求和限制的默认值

由于 Kubernetes 不设置默认请求或限制，容器从底层主机、CPU 和内存的资源消耗是无限制的。Kubernetes 调度程序查看 pod 的总请求(来自 pod 容器的总请求或 pod 的 Init 容器的总资源中的较高值)来确定将 pod 调度到哪个工作节点上。同样，Karpenter 考虑 pod 的请求来确定它需要配置什么类型的实例。您可以使用限制范围为某个命名空间应用合理的默认值，以防某些 pod 未指定资源请求。

请参阅 [为命名空间配置默认内存请求和限制](https://kubernetes.io/docs/tasks/administer-cluster/manage-resources/memory-default-namespace/)

### 为所有工作负载应用准确的资源请求

当 Karpenter 对您的工作负载需求有准确的信息时，它就能够启动最适合您的工作负载的节点。如果使用 Karpenter 的整合功能，这一点尤其重要。

请参阅 [为所有工作负载配置和调整资源请求/限制](https://aws.github.io/aws-eks-best-practices/reliability/docs/dataplane/#configure-and-size-resource-requestslimits-for-all-workloads)

## CoreDNS 建议

### 更新 CoreDNS 配置以保持可靠性
在将 CoreDNS pod 部署到由 Karpenter 管理的节点上时，鉴于 Karpenter 快速终止/创建新节点以满足需求的动态特性，建议遵循以下最佳实践:

[CoreDNS lameduck duration](https://aws.github.io/aws-eks-best-practices/scalability/docs/cluster-services/#coredns-lameduck-duration)

[CoreDNS readiness probe](https://aws.github.io/aws-eks-best-practices/scalability/docs/cluster-services/#coredns-readiness-probe)

这将确保 DNS 查询不会被路由到尚未就绪或已被终止的 CoreDNS Pod。

## Karpenter 蓝图
由于 Karpenter 采用以应用为先的方式来为 Kubernetes 数据平面配置计算能力，因此您可能想知道如何正确配置一些常见的工作负载场景。[Karpenter 蓝图](https://github.com/aws-samples/karpenter-blueprints)是一个存储库，其中包含了一系列遵循此处所述最佳实践的常见工作负载场景。您将拥有所需的所有资源，甚至可以创建一个配置了 Karpenter 的 EKS 集群，并测试存储库中包含的每个蓝图。您可以组合不同的蓝图来最终为您的工作负载创建所需的蓝图。

## 其他资源
* [Karpenter/Spot 研讨会](https://ec2spotworkshops.com/karpenter.html)
* [Karpenter 节点配置器](https://youtu.be/_FXRIKWJWUk)
* [TGIK Karpenter](https://youtu.be/zXqrNJaTCrU)
* [Karpenter 与集群自动缩放器](https://youtu.be/3QsVRHVdOnM)
* [使用 Karpenter 实现无组自动缩放](https://www.youtube.com/watch?v=43g8uPohTgc)
* [教程: 使用 Amazon EC2 Spot 和 Karpenter 以更低成本运行 Kubernetes 集群](https://community.aws/tutorials/run-kubernetes-clusters-for-less-with-amazon-ec2-spot-and-karpenter#step-6-optional-simulate-spot-interruption)