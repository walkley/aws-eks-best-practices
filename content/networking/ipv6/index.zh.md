# 运行 IPv6 EKS 集群

<iframe width="560" height="315" src="https://www.youtube.com/embed/zdXpTT0bZXo" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe>

EKS 在 IPv6 模式下可以解决大规模 EKS 集群中常见的 IPv4 耗尽挑战。EKS 对 IPv6 的支持旨在解决 IPv4 地址空间有限导致的 IPv4 耗尽问题。这是许多客户提出的一个重大问题，与 Kubernetes 的"[IPv4/IPv6 双栈](https://kubernetes.io/docs/concepts/services-networking/dual-stack/)"功能不同。
EKS/IPv6 还将提供使用 IPv6 CIDR 互连网络边界的灵活性，从而最小化遭受 CIDR 重叠的可能性，因此解决了两个问题(集群内和跨集群)。
在 IPv6 模式(--ip-family ipv6)部署 EKS 集群时，此操作是不可逆的。简单来说，EKS IPv6 支持将在整个集群生命周期内启用。

在 IPv6 EKS 集群中，Pod 和 Service 将收到 IPv6 地址，同时保持与遗留 IPv4 端点的兼容性。这包括外部 IPv4 端点访问集群内服务的能力，以及 Pod 访问外部 IPv4 端点的能力。

Amazon EKS IPv6 支持利用了 VPC 原生的 IPv6 功能。每个 VPC 都分配了一个 IPv4 地址前缀(CIDR 块大小可以从 /16 到 /28)和来自 Amazon 的 GUA(全局单播地址)的唯一 /56 IPv6 地址前缀(固定);您可以为 VPC 中的每个子网分配一个 /64 地址前缀。IPv4 功能，如路由表、网络访问控制列表、对等和 DNS 解析，在启用了 IPv6 的 VPC 中的工作方式相同。然后，VPC 被称为双栈 VPC，在双栈子网之后，下图描述了支持基于 EKS/IPv6 的集群的 IPV4&IPv6 VPC 基础模式:

![双堆栈 VPC，EKS 集群在 IPv6 模式下的必需基础](./eks-ipv6-foundation.png)

