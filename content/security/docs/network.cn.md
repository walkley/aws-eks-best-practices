# 网络安全

网络安全有几个方面。第一个涉及应用规则来限制网络流量在服务之间的流动。第二个涉及在传输过程中对流量进行加密。在 EKS 上实现这些安全措施的机制各不相同，但通常包括以下几项:

## 流量控制

- 网络策略
- 安全组

## 网络加密

- 服务网格
- 容器网络接口 (CNI)
- Ingress 控制器和负载均衡器
- Nitro 实例
- ACM 私有 CA 与 cert-manager

## 网络策略

在 Kubernetes 集群中，默认情况下允许所有 Pod 到 Pod 的通信。虽然这种灵活性可能有助于促进实验，但它并不被认为是安全的。Kubernetes 网络策略为您提供了一种限制 Pod 之间网络流量(通常称为东西向流量)以及 Pod 和外部服务之间网量的机制。Kubernetes 网络策略在 OSI 模型的第 3 层和第 4 层运行。网络策略使用 pod、命名空间选择器和标签来识别源和目标 pod，但也可以包括 IP 地址、端口号、协议或这些的组合。网络策略可以应用于 pod 的入站或出站连接，通常称为入站和出站规则。

通过 Amazon VPC CNI 插件的原生网络策略支持，您可以实施网络策略来保护 Kubernetes 集群中的网络流量。这与上游 Kubernetes 网络策略 API 集成，确保与 Kubernetes 标准兼容和遵从。您可以使用上游 API 支持的不同[标识符](https://kubernetes.io/docs/concepts/services-networking/network-policies/)定义策略。默认情况下，允许所有入站和出站流量到达 Pod。当指定了 policyType Ingress 的网络策略时，允许进入 Pod 的连接仅限于来自 Pod 节点的连接以及入站规则允许的连接。出站规则也是如此。如果定义了多个规则，则在做出决策时会考虑所有规则的并集。因此，评估顺序不会影响策略结果。

!!! attention
    当您首次配置 EKS 集群时，默认情况下不启用 VPC CNI 网络策略功能。请确保部署了受支持的 VPC CNI 插件版本，并在 vpc-cni 插件上将 `ENABLE_NETWORK_POLICY` 标志设置为 `true` 以启用此功能。有关详细说明，请参阅 [Amazon EKS 用户指南](https://docs.aws.amazon.com/eks/latest/userguide/managing-vpc-cni.html)。

## 建议

### 网络策略入门 - 遵循最小特权原则

#### 创建默认拒绝策略

与 RBAC 策略一样，建议在网络策略中遵循最小特权访问原则。首先创建一个拒绝所有策略，限制命名空间内的所有入站和出站流量。

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny
  namespace: default
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
```

![default-deny](./images/default-deny.jpg)

!!! tip
    上图由 [Tufin](https://orca.tufin.io/netpol/) 的网络策略查看器创建。

#### 创建规则以允许 DNS 查询

一旦设置了默认的全部拒绝规则，您就可以开始层层添加其他规则，例如允许 Pod 查询 CoreDNS 进行名称解析的规则。

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns-access
  namespace: default
spec:
  podSelector:
    matchLabels: {}
  policyTypes:
  - Egress
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
      podSelector:
        matchLabels:
          k8s-app: kube-dns
    ports:
    - protocol: UDP
      port: 53
```

![allow-dns-access](./images/allow-dns-access.jpg)

#### 逐步添加规则以选择性地允许命名空间/Pod 之间的流量流动

了解应用程序需求，并根据需要创建细粒度的入站和出站规则。下面的示例显示了如何将端口 80 上的入站流量限制为从 `client-one` 到 `app-one`。这有助于最小化攻击面并降低未经授权访问的风险。

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-ingress-app-one
  namespace: default
spec:
  podSelector:
    matchLabels:
      k8s-app: app-one
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          k8s-app: client-one
    ports:
    - protocol: TCP
      port: 80
```

![allow-ingress-app-one](./images/allow-ingress-app-one.png)

### 监控网络策略执行情况

- **使用网络策略编辑器**
  - [网络策略编辑器](https://networkpolicy.io/)可帮助进行可视化、安全评分，并从网络流日志自动生成
  - 以交互方式构建网络策略
- **审计日志**
  - 定期审查您的 EKS 集群的审计日志
  - 审计日志提供了有关在集群上执行的操作的丰富信息，包括对网络策略的更改
  - 使用此信息跟踪网络策略随时间的变化，并检测任何未经授权或意外的更改
- **自动化测试**
  - 通过创建一个镜像生产环境的测试环境并定期部署试图违反您的网络策略的工作负载来实现自动化测试。
- **监控指标**
  - 配置您的可观测性代理从 VPC CNI 节点代理中抓取 Prometheus 指标，这允许监控代理运行状况和 SDK 错误。
- **定期审核网络策略**
  - 定期审核您的网络策略，以确保它们满足您当前的应用程序要求。随着应用程序的发展，审核可让您有机会删除冗余的入站、出站规则，并确保您的应用程序没有过多权限。
- **使用开放策略代理 (OPA) 确保网络策略存在**
  - 使用如下所示的 OPA 策略，在加入应用程序 Pod 之前确保网络策略始终存在。如果不存在相应的网络策略，此策略将拒绝加入带有标签 `k8s-app: sample-app` 的 k8s Pod。

```javascript
package kubernetes.admission
import data.kubernetes.networkpolicies

deny[msg] {
    input.request.kind.kind == "Pod"
    pod_label_value := {v["k8s-app"] | v := input.request.object.metadata.labels}
    contains_label(pod_label_value, "sample-app")
    np_label_value := {v["k8s-app"] | v := networkpolicies[_].spec.podSelector.matchLabels}
    not contains_label(np_label_value, "sample-app")
    msg:= sprintf("Pod %v 无法创建，因为它缺少关联的网络策略。", [input.request.object.metadata.name])
}
contains_label(arr, val) {
    arr[_] == val
}
```

### 故障排除

#### 监控 vpc-network-policy-controller 和 node-agent 日志

启用 EKS 控制平面控制器管理器日志以诊断网络策略功能。您可以将控制平面日志流式传输到 CloudWatch 日志组，并使用 [CloudWatch 日志洞见](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/AnalyzingLogData.html) 执行高级查询。从日志中，您可以查看哪些 pod 端点对象被解析为网络策略、策略的协调状态，并调试策略是否按预期工作。

此外，Amazon VPC CNI 允许您启用从 EKS 工作节点收集和导出策略执行日志到 [Amazon Cloudwatch](https://aws.amazon.com/cloudwatch/)。启用后，您可以利用 [CloudWatch 容器洞见](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/ContainerInsights.html) 来提供与网络策略相关的使用情况洞见。

Amazon VPC CNI 还附带了一个 SDK，提供了与节点上的 eBPF 程序交互的接口。当 `aws-node` 部署到节点上时，SDK 也会安装。您可以在节点上的 `/opt/cni/bin` 目录下找到已安装的 SDK 二进制文件。在启动时，SDK 提供了检查 eBPF 程序和映射等基本功能的支持。

```shell
sudo /opt/cni/bin/aws-eks-na-cli ebpf progs
```

#### 记录网络流量元数据

[AWS VPC Flow Logs](https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs.html) 捕获了流经 VPC 的流量的元数据，例如源和目标 IP 地址和端口以及已接受/已丢弃的数据包。可以分析此信息以查找 VPC 内资源之间的可疑或异常活动，包括 Pod。但是，由于 Pod 的 IP 地址在替换时会频繁更改，因此 Flow Logs 本身可能不够。Calico Enterprise 通过 Pod 标签和其他元数据扩展了 Flow Logs，从而更容易解码 Pod 之间的流量流。

## 安全组

EKS 使用 [AWS VPC 安全组](https://docs.aws.amazon.com/vpc/latest/userguide/VPC_SecurityGroups.html) (SG) 来控制 Kubernetes 控制平面与集群工作节点之间的流量。安全组还用于控制工作节点与其他 VPC 资源和外部 IP 地址之间的流量。当您配置 EKS 集群(使用 Kubernetes 版本 1.14-eks.3 或更高版本)时，将为您自动创建一个集群安全组。此安全组允许 EKS 控制平面与托管节点组中的节点之间进行无阻碍的通信。为简单起见，建议您将集群 SG 添加到所有节点组，包括非托管节点组。

在 Kubernetes 1.14 版本和 EKS eks.3 版本之前，EKS 控制平面和节点组有单独配置的安全组。控制平面和节点组安全组的最小和建议规则可以在 [https://docs.aws.amazon.com/eks/latest/userguide/sec-group-reqs.html](https://docs.aws.amazon.com/eks/latest/userguide/sec-group-reqs.html) 找到。_控制平面安全组_的最小规则允许来自工作节点安全组的入站 443 端口。这个规则允许 kubelet 与 Kubernetes API 服务器通信。它还包括到工作节点安全组的出站 10250 端口;10250 是 kubelet 监听的端口。同样，_节点组_的最小规则允许来自控制平面安全组的入站 10250 端口和到控制平面安全组的出站 443 端口。最后，还有一个规则允许节点组内节点之间的无限制通信。

如果您需要控制在集群内运行的服务与集群外运行的服务(如 RDS 数据库)之间的通信，请考虑[为 Pod 配置安全组](https://docs.aws.amazon.com/eks/latest/userguide/security-groups-for-pods.html)。使用 Pod 安全组，您可以将**现有**安全组分配给一组 Pod。

!!! warning
    如果您引用了在创建 Pod 之前不存在的安全组，则不会调度这些 Pod。

您可以通过创建 `SecurityGroupPolicy` 对象并指定 `PodSelector` 或 `ServiceAccountSelector` 来控制哪些 Pod 被分配到安全组。将选择器设置为 `{}` 将把 `SecurityGroupPolicy` 中引用的安全组分配给命名空间中的所有 Pod 或命名空间中的所有服务账户。在实施 Pod 安全组之前，请确保您已熟悉所有[注意事项](https://docs.aws.amazon.com/eks/latest/userguide/security-groups-for-pods.html#security-groups-pods-considerations)。

!!! important
    如果为 pod 使用安全组，您**必须**创建允许出站端口 53 到集群安全组的安全组。同样，您**必须**更新集群安全组以接受来自 pod 安全组的入站端口 53 流量。

!!! important
    使用安全组为 pod 时，[安全组的限制](https://docs.aws.amazon.com/vpc/latest/userguide/amazon-vpc-limits.html#vpc-limits-security-groups)仍然适用，因此请谨慎使用。

!!! important
    您**必须**为集群安全组（kubelet）的所有配置的 pod 探测创建入站流量规则。

!!! important
    Pod 的安全组依赖于一个名为 [ENI 汇聚](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/container-instance-eni.html)的功能，该功能旨在提高 EC2 实例的 ENI 密度。当 pod 被分配给一个安全组时，VPC 控制器会将节点组中的一个分支 ENI 与该 pod 关联。如果在调度 pod 时节点组中没有足够的分支 ENI，则该 pod 将保持挂起状态。实例可支持的分支 ENI 数量因实例类型/系列而异。有关更多详细信息，请参阅 [https://docs.aws.amazon.com/eks/latest/userguide/security-groups-for-pods.html#supported-instance-types](https://docs.aws.amazon.com/eks/latest/userguide/security-groups-for-pods.html#supported-instance-types)。

虽然为 Pod 配置安全组提供了一种 AWS 原生的方式来控制集群内外的网络流量而无需策略守护程序的开销，但也有其他选择。例如，Cilium 策略引擎允许您在网络策略中引用 DNS 名称。Calico Enterprise 包括将网络策略映射到 AWS 安全组的选项。如果您已实施了 Istio 等服务网格，您可以使用出口网关来限制网络出口到特定的完全限定域或 IP 地址。有关此选项的更多信息，请阅读关于 [Istio 中的出口流量控制](https://istio.io/blog/2019/egress-traffic-control-in-istio-part-1/)的三部分系列文章。

## 何时使用网络策略与 Pod 安全组?

### 何时使用 Kubernetes 网络策略

- **控制 Pod 到 Pod 的流量**
  - 适用于控制集群内 Pod 之间的网络流量(东西向流量)
- **在 IP 地址或端口级别(OSI 第 3 或第 4 层)控制流量**

### 何时使用 AWS Pod 安全组 (SGP)

- **利用现有 AWS 配置**
  - 如果您已经有复杂的 EC2 安全组集来管理对 AWS 服务的访问，并且您正在将应用程序从 EC2 实例迁移到 EKS，SGP 可能是一个非常好的选择，允许您重用安全组资源并将其应用于您的 Pod。
- **控制对 AWS 服务的访问**
  - 如果您在 EKS 集群中运行的应用程序需要与其他 AWS 服务(RDS 数据库)通信，请使用 SGP 作为有效的机制来控制从 Pod 到 AWS 服务的流量。
- **隔离 Pod 和节点流量**
  - 如果您想完全分离 Pod 流量和其余节点流量，请在 `POD_SECURITY_GROUP_ENFORCING_MODE=strict` 模式下使用 SGP。

### 使用 `Pod 安全组`和`网络策略`的最佳实践

- **分层安全**
  - 使用SGP和kubernetes网络策略的组合来实现分层安全方法
  - 使用SGP来限制对不属于集群的AWS服务的网络级访问，而kubernetes网络策略可以限制集群内pod之间的网络流量
- **最小特权原则**
  - 只允许pod或命名空间之间所需的流量
- **分段您的应用程序**
  - 尽可能通过网络策略对应用程序进行分段，以减少应用程序受到威胁时的影响范围
- **保持策略简单明了**
  - Kubernetes网络策略可以非常细致和复杂，最好保持尽可能简单，以降低配置错误的风险并简化管理开销
- **减少攻击面**
  - 通过限制应用程序的暴露来最小化攻击面

!!! attention
    Pod的安全组提供了两种强制模式:`strict`和`standard`。在EKS集群中同时使用网络策略和Pod安全组功能时，您必须使用`standard`模式。

在网络安全方面，分层方法通常是最有效的解决方案。将kubernetes网络策略和SGP结合使用，可为在EKS中运行的应用程序提供强大的深度防御策略。

## 服务网格策略执行或Kubernetes网络策略

`服务网格`是您可以添加到应用程序中的专用基础设施层。它允许您透明地添加诸如可观察性、流量管理和安全性等功能，而无需将它们添加到您自己的代码中。

服务网格在OSI模型的第7层(应用程序)强制执行策略，而kubernetes网络策略在第3层(网络)和第4层(传输)运行。这个领域有许多产品，如AWS AppMesh、Istio、Linkerd等。

### 何时使用服务网格进行策略执行

- 已在服务网格上有现有投资
- 需要更高级的功能，如流量管理、可观测性和安全性
  - 流量控制、负载均衡、断路器、速率限制、超时等
  - 对服务性能的详细洞察(延迟、错误率、每秒请求数、请求量等)
  - 您希望实施并利用服务网格的安全功能，如mTLS

### 对于简单的用例选择Kubernetes网络策略

- 限制哪些pod可以相互通信
- 与服务网格相比，网络策略需要更少的资源，因此非常适合简单的用例或较小的集群，在这些集群中运行和管理服务网格的开销可能是不合理的

!!! 提示
    网络策略和服务网格也可以一起使用。使用网络策略为您的pod提供基线级别的安全性和隔离，然后使用服务网格添加额外的功能，如流量管理、可观测性和安全性。

## 第三方网络策略引擎

当您有诸如全局网络策略、基于DNS主机名的规则、第7层规则、基于服务帐户的规则以及显式拒绝/日志操作等高级策略要求时，请考虑第三方网络策略引擎。[Calico](https://docs.projectcalico.org/introduction/)是[Tigera](https://tigera.io)的一款开源策略引擎，可与EKS很好地协作。除了实现完整的Kubernetes网络策略功能外，Calico还支持集成Istio后的扩展网络策略，具有更丰富的功能，包括支持第7层规则(如HTTP)。Calico策略可以在命名空间、Pod、服务帐户或全局范围内进行定义。当策略范围为服务帐户时，它会将一组入站/出站规则与该服务帐户关联。通过适当的RBAC规则，您可以防止团队覆盖这些规则，从而允许IT安全专业人员安全地委派命名空间的管理。[Cilium](https://cilium.readthedocs.io/en/stable/intro/)的维护者Isovalent也扩展了网络策略，包括对第7层规则(如HTTP)的部分支持。Cilium还支持DNS主机名，这对于限制与VPC内外运行的Kubernetes服务/Pod和资源之间的流量很有用。相比之下，Calico Enterprise包括一项功能，允许您将Kubernetes网络策略映射到AWS安全组，以及DNS主机名。

您可以在[https://github.com/ahmetb/kubernetes-network-policy-recipes](https://github.com/ahmetb/kubernetes-network-policy-recipes)找到常见的Kubernetes网络策略列表。Calico的类似规则集可在[https://docs.projectcalico.org/security/calico-network-policy](https://docs.projectcalico.org/security/calico-network-policy)获得。

### 迁移到Amazon VPC CNI网络策略引擎

为了保持一致性并避免 Pod 通信行为出现意外，建议在集群中只部署一个网络策略引擎。如果您想从第三方网络策略迁移到 VPC CNI 网络策略引擎，我们建议在启用 VPC CNI 网络策略支持之前，将现有的第三方 NetworkPolicy CRD 转换为 Kubernetes NetworkPolicy 资源。并且，在将转换后的策略应用到生产环境之前，请先在单独的测试集群中测试这些策略。这样可以帮助您识别并解决 Pod 通信行为中可能存在的任何问题或不一致性。

#### 迁移工具

为了协助您的迁移过程，我们开发了一个名为 [K8s Network Policy Migrator](https://github.com/awslabs/k8s-network-policy-migrator) 的工具，可以将您现有的 Calico/Cilium 网络策略 CRD 转换为 Kubernetes 原生网络策略。转换后，您可以直接在运行 VPC CNI 网络策略控制器的新集群上测试转换后的网络策略。该工具旨在帮助您简化迁移过程，确保顺利过渡。

!!! 重要
    迁移工具只会转换与原生 Kubernetes 网络策略 API 兼容的第三方策略。如果您使用了第三方插件提供的高级网络策略功能，迁移工具将跳过并报告这些策略。

请注意，迁移工具目前未得到 AWS VPC CNI 网络策略工程团队的支持，仅以尽力而为的方式提供给客户使用。我们鼓励您利用这个工具来促进迁移过程。如果您在使用该工具时遇到任何问题或错误，请在 [GitHub issue](https://github.com/awslabs/k8s-network-policy-migrator/issues) 中提出。您的反馈对我们非常宝贵，将有助于我们不断改进服务。

### 其他资源

- [Kubernetes & Tigera: 网络策略、安全性和审计](https://youtu.be/lEY2WnRHYpg)
- [Calico Enterprise](https://www.tigera.io/tigera-products/calico-enterprise/)
- [Cilium](https://cilium.readthedocs.io/en/stable/intro/)
- [NetworkPolicy Editor](https://cilium.io/blog/2021/02/10/network-policy-editor) Cilium 提供的交互式策略编辑器
- [Inspektor Gadget advise network-policy gadget](https://www.inspektor-gadget.io/docs/latest/gadgets/advise/network-policy/) 根据网络流量分析建议网络策略

## 传输中的加密

需要符合 PCI、HIPAA 或其他法规的应用程序可能需要在传输过程中加密数据。如今 TLS 是加密网络流量的事实标准。TLS 与其前身 SSL 一样，使用加密协议在网络上提供安全通信。TLS 使用对称加密，其中用于加密数据的密钥是基于会话开始时协商的共享密钥生成的。以下是您可以在 Kubernetes 环境中加密数据的一些方式。

### Nitro 实例

在以下 Nitro 实例类型之间交换的流量默认会自动加密，例如 C5n、G4、I3en、M5dn、M5n、P3dn、R5dn 和 R5n。当存在中间跳转(如传输网关或负载均衡器)时，流量不会被加密。有关传输中的加密以及默认支持网络加密的完整实例类型列表的更多详细信息，请参阅[传输中的加密](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/data-protection.html#encryption-transit)。

### 容器网络接口 (CNI)

[WeaveNet](https://www.weave.works/oss/net/) 可以配置为使用 NaCl 加密自动加密所有 sleeve 流量，并使用 IPsec ESP 加密快速数据路径流量。

### 服务网格

传输中的加密也可以通过服务网格（如 App Mesh、Linkerd v2 和 Istio）来实现。AppMesh 支持使用 X.509 证书或 Envoy 的 Secret Discovery Service (SDS) 进行 [mTLS](https://docs.aws.amazon.com/app-mesh/latest/userguide/mutual-tls.html)。Linkerd 和 Istio 都支持 mTLS。

[aws-app-mesh-examples](https://github.com/aws/aws-app-mesh-examples) GitHub 仓库提供了使用 X.509 证书和 SPIRE 作为 SDS 提供程序为您的 Envoy 容器配置 mTLS 的演练：

- [使用 X.509 证书配置 mTLS](https://github.com/aws/aws-app-mesh-examples/tree/main/walkthroughs/howto-k8s-mtls-file-based)
- [使用 SPIRE (SDS) 配置 TLS](https://github.com/aws/aws-app-mesh-examples/tree/main/walkthroughs/howto-k8s-mtls-sds-based)

App Mesh 还支持使用 [AWS Certificate Manager](https://docs.aws.amazon.com/acm/latest/userguide/acm-overview.html) (ACM) 颁发的私有证书或存储在虚拟节点本地文件系统上的证书进行 [TLS 加密](https://docs.aws.amazon.com/app-mesh/latest/userguide/virtual-node-tls.html)。

[aws-app-mesh-examples](https://github.com/aws/aws-app-mesh-examples) GitHub 仓库提供了使用 ACM 颁发的证书和打包在您的 Envoy 容器中的证书配置 TLS 的演练：

- [使用文件提供的 TLS 证书配置 TLS](https://github.com/aws/aws-app-mesh-examples/tree/master/walkthroughs/howto-tls-file-provided)
- [使用 AWS Certificate Manager 配置 TLS](https://github.com/aws/aws-app-mesh-examples/tree/master/walkthroughs/tls-with-acm)

### 入口控制器和负载均衡器

入口控制器是一种智能路由从集群外部发出的HTTP/S流量到集群内部运行的服务的方式。通常，这些入口前面是第4层负载均衡器，如经典负载均衡器或网络负载均衡器(NLB)。加密流量可以在网络中的不同位置终止，例如在负载均衡器、入口资源或Pod上。您终止SSL连接的方式和位置最终将由您组织的网络安全策略决定。例如，如果您有一个要求端到端加密的策略，您将不得不在Pod上解密流量。这将给您的Pod增加额外的负担，因为它必须花费周期建立初始握手。总的来说，SSL/TLS处理是非常CPU密集型的。因此，如果您有灵活性，请尝试在入口或负载均衡器上执行SSL卸载。

#### 使用AWS Elastic负载均衡器进行加密

[AWS Application Load Balancer](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/introduction.html) (ALB)和[Network Load Balancer](https://docs.aws.amazon.com/elasticloadbalancing/latest/network/introduction.html) (NLB)都支持传输加密(SSL和TLS)。ALB的`alb.ingress.kubernetes.io/certificate-arn`注释允许您指定要添加到ALB的证书。如果省略注释，控制器将尝试通过使用主机字段匹配可用的[AWS Certificate Manager (ACM)](https://docs.aws.amazon.com/acm/latest/userguide/acm-overview.html)证书来向需要它的侦听器添加证书。从EKS v1.15开始，您可以使用如下示例所示的`service.beta.kubernetes.io/aws-load-balancer-ssl-cert`注释与NLB一起使用。

```yaml
apiVersion: v1
kind: Service
metadata:
  name: demo-app
  namespace: default
  labels:
    app: demo-app
  annotations:
     service.beta.kubernetes.io/aws-load-balancer-type: "nlb"
     service.beta.kubernetes.io/aws-load-balancer-ssl-cert: "<certificate ARN>"
     service.beta.kubernetes.io/aws-load-balancer-ssl-ports: "443"
     service.beta.kubernetes.io/aws-load-balancer-backend-protocol: "http"
spec:
  type: LoadBalancer
  ports:
  - port: 443
    targetPort: 80
    protocol: TCP
  selector:
    app: demo-app
---
kind: Deployment
apiVersion: apps/v1
metadata:
  name: nginx
  namespace: default
  labels:
    app: demo-app
spec:
  replicas: 1
  selector:
    matchLabels:
      app: demo-app
  template:
    metadata:
      labels:
        app: demo-app
    spec:
      containers:
        - name: nginx
          image: nginx
          ports:
            - containerPort: 443
              protocol: TCP
            - containerPort: 80
              protocol: TCP
```

以下是SSL/TLS终止的其他示例。

- [以GitOps方式使用Contour和Let's Encrypt保护EKS Ingress](https://aws.amazon.com/blogs/containers/securing-eks-ingress-contour-lets-encrypt-gitops/)
- [如何使用ACM在Amazon EKS工作负载上终止HTTPS流量?](https://aws.amazon.com/premiumsupport/knowledge-center/terminate-https-traffic-eks-acm/)

!!! 注意
    某些Ingress，如AWS LB控制器，使用注解而不是Ingress规范来实现SSL/TLS。

### 使用cert-manager的ACM私有CA

您可以启用 TLS 和 mTLS 来保护 EKS 应用程序工作负载的入口、Pod 和 Pod 之间的通信，使用 ACM 私有证书颁发机构 (CA) 和 [cert-manager](https://cert-manager.io/)（一种流行的 Kubernetes 插件，用于分发、续订和吊销证书）。ACM 私有 CA 是一种高度可用、安全且托管的 CA，无需支付管理自己的 CA 的前期和维护成本。如果您正在使用默认的 Kubernetes 证书颁发机构，那么使用 ACM 私有 CA 可以提高安全性并满足合规性要求。ACM 私有 CA 在 FIPS 140-2 Level 3 硬件安全模块(非常安全)中保护私钥，而默认的 CA 则将密钥编码存储在内存中(不太安全)。集中式 CA 还可以让您更好地控制和审计 Kubernetes 环境内外的私有证书。

#### 用于工作负载之间相互 TLS 的短期 CA 模式

在 EKS 中使用 ACM 私有 CA 进行 mTLS 时，建议使用短期证书和 _short-lived CA mode_。虽然在通用 CA 模式下也可以颁发短期证书，但对于需要频繁颁发新证书的用例而言，使用短期 CA 模式的成本效益更高(比通用模式便宜约 75%)。此外，您还应该尝试将私有证书的有效期与 EKS 集群中 Pod 的生命周期保持一致。[在此了解有关 ACM 私有 CA 及其优势的更多信息](https://aws.amazon.com/certificate-manager/private-certificate-authority/)。

#### ACM 设置说明

首先按照 [ACM Private CA 技术文档](https://docs.aws.amazon.com/acm-pca/latest/userguide/create-CA.html)中提供的步骤创建一个私有 CA。创建好私有 CA 后，使用[常规安装说明](https://cert-manager.io/docs/installation/)安装 cert-manager。安装 cert-manager 后，按照 [GitHub 上的设置说明](https://github.com/cert-manager/aws-privateca-issuer#setup)安装私有 CA Kubernetes cert-manager 插件。该插件允许 cert-manager 从 ACM Private CA 请求私有证书。

现在您已经拥有了一个私有 CA 和一个安装了 cert-manager 和插件的 EKS 集群，是时候设置权限并创建发行者了。更新 EKS 节点角色的 IAM 权限以允许访问 ACM Private CA。将 `<CA_ARN>` 替换为您的私有 CA 的值:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "awspcaissuer",
            "Action": [
                "acm-pca:DescribeCertificateAuthority",
                "acm-pca:GetCertificate",
                "acm-pca:IssueCertificate"
            ],
            "Effect": "Allow",
            "Resource": "<CA_ARN>"
        }
    ]
}
```

也可以使用 [IAM 账户的服务角色或 IRSA](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html)。请参阅下面的附加资源部分以获取完整示例。

通过创建一个名为 cluster-issuer.yaml 的自定义资源定义文件并在其中输入以下内容来在 Amazon EKS 中创建发行者，将 `<CA_ARN>` 和 `<Region>` 信息替换为您的私有 CA 的信息。

```yaml
apiVersion: awspca.cert-manager.io/v1beta1
kind: AWSPCAClusterIssuer
metadata:
          name: demo-test-root-ca
spec:
          arn: <CA_ARN>
          region: <Region>
```

部署您创建的发行者。

```bash
kubectl apply -f cluster-issuer.yaml
```

您的 EKS 集群已配置为从私有 CA 请求证书。您现在可以通过将 `issuerRef` 字段的值更改为上面创建的私有 CA Issuer，使用 cert-manager 的 `Certificate` 资源来颁发证书。有关如何指定和请求证书资源的更多详细信息，请查看 cert-manager 的[证书资源指南](https://cert-manager.io/docs/usage/certificate/)。[在这里查看示例](https://github.com/cert-manager/aws-privateca-issuer/tree/main/config/samples/)。

### 使用 Istio 和 cert-manager 的 ACM 私有 CA

如果您在 EKS 集群中运行 Istio，您可以禁用 Istio 控制平面(特别是 `istiod`)充当根证书颁发机构(CA)的功能，并将 ACM 私有 CA 配置为工作负载之间 mTLS 的根 CA。如果您采用这种方法，请考虑在 ACM 私有 CA 中使用_短期 CA 模式_。有关更多详细信息，请参阅[上一节](#short-lived-ca-mode-for-mutual-tls-between-workloads)和这篇[博客文章](https://aws.amazon.com/blogs/security/how-to-use-aws-private-certificate-authority-short-lived-certificate-mode)。

#### Istio 中的证书签名工作原理(默认)

Kubernetes 中的工作负载使用服务帐户进行标识。如果您没有指定服务帐户，Kubernetes 将自动为您的工作负载分配一个。此外，服务帐户会自动挂载一个关联的令牌。该令牌用于服务帐户，以便工作负载对 Kubernetes API 进行身份验证。服务帐户可能足以作为 Kubernetes 的身份，但 Istio 有自己的身份管理系统和 CA。当工作负载及其 envoy 边车代理启动时，它需要从 Istio 分配一个身份，以被视为可信任并被允许与网格中的其他服务进行通信。

要从 Istio 获取此身份，`istio-agent` 会向 Istio 控制平面发送一个称为证书签名请求（或 CSR）的请求。此 CSR 包含服务帐户令牌，以便在处理之前可以验证工作负载的身份。此验证过程由 `istiod` 处理，它充当注册机构（或 RA）和 CA 的双重角色。RA 充当网关，确保只有经过验证的 CSR 才能通过并发送到 CA。一旦 CSR 通过验证，它将被转发到 CA，CA 随后将颁发包含带有服务帐户的 [SPIFFE](https://spiffe.io/) 身份的证书。此证书称为 SPIFFE 可验证身份文档（或 SVID）。SVID 被分配给请求服务，用于识别目的和加密通信服务之间的传输流量。

![Default flow for Istio Certificate Signing Requests](./images/default-istio-csr-flow.png)

#### 在 Istio 中使用 ACM Private CA 进行证书签名的工作原理

您可以使用名为 Istio 证书签名请求代理（[istio-csr](https://cert-manager.io/docs/projects/istio-csr/)）的 cert-manager 插件将 Istio 与 ACM Private CA 集成。此代理允许使用 cert manager 发行者（在本例中为 ACM Private CA）来保护 Istio 工作负载和控制平面组件。_istio-csr_ 代理公开与 _istiod_ 在默认配置中提供的验证传入 CSR 的相同服务。不同之处在于，在验证之后，它会将请求转换为 cert manager 支持的资源（即与外部 CA 发行者的集成）。

每当有来自工作负载的 CSR 时，它都会被转发到 _istio-csr_,后者将从 ACM Private CA 请求证书。_istio-csr_ 与 ACM Private CA 之间的通信是由 [AWS Private CA 发行者插件](https://github.com/cert-manager/aws-privateca-issuer)启用的。Cert manager 使用此插件从 ACM Private CA 请求 TLS 证书。发行者插件将与 ACM Private CA 服务通信，为工作负载请求签名证书。一旦证书被签名，它将被返回给 _istio-csr_,后者将读取签名的请求，并将其返回给发起 CSR 的工作负载。

![Istio 证书签名请求与 istio-csr 的流程](./images/istio-csr-with-acm-private-ca.png)

#### 使用私有 CA 设置 Istio 的说明

1. 首先按照[本节](#acm-private-ca-with-cert-manager)中的相同[设置说明]完成以下操作:
2. 创建私有 CA
3. 安装 cert-manager
4. 安装发行者插件
5. 设置权限并创建发行者。发行者代表 CA，用于签署 `istiod` 和网格工作负载证书。它将与 ACM Private CA 通信。
6. 创建 `istio-system` 命名空间。这是将部署 `istiod 证书`和其他 Istio 资源的地方。
7. 安装配置了 AWS Private CA 发行者插件的 Istio CSR。您可以保留工作负载的证书签名请求，以验证它们是否获得批准和签名(`preserveCertificateRequests=true`)。

```bash
helm install -n cert-manager cert-manager-istio-csr jetstack/cert-manager-istio-csr \
--set "app.certmanager.issuer.group=awspca.cert-manager.io" \
--set "app.certmanager.issuer.kind=AWSPCAClusterIssuer" \
--set "app.certmanager.issuer.name=<您创建的发行者的名称>" \
--set "app.certmanager.preserveCertificateRequests=true" \
--set "app.server.maxCertificateDuration=48h" \
--set "app.tls.certificateDuration=24h" \
--set "app.tls.istiodCertificateDuration=24h" \
--set "app.tls.rootCAFile=/var/run/secrets/istio-csr/ca.pem" \
--set "volumeMounts[0].name=root-ca" \
--set "volumeMounts[0].mountPath=/var/run/secrets/istio-csr" \
--set "volumes[0].name=root-ca" \
--set "volumes[0].secret.secretName=istio-root-ca"
```

8. 使用自定义配置安装 Istio，将 `cert-manager istio-csr` 作为网格的证书提供程序替换 `istiod`。此过程可以使用 [Istio Operator](https://tetrate.io/blog/what-is-istio-operator/) 进行。

```yaml
apiVersion: install.istio.io/v1alpha1
kind: IstioOperator
metadata:
  name: istio
  namespace: istio-system
spec:
  profile: "demo"
  hub: gcr.io/istio-release
  values:
  global:
    # 将证书提供程序更改为 istio 代理的 cert-manager istio 代理
    caAddress: cert-manager-istio-csr.cert-manager.svc:443
  components:
    pilot:
      k8s:
        env:
          # 禁用 istiod CA 服务器功能
        - name: ENABLE_CA_SERVER
          value: "false"
        overlays:
        - apiVersion: apps/v1
          kind: Deployment
          name: istiod
          patches:

# 从Secret挂载istiod服务和webhook证书
              - path: spec.template.spec.containers.[name:discovery].args[7]
                value: "--tlsCertFile=/etc/cert-manager/tls/tls.crt"
              - path: spec.template.spec.containers.[name:discovery].args[8]
                value: "--tlsKeyFile=/etc/cert-manager/tls/tls.key"
              - path: spec.template.spec.containers.[name:discovery].args[9]
                value: "--caCertFile=/etc/cert-manager/ca/root-cert.pem"

              - path: spec.template.spec.containers.[name:discovery].volumeMounts[6]
                value:
                  name: cert-manager
                  mountPath: "/etc/cert-manager/tls"
                  readOnly: true
              - path: spec.template.spec.containers.[name:discovery].volumeMounts[7]
                value:
                  name: ca-root-cert
                  mountPath: "/etc/cert-manager/ca"
                  readOnly: true

              - path: spec.template.spec.volumes[6]
                value:
                  name: cert-manager
                  secret:
                    secretName: istiod-tls
              - path: spec.template.spec.volumes[7]
                value:
                  name: ca-root-cert
                  configMap:
                    defaultMode: 420
                    name: istio-ca-root-cert
    ```

9. 部署您创建的上述自定义资源。

    ```bash
    istioctl operator init
    kubectl apply -f istio-custom-config.yaml
    ```

10. 现在您可以在EKS集群中部署工作负载到网格，并[强制执行mTLS](https://istio.io/latest/docs/reference/config/security/peer_authentication/)。

![Istio证书签名请求](./images/istio-csr-requests.png)

## 工具和资源

- [Amazon EKS 安全沉浸式研讨会 - 网络安全](https://catalog.workshops.aws/eks-security-immersionday/en-US/6-network-security)
- [如何在 EKS 上实现 cert-manager 和 ACM Private CA 插件以启用 TLS](https://aws.amazon.com/blogs/security/tls-enabled-kubernetes-clusters-with-acm-private-ca-and-amazon-eks-2/)。
- [使用新的 AWS 负载均衡器控制器和 ACM Private CA 在 Amazon EKS 上设置端到端 TLS 加密](https://aws.amazon.com/blogs/containers/setting-up-end-to-end-tls-encryption-on-amazon-eks-with-the-new-aws-load-balancer-controller/)。
- [GitHub 上的 Private CA Kubernetes cert-manager 插件](https://github.com/cert-manager/aws-privateca-issuer)。
- [Private CA Kubernetes cert-manager 插件用户指南](https://docs.aws.amazon.com/acm-pca/latest/userguide/PcaKubernetes.html)。
- [如何使用 AWS Private Certificate Authority 短期证书模式](https://aws.amazon.com/blogs/security/how-to-use-aws-private-certificate-authority-short-lived-certificate-mode)
- [在 Kubernetes 中使用 ksniff 和 Wireshark 验证服务网格 TLS](https://itnext.io/verifying-service-mesh-tls-in-kubernetes-using-ksniff-and-wireshark-2e993b26bf95)
- [ksniff](https://github.com/eldadru/ksniff)
- [egress-operator](https://github.com/monzo/egress-operator) 一个操作员和 DNS 插件，用于控制从集群出口的流量，无需协议检查
- [SUSE 的 NeuVector](https://www.suse.com/neuvector/) 开源、零信任容器安全平台，提供策略网络规则、数据丢失防护 (DLP)、Web 应用程序防火墙 (WAF) 和网络威胁签名。