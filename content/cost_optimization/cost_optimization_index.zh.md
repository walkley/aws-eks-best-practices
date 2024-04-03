# 亚马逊 EKS 成本优化最佳实践指南

成本优化是以最低价格实现您的业务目标。通过遵循本指南中的文档，您将优化您的亚马逊 EKS 工作负载。

# 一般指导原则

在云中，有一些一般指导原则可以帮助您实现微服务的成本优化:
+ 确保在亚马逊 EKS 上运行的工作负载独立于用于运行容器的特定基础架构类型，这将为在最便宜的基础架构类型上运行它们提供更大的灵活性。虽然使用亚马逊 EKS 与 EC2 时，当我们有需要特定类型 EC2 实例的工作负载时，如[需要 GPU](https://docs.aws.amazon.com/eks/latest/userguide/gpu-ami.html) 或其他实例类型，由于工作负载的性质，可能会有例外。
+ 选择最佳配置的容器实例 - 对生产或预生产环境进行分析，并使用诸如 [Amazon CloudWatch Container Insights for Amazon EKS](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/deploy-container-insights-EKS.html) 或 Kubernetes 生态系统中可用的第三方工具监控关键指标，如 CPU 和内存。这将确保我们可以分配正确数量的资源，避免资源浪费。
+ 利用 AWS 中为运行 EKS 与 EC2 提供的不同购买选项，例如 On-Demand、Spot 和 Savings Plan。

# EKS 成本优化最佳实践

云中成本优化有三个一般最佳实践领域:

+ 经济高效的资源 (自动缩放、缩减、策略和购买选项)
+ 支出意识 (使用 AWS 和第三方工具)
+ 随时间优化 (正确调整大小)

与任何指导一样，都存在权衡取舍。请与您的组织合作，了解此工作负载的优先级，以及哪些最佳实践最为重要。

## 如何使用本指南

本指南旨在为负责实施和管理 EKS 集群及其支持的工作负载的 DevOps 团队提供帮助。本指南按照不同的最佳实践领域进行组织，以便于阅读。每个主题都列出了建议、工具以及优化 EKS 集群成本的最佳实践。这些主题不需要按特定顺序阅读。

### 关键 AWS 服务和 Kubernetes 功能
以下 AWS 服务和功能支持成本优化:
+ 具有不同价格的 EC2 实例类型、Savings Plan (以及 Reserved Instances) 和 Spot Instances。
+ 结合 Kubernetes 原生自动缩放策略的自动缩放。对于可预测的工作负载，请考虑使用 Savings Plan (以前的 Reserved Instances)。使用托管数据存储(如 EBS 和 EFS),以实现应用程序数据的弹性和持久性。
+ Billing and Cost Management 控制台仪表板以及 AWS Cost Explorer 提供了您的 AWS 使用情况概览。使用 AWS Organizations 获取详细的计费明细。还分享了多个第三方工具的详细信息。
+ Amazon CloudWatch Container Metrics 提供了有关 EKS 集群资源使用情况的指标。除了 Kubernetes 仪表板外，Kubernetes 生态系统中还有多个工具可用于减少浪费。

本指南包含了一系列建议，您可以使用这些建议来改善您的 Amazon EKS 集群的成本优化。

## 反馈
我们将本指南发布到 GitHub 上，以便从更广泛的 EKS/Kubernetes 社区收集直接反馈和建议。如果您有任何认为应该包含在本指南中的最佳实践，请在 GitHub 存储库中提出问题或提交 PR。我们的目的是在服务添加新功能或出现新的最佳实践时，定期更新本指南。