在 IPv6 世界中，每个地址都是可路由到互联网的。默认情况下，VPC 从公共 GUA 范围分配 IPv6 CIDR。VPC 不支持从 RFC 4193 定义的[唯一本地地址 (ULA)](https://en.wikipedia.org/wiki/Unique_local_address) 范围 (fd00::/8 或 fc00::/8) 分配私有 IPv6 地址。即使您希望分配您自己拥有的 IPv6 CIDR，也是如此。通过在 VPC 中实现仅出口互联网网关 (EIGW)，可以从私有子网出口到互联网，允许出站流量但阻止所有入站流量。
以下图表显示了 EKS/IPv6 集群内 Pod IPv6 互联网出口流量的流向:

![双堆栈 VPC， EKS 集群在 IPv6 模式下， Pod 在私有子网出口到互联网 IPv6 端点](./eks-egress-ipv6.png)

实现 IPv6 子网的最佳实践可以在 [VPC 用户指南](https://docs.aws.amazon.com/whitepapers/latest/ipv6-on-aws/IPv6-on-AWS.html)中找到。

在 IPv6 EKS 集群中，节点和 Pod 会收到公共 IPv6 地址。EKS 根据唯一本地 IPv6 单播地址 (ULA) 为服务分配 IPv6 地址。IPv6 集群的 ULA 服务 CIDR 在集群创建阶段自动分配，与 IPv4 不同，无法指定。以下图表显示了基于 EKS/IPv6 的集群控制平面和数据平面基础模式:

![双堆栈 VPC， EKS 集群在 IPv6 模式下， 控制平面 ULA， 数据平面 EC2 和 Pod 的 IPv6 GUA](./eks-cluster-ipv6-foundation.png)

## 概述

EKS/IPv6 仅在前缀模式下受支持 (VPC-CNI 插件 ENI IP 分配模式)。了解更多关于 [前缀模式](https://aws.github.io/aws-eks-best-practices/networking/prefix-mode/index_linux/)的信息。
> 前缀分配仅适用于基于 Nitro 的 EC2 实例，因此 EKS/IPv6 仅在集群数据平面使用基于 Nitro 的 EC2 实例时受支持。

简单来说，每个工作节点的/80 IPv6前缀将产生约10^14个IPv6地址，限制因素将不再是IP，而是Pod密度(资源方面)。

IPv6前缀分配仅在EKS工作节点引导时发生。
这种行为旨在缓解高Pod周转EKS/IPv4集群中由于VPC CNI插件(ipamd)生成的节流API调用(旨在及时分配私有IPv4地址)而导致Pod调度延迟的情况。它还被认为使VPC-CNI插件高级旋钮调优[WARM_IP/ENI*,MINIMUM_IP*](https://github.com/aws/amazon-vpc-cni-k8s#warm_ip_target)变得不必要。

下图放大显示了IPv6工作节点弹性网络接口(ENI):

![illustration of worker subnet, including primary ENI with multiple IPv6 Addresses](./image-2.png)

每个EKS工作节点都被分配了IPv4和IPv6地址，以及相应的DNS条目。对于给定的工作节点，只消耗了双栈子网中的一个IPv4地址。EKS对IPv6的支持使您能够通过高度固定的仅出口IPv4模型与IPv4端点(AWS、内部、互联网)通信。EKS实现了一个主机本地CNI插件，次于VPC CNI插件，用于为Pod分配和配置IPv4地址。CNI插件从169.254.172.0/22范围为Pod配置一个主机特定的不可路由IPv4地址。分配给Pod的IPv4地址*仅对工作节点唯一*,*不会在工作节点之外传播*。169.254.172.0/22提供了多达1024个唯一的IPv4地址，可支持大型实例类型。

下图描绘了IPv6 Pod连接到集群边界之外的IPv4端点(非互联网)的流程:

![EKS/IPv6, IPv4 egress-only flow](./eks-ipv4-snat-cni.png)

在上图中，Pod 将对端点执行 DNS 查找，并在收到 IPv4 "A" 响应后，Pod 的节点专用唯一 IPv4 地址将通过源网络地址转换 (SNAT) 转换为附加到 EC2 Worker 节点的主网络接口的私有 IPv4 (VPC) 地址。

EKS/IPv6 Pod 还需要使用公共 IPv4 地址通过互联网连接到 IPv4 端点，为此存在类似的流程。
下图描述了 IPv6 Pod 连接到集群边界之外的 IPv4 端点(可路由到互联网)的流程:

![EKS/IPv6, IPv4 Internet egress-only flow](./eks-ipv4-snat-cni-internet.png)

在上图中，Pod 将对端点执行 DNS 查找，并在收到 IPv4 "A" 响应后，Pod 的节点专用唯一 IPv4 地址将通过源网络地址转换 (SNAT) 转换为附加到 EC2 Worker 节点的主网络接口的私有 IPv4 (VPC) 地址。然后 Pod IPv4 地址(源 IPv4: EC2 主 IP)将路由到 IPv4 NAT 网关，在那里 EC2 主 IP 将被转换(SNAT)为有效的可路由到互联网的 IPv4 公共 IP 地址(NAT 网关分配的公共 IP)。

任何跨节点的 Pod 到 Pod 通信始终使用 IPv6 地址。VPC CNI 配置 iptables 来处理 IPv6 并阻止任何 IPv4 连接。

Kubernetes 服务将仅从 [本地 IPv6 单播地址 (ULA)](https://datatracker.ietf.org/doc/html/rfc4193) 的唯一地址范围内接收 IPv6 地址(ClusterIP)。IPv6 集群的 ULA 服务 CIDR 在 EKS 集群创建阶段自动分配，无法修改。下图描述了 Pod 到 Kubernetes 服务的流程:

![EKS/IPv6, IPv6 Pod to IPv6 k8s service (ClusterIP ULA) flow](./Pod-to-service-ipv6.png)

服务通过AWS负载均衡器暴露在互联网上。负载均衡器接收公共IPv4和IPv6地址，也称为双栈负载均衡器。对于访问IPv6集群Kubernetes服务的IPv4客户端，负载均衡器执行IPv4到IPv6的转换。

Amazon EKS建议在私有子网中运行工作节点和Pod。您可以在公共子网中创建公共负载均衡器，这些负载均衡器将流量负载均衡到运行在私有子网中节点上的Pod。
下图描绘了互联网IPv4用户访问EKS/IPv6 Ingress服务的情况:

![Internet IPv4 user to EKS/IPv6 Ingress service](./ipv4-internet-to-eks-ipv6.png)

> 注意:上述模式需要部署[最新版本](https://kubernetes-sigs.github.io/aws-load-balancer-controller)的AWS负载均衡器控制器

### EKS控制平面 <-> 数据平面通信

EKS将以双栈模式(IPv4/IPv6)在跨账户ENI(X-ENI)中设置。Kubernetes节点组件如kubelet和kube-proxy被配置为支持双栈。Kubelet和kube-proxy在hostNetwork模式下运行，并绑定到节点主网络接口上附加的IPv4和IPv6地址。Kubernetes api-server通过X-ENI与Pod和节点组件通信，基于IPv6。Pod通过X-ENI与api-server通信，Pod到api-server的通信始终使用IPv6模式。

![illustration of cluster including X-ENIs](./image-5.png)

## 建议

### 保持对IPv4 EKS API的访问

EKS API只能通过IPv4访问。这也包括集群API端点。您将无法从纯IPv6网络访问集群端点和API。您的网络需要支持(1)NAT64/DNS64等IPv6过渡机制，以促进IPv6和IPv4主机之间的通信，(2)支持IPv4端点转换的DNS服务。

### 根据计算资源进行调度

单个IPv6前缀就足以在单个节点上运行许多Pod。这也有效地消除了ENI和IP对节点上最大Pod数量的限制。尽管IPv6消除了对max-Pods的直接依赖性，但当使用较小的实例类型(如m5.large)的前缀附件时，您可能会先耗尽实例的CPU和内存资源，而不是IP地址。如果您使用自管理节点组或具有自定义AMI ID的托管节点组，则必须手动设置EKS推荐的最大Pod值。

您可以使用以下公式来确定可以在IPv6 EKS集群的节点上部署的最大Pod数量。

* ((实例类型的网络接口数量(每个网络接口的前缀数-1)* 16) + 2

* ((3个ENI)*((每个ENI的10个辅助IP-1)* 16)) + 2 = 460 (实际)

托管节点组会自动为您计算最大Pod数量。避免更改EKS推荐的最大Pod数量值，以避免由于资源限制而导致Pod调度失败。

### 评估现有自定义网络的目的

如果当前已启用[自定义网络](https://aws.github.io/aws-eks-best-practices/networking/custom-networking/),Amazon EKS建议您重新评估在IPv6下对其的需求。如果您选择使用自定义网络来解决IPv4耗尽问题，那么在IPv6下就不再需要了。如果您正在利用自定义网络来满足安全要求，例如为节点和Pod提供单独的网络，我们鼓励您提交[EKS路线图请求](https://github.com/aws/containers-roadmap/issues)。

### EKS/IPv6集群中的Fargate Pod

EKS支持在Fargate上运行的Pod使用IPv6。在Fargate上运行的Pod将消耗从VPC CIDR范围（IPv4和IPv6）划分的IPv6和VPC可路由私有IPv4地址。简单来说，您的EKS/Fargate Pod集群范围内的密度将受到可用IPv4和IPv6地址的限制。建议为您的双栈子网/VPC CIDR预留未来增长空间。如果底层子网没有可用的IPv4地址，无论是否有可用的IPv6地址，您都将无法调度新的Fargate Pod。

### 部署AWS负载均衡器控制器 (LBC)

**上游内置的Kubernetes服务控制器不支持IPv6**。我们建议使用[最新版本](https://kubernetes-sigs.github.io/aws-load-balancer-controller)的AWS负载均衡器控制器插件。LBC只会在消费带有注解`"alb.ingress.kubernetes.io/ip-address-type: dualstack"`和`"alb.ingress.kubernetes.io/target-type: ip"`的相应kubernetes服务/ingress定义时部署双栈NLB或双栈ALB。

AWS网络负载均衡器不支持双栈UDP协议地址类型。如果您对低延迟、实时流媒体、在线游戏和物联网有强烈需求，我们建议运行IPv4集群。要了解如何管理UDP服务的健康检查，请参阅["如何将UDP流量路由到Kubernetes"](https://aws.amazon.com/blogs/containers/how-to-route-udp-traffic-into-kubernetes/)。

### 识别对IMDSv2的依赖

EKS在IPv6模式下暂不支持IMDSv2端点。如果IMDSv2是您迁移到EKS/IPv6的阻碍，请开立支持工单。