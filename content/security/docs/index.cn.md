# Amazon EKS 安全最佳实践指南

本指南提供了有关保护依赖于 EKS 的信息、系统和资产的建议，同时通过风险评估和缓解策略提供业务价值。本指南中的指导是 AWS 发布的一系列最佳实践指南的一部分，旨在帮助客户按照最佳实践实施 EKS。性能、运营卓越、成本优化和可靠性指南将在未来几个月内推出。

## 如何使用本指南

本指南面向负责实施和监控 EKS 集群及其支持的工作负载的安全控制有效性的安全从业人员。本指南按主题区域组织，以便于阅读。每个主题首先简要概述，然后列出了保护 EKS 集群的建议和最佳实践。主题不需按特定顺序阅读。

## 了解共享责任模型

使用 EKS 等托管服务时，安全和合规性被视为共享责任。一般而言，AWS 负责"云"的安全，而您作为客户则负责"云中"的安全。对于 EKS，AWS 负责管理 EKS 托管的 Kubernetes 控制平面。这包括 Kubernetes 控制平面节点、ETCD 数据库以及 AWS 提供安全可靠服务所需的其他基础设施。作为 EKS 的消费者，您主要负责本指南中的主题，例如 IAM、Pod 安全性、运行时安全性、网络安全性等。

在基础设施安全方面，随着从自管理工作节点到托管节点组再到 Fargate，AWS 将承担更多责任。例如，对于 Fargate，AWS 负责保护用于运行 Pod 的底层实例/运行时。

![共享责任模型 - Fargate](images/SRM-EKS.jpg)

AWS 还将负责保持 EKS 优化的 AMI 与 Kubernetes 补丁版本和安全补丁保持最新。使用托管节点组 (MNG) 的客户负责通过 EKS API、CLI、Cloudformation 或 AWS 控制台将其节点组升级到最新的 AMI。与 Fargate 不同的是，MNG 不会自动扩展您的基础设施/集群。这可以由 [cluster-autoscaler](https://github.com/kubernetes/autoscaler/blob/master/cluster-autoscaler/cloudprovider/aws/README.md) 或其他技术如 [Karpenter](https://karpenter.sh/)、原生 AWS 自动缩放、SpotInst 的 [Ocean](https://spot.io/solutions/kubernetes-2/) 或 Atlassian 的 [Escalator](https://github.com/atlassian/escalator) 来处理。

![共享责任模型 - MNG](./images/SRM-MNG.jpg)

在设计您的系统之前，了解您和服务提供商 (AWS) 之间的责任划分界限非常重要。

有关共享责任模型的更多信息，请参阅 [https://aws.amazon.com/compliance/shared-responsibility-model/](https://aws.amazon.com/compliance/shared-responsibility-model/)

## 简介

在使用像 EKS 这样的托管 Kubernetes 服务时，有几个安全最佳实践领域是相关的:

- 身份和访问管理
- Pod 安全性
- 运行时安全性
- 网络安全性
- 多租户
- 多账户用于多租户
- 检测控制
- 基础设施安全性
- 数据加密和密钥管理
- 合规性
- 事件响应和取证
- 镜像安全性

在设计任何系统时，您需要考虑其安全影响和可能影响安全态势的做法。例如，您需要控制谁可以对一组资源执行操作。您还需要能够快速识别安全事件，保护您的系统和服务免受未经授权的访问，并通过数据保护来维护数据的机密性和完整性。拥有一套明确定义和经过演练的响应安全事件的流程也将改善您的安全态势。这些工具和技术很重要，因为它们支持诸如防止财务损失或遵守监管义务等目标。

AWS通过提供一套基于广泛的安全意识客户反馈而不断发展的丰富安全服务，帮助组织实现其安全和合规目标。通过提供高度安全的基础，客户可以花费更少时间在"无差异的重体力劳动"上，而将更多时间用于实现业务目标。

## 反馈

本指南在GitHub上发布，以便从更广泛的EKS/Kubernetes社区收集直接反馈和建议。如果您有任何最佳实践认为我们应该包含在指南中，请在GitHub存储库中提出问题或提交PR。我们的目的是在服务添加新功能或出现新的最佳实践时，定期更新指南。

## 进一步阅读

[Kubernetes安全白皮书](https://github.com/kubernetes/sig-security/blob/main/sig-security-external-audit/security-audit-2019/findings/Kubernetes%20White%20Paper.pdf),由安全审计工作组赞助，该白皮书描述了Kubernetes攻击面和安全架构的关键方面，旨在帮助安全从业者做出合理的设计和实施决策。

CNCF还发布了一份关于云原生安全的[白皮书](https://github.com/cncf/tag-security/blob/efb183dc4f19a1bf82f967586c9dfcb556d87534/security-whitepaper/v2/CNCF_cloud-native-security-whitepaper-May2022-v2.pdf)。该白皮书研究了技术环境的演变，并倡导采用与DevOps流程和敏捷方法相一致的安全实践。

## 工具和资源

[Amazon EKS 安全沉浸式研讨会](https://catalog.workshops.aws/eks-security-immersionday/en-US)