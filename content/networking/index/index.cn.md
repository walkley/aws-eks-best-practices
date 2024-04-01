# Amazon EKS 网络最佳实践指南

了解 Kubernetes 网络对于高效运行集群和应用程序至关重要。Pod 网络(也称为集群网络)是 Kubernetes 网络的核心。Kubernetes 支持 [Container Network Interface](https://github.com/containernetworking/cni) (CNI) 插件用于集群网络。

Amazon EKS 官方支持 [Amazon Virtual Private Cloud (VPC)](https://docs.aws.amazon.com/vpc/latest/userguide/what-is-amazon-vpc.html) CNI 插件来实现 Kubernetes Pod 网络。VPC CNI 与 AWS VPC 实现了本地集成，并以底层模式工作。在底层模式下，Pod 和主机位于同一网络层，共享网络命名空间。从集群和 VPC 的角度来看，Pod 的 IP 地址是一致的。

本指南介绍了 [Amazon VPC Container Network Interface](https://github.com/aws/amazon-vpc-cni-k8s)[(VPC CNI)](https://github.com/aws/amazon-vpc-cni-k8s) 在 Kubernetes 集群网络中的应用。VPC CNI 是 EKS 支持的默认网络插件，因此是本指南的重点。VPC CNI 高度可配置，可支持不同的使用场景。本指南还包括了关于不同 VPC CNI 使用场景、操作模式、子组件的专门章节，以及相关建议。

Amazon EKS 运行上游 Kubernetes 并通过了 Kubernetes 一致性认证。尽管您可以使用替代 CNI 插件，但本指南不提供管理替代 CNI 的建议。请查阅 [EKS 替代 CNI](https://docs.aws.amazon.com/eks/latest/userguide/alternate-cni-plugins.html) 文档，了解合作伙伴列表和有效管理替代 CNI 的资源。

## Kubernetes 网络模型

Kubernetes 对集群网络提出了以下要求:

* 在同一节点上调度的 Pod 必须能够在不使用 NAT (网络地址转换) 的情况下与其他 Pod 通信。
* 运行在特定节点上的所有系统守护进程(例如后台进程 [kubelet](https://kubernetes.io/docs/concepts/overview/components/)) 都可以与运行在同一节点上的 Pod 通信。
* 使用 [主机网络](https://docs.docker.com/network/host/) 的 Pod 必须能够在不使用 NAT 的情况下与所有其他节点上的所有其他 Pod 联系。

有关 Kubernetes 对兼容网络实现的期望的详细信息，请参阅 [Kubernetes 网络模型](https://kubernetes.io/docs/concepts/services-networking/#the-kubernetes-network-model)。下图说明了 Pod 网络命名空间与主机网络命名空间之间的关系。


![illustration of host network and 2 pod network namespaces](image.png)
## 容器网络接口 (CNI)

Kubernetes 支持 CNI 规范和插件来实现 Kubernetes 网络模型。CNI 由一个 [规范](https://github.com/containernetworking/cni/blob/main/SPEC.md)(当前版本为 1.0.0)和用于编写插件以配置容器中网络接口的库组成，以及许多受支持的插件。CNI 仅关注容器的网络连接以及在删除容器时释放已分配的资源。

通过向 kubelet 传递 `--network-plugin=cni` 命令行选项，可以启用 CNI 插件。kubelet 从 `--cni-conf-dir` (默认为 /etc/cni/net.d) 读取文件，并使用该文件中的 CNI 配置为每个 Pod 设置网络。CNI 配置文件必须与 CNI 规范(最低版本 v0.4.0)匹配，并且配置中引用的任何所需 CNI 插件都必须存在于 `--cni-bin-dir` 目录(默认为 /opt/cni/bin)中。如果目录中有多个 CNI 配置文件，*kubelet 将使用按字母顺序排列的第一个配置文件*。


## Amazon 虚拟私有云 (VPC) CNI

AWS提供的VPC CNI是EKS集群的默认网络插件。在配置EKS集群时，VPC CNI插件会默认安装。VPC CNI运行在Kubernetes工作节点上。VPC CNI插件由CNI二进制文件和IP地址管理(ipamd)插件组成。CNI从VPC网络为Pod分配IP地址。ipamd为每个Kubernetes节点管理AWS弹性网络接口(ENI),并维护IP地址的预热池。VPC CNI提供了预分配ENI和IP地址的配置选项，以实现快速的Pod启动时间。请参阅[Amazon VPC CNI](../vpc-cni/index.md)以获取推荐的插件管理最佳实践。

Amazon EKS建议在创建集群时至少指定两个可用区的子网。Amazon VPC CNI从节点子网为Pod分配IP地址。我们强烈建议检查子网中可用的IP地址。在部署EKS集群之前，请考虑[VPC和子网](../subnets/index.md)的建议。

Amazon VPC CNI从附加到节点主ENI的子网中分配ENI和辅助IP地址的预热池。这种VPC CNI的模式称为"[辅助IP模式](../vpc-cni/index.md)"。IP地址的数量(因此也是Pod的数量，即Pod密度)由ENI的数量和每个ENI的IP地址数量(限制)决定，这由实例类型定义。辅助模式是默认模式，适用于较小的实例类型的小型集群。如果您遇到Pod密度挑战，请考虑使用[前缀模式](../prefix-mode/index_linux.md)。您还可以通过为ENI分配前缀来增加节点上Pod可用的IP地址。

Amazon VPC CNI 与 AWS VPC 原生集成，允许用户在构建 Kubernetes 集群时应用现有的 AWS VPC 网络和安全最佳实践。这包括能够使用 VPC 流日志、VPC 路由策略和安全组来实现网络流量隔离。默认情况下，Amazon VPC CNI 将与节点上主 ENI 关联的安全组应用于 Pod。当您希望为 Pod 分配不同的网络规则时，请考虑启用[Pod 安全组](../sgpp/index.md)。

默认情况下，VPC CNI 会从分配给节点主 ENI 的子网中为 Pod 分配 IP 地址。在运行包含数千个工作负载的大型集群时，经常会遇到 IPv4 地址短缺的情况。AWS VPC 允许您通过[分配辅助 CIDR](https://docs.aws.amazon.com/vpc/latest/userguide/configure-your-vpc.html#add-cidr-block-restrictions) 来扩展可用 IP，从而解决 IPv4 CIDR 块耗尽的问题。AWS VPC CNI 允许您为 Pod 使用不同的子网 CIDR 范围。VPC CNI 的这一功能称为[自定义网络](../custom-networking/index.md)。您可以考虑使用自定义网络，将 100.64.0.0/10 和 198.19.0.0/16 CIDR (CG-NAT) 与 EKS 一起使用。这有效地允许您创建一个环境，在该环境中，Pod 不再消耗来自 VPC 的任何 RFC1918 IP 地址。

自定义网络是解决 IPv4 地址耗尽问题的一种选择，但需要操作开销。我们建议使用 IPv6 集群而不是自定义网络来解决此问题。具体来说，如果您已经完全耗尽了 VPC 的所有可用 IPv4 地址空间，我们建议迁移到[IPv6 集群](../ipv6/index.md)。评估您组织支持 IPv6 的计划，并考虑投资 IPv6 是否可能具有更长远的价值。

EKS 支持 IPv6 旨在解决由于 IPv4 地址空间有限而导致的 IP 耗尽问题。为了响应客户遇到的 IPv4 耗尽问题，EKS 优先考虑了 IPv6 单栈 Pod 而非双栈 Pod。也就是说，Pod 可能能够访问 IPv4 资源，但它们不会从 VPC CIDR 范围分配 IPv4 地址。VPC CNI 从 AWS 托管的 VPC IPv6 CIDR 块为 Pod 分配 IPv6 地址。

## 子网计算器

该项目包括一个 [子网计算器 Excel 文档](../subnet-calc/subnet-calc.xlsx)。该计算器文档模拟了在不同 ENI 配置选项(如 `WARM_IP_TARGET` 和 `WARM_ENI_TARGET`)下指定工作负载的 IP 地址消耗情况。该文档包括两个工作表，第一个用于 Warm ENI 模式，第二个用于 Warm IP 模式。有关这些模式的更多信息，请查阅 [VPC CNI 指南](../vpc-cni/index.md)。

输入:
- 子网 CIDR 大小
- Warm ENI 目标 *或* Warm IP 目标
- 实例列表
    - 类型、数量以及每个实例上调度的工作负载 Pod 数量

输出:
- 托管的总 Pod 数量
- 消耗的子网 IP 数量
- 剩余的子网 IP 数量
- 实例级别详细信息
    - 每个实例的 Warm IP/ENI 数量
    - 每个实例的活动 IP/ENI 数量