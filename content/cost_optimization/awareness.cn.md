# 支出意识

支出意识是了解谁、在哪里以及是什么导致了您的 EKS 集群中的支出。获得这些数据的准确情况将有助于提高您对支出的意识，并突出需要补救的领域。

## 建议
### 使用成本资源管理器

[AWS 成本资源管理器](https://aws.amazon.com/aws-cost-management/aws-cost-explorer/)提供了一个易于使用的界面，让您可以随时了解和管理您的 AWS 成本和使用情况。您可以使用成本资源管理器中可用的过滤器，在各个级别分析成本和使用数据。

#### EKS 控制平面和 EKS Fargate 成本

如下图所示，我们可以使用过滤器查询 EKS 控制平面和 Fargate Pod 产生的成本:

![成本资源管理器 - EKS 控制平面](../images/eks-controlplane-costexplorer.png)

如下图所示，我们可以使用过滤器查询 EKS 中跨区域 Fargate Pod 产生的总成本 - 包括每 CPU vCPU 小时和 GB 小时:

![成本资源管理器 - EKS Fargate](../images/eks-fargate-costexplorer.png)

#### 资源标记

Amazon EKS 支持[为 Amazon EKS 集群添加 AWS 标记](https://docs.aws.amazon.com/eks/latest/userguide/eks-using-tags.html)。这使得控制对 EKS API 的访问以管理集群变得很容易。添加到 EKS 集群的标记仅特定于 AWS EKS 集群资源，它们不会传播到集群使用的其他 AWS 资源，如 EC2 实例或负载均衡器。目前，通过 AWS API、控制台和 SDK 支持为所有新的和现有的 EKS 集群添加集群标记。

AWS Fargate 是一项为容器提供按需、适当调整的计算容量的技术。在您可以在集群中调度 Fargate 上的 Pod 之前，您必须定义至少一个 Fargate 配置文件，指定在启动时哪些 Pod 应该使用 Fargate。

为 EKS 集群添加和列出标签：
```
$ aws eks tag-resource --resource-arn arn:aws:eks:us-west-2:xxx:cluster/ekscluster1 --tags team=devops,env=staging,bu=cio,costcenter=1234
$ aws eks list-tags-for-resource --resource-arn arn:aws:eks:us-west-2:xxx:cluster/ekscluster1
{
    "tags": {
        "bu": "cio",
        "env": "staging",
        "costcenter": "1234",
        "team": "devops"
    }
}
```
在您在 [AWS 成本资源管理器](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/cost-alloc-tags.html)中激活成本分配标签后，AWS 会使用成本分配标签来组织您的资源成本，以便于您在成本分配报告中对 AWS 成本进行分类和跟踪。

标签对于 Amazon EKS 没有任何语义含义，并且被严格解释为一串字符。例如，您可以为 Amazon EKS 集群定义一组标签，以帮助您跟踪每个集群的所有者和堆栈级别。

### 使用 AWS Trusted Advisor

AWS Trusted Advisor 提供了一套丰富的最佳实践检查和建议，涵盖五个类别：成本优化、安全性、容错能力、性能和服务限制。

对于成本优化，Trusted Advisor 有助于消除未使用和空闲的资源，并建议对预留容量进行承诺。对于 Amazon EKS 而言，关键的操作项目将围绕低利用率的 EC2 实例、未关联的弹性 IP 地址、空闲负载均衡器、低利用率的 EBS 卷等。完整的检查列表可在 https://aws.amazon.com/premiumsupport/technology/trusted-advisor/best-practice-checklist/ 上找到。

Trusted Advisor 还为 EC2 实例和 Fargate 提供了节省计划和预留实例建议，这允许您承诺一致的使用量以换取折扣价格。

!!! 注意
    Trusted Advisor 的建议是通用建议，而不是针对 EKS 的具体建议。

### 使用 Kubernetes 仪表板

***Kubernetes 仪表板***

Kubernetes 仪表板是一个通用的基于 Web 的 Kubernetes 集群 UI，它提供了有关 Kubernetes 集群的信息，包括集群、节点和 Pod 级别的资源使用情况。在 Amazon EKS 集群上部署 Kubernetes 仪表板的过程在 [Amazon EKS 文档](https://docs.aws.amazon.com/eks/latest/userguide/dashboard-tutorial.html)中有描述。

仪表板提供了每个节点和 Pod 的资源使用情况细分，以及有关 Pod、服务、Deployment 和其他 Kubernetes 对象的详细元数据。这些综合信息为您提供了对 Kubernetes 环境的可见性。

![Kubernetes 仪表板](../images/kubernetes-dashboard.png)

***kubectl top 和 describe 命令***

使用 kubectl top 和 kubectl describe 命令查看资源使用情况指标。kubectl top 将显示集群中 Pod 或节点的当前 CPU 和内存使用情况，或特定 Pod 或节点的使用情况。kubectl describe 命令将提供有关特定节点或 Pod 的更多详细信息。
```
$ kubectl top pods
$ kubectl top nodes
$ kubectl top pod pod-name --namespace mynamespace --containers
```

使用 top 命令时，输出将显示节点正在使用的 CPU 总量（以核心为单位）和内存总量（以 MiB 为单位），以及这些数字占节点可分配容量的百分比。然后，您可以通过添加 *--containers* 标志深入到下一级别，即 Pod 中的容器级别。


```
$ kubectl describe node <node>
$ kubectl describe pod <pod>
```

*kubectl describe* 返回每个资源请求或限制所代表的总可用容量的百分比。

kubectl top 和 describe 可跟踪 kubernetes pod、节点和容器中关键资源（如 CPU、内存和存储）的利用率和可用性。这种意识将有助于了解资源使用情况并帮助控制成本。


### 使用 CloudWatch Container Insights

使用 [CloudWatch Container Insights](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/deploy-container-insights-EKS.html) 来收集、聚合和汇总您的容器化应用程序和微服务的指标和日志。Container Insights 可用于 Amazon Elastic Kubernetes Service on EC2 和 Amazon EC2 上的 Kubernetes 平台。这些指标包括 CPU、内存、磁盘和网络等资源的利用率。

安装 insights 的步骤在 [文档](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/deploy-container-insights-EKS.html) 中给出。

CloudWatch 会将聚合后的指标创建为集群、节点、Pod、任务和服务级别的 CloudWatch 指标。

**以下查询显示了按平均节点 CPU 利用率排序的节点列表**
```
STATS avg(node_cpu_utilization) as avg_node_cpu_utilization by NodeName
| SORT avg_node_cpu_utilization DESC 
```

**按容器名称显示 CPU 使用情况**
```
stats pct(container_cpu_usage_total, 50) as CPUPercMedian by kubernetes.container_name 
| filter Type="Container"
```
**按容器名称显示磁盘使用情况**
```
stats floor(avg(container_filesystem_usage/1024)) as container_filesystem_usage_avg_kb by InstanceId, kubernetes.container_name, device 
| filter Type="ContainerFS" 
| sort container_filesystem_usage_avg_kb desc
```

更多示例查询在 [Container Insights 文档](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Container-Insights-view-metrics.html) 中给出。

这种了解将有助于理解资源使用情况并帮助控制成本。

### 使用 KubeCost 了解支出情况并获取指导

第三方工具如 [kubecost](https://kubecost.com/) 也可以部署在 Amazon EKS 上，以获得运行 Kubernetes 集群的成本可见性。请参阅此 [AWS 博客](https://aws.amazon.com/blogs/containers/how-to-track-costs-in-multi-tenant-amazon-eks-clusters-using-kubecost/)，了解如何使用 Kubecost 跟踪成本。

使用 Helm 3 部署 kubecost:
```
$ curl -sSL https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash
$ helm version --short
v3.2.1+gfe51cd1
$ helm repo add stable https://kubernetes-charts.storage.googleapis.com/
$ helm repo add stable https://kubernetes-charts.storage.googleapis.com/c^C
$ kubectl create namespace kubecost 
namespace/kubecost created
$ helm repo add kubecost https://kubecost.github.io/cost-analyzer/ 
"kubecost" has been added to your repositories

$ helm install kubecost kubecost/cost-analyzer --namespace kubecost --set kubecostToken="aGRoZEBqc2pzLmNvbQ==xm343yadf98"
NAME: kubecost
LAST DEPLOYED: Mon May 18 08:49:05 2020
NAMESPACE: kubecost
STATUS: deployed
REVISION: 1
TEST SUITE: None
NOTES:
--------------------------------------------------Kubecost 已成功安装。当 pod 准备就绪后，您可以使用以下命令启用端口转发:
    
    kubectl port-forward --namespace kubecost deployment/kubecost-cost-analyzer 9090
    
接下来，在 Web 浏览器中导航到 http://localhost:9090。
$ kubectl port-forward --namespace kubecost deployment/kubecost-cost-analyzer 9090

注意: 如果您使用的是 Cloud 9 或需要转发到其他端口如 8080，请发出以下命令
$ kubectl port-forward --namespace kubecost deployment/kubecost-cost-analyzer 8080:9090

```
Kube 成本仪表板 -
![Kubernetes Cluster Auto Scaler logs](../images/kube-cost.png)

### 使用 Kubernetes 成本分配和容量规划分析工具

[Kubernetes Opex Analytics](https://github.com/rchakode/kube-opex-analytics) 是一款帮助组织跟踪 Kubernetes 集群消耗的资源的工具，以防止付费过多。为此，它生成短期 (7 天)、中期 (14 天) 和长期 (12 个月) 使用报告，显示每个项目随时间消耗资源的相关见解。

![Kubernetes Opex Analytics](../images/kube-opex-analytics.png)


### Magalix Kubeadvisor

[KubeAdvisor](https://www.magalix.com/kubeadvisor) 持续扫描您的 Kubernetes 集群并报告如何修复问题、应用最佳实践以及优化集群(提供有关成本效率的 CPU/内存等资源的建议)。

### Spot.io, 之前称为 Spotinst

Spotinst Ocean 是一种应用程序扩展服务。与 Amazon Elastic Compute Cloud (Amazon EC2) 自动扩展组类似，Spotinst Ocean 旨在通过利用 Spot 实例与按需实例和预留实例相结合来优化性能和成本。使用自动化 Spot 实例管理和各种实例大小的组合，Ocean 集群自动扩缩器根据 pod 资源需求进行扩缩。Spotinst Ocean 还包括一种预测算法，可以提前 15 分钟预测 Spot 实例中断，并在不同的 Spot 容量池中启动新节点。

这是由 Spotinst 公司与 AWS 合作开发的 [AWS Quickstart](https://aws.amazon.com/quickstart/architecture/spotinst-ocean-eks/)。

EKS 研讨会还有一个关于 [Optimized Worker Node on Amazon EKS Management](https://eksworkshop.com/beginner/190_ocean/) 的模块，其中包括 Spot.io 的 Ocean 部分，涵盖了成本分配、正确调整大小和扩展策略。

### Yotascale

Yotascale 有助于准确分配 Kubernetes 成本。Yotascale Kubernetes 成本分配功能利用实际成本数据(包括预留实例折扣和 Spot 实例定价，而不是通用市场价格估算),来确定 Kubernetes 的总成本支出。

更多详细信息可在 [他们的网站](https://www.yotascale.com/) 上找到。

### Alcide Advisor

Alcide是AWS合作伙伴网络(APN)的高级技术合作伙伴。Alcide Advisor可帮助确保您的Amazon EKS集群、节点和Pod配置都根据安全最佳实践和内部指导原则进行了优化。Alcide Advisor是一种无代理的Kubernetes审计和合规服务，旨在通过在进入生产环境之前加固开发阶段，确保无缝和安全的DevSecOps流程。

更多详细信息可以在这篇[博客文章](https://aws.amazon.com/blogs/apn/driving-continuous-security-and-configuration-checks-for-amazon-eks-with-alcide-advisor/)中找到。


## 其他工具


### Kubernetes垃圾收集

[Kubernetes垃圾收集器](https://kubernetes.io/docs/concepts/workloads/controllers/garbage-collection/)的作用是删除某些曾经有所有者但现在没有所有者的对象。

### Fargate计数

[Fargatecount](https://github.com/mreferre/fargatecount)是一个有用的工具，它允许AWS客户使用自定义CloudWatch指标跟踪在特定区域的特定账户中部署在Fargate上的EKS Pod总数。这有助于跟踪跨EKS集群运行的所有Fargate Pod。

### Kubernetes Ops View

[Kube Ops View](https://github.com/hjacobs/kube-ops-view)是一个有用的工具，它为多个Kubernetes集群提供了一个通用的可视化操作图。

```
git clone https://github.com/hjacobs/kube-ops-view
cd kube-ops-view
kubectl apply -k deploy/
```

![主页](../images/kube-ops-report.png)


### Popeye - 一个Kubernetes集群清理工具

[Popeye - 一个Kubernetes集群清理工具](https://github.com/derailed/popeye)是一个实用程序，它扫描实时Kubernetes集群并报告已部署资源和配置中潜在的问题。它根据部署的内容而不是磁盘上的内容来清理您的集群。通过扫描您的集群，它可以检测到错误配置，并帮助您确保实施了最佳实践

### 资源
参考以下资源以了解有关成本优化最佳实践的更多信息。

文档和博客
+	[Amazon EKS 支持标记](https://docs.aws.amazon.com/eks/latest/userguide/eks-using-tags.html)

工具
+	[什么是 AWS Billing and Cost Management?](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/cost-alloc-tags.html)
+	[Amazon CloudWatch Container Insights](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/ContainerInsights.html)
+   [如何使用 Kubecost 跟踪多租户 Amazon EKS 集群中的成本](https://aws.amazon.com/blogs/containers/how-to-track-costs-in-multi-tenant-amazon-eks-clusters-using-kubecost/)
+   [Kube Cost](https://kubecost.com/)
+   [Kube Opsview](https://github.com/hjacobs/kube-ops-view)
+   [Kube Janitor](https://github.com/hjacobs/kube-janitor)
+   [Kubernetes Opex Analytics](https://github.com/rchakode/kube-opex-analytics)