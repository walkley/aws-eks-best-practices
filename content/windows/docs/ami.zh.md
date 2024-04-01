# Amazon EKS 优化的 Windows AMI 管理
Windows Amazon EKS 优化的 AMI 是基于 Windows Server 2019 和 Windows Server 2022 构建的。它们被配置为 Amazon EKS 节点的基础镜像。默认情况下，AMI 包括以下组件:
- [kubelet](https://kubernetes.io/docs/reference/command-line-tools-reference/kubelet/)
- [kube-proxy](https://kubernetes.io/docs/reference/command-line-tools-reference/kube-proxy/)
- [AWS IAM Authenticator for Kubernetes](https://github.com/kubernetes-sigs/aws-iam-authenticator)
- [csi-proxy](https://github.com/kubernetes-csi/csi-proxy)
- [containerd](https://containerd.io/)

您可以通过查询 AWS Systems Manager Parameter Store API 以编程方式检索 Amazon EKS 优化的 AMI ID。此参数消除了您手动查找 Amazon EKS 优化的 AMI ID 的需求。有关 Systems Manager Parameter Store API 的更多信息，请参阅 [GetParameter](https://docs.aws.amazon.com/systems-manager/latest/APIReference/API_GetParameter.html)。您的用户账户必须具有 ssm:GetParameter IAM 权限才能检索 Amazon EKS 优化的 AMI 元数据。

以下示例检索 Windows Server 2019 LTSC Core 的最新 Amazon EKS 优化 AMI 的 AMI ID。AMI 名称中列出的版本号与相应的准备就绪的 Kubernetes 版本有关。

```bash    
aws ssm get-parameter --name /aws/service/ami-windows-latest/Windows_Server-2019-English-Core-EKS_Optimized-1.21/image_id --region us-east-1 --query "Parameter.Value" --output text
```

示例输出:

```
ami-09770b3eec4552d4e
```

## 管理您自己的 Amazon EKS 优化的 Windows AMI

生产环境的一个重要步骤是在整个 Amazon EKS 集群中维护相同的 Amazon EKS 优化的 Windows AMI 和 kubelet 版本。

在整个 Amazon EKS 集群中使用相同版本可减少故障排除时间并提高集群一致性。[Amazon EC2 Image Builder](https://aws.amazon.com/image-builder/) 有助于创建和维护自定义的 Amazon EKS 优化 Windows AMI，以便在 Amazon EKS 集群中使用。

使用 Amazon EC2 Image Builder 可在 Windows Server 版本、AWS Windows Server AMI 发布日期和/或操作系统版本之间进行选择。在构建组件步骤中，您可以选择现有的 EKS 优化 Windows 工件以及 kubelet 版本。更多信息:https://docs.aws.amazon.com/eks/latest/userguide/eks-custom-ami-windows.html

![](./images/build-components.png)

**注意:** 在选择基础映像之前，请参阅 [Windows Server 版本和许可证](licensing.md) 部分，了解有关发布渠道更新的重要详细信息。

## 配置自定义 EKS 优化 AMI 的更快启动 ##

使用自定义 Windows Amazon EKS 优化 AMI 时，通过启用快速启动功能，Windows 工作节点可以加快高达 65% 的启动速度。此功能维护一组预置的快照，其中已完成 _Sysprep 专用化_、_Windows 开箱体验 (OOBE)_ 步骤和所需的重新启动。随后启动时将使用这些快照，从而减少扩展或替换节点所需的时间。只能通过 EC2 控制台或 AWS CLI 为*您拥有的* AMI 启用快速启动，并且可以配置维护的快照数量。

**注意:** 快速启动与默认的 Amazon 提供的 EKS 优化 AMI 不兼容，请在尝试启用它之前创建上述自定义 AMI。

更多信息: [AWS Windows AMI - 配置 AMI 以实现更快的启动](https://docs.aws.amazon.com/AWSEC2/latest/WindowsGuide/windows-ami-version-history.html#win-ami-config-fast-launch)

## 在自定义 AMI 上缓存 Windows 基础层 ##

Windows 容器镜像比其 Linux 对应镜像更大。如果您运行任何基于 .NET Framework 的容器化应用程序，平均镜像大小约为 8.24GB。在 pod 调度期间，必须在磁盘上完全拉取和解压容器镜像，然后 pod 才能达到 Running 状态。

在此过程中，容器运行时 (containerd) 会在磁盘上拉取和解压整个容器镜像。拉取操作是并行进行的，这意味着容器运行时会并行拉取容器镜像层。相比之下，解压操作是按顺序进行的，而且是 I/O 密集型的。因此，容器镜像需要超过 8 分钟才能完全解压并准备好供容器运行时 (containerd) 使用，从而导致 pod 启动时间可能需要几分钟。

如 **Patching Windows Server and Container** 主题中所述，有一个选项可以使用 EKS 构建自定义 AMI。在准备 AMI 期间，您可以添加一个额外的 EC2 Image Builder 组件来本地拉取所有必需的 Windows 容器镜像，然后生成 AMI。这种策略将大大缩短 pod 达到 **Running** 状态所需的时间。

在 Amazon EC2 Image Builder 上，创建一个[组件](https://docs.aws.amazon.com/imagebuilder/latest/userguide/manage-components.html)来下载必需的镜像，并将其附加到 Image Recipe。以下示例从 ECR 存储库中拉取特定镜像。

```
name: ContainerdPull
description: This component pulls the necessary containers images for a cache strategy.
schemaVersion: 1.0

阶段:
  - 名称: 构建
    步骤:
      - 名称: containerdpull
        操作: ExecutePowerShell
        输入:
          命令:
            - Set-ExecutionPolicy Unrestricted -Force
            - (Get-ECRLoginCommand).Password | docker login --username AWS --password-stdin 111000111000.dkr.ecr.us-east-1.amazonaws.com
            - ctr image pull mcr.microsoft.com/dotnet/framework/aspnet:latest
            - ctr image pull 111000111000.dkr.ecr.us-east-1.amazonaws.com/myappcontainerimage:latest
```

为确保以下组件按预期工作，请检查EC2 Image Builder (EC2InstanceProfileForImageBuilder)使用的IAM角色是否附加了以下策略:

![](./images/permissions-policies.png)

## 博客文章 ##
在以下博客文章中，您将找到有关如何为自定义Amazon EKS Windows AMI实现缓存策略的分步说明:

[使用EC2 Image Builder和镜像缓存策略加快Windows容器启动时间](https://aws.amazon.com/blogs/containers/speeding-up-windows-container-launch-times-with-ec2-image-builder-and-image-cache-strategy/)