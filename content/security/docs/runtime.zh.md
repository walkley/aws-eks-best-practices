# 运行时安全

运行时安全为您的容器在运行时提供主动保护。其思想是检测和/或防止在容器内部发生恶意活动。这可以通过Linux内核或与Kubernetes集成的内核扩展中的多种机制来实现，例如Linux功能、安全计算(seccomp)、AppArmor或SELinux。还有一些选项，如Amazon GuardDuty和第三方工具，可以帮助建立基线并检测异常活动，而无需手动配置Linux内核机制。

!!! attention
    Kubernetes当前不提供任何本地机制来将seccomp、AppArmor或SELinux配置文件加载到节点上。它们要么必须手动加载，要么在引导节点时安装。这必须在引用它们之前完成，因为调度程序不知道哪些节点有配置文件。请参阅下面如何使用工具(如Security Profiles Operator)来帮助自动将配置文件配置到节点上。

## 安全上下文和Kubernetes内置控制

许多Linux运行时安全机制与Kubernetes紧密集成，并且可以通过Kubernetes [安全上下文](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/)进行配置。其中一个选项是`privileged`标志，默认情况下为`false`,如果启用，基本上相当于主机上的root。在生产工作负载中启用特权模式几乎总是不合适的，但还有许多其他控制可以根据需要为容器提供更细粒度的权限。

### Linux功能

Linux功能允许您在不提供root用户的所有能力的情况下，向Pod或容器授予某些功能。示例包括`CAP_NET_ADMIN`,允许配置网络接口或防火墙，或`CAP_SYS_TIME`,允许操作系统时钟。

### Seccomp

通过安全计算(seccomp)，您可以防止容器化应用程序对底层主机操作系统内核进行某些系统调用。虽然Linux操作系统有几百个系统调用，但大部分都不是运行容器所必需的。通过限制容器可以进行的系统调用，您可以有效地减小应用程序的攻击面。

