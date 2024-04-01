# Amazon VPC CNI

<iframe width="560" height="315" src="https://www.youtube.com/embed/RBE3yk2UlYA" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen></iframe>

Amazon EKS通过[Amazon VPC Container Network Interface](https://github.com/aws/amazon-vpc-cni-k8s)[(VPC CNI)](https://github.com/aws/amazon-vpc-cni-k8s)插件实现集群网络。CNI插件允许Kubernetes Pod拥有与VPC网络相同的IP地址。更具体地说，Pod内的所有容器共享一个网络命名空间，并且它们可以使用本地端口相互通信。

Amazon VPC CNI有两个组件:

* CNI二进制文件，用于设置Pod网络以启用Pod到Pod的通信。CNI二进制文件运行在节点根文件系统上，并由kubelet在向节点添加新Pod或从节点删除现有Pod时调用。
* ipamd,一个长期运行的节点本地IP地址管理(IPAM)守护进程，负责:
  * 管理节点上的ENI，以及
  * 维护一个可用IP地址或前缀的热池

当创建实例时，EC2会创建并附加与主子网关联的主ENI。主子网可以是公共的或私有的。在hostNetwork模式下运行的Pod使用分配给节点主ENI的主IP地址，并与主机共享相同的网络命名空间。

CNI插件管理节点上的[弹性网络接口(ENI)](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-eni.html)。当节点被供应时，CNI插件会自动从节点的子网中为主ENI分配一个IP或前缀池。这个池被称为*热池*,其大小由节点的实例类型决定。根据CNI设置，一个插槽可能是一个IP地址或一个前缀。当ENI上的一个插槽被分配后，CNI可能会将带有热池插槽的额外ENI附加到节点上。这些额外的ENI被称为辅助ENI。每个ENI只能支持一定数量的插槽，这取决于实例类型。CNI根据所需的插槽数量(通常对应于Pod数量)为实例附加更多的ENI。这个过程一直持续到节点无法支持额外的ENI为止。CNI还会预分配"热"ENI和插槽，以加快Pod启动速度。请注意，每种实例类型可以附加的ENI数量都有上限。这是Pod密度(每个节点的Pod数量)的一个约束，除了计算资源之外。

![流程图说明了何时需要新的ENI委派前缀](./image.png)

网络接口的最大数量和您可以使用的最大插槽数量因EC2实例类型而异。由于每个Pod在一个插槽上消耗一个IP地址，因此您可以在特定EC2实例上运行的Pod数量取决于可以附加到它的ENI数量以及每个ENI支持的插槽数量。我们建议按照EKS用户指南设置每个节点的最大Pod数量，以避免耗尽实例的CPU和内存资源。使用`hostNetwork`的Pod不包括在此计算中。您可以考虑使用一个名为[max-pod-calculator.sh](https://github.com/awslabs/amazon-eks-ami/blob/master/files/max-pods-calculator.sh)的脚本来计算EKS为给定实例类型推荐的最大Pod数。

## 概述

辅助 IP 模式是 VPC CNI 的默认模式。本指南概述了启用辅助 IP 模式时 VPC CNI 的一般行为。ipamd (IP 地址分配)的功能可能因 VPC CNI 的配置设置而有所不同，例如[前缀模式](../prefix-mode/index_linux.md)、[每个 Pod 的安全组](../sgpp/index.md)和[自定义网络](../custom-networking/index.md)。

Amazon VPC CNI 作为名为 aws-node 的 Kubernetes Daemonset 部署在工作节点上。当配置工作节点时，它会附加一个默认 ENI，称为主 ENI。CNI 从附加到节点主 ENI 的子网中分配一个热 ENI 池和辅助 IP 地址。默认情况下，ipamd 会尝试为节点分配一个额外的 ENI。当调度单个 Pod 并从主 ENI 分配辅助 IP 地址时，IPAMD 会分配额外的 ENI。这个"热"ENI 可以实现更快的 Pod 网络。当辅助 IP 地址池用尽时，CNI 会添加另一个 ENI 以分配更多地址。

ENI 和 IP 地址池的数量通过名为 [WARM_ENI_TARGET、WARM_IP_TARGET、MINIMUM_IP_TARGET](https://github.com/aws/amazon-vpc-cni-k8s/blob/master/docs/eni-and-ip-target.md) 的环境变量进行配置。aws-node Daemonset 会定期检查是否附加了足够数量的 ENI。当满足所有 `WARM_ENI_TARGET` 或 `WARM_IP_TARGET` 和 `MINIMUM_IP_TARGET` 条件时，就表示附加了足够数量的 ENI。如果附加的 ENI 数量不足，CNI 将向 EC2 发出 API 调用以附加更多 ENI，直到达到 `MAX_ENI` 限制。

* `WARM_ENI_TARGET` - 整数，值>0表示启用了该要求
  * 要维护的热ENI的数量。当ENI作为辅助ENI附加到节点但未被任何Pod使用时，它就是"热"的。更具体地说，ENI的任何IP地址都未与任何Pod关联。
  * 示例:考虑一个实例有2个ENI，每个ENI支持5个IP地址。WARM_ENI_TARGET设置为1。如果正好有5个IP地址与该实例关联，CNI将维护2个附加到该实例的ENI。第一个ENI正在使用中，其所有5个可能的IP地址都已使用。第二个ENI是"热"的，其5个IP地址都在池中。如果在该实例上启动另一个Pod，将需要第6个IP地址。CNI将从第二个ENI的5个IP地址池中为该第6个Pod分配一个IP地址。第二个ENI现在正在使用中，不再处于"热"状态。CNI将分配第三个ENI，以维护至少1个热ENI。

!!! 注意
    热ENI仍然会从您的VPC的CIDR中消耗IP地址。IP地址在与工作负载(如Pod)关联之前是"未使用"或"热"的。

* `WARM_IP_TARGET`，整数，值>0表示启用该要求
  * 要维护的热IP地址数量。热IP位于活动附加的ENI上，但尚未分配给Pod。换句话说，可用的热IP数量是可以分配给Pod而无需额外ENI的IP数量。
  * 示例:考虑一个具有1个ENI的实例，每个ENI支持20个IP地址。WARM_IP_TARGET设置为5。WARM_ENI_TARGET设置为0。只有在需要第16个IP地址时，CNI才会附加第二个ENI，从子网CIDR中消耗20个可能的地址。
* `MINIMUM_IP_TARGET`，整数，值>0表示启用该要求
  * 在任何时候都要分配的最小IP地址数量。这通常用于在实例启动时预先分配多个ENI。
  * 示例:考虑一个新启动的实例。它有1个ENI，每个ENI支持10个IP地址。MINIMUM_IP_TARGET设置为100。ENI立即附加9个更多的ENI，总共100个地址。这不受任何WARM_IP_TARGET或WARM_ENI_TARGET值的影响。

该项目包括一个[子网计算器Excel文档](../subnet-calc/subnet-calc.xlsx)。该计算器文档模拟了在不同ENI配置选项(如`WARM_IP_TARGET`和`WARM_ENI_TARGET`)下指定工作负载的IP地址消耗。

![分配IP地址给Pod所涉及的组件示意图](./image-2.png)

当Kubelet收到添加Pod请求时，CNI二进制文件会查询ipamd以获取可用的IP地址，然后ipamd将其提供给Pod。CNI二进制文件连接主机和Pod网络。

默认情况下，部署在节点上的Pod被分配到与主ENI相同的安全组。或者，也可以为Pod配置不同的安全组。

![分配IP地址给Pod所涉及的组件的第二个示意图](./image-3.png)

随着IP地址池的耗尽，插件会自动为实例附加另一个弹性网络接口，并为该接口分配另一组辅助IP地址。这个过程会一直持续，直到节点无法再支持额外的弹性网络接口为止。

![分配Pod IP地址所涉及组件的第三个示意图](./image-4.png)

当删除一个Pod时，VPC CNI会将该Pod的IP地址放入30秒的冷却缓存中。冷却缓存中的IP不会被分配给新的Pod。冷却期结束后，VPC CNI会将Pod IP移回暖池。冷却期可防止Pod IP地址过早被回收，并允许集群中所有节点上的kube-proxy完成更新iptables规则。当IP或ENI的数量超过暖池设置的数量时，ipamd插件会将IP和ENI返回给VPC。

如上所述，在辅助IP模式下，每个Pod都会从附加到实例的ENI之一获得一个辅助私有IP地址。由于每个Pod都使用一个IP地址，因此您可以在特定EC2实例上运行的Pod数量取决于可以附加到该实例的ENI数量以及它支持的IP地址数量。VPC CNI会检查[限制](https://github.com/aws/amazon-vpc-resource-controller-k8s/blob/master/pkg/aws/vpc/limits.go)文件，以了解每种实例类型允许的ENI和IP地址数量。

您可以使用以下公式来确定可以在节点上部署的最大Pod数量:

`(实例类型的网络接口数量 × (每个网络接口的IP地址数量 - 1)) + 2`

+2表示需要主机网络的Pod，如kube-proxy和VPC CNI。Amazon EKS要求kube-proxy和VPC CNI在每个节点上运行，这些要求已被考虑在最大Pod值中。如果您想运行额外的主机网络Pod，请考虑更新最大Pod值。

+2 表示使用主机网络的 Kubernetes Pod，如 kube-proxy 和 VPC CNI。Amazon EKS 要求在每个节点上运行 kube-proxy 和 VPC CNI，并将其计入 max-pods。如果您计划运行更多主机网络 Pod，请考虑更新 max-pods。您可以在启动模板中将 `--kubelet-extra-args "—max-pods=110"` 指定为用户数据。

例如，在具有 3 个 c5.large 节点(3 个 ENI 和每个 ENI 最多 10 个 IP)的集群中，当集群启动并有 2 个 CoreDNS pod 时，CNI 将消耗 49 个 IP 地址并将它们保留在热池中。热池可以在部署应用程序时加快 Pod 启动速度。

节点 1(带 CoreDNS pod):2 个 ENI，分配 20 个 IP

节点 2(带 CoreDNS pod):2 个 ENI，分配 20 个 IP  

节点 3(无 Pod):1 个 ENI，分配 10 个 IP。

请记住，通常作为 DaemonSet 运行的基础设施 Pod 也会占用 max-pod 计数。这些可能包括:

* CoreDNS
* Amazon Elastic Load Balancer
* metrics-server 的操作 Pod

我们建议您通过组合这些 Pod 的容量来规划基础设施。有关每种实例类型支持的最大 Pod 数量的列表，请参阅 GitHub 上的 [eni-max-Pods.txt](https://github.com/awslabs/amazon-eks-ami/blob/master/files/eni-max-pods.txt)。

![illustration of multiple ENIs attached to a node](./image-5.png)

## 建议

### 部署 VPC CNI 托管插件

当您配置集群时，Amazon EKS 会自动安装 VPC CNI。不过，Amazon EKS 支持托管插件，使集群能够与底层的 AWS 计算、存储和网络资源进行交互。我们强烈建议您使用包括 VPC CNI 在内的托管插件部署集群。

Amazon EKS 托管插件为 Amazon EKS 集群提供 VPC CNI 安装和管理。Amazon EKS 插件包含最新的安全补丁、错误修复，并经过 AWS 验证可与 Amazon EKS 一起使用。VPC CNI 插件使您能够持续确保 Amazon EKS 集群的安全性和稳定性，并减少安装、配置和更新插件所需的工作量。此外，托管插件可通过 Amazon EKS API、AWS 管理控制台、AWS CLI 和 eksctl 进行添加、更新或删除。

您可以使用 `kubectl get` 命令和 `--show-managed-fields` 标志查找 VPC CNI 的托管字段。

```
kubectl get daemonset aws-node --show-managed-fields -n kube-system -o yaml
```

托管插件通过每 15 分钟自动覆盖配置来防止配置偏移。这意味着在创建插件后通过 Kubernetes API 对托管插件所做的任何更改都将被自动漂移防止过程覆盖，并在更新插件过程中设置为默认值。

EKS 管理的字段列在 managedFields 下，manager 为 EKS。EKS 管理的字段包括服务帐户、镜像、镜像 URL、活跃探测、就绪探测、标签、卷和卷挂载。

!!! Info
最常用的字段如 WARM_ENI_TARGET、WARM_IP_TARGET 和 MINIMUM_IP_TARGET 不受管理，在更新插件时不会被协调。对这些字段的更改将在更新插件时得到保留。

我们建议在更新生产集群之前，先在非生产集群中针对特定配置测试插件行为。此外，请按照 EKS 用户指南中的[插件](https://docs.aws.amazon.com/eks/latest/userguide/eks-add-ons.html)配置步骤进行操作。

#### 迁移到托管插件

您将管理自管理 VPC CNI 的版本兼容性并更新安全补丁。要更新自管理插件，您必须使用 Kubernetes API 和 [EKS 用户指南](https://docs.aws.amazon.com/eks/latest/userguide/managing-vpc-cni.html#updating-vpc-cni-add-on)中概述的说明。我们建议将现有 EKS 集群迁移到托管插件，并在迁移之前强烈建议备份您当前的 CNI 设置。要配置托管插件，您可以使用 Amazon EKS API、AWS 管理控制台或 AWS 命令行界面。

```
kubectl apply view-last-applied daemonset aws-node -n kube-system > aws-k8s-cni-old.yaml
```

如果字段列为托管，Amazon EKS 将用默认设置替换 CNI 配置设置。我们建议不要修改托管字段。插件不会协调配置字段，如 *warm* 环境变量和 CNI 模式。在您迁移到托管 CNI 时，Pod 和应用程序将继续运行。

#### 在更新之前备份 CNI 设置

VPC CNI 在客户数据平面(节点)上运行，因此当发布新版本或您[更新集群](https://docs.aws.amazon.com/eks/latest/userguide/update-cluster.html)到新的 Kubernetes 次要版本后，Amazon EKS 不会自动更新插件(托管和自管理)。要为现有集群更新插件，您必须通过 update-addon API 或在 EKS 控制台中单击"立即更新"链接来触发更新。如果您已部署自管理插件，请按照[更新自管理 VPC CNI 插件](https://docs.aws.amazon.com/eks/latest/userguide/managing-vpc-cni.html#updating-vpc-cni-add-on)中提到的步骤操作。

我们强烈建议您一次只更新一个次要版本。例如，如果您当前的次要版本是 `1.9`,并且您想要更新到 `1.11`,您应该首先更新到 `1.10` 的最新补丁版本，然后再更新到 `1.11` 的最新补丁版本。

在更新 Amazon VPC CNI 之前，请检查 aws-node Daemonset。备份现有设置。如果使用托管插件，请确认您没有更新任何可能被 Amazon EKS 覆盖的设置。我们建议在自动化工作流程中添加更新后的钩子，或在插件更新后手动应用。

```
kubectl apply view-last-applied daemonset aws-node -n kube-system > aws-k8s-cni-old.yaml
```

对于自管理插件，请将备份与 GitHub 上的 `releases` 进行比较，查看可用版本并熟悉您要更新到的版本中的更改。我们建议使用 Helm 管理自管理插件，并利用值文件应用设置。任何涉及 Daemonset 删除的更新操作都将导致应用程序停机，必须避免。

### 了解安全上下文

我们强烈建议您了解为有效管理 VPC CNI 而配置的安全上下文。Amazon VPC CNI 有两个组件:CNI 二进制文件和 ipamd (aws-node) Daemonset。CNI 作为二进制文件在节点上运行，可访问节点根文件系统，并具有特权访问权限，因为它在节点级别处理 iptables。当 Pod 被添加或删除时，kubelet 会调用 CNI 二进制文件。

aws-node Daemonset 是一个长期运行的进程，负责节点级别的 IP 地址管理。aws-node 在 `hostNetwork` 模式下运行，允许访问回环设备和同一节点上其他 Pod 的网络活动。aws-node init-container 以特权模式运行并挂载 CRI 套接字，允许 Daemonset 监控节点上运行的 Pod 的 IP 使用情况。Amazon EKS 正在努力消除 aws-node init 容器的特权要求。此外，aws-node 需要更新 NAT 条目并加载 iptables 模块，因此以 NET_ADMIN 权限运行。

Amazon EKS建议部署aws-node manifest中定义的安全策略，用于Pod的IP管理和网络设置。请考虑更新到最新版本的VPC CNI。此外，如果您有特定的安全要求，请考虑在[GitHub issue](https://github.com/aws/amazon-vpc-cni-k8s/issues)中提出。

### 为CNI使用单独的IAM角色

AWS VPC CNI需要AWS Identity and Access Management (IAM)权限。在使用IAM角色之前，需要设置CNI策略。您可以使用[`AmazonEKS_CNI_Policy`](https://console.aws.amazon.com/iam/home#/policies/arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy%24jsonEditor)，这是一个适用于IPv4集群的AWS托管策略。AmazonEKS CNI托管策略仅具有IPv4集群的权限。您必须为IPv6集群创建一个单独的IAM策略，其中包含[此处](https://docs.aws.amazon.com/eks/latest/userguide/cni-iam-role.html#cni-iam-role-create-ipv6-policy)列出的权限。

默认情况下，VPC CNI继承[Amazon EKS节点IAM角色](https://docs.aws.amazon.com/eks/latest/userguide/create-node-role.html)（托管和自管理节点组）。

强烈建议为Amazon VPC CNI配置一个单独的IAM角色，并分配相关策略。否则，Amazon VPC CNI的Pod将获得分配给节点IAM角色的权限，并可以访问分配给节点的实例配置文件。

VPC CNI插件会创建并配置一个名为aws-node的服务账户。默认情况下，该服务账户绑定到附加了Amazon EKS CNI策略的Amazon EKS节点IAM角色。要使用单独的IAM角色，我们建议您[创建一个新的服务账户](https://docs.aws.amazon.com/eks/latest/userguide/cni-iam-role.html#cni-iam-role-create-role),并附加Amazon EKS CNI策略。要使用新的服务账户，您必须[重新部署CNI pod](https://docs.aws.amazon.com/eks/latest/userguide/cni-iam-role.html#cni-iam-role-redeploy-pods)。在创建新集群时，请考虑为VPC CNI托管插件指定`--service-account-role-arn`。请确保从Amazon EKS节点角色中删除IPv4和IPv6的Amazon EKS CNI策略。

建议您[阻止访问实例元数据](https://aws.github.io/aws-eks-best-practices/security/docs/iam/#restrict-access-to-the-instance-profile-assigned-to-the-worker-node),以最小化安全漏洞的影响范围。

### 处理活性/就绪探针故障

我们建议增加EKS 1.20及更高版本集群的活性和就绪探针超时值(默认`timeoutSeconds: 10`),以防止探针故障导致您的应用程序的Pod陷入containerCreating状态。这个问题在数据密集型和批处理集群中已被发现。高CPU使用会导致aws-node探针健康检查失败，进而导致Pod的CPU请求无法满足。除了修改探针超时值外，还要确保为aws-node正确配置CPU资源请求(默认`CPU: 25m`)。我们不建议在节点没有问题的情况下更新这些设置。

我们强烈建议您在与Amazon EKS支持人员联系时，在节点上运行sudo `bash /opt/cni/bin/aws-cni-support.sh`。该脚本将帮助评估kubelet日志和节点上的内存利用率。请考虑在Amazon EKS工作节点上安装SSM Agent以运行该脚本。

### 在非EKS优化AMI实例上配置IPTables转发策略

如果您使用自定义 AMI，请确保在 [kubelet.service](https://github.com/awslabs/amazon-eks-ami/blob/master/files/kubelet.service#L8) 下将 iptables 转发策略设置为 ACCEPT。许多系统将 iptables 转发策略设置为 DROP。您可以使用 [HashiCorp Packer](https://packer.io/intro/why.html) 和包含来自 [Amazon EKS AMI 存储库在 AWS GitHub](https://github.com/awslabs/amazon-eks-ami) 上的资源和配置脚本的构建规范来构建自定义 AMI。您可以更新 [kubelet.service](https://github.com/awslabs/amazon-eks-ami/blob/master/files/kubelet.service#L8) 并按照[此处](https://aws.amazon.com/premiumsupport/knowledge-center/eks-custom-linux-ami/)指定的说明创建自定义 AMI。

### 定期升级 CNI 版本

VPC CNI 向后兼容。最新版本适用于所有 Amazon EKS 支持的 Kubernetes 版本。此外，VPC CNI 作为 EKS 插件提供(参见上面的"部署 VPC CNI 托管插件")。虽然 EKS 插件协调升级插件，但它不会自动升级像 CNI 这样在数据平面上运行的插件。您有责任在托管和自管理工作节点升级后按照升级 VPC CNI 插件。