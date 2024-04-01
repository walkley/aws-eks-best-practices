# 每个 Pod 的安全组

AWS 安全组充当 EC2 实例的虚拟防火墙，用于控制入站和出站流量。默认情况下，Amazon VPC CNI 将使用与节点上主 ENI 关联的安全组。更具体地说，与实例关联的每个 ENI 都将具有相同的 EC2 安全组。因此，节点上的每个 Pod 都共享该节点的相同安全组。

如下图所示，运行在工作节点上的所有应用程序 Pod 都将能够访问 RDS 数据库服务(考虑到 RDS 入站允许节点安全组)。安全组过于粗粒度，因为它们适用于在节点上运行的所有 Pod。Pod 的安全组为工作负载提供了网络隔离，这是良好的深度防御策略的重要组成部分。

![节点与安全组连接到 RDS 的插图](./image.png)

使用 Pod 的安全组，您可以通过在共享计算资源上运行具有不同网络安全要求的应用程序来提高计算效率。可以在 EC2 安全组中定义多种类型的安全规则，例如 Pod 到 Pod 和 Pod 到外部 AWS 服务，并使用 Kubernetes 原生 API 将其应用于工作负载。下图显示了在 Pod 级别应用的安全组，以及它们如何简化您的应用程序部署和节点架构。Pod 现在可以访问 Amazon RDS 数据库。

![Pod 和节点与不同安全组连接到 RDS 的插图](./image-2.png)

您可以通过为 VPC CNI 设置 `ENABLE_POD_ENI=true` 来为 Pod 启用安全组。启用后，在控制平面上运行的 "[VPC 资源控制器](https://github.com/aws/amazon-vpc-resource-controller-k8s)"(由 EKS 管理)会创建并将一个名为 "aws-k8s-trunk-eni" 的主干接口附加到节点。主干接口充当附加到实例的标准网络接口。要管理主干接口，您必须将 `AmazonEKSVPCResourceController` 托管策略添加到与您的 Amazon EKS 集群相关联的集群角色。