Seccomp通过拦截系统调用并仅允许已允许列表中的系统调用通过来工作。Docker有一个[默认](https://github.com/moby/moby/blob/master/profiles/seccomp/default.json)的seccomp配置文件，适用于大多数通用工作负载，其他容器运行时如containerd也提供了可比的默认值。您可以通过在Pod规范的`securityContext`部分添加以下内容，将容器或Pod配置为使用容器运行时的默认seccomp配置文件:

```yaml
securityContext:
  seccompProfile:
    type: RuntimeDefault
```

从1.22版本开始(alpha版本，1.27版本稳定),上述`RuntimeDefault`可以使用[单个kubelet标志](https://kubernetes.io/docs/tutorials/security/seccomp/#enable-the-use-of-runtimedefault-as-the-default-seccomp-profile-for-all-workloads)(`--seccomp-default`)在节点上的所有Pod上使用。然后，`securityContext`中指定的配置文件仅用于其他配置文件。

对于需要额外权限的情况，也可以创建自己的配置文件。手动执行这一操作可能非常繁琐，但有一些工具如[Inspektor Gadget](https://github.com/inspektor-gadget/inspektor-gadget)(在[网络安全部分](../network/)中也推荐用于生成网络策略)和[Security Profiles Operator](https://github.com/inspektor-gadget/inspektor-gadget),支持使用诸如eBPF或日志之类的工具记录基线权限要求作为seccomp配置文件。Security Profiles Operator进一步允许自动将记录的配置文件部署到节点上，供Pod和容器使用。

### AppArmor 和 SELinux

AppArmor 和 SELinux 被称为[强制访问控制或 MAC 系统](https://en.wikipedia.org/wiki/Mandatory_access_control)。它们在概念上与 seccomp 类似，但具有不同的 API 和功能，允许对特定文件系统路径或网络端口等进行访问控制。对这些工具的支持取决于 Linux 发行版，Debian/Ubuntu 支持 AppArmor，而 RHEL/CentOS/Bottlerocket/Amazon Linux 2023 支持 SELinux。另请参阅[基础设施安全部分](../hosts/#run-selinux)以进一步讨论 SELinux。

AppArmor 和 SELinux 都与 Kubernetes 集成，但截至 Kubernetes 1.28，AppArmor 配置文件必须通过[注解](https://kubernetes.io/docs/tutorials/security/apparmor/#securing-a-pod)指定，而 SELinux 标签可以直接通过安全上下文中的 [SELinuxOptions](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.28/#selinuxoptions-v1-core) 字段设置。

与 seccomp 配置文件一样，上述提到的安全配置文件操作员可以帮助将配置文件部署到集群中的节点。(未来，该项目还旨在为 AppArmor 和 SELinux 生成配置文件，就像它为 seccomp 所做的那样。)

## 建议

### 使用 Amazon GuardDuty 对您的 EKS 环境进行运行时监控和检测威胁

如果您目前没有解决方案来持续监控 EKS 运行时并分析 EKS 审计日志，并扫描恶意软件和其他可疑活动，Amazon 强烈建议希望以简单、快速、安全、可扩展和经济高效的一键式方式保护其 AWS 环境的客户使用 [Amazon GuardDuty](https://aws.amazon.com/guardduty/)。Amazon GuardDuty 是一种安全监控服务，可分析和处理基础数据源，如 AWS CloudTrail 管理事件、AWS CloudTrail 事件日志、VPC 流日志(来自 Amazon EC2 实例)、Kubernetes 审计日志和 DNS 日志。它还包括 EKS 运行时监控。它使用不断更新的威胁情报源，如恶意 IP 地址和域名列表，以及机器学习来识别您的 AWS 环境中意外、可能未经授权和恶意活动。这可能包括特权升级、使用已暴露的凭证或与恶意 IP 地址、域进行通信、您的 Amazon EC2 实例和 EKS 容器工作负载上存在恶意软件，或发现可疑的 API 活动等问题。GuardDuty 通过在 GuardDuty 控制台或通过 Amazon EventBridge 生成您可以查看的安全发现结果，来通知您 AWS 环境的状态。GuardDuty 还支持您将发现结果导出到 Amazon 简单存储服务 (S3) 存储桶，并与其他服务(如 AWS Security Hub 和 Detective) 集成。

观看此 AWS 在线技术讨论 ["使用 Amazon GuardDuty 增强对 Amazon EKS 的威胁检测 - AWS 在线技术讨论"](https://www.youtube.com/watch?v=oNHGRRroJuE),了解如何在几分钟内一步步启用这些额外的 EKS 安全功能。

### 可选:使用第三方解决方案进行运行时监控

创建和管理seccomp和Apparmor配置文件可能会很困难，如果您不熟悉Linux安全性的话。如果您没有时间来熟练掌握，可以考虑使用第三方商业解决方案。很多解决方案已经不再局限于静态配置文件，如Apparmor和seccomp，而是开始使用机器学习来阻止或警告可疑活动。下面的[工具](#tools-and-resources)部分列出了其中一些解决方案。您还可以在[AWS Marketplace for Containers](https://aws.amazon.com/marketplace/features/containers)上找到更多选项。

### 在编写seccomp策略之前，考虑添加/删除Linux功能

功能涉及可通过syscall访问的各种内核函数检查。如果检查失败，syscall通常会返回错误。检查可以在特定syscall的开头立即执行，也可以在可能通过多个不同syscall访问的内核区域中执行(例如写入特定的特权文件)。另一方面，seccomp是一种syscall过滤器，在运行syscall之前应用于所有syscall。进程可以设置一个过滤器，允许它们撤销运行某些syscall或某些syscall的特定参数的权限。

在使用seccomp之前，请考虑添加/删除Linux功能是否可以满足您的需求。有关更多信息，请参阅[为容器设置功能](https://kubernetes.io/docs/tasks/configure-pod-container/security-context/#set-capabilities-for-a-container)。

### 查看是否可以通过使用Pod安全策略(PSP)来实现您的目标

Pod安全策略提供了许多不同的方式来改善您的安全态势，而不会引入过多的复杂性。在着手构建seccomp和Apparmor配置文件之前，请先探索PSP中提供的选项。

!!! warning
    从Kubernetes 1.25版本开始，PSP已被移除并替换为[Pod安全准入控制器](https://kubernetes.io/docs/concepts/security/pod-security-admission/)。第三方替代方案包括OPA/Gatekeeper和Kyverno。可以从GitHub上的[Gatekeeper库](https://github.com/open-policy-agent/gatekeeper-library/tree/master/library/pod-security-policy)仓库中获取实现PSP中常见策略的Gatekeeper约束和约束模板集合。而在[Kyverno策略库](https://main.kyverno.io/policies/)中也可以找到许多PSP的替代方案，包括完整的[Pod安全标准](https://kubernetes.io/docs/concepts/security/pod-security-standards/)集合。

## 工具和资源

- [7 件你在开始之前应该知道的事情](https://itnext.io/seccomp-in-kubernetes-part-i-7-things-you-should-know-before-you-even-start-97502ad6b6d6)
- [AppArmor 加载器](https://github.com/kubernetes/kubernetes/tree/master/test/images/apparmor-loader)
- [使用配置文件设置节点](https://kubernetes.io/docs/tutorials/clusters/apparmor/#setting-up-nodes-with-profiles)
- [安全配置文件操作员](https://github.com/kubernetes-sigs/security-profiles-operator) 是一个 Kubernetes 增强功能，旨在让用户更容易在 Kubernetes 集群中使用 SELinux、seccomp 和 AppArmor。它提供了从运行中的工作负载生成配置文件以及将配置文件加载到 Kubernetes 节点上以供 Pod 使用的功能。
- [Inspektor Gadget](https://github.com/inspektor-gadget/inspektor-gadget) 允许检查、跟踪和分析 Kubernetes 上许多运行时行为方面，包括协助生成 seccomp 配置文件。
- [Aqua](https://www.aquasec.com/products/aqua-cloud-native-security-platform/)
- [Qualys](https://www.qualys.com/apps/container-security/)
- [Stackrox](https://www.stackrox.com/use-cases/threat-detection/)
- [Sysdig Secure](https://sysdig.com/products/kubernetes-security/)
- [Prisma](https://docs.paloaltonetworks.com/cn-series)
- [SUSE 的 NeuVector](https://www.suse.com/neuvector/) 开源、零信任容器安全平台，提供进程配置文件规则和文件访问规则。