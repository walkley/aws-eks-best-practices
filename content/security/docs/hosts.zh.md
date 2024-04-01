# 保护基础设施 (主机)

虽然确保容器镜像的安全性很重要，但同样重要的是要保护运行它们的基础设施。本节探讨了缓解直接针对主机发起攻击风险的不同方式。这些指导方针应与 [运行时安全](runtime.md) 一节中概述的指导方针一起使用。

## 建议

### 使用针对运行容器进行了优化的操作系统

考虑使用 Flatcar Linux、Project Atomic、RancherOS 和 [Bottlerocket](https://github.com/bottlerocket-os/bottlerocket/)，这是 AWS 专门为运行 Linux 容器而设计的特殊操作系统。它包括减小的攻击面、在启动时验证的磁盘映像，以及使用 SELinux 强制执行的权限边界。

或者，对于您的 Kubernetes 工作节点使用 [EKS 优化的 AMI][eks-ami]。EKS 优化的 AMI 会定期发布，并包含运行容器化工作负载所需的最小操作系统包和二进制文件集。

[eks-ami]: https://docs.aws.amazon.com/eks/latest/userguide/eks-optimized-amis.html

请参阅 [Amazon EKS AMI RHEL 构建规范](https://github.com/aws-samples/amazon-eks-ami-rhel),其中包含一个示例配置脚本，可用于使用 Hashicorp Packer 在 Red Hat Enterprise Linux 上构建自定义 Amazon EKS AMI。此脚本可以进一步用于构建符合 STIG 的 EKS 自定义 AMI。

### 保持工作节点操作系统的更新

无论您使用 Bottlerocket 等针对容器优化的主机操作系统，还是使用 EKS 优化的 AMI 等较大但仍然简约的 Amazon Machine Image，最佳实践是使这些主机操作系统镜像保持最新的安全补丁。

对于 EKS 优化的 AMI，请定期查看 [变更日志][eks-ami-changes] 和/或 [发布说明频道][eks-ami-releases],并自动将更新的工作节点镜像部署到您的集群中。

### 将您的基础设施视为不可变的，并自动替换工作节点

当新的补丁或更新可用时，请不要执行就地升级，而是替换您的工作节点。可以通过以下几种方式来实现。您可以使用最新的 AMI 向现有的自动伸缩组添加实例，同时按顺序隔离和排空节点，直到该组中的所有节点都已使用最新的 AMI 进行了替换。或者，您可以在新的节点组中添加实例，同时按顺序从旧的节点组中隔离和排空节点，直到所有节点都已替换。EKS [托管节点组](https://docs.aws.amazon.com/eks/latest/userguide/managed-node-groups.html)使用第一种方法，当新的 AMI 可用时，将在控制台中显示一条消息来升级您的工作节点。`eksctl` 还提供了一种机制，用于使用最新的 AMI 创建节点组，并在终止实例之前优雅地隔离和排空节点组中的 Pod。如果您决定使用其他方法来替换工作节点，我们强烈建议您自动化该过程，以最大程度减少人工监督，因为您可能需要定期替换工作节点，因为新的更新/补丁发布时以及控制平面升级时都需要进行替换。

使用 EKS Fargate，AWS 将在有更新可用时自动更新底层基础设施。大多数情况下，这可以无缝完成，但有时更新可能会导致您的 Pod 被重新调度。因此，我们建议在将应用程序作为 Fargate Pod 运行时创建具有多个副本的部署。

### 定期运行 kube-bench 以验证是否符合 [Kubernetes CIS 基准](https://www.cisecurity.org/benchmark/kubernetes/)

kube-bench 是 Aqua 的一个开源项目，用于根据 CIS Kubernetes 基准评估您的集群。该基准描述了确保非托管 Kubernetes 集群安全的最佳实践。CIS Kubernetes 基准涵盖了控制平面和数据平面。由于 Amazon EKS 提供了完全托管的控制平面，因此并非 CIS Kubernetes 基准中的所有建议都适用。为确保此范围反映了 Amazon EKS 的实现方式，AWS 创建了 *CIS Amazon EKS 基准*。EKS 基准继承自 CIS Kubernetes 基准，并结合了社区的其他输入，特别考虑了 EKS 集群的配置。

在 EKS 集群上运行 [kube-bench](https://github.com/aquasecurity/kube-bench) 时，请按照 Aqua Security 的[这些说明](https://github.com/aquasecurity/kube-bench/blob/main/docs/running.md#running-cis-benchmark-in-an-eks-cluster)操作。更多信息，请参阅[介绍 CIS Amazon EKS 基准](https://aws.amazon.com/blogs/containers/introducing-cis-amazon-eks-benchmark/)。

### 最小化对工作节点的访问

与其启用 SSH 访问，不如在需要远程访问主机时使用 [SSM Session Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html)。与可能丢失、复制或共享的 SSH 密钥不同，Session Manager 允许您使用 IAM 控制对 EC2 实例的访问。此外，它还提供了审计跟踪和在实例上运行的命令的日志。

截至 2020 年 8 月 19 日，托管节点组支持自定义 AMI 和 EC2 启动模板。这允许您将 SSM 代理嵌入到 AMI 中，或在引导工作节点时安装它。如果您不想修改优化 AMI 或 ASG 的启动模板，您可以使用 DaemonSet 安装 SSM 代理，如[此示例](https://github.com/aws-samples/ssm-agent-daemonset-installer)所示。

#### 基于 SSM 的 SSH 访问的最小 IAM 策略

AWS 托管策略 `AmazonSSMManagedInstanceCore` 包含了一些不需要的权限，如果您只是想避免 SSH 访问而使用 SSM Session Manager / SSM RunCommand 的话。具体来说，`ssm:GetParameter(s)` 的 `*` 权限会让该角色能够访问参数存储中的所有参数(包括使用 AWS 托管 KMS 密钥配置的 SecureStrings)。

以下 IAM 策略包含了通过 SSM Systems Manager 启用节点访问所需的最小权限集合。

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "EnableAccessViaSSMSessionManager",
      "Effect": "Allow",
      "Action": [
        "ssmmessages:OpenDataChannel",
        "ssmmessages:OpenControlChannel",
        "ssmmessages:CreateDataChannel",
        "ssmmessages:CreateControlChannel",
        "ssm:UpdateInstanceInformation"
      ],
      "Resource": "*"
    },
    {
      "Sid": "EnableSSMRunCommand",
      "Effect": "Allow",
      "Action": [
        "ssm:UpdateInstanceInformation",
        "ec2messages:SendReply",
        "ec2messages:GetMessages",
        "ec2messages:GetEndpoint",
        "ec2messages:FailMessage",
        "ec2messages:DeleteMessage",
        "ec2messages:AcknowledgeMessage"
      ],
      "Resource": "*"
    }
  ]
}
```

配置好该策略并安装 [Session Manager 插件](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html)后，您就可以运行

```bash
aws ssm start-session --target [EKS_节点的_INSTANCE_ID]
```

来访问节点。

!!! note
    您也可以考虑添加 [启用 Session Manager 日志记录](https://docs.aws.amazon.com/systems-manager/latest/userguide/getting-started-create-iam-instance-profile.html#create-iam-instance-profile-ssn-logging) 的权限。

### 将 worker 节点部署到私有子网

通过将工作节点部署到私有子网，可以最大程度地减少它们暴露在互联网上的风险，因为攻击通常来自互联网。从2020年4月22日开始，在托管节点组中分配给节点的公有IP地址将由它们所部署到的子网来控制。在此之前，托管节点组中的节点会自动分配公有IP。如果您选择将工作节点部署到公有子网，请实施严格的AWS安全组规则来限制它们的暴露。

### 运行Amazon Inspector来评估主机暴露、漏洞以及与最佳实践的偏差

您可以使用[Amazon Inspector](https://docs.aws.amazon.com/inspector/latest/user/what-is-inspector.html)来检查您的节点是否存在意外的网络访问以及底层Amazon EC2实例上的漏洞。

只有在安装并启用Amazon EC2 Systems Manager (SSM) 代理的情况下，Amazon Inspector才能为您的Amazon EC2实例提供常见漏洞和暴露(CVE)数据。该代理预装在多个[Amazon Machine Images (AMIs)](https://docs.aws.amazon.com/systems-manager/latest/userguide/ami-preinstalled-agent.html)上，包括[EKS优化的Amazon Linux AMIs](https://docs.aws.amazon.com/eks/latest/userguide/eks-optimized-ami.html)。无论SSM代理状态如何，所有Amazon EC2实例都会被扫描以检查网络可达性问题。有关为Amazon EC2配置扫描的更多信息，请参阅[扫描Amazon EC2实例](https://docs.aws.amazon.com/inspector/latest/user/enable-disable-scanning-ec2.html)。

!!! attention
    Inspector无法在用于运行Fargate pod的基础设施上运行。

## 替代方案

### 运行SELinux

!!! info
    可用于Red Hat Enterprise Linux (RHEL)、CentOS、Bottlerocket和Amazon Linux 2023

SELinux提供了一个额外的安全层，用于隔离容器与容器之间以及容器与主机之间的访问。SELinux允许管理员对每个用户、应用程序、进程和文件强制执行强制访问控制(MAC)。可以将其视为一种后备措施，根据一组标签限制对特定资源的操作。在EKS上，SELinux可用于防止容器访问彼此的资源。

容器SELinux策略在[container-selinux](https://github.com/containers/container-selinux)包中定义。Docker CE需要此包(及其依赖项),以便由Docker(或其他容器运行时)创建的进程和文件以有限的系统访问权限运行。容器利用了`container_t`标签，这是`svirt_lxc_net_t`的别名。这些策略有效地防止了容器访问主机的某些功能。

当您为Docker配置SELinux时，Docker会自动将工作负载标记为`container_t`类型，并为每个容器分配一个唯一的MCS级别。这将隔离容器彼此之间。如果您需要更宽松的限制，您可以在SElinux中创建自己的配置文件，该配置文件授予容器访问文件系统特定区域的权限。这类似于PSP，您可以为不同的容器/pod创建不同的配置文件。例如，您可以为一般工作负载设置一组限制性控制，为需要特权访问的工作负载设置另一组控制。

容器的SELinux有一组可配置的选项，用于修改默认限制。根据您的需求，可以启用或禁用以下SELinux布尔值:

| 布尔值 | 默认值 | 描述 |
|---|:--:|---|
| `container_connect_any` | `off` | 允许容器访问主机上的特权端口。例如，如果您有一个需要映射到主机上的443或80端口的容器。|
| `container_manage_cgroup` | `off` | 允许容器管理cgroup配置。例如，运行systemd的容器将需要启用此选项。|
| `container_use_cephfs` | `off` | 允许容器使用ceph文件系统。|

默认情况下，容器被允许在 `/usr` 下读/执行，并从 `/etc` 读取大部分内容。位于 `/var/lib/docker` 和 `/var/lib/containers` 下的文件具有 `container_var_lib_t` 标签。要查看默认标签的完整列表，请参阅 [container.fc](https://github.com/containers/container-selinux/blob/master/container.fc) 文件。

```bash
docker container run -it \
  -v /var/lib/docker/image/overlay2/repositories.json:/host/repositories.json \
  centos:7 cat /host/repositories.json
# cat: /host/repositories.json: 权限被拒绝

docker container run -it \
  -v /etc/passwd:/host/etc/passwd \
  centos:7 cat /host/etc/passwd
# cat: /host/etc/passwd: 权限被拒绝
```

标记为 `container_file_t` 的文件是容器唯一可写的文件。如果您希望卷挂载可写，您将需要在末尾指定 `:z` 或 `:Z`。

- `:z` 将重新标记文件，以便容器可以读/写
- `:Z` 将重新标记文件，以便**只有**容器可以读/写

```bash
ls -Z /var/lib/misc
# -rw-r--r--. root root system_u:object_r:var_lib_t:s0   postfix.aliasesdb-stamp

docker container run -it \
  -v /var/lib/misc:/host/var/lib/misc:z \
  centos:7 echo "重新标记!"

ls -Z /var/lib/misc
#-rw-r--r--. root root system_u:object_r:container_file_t:s0 postfix.aliasesdb-stamp
```

```bash
docker container run -it \
  -v /var/log:/host/var/log:Z \
  fluentbit:latest
```

在Kubernetes中，重新标记略有不同。不是让Docker自动重新标记文件，而是可以指定一个自定义的MCS标签来运行pod。支持重新标记的卷将自动重新标记，以便可以访问它们。具有匹配MCS标签的Pod将能够访问该卷。如果需要严格隔离，请为每个Pod设置不同的MCS标签。

```yaml
securityContext:
  seLinuxOptions:
    # Provide a unique MCS label per container
    # You can specify user, role, and type also
    # enforcement based on type and level (svert)
    level: s0:c144:c154
```

在此示例中，`s0:c144:c154`对应于分配给容器允许访问的文件的MCS标签。

在EKS上，您可以创建允许特权容器(如FluentD)运行的策略，并创建SELinux策略以允许它从主机上的/var/log读取，而无需重新标记主机目录。具有相同标签的Pod将能够访问相同的主机卷。

我们已经实现了[Amazon EKS的示例AMI](https://github.com/aws-samples/amazon-eks-custom-amis),其中在CentOS 7和RHEL 7上配置了SELinux。这些AMI是为满足高度监管客户(如STIG、CJIS和C2S)的要求而开发的示例实现。

!!! caution
    SELinux将忽略类型为unconfined的容器。

## 工具和资源

- [SELinux Kubernetes RBAC 和为本地应用程序发布安全策略](https://platform9.com/blog/selinux-kubernetes-rbac-and-shipping-security-policies-for-on-prem-applications/)
- [Kubernetes 的迭代强化](https://jayunit100.blogspot.com/2019/07/iterative-hardening-of-kubernetes-and.html)
- [Audit2Allow](https://linux.die.net/man/1/audit2allow)
- [SEAlert](https://linux.die.net/man/8/sealert)
- [使用 Udica 为容器生成 SELinux 策略](https://www.redhat.com/en/blog/generate-selinux-policies-containers-with-udica) 介绍了一个工具，它查看容器规范文件中的 Linux 功能、端口和挂载点，并生成一组 SELinux 规则，允许容器正常运行
- [AMI 强化](https://github.com/aws-samples/amazon-eks-custom-amis#hardening) 剧本用于加固操作系统以满足不同的监管要求
- [Keiko 升级管理器](https://github.com/keikoproj/upgrade-manager) 一个来自 Intuit 的开源项目，用于协调工作节点的轮换。
- [Sysdig Secure](https://sysdig.com/products/kubernetes-security/)
- [eksctl](https://eksctl.io/)