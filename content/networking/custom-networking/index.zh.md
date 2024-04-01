# 自定义网络

默认情况下，Amazon VPC CNI 将从主子网中选择一个 IP 地址分配给 Pod。主子网是主网络接口附加到的子网 CIDR，通常是节点/主机所在的子网。

如果子网 CIDR 太小，CNI 可能无法获取足够的辅助 IP 地址分配给 Pod。这是 EKS IPv4 集群的一个常见挑战。

自定义网络是解决此问题的一种解决方案。

自定义网络通过从辅助 VPC 地址空间(CIDR)分配节点和 Pod IP 来解决 IP 耗尽问题。自定义网络支持 ENIConfig 自定义资源。ENIConfig 包括一个备用子网 CIDR 范围(从辅助 VPC CIDR 中划分)，以及 Pod 将属于的安全组。启用自定义网络后，VPC CNI 会在 ENIConfig 中定义的子网中创建辅助网络接口。CNI 从 ENIConfig CRD 中定义的 CIDR 范围为 Pod 分配 IP 地址。

由于自定义网络不使用主网络接口，因此您可以在节点上运行的 Pod 数量较少。主机网络 Pod 继续使用分配给主网络接口的 IP 地址。此外，主网络接口用于处理源网络转换并路由节点外部的 Pod 流量。

## 示例配置