控制器还会创建名为 "aws-k8s-branch-eni" 的分支接口并将其与主干接口关联。Pod 使用 [SecurityGroupPolicy](https://github.com/aws/amazon-vpc-resource-controller-k8s/blob/master/config/crd/bases/vpcresources.k8s.aws_securitygrouppolicies.yaml) 自定义资源分配安全组，并与分支接口关联。由于安全组是与网络接口关联的，因此我们现在可以在这些额外的网络接口上调度需要特定安全组的 Pod。请查看 [EKS 用户指南中关于 Pod 的安全组部分](https://docs.aws.amazon.com/eks/latest/userguide/security-groups-for-pods.html)，包括部署先决条件。

![illustration of worker subnet with security groups associated with ENIs](./image-3.png)

分支接口容量是对现有实例类型的辅助 IP 地址限制的*累加*。使用安全组的 Pod 不计入 max-pods 公式中，当您为 Pod 使用安全组时，您需要考虑提高 max-pods 值或接受运行比节点实际支持的 Pod 更少的情况。

m5.large 可以有多达 9 个分支网络接口，并且可以为其标准网络接口分配多达 27 个辅助 IP 地址。如下例所示，m5.large 的默认 max-pods 为 29，EKS 会将使用安全组的 Pod 计入最大 Pod 数量。请参阅 [EKS 用户指南](https://docs.aws.amazon.com/eks/latest/userguide/cni-increase-ip-addresses.html) 了解如何更改节点的 max-pods。

当将 Pod 的安全组与 [自定义网络](https://docs.aws.amazon.com/eks/latest/userguide/cni-custom-network.html) 结合使用时，将使用 Pod 的安全组中定义的安全组，而不是在 ENIConfig 中指定的安全组。因此，启用自定义网络时，请仔细评估使用每个 Pod 的安全组时的安全组排序。

## 建议

### 对于存活探针禁用 TCP 提前解复用

如果您使用存活或就绪探针，您还需要禁用 TCP 提前解复用，以便 kubelet 可以通过 TCP 连接到分支网络接口上的 Pod。这仅在严格模式下需要。要执行此操作，请运行以下命令:

```
kubectl edit daemonset aws-node -n kube-system
```

在 `initContainer` 部分，将 `DISABLE_TCP_EARLY_DEMUX` 的值更改为 `true`。

### 使用 Pod 的安全组来利用现有的 AWS 配置投资。

安全组可以更轻松地限制对 VPC 资源(如 RDS 数据库或 EC2 实例)的网络访问。每个 Pod 使用安全组的一个明显优势是可以重用现有的 AWS 安全组资源。
如果您使用安全组作为网络防火墙来限制对 AWS 服务的访问，我们建议将安全组应用于使用分支 ENI 的 Pod。如果您要将应用从 EC2 实例转移到 EKS，并使用安全组限制对其他 AWS 服务的访问，请考虑为 Pod 使用安全组。

### 配置 Pod 安全组强制模式

Amazon VPC CNI插件版本1.11添加了一个名为`POD_SECURITY_GROUP_ENFORCING_MODE`("执行模式")的新设置。执行模式控制应用于pod的安全组以及是否启用源NAT。您可以将执行模式指定为strict或standard。Strict是默认值，反映了之前将`ENABLE_POD_ENI`设置为`true`时VPC CNI的行为。

在Strict模式下，只有分支ENI安全组会被强制执行。源NAT也会被禁用。

在Standard模式下，与主ENI和分支ENI(与pod关联)关联的安全组都会被应用。网络流量必须符合这两个安全组的规则。

!!! 警告
    任何模式更改只会影响新启动的Pod。现有Pod将使用创建Pod时配置的模式。如果客户想要更改流量行为，他们需要重新启动现有Pod以应用新的安全组。

### 执行模式:使用Strict模式隔离pod和节点流量:

默认情况下，Pod的安全组设置为"strict模式"。如果您必须完全将Pod流量与节点的其他流量分离，请使用此设置。在strict模式下，源NAT会被关闭，因此可以使用分支ENI的出站安全组。

!!! 警告
    当启用strict模式时，来自pod的所有出站流量都将离开节点并进入VPC网络。同一节点上pod之间的流量将通过VPC。这会增加VPC流量，并限制基于节点的功能。NodeLocal DNSCache不支持strict模式。

### 执行模式:在以下情况下使用Standard模式

**容器中的Pod可见客户端源IP**

如果需要在 Pod 中保留客户端源 IP 可见性，请考虑将 `POD_SECURITY_GROUP_ENFORCING_MODE` 设置为 `standard`。Kubernetes 服务支持 externalTrafficPolicy=local 以保留客户端源 IP (默认类型为 cluster)。您现在可以在标准模式下使用实例目标运行类型为 NodePort 和 LoadBalancer 的 Kubernetes 服务，并将 externalTrafficPolicy 设置为 Local。`Local` 可以保留客户端源 IP，并避免 LoadBalancer 和 NodePort 类型服务的第二次跳转。

**部署 NodeLocal DNSCache**

在为 Pod 使用安全组时，请配置标准模式以支持使用 [NodeLocal DNSCache](https://kubernetes.io/docs/tasks/administer-cluster/nodelocaldns/) 的 Pod。NodeLocal DNSCache 通过在集群节点上以 DaemonSet 的形式运行 DNS 缓存代理来提高集群 DNS 性能。这将有助于具有最高 DNS QPS 需求的 Pod 查询本地 kube-dns/CoreDNS,从而利用本地缓存来提高延迟。

由于所有网络流量(即使是到节点的流量)都进入 VPC，因此严格模式不支持 NodeLocal DNSCache。

**支持 Kubernetes 网络策略**

在使用与 Pod 关联的安全组时，我们建议使用标准强制模式来使用网络策略。

我们强烈建议对 Pod 使用安全组来限制对不属于集群的 AWS 服务的网络级访问。考虑使用网络策略来限制集群内 Pod 之间的网络流量，通常称为东西向流量。

### 识别与 Pod 安全组的不兼容性

基于 Windows 和非 nitro 实例不支持 Pod 安全组。要利用 Pod 安全组，实例必须标记为 isTrunkingEnabled。如果您的 Pod 不依赖于 VPC 内或外部的任何 AWS 服务，请使用网络策略而不是安全组来管理 Pod 之间的访问。

### 使用 Pod 安全组高效控制对 AWS 服务的流量

如果在 EKS 集群中运行的应用程序需要与 VPC 内的另一资源通信(例如 RDS 数据库)，则可考虑为 Pod 使用安全组。虽然有一些策略引擎允许您指定 CIDR 或 DNS 名称，但当与在 VPC 内具有端点的 AWS 服务进行通信时，它们并不是最佳选择。

相比之下，Kubernetes [网络策略](https://kubernetes.io/docs/concepts/services-networking/network-policies/)提供了一种控制集群内外入站和出站流量的机制。如果您的应用程序对其他 AWS 服务的依赖有限，则应考虑使用 Kubernetes 网络策略。您可以配置基于 CIDR 范围指定出站规则的网络策略，以限制对 AWS 服务的访问，而不是使用 AWS 原生语义(如安全组)。您可以使用 Kubernetes 网络策略来控制 Pod 之间(通常称为东西向流量)以及 Pod 和外部服务之间的网络流量。Kubernetes 网络策略在 OSI 第 3 层和第 4 层实现。

Amazon EKS 允许您使用网络策略引擎，如 [Calico](https://projectcalico.docs.tigera.io/getting-started/kubernetes/managed-public-cloud/eks) 和 [Cilium](https://docs.cilium.io/en/stable/intro/)。默认情况下，不会安装网络策略引擎。请查看相应的安装指南，了解如何设置的说明。有关如何使用网络策略的更多信息，请参阅 [EKS 安全最佳实践](https://aws.github.io/aws-eks-best-practices/security/docs/network/#network-policy)。DNS 主机名功能可在网络策略引擎的企业版本中使用，这对于控制 Kubernetes 服务/Pod 与 AWS 之外运行的资源之间的流量可能很有用。此外，对于默认不支持安全组的 AWS 服务，您也可以考虑 DNS 主机名支持。

### 使用 AWS Loadbalancer Controller 标记单个安全组

当为一个Pod分配了多个安全组时，Amazon EKS建议使用标签 [`kubernetes.io/cluster/$name`](http://kubernetes.io/cluster/$name) 来标记一个共享或拥有的单个安全组。该标签允许AWS负载均衡器控制器更新安全组规则以将流量路由到Pod。如果只为一个Pod分配了一个安全组，则标记是可选的。安全组中设置的权限是累加的，因此标记单个安全组就足以让负载均衡器控制器定位和协调规则。这也有助于遵守安全组定义的[默认配额](https://docs.aws.amazon.com/vpc/latest/userguide/amazon-vpc-limits.html#vpc-limits-security-groups)。

### 为出站流量配置NAT

对于分配了安全组的Pod的出站流量，源NAT是禁用的。对于需要访问互联网的使用安全组的Pod，请在配置了NAT网关或实例的私有子网上启动工作节点，并在CNI中启用[外部SNAT](https://docs.aws.amazon.com/eks/latest/userguide/external-snat.html)。

```
kubectl set env daemonset -n kube-system aws-node AWS_VPC_K8S_CNI_EXTERNALSNAT=true
```

### 将使用安全组的Pod部署到私有子网

分配了安全组的Pod必须在部署到私有子网的节点上运行。请注意，部署到公共子网的分配了安全组的Pod将无法访问互联网。

### 验证Pod规范文件中的*terminationGracePeriodSeconds*

确保您的Pod规范文件中的`terminationGracePeriodSeconds`不为零(默认为30秒)。这对于Amazon VPC CNI从工作节点删除Pod网络至关重要。当设置为零时，CNI插件不会从主机删除Pod网络，并且分支ENI无法有效清理。

### 在Fargate上使用安全组来保护Pod

针对在 Fargate 上运行的 Pod，其安全组的工作方式与在 EC2 工作节点上运行的 Pod 非常相似。例如，在将 SecurityGroupPolicy 与 Fargate Pod 关联之前，您必须先创建安全组。默认情况下，当您没有明确为 Fargate Pod 分配 SecurityGroupPolicy 时，[集群安全组](https://docs.aws.amazon.com/eks/latest/userguide/sec-group-reqs.html)会被分配给所有 Fargate Pod。为简单起见，您可能希望将集群安全组添加到 Fargate Pod 的 SecurityGroupPolicy 中，否则您将不得不向安全组添加最小安全组规则。您可以使用 describe-cluster API 查找集群安全组。

```bash
 aws eks describe-cluster --name CLUSTER_NAME --query 'cluster.resourcesVpcConfig.clusterSecurityGroupId'
```

```bash
cat >my-fargate-sg-policy.yaml <<EOF
apiVersion: vpcresources.k8s.aws/v1beta1
kind: SecurityGroupPolicy
metadata:
  name: my-fargate-sg-policy
  namespace: my-fargate-namespace
spec:
  podSelector: 
    matchLabels:
      role: my-fargate-role
  securityGroups:
    groupIds:
      - cluster_security_group_id
      - my_fargate_pod_security_group_id
EOF
```

最小安全组规则列在[此处](https://docs.aws.amazon.com/eks/latest/userguide/sec-group-reqs.html)。这些规则允许 Fargate Pod 与集群内服务（如 kube-apiserver、kubelet 和 CoreDNS）进行通信。您还需要添加规则以允许与 Fargate Pod 进行入站和出站连接。这将允许您的 Pod 与 VPC 中的其他 Pod 或资源进行通信。此外，您必须包含规则以允许 Fargate 从 Amazon ECR 或其他容器注册表（如 DockerHub）拉取容器镜像。有关更多信息，请参阅 [AWS 通用参考](https://docs.aws.amazon.com/general/latest/gr/aws-ip-ranges.html)中的 AWS IP 地址范围。

您可以使用以下命令查找应用于 Fargate Pod 的安全组。

```bash
kubectl get pod FARGATE_POD -o jsonpath='{.metadata.annotations.vpc\.amazonaws\.com/pod-eni}{"\n"}'
```

记下上述命令输出的 eniId。

```bash
aws ec2 describe-network-interfaces --network-interface-ids ENI_ID --query 'NetworkInterfaces[*].Groups[*]'
```

必须删除并重新创建现有的 Fargate pod，以应用新的安全组。例如，以下命令将启动 example-app 的部署。要更新特定的 pod，您可以在下面的命令中更改命名空间和部署名称。

```bash
kubectl rollout restart -n example-ns deployment example-pod
```