---
date: 2023-09-22
authors: 
  - Lukonde Mwila
---
# 成本优化 - 网络

为实现弹性和容错能力，架构高可用性 (HA) 系统是最佳实践。在实践中，这意味着要在给定的 AWS 区域中跨多个可用区 (AZ) 分布您的工作负载和底层基础设施。确保这些特性在您的 Amazon EKS 环境中得到实现，将提高整个系统的可靠性。与此同时，您的 EKS 环境可能还包含各种构造 (如 VPC)、组件 (如 ELB) 和集成 (如 ECR 和其他容器注册表)。

高可用系统和其他特定于用例的组件的组合，可能会在数据传输和处理方面发挥重要作用。这反过来又会影响由于数据传输和处理而产生的成本。

下面详述的做法将帮助您设计和优化 EKS 环境，以实现不同领域和用例的成本效益。


## Pod 到 Pod 通信

根据您的设置，Pod 之间的网络通信和数据传输可能会对运行 Amazon EKS 工作负载的总体成本产生重大影响。本节将介绍不同的概念和方法，以减少与 Pod 间通信相关的成本，同时考虑高可用 (HA) 架构、应用程序性能和弹性。

### 限制流量在可用区内

频繁的跨区流量 (在可用区之间分布的流量) 可能会对您的网络相关成本产生重大影响。以下是一些控制 EKS 集群中 Pod 之间跨区流量量的策略。

