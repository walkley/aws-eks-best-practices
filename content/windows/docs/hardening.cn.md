# Windows 工作节点加固

操作系统加固是一种组合操作系统配置、打补丁和删除不必要的软件包的方法，旨在锁定系统并减少攻击面。最佳做法是准备自己的带有公司所需加固配置的 EKS 优化 Windows AMI。

AWS 每月都会提供一个新的 EKS 优化 Windows AMI，其中包含最新的 Windows Server 安全补丁。但是，无论使用自管理还是托管节点组，用户仍有责任通过应用必要的操作系统配置来加固其 AMI。

微软提供了一系列工具，如 [Microsoft Security Compliance Toolkit](https://www.microsoft.com/en-us/download/details.aspx?id=55319) 和 [Security Baselines](https://docs.microsoft.com/en-us/windows/security/threat-protection/windows-security-baselines),可帮助您根据安全策略需求实现加固。[CIS 基准](https://learn.cisecurity.org/benchmarks?_gl=1*eoog69*_ga*MTgzOTM2NDE0My4xNzA0NDgwNTcy*_ga_3FW1B1JC98*MTcwNDQ4MDU3MS4xLjAuMTcwNDQ4MDU3MS4wLjAuMA..*_ga_N70Z2MKMD7*MTcwNDQ4MDU3MS4xLjAuMTcwNDQ4MDU3MS42MC4wLjA.) 也可用，并且应该在 Amazon EKS 优化 Windows AMI 之上实施，以用于生产环境。

## 使用 Windows Server Core 减少攻击面

Windows Server Core 是 [EKS 优化 Windows AMI](https://docs.aws.amazon.com/eks/latest/userguide/eks-optimized-windows-ami.html) 中可用的一种最小安装选项。部署 Windows Server Core 有几个好处。首先，它的磁盘占用空间相对较小，Server Core 为 6GB，而 Windows Server 带桌面体验为 10GB。其次，由于其较小的代码库和可用 API，它具有较小的攻击面。

AWS 每月都会为客户提供新的 Amazon EKS 优化的 Windows AMI，其中包含最新的 Microsoft 安全补丁，无论 Amazon EKS 支持的版本如何。作为最佳实践，必须使用基于最新 Amazon EKS 优化 AMI 的新节点替换 Windows 工作节点。任何运行超过 45 天且未更新或未替换节点的操作都不符合安全最佳实践。

## 避免 RDP 连接

远程桌面协议 (RDP) 是 Microsoft 开发的一种连接协议，用于为用户提供图形界面，以便通过网络连接到另一台 Windows 计算机。

作为最佳实践，您应该将 Windows 工作节点视为临时主机。这意味着不进行管理连接、不进行更新和不进行故障排除。任何修改和更新都应作为新的自定义 AMI 实施，并通过更新自动伸缩组进行替换。请参阅 **Patching Windows Servers and Containers** 和 **Amazon EKS optimized Windows AMI management**。

在部署期间通过将 ssh 属性的值设置为 **false** 来禁用 Windows 节点上的 RDP 连接，如下例所示：

```yaml
nodeGroups:
- name: windows-ng
  instanceType: c5.xlarge
  minSize: 1
  volumeSize: 50
  amiFamily: WindowsServer2019CoreContainer
  ssh:
    allow: false
```

如果需要访问 Windows 节点，请使用 [AWS System Manager Session Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html) 通过 AWS 控制台和 SSM 代理建立安全的 PowerShell 会话。要了解如何实施该解决方案，请观看 [Securely Access Windows Instances Using AWS Systems Manager Session Manager](https://www.youtube.com/watch?v=nt6NTWQ-h6o)

为了使用 System Manager Session Manager，必须将附加 IAM 策略应用于用于启动 Windows 工作节点的 IAM 角色。下面是一个示例，其中在 `eksctl` 集群清单中指定了 **AmazonSSMManagedInstanceCore**：

```yaml
 nodeGroups:
- name: windows-ng
  instanceType: c5.xlarge
  minSize: 1
  volumeSize: 50
  amiFamily: WindowsServer2019CoreContainer
  ssh:
    allow: false
  iam:
    attachPolicyARNs:
      - arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy
      - arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy
      - arn:aws:iam::aws:policy/ElasticLoadBalancingFullAccess
      - arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly
      - arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
```

## Amazon Inspector
> [Amazon Inspector](https://aws.amazon.com/inspector/) 是一项自动化安全评估服务，可帮助提高部署在AWS上的应用程序的安全性和合规性。Amazon Inspector会自动评估应用程序是否存在暴露、漏洞和偏离最佳实践的情况。执行评估后，Amazon Inspector会生成一份详细的安全发现列表，按严重级别对其进行优先级排序。您可以直接查看这些发现，或作为详细评估报告的一部分进行查看，这些报告可通过Amazon Inspector控制台或API获取。

可以使用Amazon Inspector在Windows工作节点上运行CIS基准评估，只需执行以下任务即可在Windows Server Core上安装:

1. 下载以下.exe文件:
https://inspector-agent.amazonaws.com/windows/installer/latest/AWSAgentInstall.exe
2. 将代理传输到Windows工作节点。
3. 在PowerShell上运行以下命令以安装Amazon Inspector代理: `.\AWSAgentInstall.exe /install`

下面是首次运行后的输出。如您所见，它根据[CVE](https://cve.mitre.org/)数据库生成了发现结果。您可以使用这些结果来加固您的工作节点或基于经过加固的配置创建AMI。

![](./images/inspector-agent.png)

有关Amazon Inspector的更多信息，包括如何安装Amazon Inspector代理、设置CIS基准评估和生成报告，请观看[使用Amazon Inspector改善Windows工作负载的安全性和合规性](https://www.youtube.com/watch?v=nIcwiJ85EKU)视频。

## Amazon GuardDuty
> [Amazon GuardDuty](https://aws.amazon.com/guardduty/)是一种威胁检测服务，可持续监控恶意活动和未经授权的行为，以保护您的AWS账户、工作负载和存储在Amazon S3中的数据。借助云，收集和汇总账户和网络活动变得更加简单，但安全团队持续分析事件日志数据以发现潜在威胁可能会耗费大量时间。

通过使用Amazon GuardDuty，您可以看到针对Windows工作节点的恶意活动，如RDP暴力破解和端口探测攻击。

观看[使用Amazon GuardDuty对Windows工作负载进行威胁检测](https://www.youtube.com/watch?v=ozEML585apQ)视频，了解如何在优化的EKS Windows AMI上实施和运行CIS基准。

## Windows上Amazon EC2的安全性
阅读[Amazon EC2 Windows实例的安全最佳实践](https://docs.aws.amazon.com/AWSEC2/latest/WindowsGuide/ec2-security.html),在每一层实施安全控制。