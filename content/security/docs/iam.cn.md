# 身份和访问管理

[身份和访问管理](https://docs.aws.amazon.com/IAM/latest/UserGuide/introduction.html) (IAM) 是一项 AWS 服务，执行两个基本功能：身份验证和授权。身份验证涉及身份验证，而授权管理 AWS 资源可以执行的操作。在 AWS 中，资源可以是另一项 AWS 服务，例如 EC2，或者是 AWS [主体](https://docs.aws.amazon.com/IAM/latest/UserGuide/intro-structure.html#intro-structure-principal)，如 [IAM 用户](https://docs.aws.amazon.com/IAM/latest/UserGuide/id.html#id_iam-users)或[角色](https://docs.aws.amazon.com/IAM/latest/UserGuide/id.html#id_iam-roles)。规范资源被允许执行的操作的规则表示为 [IAM 策略](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies.html)。

## 控制对 EKS 集群的访问

Kubernetes 项目支持各种不同的策略来对 kube-apiserver 服务的请求进行身份验证，例如 Bearer 令牌、X.509 证书、OIDC 等。EKS 目前支持 [webhook 令牌身份验证](https://kubernetes.io/docs/reference/access-authn-authz/authentication/#webhook-token-authentication)、[服务账户令牌](https://kubernetes.io/docs/reference/access-authn-authz/authentication/#service-account-tokens)，以及自 2021 年 2 月 21 日起，OIDC 身份验证。

Webhook 身份验证策略调用一个 Webhook 来验证持有者令牌。在 EKS 上，这些持有者令牌是由 AWS CLI 或 [aws-iam-authenticator](https://github.com/kubernetes-sigs/aws-iam-authenticator) 客户端在您运行 `kubectl` 命令时生成的。当您执行命令时，令牌会被传递给 kube-apiserver,然后 kube-apiserver 会将其转发给身份验证 Webhook。如果请求格式正确，Webhook 会调用令牌正文中嵌入的预签名 URL。该 URL 验证请求的签名并将有关用户的信息(如用户的账户、Arn 和 UserId)返回给 kube-apiserver。

要手动生成身份验证令牌，请在终端窗口中键入以下命令:

```bash
aws eks get-token --cluster-name <cluster_name>
```

您也可以以编程方式获取令牌。下面是一个用 Go 编写的示例:

```golang
package main

import (
  "fmt"
  "log"
  "sigs.k8s.io/aws-iam-authenticator/pkg/token"
)

func main()  {
  g, _ := token.NewGenerator(false, false)
  tk, err := g.Get("<cluster_name>")
  if err != nil {
    log.Fatal(err)
  }
  fmt.Println(tk)
}
```

输出应该类似于这样:

```json
{
  "kind": "ExecCredential",
  "apiVersion": "client.authentication.k8s.io/v1alpha1",
  "spec": {},
  "status": {
    "expirationTimestamp": "2020-02-19T16:08:27Z",
    "token": "k8s-aws-v1.aHR0cHM6Ly9zdHMuYW1hem9uYXdzLmNvbS8_QWN0aW9uPUdldENhbGxlcklkZW50aXR5JlZlcnNpb249MjAxMS0wNi0xNSZYLUFtei1BbGdvcml0aG09QVdTNC1ITUFDLVNIQTI1NiZYLUFtei1DcmVkZW50aWFsPUFLSUFKTkdSSUxLTlNSQzJXNVFBJTJGMjAyMDAyMTklMkZ1cy1lYXN0LTElMkZzdHMlMkZhd3M0X3JlcXVlc3QmWC1BbXotRGF0ZT0yMDIwMDIxOVQxNTU0MjdaJlgtQW16LUV4cGlyZXM9NjAmWC1BbXotU2lnbmVkSGVhZGVycz1ob3N0JTNCeC1rOHMtYXdzLWlkJlgtQW16LVNpZ25hdHVyZT0yMjBmOGYzNTg1ZTMyMGRkYjVlNjgzYTVjOWE0MDUzMDFhZDc2NTQ2ZjI0ZjI4MTExZmRhZDA5Y2Y2NDhhMzkz"
  }
}
```

每个令牌以 `k8s-aws-v1.` 开头，后跟一个 base64 编码的字符串。解码后的字符串应该类似于这样:

```bash
https://sts.amazonaws.com/?Action=GetCallerIdentity&Version=2011-06-15&X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=XXXXJPFRILKNSRC2W5QA%2F20200219%2Fus-xxxx-1%2Fsts%2Faws4_request&X-Amz-Date=20200219T155427Z&X-Amz-Expires=60&X-Amz-SignedHeaders=host%3Bx-k8s-aws-id&X-Amz-Signature=XXXf8f3285e320ddb5e683a5c9a405301ad76546f24f28111fdad09cf648a393
```

令牌由包含Amazon凭证和签名的预签名URL组成。有关更多详细信息，请参见[https://docs.aws.amazon.com/STS/latest/APIReference/API_GetCallerIdentity.html](https://docs.aws.amazon.com/STS/latest/APIReference/API_GetCallerIdentity.html)。

令牌的生存时间(TTL)为15分钟，之后需要生成新的令牌。当您使用诸如`kubectl`之类的客户端时，这是自动处理的，但是，如果您使用Kubernetes仪表板，则每次令牌过期时，您都需要生成新的令牌并重新进行身份验证。

一旦用户的身份已由AWS IAM服务进行身份验证，kube-apiserver就会读取`kube-system`命名空间中的`aws-auth` ConfigMap,以确定要与用户关联的RBAC组。`aws-auth` ConfigMap用于在IAM主体(即IAM用户和角色)与Kubernetes RBAC组之间创建静态映射。RBAC组可以在Kubernetes RoleBinding或ClusterRoleBinding中引用。它们类似于IAM角色，因为它们定义了可以对Kubernetes资源(对象)集合执行的一组操作(动词)。

### 集群访问管理器

集群访问管理器(Cluster Access Manager)现在是管理AWS IAM主体访问Amazon EKS集群的首选方式，它是AWS API的一项功能，并且是EKS v1.23及更高版本集群(新集群或现有集群)的一项可选功能。它简化了AWS IAM和Kubernetes RBAC之间的身份映射，消除了在AWS和Kubernetes API之间切换或编辑`aws-auth` ConfigMap进行访问管理的需求，从而减少了操作开销，并有助于解决错误配置问题。该工具还允许集群管理员自动撤销或细化为创建集群时使用的AWS IAM主体授予的`cluster-admin`权限。

该API依赖于两个概念:

- **访问条目:** 直接链接到允许身份验证到Amazon EKS集群的AWS IAM主体(用户或角色)的集群身份。
- **访问策略:** 是Amazon EKS特定的策略，为访问条目提供在Amazon EKS集群中执行操作的授权。

> 在发布时，Amazon EKS仅支持预定义和AWS管理的策略。访问策略不是IAM实体，由Amazon EKS定义和管理。

集群访问管理器允许将上游RBAC与支持允许和通过(但不是拒绝)Kubernetes AuthZ决策的访问策略相结合，关于API服务器请求。当上游RBAC和Amazon EKS授权者都无法确定请求评估的结果时，将发生拒绝决定。

使用此功能，Amazon EKS支持三种身份验证模式:

1. `CONFIG_MAP` 继续专门使用`aws-auth` configMap。
2. `API_AND_CONFIG_MAP` 从EKS访问条目API和`aws-auth` configMap获取经过身份验证的IAM主体，优先考虑访问条目。理想情况下将现有的`aws-auth`权限迁移到访问条目。
3. `API` 专门依赖EKS访问条目API。这是新的**推荐方法**。

开始使用时，集群管理员可以创建或更新 Amazon EKS 集群，将首选身份验证设置为 `API_AND_CONFIG_MAP` 或 `API` 方法，并定义访问条目以授予所需的 AWS IAM 主体访问权限。

```bash
$ aws eks create-cluster \
    --name <CLUSTER_NAME> \
    --role-arn <CLUSTER_ROLE_ARN> \
    --resources-vpc-config subnetIds=<value>,endpointPublicAccess=true,endpointPrivateAccess=true \
    --logging '{"clusterLogging":[{"types":["api","audit","authenticator","controllerManager","scheduler"],"enabled":true}]}' \
    --access-config authenticationMode=API_AND_CONFIG_MAP,bootstrapClusterCreatorAdminPermissions=false
```

上面的命令是一个创建 Amazon EKS 集群的示例，该集群已经没有集群创建者的管理员权限。

可以使用 `update-cluster-config` 命令更新 Amazon EKS 集群配置以启用 `API` authenticationMode，对于使用 `CONFIG_MAP` 的现有集群，您将不得不先更新到 `API_AND_CONFIG_MAP`，然后再更新到 `API`。**这些操作无法撤消**，这意味着无法从 `API` 切换到 `API_AND_CONFIG_MAP` 或 `CONFIG_MAP`，也无法从 `API_AND_CONFIG_MAP` 切换到 `CONFIG_MAP`。

```bash
$ aws eks update-cluster-config \
    --name <CLUSTER_NAME> \
    --access-config authenticationMode=API
```

API 支持添加和撤销对集群的访问权限的命令，以及验证指定集群的现有访问策略和访问条目。默认策略会根据 Kubernets RBAC 创建，如下所示。

| EKS 访问策略 | Kubernetes RBAC |
|--|--|
| AmazonEKSClusterAdminPolicy | cluster-admin |
| AmazonEKSAdminPolicy | admin |
| AmazonEKSEditPolicy | edit |
| AmazonEKSViewPolicy | view |

```bash
$ aws eks list-access-policies
{
    "accessPolicies": [
        {
            "name": "AmazonEKSAdminPolicy",
            "arn": "arn:aws:eks::aws:cluster-access-policy/AmazonEKSAdminPolicy"
        },
        {
            "name": "AmazonEKSClusterAdminPolicy",
            "arn": "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
        },
        {
            "name": "AmazonEKSEditPolicy",
            "arn": "arn:aws:eks::aws:cluster-access-policy/AmazonEKSEditPolicy"
        },
        {
            "name": "AmazonEKSViewPolicy",
            "arn": "arn:aws:eks::aws:cluster-access-policy/AmazonEKSViewPolicy"
        }
    ]
}

$ aws eks list-access-entries --cluster-name <CLUSTER_NAME>

{
    "accessEntries": []
}
```

> 当集群在创建时没有集群创建者管理员权限时，就不会有可用的访问条目，这是默认情况下唯一创建的条目。

### `aws-auth` ConfigMap _(已弃用)_

Kubernetes与AWS身份验证集成的一种方式是通过`aws-auth` ConfigMap，它位于`kube-system`命名空间中。它负责将AWS IAM身份(用户、组和角色)身份验证映射到Kubernetes基于角色的访问控制(RBAC)授权。在Amazon EKS集群的供应阶段会自动在集群中创建`aws-auth` ConfigMap。它最初是为了允许节点加入您的集群而创建的，但正如所提到的，您也可以使用此ConfigMap为IAM主体添加RBAC访问权限。

要检查集群的`aws-auth` ConfigMap,您可以使用以下命令。

```bash
kubectl -n kube-system get configmap aws-auth -o yaml
```

这是`aws-auth` ConfigMap的默认配置示例。

```yaml
apiVersion: v1
data:
  mapRoles: |
    - groups:
      - system:bootstrappers
      - system:nodes
      - system:node-proxier
      rolearn: arn:aws:iam::<AWS_ACCOUNT_ID>:role/kube-system-<SELF_GENERATED_UUID>
      username: system:node:{{SessionName}}
kind: ConfigMap
metadata:
  creationTimestamp: "2023-10-22T18:19:30Z"
  name: aws-auth
  namespace: kube-system
```

该ConfigMap的主要部分在`data`下的`mapRoles`块中，基本由3个参数组成。

- **groups:** 将IAM角色映射到的Kubernetes组。这可以是默认组，也可以是在`clusterrolebinding`或`rolebinding`中指定的自定义组。在上面的示例中，我们只声明了系统组。
- **rolearn:** 要映射到Kubernetes组的AWS IAM角色的ARN，使用以下格式`arn:<PARTITION>:iam::<AWS_ACCOUNT_ID>:role/role-name`。
- **username:** 在Kubernetes中映射到AWS IAM角色的用户名。这可以是任何自定义名称。

> 也可以通过在`aws-auth` ConfigMap的`data`下定义一个新的`mapUsers`配置块来映射AWS IAM用户的权限，将**rolearn**参数替换为**userarn**，但作为**最佳实践**，建议始终使用`mapRoles`。

要管理权限，您可以通过添加或删除对Amazon EKS集群的访问权限来编辑`aws-auth` ConfigMap。虽然可以手动编辑`aws-auth` ConfigMap，但建议使用诸如`eksctl`之类的工具，因为这是一个非常敏感的配置，不准确的配置可能会将您锁定在Amazon EKS集群之外。有关更多详细信息，请查看下面的小节[使用工具对aws-auth ConfigMap进行更改](https://aws.github.io/aws-eks-best-practices/security/docs/iam/#use-tools-to-make-changes-to-the-aws-auth-configmap)。

## 集群访问建议

### 使EKS集群端点私有化

默认情况下，当您配置 EKS 集群时，API 集群端点被设置为公共的，即可以从互联网访问。尽管可以从互联网访问，但该端点仍被视为安全的，因为它要求所有 API 请求都由 IAM 进行身份验证，然后由 Kubernetes RBAC 进行授权。尽管如此，如果您的公司安全政策要求您限制从互联网访问 API 或防止您将流量路由到集群 VPC 之外，您可以:

- 将 EKS 集群端点配置为私有。有关此主题的更多信息，请参阅[修改集群端点访问](https://docs.aws.amazon.com/eks/latest/userguide/cluster-endpoint.html)。
- 保持集群端点公开并指定哪些 CIDR 块可以与集群端点通信。这些块实际上是一组允许访问集群端点的白名单公共 IP 地址。
- 使用一组白名单 CIDR 块配置公共访问权限并将私有端点访问设置为启用。这将允许从特定范围的公共 IP 进行公共访问，同时强制 kubelets(工作节点)和 Kubernetes API 之间的所有网络流量通过在配置控制平面时在集群 VPC 中配置的跨账户 ENI。

### 不要使用服务账户令牌进行身份验证

服务账户令牌是一个长期的、静态的凭证。如果它被泄露、丢失或被盗，攻击者可能能够执行与该令牌相关的所有操作，直到该服务账户被删除。有时，您可能需要为必须从集群外部消费 Kubernetes API 的应用程序授予例外，例如 CI/CD 管道应用程序。如果此类应用程序运行在 AWS 基础设施(如 EC2 实例)上，请考虑使用实例配置文件并将其映射到 Kubernetes RBAC 角色。

### 对 AWS 资源采用最小特权访问

IAM 用户无需被分配访问 AWS 资源的权限即可访问 Kubernetes API。如果需要授予 IAM 用户访问 EKS 集群的权限，请为该用户在 `aws-auth` ConfigMap 中创建一个条目，将其映射到特定的 Kubernetes RBAC 组。

### 从集群创建者主体中删除 cluster-admin 权限

默认情况下，Amazon EKS 集群在创建时会将永久的 `cluster-admin` 权限绑定到集群创建者主体。使用 Cluster Access Manager API，可以在使用 `API_AND_CONFIG_MAP` 或 `API` 身份验证模式时，通过将 `--access-config bootstrapClusterCreatorAdminPermissions` 设置为 `false` 来创建没有此权限设置的集群。吊销此访问权限被视为最佳实践，以避免对集群配置进行任何意外更改。吊销此访问权限的过程与吊销对集群的任何其他访问权限的过程相同。

API 为您提供了灵活性，只能将 IAM 主体与访问策略（在本例中为 `AmazonEKSClusterAdminPolicy`）解除关联。

```bash
$ aws eks list-associated-access-policies \
    --cluster-name <CLUSTER_NAME> \
    --principal-arn <IAM_PRINCIPAL_ARN>

$ aws eks disassociate-access-policy --cluster-name <CLUSTER_NAME> \
    --principal-arn <IAM_PRINCIPAL_ARN. \
    --policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy
```

或者完全删除与 `cluster-admin` 权限关联的访问条目。

```bash
$ aws eks list-access-entries --cluster-name <CLUSTER_NAME>

{
    "accessEntries": []
}

$ aws eks delete-access-entry --cluster-name <CLUSTER_NAME> \
  --principal-arn <IAM_PRINCIPAL_ARN>
```

> 在发生事故、紧急情况或者集群无法访问的情况下，可以根据需要重新授予此访问权限。

如果集群仍然使用 `CONFIG_MAP` 身份验证方法配置，则应通过 `aws-auth` ConfigMap 为所有其他用户授予对集群的访问权限。在配置 `aws-auth` ConfigMap 后，可以删除分配给创建集群的实体的角色，并且只有在发生事故、紧急情况或者打破玻璃情况下，或者 `aws-auth` ConfigMap 损坏且集群无法访问时，才需要重新创建该角色。这在生产集群中特别有用。

### 当多个用户需要相同的集群访问权限时使用 IAM 角色

与为每个单独的 IAM 用户创建条目不同，允许这些用户承担 IAM 角色并将该角色映射到 Kubernetes RBAC 组。这将更容易维护，尤其是在需要访问权限的用户数量增加时。

!!! attention
    使用 `aws-auth` ConfigMap 映射的 IAM 实体访问 EKS 集群时，所描述的用户名将记录在 Kubernetes 审计日志的用户字段中。如果您使用 IAM 角色，则无法记录和审计实际承担该角色的用户。

如果仍在使用 `aws-auth` configMap 作为身份验证方法，在为 IAM 角色分配 K8s RBAC 权限时，您应该在用户名中包含 {{SessionName}}。这样，审计日志将记录会话名称，以便您可以跟踪实际承担此角色的用户以及 CloudTrail 日志。

```yaml
- rolearn: arn:aws:iam::XXXXXXXXXXXX:role/testRole
  username: testRole:{{SessionName}}
  groups:
    - system:masters
```

> 在 Kubernetes 1.20 及更高版本中，不再需要进行此更改，因为 ```user.extra.sessionName.0``` 已添加到 Kubernetes 审计日志中。

### 在创建 RoleBinding 和 ClusterRoleBinding 时采用最小特权访问

与之前关于授予对AWS资源的访问权限的要点一样，RoleBindings和ClusterRoleBindings应该只包含执行特定功能所需的一组权限。除非绝对必要，否则请避免在您的Roles和ClusterRoles中使用`["*"]`。如果您不确定要分配哪些权限，可以考虑使用诸如[audit2rbac](https://github.com/liggitt/audit2rbac)之类的工具，根据Kubernetes审计日志中观察到的API调用自动生成Roles和绑定。

### 使用自动化流程创建集群

如前面的步骤所示，在创建Amazon EKS集群时，如果不使用`API_AND_CONFIG_MAP`或`API`身份验证模式，并且没有选择不将`cluster-admin`权限委派给集群创建者，则创建集群的IAM实体用户或角色(如联合用户)将自动在集群的RBAC配置中获得`system:masters`权限。即使作为最佳实践，如[此处](Rremove-the-cluster-admin-permissions-from-the-cluster-creator-principal)所述，如果使用`CONFIG_MAP`身份验证方法依赖`aws-auth`ConfigMap,则无法撤销此访问权限。因此，最好使用与专用IAM角色相关联的基础设施自动化管道来创建集群，该角色没有权限供其他用户或实体承担，并定期审核此角色的权限、策略以及谁有权触发该管道。此外，此角色不应用于对集群执行例行操作，应专门用于通过管道(例如通过SCM代码更改)触发的集群级操作。

### 使用专用IAM角色创建集群

当您创建 Amazon EKS 集群时，创建集群的 IAM 实体用户或角色(如联合用户)将自动在集群的 RBAC 配置中获得 `system:masters` 权限。这种访问权限无法被移除，也不受 `aws-auth` ConfigMap 管理。因此，最好使用专用的 IAM 角色创建集群，并定期审计谁可以扮演该角色。该角色不应用于在集群上执行日常操作，而应通过 `aws-auth` ConfigMap 为此目的授予其他用户访问集群的权限。配置 `aws-auth` ConfigMap 后，应该保护该角色，仅在集群无法访问的情况下临时提升权限/紧急情况下使用。这在未配置直接用户访问的集群中特别有用。

### 定期审计对集群的访问权限

随着时间的推移，需要访问权限的人员可能会发生变化。计划定期审计 `aws-auth` ConfigMap,查看谁被授予了访问权限以及他们被分配的权限。您还可以使用开源工具，如 [kubectl-who-can](https://github.com/aquasecurity/kubectl-who-can) 或 [rbac-lookup](https://github.com/FairwindsOps/rbac-lookup) 来检查绑定到特定服务账户、用户或组的角色。我们将在讨论[审计](detective.md)时进一步探讨这个主题。NCC Group 的这篇[文章](https://www.nccgroup.trust/us/about-us/newsroom-and-events/blog/2019/august/tools-and-methods-for-auditing-kubernetes-rbac-policies/?mkt_tok=eyJpIjoiWWpGa056SXlNV1E0WWpRNSIsInQiOiJBT1hyUTRHYkg1TGxBV0hTZnRibDAyRUZ0VzBxbndnRzNGbTAxZzI0WmFHckJJbWlKdE5WWDdUQlBrYVZpMnNuTFJ1R3hacVYrRCsxYWQ2RTRcL2pMN1BtRVA1ZFZcL0NtaEtIUDdZV3pENzNLcE1zWGVwUndEXC9Pb2tmSERcL1pUaGUifQ%3D%3D)中也有一些其他想法。

### 如果依赖 `aws-auth` configMap,请使用工具进行更改

不当格式化的aws-auth ConfigMap可能会导致您无法访问集群。如果您需要对ConfigMap进行更改，请使用工具。

**eksctl**
`eksctl` CLI包含一个用于向aws-auth ConfigMap添加身份映射的命令。

查看CLI帮助:

```bash
$ eksctl create iamidentitymapping --help
...
```

检查映射到您的Amazon EKS集群的身份。

```bash
$ eksctl get iamidentitymapping --cluster $CLUSTER_NAME --region $AWS_REGION
ARN                                                                   USERNAME                        GROUPS                                                  ACCOUNT
arn:aws:iam::788355785855:role/kube-system-<SELF_GENERATED_UUID>      system:node:{{SessionName}}     system:bootstrappers,system:nodes,system:node-proxier  
```

使IAM角色成为集群管理员:

```bash
$ eksctl create iamidentitymapping --cluster  <CLUSTER_NAME> --region=<region> --arn arn:aws:iam::123456:role/testing --group system:masters --username admin
...
```

有关更多信息，请查看[`eksctl`文档](https://eksctl.io/usage/iam-identity-mappings/)

**[aws-auth](https://github.com/keikoproj/aws-auth) by keikoproj**

keikoproj的`aws-auth`同时包含CLI和Go库。

下载并查看CLI帮助:

```bash
$ go get github.com/keikoproj/aws-auth
...
$ aws-auth help
...
```

或者，使用[krew插件管理器](https://krew.sigs.k8s.io)为kubectl安装`aws-auth`。

```bash
$ kubectl krew install aws-auth
...
$ kubectl aws-auth
...
```

[在GitHub上查看aws-auth文档](https://github.com/keikoproj/aws-auth/blob/master/README.md)以获取更多信息，包括Go库。

**[AWS IAM Authenticator CLI](https://github.com/kubernetes-sigs/aws-iam-authenticator/tree/master/cmd/aws-iam-authenticator)**

`aws-iam-authenticator`项目包含一个用于更新ConfigMap的CLI。

[在GitHub上下载发行版](https://github.com/kubernetes-sigs/aws-iam-authenticator/releases)。

为IAM角色添加集群权限:

```bash
$ ./aws-iam-authenticator add role --rolearn arn:aws:iam::185309785115:role/lil-dev-role-cluster --username lil-dev-user --groups system:masters --kubeconfig ~/.kube/config
...
```

### 认证和访问管理的其他方法

虽然 IAM 是向需要访问 EKS 集群的用户进行身份验证的首选方式，但也可以使用 OIDC 身份提供程序（如 GitHub）通过身份验证代理和 Kubernetes [模拟](https://kubernetes.io/docs/reference/access-authn-authz/authentication/#user-impersonation)来进行身份验证。AWS Open Source 博客上发布了两种此类解决方案的文章：

- [使用 GitHub 凭证对 EKS 进行身份验证](https://aws.amazon.com/blogs/opensource/authenticating-eks-github-credentials-teleport/)
- [使用 kube-oidc-proxy 在多个 EKS 集群之间实现一致的 OIDC 身份验证](https://aws.amazon.com/blogs/opensource/consistent-oidc-authentication-across-multiple-eks-clusters-using-kube-oidc-proxy/)

!!! attention
    EKS 原生支持无需使用代理即可进行 OIDC 身份验证。有关更多信息，请阅读发布博客 [为 Amazon EKS 引入 OIDC 身份提供程序身份验证](https://aws.amazon.com/blogs/containers/introducing-oidc-identity-provider-authentication-amazon-eks/)。有关如何使用 Dex（一种流行的开源 OIDC 提供程序，具有各种不同身份验证方法的连接器）配置 EKS 的示例，请参阅 [使用 Dex 和 dex-k8s-authenticator 对 Amazon EKS 进行身份验证](https://aws.amazon.com/blogs/containers/using-dex-dex-k8s-authenticator-to-authenticate-to-amazon-eks/)。如博客所述，通过 OIDC 提供程序进行身份验证的用户的用户名/组将显示在 Kubernetes 审计日志中。

您也可以使用 [AWS SSO](https://docs.aws.amazon.com/singlesignon/latest/userguide/what-is.html) 将 AWS 与外部身份提供商（如 Azure AD）联合。如果您决定使用它，AWS CLI v2.0 包含一个选项，可以创建一个命名配置文件，从而轻松地将 SSO 会话与当前的 CLI 会话相关联并承担 IAM 角色。请注意，您必须在运行 `kubectl` 之前承担一个角色，因为 IAM 角色用于确定用户的 Kubernetes RBAC 组。

## EKS pod 的身份和凭证

在 Kubernetes 集群中运行的某些应用程序需要获得调用 Kubernetes API 的权限才能正常运行。例如，[AWS Load Balancer Controller](https://github.com/kubernetes-sigs/aws-load-balancer-controller) 需要能够列出服务的端点。控制器还需要能够调用 AWS API 来配置和设置 ALB。在本节中，我们将探讨为 Pod 分配权限和特权的最佳实践。

### Kubernetes 服务账户

服务账户是一种特殊类型的对象，允许您将 Kubernetes RBAC 角色分配给 Pod。在集群中的每个命名空间中都会自动创建一个默认服务账户。当您在命名空间中部署 Pod 时，如果没有引用特定的服务账户，该命名空间的默认服务账户将自动分配给该 Pod，并且该服务账户（JWT）令牌的 Secret 将作为卷挂载到 Pod 的 `/var/run/secrets/kubernetes.io/serviceaccount` 目录下。解码该目录中的服务账户令牌将显示以下元数据：

```json
{
  "iss": "kubernetes/serviceaccount",
  "kubernetes.io/serviceaccount/namespace": "default",
  "kubernetes.io/serviceaccount/secret.name": "default-token-5pv4z",
  "kubernetes.io/serviceaccount/service-account.name": "default",
  "kubernetes.io/serviceaccount/service-account.uid": "3b36ddb5-438c-11ea-9438-063a49b60fba",
  "sub": "system:serviceaccount:default:default"
}
```

默认服务账户对Kubernetes API具有以下权限。

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  annotations:
    rbac.authorization.kubernetes.io/autoupdate: "true"
  creationTimestamp: "2020-01-30T18:13:25Z"
  labels:
    kubernetes.io/bootstrapping: rbac-defaults
  name: system:discovery
  resourceVersion: "43"
  selfLink: /apis/rbac.authorization.k8s.io/v1/clusterroles/system%3Adiscovery
  uid: 350d2ab8-438c-11ea-9438-063a49b60fba
rules:
- nonResourceURLs:
  - /api
  - /api/*
  - /apis
  - /apis/*
  - /healthz
  - /openapi
  - /openapi/*
  - /version
  - /version/
  verbs:
  - get
```

该角色授权未经身份验证和已通过身份验证的用户读取API信息，并被视为可以公开访问。

当运行在Pod中的应用程序调用Kubernetes API时，需要为该Pod分配一个明确授予它调用这些API的权限的服务账户。与用户访问权限指南类似，绑定到服务账户的Role或ClusterRole应该仅限于应用程序运行所需的API资源和方法，不能有其他权限。要使用非默认服务账户，只需将Pod的`spec.serviceAccountName`字段设置为您希望使用的服务账户的名称即可。有关创建服务账户的更多信息，请参阅[https://kubernetes.io/docs/reference/access-authn-authz/rbac/#service-account-permissions]。

!!! note
    在Kubernetes 1.24之前，Kubernetes会自动为每个服务帐户创建一个secret。该secret会被挂载到pod的/var/run/secrets/kubernetes.io/serviceaccount路径下，并被pod用于向Kubernetes API服务器进行身份验证。在Kubernetes 1.24中，服务帐户令牌在pod运行时动态生成，默认情况下仅有效1小时。不会为服务帐户创建secret。如果您有在集群外运行并需要向Kubernetes API进行身份验证的应用程序(例如Jenkins),您需要创建一个类型为`kubernetes.io/service-account-token`的secret，并添加一个引用服务帐户的注解，如`metadata.annotations.kubernetes.io/service-account.name: <SERVICE_ACCOUNT_NAME>`。以这种方式创建的secret不会过期。

### IAM角色服务帐户 (IRSA)

IRSA是一项允许您将IAM角色分配给Kubernetes服务帐户的功能。它通过利用一个名为[服务帐户令牌卷投影](https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/#serviceaccount-token-volume-projection)的Kubernetes功能来实现。当Pod配置了引用IAM角色的服务帐户时，Kubernetes API服务器会在启动时调用集群的公共OIDC发现端点。该端点使用加密方式对Kubernetes颁发的OIDC令牌进行签名，生成的签名令牌将作为卷挂载。该签名令牌允许Pod调用与关联的IAM角色相关的AWS API。当调用AWS API时，AWS SDK会调用`sts:AssumeRoleWithWebIdentity`。在验证令牌签名后，IAM会将Kubernetes颁发的令牌交换为临时AWS角色凭证。

使用IRSA时，重要的是[重用AWS SDK会话](#reuse-aws-sdk-sessions-with-irsa),以避免不必要的AWS STS调用。

解码IRSA的(JWT)令牌将产生类似于下面示例的输出:

```json
{
  "aud": [
    "sts.amazonaws.com"
  ],
  "exp": 1582306514,
  "iat": 1582220114,
  "iss": "https://oidc.eks.us-west-2.amazonaws.com/id/D43CF17C27A865933144EA99A26FB128",
  "kubernetes.io": {
    "namespace": "default",
    "pod": {
      "name": "alpine-57b5664646-rf966",
      "uid": "5a20f883-5407-11ea-a85c-0e62b7a4a436"
    },
    "serviceaccount": {
      "name": "s3-read-only",
      "uid": "a720ba5c-5406-11ea-9438-063a49b60fba"
    }
  },
  "nbf": 1582220114,
  "sub": "system:serviceaccount:default:s3-read-only"
}
```

此特定令牌通过承担 IAM 角色，授予 Pod 对 S3 的只读权限。当应用程序尝试从 S3 读取时，令牌将被交换为临时的 IAM 凭证，类似于这样:

```json
{
    "AssumedRoleUser": {
        "AssumedRoleId": "AROA36C6WWEJULFUYMPB6:abc",
        "Arn": "arn:aws:sts::123456789012:assumed-role/eksctl-winterfell-addon-iamserviceaccount-de-Role1-1D61LT75JH3MB/abc"
    },
    "Audience": "sts.amazonaws.com",
    "Provider": "arn:aws:iam::123456789012:oidc-provider/oidc.eks.us-west-2.amazonaws.com/id/D43CF17C27A865933144EA99A26FB128",
    "SubjectFromWebIdentityToken": "system:serviceaccount:default:s3-read-only",
    "Credentials": {
        "SecretAccessKey": "ORJ+8Adk+wW+nU8FETq7+mOqeA8Z6jlPihnV8hX1",
        "SessionToken": "FwoGZXIvYXdzEGMaDMLxAZkuLpmSwYXShiL9A1S0X87VBC1mHCrRe/pB2oes+l1eXxUYnPJyC9ayOoXMvqXQsomq0xs6OqZ3vaa5Iw1HIyA4Cv1suLaOCoU3hNvOIJ6C94H1vU0siQYk7DIq9Av5RZe+uE2FnOctNBvYLd3i0IZo1ajjc00yRK3v24VRq9nQpoPLuqyH2jzlhCEjXuPScPbi5KEVs9fNcOTtgzbVf7IG2gNiwNs5aCpN4Bv/Zv2A6zp5xGz9cWj2f0aD9v66vX4bexOs5t/YYhwuwAvkkJPSIGvxja0xRThnceHyFHKtj0H+bi/PWAtlI8YJcDX69cM30JAHDdQH+ltm/4scFptW1hlvMaP+WReCAaCrsHrAT+yka7ttw5YlUyvZ8EPog+j6fwHlxmrXM9h1BqdikomyJU00gm1++FJelfP+1zAwcyrxCnbRl3ARFrAt8hIlrT6Vyu8WvWtLxcI8KcLcJQb/LgkW+sCTGlYcY8z3zkigJMbYn07ewTL5Ss7LazTJJa758I7PZan/v3xQHd5DEc5WBneiV3iOznDFgup0VAMkIviVjVCkszaPSVEdK2NU7jtrh6Jfm7bU/3P6ZG+CkyDLIa8MBn9KPXeJd/y+jTk5Ii+fIwO/+mDpGNUribg6TPxhzZ8b/XdZO1kS1gVgqjXyVC+M+BRBh6C4H21w/eMzjCtDIpoxt5rGKL6Nu/IFMipoC4fgx6LIIHwtGYMG7SWQi7OsMAkiwZRg0n68/RqWgLzBt/4pfjSRYuk=",
        "Expiration": "2020-02-20T18:49:50Z",
        "AccessKeyId": "XXXX36C6WWEJUMHA3L7Z"
    }
}
```

作为EKS控制平面的一部分运行的变更Webhook将AWS角色ARN和指向Web身份令牌文件的路径注入到Pod中作为环境变量。这些值也可以手动提供。

```bash
AWS_ROLE_ARN=arn:aws:iam::AWS_ACCOUNT_ID:role/IAM_ROLE_NAME
AWS_WEB_IDENTITY_TOKEN_FILE=/var/run/secrets/eks.amazonaws.com/serviceaccount/token
```

kubelet 会在投射的令牌年龄超过其总 TTL 的 80% 或 24 小时后自动轮换该令牌。AWS SDK 负责在令牌轮换时重新加载令牌。有关 IRSA 的更多信息，请参阅 [https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts-technical-overview.html](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts-technical-overview.html)。

### EKS Pod Identities

[EKS Pod Identities](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html) 是在 2023 年 re:Invent 上推出的一项功能，允许您将 IAM 角色分配给 Kubernetes 服务账户，而无需为您的 AWS 账户中的每个集群配置 Open Id Connect (OIDC) 身份提供程序 (IDP)。要使用 EKS Pod Identity，您必须部署一个作为 DaemonSet pod 在每个合格的工作节点上运行的代理。该代理作为 EKS 插件提供给您，是使用 EKS Pod Identity 功能的先决条件。您的应用程序必须使用[支持的 AWS SDK 版本](https://docs.aws.amazon.com/eks/latest/userguide/pod-id-minimum-sdk.html)才能使用此功能。

当为 Pod 配置了 EKS Pod Identities 时，EKS 将在 `/var/run/secrets/pods.eks.amazonaws.com/serviceaccount/eks-pod-identity-token` 处挂载和刷新 pod identity 令牌。AWS SDK 将使用此令牌与 EKS Pod Identity Agent 通信，该代理使用 pod identity 令牌和代理的 IAM 角色通过调用 [AssumeRoleForPodIdentity API](https://docs.aws.amazon.com/eks/latest/APIReference/API_auth_AssumeRoleForPodIdentity.html) 为您的 pod 创建临时凭证。传递给您的 pod 的 pod identity 令牌是由您的 EKS 集群发布并加密签名的 JWT，其中包含适用于 EKS Pod Identities 的 JWT 声明。

要了解有关 EKS Pod Identities 的更多信息，请参阅[此博客](https://aws.amazon.com/blogs/containers/amazon-eks-pod-identity-a-new-way-for-applications-on-eks-to-obtain-iam-credentials/)。

您无需对应用程序代码进行任何修改即可使用 EKS Pod Identities。支持的 AWS SDK 版本将自动通过使用[凭证提供程序链](https://docs.aws.amazon.com/sdkref/latest/guide/standardized-credentials.html)发现 EKS Pod Identities 提供的凭证。与 IRSA 一样，EKS pod identities 会在您的 pod 中设置变量，指导它们如何查找 AWS 凭证。

#### 使用 EKS Pod Identities 的 IAM 角色

- EKS Pod Identities 只能直接承担与 EKS 集群位于同一 AWS 账户的 IAM 角色。要访问另一个 AWS 账户中的 IAM 角色，您必须通过[在 SDK 配置中配置配置文件](https://docs.aws.amazon.com/sdkref/latest/guide/feature-assume-role-credentials.html)或[在应用程序代码中](https://docs.aws.amazon.com/IAM/latest/UserGuide/sts_example_sts_AssumeRole_section.html)来承担该角色。
- 在为服务账户配置 Pod Identity 关联时，配置 Pod Identity 关联的人员或进程必须对该角色具有 `iam:PassRole` 权限。
- 每个服务账户只能通过 EKS Pod Identities 与一个 IAM 角色关联，但您可以将同一 IAM 角色与多个服务账户关联。
- 与 EKS Pod Identities 一起使用的 IAM 角色必须允许 `pods.eks.amazonaws.com` 服务主体承担它们，_并且_设置会话标签。以下是允许 EKS Pod Identities 使用 IAM 角色的示例角色信任策略：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "pods.eks.amazonaws.com"
      },
      "Action": [
        "sts:AssumeRole",
        "sts:TagSession"
      ],
      "Condition": {
        "StringEquals": {
          "aws:SourceOrgId": "${aws:ResourceOrgId}"
        }
      }
    }
  ]
}
```

AWS建议使用诸如 `aws:SourceOrgId` 之类的条件键来帮助防止[跨服务混淆代理问题](https://docs.aws.amazon.com/IAM/latest/UserGuide/confused-deputy.html#cross-service-confused-deputy-prevention)。在上面的示例角色信任策略中，`ResourceOrgId` 是一个变量，等于AWS账户所属的AWS组织的组织ID。当使用EKS Pod Identities担任角色时，EKS将传入一个等于该值的 `aws:SourceOrgId` 值。

#### ABAC和EKS Pod Identities

当EKS Pod Identities担任IAM角色时，它会设置以下会话标签:

|EKS Pod Identities会话标签 | 值 |
|:--|:--|
|kubernetes-namespace | EKS Pod Identities所关联的pod运行所在的命名空间。|
|kubernetes-service-account | 与EKS Pod Identities关联的Kubernetes服务账户的名称|
|eks-cluster-arn | EKS集群的ARN，例如 `arn:${Partition}:eks:${Region}:${Account}:cluster/${ClusterName}`。集群ARN是唯一的，但如果在同一AWS账户和区域中使用相同名称删除并重新创建集群，它将具有相同的ARN。|
|eks-cluster-name | EKS集群的名称。请注意，在您的AWS账户中，EKS集群名称可能相同，而在其他AWS账户中的EKS集群也可能具有相同名称。|
|kubernetes-pod-name | EKS中的pod名称。|
|kubernetes-pod-uid | EKS中的pod UID。|

这些会话标签允许您使用[基于属性的访问控制(ABAC)](https://docs.aws.amazon.com/IAM/latest/UserGuide/introduction_attribute-based-access-control.html)仅授予特定的kubernetes服务账户访问您的AWS资源的权限。这样做时，非常重要的是要理解kubernetes服务账户仅在命名空间内是唯一的，而kubernetes命名空间仅在EKS集群内是唯一的。这些会话标签可以在AWS策略中使用`aws:PrincipalTag/<tag-key>`全局条件键访问，例如`aws:PrincipalTag/eks-cluster-arn`

例如，如果您想仅授予特定服务账户访问您账户中的AWS资源的权限，并使用IAM或资源策略，您需要检查`eks-cluster-arn`和`kubernetes-namespace`标签以及`kubernetes-service-account`,以确保只有来自预期集群的服务账户才能访问该资源，因为其他集群可能具有相同的`kubernetes-service-accounts`和`kubernetes-namespaces`。

此示例S3存储桶策略仅在`kubernetes-service-account`、`kubernetes-namespace`、`eks-cluster-arn`都符合其预期值时，才授予对附加到该S3存储桶中对象的访问权限，其中EKS集群托管在AWS账户`111122223333`中。

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::111122223333:root"
            },
            "Action": "s3:*",
            "Resource":            [
                "arn:aws:s3:::ExampleBucket/*"
            ],
            "Condition": {
                "StringEquals": {
                    "aws:PrincipalTag/kubernetes-service-account": "s3objectservice",
                    "aws:PrincipalTag/eks-cluster-arn": "arn:aws:eks:us-west-2:111122223333:cluster/ProductionCluster",
                    "aws:PrincipalTag/kubernetes-namespace": "s3datanamespace"
                }
            }
        }
    ]
}
```

### EKS Pod Identities 与 IRSA 的比较

EKS Pod Identities 和 IRSA 都是向 EKS pods 提供临时 AWS 凭证的首选方式。除非您有特定的 IRSA 用例，否则我们建议您在使用 EKS 时使用 EKS Pod Identities。下表有助于比较这两个功能。

|# |EKS Pod Identities | IRSA |
|:--|:--|:--|
|是否需要在您的 AWS 账户中创建 OIDC IDP 的权限?|否|是|
|是否需要为每个集群设置唯一的 IDP |否|是|
|是否设置相关会话标签以用于 ABAC?|是|否|
|是否需要 iam:PassRole 检查?|是|否|
|是否使用您的 AWS 账户的 AWS STS 配额?|否|是|
|是否可以访问其他 AWS 账户 | 间接通过角色链接 | 直接通过 sts:AssumeRoleWithWebIdentity|
|是否与 AWS SDK 兼容 |是|是|
|是否需要在节点上部署 Pod Identity Agent Daemonset? |是|否|

## 为 EKS pods 提供身份和凭证的建议

### 更新 aws-node daemonset 以使用 IRSA

目前，aws-node daemonset 被配置为使用分配给 EC2 实例的角色来为 pod 分配 IP。该角色包括几个 AWS 托管策略，例如 AmazonEKS_CNI_Policy 和 EC2ContainerRegistryReadOnly，这实际上允许节点上运行的**所有**pod 附加/分离 ENI、分配/取消分配 IP 地址或从 ECR 拉取镜像。由于这会给您的集群带来风险，因此建议您更新 aws-node daemonset 以使用 IRSA。可以在本指南的[存储库](https://github.com/aws/aws-eks-best-practices/tree/master/projects/enable-irsa/src)中找到执行此操作的脚本。

aws-node daemonset 目前不支持 EKS Pod Identities。

### 限制对分配给工作节点的实例配置文件的访问

当您使用 IRSA 或 EKS Pod Identities 时，它会更新 pod 的凭证链以首先使用 IRSA 或 EKS Pod Identities，但是，pod _仍然可以继承分配给工作节点的实例配置文件的权限_。使用 IRSA 或 EKS Pod Identities 时，**强烈**建议您阻止访问[实例元数据](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configuring-instance-metadata-service.html),以帮助确保您的应用程序只具有所需的权限，而不是它们的节点。

!!! caution
    阻止访问实例元数据将阻止不使用 IRSA 或 EKS Pod Identities 的 pod 继承分配给工作节点的角色。

您可以通过要求实例仅使用 IMDSv2 并将跃点计数更新为 1 来阻止访问实例元数据，如下例所示。您还可以在节点组的启动模板中包含这些设置。请**不要**禁用实例元数据，因为这将阻止依赖实例元数据的组件(如节点终止处理程序等)正常工作。

```bash
$ aws ec2 modify-instance-metadata-options --instance-id <value> --http-tokens required --http-put-response-hop-limit 1
...
```

如果您使用 Terraform 为 Managed Node Groups 创建启动模板，请添加元数据块以配置跃点数，如以下代码片段所示:

``` tf hl_lines="7"
resource "aws_launch_template" "foo" {
  name = "foo"
  ...
    metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }
  ...
```

您还可以通过在节点上操作 iptables 来阻止 pod 访问 EC2 元数据。有关此方法的更多信息，请参阅[限制访问实例元数据服务](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instancedata-data-retrieval.html#instance-metadata-limiting-access)。

如果您的应用程序使用的是不支持 IRSA 或 EKS Pod Identities 的旧版 AWS SDK，您应该更新 SDK 版本。

### 将 IRSA 角色的 IAM 角色信任策略范围缩小到服务帐户名称、命名空间和集群

信任策略可以缩小到命名空间或命名空间中的特定服务帐户。使用 IRSA 时，最好通过包含服务帐户名称来使角色信任策略尽可能明确。这将有效防止同一命名空间中的其他 Pod 承担该角色。CLI `eksctl` 在您使用它创建服务帐户/IAM 角色时会自动执行此操作。有关更多信息，请参阅 [https://eksctl.io/usage/iamserviceaccounts/](https://eksctl.io/usage/iamserviceaccounts/)。

在直接使用 IAM 时，这是在角色的信任策略中添加条件，使用条件来确保 `:sub` 声明是您期望的命名空间和服务帐户。例如，在此之前，我们有一个 IRSA 令牌，其 sub 声明为 "system:serviceaccount:default:s3-read-only"。这是 `default` 命名空间，服务帐户是 `s3-read-only`。您可以使用以下条件来确保只有您集群中给定命名空间中的服务帐户才能担任该角色:

```json
  "Condition": {
      "StringEquals": {
          "oidc.eks.us-west-2.amazonaws.com/id/D43CF17C27A865933144EA99A26FB128:aud": "sts.amazonaws.com",
          "oidc.eks.us-west-2.amazonaws.com/id/D43CF17C27A865933144EA99A26FB128:sub": "system:serviceaccount:default:s3-read-only"
      }
  }
```

### 为每个应用程序使用一个 IAM 角色

对于 IRSA 和 EKS Pod Identity 而言，最佳实践是为每个应用程序提供自己的 IAM 角色。这可以提高隔离性，因为您可以修改一个应用程序而不影响另一个应用程序，并允许您应用最小权限原则，只为应用程序授予它所需的权限。

在使用 EKS Pod Identity 的 ABAC 时，您可以跨多个服务帐户使用通用 IAM 角色，并依赖其会话属性进行访问控制。当大规模运行时，这尤其有用，因为 ABAC 允许您使用更少的 IAM 角色进行操作。

### 当您的应用程序需要访问 IMDS 时，请使用 IMDSv2 并将 EC2 实例上的跃点限制增加到 2

IMDSv2 (https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configuring-instance-metadata-service.html) 需要您使用 PUT 请求来获取会话令牌。初始 PUT 请求必须包含会话令牌的 TTL。较新版本的 AWS SDK 将自动处理此操作和续订该令牌。同时也很重要注意到，EC2 实例上的默认跃点限制有意设置为 1，以防止 IP 转发。因此，在 EC2 实例上运行并请求会话令牌的 Pod 最终可能会超时并回退到使用 IMDSv1 数据流。EKS 通过启用 v1 和 v2 并将由 eksctl 或使用官方 CloudFormation 模板供应的节点上的跃点限制更改为 2，从而支持 IMDSv2。

### 禁用自动挂载服务帐户令牌

如果您的应用程序不需要调用 Kubernetes API，请在应用程序的 PodSpec 中将 `automountServiceAccountToken` 属性设置为 `false`,或者在每个命名空间中修补默认服务帐户，使其不再自动挂载到 Pod。例如:

```bash
kubectl patch serviceaccount default -p $'automountServiceAccountToken: false'
```

### 为每个应用程序使用专用服务帐户

每个应用程序都应该有自己专用的服务帐户。这适用于 Kubernetes API 的服务帐户以及 IRSA 和 EKS Pod Identity。

!!! attention
    如果在使用 IRSA 时采用蓝/绿集群升级方式而不是就地集群升级，您将需要使用新集群的 OIDC 端点更新每个 IRSA IAM 角色的信任策略。蓝/绿集群升级是指在旧集群旁边创建一个运行较新版本 Kubernetes 的新集群，并使用负载均衡器或服务网格将运行在旧集群上的服务的流量无缝切换到新集群。
    在使用 EKS Pod Identity 进行蓝/绿集群升级时，您需要在新集群中创建 pod identity 关联，将 IAM 角色与服务账户关联。如果您有 `sourceArn` 条件，还需要更新 IAM 角色信任策略。

### 以非 root 用户身份运行应用程序

容器默认以 root 身份运行。虽然这允许它们读取 Web 身份令牌文件，但以 root 身份运行容器不被视为最佳实践。作为替代方案，请考虑在 PodSpec 中添加 `spec.securityContext.runAsUser` 属性。`runAsUser` 的值是任意值。

在以下示例中，Pod 中的所有进程都将以 `runAsUser` 字段中指定的用户 ID 运行。

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: security-context-demo
spec:
  securityContext:
    runAsUser: 1000
    runAsGroup: 3000
  containers:
  - name: sec-ctx-demo
    image: busybox
    command: [ "sh", "-c", "sleep 1h" ]
```

当您以非 root 用户身份运行容器时，它会阻止容器读取 IRSA 服务账户令牌，因为令牌默认被分配了 0600 [root] 权限。如果您将容器的 securityContext 更新为包含 fsgroup=65534 [Nobody],它将允许容器读取令牌。

```yaml
spec:
  securityContext:
    fsGroup: 65534
```

在 Kubernetes 1.19 及更高版本中，不再需要进行此更改，应用程序可以在不将它们添加到 Nobody 组中的情况下读取 IRSA 服务账户令牌。

### 授予应用程序最小特权访问权限

[Action Hero](https://github.com/princespaghetti/actionhero) 是一个可以与您的应用程序一起运行的实用程序，用于识别您的应用程序需要正常运行所需的 AWS API 调用和相应的 IAM 权限。它类似于 [IAM Access Advisor](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_access-advisor.html)，可帮助您逐步限制分配给应用程序的 IAM 角色的范围。有关授予 AWS 资源[最小特权访问](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html#grant-least-privilege)的更多信息，请参阅相关文档。

考虑为使用 IRSA 和 Pod Identities 的 IAM 角色设置[权限边界](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_boundaries.html)。您可以使用权限边界来确保 IRSA 或 Pod Identities 使用的角色无法超过最大权限级别。有关使用示例权限边界策略开始使用权限边界的示例指南，请参阅此 [github 仓库](https://github.com/aws-samples/example-permissions-boundary)。

### 审查并撤销对您的 EKS 集群的不必要的匿名访问

理想情况下，应该为所有 API 操作禁用匿名访问。通过为 Kubernetes 内置用户 system:anonymous 创建 RoleBinding 或 ClusterRoleBinding 来授予匿名访问。您可以使用 [rbac-lookup](https://github.com/FairwindsOps/rbac-lookup) 工具来识别 system:anonymous 用户在您的集群上拥有的权限：

```bash
./rbac-lookup | grep -P 'system:(anonymous)|(unauthenticated)'
system:anonymous               cluster-wide        ClusterRole/system:discovery
system:unauthenticated         cluster-wide        ClusterRole/system:discovery
system:unauthenticated         cluster-wide        ClusterRole/system:public-info-viewer
```

除 system:public-info-viewer 之外的任何角色或 ClusterRole 都不应绑定到 system:anonymous 用户或 system:unauthenticated 组。

在某些特定的API上启用匿名访问可能存在一些合理的原因。如果您的集群属于这种情况，请确保只有那些特定的API可被匿名用户访问，并且在不进行身份验证的情况下暴露这些API不会使您的集群面临风险。

在Kubernetes/EKS 1.14版本之前，system:unauthenticated组默认与system:discovery和system:basic-user ClusterRoles相关联。请注意，即使您已将集群更新到1.14或更高版本，这些权限可能仍在您的集群上启用，因为集群更新不会撤销这些权限。
要检查除system:public-info-viewer之外哪些ClusterRoles具有"system:unauthenticated",您可以运行以下命令(需要jq工具):

```bash
kubectl get ClusterRoleBinding -o json | jq -r '.items[] | select(.subjects[]?.name =="system:unauthenticated") | select(.metadata.name != "system:public-info-viewer") | .metadata.name'
```

并且可以使用以下命令从除"system:public-info-viewer"之外的所有角色中删除"system:unauthenticated":

```bash
kubectl get ClusterRoleBinding -o json | jq -r '.items[] | select(.subjects[]?.name =="system:unauthenticated") | select(.metadata.name != "system:public-info-viewer") | del(.subjects[] | select(.name =="system:unauthenticated"))' | kubectl apply -f -
```

或者，您可以通过kubectl describe和kubectl edit手动检查和删除。要检查system:unauthenticated组在您的集群上是否具有system:discovery权限，请运行以下命令:

```bash
kubectl describe clusterrolebindings system:discovery

Name:         system:discovery
Labels:       kubernetes.io/bootstrapping=rbac-defaults
Annotations:  rbac.authorization.kubernetes.io/autoupdate: true
Role:
  Kind:  ClusterRole
  Name:  system:discovery
Subjects:
  Kind   Name                    Namespace
  ----   ----                    ---------
  Group  system:authenticated
  Group  system:unauthenticated
```

要检查系统:unauthenticated组在集群上是否具有system:basic-user权限，请运行以下命令:

```bash
kubectl describe clusterrolebindings system:basic-user

Name:         system:basic-user
Labels:       kubernetes.io/bootstrapping=rbac-defaults
Annotations:  rbac.authorization.kubernetes.io/autoupdate: true
Role:
  Kind:  ClusterRole
  Name:  system:basic-user
Subjects:
  Kind   Name                    Namespace
  ----   ----                    ---------
  Group  system:authenticated
  Group  system:unauthenticated
```

如果系统:unauthenticated组在集群上绑定到system:discovery和/或system:basic-user ClusterRoles,您应该取消这些角色与系统:unauthenticated组的关联。使用以下命令编辑system:discovery ClusterRoleBinding:

```bash
kubectl edit clusterrolebindings system:discovery
```

上述命令将在编辑器中打开system:discovery ClusterRoleBinding的当前定义，如下所示:

```yaml
# Please edit the object below. Lines beginning with a '#' will be ignored,
# and an empty file will abort the edit. If an error occurs while saving this file will be
# reopened with the relevant failures.
#
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  annotations:
    rbac.authorization.kubernetes.io/autoupdate: "true"
  creationTimestamp: "2021-06-17T20:50:49Z"
  labels:
    kubernetes.io/bootstrapping: rbac-defaults
  name: system:discovery
  resourceVersion: "24502985"
  selfLink: /apis/rbac.authorization.k8s.io/v1/clusterrolebindings/system%3Adiscovery
  uid: b7936268-5043-431a-a0e1-171a423abeb6
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: system:discovery
subjects:
- apiGroup: rbac.authorization.k8s.io
  kind: Group
  name: system:authenticated
- apiGroup: rbac.authorization.k8s.io
  kind: Group
  name: system:unauthenticated
```

从上面的编辑器屏幕中的"subjects"部分删除system:unauthenticated组的条目。

对于 system:basic-user ClusterRoleBinding 重复相同的步骤。

### 使用 IRSA 重用 AWS SDK 会话

当您使用 IRSA 时，使用 AWS SDK 编写的应用程序会使用传递到您的 Pod 的令牌调用 `sts:AssumeRoleWithWebIdentity` 来生成临时 AWS 凭证。这与其他 AWS 计算服务不同，在其他 AWS 计算服务中，计算服务会直接将临时 AWS 凭证传递给 AWS 计算资源，例如 Lambda 函数。这意味着每次初始化 AWS SDK 会话时，都会调用 AWS STS 进行 `AssumeRoleWithWebIdentity`。如果您的应用程序快速扩展并初始化了许多 AWS SDK 会话，您可能会遇到来自 AWS STS 的节流，因为您的代码将为 `AssumeRoleWithWebIdentity` 发出许多调用。

为了避免这种情况，我们建议在您的应用程序中重用 AWS SDK 会话，以避免对 `AssumeRoleWithWebIdentity` 进行不必要的调用。

在以下示例代码中，使用 boto3 python SDK 创建了一个会话，并使用同一个会话创建客户端与 Amazon S3 和 Amazon SQS 进行交互。只调用一次 `AssumeRoleWithWebIdentity`，AWS SDK 会在 `my_session` 的凭证过期时自动刷新。

```py hl_lines="4 7 8"  
import boto3

# 创建您自己的会话
my_session = boto3.session.Session()

# 现在我们可以从会话创建低级别的客户端
sqs = my_session.client('sqs')
s3 = my_session.client('s3')

s3response = s3.list_buckets()
sqsresponse = sqs.list_queues()


#打印来自 S3 和 SQS API 的响应
print("s3 响应:")
print(s3response)
print("---")
print("sqs 响应:")
print(sqsresponse)
```

如果您正在将应用程序从其他 AWS 计算服务（如 EC2）迁移到使用 IRSA 的 EKS，这是一个特别重要的细节。在其他计算服务上，初始化 AWS SDK 会话不会调用 AWS STS，除非您指示它这样做。

### 替代方法

虽然 IRSA 和 EKS Pod Identities 是为 pod 分配 AWS 身份的_首选方式_，但它们需要您在应用程序中包含最新版本的 AWS SDK。有关当前支持 IRSA 的 SDK 的完整列表，请参阅 [https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts-minimum-sdk.html](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts-minimum-sdk.html)，对于 EKS Pod Identities，请参阅 [https://docs.aws.amazon.com/eks/latest/userguide/pod-id-minimum-sdk.html](https://docs.aws.amazon.com/eks/latest/userguide/pod-id-minimum-sdk.html)。如果您有一个暂时无法使用兼容 SDK 更新的应用程序，社区提供了几种为 Kubernetes pod 分配 IAM 角色的解决方案，包括 [kube2iam](https://github.com/jtblin/kube2iam) 和 [kiam](https://github.com/uswitch/kiam)。尽管 AWS 不支持、认可或支持使用这些解决方案，但它们经常被广大社区用来实现与 IRSA 和 EKS Pod Identities 类似的结果。

如果您需要使用这些非 AWS 提供的解决方案，请务必谨慎行事并确保您了解这样做的安全影响。

## 工具和资源

- [Amazon EKS 安全沉浸式研讨会 - 身份和访问管理](https://catalog.workshops.aws/eks-security-immersionday/en-US/2-identity-and-access-management)
- [Terraform EKS 蓝图模式 - 完全私有 Amazon EKS 集群](https://github.com/aws-ia/terraform-aws-eks-blueprints/tree/main/patterns/fully-private-cluster)
- [Terraform EKS 蓝图模式 - IAM 身份中心单点登录用于 Amazon EKS 集群](https://github.com/aws-ia/terraform-aws-eks-blueprints/tree/main/patterns/sso-iam-identity-center)
- [Terraform EKS 蓝图模式 - Okta 单点登录用于 Amazon EKS 集群](https://github.com/aws-ia/terraform-aws-eks-blueprints/tree/main/patterns/sso-okta)
- [audit2rbac](https://github.com/liggitt/audit2rbac)
- [rbac.dev](https://github.com/mhausenblas/rbac.dev) 一个包含博客和工具的额外资源列表，用于 Kubernetes RBAC
- [Action Hero](https://github.com/princespaghetti/actionhero)
- [kube2iam](https://github.com/jtblin/kube2iam)
- [kiam](https://github.com/uswitch/kiam)