_如果您想对集群中 Pod 之间的跨区域流量量有更细粒度的了解(例如以字节为单位的数据传输量)，[请参阅此文章](https://aws.amazon.com/blogs/containers/getting-visibility-into-your-amazon-eks-cross-az-pod-to-pod-network-bytes/)。_

**使用拓扑感知路由(以前称为拓扑感知提示)**

![拓扑感知路由](../images/topo_aware_routing.png)

在使用拓扑感知路由时，了解 Service、EndpointSlice 和 `kube-proxy` 在路由流量时是如何协同工作很重要。如上图所示，Service 是接收发往您的 Pod 的流量的稳定网络抽象层。创建 Service 时，会创建多个 EndpointSlice。每个 EndpointSlice 都包含一个端点列表，其中包含一部分 Pod 地址以及它们所在的节点和任何其他拓扑信息。`kube-proxy` 是在集群中每个节点上运行的 daemonset，也承担内部路由的角色，但它是根据从创建的 EndpointSlice 中获取的信息进行路由的。

当在 Kubernetes Service 上启用并实现[*拓扑感知路由*](https://kubernetes.io/docs/concepts/services-networking/topology-aware-routing/)时，EndpointSlice 控制器会按比例将端点分配到集群所跨越的不同区域。对于这些端点中的每一个，EndpointSlice 控制器还会为该区域设置一个 _hint_。_Hint_ 描述了一个端点应该为哪个区域提供流量服务。然后 `kube-proxy` 将根据应用的 _hint_ 将来自一个区域的流量路由到一个端点。

下图显示了如何以这样的方式组织带有 hint 的 EndpointSlice，以便 `kube-proxy` 可以根据流量的区域起点知道它们应该去往哪个目的地。如果没有 hint，就不会有这样的分配或组织，而是无论流量来自哪里，都会被代理到不同的区域目的地。

![Endpoint Slice](../images/endpoint_slice.png)

在某些情况下，EndpointSlice控制器可能会应用不同区域的_提示_，这意味着端点可能最终会为来自不同区域的流量提供服务。这样做的原因是为了尝试在不同区域的端点之间保持均匀的流量分布。

以下是如何为服务启用_拓扑感知路由_的代码片段。

```yaml hl_lines="6-7"
apiVersion: v1
kind: Service
metadata:
  name: orders-service
  namespace: ecommerce
    annotations:
      service.kubernetes.io/topology-mode: Auto
spec:
  selector:
    app: orders
  type: ClusterIP
  ports:
  - protocol: TCP
    port: 3003
    targetPort: 3003
```

下面的屏幕截图显示了EndpointSlice控制器成功地为在AZ `eu-west-1a` 中运行的Pod副本应用了一个提示。

![Slice shell](../images/slice_shell.png)

!!! note
    需要注意的是，拓扑感知路由仍处于**测试阶段**。此外，当工作负载广泛且均匀地分布在集群拓扑结构中时，此功能更可预测。因此，强烈建议将其与提高应用程序可用性的调度约束(如[pod拓扑分布约束](https://kubernetes.io/docs/concepts/scheduling-eviction/topology-spread-constraints/))一起使用。

**使用自动扩缩器: 将节点供应到特定的AZ**

_我们强烈建议_在多个AZ中运行您的工作负载，以提高高可用性。这可以提高应用程序的可靠性，特别是在某个AZ出现问题的情况下。如果您愿意牺牲可靠性来降低与网络相关的成本，您可以将节点限制在单个AZ中。

要在同一个可用区(AZ)中运行所有的 Pod，可以在同一个 AZ 中配置工作节点，或者将 Pod 调度到运行在同一个 AZ 中的工作节点上。要在单个 AZ 中配置节点，请使用[集群自动扩缩(CA)](https://github.com/kubernetes/autoscaler/tree/master/cluster-autoscaler)定义一个属于同一 AZ 的子网的节点组。对于 [Karpenter](https://karpenter.sh/),请使用"[_topology.kubernetes.io/zone"_](http://topology.kubernetes.io/zone%E2%80%9D)并指定您希望创建工作节点的 AZ。例如，下面的 Karpenter 配置片段在 us-west-2a AZ 中配置节点。

**Karpenter**

```yaml hl_lines="5-9"
apiVersion: karpenter.sh/v1alpha5
kind: Provisioner
metadata:
name: single-az
spec:
  requirements:
  - key: "topology.kubernetes.io/zone"
    operator: In
    values: ["us-west-2a"]
```

**集群自动扩缩(CA)**

```yaml hl_lines="7-8"
apiVersion: eksctl.io/v1alpha5
kind: ClusterConfig
metadata:
  name: my-ca-cluster
  region: us-east-1
  version: "1.21"
availabilityZones:
- us-east-1a
managedNodeGroups:
- name: managed-nodes
  labels:
    role: managed-nodes
  instanceType: t3.medium
  minSize: 1
  maxSize: 10
  desiredCapacity: 1
...
```

**使用 Pod 分配和节点亲和性**

或者，如果您有运行在多个 AZ 中的工作节点，每个节点都会有标签 _[topology.kubernetes.io/zone](http://topology.kubernetes.io/zone%E2%80%9D)_,其值为节点所在的 AZ(如 us-west-2a 或 us-west-2b)。您可以使用 `nodeSelector` 或 `nodeAffinity` 将 Pod 调度到单个 AZ 中的节点。例如，以下清单文件将在 us-west-2a AZ 中运行的节点内调度 Pod。

```yaml hl_lines="7-9"
apiVersion: v1
kind: Pod
metadata:
  name: nginx
  labels:
    env: test
spec:
  nodeSelector:
    topology.kubernetes.io/zone: us-west-2a
  containers:
  - name: nginx
    image: nginx 
    imagePullPolicy: IfNotPresent
```

### 限制流量到节点

有些情况下，仅在区域级别限制流量是不够的。除了降低成本外，您可能还需要降低某些频繁相互通信的应用程序之间的网络延迟。为了实现最佳网络性能和降低成本，您需要一种方式将流量限制在特定节点上。例如，即使在高可用(HA)设置中，微服务A也应该始终与节点1上的微服务B通信。如果节点2位于完全不同的可用区，那么节点1上的微服务A与节点2上的微服务B通信可能会对这种性质的应用程序的期望性能产生负面影响。

**使用服务内部流量策略**

为了将Pod网络流量限制在一个节点上，您可以使用_[服务内部流量策略](https://kubernetes.io/docs/concepts/services-networking/service-traffic-policy/)_。默认情况下，发送到工作负载服务的流量将在不同生成的端点之间随机分布。因此，在HA架构中，这意味着来自微服务A的流量可能会进入任何给定节点上微服务B的任何副本，跨不同的可用区。但是，如果将服务的内部流量策略设置为`Local`,流量将被限制在流量发出的节点上的端点。此策略规定了专门使用节点本地端点。这意味着，与在整个集群范围内分布相比，该工作负载的网络流量相关成本将更低。此外，延迟也会更低，从而提高应用程序的性能。

!!! note
    重要的是要注意，此功能不能与Kubernetes中的拓扑感知路由相结合。

![本地内部流量](../images/local_traffic.png)

下面是设置服务_内部流量策略_的代码片段。

```yaml hl_lines="14"
apiVersion: v1
kind: Service
metadata:
  name: orders-service
  namespace: ecommerce
spec:
  selector:
    app: orders
  type: ClusterIP
  ports:
  - protocol: TCP
    port: 3003
    targetPort: 3003
  internalTrafficPolicy: Local
```

为避免应用程序由于流量丢失而出现意外行为，您应该考虑以下方法:

* 为每个通信的Pod运行足够的副本
* 使用[拓扑分布约束](https://kubernetes.io/docs/concepts/scheduling-eviction/topology-spread-constraints/)使Pod相对均匀分布
* 利用[pod亲和性规则](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/#inter-pod-affinity-and-anti-affinity)实现通信Pod的共置

在此示例中，您有2个微服务A的副本和3个微服务B的副本。如果微服务A的副本分布在节点1和2上，而微服务B的所有3个副本都在节点3上，那么由于`Local`内部流量策略，它们将无法通信。当没有可用的节点本地端点时，流量将被丢弃。

![node-local_no_peer](../images/no_node_local_1.png)

如果微服务B在节点1和2上有2个副本，那么对等应用程序之间将会有通信。但您仍将有一个孤立的微服务B副本，没有任何对等副本可以与之通信。

![node-local_with_peer](../images/no_node_local_2.png)

!!! note
    在某些情况下，如上图所示的孤立副本如果仍然发挥作用(例如为外部传入流量提供服务),则可能不会引起关注。

**使用服务内部流量策略和拓扑分布约束**

结合使用_内部流量策略_和_拓扑分布约束_可以确保在不同节点上为通信的微服务部署正确数量的副本。

```yaml hl_lines="16-22"
apiVersion: apps/v1
kind: Deployment
metadata:
  name: express-test
spec:
  replicas: 6
  selector:
    matchLabels:
      app: express-test
  template:
    metadata:
      labels:
        app: express-test
        tier: backend
    spec:
      topologySpreadConstraints:
      - maxSkew: 1
        topologyKey: "topology.kubernetes.io/zone"
        whenUnsatisfiable: ScheduleAnyway
        labelSelector:
          matchLabels:
            app: express-test
```

**使用服务内部流量策略与Pod亲和性规则**

另一种方法是在使用服务内部流量策略时利用Pod亲和性规则。通过Pod亲和性，您可以影响调度程序将某些Pod协同放置，因为它们之间存在频繁的通信。通过对某些Pod应用严格的调度约束(`requiredDuringSchedulingIgnoredDuringExecution`)，当调度程序在节点上放置Pod时，这将为Pod协同放置提供更好的结果。

```yaml hl_lines="11-20"
apiVersion: apps/v1
kind: Deployment
metadata:
  name: graphql
  namespace: ecommerce
  labels:
    app.kubernetes.io/version: "0.1.6"
    ...
    spec:
      serviceAccountName: graphql-service-account
      affinity:
        podAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchExpressions:
              - key: app
                operator: In
                values:
                - orders
            topologyKey: "kubernetes.io/hostname"
```

## 负载均衡器与Pod之间的通信

EKS工作负载通常由负载均衡器前置，负载均衡器将流量分发到EKS集群中的相关Pod。您的架构可能包括内部和/或外部负载均衡器。根据您的架构和网络流量配置，负载均衡器与Pod之间的通信可能会占据大量的数据传输费用。

您可以使用 [AWS Load Balancer Controller](https://kubernetes-sigs.github.io/aws-load-balancer-controller) 自动管理 ELB 资源（ALB 和 NLB）的创建。在这种设置中产生的数据传输费用将取决于网络流量的路径。AWS Load Balancer Controller 支持两种网络流量模式：_instance mode_ 和 _ip mode_。

使用 _instance mode_ 时，将在您的 EKS 集群中的每个节点上打开一个 NodePort。负载均衡器将在节点之间均匀代理流量。如果目标 Pod 运行在同一节点上，则不会产生数据传输费用。但是，如果目标 Pod 位于不同的节点并且与接收流量的 NodePort 所在的可用区域不同，那么从 kube-proxy 到目标 Pod 将会有额外的网络跳转。在这种情况下，将产生跨可用区数据传输费用。由于流量在节点之间均匀分布，因此很可能会产生与从 kube-proxy 到相关目标 Pod 的跨区网络流量跳转相关的额外数据传输费用。

下图描绘了从负载均衡器到 NodePort 的网络路径，以及随后从 `kube-proxy` 到位于不同可用区域的另一个节点上的目标 Pod 的网络路径。这是 _instance mode_ 设置的一个示例。

![LB to Pod](../images/lb_2_pod.png)

使用 _ip mode_ 时，网络流量将直接从负载均衡器代理到目标 Pod。因此，这种方法不会产生任何数据传输费用。

!!! tip
    建议将您的负载均衡器设置为 _ip 流量模式_，以减少数据传输费用。对于这种设置，还需要确保您的负载均衡器部署在 VPC 中的所有子网上。

下图描绘了在网络 _ip mode_ 下从负载均衡器到 Pod 的网络流量路径。

![IP mode](../images/ip_mode.png)

## 从容器注册表传输数据

### Amazon ECR

将数据传输到 Amazon ECR 私有注册表是免费的。_区域内数据传输不收费_，但将数据传输到互联网和跨区域将在传输的两端按照互联网数据传输费率收费。

您应该利用 ECR 内置的[镜像复制功能](https://docs.aws.amazon.com/AmazonECR/latest/userguide/replication.html)将相关容器镜像复制到与您的工作负载相同的区域。这样，复制将被收取一次费用，而所有相同区域(区域内)的镜像拉取都将免费。

您可以进一步减少从 ECR 拉取镜像(数据传出)相关的数据传输成本，方法是_使用[接口 VPC 终端节点](https://docs.aws.amazon.com/whitepapers/latest/aws-privatelink/what-are-vpc-endpoints.html)连接到区域内的 ECR 存储库_。连接到 ECR 的公共 AWS 端点(通过 NAT 网关和互联网网关)的替代方法将产生更高的数据处理和传输成本。下一节将更详细地介绍如何减少工作负载与 AWS 服务之间的数据传输成本。

如果您运行的工作负载使用特别大的镜像，您可以构建自己的自定义 Amazon Machine Images (AMIs),其中预先缓存了容器镜像。这可以减少从容器注册表到 EKS 工作节点的初始镜像拉取时间和潜在数据传输成本。


## 传输数据到互联网和 AWS 服务

将 Kubernetes 工作负载与其他 AWS 服务或第三方工具和平台通过互联网集成是一种常见做法。用于路由传输到相关目的地的底层网络基础设施可能会影响数据传输过程中产生的成本。

### 使用 NAT 网关

NAT 网关是执行网络地址转换 (NAT) 的网络组件。下图描绘了 EKS 集群中的 Pod 与其他 AWS 服务 (Amazon ECR、DynamoDB 和 S3) 以及第三方平台进行通信的情况。在此示例中，Pod 运行在不同可用区的私有子网中。为了发送和接收来自互联网的流量，在一个可用区的公共子网中部署了一个 NAT 网关，允许任何具有私有 IP 地址的资源共享一个公共 IP 地址来访问互联网。这个 NAT 网关反过来与互联网网关组件通信，允许数据包被发送到最终目的地。

![NAT 网关](../images/nat_gw.png)

在使用 NAT 网关进行此类用例时，_您可以通过在每个可用区部署一个 NAT 网关来最小化数据传输成本_。这样，路由到互联网的流量将通过同一可用区的 NAT 网关，避免了跨可用区的数据传输。但是，即使您可以节省跨可用区数据传输的成本，这种设置的含义是您的架构中将产生额外的 NAT 网关成本。

下图描绘了这种推荐的方法。

![推荐方法](../images/recommended_approach.png)

### 使用 VPC 终端节点

为了进一步降低此类架构的成本，_您应该使用 [VPC 终端节点](https://docs.aws.amazon.com/whitepapers/latest/aws-privatelink/what-are-vpc-endpoints.html) 在您的工作负载和 AWS 服务之间建立连接_。VPC 终端节点允许您从 VPC 内部访问 AWS 服务，而无需数据/网络数据包穿越互联网。所有流量都是内部的，并且保持在 AWS 网络内。有两种类型的 VPC 终端节点:接口 VPC 终端节点([许多 AWS 服务支持](https://docs.aws.amazon.com/vpc/latest/privatelink/aws-services-privatelink-support.html))和网关 VPC 终端节点(仅 S3 和 DynamoDB 支持)。

**网关 VPC 终端节点**

_使用网关 VPC 终端节点不会产生每小时或数据传输费用_。使用网关 VPC 终端节点时，需要注意它们无法跨 VPC 边界扩展。它们不能用于 VPC 对等、VPN 网络或通过 Direct Connect。

**接口 VPC 终端节点**

VPC 终端节点有[每小时费用](https://aws.amazon.com/privatelink/pricing/)，并且根据 AWS 服务的不同，可能会或可能不会有与通过底层 ENI 进行数据处理相关的额外费用。为了减少与接口 VPC 终端节点相关的跨 AZ 数据传输成本，您可以在每个 AZ 中创建一个 VPC 终端节点。即使它们指向同一 AWS 服务，您也可以在同一 VPC 中创建多个 VPC 终端节点。

下图显示了 Pod 通过 VPC 终端节点与 AWS 服务进行通信。

![VPC 终端节点](../images/vpc_endpoints.png)

## 跨 VPC 的数据传输

在某些情况下，您可能在不同的 VPC 中(位于同一 AWS 区域内)有需要相互通信的工作负载。这可以通过允许流量通过连接到各自 VPC 的 Internet 网关在公共互联网上传输来实现。可以通过在公共子网中部署基础设施组件(如 EC2 实例、NAT 网关或 NAT 实例)来启用此类通信。但是，包括这些组件的设置将产生处理/传输进出 VPC 的数据的费用。如果从单独的 VPC 传入和传出的流量跨越多个可用区，则还会产生额外的数据传输费用。下图描绘了一个使用 NAT 网关和 Internet 网关在不同 VPC 中的工作负载之间建立通信的设置。

![跨 VPC](../images/between_vpcs.png)

### VPC 对等连接

为了降低此类用例的成本，您可以利用[VPC 对等连接](https://docs.aws.amazon.com/vpc/latest/peering/what-is-vpc-peering.html)。使用 VPC 对等连接时，同一可用区域内的网络流量不会产生数据传输费用。如果流量跨越多个可用区域，则会产生费用。尽管如此，对于同一 AWS 区域内不同 VPC 中的工作负载之间的高效通信，仍建议采用 VPC 对等连接方式。但重要的是要注意，VPC 对等连接主要适用于 1:1 VPC 连接，因为它不允许传递网络连接。

下图是通过 VPC 对等连接进行工作负载通信的高级表示。

![Peering](../images/peering.png)

### 传递网络连接

如前一节所述，VPC 对等连接不允许传递网络连接。如果您需要连接 3 个或更多具有传递网络要求的 VPC，那么您应该使用[Transit Gateway](https://docs.aws.amazon.com/vpc/latest/tgw/what-is-transit-gateway.html) (TGW)。这将使您能够克服 VPC 对等连接的限制或在多个 VPC 之间建立多个 VPC 对等连接所带来的任何操作开销。您需要[按小时付费](https://aws.amazon.com/transit-gateway/pricing/),并为发送到 TGW 的数据付费。_通过 TGW 流动的同一 AWS 区域内不同可用区之间的流量不会产生目的地费用。_

下图显示了通过 TGW 在同一 AWS 区域内不同 VPC 中的工作负载之间流动的跨可用区流量。

![Transitive](../images/transititive.png)

## 使用服务网格

服务网格提供了强大的网络功能，可用于降低 EKS 集群环境中的网络相关成本。但是，如果您采用服务网格，您应该仔细考虑它将为您的环境引入的操作任务和复杂性。

### 限制流量到可用区域

**使用 Istio 的区域加权分布**

Istio 允许您在路由发生后对流量应用网络策略。这是使用[目标规则](https://istio.io/latest/docs/reference/config/networking/destination-rule/)如[区域加权分布](https://istio.io/latest/docs/tasks/traffic-management/locality-load-balancing/distribute/)完成的。使用此功能，您可以根据流量的来源控制可以进入某个目的地的流量权重(以百分比表示)。该流量的来源可以是外部(或公共)负载均衡器或集群内的 Pod。当所有 Pod 端点都可用时，将根据加权循环负载均衡算法选择区域。如果某些端点不健康或不可用，[区域权重将自动调整](https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/upstream/load_balancing/locality_weight.html)以反映可用端点的这种变化。

!!! note
    在实施区域加权分布之前，您应该首先了解您的网络流量模式以及目标规则策略可能对您的应用程序行为产生的影响。因此，拥有分布式跟踪机制并使用诸如 [AWS X-Ray](https://aws.amazon.com/xray/) 或 [Jaeger](https://www.jaegertracing.io/) 等工具非常重要。

上述详细介绍的 Istio 目标规则也可应用于管理从负载均衡器到 EKS 集群中的 Pod 的流量。可以将基于区域的加权分布规则应用于从高可用负载均衡器（特别是 Ingress Gateway）接收流量的服务。这些规则允许您根据流量的区域来源（在本例中为负载均衡器）控制流量的分布。如果配置正确，与将流量均匀或随机分布到不同可用区中的 Pod 副本的负载均衡器相比，将产生较少的跨区域出口流量。

下面是 Istio 中目标规则资源的代码块示例。如下所示，此资源为来自 `eu-west-1` 区域中 3 个不同可用区的传入流量指定了加权配置。这些配置声明，来自给定可用区的大部分传入流量（在本例中为 70%）应该被代理到与其源可用区相同的目标可用区。

```yaml hl_lines="7-11"
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: express-test-dr
spec:
  host: express-test.default.svc.cluster.local
  trafficPolicy:
    loadBalancer:                        
      localityLbSetting:
        distribute:
        - from: eu-west-1/eu-west-1a/    
          to:
            "eu-west-1/eu-west-1a/*": 70 
            "eu-west-1/eu-west-1b/*": 20
            "eu-west-1/eu-west-1c/*": 10
        - from: eu-west-1/eu-west-1b/*    
          to:
            "eu-west-1/eu-west-1a/*": 20 
            "eu-west-1/eu-west-1b/*": 70
            "eu-west-1/eu-west-1c/*": 10
        - from: eu-west-1/eu-west-1c/*    
          to:
            "eu-west-1/eu-west-1a/*": 20 
            "eu-west-1/eu-west-1b/*": 10
            "eu-west-1/eu-west-1c/*": 70**
    connectionPool:
      http:
        http2MaxRequests: 10
        maxRequestsPerConnection: 10
    outlierDetection:
      consecutiveGatewayErrors: 1
      interval: 1m
      baseEjectionTime: 30s
```

!!! note
    可以分配到目标地址的最小权重为1%。这样做的原因是为了在主目标地址的端点出现故障或不可用时保持故障转移区域和区域。

下图描绘了一种情况，在该情况下，_eu-west-1_区域中有一个高可用负载均衡器，并应用了基于位置的加权分布。此图的目标规则策略配置为将来自_eu-west-1a_的60%流量发送到同一可用区域中的Pod，而来自_eu-west-1a_的40%流量应发送到eu-west-1b中的Pod。

![Istio Traffic Control](../images/istio-traffic-control.png)

### 限制对可用区域和节点的流量

**使用Istio的服务内部流量策略**

为了减轻与_外部_传入流量和Pod之间_内部_流量相关的网络成本，您可以将Istio的目标规则与Kubernetes服务_内部流量策略_结合使用。将Istio目标规则与服务内部流量策略相结合的方式在很大程度上取决于以下3个因素:

* 微服务的角色
* 微服务之间的网络流量模式
* 微服务应该如何部署在Kubernetes集群拓扑中

下图显示了在嵌套请求的情况下网络流量的流向，以及上述策略如何控制流量。

![External and Internal traffic policy](../images/external-and-internal-traffic-policy.png)

1. 最终用户向 **APP A** 发出请求，后者又向 **APP C** 发出嵌套请求。该请求首先被发送到一个高可用负载均衡器，如上图所示，该负载均衡器在 AZ 1 和 AZ 2 中都有实例。
2. 外部传入请求随后由 Istio 虚拟服务路由到正确的目的地。
3. 请求被路由后，Istio 目标规则会根据请求来源（AZ 1 或 AZ 2）控制流量分配到各个 AZ 的比例。
4. 流量然后进入 **APP A** 的服务，并被代理到各个 Pod 端点。如图所示，80% 的传入流量被发送到 AZ 1 的 Pod 端点，20% 的传入流量被发送到 AZ 2。
5. **APP A** 随后向 **APP C** 发出内部请求。**APP C** 的服务启用了内部流量策略（`internalTrafficPolicy``: Local`）。
6. 从 **APP A**（在 *NODE 1* 上）到 **APP C** 的内部请求成功，因为 **APP C** 在该节点上有可用的本地端点。
7. 从 **APP A**（在 *NODE 3* 上）到 **APP C** 的内部请求失败，因为 **APP C** 在该节点上没有可用的本地端点。如图所示，APP C 在 NODE 3 上没有副本。****

下面的屏幕截图来自于这种方法的实时示例。第一组截图展示了对 `graphql` 的成功外部请求，以及从 `graphql` 到同一节点 `ip-10-0-0-151.af-south-1.compute.internal` 上的 `orders` 副本的成功嵌套请求。

![Before](../images/before.png)
![Before results](../images/before-results.png)

使用 Istio，您可以验证和导出代理所知的任何[上游集群](https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/intro/terminology)和端点的统计信息。这有助于提供网络流量的图像以及工作负载服务之间的分布份额。继续使用相同的示例，`graphql` 代理所知的 `orders` 端点可以使用以下命令获取:

```bash
kubectl exec -it deploy/graphql -n ecommerce -c istio-proxy -- curl localhost:15000/clusters | grep orders 
```

```bash
...
orders-service.ecommerce.svc.cluster.local::10.0.1.33:3003::**rq_error::0**
orders-service.ecommerce.svc.cluster.local::10.0.1.33:3003::**rq_success::119**
orders-service.ecommerce.svc.cluster.local::10.0.1.33:3003::**rq_timeout::0**
orders-service.ecommerce.svc.cluster.local::10.0.1.33:3003::**rq_total::119**
orders-service.ecommerce.svc.cluster.local::10.0.1.33:3003::**health_flags::healthy**
orders-service.ecommerce.svc.cluster.local::10.0.1.33:3003::**region::af-south-1**
orders-service.ecommerce.svc.cluster.local::10.0.1.33:3003::**zone::af-south-1b**
...
```

在这种情况下，`graphql` 代理只知道与它共享节点的副本的 `orders` 端点。如果从 orders 服务中删除 `internalTrafficPolicy: Local` 设置，并重新运行类似上面的命令，那么结果将返回分布在不同节点上的所有副本的端点。此外，通过检查各个端点的 `rq_total`，您会注意到网络分布中相对均匀的份额。因此，如果端点与在不同可用区域中运行的上游服务相关联，那么跨区域的这种网络分布将导致更高的成本。

如上一节所述，您可以通过利用 pod-affinity 来共置频繁通信的 Pod。

```yaml hl_lines="11-20"
...
spec:
...
  template:
    metadata:
      labels:
        app: graphql
        role: api
        workload: ecommerce
    spec:
      affinity:
        podAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchExpressions:
              - key: app
                operator: In
                values:
                - orders
            topologyKey: "kubernetes.io/hostname"
      nodeSelector:
        managedBy: karpenter
        billing-team: ecommerce
...
```

当 `graphql` 和 `orders` 副本不存在于同一节点 (`ip-10-0-0-151.af-south-1.compute.internal`) 时，如下 Postman 截图所示，第一个对 `graphql` 的请求成功，响应代码为 `200`，而 `graphql` 对 `orders` 的第二个嵌套请求则失败，响应代码为 `503`。

![After](../images/after.png)
![After results](../images/after-results.png)

## 其他资源

* [解决使用 Istio 在 EKS 上的延迟和数据传输成本](https://aws.amazon.com/blogs/containers/addressing-latency-and-data-transfer-costs-on-eks-using-istio/)
* [探索拓扑感知提示对 Amazon Elastic Kubernetes Service 中网络流量的影响](https://aws.amazon.com/blogs/containers/exploring-the-effect-of-topology-aware-hints-on-network-traffic-in-amazon-elastic-kubernetes-service/)
* [获取 Amazon EKS 跨可用区 Pod 到 Pod 网络字节的可见性](https://aws.amazon.com/blogs/containers/getting-visibility-into-your-amazon-eks-cross-az-pod-to-pod-network-bytes/)
* [Optimize AZ Traffic with Istio](https://youtu.be/EkpdKVm9kQY)
* [Optimize AZ Traffic with Topology Aware Routing](https://youtu.be/KFgE_lNVfz4)
* [Optimize Kubernetes Cost & Performance with Service Internal Traffic Policy](https://youtu.be/-uiF_zixEro)
* [Optimize Kubernetes Cost & Performance with Istio and Service Internal Traffic Policy](https://youtu.be/edSgEe7Rihc)
* [常见架构的数据传输成本概述](https://aws.amazon.com/blogs/architecture/overview-of-data-transfer-costs-for-common-architectures/)
* [了解 AWS 容器服务的数据传输成本](https://aws.amazon.com/blogs/containers/understanding-data-transfer-costs-for-aws-container-services/)