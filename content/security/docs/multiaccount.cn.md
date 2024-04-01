# 多账户策略

AWS建议使用[多账户策略](https://docs.aws.amazon.com/whitepapers/latest/organizing-your-aws-environment/organizing-your-aws-environment.html)和AWS组织来帮助隔离和管理您的业务应用程序和数据。使用多账户策略有[多种好处](https://docs.aws.amazon.com/whitepapers/latest/organizing-your-aws-environment/benefits-of-using-multiple-aws-accounts.html)：

- 增加AWS API服务配额。配额是应用于AWS账户的，为您的工作负载使用多个账户可以增加工作负载可用的总配额。
- 更简单的身份和访问管理(IAM)策略。只授予工作负载及其支持运营人员访问自己的AWS账户权限，意味着减少了制定细粒度IAM策略以实现最小权限原则所需的时间。
- 改善AWS资源隔离。根据设计，在一个账户中配置的所有资源在逻辑上都与其他账户中配置的资源隔离。这种隔离边界为您提供了一种限制应用程序相关问题、错误配置或恶意行为风险的方式。如果一个账户中出现问题，对其他账户中包含的工作负载的影响可以减少或消除。
- 更多好处，如[AWS多账户策略白皮书](https://docs.aws.amazon.com/whitepapers/latest/organizing-your-aws-environment/benefits-of-using-multiple-aws-accounts.html#group-workloads-based-on-business-purpose-and-ownership)所述

以下部分将解释如何使用集中式或分散式EKS集群方法为您的EKS工作负载实施多账户策略。

## 为多租户集群规划多工作负载账户策略

在多账户AWS策略中，属于某个工作负载的资源(如S3存储桶、ElastiCache集群和DynamoDB表)都是在包含该工作负载所有资源的AWS账户中创建的。这些被称为工作负载账户，而EKS集群则部署在被称为集群账户的账户中。集群账户将在下一节中探讨。将资源部署到专用的工作负载账户类似于将kubernetes资源部署到专用的命名空间。

如果合适，工作负载账户可以进一步按软件开发生命周期或其他要求进行细分。例如，给定工作负载可以有生产账户、开发账户，或在特定区域托管该工作负载实例的账户。[更多信息](https://docs.aws.amazon.com/whitepapers/latest/organizing-your-aws-environment/organizing-workload-oriented-ous.html)可在此AWS白皮书中找到。

在实施EKS多账户策略时，您可以采用以下方法:

## 集中式EKS集群

在此方法中，您的EKS集群将部署在一个名为`集群账户`的单一AWS账户中。使用[服务账户的IAM角色(IRSA)](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html)或[EKS Pod身份](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html)来提供临时AWS凭证，以及[AWS资源访问管理器(RAM)](https://aws.amazon.com/ram/)来简化网络访问，您可以为多租户EKS集群采用多账户策略。集群账户将包含VPC、子网、EKS集群、EC2/Fargate计算资源(工作节点)以及运行EKS集群所需的任何其他网络配置。

在多租户集群的多工作负载账户策略中，AWS 账户通常与 [kubernetes 命名空间](https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/)对齐，作为隔离资源组的机制。在实施多租户 EKS 集群的多账户策略时，仍应遵循 EKS 集群内的[租户隔离最佳实践](/security/docs/multitenancy/)。

在您的 AWS 组织中可能有多个"集群账户",并且拥有与您的软件开发生命周期需求相一致的多个"集群账户"是最佳实践。对于大规模运行的工作负载，您可能需要多个"集群账户",以确保所有工作负载都有足够的 kubernetes 和 AWS 服务配额。

| ![multi-account-eks](./images/multi-account-eks.jpg) |
|:--:|
| 在上图中，AWS RAM 用于从集群账户共享子网到工作负载账户。然后在 EKS pod 中运行的工作负载使用 IRSA 或 EKS Pod 身份并通过角色链接来承担其工作负载账户中的角色，并访问其 AWS 资源。|

### 实施多租户集群的多工作负载账户策略

#### 使用 AWS Resource Access Manager 共享子网

[AWS Resource Access Manager](https://aws.amazon.com/ram/) (RAM) 允许您跨 AWS 账户共享资源。

如果为您的 AWS 组织[启用了 RAM](https://docs.aws.amazon.com/ram/latest/userguide/getting-started-sharing.html#getting-started-sharing-orgs),您可以从集群账户共享 VPC 子网到您的工作负载账户。这将允许您的工作负载账户拥有的 AWS 资源(如 [Amazon ElastiCache](https://aws.amazon.com/elasticache/) 集群或 [Amazon 关系数据库服务 (RDS)](https://aws.amazon.com/rds/) 数据库)部署到与您的 EKS 集群相同的 VPC 中，并可被运行在您 EKS 集群上的工作负载使用。

要通过 RAM 共享资源，请在集群账户的 AWS 控制台中打开 RAM，选择"资源共享"和"创建资源共享"。为您的资源共享命名并选择要共享的子网。再次选择"下一步",输入您希望与之共享子网的工作负载账户的 12 位账户 ID，再次选择"下一步",然后单击"创建资源共享"完成。完成此步骤后，工作负载账户可以在这些子网中部署资源。

资源共享也可以通过编程或基础设施即代码的方式创建。

#### 在 EKS Pod 身份和 IRSA 之间进行选择

在 2023 年的 re:Invent 大会上，AWS 推出了 EKS Pod 身份作为一种更简单的方式，为您在 EKS 上的 Pod 提供临时 AWS 凭证。IRSA 和 EKS Pod 身份都是向您的 EKS Pod 提供临时 AWS 凭证的有效方法，并将继续得到支持。您应该考虑哪种提供方式最能满足您的需求。

在使用 EKS 集群和多个 AWS 账户时，IRSA 可以直接在 EKS 集群所在的账户以外的 AWS 账户中承担角色，而 EKS Pod 身份则需要您配置角色链接。请参阅 [EKS 文档](https://docs.aws.amazon.com/eks/latest/userguide/service-accounts.html#service-accounts-iam) 以获取深入比较。

##### 使用服务账户的 IAM 角色访问 AWS API 资源

[服务账户的 IAM 角色 (IRSA)](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html) 允许您为在 EKS 上运行的工作负载提供临时 AWS 凭证。IRSA 可用于从集群账户获取工作负载账户中 IAM 角色的临时凭证。这允许您在集群账户中的 EKS 集群上运行的工作负载无缝地使用托管在工作负载账户中的 AWS API 资源，例如 S3 存储桶，并使用 IAM 身份验证访问诸如 Amazon RDS 数据库或 Amazon EFS 文件系统之类的资源。

AWS API 资源和其他使用工作负载账户中 IAM 身份验证的资源只能由同一工作负载账户中的 IAM 角色凭证访问，除非支持跨账户访问并已明确启用。

###### 为跨账户访问启用 IRSA

要为集群账户中的工作负载启用访问工作负载账户中资源的 IRSA，您首先必须在工作负载账户中创建 IAM OIDC 身份提供程序。这可以通过与设置 [IRSA](https://docs.aws.amazon.com/eks/latest/userguide/enable-iam-roles-for-service-accounts.html) 相同的过程完成，只是身份提供程序将在工作负载账户中创建。

然后，在为 EKS 上的工作负载配置 IRSA 时，您可以[按照与文档相同的步骤](https://docs.aws.amazon.com/eks/latest/userguide/associate-service-account-role.html),但使用"从另一个账户的集群创建身份提供程序"一节中提到的[工作负载账户的 12 位账号 ID](https://docs.aws.amazon.com/eks/latest/userguide/cross-account-access.html)。

配置完成后，您在 EKS 上运行的应用程序将能够直接使用其服务账户来承担工作负载账户中的角色，并使用其中的资源。

##### 使用 EKS Pod 身份访问 AWS API 资源

[EKS Pod 身份](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html)是一种新的向运行在 EKS 上的工作负载交付 AWS 凭证的方式。EKS pod 身份简化了 AWS 资源的配置，因为您不再需要管理 OIDC 配置来向 EKS 上的 pod 交付 AWS 凭证。

###### 为跨账户访问启用 EKS Pod 身份

与 IRSA 不同，EKS Pod Identities 只能用于直接授予同一账户中 EKS 集群的角色访问权限。要访问另一个 AWS 账户中的角色，使用 EKS Pod Identities 的 pod 必须执行[角色链接](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_terms-and-concepts.html#iam-term-role-chaining)。

可以在应用程序的 aws 配置文件中使用各种 AWS SDK 中提供的[进程凭证提供程序](https://docs.aws.amazon.com/sdkref/latest/guide/feature-process-credentials.html)来配置角色链接。在配置配置文件时，可以使用 `credential_process` 作为凭证源，例如：

```bash
# AWS 配置文件内容
[profile account_b_role] 
source_profile = account_a_role 
role_arn = arn:aws:iam::444455556666:role/account-b-role

[profile account_a_role] 
credential_process = /eks-credential-processrole.sh
```

credential_process 调用的脚本源码：

```bash
#!/bin/bash
# eks-credential-processrole.sh 内容
# 这将从 pod identities 代理中检索凭证，
# 并在引用配置文件时将其返回给 AWS SDK
curl -H "Authorization: $(cat $AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE)" $AWS_CONTAINER_CREDENTIALS_FULL_URI | jq -c '{AccessKeyId: .AccessKeyId, SecretAccessKey: .SecretAccessKey, SessionToken: .Token, Expiration: .Expiration, Version: 1}' 
```

您可以按照上面的示例创建一个包含账户 A 和 B 角色的 aws 配置文件，并在 pod spec 中指定 AWS_CONFIG_FILE 和 AWS_PROFILE 环境变量。如果 pod spec 中已经存在这些环境变量，EKS Pod identity webhook 不会覆盖它们。

```yaml
# Pod 规约片段
containers: 
  - name: container-name
    image: container-image:version
    env:
    - name: AWS_CONFIG_FILE
      value: path-to-customer-provided-aws-config-file
    - name: AWS_PROFILE
      value: account_b_role
```

在为 EKS pod 身份配置角色信任策略以进行角色链接时，您可以将 [EKS 特定属性](https://docs.aws.amazon.com/eks/latest/userguide/pod-id-abac.html) 作为会话标签进行引用，并使用基于属性的访问控制(ABAC)来限制对您的 IAM 角色的访问，仅限于特定的 EKS Pod 身份会话，例如 pod 所属的 Kubernetes 服务帐户。

请注意，其中一些属性可能不是通用唯一的，例如两个 EKS 集群可能具有相同的命名空间，并且一个集群可能在不同命名空间中具有相同名称的服务帐户。因此，在通过 EKS Pod 身份和 ABAC 授予访问权限时，最佳实践是始终考虑集群 arn 和命名空间，以授予对服务帐户的访问权限。

###### 跨账户访问的 ABAC 和 EKS Pod 身份

在使用 EKS Pod 身份作为多账户策略的一部分来承担其他账户中的角色(角色链接)时，您可以选择为每个需要访问另一个账户的服务帐户分配一个唯一的 IAM 角色，或者跨多个服务帐户使用一个通用的 IAM 角色，并使用 ABAC 来控制它可以访问哪些账户。

要使用 ABAC 控制哪些服务帐户可以通过角色链接承担另一个账户中的角色，您需要创建一个角色信任策略语句，该语句仅在存在预期值时才允许承担角色会话。以下角色信任策略将仅允许来自 EKS 集群账户(账户 ID 111122223333)的角色承担一个角色，前提是 `kubernetes-service-account`、`eks-cluster-arn` 和 `kubernetes-namespace` 标签都具有预期值。

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::111122223333:root"
            },
            "Action": "sts:AssumeRole",
            "Condition": {
                "StringEquals": {
                    "aws:PrincipalTag/kubernetes-service-account": "PayrollApplication",
                    "aws:PrincipalTag/eks-cluster-arn": "arn:aws:eks:us-east-1:111122223333:cluster/ProductionCluster",
                    "aws:PrincipalTag/kubernetes-namespace": "PayrollNamespace"
                }
            }
        }
    ]
}
```

使用这种策略时，最佳实践是确保通用 IAM 角色只有 `sts:AssumeRole` 权限，没有其他 AWS 访问权限。

在使用 ABAC 时，重要的是要控制谁有能力为 IAM 角色和用户添加标签，只有那些严格需要这样做的人才能这样做。任何有能力为 IAM 角色或用户设置标签的人都可能会设置与 EKS Pod Identities 设置的标签相同的标签，从而可能会提升他们的权限。您可以使用 IAM 策略或服务控制策略 (SCP) 来限制谁有权在 IAM 角色和用户上设置 `kubernetes-` 和 `eks-` 标签。

## 去中心化的 EKS 集群

在这种方法中，EKS 集群部署在各自的工作负载 AWS 账户中，并与其他 AWS 资源（如 Amazon S3 存储桶、VPC、Amazon DynamoDB 表等）一起存在。每个工作负载账户都是独立的、自给自足的，并由各自的业务单位/应用程序团队进行操作。这种模型允许创建各种集群功能（AI/ML 集群、批处理、通用等）的可重用蓝图，并根据应用程序团队的要求提供集群。应用程序团队和平台团队都从各自的 [GitOps](https://www.weave.works/technologies/gitops/) 存储库中管理对工作负载集群的部署。

|![去中心化的 EKS 集群架构](./images/multi-account-eks-decentralized.png)|
|:--:|
| 在上图中，Amazon EKS 集群和其他 AWS 资源部署在各自的工作负载账户中。然后在 EKS pod 中运行的工作负载使用 IRSA 或 EKS Pod Identities 来访问它们的 AWS 资源。|

GitOps 是一种管理应用程序和基础设施部署的方式，整个系统都以声明式的方式描述在 Git 存储库中。它是一种操作模型，可让您使用版本控制、不可变工件和自动化的最佳实践来管理多个 Kubernetes 集群的状态。在这种多集群模型中，每个工作负载集群都使用多个 Git 存储库进行引导，从而允许每个团队(应用程序、平台、安全等)在集群上部署各自的更改。

您可以在每个账户中使用 [IAM 角色服务账户 (IRSA)](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html) 或 [EKS Pod Identities](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html)，允许您的 EKS 工作负载获取临时 aws 凭证以安全访问其他 AWS 资源。IAM 角色在各自的工作负载 AWS 账户中创建，并将它们映射到 k8s 服务账户以提供临时 IAM 访问权限。因此，在这种方法中不需要跨账户访问。请按照 [IAM 角色服务账户](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html)文档中的说明在每个工作负载中设置 IRSA，以及 [EKS Pod Identities](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html) 文档中的说明在每个账户中设置 EKS pod identities。

### 集中式网络

您也可以利用 AWS RAM 将 VPC 子网共享给工作负载账户，并在其中启动 Amazon EKS 集群和其他 AWS 资源。这样可以实现集中式网络管理/管理、简化网络连接，以及去中心化 EKS 集群。请参阅此 [AWS 博客](https://aws.amazon.com/blogs/containers/use-shared-vpcs-in-amazon-eks/)以获取此方法的详细演练和注意事项。

|![使用 VPC 共享子网的去中心化 EKS 集群架构](./images/multi-account-eks-shared-subnets.png)|
|:--:|
| 在上图中，AWS RAM 用于将子网从中央网络账户共享到工作负载账户。然后在各自的工作负载账户中的这些子网中启动 EKS 集群和其他 AWS 资源。EKS pod 使用 IRSA 或 EKS Pod 身份来访问其 AWS 资源。|

## 集中式与去中心化 EKS 集群

选择运行集中式还是去中心化将取决于您的需求。此表格展示了每种策略的关键区别。

|# |集中式 EKS 集群 | 分散式 EKS 集群 |
|:--|:--|:--|
|集群管理: |管理单个 EKS 集群比管理多个集群更容易 | 需要高效的集群管理自动化来减少管理多个 EKS 集群的运营开销|
|成本效率: | 允许重复使用 EKS 集群和网络资源，从而提高成本效率 | 每个工作负载都需要网络和集群设置，需要额外的资源|
|弹性: | 集中式集群上的多个工作负载可能会受到集群受损的影响 | 如果集群受损，损害仅限于在该集群上运行的工作负载。所有其他工作负载不受影响 |
|隔离和安全性:|使用 k8s 原生构造(如 `Namespaces`)实现隔离/软多租户。工作负载可能共享底层资源，如 CPU、内存等。AWS 资源被隔离到各自的工作负载账户中，默认情况下无法从其他 AWS 账户访问。|计算资源具有更强的隔离性，因为工作负载在单独的集群和节点上运行，不共享任何资源。AWS 资源被隔离到各自的工作负载账户中，默认情况下无法从其他 AWS 账户访问。|
|性能和可扩展性:|随着工作负载规模增长到非常大，您可能会遇到集群账户中的 kubernetes 和 AWS 服务配额。您可以部署额外的集群账户以进一步扩展|随着集群和 VPC 的增加，每个工作负载都有更多可用的 k8s 和 AWS 服务配额|
|网络: | 每个集群使用单个 VPC，允许该集群上的应用程序进行更简单的连接 | 必须在分散式 EKS 集群 VPC 之间建立路由 |
|Kubernetes 访问管理: |需要在集群中维护许多不同的角色和用户，以便为所有工作负载团队提供访问权限，并确保正确隔离 kubernetes 资源| 访问管理简化，因为每个集群专用于一个工作负载/团队|
|AWS 访问管理: |AWS 资源部署到各自的账户中，默认情况下只能通过工作负载账户中的 IAM 角色访问。工作负载账户中的 IAM 角色通过 IRSA 或 EKS Pod Identities 跨账户假设。|AWS 资源部署到各自的账户中，默认情况下只能通过工作负载账户中的 IAM 角色访问。工作负载账户中的 IAM 角色直接传递给 Pod，使用 IRSA 或 EKS Pod Identities。|