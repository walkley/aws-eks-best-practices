# 运行异构工作负载¶

Kubernetes支持异构集群，在同一个集群中可以混合使用Linux和Windows节点。在该集群中，您可以混合运行在Linux上的Pod和在Windows上的Pod。您甚至可以在同一个集群中运行多个版本的Windows。但是，在做出这个决定时，需要考虑一些因素(如下所述)。

# 将POD分配给节点的最佳实践

为了将Linux和Windows工作负载保留在各自的特定操作系统节点上，您需要使用节点选择器和污点/容忍度的组合。在异构环境中调度工作负载的主要目标是避免破坏现有Linux工作负载的兼容性。

## 确保特定操作系统的工作负载落在适当的容器主机上

用户可以使用nodeSelectors确保Windows容器可以调度到适当的主机上。当今所有Kubernetes节点都具有以下默认标签:

    kubernetes.io/os = [windows|linux]
    kubernetes.io/arch = [amd64|arm64|...]

如果Pod规范不包含诸如``"kubernetes.io/os": windows``的nodeSelector，则该Pod可能会被调度到任何主机，无论是Windows还是Linux。这可能会有问题，因为Windows容器只能在Windows上运行，而Linux容器只能在Linux上运行。

在企业环境中，拥有大量预先存在的Linux容器部署以及现成的配置生态系统(如Helm charts)是很常见的。在这种情况下，您可能不愿意更改部署的nodeSelectors。**替代方案是使用污点**。

例如: `--register-with-taints='os=windows:NoSchedule'`

如果您使用EKS，eksctl提供了通过clusterConfig应用污点的方法:

```yaml
NodeGroups:
  - name: windows-ng
    amiFamily: WindowsServer2022FullContainer
    ...
    labels:
      nodeclass: windows2022
    taints:
      os: "windows:NoSchedule"
```

将污点添加到所有Windows节点后，调度器将不会在这些节点上调度Pod，除非它们能够容忍该污点。Pod清单示例:

```yaml
nodeSelector:
    kubernetes.io/os: windows
tolerations:
    - key: "os"
      operator: "Equal"
      value: "windows"
      effect: "NoSchedule"
```

## 在同一集群中处理多个Windows版本

每个Pod使用的Windows容器基础镜像必须与节点使用的相同内核版本匹配。如果您希望在同一集群中使用多个Windows Server版本，那么您应该设置额外的节点标签、nodeSelector或利用名为**windows-build**的标签。

Kubernetes 1.17自动为Windows节点添加了一个新的标签**node.kubernetes.io/windows-build**,以简化同一集群中多个Windows版本的管理。如果您运行的是旧版本，则建议手动为Windows节点添加此标签。

该标签反映了Windows的主版本号、次版本号和内部版本号，这些版本号必须匹配才能保证兼容性。下面是目前每个Windows Server版本使用的值。

值得注意的是，Windows Server正在将Long-Term Servicing Channel(LTSC)作为主要发布渠道。Windows Server Semi-Annual Channel(SAC)已于2022年8月9日停止使用。将来不会再有Windows Server的SAC版本。

| 产品名称 | 内部版本号 |
| -------- | -------- |
| Server full 2022 LTSC    | 10.0.20348    |
| Server core 2019 LTSC    | 10.0.17763    |

可以通过以下命令检查操作系统的内部版本号:

```bash    
kubectl get nodes -o wide
```

KERNEL-VERSION输出与Windows操作系统的内部版本号匹配。

```bash
名称                          状态    角色    年龄  版本                  内部IP        外部IP         操作系统映像                     内核版本                        容器运行时
ip-10-10-2-235.ec2.internal   就绪    <none>   23m   v1.24.7-eks-fb459a0    10.10.2.235   3.236.30.157    Windows Server 2022 Datacenter   10.0.20348.1607                 containerd://1.6.6
ip-10-10-31-27.ec2.internal   就绪    <none>   23m   v1.24.7-eks-fb459a0    10.10.31.27   44.204.218.24   Windows Server 2019 Datacenter   10.0.17763.4131                 containerd://1.6.6
ip-10-10-7-54.ec2.internal    就绪    <none>   31m   v1.24.11-eks-a59e1f0   10.10.7.54    3.227.8.172     Amazon Linux 2                   5.10.173-154.642.amzn2.x86_64   containerd://1.6.19
```

下面的示例将额外的 nodeSelector 应用于 pod 清单，以便在运行不同 Windows 节点组操作系统版本时匹配正确的 Windows 构建版本。

```yaml
nodeSelector:
    kubernetes.io/os: windows
    node.kubernetes.io/windows-build: '10.0.20348'
tolerations:
    - key: "os"
    operator: "Equal"
    value: "windows"
    effect: "NoSchedule"
```

## 使用 RuntimeClass 简化 Pod 清单中的 NodeSelector 和 Toleration

您还可以使用 RuntimeClass 来简化使用污点和容忍度的过程。这可以通过创建一个用于封装这些污点和容忍度的 RuntimeClass 对象来实现。

通过运行以下清单创建 RuntimeClass:

```yaml
apiVersion: node.k8s.io/v1beta1
kind: RuntimeClass
metadata:
  name: windows-2022
handler: 'docker'
scheduling:
  nodeSelector:
    kubernetes.io/os: 'windows'
    kubernetes.io/arch: 'amd64'
    node.kubernetes.io/windows-build: '10.0.20348'
  tolerations:
  - effect: NoSchedule
    key: os
    operator: Equal
    value: "windows"
```

一旦创建了 Runtimeclass，就可以将其作为规范分配给 Pod 清单:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: iis-2022
  labels:
    app: iis-2022
spec:
  replicas: 1
  template:
    metadata:
      name: iis-2022
      labels:
        app: iis-2022
    spec:
      runtimeClassName: windows-2022
      containers:
      - name: iis
```

## 托管节点组支持
为了帮助客户以更加简化的方式运行其Windows应用程序，AWS于2022年12月15日推出了对Amazon [EKS托管节点组(MNG)支持Windows容器](https://aws.amazon.com/about-aws/whats-new/2022/12/amazon-eks-automated-provisioning-lifecycle-management-windows-containers/)的支持。为了帮助统一运维团队的工作流程，[Windows MNG](https://docs.aws.amazon.com/eks/latest/userguide/managed-node-groups.html)使用与[Linux MNG](https://docs.aws.amazon.com/eks/latest/userguide/managed-node-groups.html)相同的工作流程和工具进行启用。支持Windows Server 2019和2022的完整版和核心版AMI(Amazon Machine Image)。

以下AMI家族支持托管节点组(MNG)。

| AMI家族 |
| ---------   | 
| WINDOWS_CORE_2019_x86_64    | 
| WINDOWS_FULL_2019_x86_64    | 
| WINDOWS_CORE_2022_x86_64    | 
| WINDOWS_FULL_2022_x86_64    | 

## 其他文档


AWS官方文档:
https://docs.aws.amazon.com/eks/latest/userguide/windows-support.html

要更好地了解Pod网络(CNI)的工作原理，请查看以下链接: https://docs.aws.amazon.com/eks/latest/userguide/pod-networking.html

AWS博客关于在EKS上部署Windows托管节点组:
https://aws.amazon.com/blogs/containers/deploying-amazon-eks-windows-managed-node-groups/