# 集群升级的最佳实践

本指南向集群管理员展示如何规划和执行他们的 Amazon EKS 升级策略。它还描述了如何升级自管理节点、托管节点组、Karpenter 节点和 Fargate 节点。它不包括有关 EKS Anywhere、自管理 Kubernetes、AWS Outposts 或 AWS Local Zones 的指导。

## 概述

Kubernetes 版本包括控制平面和数据平面。为确保顺利运行，控制平面和数据平面都应运行相同的 [Kubernetes 次要版本，如 1.24](https://kubernetes.io/releases/version-skew-policy/#supported-versions)。虽然 AWS 管理和升级控制平面，但更新数据平面中的工作节点是您的责任。

* **控制平面** — 控制平面的版本由 Kubernetes API 服务器决定。在 Amazon EKS 集群中，AWS 负责管理此组件。可通过 AWS API 发起控制平面升级。
* **数据平面** — 数据平面版本与运行在各个节点上的 Kubelet 版本相关联。同一集群中的节点可能运行不同的版本。您可以通过运行 `kubectl get nodes` 来检查所有节点的版本。

## 升级前

如果您计划在 Amazon EKS 中升级 Kubernetes 版本，在开始升级之前，您应该制定一些重要的策略、工具和程序。

* **了解弃用政策** — 深入了解 [Kubernetes 弃用政策](https://kubernetes.io/docs/reference/using-api/deprecation-policy/)的工作原理。注意任何可能影响您现有应用程序的即将发生的变化。Kubernetes 的较新版本通常会逐步淘汰某些 API 和功能，可能会导致正在运行的应用程序出现问题。
* **查看 Kubernetes 更改日志** — 彻底查看 [Kubernetes 更改日志](https://github.com/kubernetes/kubernetes/tree/master/CHANGELOG)以及 [Amazon EKS Kubernetes 版本](https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html),以了解可能对您的集群产生影响的任何内容，例如可能影响您的工作负载的重大更改。
* **评估集群插件的兼容性** — 当发布新版本或在您将集群更新到新的 Kubernetes 次要版本后，Amazon EKS 不会自动更新插件。查看[更新插件](https://docs.aws.amazon.com/eks/latest/userguide/managing-add-ons.html#updating-an-add-on),以了解任何现有集群插件与您打算升级到的集群版本的兼容性。
* **启用控制平面日志记录** — 启用[控制平面日志记录](https://docs.aws.amazon.com/eks/latest/userguide/control-plane-logs.html),以捕获升级过程中可能出现的日志、错误或问题。考虑查看这些日志以发现任何异常情况。在非生产环境中测试集群升级，或将自动化测试集成到您的持续集成工作流中，以评估版本与您的应用程序、控制器和自定义集成的兼容性。
* **探索 eksctl 进行集群管理** — 考虑使用 [eksctl](https://eksctl.io/) 来管理您的 EKS 集群。它为您提供了[更新控制平面、管理插件和处理工作节点更新](https://eksctl.io/usage/cluster-upgrade/)的能力。
* **选择托管节点组或 EKS on Fargate** — 通过使用 [EKS 托管节点组](https://docs.aws.amazon.com/eks/latest/userguide/managed-node-groups.html)或 [EKS on Fargate](https://docs.aws.amazon.com/eks/latest/userguide/fargate.html),简化并自动化工作节点升级。这些选项可以简化流程并减少手动干预。
* **使用 kubectl Convert 插件** — 利用 [kubectl convert 插件](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/#install-kubectl-convert-plugin)来促进[在不同 API 版本之间转换 Kubernetes 清单文件](https://kubernetes.io/docs/tasks/tools/included/kubectl-convert-overview/)。这可以帮助确保您的配置与新的 Kubernetes 版本保持兼容。

## 保持集群的最新状态

保持与 Kubernetes 更新同步对于确保 Amazon EKS 环境的安全性和效率至关重要，这反映了共享责任模式。通过将这些策略整合到您的操作工作流程中，您就可以保持集群的最新状态、安全性，并充分利用最新功能和改进。策略:

* **支持的版本政策** — 与 Kubernetes 社区保持一致，Amazon EKS 通常提供三个活跃的 Kubernetes 版本，同时每年淘汰一个版本。在版本到达支持结束日期前至少 60 天会发出弃用通知。有关更多详细信息，请参阅 [EKS 版本常见问题解答](https://aws.amazon.com/eks/eks-version-faq/)。
* **自动升级政策** — 我们强烈建议您在 EKS 集群中保持与 Kubernetes 更新同步。Kubernetes 社区支持(包括错误修复和安全补丁)通常会在一年后停止支持旧版本。弃用的版本可能也缺乏漏洞报告，存在潜在风险。如果在版本的生命周期结束前未主动升级，将会触发自动升级，这可能会中断您的工作负载和系统。有关更多信息，请参阅 [EKS 版本支持政策](https://aws.amazon.com/eks/eks-version-support-policy/)。
* **创建升级运行手册** — 建立一个有记录的流程来管理升级。作为主动方法的一部分，开发适合您的升级流程的运行手册和专门工具。这不仅提高了您的准备程度，而且还简化了复杂的过渡。将至少每年升级集群一次作为标准做法。这种做法使您与不断发展的技术保持一致，从而提高环境的效率和安全性。

## 查看 EKS 发布日历

[查看 EKS Kubernetes 发布日历](https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html#kubernetes-release-calendar)以了解新版本的发布时间以及特定版本的支持终止时间。通常情况下，EKS 每年发布三个 Kubernetes 小版本，每个小版本的支持时间约为 14 个月。

此外，请查看上游 [Kubernetes 发布信息](https://kubernetes.io/releases/)。

## 了解共享责任模型如何应用于集群升级

您负责启动控制平面和数据平面的升级。[了解如何启动升级。](https://docs.aws.amazon.com/eks/latest/userguide/update-cluster.html)当您启动集群升级时，AWS 会管理升级集群控制平面。您负责升级数据平面，包括 Fargate pod 和[其他插件。](#upgrade-add-ons-and-components-using-the-kubernetes-api)您必须验证和规划集群上运行的工作负载的升级，以确保在集群升级后它们的可用性和操作不受影响。

## 就地升级集群

EKS 支持就地集群升级策略。这种方式可以保留集群资源，并保持集群配置的一致性(例如 API 端点、OIDC、ENI、负载均衡器)。这对集群用户的干扰较小，并且它将使用集群中现有的工作负载和资源，无需您重新部署工作负载或迁移外部资源(例如 DNS、存储)。

在执行就地集群升级时，请注意一次只能执行一个小版本升级(例如，从 1.24 升级到 1.25)。

这意味着如果您需要更新多个版本，则需要进行一系列顺序升级。规划顺序升级更加复杂，并且存在更高的停机风险。在这种情况下，[评估蓝/绿集群升级策略。](#evaluate-bluegreen-clusters-as-an-alternative-to-in-place-cluster-upgrades)

## 按顺序升级控制平面和数据平面

要升级集群，您需要执行以下操作:

1. [查看Kubernetes和EKS发行说明。](#use-the-eks-documentation-to-create-an-upgrade-checklist)
2. [备份集群。(可选)](#backup-the-cluster-before-upgrading)
3. [识别并修复工作负载中已弃用和已删除的API使用情况。](#identify-and-remediate-removed-api-usage-before-upgrading-the-control-plane)
4. [确保Managed Node Groups(如果使用)与控制平面使用相同的Kubernetes版本。](#track-the-version-skew-of-nodes-ensure-managed-node-groups-are-on-the-same-version-as-the-control-plane-before-upgrading) EKS托管节点组和由EKS Fargate Profiles创建的节点仅支持控制平面和数据平面之间的1个次要版本偏差。
5. [使用AWS控制台或cli升级集群控制平面。](https://docs.aws.amazon.com/eks/latest/userguide/update-cluster.html)
6. [查看插件兼容性。](#upgrade-add-ons-and-components-using-the-kubernetes-api) 根据需要升级您的Kubernetes插件和自定义控制器。
7. [更新kubectl。](https://docs.aws.amazon.com/eks/latest/userguide/install-kubectl.html)
8. [升级集群数据平面。](https://docs.aws.amazon.com/eks/latest/userguide/update-managed-node-group.html) 将节点升级到与升级后的集群相同的Kubernetes次要版本。

## 使用EKS文档创建升级检查表

EKS Kubernetes [版本文档](https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html)包括每个版本的详细更改列表。为每次升级构建检查表。

对于特定的 EKS 版本升级指南，请查看每个版本的重大更改和注意事项文档。

* [EKS 1.27](https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html#kubernetes-1.27)
* [EKS 1.26](https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html#kubernetes-1.26)
* [EKS 1.25](https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html#kubernetes-1.25)
* [EKS 1.24](https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html#kubernetes-1.24)
* [EKS 1.23](https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html#kubernetes-1.23)
* [EKS 1.22](https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html#kubernetes-1.22)

## 使用 Kubernetes API 升级插件和组件

在升级集群之前，您应该了解正在使用的 Kubernetes 组件版本。列出集群组件，并识别直接使用 Kubernetes API 的组件。这包括关键集群组件，如监控和日志代理、集群自动扩缩器、容器存储驱动程序(例如 [EBS CSI](https://docs.aws.amazon.com/eks/latest/userguide/ebs-csi.html)、[EFS CSI](https://docs.aws.amazon.com/eks/latest/userguide/efs-csi.html))、Ingress 控制器以及任何其他直接依赖 Kubernetes API 的工作负载或插件。

!!! 提示
    关键集群组件通常安装在 `*-system` 命名空间中
    
    ```
    kubectl get ns | grep '-system'
    ```

一旦确定了依赖Kubernetes API的组件，请查看它们的文档以了解版本兼容性和升级要求。例如，请参阅[AWS Load Balancer Controller](https://kubernetes-sigs.github.io/aws-load-balancer-controller/v2.4/deploy/installation/)文档以了解版本兼容性。在继续集群升级之前，某些组件可能需要升级或更改配置。需要检查的一些关键组件包括[CoreDNS](https://github.com/coredns/coredns)、[kube-proxy](https://kubernetes.io/docs/concepts/overview/components/#kube-proxy)、[VPC CNI](https://github.com/aws/amazon-vpc-cni-k8s)和存储驱动程序。

集群通常包含许多使用Kubernetes API的工作负载，这些工作负载对于工作负载功能(如入口控制器、持续交付系统和监控工具)是必需的。升级EKS集群时，您还必须升级附加组件和第三方工具，以确保它们兼容。

请参阅以下常见附加组件及其相关升级文档示例:

* **Amazon VPC CNI:** 有关每个集群版本推荐的 Amazon VPC CNI 插件版本，请参阅[更新 Kubernetes 自管理插件 Amazon VPC CNI](https://docs.aws.amazon.com/eks/latest/userguide/managing-vpc-cni.html)。**当作为 Amazon EKS 插件安装时，每次只能升级一个次要版本。**
* **kube-proxy:** 请参阅[更新 Kubernetes 自管理插件 kube-proxy](https://docs.aws.amazon.com/eks/latest/userguide/managing-kube-proxy.html)。
* **CoreDNS:** 请参阅[更新 CoreDNS 自管理插件](https://docs.aws.amazon.com/eks/latest/userguide/managing-coredns.html)。
* **AWS Load Balancer Controller:** AWS Load Balancer Controller 需要与您部署的 EKS 版本兼容。有关更多信息，请参阅[安装指南](https://docs.aws.amazon.com/eks/latest/userguide/aws-load-balancer-controller.html)。
* **Amazon Elastic Block Store (Amazon EBS) 容器存储接口 (CSI) 驱动程序:** 有关安装和升级信息，请参阅[将 Amazon EBS CSI 驱动程序作为 Amazon EKS 插件进行管理](https://docs.aws.amazon.com/eks/latest/userguide/managing-ebs-csi.html)。
* **Amazon Elastic File System (Amazon EFS) 容器存储接口 (CSI) 驱动程序:** 有关安装和升级信息，请参阅[Amazon EFS CSI 驱动程序](https://docs.aws.amazon.com/eks/latest/userguide/efs-csi.html)。
* **Kubernetes Metrics Server:** 有关更多信息，请参阅 GitHub 上的 [metrics-server](https://kubernetes-sigs.github.io/metrics-server/)。
* **Kubernetes Cluster Autoscaler:** 要升级 Kubernetes Cluster Autoscaler 的版本，请更改部署中的镜像版本。Cluster Autoscaler 与 Kubernetes 调度程序紧密耦合。升级集群时，您始终需要升级它。查看 [GitHub 发行版](https://github.com/kubernetes/autoscaler/releases),找到与您的 Kubernetes 次要版本对应的最新发行版地址。
* **Karpenter:** 有关安装和升级信息，请参阅 [Karpenter 文档](https://karpenter.sh/docs/upgrading/)。

## 在升级前验证基本的 EKS 要求

AWS 要求您的账户中具有某些资源才能完成升级过程。如果这些资源不存在，集群就无法升级。控制平面升级需要以下资源:

1. 可用 IP 地址:Amazon EKS 需要您在创建集群时指定的子网中最多有 5 个可用 IP 地址，以便更新集群。如果没有，请在执行版本更新之前更新集群配置，以包含新的集群子网。
2. EKS IAM 角色:控制平面 IAM 角色仍存在于具有必要权限的账户中。
3. 如果您的集群启用了密钥加密，那么请确保集群 IAM 角色具有使用 AWS Key Management Service (AWS KMS) 密钥的权限。

### 验证可用 IP 地址

要更新集群，Amazon EKS 需要您在创建集群时指定的子网中最多有 5 个可用 IP 地址。

要验证您的子网是否有足够的 IP 地址来升级集群，您可以运行以下命令:

```
CLUSTER=<cluster name>
aws ec2 describe-subnets --subnet-ids \
  $(aws eks describe-cluster --name ${CLUSTER} \
  --query 'cluster.resourcesVpcConfig.subnetIds' \
  --output text) \
  --query 'Subnets[*].[SubnetId,AvailabilityZone,AvailableIpAddressCount]' \
  --output table

----------------------------------------------------
|                  DescribeSubnets                 |
+---------------------------+--------------+-------+
|  subnet-067fa8ee8476abbd6 |  us-east-1a  |  8184 |
|  subnet-0056f7403b17d2b43 |  us-east-1b  |  8153 |
|  subnet-09586f8fb3addbc8c |  us-east-1a  |  8120 |
|  subnet-047f3d276a22c6bce |  us-east-1b  |  8184 |
+---------------------------+--------------+-------+
```

可以使用 [VPC CNI Metrics Helper](https://github.com/aws/amazon-vpc-cni-k8s/blob/master/cmd/cni-metrics-helper/README.md) 来创建 VPC 指标的 CloudWatch 控制面板。
如果在集群创建期间最初指定的子网中的 IP 地址不足，Amazon EKS 建议在开始 Kubernetes 版本升级之前使用 "UpdateClusterConfiguration" API 更新集群子网。请验证您将要提供的新子网：

* 属于在集群创建期间选择的同一组可用区。
* 属于在集群创建期间提供的同一个 VPC

如果现有 VPC CIDR 块中的 IP 地址用尽，请考虑关联其他 CIDR 块。AWS 允许将其他 CIDR 块与现有集群 VPC 关联，从而有效扩展您的 IP 地址池。此扩展可通过引入额外的私有 IP 范围 (RFC 1918) 或必要时公共 IP 范围 (非 RFC 1918) 来实现。您必须先添加新的 VPC CIDR 块并允许 VPC 刷新完成，然后 Amazon EKS 才能使用新的 CIDR。之后，您可以根据新设置的 CIDR 块更新子网到 VPC。

### 验证 EKS IAM 角色

要验证 IAM 角色在您的账户中可用并具有正确的 assume role 策略，您可以运行以下命令：

```
CLUSTER=<cluster name>
ROLE_ARN=$(aws eks describe-cluster --name ${CLUSTER} \
  --query 'cluster.roleArn' --output text)
aws iam get-role --role-name ${ROLE_ARN##*/} \
  --query 'Role.AssumeRolePolicyDocument'
  
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "eks.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
```

## 迁移到 EKS 插件

Amazon EKS 会自动为每个集群安装诸如 Amazon VPC CNI 插件、`kube-proxy` 和 CoreDNS 等插件。这些插件可以自行管理，也可以作为 Amazon EKS 插件进行安装。Amazon EKS 插件是使用 EKS API 管理插件的另一种方式。

您可以使用 Amazon EKS 插件通过单个命令更新版本。例如:

```
aws eks update-addon —cluster-name my-cluster —addon-name vpc-cni —addon-version version-number \
--service-account-role-arn arn:aws:iam::111122223333:role/role-name —configuration-values '{}' —resolve-conflicts PRESERVE
```

使用以下命令检查是否有任何 EKS 插件:

```
aws eks list-addons --cluster-name <cluster name>
```

!!! warning
      
    在控制平面升级期间，EKS 插件不会自动升级。您必须启动 EKS 插件更新，并选择所需的版本。

    * 您需要从所有可用版本中选择兼容的版本。[查看有关插件版本兼容性的指南。](#upgrade-add-ons-and-components-using-the-kubernetes-api)
    * Amazon EKS 插件每次只能升级一个次要版本。

[了解有关哪些组件可作为 EKS 插件以及如何开始使用的更多信息。](https://docs.aws.amazon.com/eks/latest/userguide/eks-add-ons.html)

[了解如何为 EKS 插件提供自定义配置。](https://aws.amazon.com/blogs/containers/amazon-eks-add-ons-advanced-configuration/)

## 在升级控制平面之前识别并修复已删除的 API 使用情况

在升级 EKS 控制平面之前，您应该识别已删除 API 的使用情况。为此，我们建议使用可以检查正在运行的集群或静态渲染的 Kubernetes 清单文件的工具。

对静态清单文件运行检查通常更加准确。如果针对实时集群运行，这些工具可能会返回误报。

已弃用的 Kubernetes API 并不意味着该 API 已被移除。您应该查看 [Kubernetes 弃用政策](https://kubernetes.io/docs/reference/using-api/deprecation-policy/)以了解 API 移除对您的工作负载的影响。

### 集群洞见
[集群洞见](https://docs.aws.amazon.com/eks/latest/userguide/cluster-insights.html)是一项功能，可提供有关可能影响将 EKS 集群升级到较新版本的 Kubernetes 的问题的发现结果。这些发现结果由 Amazon EKS 策划和管理，并提供了如何修复它们的建议。通过利用集群洞见，您可以最大限度地减少升级到较新的 Kubernetes 版本所需的工作量。

要查看 EKS 集群的洞见，您可以运行以下命令:
```
aws eks list-insights --region <region-code> --cluster-name <my-cluster>

{
    "insights": [
        {
            "category": "UPGRADE_READINESS", 
            "name": "Deprecated APIs removed in Kubernetes v1.29", 
            "insightStatus": {
                "status": "PASSING", 
                "reason": "No deprecated API usage detected within the last 30 days."
            }, 
            "kubernetesVersion": "1.29", 
            "lastTransitionTime": 1698774710.0, 
            "lastRefreshTime": 1700157422.0, 
            "id": "123e4567-e89b-42d3-a456-579642341238", 
            "description": "Checks for usage of deprecated APIs that are scheduled for removal in Kubernetes v1.29. Upgrading your cluster before migrating to the updated APIs supported by v1.29 could cause application impact."
        }
    ]
}
```

要获得有关收到的洞见的更详细输出，您可以运行以下命令:
```
aws eks describe-insight --region <region-code> --id <insight-id> --cluster-name <my-cluster>
```

您也可以选择在 [Amazon EKS 控制台](https://console.aws.amazon.com/eks/home#/clusters)中查看洞见。在从集群列表中选择您的集群后，洞见发现结果位于 ```Upgrade Insights``` 选项卡下。

如果你发现集群洞察中有 `"status": ERROR`，你必须在执行集群升级之前解决这个问题。运行 `aws eks describe-insight` 命令，它将分享以下修复建议:

受影响的资源:
```
"resources": [
      {
        "insightStatus": {
          "status": "ERROR"
        },
        "kubernetesResourceUri": "/apis/policy/v1beta1/podsecuritypolicies/null"
      }
]
```

已弃用的 API:
```
"deprecationDetails": [
      {
        "usage": "/apis/flowcontrol.apiserver.k8s.io/v1beta2/flowschemas", 
        "replacedWith": "/apis/flowcontrol.apiserver.k8s.io/v1beta3/flowschemas", 
        "stopServingVersion": "1.29", 
        "clientStats": [], 
        "startServingReplacementVersion": "1.26"
      }
]
```

建议采取的行动:
```
"recommendation": "在升级到 Kubernetes v1.26 之前，如果适用，请更新清单和 API 客户端以使用更新的 Kubernetes API。"
```

通过 EKS 控制台或 CLI 利用集群洞察可以加快成功升级 EKS 集群版本的过程。了解更多信息请参考以下资源:
* [官方 EKS 文档](https://docs.aws.amazon.com/eks/latest/userguide/cluster-insights.html)
* [集群洞察发布博客](https://aws.amazon.com/blogs/containers/accelerate-the-testing-and-verification-of-amazon-eks-upgrades-with-upgrade-insights/)。

### Kube-no-trouble

[Kube-no-trouble](https://github.com/doitintl/kube-no-trouble) 是一个开源的命令行工具，其命令为 `kubent`。当你在不带任何参数的情况下运行 `kubent` 时，它将使用你当前的 KubeConfig 上下文并扫描集群，然后打印一份报告，其中包含将被弃用和删除的 API。

```
kubent

4:17PM INF >>> Kube No Trouble `kubent` <<<
4:17PM INF 版本 0.7.0 (git sha d1bb4e5fd6550b533b2013671aa8419d923ee042)
4:17PM INF 初始化收集器并检索数据
4:17PM INF 目标 K8s 版本为 1.24.8-eks-ffeb93d
4:l INF 从收集器 name=Cluster 中检索到 93 个资源
4:17PM INF 从收集器 name="Helm v3" 中检索到 16 个资源
4:17PM INF 已加载规则集 name=custom.rego.tmpl
4:17PM INF 已加载规则集 name=deprecated-1-16.rego
4:17PM INF 已加载规则集 name=deprecated-1-22.rego
4:17PM INF 已加载规则集 name=deprecated-1-25.rego
4:17PM INF 已加载规则集 name=deprecated-1-26.rego
4:17PM INF 已加载规则集 name=deprecated-future.rego
__________________________________________________________________________________________
>>> 在 1.25 中已移除的废弃 API <<<
------------------------------------------------------------------------------------------
KIND                NAMESPACE     NAME             API_VERSION      REPLACE_WITH (SINCE)
PodSecurityPolicy   <undefined>   eks.privileged   policy/v1beta1   <removed> (1.21.0)
```

它也可以用于扫描静态清单文件和 Helm 包。建议在持续集成 (CI) 过程中运行 `kubent`，以便在部署清单之前识别问题。扫描清单比扫描实时集群更加准确。

Kube-no-trouble 提供了一个示例 [Service Account 和 Role](https://github.com/doitintl/kube-no-trouble/blob/master/docs/k8s-sa-and-role-example.yaml)，其中包含扫描集群所需的适当权限。

### Pluto

另一个选择是 [pluto](https://pluto.docs.fairwinds.com/)，它与 `kubent` 类似，因为它支持扫描实时集群、清单文件、Helm 图表，并且有一个可以在 CI 过程中包含的 GitHub Action。

```
pluto detect-all-in-cluster

NAME             KIND                VERSION          REPLACEMENT   REMOVED   DEPRECATED   REPL AVAIL  
eks.privileged   PodSecurityPolicy   policy/v1beta1                 false     true         true
```

### 资源

在升级之前，您应该监控以下内容以验证您的集群不使用已弃用的API：

* 从Kubernetes v1.19开始的指标 `apiserver_requested_deprecated_apis`：

```
kubectl get --raw /metrics | grep apiserver_requested_deprecated_apis

apiserver_requested_deprecated_apis{group="policy",removed_release="1.25",resource="podsecuritypolicies",subresource="",version="v1beta1"} 1
```

* [审计日志](https://docs.aws.amazon.com/eks/latest/userguide/control-plane-logs.html)中带有 `k8s.io/deprecated` 设置为 `true` 的事件：

```
CLUSTER="<cluster_name>"
QUERY_ID=$(aws logs start-query \
 --log-group-name /aws/eks/${CLUSTER}/cluster \
 --start-time $(date -u --date="-30 minutes" "+%s") # or date -v-30M "+%s" on MacOS \
 --end-time $(date "+%s") \
 --query-string 'fields @message | filter `annotations.k8s.io/deprecated`="true"' \
 --query queryId --output text)

echo "Query started (query id: $QUERY_ID), please hold ..." && sleep 5 # give it some time to query

aws logs get-query-results --query-id $QUERY_ID
```

如果使用了已弃用的API，将输出相应的行：

```
{
    "results": [
        [
            {
                "field": "@message",
                "value": "{\"kind\":\"Event\",\"apiVersion\":\"audit.k8s.io/v1\",\"level\":\"Request\",\"auditID\":\"8f7883c6-b3d5-42d7-967a-1121c6f22f01\",\"stage\":\"ResponseComplete\",\"requestURI\":\"/apis/policy/v1beta1/podsecuritypolicies?allowWatchBookmarks=true\\u0026resourceVersion=4131\\u0026timeout=9m19s\\u0026timeoutSeconds=559\\u0026watch=true\",\"verb\":\"watch\",\"user\":{\"username\":\"system:apiserver\",\"uid\":\"8aabfade-da52-47da-83b4-46b16cab30fa\",\"groups\":[\"system:masters\"]},\"sourceIPs\":[\"::1\"],\"userAgent\":\"kube-apiserver/v1.24.16 (linux/amd64) kubernetes/af930c1\",\"objectRef\":{\"resource\":\"podsecuritypolicies\",\"apiGroup\":\"policy\",\"apiVersion\":\"v1beta1\"},\"responseStatus\":{\"metadata\":{},\"code\":200},\"requestReceivedTimestamp\":\"2023-10-04T12:36:11.849075Z\",\"stageTimestamp\":\"2023-10-04T12:45:30.850483Z\",\"annotations\":{\"authorization.k8s.io/decision\":\"allow\",\"authorization.k8s.io/reason\":\"\",\"k8s.io/deprecated\":\"true\",\"k8s.io/removed-release\":\"1.25\"}}"
            },
[...]
```

## 更新Kubernetes工作负载。使用kubectl-convert更新清单

在确定需要更新哪些工作负载和清单之后，您可能需要在清单文件中更改资源类型（例如，从PodSecurityPolicies更改为PodSecurityStandards）。这将需要更新资源规范并根据要替换的资源进行额外研究。

如果资源类型保持不变但需要更新API版本，您可以使用`kubectl-convert`命令自动转换清单文件。例如，将较旧的Deployment转换为`apps/v1`。有关更多信息，请参阅Kubernetes网站上的[安装kubectl转换插件](https://kubernetes.io/docs/tasks/tools/install-kubectl-linux/#install-kubectl-convert-plugin)。

`kubectl-convert -f <file> --output-version <group>/<version>`

## 配置 PodDisruptionBudgets 和 topologySpreadConstraints 以确保在数据平面升级期间工作负载的可用性

确保您的工作负载具有适当的 [PodDisruptionBudgets](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/#pod-disruption-budgets) 和 [topologySpreadConstraints](https://kubernetes.io/docs/concepts/scheduling-eviction/topology-spread-constraints)，以确保在数据平面升级期间工作负载的可用性。并非每个工作负载都需要相同级别的可用性，因此您需要验证工作负载的规模和要求。

确保工作负载分布在多个可用区和多个主机上，并使用拓扑扩展将为工作负载自动迁移到新的数据平面而无事故提供更高的信心水平。

以下是一个工作负载示例，它将始终保持 80% 的副本可用，并跨区域和主机分布副本

```
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: myapp
spec:
  minAvailable: "80%"
  selector:
    matchLabels:
      app: myapp
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
spec:
  replicas: 10
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      containers:
      - image: public.ecr.aws/eks-distro/kubernetes/pause:3.2
        name: myapp
        resources:
          requests:
            cpu: "1"
            memory: 256M
      topologySpreadConstraints:
      - labelSelector:
          matchLabels:
            app: host-zone-spread
        maxSkew: 2
        topologyKey: kubernetes.io/hostname
        whenUnsatisfiable: DoNotSchedule
      - labelSelector:
          matchLabels:
            app: host-zone-spread
        maxSkew: 2
        topologyKey: topology.kubernetes.io/zone
        whenUnsatisfiable: DoNotSchedule
```

AWS Resilience Hub (https://aws.amazon.com/resilience-hub/) 已将 Amazon Elastic Kubernetes Service (Amazon EKS) 作为支持的资源。Resilience Hub 提供了一个单一的位置来定义、验证和跟踪您应用程序的弹性，以避免由软件、基础设施或操作中断导致的不必要的停机时间。

## 使用托管节点组或 Karpenter 来简化数据平面升级

托管节点组和 Karpenter 都可以简化节点升级，但它们采用了不同的方法。

托管节点组自动化节点的供应和生命周期管理。这意味着您可以通过单一操作创建、自动更新或终止节点。

在默认配置中，Karpenter 使用最新的兼容 EKS 优化 AMI 自动创建新节点。当 EKS 发布更新的 EKS 优化 AMI 或集群升级时，Karpenter 将自动开始使用这些镜像。[Karpenter 还实现了节点过期功能来更新节点。](#enable-node-expiry-for-karpenter-managed-nodes)

[Karpenter 可以配置为使用自定义 AMI。](https://karpenter.sh/docs/concepts/nodeclasses/) 如果您在 Karpenter 中使用自定义 AMI，则需要负责 kubelet 的版本。

## 确认与现有节点和控制平面的版本兼容性

在 Amazon EKS 中继续 Kubernetes 升级之前，确保托管节点组、自管理节点和控制平面之间的兼容性至关重要。兼容性由您使用的 Kubernetes 版本决定，并根据不同情况而有所不同。策略:

* **Kubernetes v1.28+** — **从Kubernetes 1.28版本开始，核心组件采用了更加宽松的版本策略。具体来说，Kubernetes API服务器和kubelet之间支持的版本差距已从n-2扩展到n-3。例如，如果您的EKS控制平面版本是1.28,您可以安全地使用1.25及更高版本的kubelet。这种版本差距在[AWS Fargate](https://docs.aws.amazon.com/eks/latest/userguide/fargate.html)、[托管节点组](https://docs.aws.amazon.com/eks/latest/userguide/managed-node-groups.html)和[自管理节点](https://docs.aws.amazon.com/eks/latest/userguide/worker.html)中都受支持。出于安全原因，我们强烈建议您保持[Amazon Machine Image (AMI)](https://docs.aws.amazon.com/eks/latest/userguide/eks-optimized-amis.html)版本的最新状态。较旧的kubelet版本可能存在潜在的常见漏洞和风险(CVE),这可能会超过使用较旧kubelet版本的好处。
* **Kubernetes < v1.28** — 如果您使用的是1.28之前的版本，API服务器和kubelet之间支持的版本差距为n-2。例如，如果您的EKS版本是1.27,您可以使用的最旧kubelet版本是1.25。这种版本差距适用于[AWS Fargate](https://docs.aws.amazon.com/eks/latest/userguide/fargate.html)、[托管节点组](https://docs.aws.amazon.com/eks/latest/userguide/managed-node-groups.html)和[自管理节点](https://docs.aws.amazon.com/eks/latest/userguide/worker.html)。

## 为Karpenter管理的节点启用节点过期

Karpenter实现节点升级的一种方式是使用节点过期的概念。这减少了节点升级所需的规划。当您在供应器中设置 **ttlSecondsUntilExpired** 的值时，这将激活节点过期。节点达到定义的秒数年龄后，它们将被安全排空并删除。即使它们正在使用中也是如此，这允许您用新供应的升级实例替换节点。当节点被替换时，Karpenter使用最新的EKS优化AMI。有关更多信息，请参阅Karpenter网站上的[去供应](https://karpenter.sh/docs/concepts/deprovisioning/#methods)。

Karpenter不会自动为此值添加抖动。为防止过多的工作负载中断，请定义[pod中断预算](https://kubernetes.io/docs/tasks/run-application/configure-pdb/),如Kubernetes文档所示。

如果您在供应器上配置了 **ttlSecondsUntilExpired**,这将应用于与该供应器关联的现有节点。

## 对于Karpenter管理的节点使用漂移功能

[Karpenter的漂移功能](https://karpenter.sh/docs/concepts/deprovisioning/#drift)可以自动将Karpenter供应的节点升级到与EKS控制平面保持同步。当前需要使用[功能门](https://karpenter.sh/docs/concepts/settings/#feature-gates)启用Karpenter漂移。Karpenter的默认配置使用与EKS集群控制平面相同的主要和次要版本的最新EKS优化AMI。

EKS 集群升级完成后，Karpenter 的 Drift 功能会检测到由 Karpenter 供应的节点正在使用先前集群版本的 EKS 优化 AMI，并自动将这些节点隔离、排空和替换。为了支持 Pod 迁移到新节点，请遵循 Kubernetes 最佳实践，设置适当的 Pod [资源配额](https://kubernetes.io/docs/concepts/policy/resource-quotas/)并使用[Pod 中断预算](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/) (PDB)。Karpenter 的解除供应将根据 Pod 资源请求预先启动替换节点，并在解除节点供应时遵守 PDB。

## 使用 eksctl 自动升级自管理节点组

自管理节点组是在您的账户中部署并连接到集群之外的 EC2 实例。这些通常由某种形式的自动化工具部署和管理。要升级自管理节点组，您应参考工具文档。

例如，eksctl 支持[删除和排空自管理节点。](https://eksctl.io/usage/managing-nodegroups/#deleting-and-draining)

一些常见工具包括:

* [eksctl](https://eksctl.io/usage/nodegroup-upgrade/)
* [kOps](https://kops.sigs.k8s.io/operations/updates_and_upgrades/)
* [EKS Blueprints](https://aws-ia.github.io/terraform-aws-eks-blueprints/node-groups/#self-managed-node-groups)

## 在升级前备份集群

Kubernetes 的新版本为您的 Amazon EKS 集群引入了重大变化。升级集群后，您无法降级。

[Velero](https://velero.io/) 是一个社区支持的开源工具，可用于备份现有集群并将备份应用于新集群。

请注意，您只能为EKS当前支持的Kubernetes版本创建新集群。如果您当前集群运行的版本仍然受支持且升级失败，您可以使用原始版本创建新集群并恢复数据平面。请注意，Velero备份不包括AWS资源(包括IAM)。这些资源需要重新创建。

## 在升级控制平面后重新启动Fargate部署

要升级Fargate数据平面节点，您需要重新部署工作负载。您可以使用`-o wide`选项列出所有在fargate节点上运行的pod。任何以`fargate-`开头的节点名称都需要在集群中重新部署。

## 评估蓝/绿集群作为替代集群就地升级的方案

一些客户更喜欢采用蓝/绿升级策略。这可能有好处，但也应该考虑一些缺点。

优点包括:

* 可能一次更改多个EKS版本(例如1.23到1.25)
* 能够切换回旧集群
* 创建新集群，可能由较新的系统管理(例如terraform)
* 工作负载可以单独迁移

一些缺点包括:

* API端点和OIDC更改，需要更新消费者(例如kubectl和CI/CD)
* 在迁移期间需要并行运行2个集群，这可能会很昂贵并限制区域容量
* 如果工作负载相互依赖，需要更多协调才能一起迁移
* 负载均衡器和外部DNS无法轻易跨多个集群

虽然可以采用这种策略，但比就地升级更昂贵，并需要更多时间进行协调和工作负载迁移。在某些情况下可能需要这样做，应该进行仔细规划。

通过高度自动化和声明式系统(如GitOps),这可能会更容易做到。您需要为有状态工作负载采取额外的预防措施，以便将数据备份并迁移到新集群。

查看以下博客文章以了解更多信息：

* [Kubernetes 集群升级：蓝绿部署策略](https://aws.amazon.com/blogs/containers/kubernetes-cluster-upgrade-the-blue-green-deployment-strategy/)
* [无状态 ArgoCD 工作负载的蓝绿或金丝雀 Amazon EKS 集群迁移](https://aws.amazon.com/blogs/containers/blue-green-or-canary-amazon-eks-clusters-migration-for-stateless-argocd-workloads/)

## 跟踪 Kubernetes 项目中计划的重大变更 - 提前思考

不要只关注下一个版本。在新版本的 Kubernetes 发布时进行审查，并识别重大变更。例如，某些应用程序直接使用了 docker API，而对 Docker 的容器运行时接口 (CRI) 支持 (也称为 Dockershim) 在 Kubernetes `1.24` 中被移除。这种变更需要更多时间来准备。

查看您要升级到的版本的所有记录的更改，并注意任何必需的升级步骤。同时也要注意任何特定于 Amazon EKS 托管集群的要求或程序。

* [Kubernetes 更改日志](https://github.com/kubernetes/kubernetes/tree/master/CHANGELOG)

## 关于功能移除的具体指导

### 在 1.25 中移除 Dockershim - 使用 Docker Socket 检测器 (DDS)

1.25 的 EKS 优化 AMI 不再包含对 Dockershim 的支持。如果您依赖于 Dockershim，例如您正在挂载 Docker 套接字，那么在升级工作节点到 1.25 之前，您需要消除这些依赖关系。

在升级到 1.25 之前，找出您对 Docker 套接字有依赖的实例。我们建议使用 [Docker Socket 检测器 (DDS)，一个 kubectl 插件](https://github.com/aws-containers/kubectl-detector-for-docker-socket)。

### 在 1.25 中移除 PodSecurityPolicy - 迁移到 Pod 安全标准或策略即代码解决方案

Kubernetes 1.21 [已弃用 `PodSecurityPolicy`](https://kubernetes.io/blog/2021/04/06/podsecuritypolicy-deprecation-past-present-and-future/)，并在 Kubernetes 1.25 中被移除。如果您在集群中使用 PodSecurityPolicy，那么在升级集群到 1.25 版本之前，您必须迁移到内置的 Kubernetes Pod 安全标准 (PSS) 或策略即代码解决方案，以避免对您的工作负载造成中断。

AWS 在 EKS 文档中发布了[详细的常见问题解答](https://docs.aws.amazon.com/eks/latest/userguide/pod-security-policy-removal-faq.html)。

查看 [Pod 安全标准 (PSS) 和 Pod 安全准入 (PSA)](https://aws.github.io/aws-eks-best-practices/security/docs/pods/#pod-security-standards-pss-and-pod-security-admission-psa) 最佳实践。

查看 Kubernetes 网站上的 [PodSecurityPolicy 弃用博客文章](https://kubernetes.io/blog/2021/04/06/podsecuritypolicy-deprecation-past-present-and-future/)。

### 1.23 版本中内置存储驱动程序的弃用 - 迁移到容器存储接口 (CSI) 驱动程序

容器存储接口 (CSI) 旨在帮助 Kubernetes 取代其现有的内置存储驱动机制。Amazon EBS 容器存储接口 (CSI) 迁移功能在 Amazon EKS `1.23` 及更高版本的集群中默认启用。如果您在 `1.22` 或更早版本的集群上运行 Pod，那么您必须在升级集群到 `1.23` 版本之前安装 [Amazon EBS CSI 驱动程序](https://docs.aws.amazon.com/eks/latest/userguide/ebs-csi.html)，以避免服务中断。

查看 [Amazon EBS CSI 迁移常见问题解答](https://docs.aws.amazon.com/eks/latest/userguide/ebs-csi-migration-faq.html)。

## 其他资源

### ClowdHaus EKS 升级指南

[ClowdHaus EKS 升级指南](https://clowdhaus.github.io/eksup/) 是一个 CLI 工具，用于协助升级 Amazon EKS 集群。它可以分析集群中任何潜在的问题，以便在升级前进行修复。

### GoNoGo

GoNoGo（https://github.com/FairwindsOps/GoNoGo）是一款用于确定集群插件升级置信度的 alpha 阶段工具。