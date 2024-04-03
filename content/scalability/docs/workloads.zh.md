# 工作负载

工作负载会影响集群可扩展的规模。大量使用Kubernetes API的工作负载将限制单个集群中可以拥有的总工作负载量，但您可以更改一些默认值来帮助减轻负载。

Kubernetes集群中的工作负载可以访问与Kubernetes API集成的功能(例如Secret和ServiceAccount),但并非始终需要这些功能，如果不使用它们应该将其禁用。限制工作负载对Kubernetes控制平面的访问和依赖性将增加集群中可以运行的工作负载数量，并通过删除对工作负载的不必要访问和实施最小特权实践来提高集群的安全性。请阅读[安全最佳实践](https://aws.github.io/aws-eks-best-practices/security/docs/)以了解更多信息。

## 为Pod网络使用IPv6

您无法将VPC从IPv4过渡到IPv6，因此在配置集群之前启用IPv6很重要。如果在VPC中启用了IPv6，并不意味着您必须使用它，如果您的Pod和服务使用IPv6，您仍然可以将流量路由到和从IPv4地址。请参阅[EKS网络最佳实践](https://aws.github.io/aws-eks-best-practices/networking/index/)了解更多信息。

在集群中[使用IPv6](https://docs.aws.amazon.com/eks/latest/userguide/cni-ipv6.html)可以避免一些最常见的集群和工作负载扩展限制。IPv6避免了IP地址耗尽的情况，即由于没有可用的IP地址而无法创建Pod和节点。它还通过减少每个节点的ENI附加数量来提高每个节点的性能，因为Pod可以更快地获得IP地址。您可以通过在VPC CNI中使用[IPv4前缀模式](https://aws.github.io/aws-eks-best-practices/networking/prefix-mode/)来实现类似的节点性能，但您仍然需要确保VPC中有足够的IP地址可用。

## 限制每个命名空间中的服务数量

每个命名空间中[服务的最大数量为5，000，集群中服务的最大数量为10，000](https://github.com/kubernetes/community/blob/master/sig-scalability/configs-and-limits/thresholds.md)。为了帮助组织工作负载和服务、提高性能以及避免命名空间作用域资源的级联影响，我们建议将每个命名空间中的服务数量限制在500以内。

随着集群中服务总数的增加，kube-proxy在每个节点上创建的IP表规则数量也会增加。生成数千条IP表规则并通过这些规则路由数据包会对节点的性能产生影响，并增加网络延迟。

创建Kubernetes命名空间以包含单个应用程序环境，只要每个命名空间中的服务数量低于500。这将使服务发现的规模足够小，避免服务发现限制，并且还可以帮助您避免服务命名冲突。应用程序环境(如dev、test、prod)应使用单独的EKS集群，而不是命名空间。

## 了解弹性负载均衡器配额

在创建服务时，请考虑将使用何种类型的负载均衡(例如网络负载均衡器(NLB)或应用程序负载均衡器(ALB))。每种负载均衡器类型提供不同的功能，并且具有[不同的配额](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-limits.html)。某些默认配额可以调整，但也有一些配额上限无法更改。要查看您的账户配额和使用情况，请在AWS控制台中查看[服务配额仪表板](http://console.aws.amazon.com/servicequotas)。

例如，默认ALB目标数是1000。如果您的服务有超过1000个端点，您需要增加配额或将服务分散到多个ALB上，或使用Kubernetes Ingress。默认NLB目标数是3000，但每个可用区限制为500个目标。如果您的集群为NLB服务运行了超过500个Pod，您需要使用多个可用区或请求增加配额限制。

使用与服务耦合的负载均衡器的替代方案是使用[Ingress控制器](https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/)。AWS Load Balancer控制器可以为Ingress资源创建ALB，但您可以考虑在集群中运行专用控制器。集群内Ingress控制器允许您通过在集群内运行反向代理来从单个负载均衡器公开多个Kubernetes服务。控制器具有不同的功能，例如支持[网关API](https://gateway-api.sigs.k8s.io/)，这可能会带来好处，具体取决于您的工作负载的数量和大小。

## 使用Route 53、Global Accelerator或CloudFront

要使用多个负载均衡器的服务作为单个端点可用，您需要使用[Amazon CloudFront](https://aws.amazon.com/cloudfront/)、[AWS Global Accelerator](https://aws.amazon.com/global-accelerator/)或[Amazon Route 53](https://aws.amazon.com/route53/)将所有负载均衡器公开为单个面向客户的端点。每个选项都有不同的优点，可以根据您的需求单独或一起使用。

Route 53 可以在一个通用名称下公开多个负载均衡器，并根据分配的权重将流量发送到每个负载均衡器。您可以在[文档](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/resource-record-sets-values-weighted.html#rrsets-values-weighted-weight)中阅读有关 DNS 权重的更多信息，您也可以在 [AWS 负载均衡器控制器文档](https://kubernetes-sigs.github.io/aws-load-balancer-controller/v2.4/guide/integrations/external_dns/#usage)中阅读如何使用 [Kubernetes 外部 DNS 控制器](https://github.com/kubernetes-sigs/external-dns)实现它们。

Global Accelerator 可以根据请求 IP 地址将工作负载路由到最近的区域。对于部署到多个区域的工作负载，这可能很有用，但它不会改善对单个区域中单个集群的路由。将 Route 53 与 Global Accelerator 结合使用具有额外的好处，例如健康检查和自动故障转移(如果某个可用区不可用)。您可以在[这篇博客文章](https://aws.amazon.com/blogs/containers/operating-a-multi-regional-stateless-application-using-amazon-eks/)中看到使用 Global Accelerator 和 Route 53 的示例。

CloudFront 可以与 Route 53 和 Global Accelerator 一起使用，也可以单独使用来路由流量到多个目的地。CloudFront 缓存从源服务器提供的资产，这可能会减少带宽需求，具体取决于您提供的内容。

## 使用 EndpointSlices 而不是 Endpoints

在发现与服务标签匹配的 pod 时，您应该使用 [EndpointSlices](https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/) 而不是 Endpoints。Endpoints 是一种在小规模上公开服务的简单方式，但大型服务自动扩展或更新会导致大量 Kubernetes 控制平面流量。EndpointSlices 具有自动分组功能，可以实现诸如拓扑感知提示之类的功能。

并非所有控制器都默认使用 EndpointSlices。您应该验证控制器设置并在需要时启用它。对于 [AWS 负载均衡器控制器](https://kubernetes-sigs.github.io/aws-load-balancer-controller/v2.4/deploy/configurations/#controller-command-line-flags)，您应该启用 `--enable-endpoint-slices` 可选标志以使用 EndpointSlices。

## 如果可能的话，使用不可变和外部 Secret

kubelet 会缓存该节点上 Pod 所使用卷中的 Secret 的当前密钥和值。kubelet 会对 Secret 设置监视以检测变化。随着集群规模的扩大，越来越多的监视会对 API 服务器的性能产生负面影响。

减少对 Secret 的监视数量有两种策略:

* 对于不需要访问 Kubernetes 资源的应用程序，您可以通过设置 automountServiceAccountToken: false 来禁用自动挂载服务帐户 Secret
* 如果您的应用程序的 Secret 是静态的，并且将来不会被修改，请将 [Secret 标记为不可变](https://kubernetes.io/docs/concepts/configuration/secret/#secret-immutable)。kubelet 不会对不可变的 Secret 维护 API 监视。

要禁止自动将服务帐户挂载到 Pod，您可以在工作负载中使用以下设置。如果特定工作负载需要服务帐户，您可以覆盖这些设置。

```
apiVersion: v1
kind: ServiceAccount
metadata:
  name: app
automountServiceAccountToken: true
```

在集群中的 Secret 数量超过 10，000 的限制之前监控它。您可以使用以下命令查看集群中 Secret 的总数。您应该通过集群监控工具监控此限制。

```
kubectl get secrets -A | wc -l
```

您应该设置监控以在达到此限制之前提醒集群管理员。考虑使用外部密钥管理选项，如 [AWS Key Management Service (AWS KMS)](https://aws.amazon.com/kms/) 或 [Hashicorp Vault](https://www.vaultproject.io/) 与 [Secrets Store CSI 驱动程序](https://secrets-store-csi-driver.sigs.k8s.io/)。

## 限制部署历史记录

由于集群中仍在跟踪旧对象，因此在创建、更新或删除 Pod 时可能会很慢。您可以减少 [deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#clean-up-policy) 的 `revisionHistoryLimit` 以清理旧的 ReplicaSet，从而降低 Kubernetes 控制器管理器跟踪的总对象数量。Deployment 的默认历史记录限制为 10。

如果您的集群通过 CronJob 或其他机制创建了大量作业对象，您应该使用 [`ttlSecondsAfterFinished` 设置](https://kubernetes.io/docs/concepts/workloads/controllers/ttlafterfinished/) 自动清理集群中的旧 Pod。这将在指定的时间后从作业历史记录中删除已成功执行的作业。

## 默认禁用 enableServiceLinks

当 Pod 在节点上运行时，kubelet 会为每个活动服务添加一组环境变量。Linux 进程对其环境的大小有最大限制，如果您的命名空间中有太多服务，则可能会达到此限制。每个命名空间中的服务数量不应超过 5，000 个。之后，服务环境变量的数量会超出 shell 限制，导致 Pod 在启动时崩溃。

Pod 不应使用服务环境变量进行服务发现还有其他原因。环境变量名称冲突、泄露服务名称和总环境大小就是其中几个原因。您应该使用 CoreDNS 来发现服务端点。

## 限制每个资源的动态准入 Webhook 数量

动态准入Webhook包括[准入Webhook和变更Webhook](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/)。它们是Kubernetes控制平面之外的API端点，在将资源发送到Kubernetes API时会按顺序调用。每个Webhook的默认超时时间为10秒，如果您有多个Webhook或任何一个超时，都会增加API请求所需的时间。

请确保您的Webhook高度可用——尤其是在AZ事件期间——并且正确设置了[failurePolicy](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/#failure-policy)以拒绝资源或忽略失败。不需要调用Webhook时，请允许--dry-run kubectl命令绕过Webhook。

```
apiVersion: admission.k8s.io/v1
kind: AdmissionReview
request:
  dryRun: False
```

变更Webhook可以连续修改资源。如果您有5个变更Webhook并部署了50个资源，etcd将存储每个资源的所有版本，直到压缩运行——每5分钟——以删除已修改资源的旧版本。在这种情况下，当etcd删除被取代的资源时，将从etcd中删除200个资源版本，并且根据资源的大小，可能会在主机上占用大量空间，直到每15分钟进行一次碎片整理。

这种碎片整理可能会导致etcd暂停，从而对Kubernetes API和控制器产生其他影响。您应该避免频繁修改大型资源或快速连续修改数百个资源。