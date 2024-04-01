# VPC 和子网注意事项

运行 EKS 集群除了需要了解 Kubernetes 网络之外，还需要了解 AWS VPC 网络。

我们建议您在开始设计 VPC 或将集群部署到现有 VPC 之前，先了解 EKS 控制平面通信机制。

在为 EKS 构建 VPC 和子网时，请参考[集群 VPC 注意事项](https://docs.aws.amazon.com/eks/latest/userguide/network_reqs.html)和[Amazon EKS 安全组注意事项](https://docs.aws.amazon.com/eks/latest/userguide/sec-group-reqs.html)。

## 概述

### EKS 集群架构

EKS 集群由两个 VPC 组成:

* 一个由 AWS 管理的 VPC，用于托管 Kubernetes 控制平面。该 VPC 不会出现在客户账户中。
* 一个由客户管理的 VPC，用于托管 Kubernetes 节点。容器运行在这里，以及其他由客户管理的 AWS 基础设施，如集群使用的负载均衡器。该 VPC 会出现在客户账户中。您需要在创建集群之前创建客户管理的 VPC。如果您没有提供 VPC，eksctl 会创建一个。

客户 VPC 中的节点需要能够连接到 AWS VPC 中的托管 API 服务器端点。这允许节点注册到 Kubernetes 控制平面，并接收运行应用程序 Pod 的请求。

节点通过 (a) EKS 公共端点或 (b) 由 EKS 管理的跨账户[弹性网络接口](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-eni.html) (X-ENI) 连接到 EKS 控制平面。在创建集群时，您需要指定至少两个 VPC 子网。EKS 会在创建集群时指定的每个子网中放置一个跨账户 ENI(也称为集群子网)。Kubernetes API 服务器使用这些跨账户 ENI 与部署在客户管理的集群 VPC 子网上的节点进行通信。

![集群网络的一般说明，包括负载均衡器、节点和 Pod。](./image.png)

当节点启动时，EKS 引导脚本被执行，并安装 Kubernetes 节点配置文件。作为每个实例的启动过程的一部分，容器运行时代理、kubelet 和 Kubernetes 节点代理被启动。

为了注册节点，Kubelet 会联系 Kubernetes 集群端点。它会与 VPC 外部的公共端点或 VPC 内部的私有端点建立连接。Kubelet 会定期接收 API 指令，并向端点提供状态更新和心跳。

### EKS 控制平面通信

EKS 有两种方式来控制对[集群端点](https://docs.aws.amazon.com/eks/latest/userguide/cluster-endpoint.html)的访问。端点访问控制允许您选择端点是否可以从公共互联网访问，或仅通过您的 VPC 访问。您可以启用公共端点(这是默认设置)、私有端点或同时启用两者。

集群 API 端点的配置决定了节点与控制平面通信的路径。请注意，这些端点设置可以随时通过 EKS 控制台或 API 进行更改。

#### 公共端点

这是新的 Amazon EKS 集群的默认行为。当仅启用集群的公共端点时，源自集群 VPC 内部(如工作节点到控制平面的通信)的 Kubernetes API 请求会离开 VPC，但不会离开 Amazon 的网络。为了让节点连接到控制平面，它们必须具有公共 IP 地址，并有一条通往互联网网关或 NAT 网关的路由，以便它们可以使用 NAT 网关的公共 IP 地址。

#### 公共和私有端点

当同时启用公共和私有端点时，来自 VPC 内部的 Kubernetes API 请求会通过 VPC 内的 X-ENI 与控制平面通信。您的集群 API 服务器可从互联网访问。

#### 私有端点

当仅启用私有端点时，您的 API 服务器无法从互联网公开访问。所有发往您集群 API 服务器的流量必须来自您的 VPC 或连接的网络。节点通过 VPC 内的 X-ENI 与 API 服务器通信。请注意，集群管理工具必须能够访问私有端点。了解更多关于[如何从 Amazon VPC 外部连接到私有 Amazon EKS 集群端点的信息。](https://aws.amazon.com/premiumsupport/knowledge-center/eks-private-cluster-endpoint-vpc/)

请注意，集群的 API 服务器端点由公共 DNS 服务器解析为来自 VPC 的私有 IP 地址。过去，该端点只能从 VPC 内部解析。

### VPC 配置

Amazon VPC 支持 IPv4 和 IPv6 寻址。Amazon EKS 默认支持 IPv4。VPC 必须与之关联一个 IPv4 CIDR 块。您也可以选择将多个 IPv4 [无类域间路由](http://en.wikipedia.org/wiki/CIDR_notation) (CIDR) 块和多个 IPv6 CIDR 块关联到您的 VPC。创建 VPC 时，您必须从 [RFC 1918](http://www.faqs.org/rfcs/rfc1918.html) 中指定的私有 IPv4 地址范围为 VPC 指定一个 IPv4 CIDR 块。允许的块大小介于 /16 前缀(65,536 个 IP 地址)和 /28 前缀(16 个 IP 地址)之间。

创建新的 VPC 时，您可以附加一个 IPv6 CIDR 块，更改现有 VPC 时最多可以附加五个。IPv6 CIDR 块大小的前缀长度可以在 /44 和 /60 之间，而 IPv6 子网可以在 /44 和 /64 之间。您可以从 Amazon 维护的 IPv6 地址池中请求一个 IPv6 CIDR 块。有关更多信息，请参阅 VPC 用户指南中的 [VPC CIDR 块](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-cidr-blocks.html)部分。

Amazon EKS 集群支持 IPv4 和 IPv6。默认情况下，EKS 集群使用 IPv4 IP。在创建集群时指定 IPv6 将启用使用 IPv6 集群。IPv6 集群需要双堆栈 VPC 和子网。

Amazon EKS 建议您在创建集群时至少使用两个位于不同可用区的子网。在集群创建期间传入的子网称为集群子网。创建集群时，Amazon EKS 会在您指定的子网中创建多达 4 个跨账户 (x-account 或 x-ENIs) ENI。x-ENI 始终部署并用于集群管理流量，如日志传递、exec 和代理。有关完整的 VPC 和子网要求详情，请参阅 EKS 用户指南中的[VPC 和子网要求](https://docs.aws.amazon.com/eks/latest/userguide/network_reqs.html#network-requirements-subnets)。

Kubernetes 工作节点可以在集群子网中运行，但不建议这样做。在[集群升级](https://aws.github.io/aws-eks-best-practices/upgrades/#verify-available-ip-addresses)期间，Amazon EKS 会在集群子网中配置额外的 ENI。当您的集群扩展时，工作节点和 Pod 可能会消耗集群子网中的可用 IP。因此，为了确保有足够的可用 IP，您可能需要考虑使用具有 /28 网络掩码的专用集群子网。

Kubernetes 工作节点可以在公共或私有子网中运行。子网是公共还是私有取决于子网内的流量是否通过[互联网网关](https://docs.aws.amazon.com/vpc/latest/userguide/VPC_Internet_Gateway.html)路由。公共子网在路由表中有一个条目，通过互联网网关访问互联网，但私有子网没有。

来自其他地方并到达您节点的流量称为*入站流量*。从节点发出并离开网络的流量称为*出站流量*。在配置了互联网网关的子网中具有公共或弹性IP地址(EIP)的节点允许来自VPC外部的入站流量。私有子网通常包括一个[NAT网关](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-nat-gateway.html)，它只允许来自VPC内部的入站流量到达节点，同时仍允许*来自*节点的流量离开VPC(*出站流量*)。

在IPv6世界中，每个地址都可以路由到互联网。与节点和pod关联的IPv6地址是公共的。通过在VPC中实现[仅出站互联网网关(EIGW)](https://docs.aws.amazon.com/vpc/latest/userguide/egress-only-internet-gateway.html)来支持私有子网，允许出站流量同时阻止所有入站流量。实施IPv6子网的最佳实践可以在[VPC用户指南](https://docs.aws.amazon.com/vpc/latest/userguide/VPC_Scenario2.html)中找到。

### 您可以通过三种不同的方式配置VPC和子网：

#### 仅使用公共子网

节点和入站资源(如负载均衡器)都在同一公共子网中创建。标记公共子网为[`kubernetes.io/role/elb`](http://kubernetes.io/role/elb)以构建面向互联网的负载均衡器。在此配置中，可以将集群端点配置为公共、私有或两者(公共和私有)。

#### 使用私有和公共子网

节点在私有子网上创建，而入站资源则在公共子网上实例化。您可以启用对集群端点的公共、私有或两者(公共和私有)访问。根据集群端点的配置，节点流量将通过NAT网关或ENI进入。

#### 仅使用私有子网

两个节点和入口都在私有子网中创建。使用[`kubernetes.io/role/internal-elb`](http://kubernetes.io/role/internal-elb:1)子网标签来构建内部负载均衡器。访问集群的端点需要VPN连接。您必须为EC2和所有Amazon ECR和S3存储库激活[AWS PrivateLink](https://docs.aws.amazon.com/vpc/latest/userguide/endpoint-service.html)。只有集群的私有端点应该被启用。在配置私有集群之前，我们建议您通读[EKS私有集群要求](https://docs.aws.amazon.com/eks/latest/userguide/private-clusters.html)。

### 跨VPC通信

在许多场景中，您需要多个VPC和部署在这些VPC中的单独EKS集群。

您可以使用[Amazon VPC Lattice](https://aws.amazon.com/vpc/lattice/)在多个VPC和账户之间一致且安全地连接服务(无需像VPC对等、AWS PrivateLink或AWS Transit Gateway这样的服务提供额外的连接)。在[这里](https://aws.amazon.com/blogs/networking-and-content-delivery/build-secure-multi-account-multi-vpc-connectivity-for-your-applications-with-amazon-vpc-lattice/)了解更多信息。

![Amazon VPC Lattice, traffic flow](./vpc-lattice.gif)

Amazon VPC Lattice在IPv4和IPv6的链路本地地址空间中运行，为可能存在重叠IPv4地址的服务之间提供连接。为了提高运营效率，我们强烈建议将EKS集群和节点部署到不重叠的IP范围。如果您的基础设施包括具有重叠IP范围的VPC，您需要相应地设计您的网络。我们建议[私有NAT网关](https://docs.aws.amazon.com/vpc/latest/userguide/vpc-nat-gateway.html#nat-gateway-basics),或与[传输网关](https://docs.aws.amazon.com/whitepapers/latest/aws-vpc-connectivity-options/aws-transit-gateway.html)结合使用[自定义网络](../custom-networking/index.md)模式下的VPC CNI，以集成EKS上的工作负载，解决重叠CIDR挑战，同时保留可路由的RFC1918 IP地址。

![Private Nat Gateway with Custom Networking, traffic flow](./private-nat-gw.gif)

如果您是服务提供商，并希望与单独账户中的客户VPC共享您的Kubernetes服务和入口(ALB或NLB),请考虑使用[AWS PrivateLink](https://docs.aws.amazon.com/vpc/latest/privatelink/privatelink-share-your-services.html),也称为端点服务。

### 跨多个账户共享VPC

许多企业采用共享Amazon VPC作为简化网络管理、降低成本和提高整个AWS组织中多个AWS账户的安全性的一种手段。他们利用AWS Resource Access Manager (RAM)安全地与单个AWS账户、组织单位(OU)或整个AWS组织共享支持的[AWS资源](https://docs.aws.amazon.com/ram/latest/userguide/shareable.html)。

您可以使用AWS RAM在另一个AWS账户的共享VPC子网中部署Amazon EKS集群、托管节点组和其他支持AWS资源(如负载均衡器、安全组、端点等)。下图描述了一个示例高级架构。这允许中央网络团队控制网络构造(如VPC、子网等)，同时允许应用程序或平台团队在各自的AWS账户中部署Amazon EKS集群。此场景的完整演练可在此[github存储库](https://github.com/aws-samples/eks-shared-subnets)中找到。

![在AWS账户之间的VPC共享子网中部署Amazon EKS。](./eks-shared-subnets.png)

#### 使用共享子网时的注意事项

* Amazon EKS集群和工作节点可以在属于同一VPC的共享子网内创建。Amazon EKS不支持跨多个VPC创建集群。

* Amazon EKS使用AWS VPC安全组(SG)来控制Kubernetes控制平面与集群工作节点之间的流量。安全组也用于控制工作节点与其他VPC资源和外部IP地址之间的流量。您必须在应用程序/参与者账户中创建这些安全组。请确保您打算为pod使用的安全组也位于参与者账户中。您可以在安全组内配置入站和出站规则，以允许与位于中央VPC账户的安全组之间的必要流量。

* 在您的Amazon EKS集群所在的参与者账户中创建IAM角色和关联的策略。这些IAM角色和策略对于授予Amazon EKS托管的Kubernetes集群、在Fargate上运行的节点和pod所需的权限至关重要。这些权限使Amazon EKS能够代表您调用其他AWS服务。

* 您可以遵循以下方法允许 k8s pod 跨账户访问 AWS 资源(如 Amazon S3 存储桶、DynamoDB 表等):
    * **基于资源的策略方法**:如果 AWS 服务支持资源策略，您可以添加适当的基于资源的策略，以允许跨账户访问分配给 kubernetes pod 的 IAM 角色。在这种情况下，OIDC 提供程序、IAM 角色和权限策略存在于应用程序账户中。要查找支持基于资源的策略的 AWS 服务，请参阅 [与 IAM 协同工作的 AWS 服务](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_aws-services-that-work-with-iam.html),并查看"基于资源"列中显示为"是"的服务。

    * **OIDC 提供程序方法**:OIDC 提供程序、IAM 角色、权限和信任策略等 IAM 资源将在存在资源的其他参与 AWS 账户中创建。这些角色将分配给应用程序账户中的 Kubernetes pod，以便它们可以访问跨账户资源。有关此方法的完整演练，请参阅 [Kubernetes 服务账户的跨账户 IAM 角色](https://aws.amazon.com/blogs/containers/cross-account-iam-roles-for-kubernetes-service-accounts/)博客。

* 您可以在应用程序或中央网络账户中部署 Amazon Elastic Load Balancer (ELB) 资源(ALB 或 NLB),以将流量路由到 k8s pod。有关在中央网络账户中部署 ELB 资源的详细说明，请参阅 [通过跨账户负载均衡器公开 Amazon EKS Pod](https://aws.amazon.com/blogs/containers/expose-amazon-eks-pods-through-cross-account-load-balancer/)演练。此选项提供了增强的灵活性，因为它授予中央网络账户对负载均衡器资源的安全配置完全控制权。

* 当使用 Amazon VPC CNI 的 `custom networking feature` 时，您需要使用中央网络账户中列出的可用区 (AZ) ID 映射来创建每个 `ENIConfig`。这是由于每个 AWS 账户中物理可用区与可用区名称的随机映射所致。

### 安全组

[*安全组*](https://docs.aws.amazon.com/vpc/latest/userguide/VPC_SecurityGroups.html) 控制与其关联的资源允许到达和离开的流量。Amazon EKS 使用安全组来管理 [控制平面和节点](https://docs.aws.amazon.com/eks/latest/userguide/sec-group-reqs.html) 之间的通信。当您创建集群时，Amazon EKS 会创建一个名为 `eks-cluster-sg-my-cluster-uniqueID` 的安全组。EKS 将这些安全组关联到托管的 ENI 和节点。默认规则允许您的集群和节点之间自由流动所有流量，并允许所有出站流量到达任何目的地。

当您创建集群时，您可以指定自己的安全组。当您指定自己的安全组时，请参阅[安全组建议](https://docs.aws.amazon.com/eks/latest/userguide/sec-group-reqs.html)。

## 建议

### 考虑多可用区部署

AWS 区域提供多个物理隔离的可用区 (AZ),这些可用区通过低延迟、高吞吐量和高度冗余的网络相连。通过可用区，您可以设计和运行能够在可用区之间自动无中断故障转移的应用程序。Amazon EKS 强烈建议将 EKS 集群部署到多个可用区。在创建集群时，请考虑在至少两个可用区中指定子网。

在节点上运行的 Kubelet 会自动为节点对象添加标签，如 [`topology.kubernetes.io/region=us-west-2` 和 `topology.kubernetes.io/zone=us-west-2d`](http://topology.kubernetes.io/region=us-west-2,topology.kubernetes.io/zone=us-west-2d)。我们建议结合使用节点标签和 [Pod 拓扑分布约束](https://kubernetes.io/docs/concepts/scheduling-eviction/topology-spread-constraints/) 来控制 Pod 在各个区域的分布。这些提示使 Kubernetes [调度器](https://kubernetes.io/docs/reference/command-line-tools-reference/kube-scheduler/) 能够更好地放置 Pod，提高预期可用性，降低相关故障影响整个工作负载的风险。请参阅 [将节点分配给 Pod](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/#nodeselector) 以查看节点选择器和可用区分布约束的示例。

您可以在创建节点时定义子网或可用区。如果未配置子网，节点将被放置在集群子网中。EKS 对于托管节点组的支持会自动将节点跨多个可用区分布在可用容量上。[Karpenter](https://karpenter.sh/) 将根据工作负载定义的拓扑分布限制，在指定的可用区中扩展节点以实现可用区分布。

AWS Elastic Load Balancer 由 Kubernetes 集群的 AWS Load Balancer Controller 管理。它为 Kubernetes ingress 资源提供应用程序负载均衡器 (ALB)，为类型为 LoadBalancer 的 Kubernetes 服务提供网络负载均衡器 (NLB)。Elastic Load Balancer 控制器使用 [标签](https://aws.amazon.com/premiumsupport/knowledge-center/eks-vpc-subnet-discovery/) 来发现子网。ELB 控制器需要至少两个可用区 (AZ) 才能成功提供 ingress 资源。考虑在至少两个可用区设置子网，以利用地理冗余带来的安全性和可靠性。

### 将节点部署到私有子网

包含私有和公有子网的 VPC 是在 EKS 上部署 Kubernetes 工作负载的理想方法。考虑在两个不同的可用区域中至少设置两个公有子网和两个私有子网。公有子网的相关路由表包含到互联网网关的路由。Pod 可以通过 NAT 网关与互联网进行交互。私有子网在 IPv6 环境中由[仅出口互联网网关](https://docs.aws.amazon.com/vpc/latest/userguide/egress-only-internet-gateway.html)（EIGW）支持。

在私有子网中实例化节点可以最大程度地控制流向节点的流量，并且对于绝大多数 Kubernetes 应用程序都是有效的。入口资源(如负载均衡器)在公有子网中实例化，并将流量路由到在私有子网上运行的 Pod。

如果您需要严格的安全性和网络隔离，请考虑仅使用私有模式。在此配置中，三个私有子网部署在 AWS 区域 VPC 中的不同可用区域中。部署到子网的资源无法访问互联网，互联网也无法访问子网中的资源。为了让您的 Kubernetes 应用程序访问其他 AWS 服务，您必须配置 PrivateLink 接口和/或网关端点。您可以设置内部负载均衡器将流量重定向到 Pod，使用 AWS 负载均衡器控制器。私有子网必须标记([`kubernetes.io/role/internal-elb: 1`](http://kubernetes.io/role/internal-elb)),以便控制器可以提供负载均衡器。为了让节点注册到集群，集群端点必须设置为私有模式。请访问[私有集群指南](https://docs.aws.amazon.com/eks/latest/userguide/private-clusters.html)了解完整的要求和注意事项。

### 考虑集群端点的公有和私有模式

Amazon EKS 提供公开、公开和私有以及私有的集群端点模式。默认模式是公开模式，但我们建议将集群端点配置为公开和私有模式。此选项允许集群 VPC 内的 Kubernetes API 调用(如节点到控制平面的通信)使用私有 VPC 端点，并且流量保持在集群 VPC 内。另一方面，您的集群 API 服务器可以从互联网访问。但是，我们强烈建议限制可以使用公共端点的 CIDR 块。[了解如何配置公共和私有端点访问，包括限制 CIDR 块。](https://docs.aws.amazon.com/eks/latest/userguide/cluster-endpoint.html#modify-endpoint-access)

当您需要安全性和网络隔离时，我们建议使用私有端点。我们建议使用 [EKS 用户指南](https://docs.aws.amazon.com/eks/latest/userguide/cluster-endpoint.html#private-access)中列出的任一选项私下连接到 API 服务器。

### 谨慎配置安全组

Amazon EKS 支持使用自定义安全组。任何自定义安全组都必须允许节点和 Kubernetes 控制平面之间的通信。如果您的组织不允许开放通信，请检查[端口要求](https://docs.aws.amazon.com/eks/latest/userguide/sec-group-reqs.html)并手动配置规则。

EKS 将您在集群创建期间提供的自定义安全组应用于托管接口 (X-ENIs)。但是，它不会立即将它们与节点关联。在创建节点组时，强烈建议手动[关联自定义安全组](https://eksctl.io/usage/schema/#nodeGroups-securityGroups)。请考虑启用 [securityGroupSelectorTerms](https://karpenter.sh/docs/concepts/nodeclasses/#specsecuritygroupselectorterms),以便在节点自动扩缩期间启用 Karpenter 节点模板发现自定义安全组。

我们强烈建议创建一个安全组来允许所有节点间通信流量。在引导过程中，节点需要出站互联网连接来访问集群端点。请评估外部访问要求，如本地连接和容器注册表访问，并相应地设置规则。在将更改投入生产之前，我们强烈建议您在开发环境中仔细检查连接。

### 在每个可用区域部署 NAT 网关

如果您在私有子网(IPv4和IPv6)中部署节点，请考虑在每个可用区域(AZ)创建一个 NAT 网关，以确保区域独立架构并减少跨 AZ 支出。每个 AZ 中的 NAT 网关都具有冗余实现。

### 使用 Cloud9 访问私有集群

AWS Cloud9 是一个基于 Web 的 IDE，可以使用 AWS Systems Manager 安全地在私有子网中运行，而无需入站访问。也可以在 Cloud9 实例上禁用出站。[了解有关使用 Cloud9 访问私有集群和子网的更多信息。](https://aws.amazon.com/blogs/security/isolating-network-access-to-your-aws-cloud9-environments/)

![AWS Cloud9 控制台连接到无入站 EC2 实例的插图。](./image-2.jpg)