# Amazon EKS 可靠性最佳实践指南

本节提供了有关使 EKS 上运行的工作负载具有弹性和高可用性的指导。

## 如何使用本指南

本指南面向希望在 EKS 中开发和运营高可用性和容错服务的开发人员和架构师。本指南按主题区域组织，以便于阅读。每个主题都以简要概述开头，然后列出了确保您的 EKS 集群可靠性的建议和最佳实践。

## 简介

EKS 的可靠性最佳实践分为以下主题:

* 应用程序
* 控制平面
* 数据平面

---

什么使系统可靠？如果一个系统在一段时间内能够持续运行并满足需求，即使环境发生变化，它也可以被称为可靠的系统。为了实现这一点，系统必须能够检测故障、自动修复自身，并且能够根据需求进行扩展。

客户可以使用 Kubernetes 作为运行关键任务应用程序和服务的可靠基础。但除了采用基于容器的应用程序设计原则外，可靠地运行工作负载还需要可靠的基础设施。在 Kubernetes 中，基础设施包括控制平面和数据平面。

EKS 提供了经过生产级别测试的 Kubernetes 控制平面，旨在实现高可用性和容错能力。

在 EKS 中，AWS 负责 Kubernetes 控制平面的可靠性。EKS 在 AWS 区域的三个可用区中运行 Kubernetes 控制平面。它会自动管理 Kubernetes API 服务器和 etcd 集群的可用性和可扩展性。

数据平面的可靠性责任由您（客户）和AWS共同承担。EKS为Kubernetes数据平面提供了三种选择。Fargate是最受管理的选项，负责数据平面的资源调配和扩缩。第二种选择是托管节点组，负责数据平面的资源调配和更新。最后，自管理节点是数据平面最不受管理的选择。您使用的AWS托管数据平面越多，您承担的责任就越少

[托管节点组](https://docs.aws.amazon.com/eks/latest/userguide/managed-node-groups.html)可自动执行EC2节点的资源调配和生命周期管理。您可以使用EKS API(通过EKS控制台、AWS API、AWS CLI、CloudFormation、Terraform或`eksctl`)来创建、扩缩和升级托管节点。托管节点在您的账户中运行经过EKS优化的Amazon Linux 2 EC2实例，您可以通过启用SSH访问来安装自定义软件包。当您调配托管节点时，它们将作为EKS托管的Auto Scaling组的一部分运行，该组可跨多个可用区;您可以通过在创建托管节点时提供的子网来控制这一点。EKS还会自动为托管节点添加标签，以便与Cluster Autoscaler一起使用。

> 对于托管节点组上的CVE和安全补丁，Amazon EKS遵循共享责任模型。由于托管节点运行Amazon EKS优化的AMI，因此当有Bug修复时，Amazon EKS负责构建这些AMI的修补版本。但是，您负责将这些修补后的AMI版本部署到您的托管节点组。

EKS还[管理节点的更新](https://docs.aws.amazon.com/eks/latest/userguide/update-managed-node-group.html),尽管您必须启动更新过程。[更新托管节点](https://docs.aws.amazon.com/eks/latest/userguide/managed-node-update-behavior.html)的过程在EKS文档中有解释。

如果您运行自管理节点，您可以使用 [Amazon EKS 优化的 Linux AMI](https://docs.aws.amazon.com/eks/latest/userguide/eks-optimized-ami.html) 来创建工作节点。您需要负责为 AMI 和节点打补丁和升级。使用 `eksctl`、CloudFormation 或基础设施作为代码工具来供应自管理节点是最佳实践，因为这将使您更容易 [升级自管理节点](https://docs.aws.amazon.com/eks/latest/userguide/update-workers.html)。在更新工作节点时，请考虑 [迁移到新节点](https://docs.aws.amazon.com/eks/latest/userguide/migrate-stack.html),因为迁移过程会将旧节点组 **标记为** `NoSchedule` 并在新堆栈准备好接受现有 pod 工作负载后 **排空** 节点。但是，您也可以执行 [就地升级自管理节点](https://docs.aws.amazon.com/eks/latest/userguide/update-stack.html)。

![Shared Responsibility Model - Fargate](./images/SRM-Fargate.jpeg)

![Shared Responsibility Model - MNG](./images/SRM-MNG.jpeg)

本指南包括一组建议，您可以使用这些建议来提高您的 EKS 数据平面、Kubernetes 核心组件和应用程序的可靠性。

## 反馈
本指南在 GitHub 上发布，旨在从更广泛的 EKS/Kubernetes 社区收集直接反馈和建议。如果您有任何您认为我们应该在指南中包含的最佳实践，请在 GitHub 存储库中提出问题或提交 PR。我们打算在服务添加新功能或出现新的最佳实践时定期更新指南。