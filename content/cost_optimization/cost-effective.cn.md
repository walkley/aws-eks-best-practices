# 高性价比资源
高性价比资源意味着为在Kubernetes集群上运行的工作负载使用适当的服务、资源和配置，从而节省成本。

## 建议
### 确保用于部署容器化服务的基础设施与应用程序配置文件和扩展需求相匹配

Amazon EKS支持几种类型的Kubernetes自动扩缩容 - [集群自动扩缩器](https://docs.aws.amazon.com/eks/latest/userguide/cluster-autoscaler.html)、[水平Pod自动扩缩器](https://docs.aws.amazon.com/eks/latest/userguide/horizontal-pod-autoscaler.html)和[垂直Pod自动扩缩器](https://docs.aws.amazon.com/eks/latest/userguide/vertical-pod-autoscaler.html)。本节介绍其中的两种，集群自动扩缩器和水平Pod自动扩缩器。

### 使用集群自动扩缩器根据当前需求调整Kubernetes集群的大小

[Kubernetes集群自动扩缩器](https://github.com/kubernetes/autoscaler/tree/master/cluster-autoscaler)在由于资源不足而无法启动Pod或集群中的节点利用率低且其Pod可以重新调度到集群中其他节点时，会自动调整EKS集群中节点的数量。集群自动扩缩器在任何指定的Auto Scaling组内扩缩工作节点，并作为部署运行在您的EKS集群中。

使用EC2托管节点组的Amazon EKS可以自动供应和管理Amazon EKS Kubernetes集群的节点(Amazon EC2实例)的生命周期。所有托管节点都作为Amazon EC2 Auto Scaling组的一部分供应，由Amazon EKS为您管理，包括Amazon EC2实例和Auto Scaling组在内的所有资源都运行在您的AWS账户中。Amazon EKS为托管节点组资源添加标签，以便Kubernetes集群自动扩缩器可以发现它们。

https://docs.aws.amazon.com/eks/latest/userguide/cluster-autoscaler.html 这份文档提供了设置托管节点组并部署 Kubernetes 集群自动扩缩器的详细指导。如果您在多个可用区域中运行由 Amazon EBS 卷支持的有状态应用程序并使用 Kubernetes 集群自动扩缩器，您应该为每个可用区域配置一个节点组。

*基于 EC2 的工作节点的集群自动扩缩器日志 -*
![Kubernetes 集群自动扩缩器日志](../images/cluster-auto-scaler.png)

当由于缺乏可用资源而无法调度 pod 时，集群自动扩缩器会确定集群必须扩容并增加节点组的大小。当使用多个节点组时，集群自动扩缩器会根据 Expander 配置选择一个。目前在 EKS 中支持以下策略:
+ **random** - 默认扩展器，随机选择实例组
+ **most-pods** - 选择可以调度最多 pod 的实例组。
+ **least-waste** - 选择扩容后将拥有最少空闲 CPU (如果相同，则选择空闲内存最少)的节点组。当您有不同类型的节点时(例如高 CPU 或高内存节点),并且只想在有待处理的 pod 需要大量这些资源时才扩容这些节点组时，这很有用。
+ **priority** - 选择用户分配的优先级最高的节点组

如果作为工作节点使用 EC2 Spot 实例，您可以为集群自动扩缩器中的 Expander 使用 **random** 放置策略。这是默认的扩展器，在集群必须扩容时会任意选择一个节点组。随机扩展器可最大限度地利用多个 Spot 容量池。

**[优先级](https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/expander/priority/readme.md)**基于扩展器根据用户为伸缩组分配的优先级选择扩展选项。示例优先级可以是让Autoscaler首先尝试扩展一个Spot实例节点组，如果无法扩展，则回退到扩展一个按需节点组。

**most-pods**基于扩展器在您使用nodeSelector确保某些pod落在某些节点上时很有用。

根据[文档](https://docs.aws.amazon.com/eks/latest/userguide/cluster-autoscaler.html)为集群自动缩放配置指定**least-waste**作为扩展器类型:


```
    spec:
      containers:
      - command:
        - ./cluster-autoscaler
        - --v=4
        - --stderrthreshold=info
        - --cloud-provider=aws
        - --skip-nodes-with-local-storage=false
        - --expander=least-waste
        - --node-group-auto-discovery=asg:tag=k8s.io/cluster-autoscaler/enabled,k8s.io/cluster-autoscaler/<YOUR CLUSTER NAME>
        - --balance-similar-node-groups
        - --skip-nodes-with-system-pods=false
```


### 部署Horizontal Pod Autoscaling以根据资源的CPU利用率或其他应用程序相关指标自动缩放部署、复制控制器或副本集中的Pod数量

[Kubernetes Horizontal Pod Autoscaler](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)根据资源指标(如CPU利用率)或自定义指标支持的其他应用程序提供的指标，自动缩放部署、复制控制器或副本集中的Pod数量。这可以帮助您的应用程序扩展以满足增加的需求，或在不需要资源时缩减，从而为其他应用程序释放工作节点。当您设置目标指标利用率百分比时，Horizontal Pod Autoscaler会扩展或缩减您的应用程序以尝试满足该目标。

k8s-cloudwatch-adapter](https://github.com/awslabs/k8s-cloudwatch-adapter) 是 Kubernetes 自定义指标 API 和外部指标 API 的一种实现，它与 CloudWatch 指标集成。它允许您使用 CloudWatch 指标通过水平 Pod 自动缩放器 (HPA) 来扩展您的 Kubernetes 部署。

要查看使用 CPU 等资源指标进行扩展的示例，请按照 https://eksworkshop.com/beginner/080_scaling/test_hpa/ 部署示例应用程序，执行简单的负载测试以测试 Pod 自动缩放，并模拟 Pod 自动缩放。

请参阅此[博客](https://aws.amazon.com/blogs/compute/scaling-kubernetes-deployments-with-amazon-cloudwatch-metrics/)，了解应用程序根据 Amazon SQS (Simple Queue Service) 队列中的消息数量进行扩展的自定义指标示例。

来自博客的 Amazon SQS 的外部指标示例:

```yaml
apiVersion: metrics.aws/v1alpha1
kind: ExternalMetric:
  metadata:
    name: hello-queue-length
  spec:
    name: hello-queue-length
    resource:
      resource: "deployment"
    queries:
      - id: sqs_helloworld
        metricStat:
          metric:
            namespace: "AWS/SQS"
            metricName: "ApproximateNumberOfMessagesVisible"
            dimensions:
              - name: QueueName
                value: "helloworld"
          period: 300
          stat: Average
          unit: Count
        returnData: true
```

利用此外部指标的 HPA 示例:

``` yaml
kind: HorizontalPodAutoscaler
apiVersion: autoscaling/v2beta1
metadata:
  name: sqs-consumer-scaler
spec:
  scaleTargetRef:
    apiVersion: apps/v1beta1
    kind: Deployment
    name: sqs-consumer
  minReplicas: 1
  maxReplicas: 10
  metrics:
  - type: External
    external:
      metricName: hello-queue-length
      targetAverageValue: 30
```

Kubernetes工作节点的集群自动缩放器和Pod的水平Pod自动缩放器的组合，将确保配置的资源尽可能接近实际利用率。

![Kubernetes Cluster AutoScaler and HPA](../images/ClusterAS-HPA.png)
***(图片来源: https://aws.amazon.com/blogs/containers/cost-optimization-for-kubernetes-on-aws/)***

***Amazon EKS with Fargate***

****Pod的水平自动缩放****

在Fargate上自动缩放EKS可以使用以下机制:

1. 使用Kubernetes指标服务器，并基于CPU和/或内存使用情况配置自动缩放。
2. 使用Prometheus和Prometheus指标适配器，基于自定义指标(如HTTP流量)配置自动缩放
3. 基于App Mesh流量配置自动缩放

上述场景在实践博客["使用自定义指标自动缩放EKS on Fargate"](https://aws.amazon.com/blogs/containers/autoscaling-eks-on-fargate-with-custom-metrics/)中有解释

****垂直Pod自动缩放****

对于在Fargate上运行的Pod，使用[垂直Pod自动缩放器](https://docs.aws.amazon.com/eks/latest/userguide/vertical-pod-autoscaler.html)来优化应用程序使用的CPU和内存。但是，由于更改Pod的资源分配需要重新启动Pod，因此必须将Pod更新策略设置为Auto或Recreate，以确保正确功能。

## 建议

### 在非工作时间使用下缩放来缩减Kubernetes Deployments、StatefulSets和/或HorizontalPodAutoscalers。

作为控制成本的一部分，下缩放未使用的资源也可以对总体成本产生巨大影响。有一些工具，如[kube-downscaler](https://github.com/hjacobs/kube-downscaler)和[Kubernetes的Descheduler](https://github.com/kubernetes-sigs/descheduler)。

**Kube-descaler**可用于在工作时间结束后或在设定的时间段内缩减Kubernetes部署。

**Kubernetes的Descheduler**,根据其策略，可以找到可以移动的pod并将其驱逐。在当前的实现中，kubernetes descheduler不会重新调度被驱逐的pod，而是依赖于默认的调度器

**Kube-descaler**

*安装kube-downscaler*:
```
git clone https://github.com/hjacobs/kube-downscaler
cd kube-downscaler
kubectl apply -k deploy/
```

示例配置使用--dry-run作为安全标志来防止缩减 - 删除它以启用缩减器，例如通过编辑部署:
```
$ kubectl edit deploy kube-downscaler
```

部署一个nginx pod，并安排在时区Mon-Fri 09:00-17:00 Asia/Kolkata运行:
```
$ kubectl run nginx1 --image=nginx
$ kubectl annotate deploy nginx1 'downscaler/uptime=Mon-Fri 09:00-17:00 Asia/Kolkata'
```
!!! note
    对于新的nginx部署，默认的宽限期为15分钟，即如果当前时间不在Mon-Fri 9-17(Asia/Kolkata时区),它将不会立即缩减，而是在15分钟后缩减。

![Kube-down-scaler for nginx](../images/kube-down-scaler.png)

更高级的缩减部署场景可在[kube-down-scaler github项目](https://github.com/hjacobs/kube-downscaler)中找到。

**Kubernetes descheduler**

Descheduler可以作为Job或CronJob在k8s集群内运行。Descheduler的策略是可配置的，并包括可启用或禁用的策略。目前已实现了七种策略*RemoveDuplicates*、*LowNodeUtilization*、*RemovePodsViolatingInterPodAntiAffinity*、*RemovePodsViolatingNodeAffinity*、*RemovePodsViolatingNodeTaints*、*RemovePodsHavingTooManyRestarts*和*PodLifeTime*。更多详细信息可在其[文档](https://github.com/kubernetes-sigs/descheduler)中找到。

一个示例策略，其中descheduler针对节点的低CPU利用率(包括了低利用和高利用的场景)、删除重启次数过多的pod等启用:

```yaml
apiVersion: "descheduler/v1alpha1"
kind: "DeschedulerPolicy"
strategies:
  "RemoveDuplicates":
     enabled: true
  "RemovePodsViolatingInterPodAntiAffinity":
     enabled: true
  "LowNodeUtilization":
     enabled: true
     params:
       nodeResourceUtilizationThresholds:
         thresholds:
           "cpu" : 20
           "memory": 20
           "pods": 20
         targetThresholds:
           "cpu" : 50
           "memory": 50
           "pods": 50
  "RemovePodsHavingTooManyRestarts":
     enabled: true
     params:
       podsHavingTooManyRestarts:
         podRestartThresholds: 100
         includingInitContainers: true
```

**集群关闭**

[集群关闭](https://github.com/kubecost/cluster-turndown)是根据自定义计划和关闭条件自动缩小和扩大Kubernetes集群后端节点的功能。此功能可用于在闲置时间减少支出和/或出于安全原因减少攻击面。最常见的用例是在非工作时间将非生产环境(例如开发集群)缩减为零。集群关闭目前处于ALPHA版本。

集群关闭使用Kubernetes自定义资源定义来创建计划。以下计划将创建一个计划，该计划将在指定的开始日期时间开始关闭，并在指定的结束日期时间重新启动(时间应采用RFC3339格式，即基于UTC的时间偏移量)。

```yaml
apiVersion: kubecost.k8s.io/v1alpha1
kind: TurndownSchedule
metadata:
  name: example-schedule
  finalizers:
  - "finalizer.kubecost.k8s.io"
spec:
  start: 2020-03-12T00:00:00Z
  end: 2020-03-12T12:00:00Z
  repeat: daily
```

### 使用LimitRanges和ResourceQuotas来帮助管理成本，限制在Namespace级别分配的资源量

默认情况下，容器在Kubernetes集群上运行时具有无限制的计算资源。通过资源配额，集群管理员可以限制基于命名空间的资源消耗和创建。在一个命名空间中，Pod或容器可以消耗由该命名空间的资源配额定义的CPU和内存。存在一种担忧，即一个Pod或容器可能会垄断所有可用资源。

Kubernetes使用资源配额和限制范围来控制CPU、内存、PersistentVolumeClaims等资源的分配。ResourceQuota在命名空间级别，而LimitRange在容器级别应用。

***限制范围***

LimitRange是一种限制命名空间中资源分配(给Pod或容器)的策略。

以下是使用限制范围设置默认内存请求和默认内存限制的示例。

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: mem-limit-range
spec:
  limits:
  - default:
      memory: 512Mi
    defaultRequest:
      memory: 256Mi
    type: Container
```

更多示例可在[Kubernetes文档](https://kubernetes.io/docs/tasks/administer-cluster/manage-resources/memory-default-namespace/)中找到。

***资源配额***

当多个用户或团队共享一个具有固定节点数量的集群时，存在一个团队可能会使用超过其应得份额的资源的担忧。资源配额是管理员解决此问题的工具。

以下是一个示例，说明如何通过在ResourceQuota对象中指定配额，为命名空间中运行的所有容器设置可使用的总内存和CPU量。这指定容器必须有内存请求、内存限制、CPU请求和CPU限制，并且不应超过ResourceQuota中设置的阈值。

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: mem-cpu-demo
spec:
  hard:
    requests.cpu: "1"
    requests.memory: 1Gi
    limits.cpu: "2"
    limits.memory: 2Gi
```

更多示例可在 [Kubernetes 文档](https://kubernetes.io/docs/tasks/administer-cluster/manage-resources/quota-memory-cpu-namespace/)中找到。

### 使用定价模型实现有效利用

Amazon EKS 的定价详情在 [定价页面](https://aws.amazon.com/eks/pricing/) 中给出。Amazon EKS on Fargate 和 EC2 共用一个控制平面成本。

如果您使用 AWS Fargate，定价是根据从开始下载容器镜像到 Amazon EKS pod 终止期间使用的 vCPU 和内存资源计算的，向上取整到最接近的秒数。最低收费为 1 分钟。详细定价信息请参阅 [AWS Fargate 定价页面](https://aws.amazon.com/fargate/pricing/)。

***Amazon EKS on EC2:***

Amazon EC2 提供了广泛的 [实例类型](https://aws.amazon.com/ec2/instance-types/) 选择，针对不同的使用场景进行了优化。实例类型包含不同组合的 CPU、内存、存储和网络能力，让您可以灵活选择适合您应用程序的合适资源组合。每种实例类型包含一个或多个实例大小，允许您根据目标工作负载的要求来扩展资源。

除了 CPU 数量、内存、处理器系列类型之外，与实例类型相关的一个关键决策参数是 [弹性网络接口(ENI)的数量](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-eni.html),这反过来会影响您可以在该 EC2 实例上运行的最大 pod 数量。[每种 EC2 实例类型的最大 pod 数量](https://github.com/awslabs/amazon-eks-ami/blob/master/files/eni-max-pods.txt) 列表维护在 github 上。

****按需 EC2 实例:****

使用 [按需实例](https://aws.amazon.com/ec2/pricing/),您可以按小时或秒(取决于您运行的实例)为计算能力付费。无需长期承诺或预付费用。

Amazon EC2 A1 实例可以带来显著的成本节省，非常适合支持广泛 Arm 生态系统的横向扩展和基于 ARM 的工作负载。您现在可以使用 Amazon Elastic Container Service for Kubernetes (EKS) 在 Amazon EC2 A1 实例上运行容器，作为[公开开发者预览版](https://github.com/aws/containers-roadmap/tree/master/preview-programs/eks-arm-preview)的一部分。Amazon ECR 现在支持[多架构容器镜像](https://aws.amazon.com/blogs/containers/introducing-multi-architecture-container-images-for-amazon-ecr/)，这使得从同一镜像仓库部署不同架构和操作系统的容器镜像变得更加简单。

您可以使用 [AWS 简单月度计算器](https://calculator.s3.amazonaws.com/index.html) 或新的[定价计算器](https://calculator.aws/)获取 EKS 工作节点的按需 EC2 实例定价。

### 使用 Spot EC2 实例:

Amazon [EC2 Spot 实例](https://aws.amazon.com/ec2/pricing/)允许您以高达按需价格的 90% 折扣请求闲置的 Amazon EC2 计算能力。

Spot 实例通常非常适合无状态的容器化工作负载，因为容器和 Spot 实例的方法类似;临时和自动扩展的容量。这意味着它们都可以在遵守 SLA 且不影响应用程序的性能或可用性的情况下添加和删除。

您可以创建多个节点组，混合使用按需实例类型和 EC2 Spot 实例，以利用这两种实例类型之间的定价优势。

![按需和 Spot 节点组](../images/spot_diagram.png)
***(图片来源: https://ec2spotworkshops.com/using_ec2_spot_instances_with_eks/spotworkers/workers_eksctl.html)***

下面是使用eksctl创建使用EC2 Spot实例的节点组的示例yaml文件。在创建节点组时，我们配置了一个节点标签，以便kubernetes知道我们配置了什么类型的节点。我们将节点的生命周期设置为Ec2Spot。我们还使用PreferNoSchedule来污染，以便优先不将pod调度到Spot实例上。这是NoSchedule的"偏好"或"软"版本，即系统将尝试避免将不容忍污点的pod放置在该节点上，但这不是必需的。我们使用这种技术是为了确保只有正确类型的工作负载才会被调度到Spot实例上。

```yaml
apiVersion: eksctl.io/v1alpha5
kind: ClusterConfig
metadata:
  name: my-cluster-testscaling
  region: us-west-2
nodeGroups:
  - name: ng-spot
    labels:
      lifecycle: Ec2Spot
    taints:
      spotInstance: true:PreferNoSchedule
    minSize: 2
    maxSize: 5
    instancesDistribution: # 应该至少指定两种实例类型
      instanceTypes:
        - m4.large
        - c4.large
        - c5.large
      onDemandBaseCapacity: 0
      onDemandPercentageAboveBaseCapacity: 0 # 所有实例都将是Spot实例
      spotInstancePools: 2
```
使用节点标签来识别节点的生命周期。
```
$ kubectl get nodes --label-columns=lifecycle --selector=lifecycle=Ec2Spot
```

我们还应该在每个Spot实例上部署[AWS Node Termination Handler](https://github.com/aws/aws-node-termination-handler)。它将监控实例上的EC2元数据服务以获取中断通知。终止处理程序由ServiceAccount、ClusterRole、ClusterRoleBinding和DaemonSet组成。AWS Node Termination Handler不仅适用于Spot实例，它还可以捕获一般的EC2维护事件，因此可以在整个集群的工作节点上使用。

如果客户使用了多样化的资源并采用了优化容量的分配策略，Spot实例将可用。您可以在清单文件中使用节点亲和性来配置此项，以优先使用Spot实例，但不要求使用。这将允许在没有可用或正确标记的Spot实例时，将Pod调度到按需节点上。

``` yaml

affinity:
nodeAffinity:
  preferredDuringSchedulingIgnoredDuringExecution:
  - weight: 1
    preference:
      matchExpressions:
      - key: lifecycle
        operator: In
        values:
        - Ec2Spot
tolerations:
- key: "spotInstance"
operator: "Equal"
value: "true"
effect: "PreferNoSchedule"

```

您可以在[在线EC2 Spot Workshop](https://ec2spotworkshops.com/using_ec2_spot_instances_with_eks.html)上完成关于EC2 Spot实例的完整研讨会。

### 使用计算节省计划

计算节省计划是一种灵活的折扣模式，它以承诺在一年或三年内使用特定金额(以每小时美元计)的计算能力为代价，为您提供与预留实例相同的折扣。详细信息在[节省计划发布常见问题解答](https://aws.amazon.com/savingsplans/faq/)中有介绍。这些计划会自动应用于任何EC2工作节点，无论区域、实例系列、操作系统或租赁方式如何，包括作为EKS集群一部分的节点。例如，您可以从C4切换到C5实例，将工作负载从都柏林迁移到伦敦，在此过程中仍可享受节省计划价格，而无需做任何操作。

AWS成本资源管理器将帮助您选择节省计划，并指导您完成购买流程。
![计算节省计划](../images/Compute-savings-plan.png)

注意 - 计算节省计划现在也适用于[AWS Fargate for AWS Elastic Kubernetes Service (EKS)](https://aws.amazon.com/about-aws/whats-new/2020/08/amazon-fargate-aws-eks-included-compute-savings-plan/)。

注意 - 上述定价不包括数据传输费用、CloudWatch、Elastic Load Balancer 和 Kubernetes 应用程序可能使用的其他 AWS 服务费用。

## 资源
参考以下资源以了解有关成本优化最佳实践的更多信息。

### 视频
+	[AWS re:Invent 2019: 在 Spot 实例上运行生产工作负载，节省高达 90% 的成本 (CMP331-R1)](https://www.youtube.com/watch?v=7q5AeoKsGJw)

### 文档和博客
+	[AWS 上 Kubernetes 的成本优化](https://aws.amazon.com/blogs/containers/cost-optimization-for-kubernetes-on-aws/)
+	[使用 Spot 实例为 EKS 构建成本优化和弹性解决方案](https://aws.amazon.com/blogs/compute/cost-optimization-and-resilience-eks-with-spot-instances/)
+ [使用自定义指标自动扩缩 EKS on Fargate](https://aws.amazon.com/blogs/containers/autoscaling-eks-on-fargate-with-custom-metrics/)
+ [AWS Fargate 注意事项](https://docs.aws.amazon.com/eks/latest/userguide/fargate.html)
+	[在 EKS 中使用 Spot 实例](https://ec2spotworkshops.com/using_ec2_spot_instances_with_eks.html)
+   [扩展 EKS API: 托管节点组](https://aws.amazon.com/blogs/containers/eks-managed-node-groups/)
+	[Amazon EKS 自动扩缩](https://docs.aws.amazon.com/eks/latest/userguide/autoscaling.html) 
+	[Amazon EKS 定价](https://aws.amazon.com/eks/pricing/)
+	[AWS Fargate 定价](https://aws.amazon.com/fargate/pricing/)
+   [节省计划](https://docs.aws.amazon.com/savingsplans/latest/userguide/what-is-savings-plans.html)
+   [在 AWS 上使用 Kubernetes 节省云成本](https://srcco.de/posts/saving-cloud-costs-kubernetes-aws.html) 

### 工具
+  [Kube downscaler](https://github.com/hjacobs/kube-downscaler)
+  [Kubernetes Descheduler](https://github.com/kubernetes-sigs/descheduler)
+  [Cluster TurnDown](https://github.com/kubecost/cluster-turndown)