虽然自定义网络将接受辅助 CIDR 范围的有效 VPC 范围，但我们建议您使用来自 CG-NAT 空间的 CIDR (/16)，即 100.64.0.0/10 或 198.19.0.0/16，因为这些范围不太可能在企业环境中使用，而不是其他 RFC1918 范围。有关您可以与 VPC 一起使用的允许和受限 CIDR 块关联的更多信息，请参阅 VPC 文档中 VPC 和子网大小调整部分的 [IPv4 CIDR 块关联限制](https://docs.aws.amazon.com/vpc/latest/userguide/configure-your-vpc.html#add-cidr-block-restrictions)。

如下图所示，工作节点的主要弹性网络接口(Elastic Network Interface, [ENI](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-eni.html))仍使用主VPC CIDR范围(在本例中为10.0.0.0/16),但辅助ENI使用辅助VPC CIDR范围(在本例中为100.64.0.0/16)。现在，为了让Pod使用100.64.0.0/16 CIDR范围，您必须配置CNI插件使用自定义网络。您可以按照[此处](https://docs.aws.amazon.com/eks/latest/userguide/cni-custom-network.html)记录的步骤进行操作。

![illustration of pods on secondary subnet](./image.png)

如果您希望CNI使用自定义网络，请将`AWS_VPC_K8S_CNI_CUSTOM_NETWORK_CFG`环境变量设置为`true`。

```
kubectl set env daemonset aws-node -n kube-system AWS_VPC_K8S_CNI_CUSTOM_NETWORK_CFG=true
```


当`AWS_VPC_K8S_CNI_CUSTOM_NETWORK_CFG=true`时，CNI将从`ENIConfig`中定义的子网分配Pod IP地址。`ENIConfig`自定义资源用于定义将调度Pod的子网。

```
apiVersion : crd.k8s.amazonaws.com/v1alpha1
kind : ENIConfig
metadata:
  name: us-west-2a
spec: 
  securityGroups:
    - sg-0dff111a1d11c1c11
  subnet: subnet-011b111c1f11fdf11
```

创建`ENIconfig`自定义资源后，您需要创建新的工作节点并排空现有节点。现有工作节点和Pod将不受影响。


## 建议

### 何时使用自定义网络

如果您面临IPv4耗尽且暂时无法使用IPv6，我们建议您考虑使用自定义网络。Amazon EKS对[RFC6598](https://datatracker.ietf.org/doc/html/rfc6598)空间的支持使您能够扩展Pod以解决[RFC1918](https://datatracker.ietf.org/doc/html/rfc1918)地址耗尽的挑战。请考虑使用自定义网络的前缀委派来增加节点上的Pod密度。

如果您有在不同网络上以不同安全组要求运行 Pod 的安全需求，您可以考虑使用自定义网络。启用自定义网络后，Pod 将使用在 ENIConfig 中定义的与节点主网络接口不同的子网或安全组。

对于部署多个 EKS 集群和应用程序以连接内部数据中心服务，自定义网络确实是一个理想的选择。您可以增加 VPC 中 EKS 可访问的私有地址(RFC1918)数量，用于诸如 Amazon Elastic Load Balancing 和 NAT-GW 等服务，同时在多个集群中使用不可路由的 CG-NAT 空间作为 Pod。使用[Transit Gateway](https://aws.amazon.com/transit-gateway/)和共享服务 VPC(包括跨多个可用区的 NAT 网关以实现高可用性)的自定义网络可以实现可扩展和可预测的流量流。这篇[博客文章](https://aws.amazon.com/blogs/containers/eks-vpc-routable-ip-address-conservation/)描述了一种架构模式，这是使用自定义网络将 EKS Pod 连接到数据中心网络的最推荐方式之一。

### 避免使用自定义网络的情况

#### 准备实施 IPv6

自定义网络可以缓解 IP 耗尽问题，但需要额外的操作开销。如果您当前正在部署双栈(IPv4/IPv6) VPC 或者您的计划包括 IPv6 支持，我们建议实施 IPv6 集群。您可以设置 IPv6 EKS 集群并迁移您的应用程序。在 IPv6 EKS 集群中，Kubernetes 和 Pod 都会获得 IPv6 地址，并且可以与 IPv4 和 IPv6 端点进行通信。请查看[运行 IPv6 EKS 集群](../ipv6/index.md)的最佳实践。

#### 耗尽 CG-NAT 空间

此外，如果您当前正在使用CG-NAT空间的CIDR或无法将辅助CIDR与集群VPC关联，您可能需要探索其他选项，例如使用替代CNI。我们强烈建议您获得商业支持或拥有内部知识来调试和提交补丁到开源CNI插件项目。有关更多详细信息，请参阅[替代CNI插件](https://docs.aws.amazon.com/eks/latest/userguide/alternate-cni-plugins.html)用户指南。

#### 使用私有NAT网关

Amazon VPC现在提供[私有NAT网关](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-nat-gateway.html)功能。Amazon的私有NAT网关使私有子网中的实例能够连接到具有重叠CIDR的其他VPC和本地网络。考虑使用此[博客文章](https://aws.amazon.com/blogs/containers/addressing-ipv4-address-exhaustion-in-amazon-eks-clusters-using-private-nat-gateways/)中描述的方法来使用私有NAT网关来解决由于重叠CIDR导致的EKS工作负载通信问题，这是我们客户表达的一个重大疑虑。自定义网络无法单独解决重叠CIDR困难，并且增加了配置挑战。

本博客文章实现中使用的网络架构遵循了Amazon VPC文档中[启用重叠网络之间的通信](https://docs.aws.amazon.com/vpc/latest/userguide/nat-gateway-scenarios.html#private-nat-overlapping-networks)的建议。正如本博客文章所示，您可以结合RFC6598地址扩展私有NAT网关的使用，以管理客户的私有IP耗尽问题。EKS集群、工作节点部署在不可路由的100.64.0.0/16 VPC辅助CIDR范围内，而私有NAT网关、NAT网关则部署在可路由的RFC1918 CIDR范围内。本博客解释了如何使用传输网关连接VPC，以便在具有重叠不可路由CIDR范围的VPC之间进行通信。对于VPC中不可路由地址范围内的EKS资源需要与没有重叠地址范围的其他VPC通信的用例，客户可以选择使用VPC对等连接来互连这些VPC。这种方法可能会节省成本，因为现在通过VPC对等连接在可用区内传输的所有数据都是免费的。

![使用私有NAT网关的网络流量示意图](./image-3.png)

#### 节点和Pod的唯一网络

如果出于安全原因需要将节点和Pod隔离到特定网络，我们建议将节点和Pod部署到较大辅助CIDR块(如100.64.0.0/8)的子网中。在VPC中安装新的CIDR后，您可以使用辅助CIDR部署另一个节点组，并排空原始节点以自动将pod重新部署到新的工作节点上。有关如何实现的更多信息，请参阅此[博客](https://aws.amazon.com/blogs/containers/optimize-ip-addresses-usage-by-pods-in-your-amazon-eks-cluster/)文章。

自定义网络在下图所示的设置中未使用。相反，Kubernetes工作节点部署在VPC的辅助VPC CIDR范围内的子网上，例如100.64.0.0/10。您可以保持EKS集群运行(控制平面将保留在原始子网上),但节点和Pod将被移动到辅助子网。这是另一种缓解VPC中IP耗尽危险的非常规技术。我们建议在重新部署Pod到新工作节点之前先清空旧节点。

![illustration of worker nodes on secondary subnet](./image-2.png)

### 使用可用区域标签自动配置

您可以启用Kubernetes自动应用相应的ENIConfig到工作节点的可用区域(AZ)。

Kubernetes会自动将标签[`topology.kubernetes.io/zone`](http://topology.kubernetes.io/zone)添加到您的工作节点上。当您每个可用区域只有一个辅助子网(备用CIDR)时，Amazon EKS建议使用可用区域作为您的ENI配置名称。请注意，标签`failure-domain.beta.kubernetes.io/zone`已被弃用，并被标签`topology.kubernetes.io/zone`所取代。

1. 将`name`字段设置为VPC的可用区域。
2. 使用以下命令启用自动配置:

```
kubectl set env daemonset aws-node -n kube-system AWS_VPC_K8S_CNI_CUSTOM_NETWORK_CFG=true
```

如果您每个可用区域有多个辅助子网，您需要创建一个特定的`ENI_CONFIG_LABEL_DEF`。您可以考虑将`ENI_CONFIG_LABEL_DEF`配置为[`k8s.amazonaws.com/eniConfig`](http://k8s.amazonaws.com/eniConfig),并为节点添加自定义eniConfig名称的标签，例如[`k8s.amazonaws.com/eniConfig=us-west-2a-subnet-1`](http://k8s.amazonaws.com/eniConfig=us-west-2a-subnet-1)和[`k8s.amazonaws.com/eniConfig=us-west-2a-subnet-2`](http://k8s.amazonaws.com/eniConfig=us-west-2a-subnet-2)。

### 配置辅助网络时替换Pod

启用自定义网络不会修改现有节点。自定义网络是一种破坏性操作。启用自定义网络后，我们建议您不要对集群中的所有工作节点进行滚动替换，而是更新 [EKS 入门指南](https://docs.aws.amazon.com/eks/latest/userguide/getting-started.html)中的 AWS CloudFormation 模板，添加一个自定义资源，该资源调用 Lambda 函数在工作节点配置之前，使用环境变量启用自定义网络来更新 `aws-node` DaemonSet。

如果在切换到自定义 CNI 网络功能之前，您的集群中有任何节点上运行着 Pod，您应该隔离并[排空这些节点](https://aws.amazon.com/premiumsupport/knowledge-center/eks-worker-node-actions/),以优雅地关闭 Pod 并终止节点。只有与 ENIConfig 标签或注释匹配的新节点才会使用自定义网络，因此，调度在这些新节点上的 Pod 才能从辅助 CIDR 分配 IP。

### 计算每个节点的最大 Pod 数量

由于节点的主 ENI 不再用于为 Pod 分配 IP 地址，因此您可以在给定的 EC2 实例类型上运行的 Pod 数量会减少。为了解决此限制，您可以在自定义网络中使用前缀分配。使用前缀分配时，每个辅助 IP 都会在辅助 ENI 上替换为 /28 前缀。

考虑使用自定义网络时 m5.large 实例的最大 Pod 数量。

如果不使用前缀分配，您可以运行的最大 Pod 数量为 29

* ((3 个 ENI - 1) * (每个 ENI 的 10 个辅助 IP - 1)) + 2 = 20

启用前缀附加后，Pod 数量增加到 290。

* (((3 个 ENI - 1) * ((每个 ENI 的 10 个辅助 IP - 1) * 16)) + 2 = 290

但是，我们建议将max-pods设置为110而不是290，因为该实例的虚拟CPU数量相当小。在更大的实例上，EKS建议将max pods值设置为250。当使用较小实例类型(如m5.large)的前缀附件时，您可能会在用尽实例的CPU和内存资源之前就用尽了其IP地址。

!!! info
    当CNI前缀为ENI分配/28前缀时，它必须是一个连续的IP地址块。如果生成前缀的子网高度分散，则前缀附件可能会失败。您可以通过为集群创建新的专用VPC或为前缀附件保留一组CIDR来缓解这种情况。有关此主题的更多信息，请访问[子网CIDR保留](https://docs.aws.amazon.com/vpc/latest/userguide/subnet-cidr-reservation.html)。

### 识别现有CG-NAT空间的使用情况

自定义网络允许您缓解IP耗尽问题，但它无法解决所有挑战。如果您已经为集群使用CG-NAT空间，或者根本无法将辅助CIDR与集群VPC关联，我们建议您探索其他选项，如使用替代CNI或迁移到IPv6集群。